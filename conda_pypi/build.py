"""
Create .conda packages from wheels.

Create wheels from pypa projects.
"""

import csv
import itertools
import json
import os
import sys
import tempfile
from importlib.metadata import PathDistribution
from pathlib import Path
from typing import Union, Optional
import logging

from conda_package_streaming.create import conda_builder
from conda.common.path.windows import win_path_to_unix
from conda.common.compat import on_win

from build import ProjectBuilder

from conda_pypi import dependencies, installer, paths
from conda_pypi.conda_build_utils import PathType, sha256_checksum
from conda_pypi.translate import CondaMetadata
from conda_pypi.utils import sha256_as_base64url


log = logging.getLogger(__name__)


def filter(tarinfo):
    """
    Anonymize uid/gid; exclude .git directories.
    """
    if tarinfo.name.endswith(".git"):
        return None
    tarinfo.uid = tarinfo.gid = 0
    tarinfo.uname = tarinfo.gname = ""
    return tarinfo


# see conda_build.build.build_info_files_json_v1
def paths_json(base: Union[Path, str]):
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


def flatten(iterable):
    return [*itertools.chain(*iterable)]


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

    build_system_requires = builder.build_system_requires
    for _retry in range(2):
        try:
            missing = dependencies.check_dependencies(build_system_requires, prefix=prefix)
            break
        except dependencies.MissingDependencyError as e:
            dependencies.ensure_requirements(e.dependencies, prefix=prefix)

    log.debug(f"Installing requirements for build system: {missing}")
    # does flatten() work for a deeper dependency chain?
    dependencies.ensure_requirements(flatten(missing), prefix=prefix)

    requirements = builder.check_dependencies(distribution)
    log.debug(f"Additional requirements for {distribution}: {requirements}")
    dependencies.ensure_requirements(flatten(requirements), prefix=prefix)

    editable_file = builder.build(distribution, output_path)
    log.debug(f"The wheel is at {editable_file}")

    return editable_file


def build_conda(
    whl,
    build_path: Path,
    output_path: Path,
    python_executable,
    project_path: Optional[Path] = None,
    is_editable=False,
) -> Path:
    if not build_path.exists():
        build_path.mkdir()

    installer.install_installer(python_executable, whl, build_path)

    site_packages = build_path / "site-packages"
    dist_info = next(site_packages.glob("*.dist-info"))
    metadata = CondaMetadata.from_distribution(PathDistribution(dist_info))
    record = metadata.package_record.to_index_json()
    # XXX set build string as hash of pypa metadata so that conda can re-install
    # when project gains new entry-points, dependencies?

    file_id = f"{record['name']}-{record['version']}-{record['build']}"

    (build_path / "info").mkdir()
    (build_path / "info" / "index.json").write_text(json_dumps(record))
    (build_path / "info" / "about.json").write_text(json_dumps(metadata.about))

    # used especially for console_scripts
    if link_json := metadata.link_json():
        (build_path / "info" / "link.json").write_text(json_dumps(link_json))

    # Allow pip to list us as editable or show the path to our project.
    # XXX leaks path
    if project_path:
        direct_url = project_path.absolute().as_uri()
        direct_url_path = dist_info / "direct_url.json"
        direct_url_path.write_text(
            json.dumps({"dir_info": {"editable": is_editable}, "url": direct_url})
        )
        record_path = dist_info / "RECORD"
        # Rewrite RECORD for any changed files
        update_RECORD(record_path, site_packages, direct_url_path)

    # Write conda's paths after all other changes
    paths = paths_json(build_path)

    (build_path / "info" / "paths.json").write_text(json_dumps(paths))

    with conda_builder(file_id, output_path) as tar:
        tar.add(build_path, "", filter=filter)

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
    output_path: Optional[Path] = None,
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
            normal_wheel,
            build_path,
            output_path or tmp_path,
            sys.executable,
            project_path=project,
            is_editable=distribution == "editable",
        )

    return package_conda
