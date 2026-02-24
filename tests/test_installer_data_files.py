"""
Tests for installer data file handling.

Tests that data files in wheels are properly installed.
"""

from pathlib import Path

import pytest
from conda.testing.fixtures import TmpEnvFixture
from conda.common.path import get_python_short_path
from conda.base.context import context

from conda_pypi import installer
from conda_pypi.build import build_pypa

HERE = Path(__file__).parent


# This mirrors the layout of the pybind11-global wheel. The identical header files
# appear in both data/include/ and headers/. The data/ copy is listed first in RECORD
# so it is written first. The headers/ copy must not raise a FileExistsError.
@pytest.fixture(scope="session")
def wheel_with_headers() -> Path:
    return HERE / "pypi_local_index" / "header-pkg" / "header_pkg-1.0.0-py3-none-any.whl"


@pytest.fixture(scope="session")
def test_package_wheel_path(tmp_path_factory):
    """Build a wheel from the test package with data files."""
    package_path = Path(__file__).parent / "packages" / "has-data-files"
    wheel_output = tmp_path_factory.mktemp("wheels")
    prefix = Path(context.default_prefix)

    return build_pypa(
        package_path,
        wheel_output,
        prefix=prefix,
        distribution="wheel",
    )


@pytest.mark.skip(reason="Test has CI-only failures that need investigation")
def test_install_installer_data_files_present(
    tmp_env: TmpEnvFixture,
    test_package_wheel_path: Path,
    tmp_path: Path,
):
    """Test that data files from wheels are installed in build_path."""
    build_path = tmp_path / "build"
    build_path.mkdir()

    with tmp_env("python=3.12", "pip") as prefix:
        python_executable = Path(prefix, get_python_short_path()) / "python"

        installer.install_installer(
            str(python_executable),
            test_package_wheel_path,
            build_path,
        )

        # Data files should be installed in build_path/share/ (data scheme)
        data_file = build_path / "share" / "test-package-with-data" / "data" / "test.txt"

        assert data_file.exists(), f"Data file not found at {data_file}"


def test_install_installer_headers(
    tmp_env: TmpEnvFixture,
    wheel_with_headers: Path,
    tmp_path: Path,
):
    """Wheel .data/headers/ files are installed to build_path/include/."""
    build_path = tmp_path / "build"
    build_path.mkdir()

    with tmp_env("python=3.12") as prefix:
        python_executable = Path(prefix, get_python_short_path())

        installer.install_installer(
            str(python_executable),
            wheel_with_headers,
            build_path,
        )

        header_file = build_path / "include" / "header_pkg" / "header_pkg.h"
        assert header_file.exists()
        assert header_file.read_text().startswith("// header_pkg public API")
