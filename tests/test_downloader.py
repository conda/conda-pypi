"""
Test handling of packages without wheels (source distributions only).

This test verifies issue #121: when a package has no wheel available (only source
distributions), the conversion should fail early with a meaningful error rather
than looping until max attempts (20).
"""

import os
from pathlib import Path

import pytest
from conda.testing.fixtures import TmpEnvFixture

from conda_pypi.exceptions import CondaPypiError

REPO = Path(__file__).parents[1] / "synthetic_repo"


def test_downloader_detects_no_wheels(tmp_env: TmpEnvFixture, monkeypatch, tmp_path: Path):
    """
    Test that the downloader correctly raises an error when no wheels are available.
    """
    import tempfile

    from conda_pypi.downloader import find_and_fetch, get_package_finder

    CONDA_PKGS_DIRS = tmp_path / "test-pkgs"
    CONDA_PKGS_DIRS.mkdir(exist_ok=True)
    monkeypatch.setitem(os.environ, "CONDA_PKGS_DIRS", str(CONDA_PKGS_DIRS))

    with tmp_env("python=3.12", "pip") as prefix:
        finder = get_package_finder(prefix)

        # Package "ach" only has source distributions
        with pytest.raises(CondaPypiError) as exc_info:
            with tempfile.TemporaryDirectory() as tmpdir:
                find_and_fetch(finder, Path(tmpdir), "ach")

        # Verify we get a meaningful error message
        error_msg = str(exc_info.value).lower()
        assert "wheel" in error_msg, f"Expected error message to mention 'wheel', got: {error_msg}"
        assert "source distributions" in error_msg or "only source" in error_msg, (
            f"Expected error message to mention source distributions, got: {error_msg}"
        )
