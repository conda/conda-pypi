"""
Create .conda packages from wheels.

Create wheels from pypa projects.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import os
import sys
import tarfile
import tempfile
import zipfile
from importlib.metadata import PathDistribution
from pathlib import Path

from build import ProjectBuilder
from conda.common.compat import on_win
from conda.common.path.windows import win_path_to_unix
from conda_package_streaming.create import conda_builder
from installer.utils import parse_wheel_filename

from conda_pypi import dependencies, installer, paths
from conda_pypi.conda_build_utils import PathType, sha256_checksum
from conda_pypi.license_files import copy_into_info_licenses
from conda_pypi.translate import CondaMetadata
from conda_pypi.utils import sha256_as_base64url

log = logging.getLogger(__name__)


def filter(tarinfo):
    """
    Anonymize uid/gid and exclude .git directories.
    """
    if tarinfo.name.endswith(".git"):
        return None
    tarinfo.uid = tarinfo.gid = 0
    tarinfo.uname = tarinfo.gname = ""
    return tarinfo


# see conda_build.build.build_info_files_json_v1
def paths_json(base: Path | str):
    """
    Build simple paths.json with only 'hardlink' or 'symlink' types.
    """
    base = str(base)

    if not base.endswith(os.sep):
        base = base + os.sep

    return {
        "paths": sorted(_paths(base, base), key=lambda entry: entry["_path"]),
        "paths_version": 1,
    }


def _paths(base, path, filter=lambda x: x.name != ".git"):
    for entry in os.scandir(path):
        relative_path = entry.path[len(base) :]
        if on_win:
            relative_path = win_path_to_unix(relative_path)
        if relative_path == "info" or not filter(entry):
            continue
        if entry.is_dir():
            yield from _paths(base, entry.path, filter=filter)
        elif entry.is_file() or entry.is_symlink():
            try:
                st_size = entry.stat().st_size
            except FileNotFoundError:
                st_size = 0  # symlink to nowhere
            yield {
                "_path": relative_path,
                "path_type": str(PathType.softlink if entry.is_symlink() else PathType.hardlink),
                "sha256": sha256_checksum(entry.path, entry),
                "size_in_bytes": st_size,
            }
        else:
            log.debug(f"Not regular file '{entry}'")
            # will Python's tarfile add pipes, device nodes to the archive?


def json_dumps(object):
    """
    Consistent json formatting.
    """
    return json.dumps(object, indent=2, sort_keys=True)


def _add_to_tar(tar, name: str, data: bytes) -> None:
    tar_info = tarfile.TarInfo(name)
    tar_info.size = len(data)
    tar.addfile(tar_info, io.BytesIO(data))


def build_pypa(
    path: Path,
    output_path,
    prefix: Path,
    distribution="editable",
):
    """
    Args:
        distribution: "editable" or "wheel"
    """
    python_executable = str(paths.get_python_executable(prefix))

    builder = ProjectBuilder(path, python_executable=python_executable)

    def install_missing(requirements):
        """
        Check if requirements are missing. If so, invoke conda to install into target prefix.
        """
        for _retry in range(2):
            try:
                missing = dependencies.check_dependencies(requirements, prefix=prefix)
                if missing:
                    dependencies.ensure_requirements(missing, prefix=prefix)
                    continue
                break
            except dependencies.MissingDependencyError as e:
                dependencies.ensure_requirements(e.dependencies, prefix=prefix)

    build_system_requires = builder.build_system_requires
    log.debug(f"Ensure requirements for build system: {build_system_requires}")
    install_missing(build_system_requires)

    requirements = builder.get_requires_for_build(distribution)
    log.debug(f"Additional requirements for {distribution}: {requirements}")
    install_missing(requirements)

    editable_file = builder.build(distribution, output_path)
    log.debug(f"The wheel is at {editable_file}")

    return editable_file


def build_conda(
    whl: Path,
    build_path: Path,
    output_path: Path,
    python_executable,
    project_path: Path | None = None,
    test_dir: Path | None = None,
    is_editable=False,
    pypi_to_conda_name_mapping: dict | None = None,
) -> Path:
    if not build_path.exists():
        build_path.mkdir()

    with (
        zipfile.ZipFile(whl) as wheel_zip,
        tempfile.TemporaryDirectory(prefix="dist-info") as dist_info_tmp,
    ):
        parsed = parse_wheel_filename(whl.name)
        dist_info_name = f"{parsed.distribution}-{parsed.version}.dist-info"

        dist_info_tmp_path = Path(dist_info_tmp)
        prefix = f"{dist_info_name}/"
        for zip_info in wheel_zip.infolist():
            if zip_info.filename.startswith(prefix):
                wheel_zip.extract(zip_info, dist_info_tmp_path)
        dist_info = dist_info_tmp_path / dist_info_name
        wheel_zip.close()  # so installer has exclusive access below

        # This is mainly for METADATA and entry_points.txt. It would be
        # straightforward to write or find a WheelDistribution() to grab these
        # files from the wheel archive directly, instead of PathDistribution():
        metadata = CondaMetadata.from_distribution(
            PathDistribution(dist_info), pypi_to_conda_name_mapping
        )
        record = metadata.package_record.to_index_json()
        file_id = f"{record['name']}-{record['version']}-{record['build']}"

        with conda_builder(file_id, output_path) as tar:
            package_paths = installer.install_installer_to_tar(python_executable, whl, tar)

            # XXX set build string as hash of pypa metadata so that conda can re-install
            # when project gains new entry-points, dependencies?

            _add_to_tar(tar, "info/index.json", json_dumps(record).encode("utf-8"))
            _add_to_tar(tar, "info/about.json", json_dumps(metadata.about).encode("utf-8"))

            info_tmp = build_path / "info"
            copy_into_info_licenses(dist_info, info_tmp, metadata.metadata)
            licenses_dir = info_tmp / "licenses"
            if licenses_dir.exists():
                for license_path in sorted(licenses_dir.rglob("*")):
                    if not license_path.is_file():
                        continue
                    rel = license_path.relative_to(info_tmp).as_posix()
                    _add_to_tar(tar, f"info/{rel}", license_path.read_bytes())

            # used especially for console_scripts
            if link_json := metadata.link_json():
                _add_to_tar(tar, "info/link.json", json_dumps(link_json).encode("utf-8"))

            # Allow pip to list us as editable or show the path to our project.
            # XXX leaks path
            if project_path:
                direct_url = project_path.absolute().as_uri()
                direct_url_bytes = json.dumps(
                    {"dir_info": {"editable": is_editable}, "url": direct_url}
                ).encode("utf-8")
                direct_url_member = f"site-packages/{dist_info_name}/direct_url.json"
                _add_to_tar(tar, direct_url_member, direct_url_bytes)
                package_paths.append(
                    {
                        "_path": direct_url_member,
                        "path_type": str(PathType.hardlink),
                        "sha256": hashlib.sha256(direct_url_bytes).hexdigest(),
                        "size_in_bytes": len(direct_url_bytes),
                    }
                )

            if test_dir:
                for test_path in sorted(test_dir.rglob("*")):
                    if not test_path.is_file():
                        continue
                    rel = test_path.relative_to(test_dir).as_posix()
                    _add_to_tar(tar, f"info/test/{rel}", test_path.read_bytes())

            paths_data = json_dumps(
                {
                    "paths": sorted(package_paths, key=lambda entry: entry["_path"]),
                    "paths_version": 1,
                }
            ).encode("utf-8")
            _add_to_tar(tar, "info/paths.json", paths_data)

    return output_path / f"{file_id}.conda"


def update_RECORD(record_path: Path, base_path: Path, changed_path: Path):
    """
    Rewrite RECORD with new size, checksum for updated_file.
    """
    # note `installer` also has code to handle RECORD
    record_text = record_path.read_text()
    record_rows = list(csv.reader(record_text.splitlines()))

    relpath = str(changed_path.relative_to(base_path)).replace(os.sep, "/")
    for row in record_rows:
        if row[0] == relpath:
            data = changed_path.read_bytes()
            row[1] = f"sha256={sha256_as_base64url(data)}"
            row[2] = str(len(data))

    with record_path.open(mode="w", newline="", encoding="utf-8") as record_file:
        writer = csv.writer(record_file)
        writer.writerows(record_rows)


def pypa_to_conda(
    project,
    prefix: Path,
    distribution="editable",
    output_path: Path | None = None,
    test_dir: Path | None = None,
    pypi_to_conda_name_mapping: dict | None = None,
):
    project = Path(project)

    # Should this logic be moved to the caller?
    if not output_path:
        output_path = project / "build"
        if not output_path.exists():
            output_path.mkdir()

    with tempfile.TemporaryDirectory(prefix="conda") as tmp_path:
        tmp_path = Path(tmp_path)

        normal_wheel = build_pypa(
            Path(project), tmp_path, prefix=prefix, distribution=distribution
        )

        build_path = tmp_path / "build"

        package_conda = build_conda(
            Path(normal_wheel),
            build_path,
            output_path or tmp_path,
            sys.executable,
            project_path=project,
            test_dir=test_dir,
            is_editable=distribution == "editable",
            pypi_to_conda_name_mapping=pypi_to_conda_name_mapping,
        )

    return package_conda
