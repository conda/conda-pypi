"""
Install a wheel / install a conda.
"""

from __future__ import annotations

import base64
import logging
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import BinaryIO, Iterable
from unittest.mock import patch

from conda.cli.main import main_subshell
from conda.core.package_cache_data import PackageCacheData
from installer import install
from installer.destinations import SchemeDictionaryDestination
from installer.records import Hash, RecordEntry
from installer.sources import WheelFile
from installer.utils import Scheme, construct_record_file, copyfileobj_with_hashing

from conda_pypi.conda_build_utils import PathType

log = logging.getLogger(__name__)


class _CondaWheelDestination(SchemeDictionaryDestination):
    """Suppress entry-point script generation.

    Conda creates entry-point scripts at install time from info/link.json
    (CEP-34), so writing them here would only embed a hardcoded shebang
    that breaks in other environments.
    """

    conda_builder: tarfile.TarFile

    def __init__(self, *args, conda_builder: tarfile.TarFile, **kwargs):
        super().__init__(*args, **kwargs)
        self.conda_builder = conda_builder
        self.package_paths: list[dict] = []
        self._members: set[str] = set()

    def write_script(self, name, module, attr, section):
        log.debug(f"Skipping script generation for {name} (handled via link.json)")
        return RecordEntry(path=name, hash_=None, size=None)

    def write_to_fs(
        self,
        scheme: Scheme,
        path: str,
        stream: BinaryIO,
        is_executable: bool,
    ) -> RecordEntry:
        """
        In installer==1.0.0, the SchemeDirectoryDestination() superclass
        delegates all write_*() functions here.
        """
        archive_path = str(Path(self.scheme_dict[scheme], path).as_posix())

        if ".." in archive_path.split("/"):
            raise ValueError(f"Path traversal detected: {archive_path}")

        tar_info = tarfile.TarInfo(name=archive_path)
        tar_info.mode = 0o775 if is_executable else 0o664

        with tempfile.SpooledTemporaryFile() as buffer:
            hash_, size = copyfileobj_with_hashing(stream, buffer, self.hash_algorithm)

            # hash_ is urlsafe-b64encode without padding. self.hash_algorithm is
            # "sha256" although it is implemented to be flexible on the wheel
            # side; but conda requires sha256.
            pad = "=" * (-len(hash_) % 4)
            hash_hex = base64.urlsafe_b64decode(hash_ + pad).hex()

            # Almost never happens, OK to waste effort before error.
            if archive_path in self._members:
                message = f"File already exists: {archive_path}"
                raise_exists = True
                if self.overwrite_existing:
                    p = next(p for p in self.package_paths if p["_path"] == archive_path)
                    if p["sha256"] == hash_hex:
                        log.warning(
                            "Wheel has overlapping paths %s with same content.", archive_path
                        )
                        raise_exists = False
                        message = (
                            f"{message}; overwrite_existing not available in write-to-archive."
                        )
                if raise_exists or not self.overwrite_existing:
                    raise FileExistsError(message)
            self._members.add(archive_path)

            tar_info.size = size
            buffer.seek(0)

            # add only happens here
            self.conda_builder.addfile(tar_info, buffer)

        self.package_paths.append(
            {
                "_path": archive_path,
                "path_type": str(PathType.hardlink),
                "sha256": hash_hex,
                "size_in_bytes": size,
            }
        )

        return RecordEntry(path, Hash(self.hash_algorithm, hash_), size)

    def finalize_installation(
        self,
        scheme: Scheme,
        record_file_path: str,
        records: Iterable[tuple[Scheme, RecordEntry]],
    ):
        """Finalize installation, by writing the ``RECORD`` file.
        Account for relpath() differences between superclass (installs to a real
        filesystem) and _CondaWheelDestination (creates an archive). Unlike
        superclass, doesn't compile bytecode.
        """

        def prefix_for_scheme(file_scheme: str) -> str | None:
            if file_scheme == scheme:
                return None

            source_prefix = self.scheme_dict[file_scheme] or "."
            target_prefix = self.scheme_dict[scheme] or "."
            path = os.path.relpath(source_prefix, start=target_prefix)
            return path + "/"

        record_list = list(records)
        with construct_record_file(record_list, prefix_for_scheme) as record_stream:
            self.write_to_fs(scheme, record_file_path, record_stream, is_executable=False)


def install_installer_to_tar(
    python_executable: str,
    whl: Path,
    tar: tarfile.TarFile,
) -> list[dict]:
    scheme = {
        "purelib": "site-packages",
        "platlib": "site-packages",
        "scripts": "bin",
        "data": "",
        "headers": "include",
    }

    destination = _CondaWheelDestination(
        scheme_dict=scheme,
        interpreter=str(python_executable),
        script_kind="posix",
        overwrite_existing=True,
        conda_builder=tar,
    )

    with WheelFile.open(whl) as source:
        install(
            source=source,
            destination=destination,
            # Additional metadata that is generated by the installation tool.
            additional_metadata={
                "INSTALLER": b"conda-pypi\n",
            },
        )

    return destination.package_paths


def install_pip(python_executable: str, whl: Path, build_path: Path):
    command = [
        python_executable,
        "-m",
        "pip",
        "install",
        "--quiet",
        "--no-deps",
        "--target",
        str(build_path / "site-packages"),
        whl,
    ]
    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    log.debug(f"Installed to {build_path}")


def install_ephemeral_conda(prefix: Path, package: Path):
    """
    Install [editable] conda package without adding it to the environment's
    package cache, since we don't want to accidentally re-install "a link to a
    source checkout" elsewhere.

    Installing packages directly from a file does not resolve dependencies.
    Should we automatically install the project's dependencies also?
    """
    persistent_pkgs = PackageCacheData.first_writable().pkgs_dir
    with (
        tempfile.TemporaryDirectory(dir=persistent_pkgs, prefix="ephemeral") as cache_dir,
        patch.dict(os.environ, {"CONDA_PKGS_DIRS": cache_dir}),
    ):
        main_subshell("install", "--prefix", str(prefix), str(package))
