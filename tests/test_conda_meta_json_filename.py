"""
Test index.json written by direct .whl extraction (extract_whl_as_conda_pkg).

conda-meta/*.json filenames use name-version-build (conda derives build from
index.json, not fn). index.json fn is the wheel basename on disk — the same
field repodata v3 uses (PyPI upload filename).
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from conda_pypi.package_extractors.whl import extract_whl_as_conda_pkg


def _make_wheel(
    path: Path,
    name: str,
    version: str,
    tags: list[str],
    filename_tag: str | None = None,
    wheel_build: str | None = None,
) -> Path:
    """Minimal installable wheel for extract_whl_as_conda_pkg (Tag/Build/RECORD/pkg).

    Separate from tests/cli/test_index.py make_wheel, which targets indexing only.
    """
    if filename_tag is None:
        filename_tag = "py3-none-any" if "py3-none-any" in tags else tags[0]
    wheel_path = path / f"{name}-{version}-{filename_tag}.whl"
    dist_info = f"{name}-{version}.dist-info"
    wheel_lines = ["Wheel-Version: 1.0\nGenerator: test\n"]
    for tag in tags:
        wheel_lines.append(f"Tag: {tag}\n")
    if wheel_build is not None:
        wheel_lines.append(f"Build: {wheel_build}\n")
    metadata = "\n".join(
        [
            "Metadata-Version: 2.1",
            f"Name: {name}",
            f"Version: {version}",
        ]
    )
    with zipfile.ZipFile(wheel_path, "w") as zf:
        zf.writestr("pkg.py", "# pkg\n")
        zf.writestr(f"{dist_info}/METADATA", metadata)
        zf.writestr(f"{dist_info}/WHEEL", "".join(wheel_lines))
        zf.writestr(f"{dist_info}/top_level.txt", "pkg\n")
        zf.writestr(f"{dist_info}/RECORD", "pkg.py,,\n")
    return wheel_path


@pytest.mark.parametrize(
    ("tags", "wheel_build", "expected_build"),
    [
        (["py2-none-any"], None, "py3_none_any_0"),
        (["py38-none-any"], None, "py3_none_any_0"),
        (["py2-none-any", "py3-none-any"], None, "py3_none_any_0"),
        (["py3-none-any"], "1", "py3_none_any_1"),
        (["cp312-cp312-win_amd64"], None, "cp312_cp312_win_amd64_0"),
    ],
)
def test_extract_whl_index_json_build_from_wheel_metadata(
    tmp_path: Path,
    tags: list[str],
    wheel_build: str | None,
    expected_build: str,
):
    name = "test_pkg"
    version = "1.0.0"
    wheel_path = _make_wheel(tmp_path, name, version, tags, wheel_build=wheel_build)
    extract_dir = tmp_path / "extract"
    extract_whl_as_conda_pkg(wheel_path, extract_dir)

    index_data = json.loads((extract_dir / "info" / "index.json").read_text())
    expected_build_number = int(wheel_build) if wheel_build is not None else 0
    assert index_data["name"] == name
    assert index_data["version"] == version
    assert index_data["fn"] == wheel_path.name
    assert index_data["build"] == expected_build
    assert index_data["build_number"] == expected_build_number


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
    extract_whl_as_conda_pkg(pypi_demo_package_wheel_path, tmp_path)

    # Check that index.json was created with correct fn field
    index_json_path = tmp_path / "info" / "index.json"
    assert index_json_path.exists()

    index_data = json.loads(index_json_path.read_text())

    # fn is the wheel basename on the path passed to extract_whl_as_conda_pkg.
    # Repodata v3 matches: fn=requests-2.32.5-py3-none-any.whl, build=py3_none_any_0.
    assert "fn" in index_data, "index.json should contain 'fn' field"
    assert index_data["fn"] == pypi_demo_package_wheel_path.name

    # build from WHEEL Tag; build_number from WHEEL Build when present (PEP 427).
    # The name field uses the Python package name from METADATA (underscores, not normalized).
    assert index_data["name"] == "demo_package"
    assert index_data["version"] == "0.1.0"
    assert index_data["build"] == "py3_none_any_0"
    assert index_data["build_number"] == 0
