# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Health check: Report packages not installed by conda"""

from __future__ import annotations

import shutil
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from conda.base.constants import OK_MARK, X_MARK
from conda.common.constants import NULL
from conda.core.prefix_data import PrefixData
from conda.exceptions import CondaError
from conda.models.records import PrefixRecord

if TYPE_CHECKING:
    from argparse import Namespace

    from conda.plugins.types import ConfirmCallback


def find_external_packages(prefix: str) -> list[PrefixRecord]:
    """Identify packages that were not installed by conda."""
    prefix_data = PrefixData(prefix, interoperability=True)
    external_packages = prefix_data.get_python_packages()
    return external_packages


def print_external_packages(prefix: str, verbose: bool) -> None:
    """Print packages not installed by conda."""
    external_packages = find_external_packages(prefix)
    if not external_packages:
        print(f"{OK_MARK} No external packages found.\n")
    else:
        print(f"{X_MARK} These packages are not installed by conda:\n")
        for package in external_packages:
            print(package.name, package.version)
        print()


def conda_has_package(name: str) -> bool:
    """Check if a package with the given name exists in conda channels."""
    from conda.api import SubdirData

    result = SubdirData.query_all(name)
    return bool(result)


def build_migration_plan(
    packages: list[PrefixRecord],
) -> tuple[list[str], list[PrefixRecord]]:
    """Determine which packages can be safely migrated to conda."""

    from conda_pypi.name_mapping import pypi_to_conda_name

    safe_pkgs_conda_names = []
    safe_pkgs_pypi = []

    for pkg in packages:
        conda_name = pypi_to_conda_name(pkg.name)

        # check if conda can install it
        if conda_has_package(conda_name):
            safe_pkgs_conda_names.append(conda_name)
            if pkg.name != conda_name:
                print(
                    f"Note: '{pkg.name}' will be reinstalled as '{conda_name}' from conda channels.\n"
                )
            safe_pkgs_pypi.append(pkg)

    return safe_pkgs_conda_names, safe_pkgs_pypi


def normalize_conda_file_paths(prefix_record: PrefixRecord) -> tuple[PurePosixPath, ...]:
    """Return package file paths normalized to conda's manifest path style."""
    return tuple(PurePosixPath(path.replace("\\", "/")) for path in prefix_record.files)


def find_python_metadata_directories(prefix_record: PrefixRecord) -> set[PurePosixPath]:
    """Identify dist-info and egg-info directories from a PrefixRecord."""
    directories = set()

    for file_path in normalize_conda_file_paths(prefix_record):
        for path in (file_path, *file_path.parents):
            if path.name.endswith((".dist-info", ".egg-info")):
                directories.add(path)
                break
    return directories


def get_conda_owned_paths(prefix: str) -> set[PurePosixPath]:
    """Get the set of file paths owned by conda packages in the environment."""

    prefix_data = PrefixData(prefix, interoperability=False).reload()
    return {
        file_path
        for record in prefix_data.iter_records()
        for file_path in normalize_conda_file_paths(record)
    }


def clean_up_stale_files(
    prefix: str, prefix_record: PrefixRecord, conda_owned_paths: set[PurePosixPath]
) -> None:
    """Remove dist-info directories left behind by pip after migration."""

    print("Cleaning up stale metadata directories...")
    prefix_path = Path(prefix)

    for metadata_dir in sorted(find_python_metadata_directories(prefix_record)):
        is_conda_owned = any(
            owned_path == metadata_dir or metadata_dir in owned_path.parents
            for owned_path in conda_owned_paths
        )

        if is_conda_owned:
            continue

        path = prefix_path.joinpath(*metadata_dir.parts)
        if path.is_dir():
            print(f"Removing stale metadata: {path}")
            shutil.rmtree(path)


def migrate_to_conda(prefix: str, args: Namespace, confirm: ConfirmCallback) -> int:
    """Migrate pip-installed packages to conda."""

    from conda.base.context import context
    from conda.cli.install import reinstall_packages

    if prefix == context.root_prefix:
        print("Cannot migrate packages in the base environment.")
        return 0

    external_packages = find_external_packages(prefix)

    if not external_packages:
        print("No external packages found.")
        return 0

    safe_pkgs_conda_names, safe_pkgs_pypi_names = build_migration_plan(external_packages)

    if not safe_pkgs_conda_names:
        print("No safe packages to migrate.")
        return 0

    print()
    confirm("Reinstall these packages with conda?")

    args.use_local = False
    args.file = []
    args.repodata_fns = ("repodata.json",)
    args.update_modifier = NULL

    try:
        reinstall_packages(
            args,
            safe_pkgs_conda_names,
            force_reinstall=True,
        )
    except CondaError as e:
        print(f"Failed to reinstall packages with conda: {e}")
        return 1

    # remove paths not owned by conda that are left behind by pip after migration
    conda_owned_paths = get_conda_owned_paths(prefix)
    for pkg in safe_pkgs_pypi_names:
        clean_up_stale_files(prefix, pkg, conda_owned_paths)

    return 0
