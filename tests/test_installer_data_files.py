"""
Tests for installer data file handling.

Tests that data files in wheels are properly installed.
"""

import io
import json
import os
import sys
import tarfile
from pathlib import Path

import pytest
from conda.base.context import context
from conda.common.path import get_python_short_path
from conda.testing.fixtures import TmpEnvFixture

from conda_pypi import installer
from conda_pypi.build import build_pypa
from conda_pypi.package_extractors.whl import extract_whl_as_conda_pkg

HERE = Path(__file__).parent


# This mirrors the layout of the pybind11-global wheel. The identical header files
# appear in both data/include/ and headers/. Duplicate archive members should be
# treated as fatal to avoid ambiguous package contents.
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
    assert not any(p.startswith("/") for p in paths), (
        f"Package paths must be relative, got absolute entries: {paths}"
    )


def test_install_installer_headers(
    tmp_env: TmpEnvFixture,
    wheel_with_headers: Path,
):
    """Wheel .data/headers/ files are added to include/ in tar members."""
    tar = tarfile.TarFile("conda.tar", "w", fileobj=io.BytesIO())

    with tmp_env("python=3.12") as prefix:
        python_executable = Path(prefix, get_python_short_path())

        installer.install_installer_to_tar(
            str(python_executable),
            wheel_with_headers,
            tar,
        )

        member_names = {member.name for member in tar.getmembers()}
        header_path = "include/header_pkg/header_pkg.h"
        assert header_path in member_names


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
    assert not any(p.startswith("/") for p in paths), (
        "paths.json entries must be relative and must not start with '/'"
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
