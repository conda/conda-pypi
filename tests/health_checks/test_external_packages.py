# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for external packages health check."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

import pytest
from conda.base.constants import OK_MARK, X_MARK
from conda.base.context import reset_context
from conda.core.prefix_data import PrefixData
from pytest import MonkeyPatch

from conda_pypi.health_checks.external_packages import (
    build_migration_plan,
    clean_up_stale_files,
    conda_has_package,
    find_external_packages,
    find_python_metadata_directories,
    get_conda_owned_paths,
    migrate_to_conda,
    normalize_conda_file_paths,
    print_external_packages,
)
from tests import PYTHON_VERSION

if TYPE_CHECKING:
    from conda.testing.fixtures import PipCLIFixture, TmpEnvFixture
    from pytest_mock import MockerFixture


def test_no_external_packages(tmp_env: TmpEnvFixture):
    with tmp_env() as prefix:
        assert find_external_packages(prefix) == []


def test_external_packages(tmp_env: TmpEnvFixture, pip_cli: PipCLIFixture):
    """Test detection of external packages after installing with pip."""
    with tmp_env(f"python={PYTHON_VERSION}", "pip") as prefix:
        _stdout, _stderr, code = pip_cli(
            "install",
            "tests/pypi_local_index/demo-package/demo_package-0.1.0-py3-none-any.whl",
            prefix=prefix,
        )
        assert code == 0
        packages = find_external_packages(prefix)
        assert packages != []

        names = []
        for pkg in packages:
            names.append(pkg.name)

        assert "demo-package" in names


@pytest.mark.parametrize(
    "package_name, expected",
    [
        ("bzip2", True),
        ("this_package_definitely_does_not_exist_xyz_123", False),
    ],
)
def test_conda_has_package(conda_local_channel, monkeypatch: MonkeyPatch, package_name, expected):
    """Test detection of packages available in conda channels."""
    monkeypatch.setenv("context.channels", conda_local_channel)
    reset_context()
    assert conda_has_package(package_name) == expected


def test_print_external_packages_output(tmp_env: TmpEnvFixture, pip_cli: PipCLIFixture, capsys):
    """Test the printed output format."""
    with tmp_env(f"python={PYTHON_VERSION}", "pip") as prefix:
        _stdout, _stderr, code = pip_cli(
            "install",
            "tests/pypi_local_index/demo-package/demo_package-0.1.0-py3-none-any.whl",
            prefix=prefix,
        )
        assert code == 0
        print_external_packages(prefix, verbose=False)
        captured = capsys.readouterr()

        assert X_MARK in captured.out


def test_print_external_packages_no_packages(tmp_env: TmpEnvFixture, capsys):
    """Test output when no external packages found."""
    with tmp_env() as prefix:
        print_external_packages(prefix, verbose=False)
        captured = capsys.readouterr()

        assert OK_MARK in captured.out


def test_build_migration_plan_safe_packages(
    tmp_env: TmpEnvFixture, pip_cli: PipCLIFixture, monkeypatch: MonkeyPatch, conda_local_channel
):
    """Test building a migration plan for packages available in conda."""
    with tmp_env(f"python={PYTHON_VERSION}", "pip") as prefix:
        monkeypatch.setenv("context.channels", conda_local_channel)
        reset_context()
        # Install a real package that exists in both pip and conda
        pip_cli("install", "tzdata", prefix=prefix)

        packages = find_external_packages(prefix)
        conda_names, pypi_names = build_migration_plan(packages)

        # tzdata should be found in conda
        assert len(conda_names) > 0
        assert len(pypi_names) == len(packages)


def test_normalize_conda_file_paths():
    """Test that backslashes are converted to forward slashes."""
    # Create a mock PrefixRecord with Windows-style paths
    from unittest.mock import Mock

    mock_record = Mock()
    mock_record.files = [
        "Lib\\site-packages\\package\\__init__.py",
        "Lib/site-packages/package/module.py",
    ]
    paths = normalize_conda_file_paths(mock_record)
    assert all("/" in str(p) for p in paths)
    assert "\\" not in str(paths)


def test_get_conda_owned_paths(tmp_env: TmpEnvFixture):
    """Test retrieval of conda-owned file paths."""
    with tmp_env("tzdata") as prefix:
        owned_paths = get_conda_owned_paths(prefix)

        assert len(owned_paths) > 0
        # verify structure is PurePosixPath
        assert all(isinstance(p, PurePosixPath) for p in owned_paths)


def test_clean_up_stale_files_removes_unowned_metadata(
    tmp_env: TmpEnvFixture, pip_cli: PipCLIFixture
):
    """Test removal of stale metadata directories."""
    with tmp_env(f"python={PYTHON_VERSION}", "pip") as prefix:
        pip_cli(
            "install",
            "tests/pypi_local_index/demo-package/demo_package-0.1.0-py3-none-any.whl",
            prefix=prefix,
        )

        packages = find_external_packages(prefix)
        conda_owned = get_conda_owned_paths(prefix)

        # Find metadata dirs before cleanup
        metadata_dirs_before = []
        for pkg in packages:
            metadata_dirs_before.extend(find_python_metadata_directories(pkg))

        for pkg in packages:
            clean_up_stale_files(prefix, pkg, conda_owned)

        # Verify those specific directories are gone
        prefix_path = Path(prefix)
        for metadata_dir in metadata_dirs_before:
            path = prefix_path / metadata_dir
            assert not path.exists(), f"Stale metadata directory {path} should have been removed"


def test_migrate_to_conda(
    mocker: MockerFixture,
    monkeypatch: MonkeyPatch,
    tmp_env: TmpEnvFixture,
    pip_cli: PipCLIFixture,
    with_rattler_solver: None,  # configures solver=rattler
):
    """Migrate pip-installed packages to conda from configured channels."""
    with tmp_env(f"python={PYTHON_VERSION}", "pip") as prefix:
        _, _, code = pip_cli("install", "tzdata", prefix=prefix)
        assert code == 0
        assert any(pkg.name == "tzdata" for pkg in find_external_packages(prefix))

        mocker.patch(
            "conda.base.context.Context.target_prefix",
            new_callable=mocker.PropertyMock,
            return_value=prefix,
        )
        monkeypatch.setenv("CONDA_ALWAYS_YES", "True")
        reset_context()

        args = Namespace(prefix=prefix, name=None, cmd="install", yes=True)
        assert migrate_to_conda(prefix, args, confirm=lambda _msg: None) == 0
        PrefixData._cache_.clear()
        assert not any(pkg.name == "tzdata" for pkg in find_external_packages(prefix))
