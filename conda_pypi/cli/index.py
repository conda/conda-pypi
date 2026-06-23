import zipfile
from argparse import Namespace, _SubParsersAction
from importlib.metadata import PackageMetadata
from pathlib import Path

from conda.auxlib.ish import dals
from conda.exceptions import ArgumentError
from installer.sources import WheelFile
from packaging.requirements import InvalidRequirement

from conda_pypi.conda_build_utils import sha256_checksum
from conda_pypi.exceptions import UnableToConvertToRepodataEntry
from conda_pypi.index import create_channel_index, store_pypi_metadata, update_index
from conda_pypi.license_files import package_metadata_from_metadata_body


def configure_parser(parser: _SubParsersAction) -> None:
    """Configure all subcommand arguments and options via argparse"""

    summary = "Index a directory of `.whl` files to generate repodata.json"
    description = summary
    epilog = dals("""
    Creates a local conda channel from a collection of wheel files.
    Examples:
    `conda pypi index <directory>`
    """)
    index = parser.add_parser(
        "index",
        help=summary,
        description=description,
        epilog=epilog,
    )
    index.add_argument(
        "directory",
        metavar="DIRECTORY",
        type=Path,
        help="Directory containing .whl files to index",
    )
    index.add_argument(
        "--base-url",
        help="Base URL for the channel (e.g. https://packages.example.com/). When omitted, each entry uses a file:// URI for each wheel file.",
    )


def validate_dir_and_return_whl_files(directory: Path) -> list[Path]:
    """Ensure provided path is a directory and follows expected structure
    Expected structure:
    root/
      <package>/ <package>-*.whl"""

    if not directory.is_dir():
        raise ArgumentError(f"Not a directory: {directory}")

    entries = list(directory.iterdir())
    if not entries:
        raise SystemExit(f"No wheel subdirectories found in the given directory: {directory}")

    # notify user of ignored invalid entries
    invalid_entries = [entry for entry in entries if not entry.is_dir()]
    if invalid_entries:
        print(
            f"Found invalid entries (not wheel directories) in the given directory, ignoring them: {invalid_entries}"
        )

    # find valid entries
    valid_entries = [entry for entry in entries if entry.is_dir()]
    if not valid_entries:
        raise SystemExit(
            f"No valid wheel subdirectories found in the given directory: {directory}"
        )

    all_wheels = []
    for entry in valid_entries:
        # one wheel file per subdirectory is expected
        all_wheels.extend(entry.glob("*.whl"))

    if not all_wheels:
        raise SystemExit(f"No wheel files found in the given directory: {directory}")

    return all_wheels


def pypi_data_dict(wheel: Path, wheel_metadata: PackageMetadata, url: str):
    """Return expected dict structure of pypi metadata with the relevant fields"""

    # convert to json format using the `json` property of the PackageMetadata class
    wheel_metadata_json = wheel_metadata.json
    # generate the expected dict structure of pypi metadata with the relevant fields as needed by the `pypi_to_repodata` function.
    pypi_data = {
        "info": {
            "name": wheel_metadata_json.get("name"),
            "version": wheel_metadata_json.get("version"),
            "requires_dist": wheel_metadata_json.get("requires_dist", []),
            "requires_python": wheel_metadata_json.get("requires_python"),
        },
        "urls": [
            {
                "packagetype": "bdist_wheel",
                "filename": wheel.name,
                "url": url,
                "size": wheel.stat().st_size,
                "digests": {"sha256": sha256_checksum(str(wheel))},
            }
        ],
    }
    return pypi_data


def execute(args: Namespace) -> int:
    """Entry point for the `conda pypi index` subcommand"""

    directory = Path(args.directory).expanduser()

    if args.base_url:
        base_url = args.base_url.rstrip("/") + "/"

    all_wheels = validate_dir_and_return_whl_files(directory)
    failed_wheels = []

    # creat channel_index and cache
    channel_index = create_channel_index(directory)
    cache = channel_index.cache_for_subdir("noarch")

    for wheel in all_wheels:
        try:
            with WheelFile.open(wheel) as source:
                wheel_metadata = package_metadata_from_metadata_body(
                    source.read_dist_info("METADATA")
                )
            if args.base_url:
                url = base_url + wheel.relative_to(directory).as_posix()
            else:
                url = wheel.resolve().as_uri()
            pypi_data = pypi_data_dict(wheel, wheel_metadata, url)
            store_pypi_metadata(cache, pypi_data)
        except UnableToConvertToRepodataEntry as e:
            print(f"Skipping {wheel.name}: not a pure-python wheel ({e})")
            failed_wheels.append(wheel)
        except InvalidRequirement as e:
            print(f"Skipping {wheel.name}: invalid metadata ({e})")
            failed_wheels.append(wheel)
        except ValueError as e:
            print(f"Skipping {wheel.name}: {e}")
            failed_wheels.append(wheel)
        except (OSError, zipfile.BadZipFile) as e:
            print(f"Failed to read {wheel.name}: {e}")
            failed_wheels.append(wheel)

    update_index(channel_index)

    # inform user about wheels that couldn't be indexed
    if failed_wheels:
        failed_names = ", ".join(wheel.name for wheel in failed_wheels)
        print(
            f"Indexed {len(all_wheels) - len(failed_wheels)} wheels; "
            f"{len(failed_wheels)} failed: {failed_names}"
        )

    return 0
