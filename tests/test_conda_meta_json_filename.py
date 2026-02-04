"""
Test that wheel files installed via conda-pypi create JSON files in conda-meta/
with the correct filename format: name-version-build.json
"""

from __future__ import annotations

import json
from pathlib import Path


def test_extract_whl_sets_fn_correctly(
    pypi_demo_package_wheel_path: Path,
    tmp_path: Path,
):
    """
    Test that extract_whl_as_conda_pkg sets the fn field correctly in index.json.
    This is a unit test that directly tests the metadata creation.
    """
    from conda_pypi.package_extractors.whl import extract_whl_as_conda_pkg

    extract_whl_as_conda_pkg(str(pypi_demo_package_wheel_path), str(tmp_path))

    # Check that index.json was created with correct fn field
    index_json_path = tmp_path / "info" / "index.json"
    assert index_json_path.exists()

    with open(index_json_path) as f:
        index_data = json.load(f)

    # Verify fn field is set correctly with build string and .whl extension
    # Note: source.distribution returns the Python package name (with underscores),
    # so fn will be "demo_package-0.1.0-pypi_0.whl" not "demo-package-0.1.0-pypi_0.whl"
    assert "fn" in index_data, "index.json should contain 'fn' field"
    # The fn field should include the build string and .whl extension
    assert index_data["fn"].endswith("-pypi_0.whl")
    # Verify the format is name-version-build.whl
    fn_parts = index_data["fn"].replace(".whl", "").rsplit("-", 2)
    assert len(fn_parts) == 3
    fn_name, fn_version, fn_build = fn_parts
    assert fn_build == "pypi_0"

    # Verify other fields
    # The name field uses the Python package name (with underscores)
    assert index_data["name"] == "demo_package"
    assert index_data["version"] == "0.1.0"
    assert index_data["build"] == "pypi_0"
    assert index_data["build_number"] == 0
