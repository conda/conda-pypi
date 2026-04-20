import json
from os import PathLike
from pathlib import Path
from typing import BinaryIO, Iterable, Literal, Tuple

import installer.utils
from installer.destinations import WheelDestination
from installer.records import Hash, RecordEntry
from installer.sources import WheelFile
from installer.utils import Scheme

from conda_pypi.license_files import copy_into_info_licenses, package_metadata_from_metadata_body
from conda_pypi.utils import sha256_base64url_to_hex

# Maps wheel scheme names to their conda package directory prefix.
# An empty string means files go directly under the package root (env prefix).
SCHEME_TO_CONDA_PREFIX: dict[Scheme, str] = {
    "purelib": "site-packages",
    "platlib": "site-packages",
    "scripts": "bin",
    "data": "",
    "headers": "include",
}


# inline version of
# from conda.gateways.disk.create import write_as_json_to_file
def write_as_json_to_file(file_path, obj):
    json_str = json.dumps(obj, indent=2, sort_keys=True, separators=(",", ":"))
    Path(file_path).write_text(json_str, encoding="utf-8")


class MyWheelDestination(WheelDestination):
    def __init__(self, target_full_path: str | Path, source: WheelFile):
        self.target_full_path = Path(target_full_path)
        self.sp_dir = self.target_full_path / "site-packages"
        self.entry_points = []
        self.source = source

    def write_script(
        self, name: str, module: str, attr: str, section: Literal["console"] | Literal["gui"]
    ) -> RecordEntry:
        # TODO check if console/gui
        entry_point = f"{name} = {module}:{attr}"
        self.entry_points.append(entry_point)
        return RecordEntry(
            path=f"../../../bin/{name}",
            hash_=None,
            size=None,
        )

    def write_file(
        self, scheme: Scheme, path: str | PathLike, stream: BinaryIO, is_executable: bool
    ) -> RecordEntry:
        if scheme not in SCHEME_TO_CONDA_PREFIX:
            raise ValueError(f"Unsupported scheme: {scheme}")

        path = Path(path).as_posix()
        conda_prefix = SCHEME_TO_CONDA_PREFIX[scheme]
        if conda_prefix:
            dest_path = self.target_full_path / conda_prefix / path
        else:
            dest_path = self.target_full_path / path
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        with dest_path.open("wb") as dest:
            hash_, size = installer.utils.copyfileobj_with_hashing(
                source=stream,
                dest=dest,
                hash_algorithm="sha256",
            )

        if is_executable:
            installer.utils.make_file_executable(dest_path)

        return RecordEntry(
            path=path,
            hash_=Hash("sha256", hash_),
            size=size,
        )

    def _create_conda_metadata(
        self, records: Iterable[Tuple[Scheme, RecordEntry]], source: WheelFile
    ) -> None:
        info_dir = self.target_full_path / "info"
        info_dir.mkdir(exist_ok=True)

        # link.json
        link_json_data = {
            "noarch": {
                "type": "python",
            },
            "package_metadata_version": 1,
        }
        if self.entry_points:
            link_json_data["noarch"]["entry_points"] = self.entry_points
        write_as_json_to_file(info_dir / "link.json", link_json_data)

        # paths.json
        paths = []
        for scheme, record in records:
            if record.path.startswith(".."):
                # entry points from write_script() use relative paths like "../../../bin/<name>"
                continue
            conda_prefix = SCHEME_TO_CONDA_PREFIX[scheme]
            conda_path = f"{conda_prefix}/{record.path}" if conda_prefix else record.path
            path = {
                "_path": conda_path,
                "path_type": "hardlink",
                "sha256": sha256_base64url_to_hex(record.hash_.value if record.hash_ else None),
                "size_in_bytes": record.size,
            }
            paths.append(path)
        paths_json_data = {
            "paths": paths,
            "paths_version": 1,
        }
        write_as_json_to_file(info_dir / "paths.json", paths_json_data)

        # index.json
        # Set fn to include the build string AND extension so _get_json_fn() works correctly
        # Format: name-version-build.whl (e.g., "requests-2.28.0-pypi_0.whl")
        # The extension is required because _get_json_fn() uses endswith() to detect package type
        package_name = str(source.distribution)
        package_version = str(source.version)
        build_string = "pypi_0"
        fn = f"{package_name}-{package_version}-{build_string}.whl"

        index_json_data = {
            "name": package_name,
            "version": package_version,
            "build": build_string,
            "build_number": 0,
            "fn": fn,
        }
        write_as_json_to_file(info_dir / "index.json", index_json_data)

        dist_infos = sorted(self.sp_dir.glob("*.dist-info"))
        if dist_infos:
            wheel_metadata = package_metadata_from_metadata_body(source.read_dist_info("METADATA"))
            copy_into_info_licenses(dist_infos[0], info_dir, wheel_metadata)

    def finalize_installation(
        self,
        scheme: Scheme,
        record_file_path: str,
        records: Iterable[Tuple[Scheme, RecordEntry]],
    ) -> None:
        record_list = list(records)
        with installer.utils.construct_record_file(record_list, lambda x: None) as record_stream:
            dest_path = self.sp_dir / record_file_path
            with dest_path.open("wb") as dest:
                hash_, size = installer.utils.copyfileobj_with_hashing(
                    record_stream, dest, "sha256"
                )
                record_file_record = RecordEntry(
                    path=record_file_path,
                    hash_=Hash("sha256", hash_),
                    size=size,
                )
        record_list[-1] = ("purelib", record_file_record)
        self._create_conda_metadata(record_list, self.source)
        return


def extract_whl_as_conda_pkg(whl_full_path: str | Path, target_full_path: str | Path):
    with WheelFile.open(whl_full_path) as source:
        installer.install(
            source=source,
            destination=MyWheelDestination(target_full_path, source),
            additional_metadata={"INSTALLER": b"conda-via-whl"},
        )
