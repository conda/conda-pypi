from importlib.metadata import PathDistribution
from pathlib import Path

from conda_pypi.license_files import copy_licenses_into_info


def _write_metadata(dist_info: Path, *license_file_lines: str) -> None:
    lines = [
        "Metadata-Version: 2.4",
        "Name: pkg",
        "Version: 1.0",
        *license_file_lines,
        "",
        "",
    ]
    (dist_info / "METADATA").write_text("\n".join(lines), encoding="utf-8")


def test_license_file_short_name_under_dist_info_licenses(tmp_path: Path):
    """Like PyPI ``packaging``: ``License-File: LICENSE`` under ``.dist-info/licenses/``."""
    dist_info = tmp_path / "pkg-1.0.dist-info"
    dist_info.mkdir()
    lic_dir = dist_info / "licenses"
    lic_dir.mkdir()
    (lic_dir / "LICENSE").write_text("Apache-2.0 OR BSD-2-Clause text\n", encoding="utf-8")
    _write_metadata(dist_info, "License-File: LICENSE")

    info_dir = tmp_path / "info"
    info_dir.mkdir()
    meta = PathDistribution(dist_info).metadata
    rel_paths = copy_licenses_into_info(dist_info, info_dir, meta, about=None)

    assert rel_paths == ["info/licenses/licenses__LICENSE"]
    copied = (info_dir / "licenses" / "licenses__LICENSE").read_text(encoding="utf-8")
    assert "Apache-2.0" in copied


def test_license_file_relative_path_licenses_subdir(tmp_path: Path):
    """``License-File: licenses/LICENSE`` with file at ``.dist-info/licenses/LICENSE``."""
    dist_info = tmp_path / "pkg-1.0.dist-info"
    dist_info.mkdir()
    lic_dir = dist_info / "licenses"
    lic_dir.mkdir()
    (lic_dir / "LICENSE").write_text("MIT\n", encoding="utf-8")
    _write_metadata(dist_info, "License-File: licenses/LICENSE")

    info_dir = tmp_path / "info"
    info_dir.mkdir()
    meta = PathDistribution(dist_info).metadata
    rel_paths = copy_licenses_into_info(dist_info, info_dir, meta, about=None)

    assert rel_paths == ["info/licenses/licenses__LICENSE"]
    assert (info_dir / "licenses" / "licenses__LICENSE").read_text() == "MIT\n"


def test_license_file_flat_in_dist_info(tmp_path: Path):
    """``License-File: LICENSE`` next to ``METADATA`` (no ``licenses/`` subdir)."""
    dist_info = tmp_path / "pkg-1.0.dist-info"
    dist_info.mkdir()
    (dist_info / "LICENSE").write_text("BSD\n", encoding="utf-8")
    _write_metadata(dist_info, "License-File: LICENSE")

    info_dir = tmp_path / "info"
    info_dir.mkdir()
    meta = PathDistribution(dist_info).metadata
    rel_paths = copy_licenses_into_info(dist_info, info_dir, meta, about=None)

    assert rel_paths == ["info/licenses/LICENSE"]
    assert (info_dir / "licenses" / "LICENSE").read_text() == "BSD\n"
