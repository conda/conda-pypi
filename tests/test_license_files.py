import sys
from importlib.metadata import PathDistribution
from pathlib import Path

import pytest

from conda_pypi.license_files import copy_into_info_licenses, package_metadata_from_metadata_body
from conda_pypi.translate import CondaMetadata


def test_package_metadata_from_body_matches_path_distribution(tmp_path: Path):
    """In-memory METADATA parse (wheel zip) agrees with ``PathDistribution`` / disk."""
    dist_info_dir = tmp_path / "pkg-1.0.dist-info"
    dist_info_dir.mkdir()
    body = (
        "Metadata-Version: 2.4\n"
        "Name: pkg\n"
        "Version: 1.0\n"
        "License-File: LICENSE\n"
        "License-File: NOTICE\n"
        "\n"
    )
    (dist_info_dir / "METADATA").write_text(body, encoding="utf-8")
    from_disk = PathDistribution(dist_info_dir).metadata
    from_body = package_metadata_from_metadata_body(body)
    assert from_disk.get_all("License-File") == from_body.get_all("License-File")
    assert from_body.get_all("License-File") == ["LICENSE", "NOTICE"]


def _write_dist_info_metadata(dist_info_dir: Path, *license_file_lines: str) -> None:
    lines = [
        "Metadata-Version: 2.4",
        "Name: pkg",
        "Version: 1.0",
        *license_file_lines,
        "",
        "",
    ]
    (dist_info_dir / "METADATA").write_text("\n".join(lines), encoding="utf-8")


def test_license_file_basename_in_dist_info_licenses(tmp_path: Path):
    """e.g. PyPI ``packaging``: ``License-File: LICENSE`` with file at ``…/licenses/LICENSE``."""
    dist_info_dir = tmp_path / "pkg-1.0.dist-info"
    dist_info_dir.mkdir()
    lic = dist_info_dir / "licenses"
    lic.mkdir()
    (lic / "LICENSE").write_text("Apache-2.0 OR BSD-2-Clause text\n", encoding="utf-8")
    _write_dist_info_metadata(dist_info_dir, "License-File: LICENSE")

    info_dir = tmp_path / "info"
    info_dir.mkdir()
    meta = PathDistribution(dist_info_dir).metadata
    rel_paths = copy_into_info_licenses(dist_info_dir, info_dir, meta)

    # #300 asserted the buggy info/licenses/licenses/LICENSE here; #322 fixes it.
    assert rel_paths == ["info/licenses/LICENSE"]
    assert "Apache-2.0" in (info_dir / "licenses" / "LICENSE").read_text(encoding="utf-8")


def test_license_file_path_with_licenses_prefix(tmp_path: Path):
    """``License-File: licenses/LICENSE`` at ``…/licenses/LICENSE``."""
    dist_info_dir = tmp_path / "pkg-1.0.dist-info"
    dist_info_dir.mkdir()
    lic = dist_info_dir / "licenses"
    lic.mkdir()
    (lic / "LICENSE").write_text("MIT\n", encoding="utf-8")
    _write_dist_info_metadata(dist_info_dir, "License-File: licenses/LICENSE")

    info_dir = tmp_path / "info"
    info_dir.mkdir()
    meta = PathDistribution(dist_info_dir).metadata
    rel_paths = copy_into_info_licenses(dist_info_dir, info_dir, meta)

    assert rel_paths == ["info/licenses/licenses/LICENSE"]
    assert (info_dir / "licenses" / "licenses" / "LICENSE").read_text() == "MIT\n"


def test_license_file_beside_metadata(tmp_path: Path):
    """``License-File: LICENSE`` as ``…dist-info/LICENSE`` (no ``licenses/`` subdir)."""
    dist_info_dir = tmp_path / "pkg-1.0.dist-info"
    dist_info_dir.mkdir()
    (dist_info_dir / "LICENSE").write_text("BSD\n", encoding="utf-8")
    _write_dist_info_metadata(dist_info_dir, "License-File: LICENSE")

    info_dir = tmp_path / "info"
    info_dir.mkdir()
    meta = PathDistribution(dist_info_dir).metadata
    rel_paths = copy_into_info_licenses(dist_info_dir, info_dir, meta)

    assert rel_paths == ["info/licenses/LICENSE"]
    assert (info_dir / "licenses" / "LICENSE").read_text() == "BSD\n"


def test_license_file_multi_segment_under_licenses_subdir(tmp_path: Path):
    """``License-File: docs/NOTICE`` with file only under ``…/licenses/docs/NOTICE``."""
    dist_info_dir = tmp_path / "pkg-1.0.dist-info"
    dist_info_dir.mkdir()
    doc = dist_info_dir / "licenses" / "docs"
    doc.mkdir(parents=True)
    (doc / "NOTICE").write_text("Legal\n", encoding="utf-8")
    _write_dist_info_metadata(dist_info_dir, "License-File: docs/NOTICE")

    info_dir = tmp_path / "info"
    info_dir.mkdir()
    meta = PathDistribution(dist_info_dir).metadata
    rel_paths = copy_into_info_licenses(dist_info_dir, info_dir, meta)

    assert rel_paths == ["info/licenses/docs/NOTICE"]
    assert (info_dir / "licenses" / "docs" / "NOTICE").read_text() == "Legal\n"


@pytest.mark.parametrize(
    "unsafe_path",
    [
        pytest.param("../LICENSE", id="parent-traversal"),
        pytest.param("foo/../../../LICENSE", id="deep-traversal"),
        pytest.param(
            "/etc/passwd",
            id="absolute-path-unix",
            marks=pytest.mark.skipif(sys.platform == "win32", reason="Unix path"),
        ),
        pytest.param(
            "C:/LICENSE",
            id="absolute-path-win",
            marks=pytest.mark.skipif(sys.platform != "win32", reason="Windows path"),
        ),
    ],
)
def test_license_file_unsafe_path_raises(tmp_path: Path, unsafe_path: str):
    """Reject License-File entries with path traversal or absolute paths."""
    dist_info_dir = tmp_path / "pkg-1.0.dist-info"
    dist_info_dir.mkdir()
    _write_dist_info_metadata(dist_info_dir, f"License-File: {unsafe_path}")

    info_dir = tmp_path / "info"
    info_dir.mkdir()
    meta = PathDistribution(dist_info_dir).metadata

    with pytest.raises(ValueError, match="unsafe path segments"):
        copy_into_info_licenses(dist_info_dir, info_dir, meta)

    assert not (info_dir / "licenses").exists(), "no files should be copied before error"


@pytest.mark.parametrize(
    "license_header,expected",
    [
        pytest.param("License-Expression: MIT", "MIT", id="license-expression"),
        pytest.param("License: MIT License", "MIT License", id="legacy-license"),
    ],
)
def test_license_extracted_from_metadata(tmp_path: Path, license_header: str, expected: str):
    """License metadata (License-Expression or legacy License) is extracted to about dict."""
    dist_info_dir = tmp_path / "pkg-1.0.dist-info"
    dist_info_dir.mkdir()
    body = f"Metadata-Version: 2.4\nName: pkg\nVersion: 1.0\n{license_header}\n\n"
    (dist_info_dir / "METADATA").write_text(body, encoding="utf-8")

    conda_meta = CondaMetadata.from_distribution(PathDistribution(dist_info_dir))
    assert conda_meta.about["license"] == expected
