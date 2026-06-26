"""
Test index.json written by direct .whl extraction (extract_whl_as_conda_pkg).

conda-meta/*.json filenames use name-version-build (conda derives build from
index.json, not fn). index.json fn is the wheel basename on disk — the same
field repodata v3 uses (PyPI upload filename).
"""

from __future__ import annotations

import json
from email.parser import HeaderParser
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from conda_pypi.package_extractors.whl import (
    _create_build_string_from_wheel_meta_and_filename,
    extract_whl_as_conda_pkg,
)

if TYPE_CHECKING:
    from email.message import Message


def _make_wheel_meta(
    tags: list[str] | None = None,
    wheel_build: str | None = None,
) -> Message:
    """Parsed WHEEL dist-info headers, as from HeaderParser on a WHEEL file."""
    lines = ["Wheel-Version: 1.0\n", "Generator: test\n"]
    if tags:
        for tag in tags:
            lines.append(f"Tag: {tag}\n")
    if wheel_build is not None:
        lines.append(f"Build: {wheel_build}\n")
    return HeaderParser().parsestr("".join(lines))


@pytest.mark.parametrize(
    ("tags", "wheel_build", "expected_build"),
    [
        (["py310-none-any", "py3-none-any"], None, "py3_none_any_0"),
        (["py38-none-any"], None, "py3_none_any_0"),
        (["py2-none-any", "py3-none-any"], None, "py3_none_any_0"),
        (["py3-none-any"], "1", "py3_none_any_1"),
        (["cp312-cp312-win_amd64"], None, "cp312_cp312_win_amd64_0"),
    ],
)
def test_create_build_string_from_wheel_meta_and_filename(
    tags: list[str],
    wheel_build: str | None,
    expected_build: str,
):
    wheel_meta = _make_wheel_meta(tags, wheel_build)
    last_tag = wheel_meta.get_all("Tag")[-1]
    wheel_filename = f"test_pkg-1.0.0-{last_tag}.whl"

    build_string, build_number = _create_build_string_from_wheel_meta_and_filename(
        wheel_meta, wheel_filename
    )

    expected_build_number = int(wheel_build) if wheel_build is not None else 0
    assert build_string == expected_build
    assert build_number == expected_build_number


@pytest.mark.parametrize(
    ("filename", "expected_build"),
    [
        ("test_pkg-1.0.0-py3-none-any.whl", "py3_none_any_0"),
        ("test_pkg-1.0.0-py38-none-any.whl", "py3_none_any_0"),
        ("test_pkg-1.0.0-py2-none-any.whl", "py3_none_any_0"),
        ("test_pkg-1.0.0-py2.py3-none-any.whl", "py3_none_any_0"),
        ("test_pkg-1.0.0-cp312-cp312-win_amd64.whl", "cp312_cp312_win_amd64_0"),
    ],
)
def test_create_build_string_from_wheel_meta_and_filename_filename_fallback(
    filename: str,
    expected_build: str,
):
    # No Tag headers — build string comes from the wheel filename tag segment.
    wheel_meta = _make_wheel_meta()
    build_string, build_number = _create_build_string_from_wheel_meta_and_filename(
        wheel_meta, filename
    )
    assert build_string == expected_build
    assert build_number == 0


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
