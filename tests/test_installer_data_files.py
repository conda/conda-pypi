"""
Tests for installer data file handling.

Tests that data files in wheels are properly installed.
"""

import json
import os
import sys
import tarfile
from pathlib import Path

import pytest
from conda.base.context import context

from conda_pypi import installer
from conda_pypi.build import build_pypa
from conda_pypi.package_extractors.whl import extract_whl_as_conda_pkg

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


def test_install_installer_to_tar_data_files_present(
    test_package_wheel_path: Path,
    tmp_path: Path,
):
    """Test that data files from wheels are included in package_paths."""
    tar_path = tmp_path / "output.tar"
    with tarfile.open(tar_path, "w") as tar:
        package_paths = installer.install_installer_to_tar(
            sys.executable,
            test_package_wheel_path,
            tar,
        )

    # Data files should be recorded with data scheme path (share/)
    paths = {p["_path"] for p in package_paths}
    data_path = "share/test-package-with-data/data/test.txt"
    assert data_path in paths, f"Data file not found in package_paths: {paths}"


def test_install_installer_to_tar_headers(
    wheel_with_headers: Path,
    tmp_path: Path,
):
    """Wheel .data/headers/ files are recorded with include/ path."""
    tar_path = tmp_path / "output.tar"
    with tarfile.open(tar_path, "w") as tar:
        package_paths = installer.install_installer_to_tar(
            sys.executable,
            wheel_with_headers,
            tar,
        )

    paths = {p["_path"] for p in package_paths}
    assert any(p.startswith("include/header_pkg/") for p in paths), (
        f"Header files not found in package_paths: {paths}"
    )


@pytest.fixture(scope="session")
def wheel_with_man_page() -> Path:
    """A minimal wheel with a man page installed via the .data/data/ scheme."""
    return HERE / "pypi_local_index" / "man-pkg" / "man_pkg-1.0.0-py3-none-any.whl"


def test_extract_whl_data_scheme_file_placement(
    wheel_with_man_page: Path,
    tmp_path: Path,
):
    """data-scheme files land at the env root, not under site-packages.

    Regression test for https://github.com/conda/conda-pypi/issues/255
    iPython's man page lives in .data/data/share/man/ and caused
    'Unsupported scheme: data' during conda extraction.
    """
    extract_whl_as_conda_pkg(wheel_with_man_page, tmp_path)

    man_page = tmp_path / "share" / "man" / "man1" / "man-pkg.1"
    assert man_page.is_file(), f"Man page not found at {man_page}"

    paths_json = json.loads((tmp_path / "info" / "paths.json").read_text())
    paths = {p["_path"] for p in paths_json["paths"]}
    assert "share/man/man1/man-pkg.1" in paths, "data-scheme path missing from paths.json"
    assert not any(p.startswith("site-packages/share") for p in paths), (
        "data-scheme files must not be nested under site-packages"
    )


def test_extract_whl_headers_scheme_file_placement(
    wheel_with_headers: Path,
    tmp_path: Path,
):
    """headers-scheme files land in include/, not under site-packages."""
    extract_whl_as_conda_pkg(wheel_with_headers, tmp_path)

    header_file = tmp_path / "include" / "header_pkg" / "header_pkg.h"
    assert header_file.is_file(), f"Header not found at {header_file}"
    assert header_file.read_text().startswith("// header_pkg public API")

    paths_json = json.loads((tmp_path / "info" / "paths.json").read_text())
    paths = {p["_path"] for p in paths_json["paths"]}
    assert any(p.startswith("include/") for p in paths), (
        "headers-scheme path missing from paths.json"
    )
    assert not any(p.startswith("site-packages/include") for p in paths), (
        "headers-scheme files must not be nested under site-packages"
    )


@pytest.fixture(scope="session")
def wheel_with_script() -> Path:
    """A minimal wheel with a script installed via the .data/scripts/ scheme."""
    return HERE / "pypi_local_index" / "script-pkg" / "script_pkg-1.0.0-py3-none-any.whl"


def test_extract_whl_scripts_scheme_file_placement(
    wheel_with_script: Path,
    tmp_path: Path,
):
    """scripts-scheme files land in bin/ with executable permissions set."""
    extract_whl_as_conda_pkg(wheel_with_script, tmp_path)

    script = tmp_path / "bin" / "my-script"
    assert script.is_file(), f"Script not found at {script}"
    assert os.access(script, os.X_OK), "Script must be executable"

    paths_json = json.loads((tmp_path / "info" / "paths.json").read_text())
    paths = {p["_path"] for p in paths_json["paths"]}
    assert "bin/my-script" in paths, "scripts-scheme path missing from paths.json"
    assert not any(p.startswith("site-packages/bin") for p in paths), (
        "scripts-scheme files must not be nested under site-packages"
    )
