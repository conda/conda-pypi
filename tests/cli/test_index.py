"""
Tests for the `conda pypi index` subcommand.
"""

import json
import shutil
import zipfile
from argparse import Namespace
from pathlib import Path

import pytest
from conda.exceptions import ArgumentError

from conda_pypi.cli.index import execute, validate_dir_and_return_whl_files

here = Path(__file__).parent.parent


def test_cli(conda_cli):
    """
    Test that index subcommands exist.
    """
    out, err, rc = conda_cli("pypi", "index", "--help", raises=SystemExit)
    assert rc.value.code == 0
    assert "DIRECTORY" in out


def test_validate_dir_not_a_directory(tmp_path):
    """Test invalid dir"""
    not_a_dir = tmp_path / "file.txt"
    with pytest.raises(ArgumentError, match="Not a directory"):
        validate_dir_and_return_whl_files(not_a_dir)


def test_validate_dir_empty(tmp_path):
    """Test empty dir"""
    with pytest.raises(SystemExit):
        validate_dir_and_return_whl_files(tmp_path)


def test_validate_dir_with_empty_subdirs(tmp_path):
    """Test dir with empty subdirs"""
    (tmp_path / "somedir").mkdir()
    with pytest.raises(SystemExit):
        validate_dir_and_return_whl_files(tmp_path)


def test_validate_dir_no_subdirectories(tmp_path):
    (tmp_path / "somefile.txt").write_text("hello")
    with pytest.raises(SystemExit):
        validate_dir_and_return_whl_files(tmp_path)


def test_validate_dir_returns_wheels():
    """Test valid dir"""
    result = validate_dir_and_return_whl_files(here / "pypi_local_index")
    assert len(result) > 1
    assert any(wheel.name == "demo_package-0.1.0-py3-none-any.whl" for wheel in result)


def test_execute_indexes_wheels(tmp_path):
    """
    Test that execute() reads .whl files from a directory structure and produces
    a repodata.json with entries under v3.whl.
    """
    shutil.copytree(here / "pypi_local_index", tmp_path / "pypi_local_index")

    args = Namespace(directory=tmp_path / "pypi_local_index", base_url=None)
    result = execute(args)

    assert result == 0

    repodata = json.loads((tmp_path / "pypi_local_index" / "noarch" / "repodata.json").read_text())
    assert "v3" in repodata
    assert "whl" in repodata["v3"]
    assert len(repodata["v3"]["whl"]) == 6


def test_execute_reports_failed_wheels(tmp_path, capsys):
    """Test OS/BadZipFile Error"""
    pkg_dir = tmp_path / "bad-package"
    pkg_dir.mkdir()
    (pkg_dir / "bad_package-1.0.0-py3-none-any.whl").write_bytes(b"not a real wheel")

    args = Namespace(directory=tmp_path, base_url=None)
    result = execute(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "Failed to read" in captured.out


def make_wheel(
    path: Path, name: str, version: str, requires_dist: list[str] = (), platform: str = "none-any"
) -> Path:
    """Create a minimal valid .whl file with given metadata."""
    wheel_name = f"{name}-{version}-py3-{platform}.whl"
    wheel_path = path / wheel_name
    metadata = "\n".join(
        [
            "Metadata-Version: 2.1",
            f"Name: {name}",
            f"Version: {version}",
            *[f"Requires-Dist: {req}" for req in requires_dist],
        ]
    )
    with zipfile.ZipFile(wheel_path, "w") as zf:
        zf.writestr(f"{name}-{version}.dist-info/METADATA", metadata)
        zf.writestr(f"{name}-{version}.dist-info/WHEEL", "Wheel-Version: 1.0\n")
    return wheel_path


def test_execute_skips_wheel_with_invalid_requirement(tmp_path, capsys):
    """Test that a wheel with a malformed Requires-Dist is skipped without crashing indexing."""
    pkg_dir = tmp_path / "bad-package"
    pkg_dir.mkdir()
    make_wheel(pkg_dir, "bad_package", "1.0.0", requires_dist=["!!!invalid!!!"])

    args = Namespace(directory=tmp_path, base_url=None)
    result = execute(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "invalid metadata" in captured.out


def test_execute_skips_platform_specific_wheel(tmp_path, capsys):
    """Test that a platform-specific wheel cannot be converted to a repodata entry and is skipped."""
    pkg_dir = tmp_path / "bad-package"
    pkg_dir.mkdir()
    make_wheel(pkg_dir, "bad_package", "1.0.0", platform="cp311-win_amd64")

    args = Namespace(directory=tmp_path, base_url=None)
    result = execute(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "not a pure-python wheel" in captured.out


def test_base_url_is_passed(tmp_path):
    """Test that if `--base-url` is passed, it is used to construct the URL for each entry in repodata.json"""
    shutil.copytree(here / "pypi_local_index", tmp_path / "pypi_local_index")
    args = Namespace(directory=tmp_path / "pypi_local_index", base_url="https://example.com/")
    result = execute(args)

    assert result == 0
    repodata = json.loads((tmp_path / "pypi_local_index" / "noarch" / "repodata.json").read_text())
    for entry in repodata["v3"]["whl"].values():
        assert entry["url"].startswith("https://example.com/")


def test_execute_expands_user_in_directory(tmp_path, monkeypatch):
    """Test that ~ in directory path is expanded to the user's home directory."""
    shutil.copytree(here / "pypi_local_index", tmp_path / "pypi_local_index")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # for windows

    args = Namespace(directory=Path("~/pypi_local_index"), base_url=None)
    result = execute(args)

    assert result == 0
    assert (tmp_path / "pypi_local_index" / "noarch" / "repodata.json").exists()
