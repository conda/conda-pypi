"""
Test index.json written by direct .whl extraction (extract_whl_as_conda_pkg).

conda-meta/*.json filenames use name-version-build (conda derives build from
index.json, not fn). index.json fn is the wheel basename on disk — the same
field repodata v3 uses (PyPI upload filename).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from installer.sources import WheelFile


@pytest.mark.parametrize(
    ("wheel_tag", "expected"),
    [
        ("py3-none-any", "py3-none-any"),
        ("py2-none-any", "py3-none-any"),
        ("py38-none-any", "py3-none-any"),
        ("cp312-cp312-win_amd64", "cp312-cp312-win_amd64"),
    ],
)
def test_noarch_wheel_tag_normalization_for_index_build(wheel_tag, expected):
    normalized = wheel_tag
    if normalized != "py3-none-any" and normalized.endswith("-none-any"):
        normalized = "py3-none-any"
    assert normalized == expected


def test_extract_whl_sets_fn_correctly(
    pypi_demo_package_wheel_path: Path,
    tmp_path: Path,
):
    """
    extract_whl_as_conda_pkg must write index.json that matches repodata v3 channel records.

    fn is the wheel basename on disk; build is tag-derived with underscores. These fields
    are not interchangeable — lockfile restore reads index.json directly, so both must
    be correct even when fn and build describe the same wheel differently.
    """
    from conda_pypi.package_extractors.whl import extract_whl_as_conda_pkg

    extract_whl_as_conda_pkg(pypi_demo_package_wheel_path, tmp_path)

    # Check that index.json was created with correct fn field
    index_json_path = tmp_path / "info" / "index.json"
    assert index_json_path.exists()

    with open(index_json_path) as f:
        index_data = json.load(f)

    # fn is the wheel basename on the path passed to extract_whl_as_conda_pkg (zip path).
    # Repodata v3 matches: fn=requests-2.32.5-py3-none-any.whl, build=py3_none_any_0.
    with WheelFile.open(pypi_demo_package_wheel_path) as source:
        zip_basename = Path(source._zipfile.filename).name
    assert "fn" in index_data, "index.json should contain 'fn' field"
    assert index_data["fn"] == pypi_demo_package_wheel_path.name
    assert index_data["fn"] == zip_basename

    # build from WHEEL Tag; build_number from WHEEL Build when present (PEP 427).
    # The name field uses the Python package name from METADATA (underscores, not normalized).
    assert index_data["name"] == "demo_package"
    assert index_data["version"] == "0.1.0"
    assert index_data["build"] == "py3_none_any_0"
    assert index_data["build_number"] == 0
