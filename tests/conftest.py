import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from conda.testing.fixtures import TmpEnvFixture
from xprocess import ProcessStarter

pytest_plugins = (
    # Add testing fixtures and internal pytest plugins here
    "conda.testing",
    "conda.testing.fixtures",
)
HERE = Path(__file__).parent

# Use the same Python version as the test environment
PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"


def clone_env(template_path: Path, target_path: Path) -> bool:
    """Clone a conda environment using platform-specific fast copy methods.

    Uses copy-on-write or reflink cloning where available:
    - macOS (APFS): cp -c for copy-on-write (~1.8s)
    - Linux: cp --reflink=auto for reflinks on btrfs/xfs, else regular copy
    - Windows: robocopy /mir for multi-threaded copy, falls back to shutil.copytree

    This is much faster than creating an environment from scratch (~10s)
    because it avoids the conda solver and package extraction steps.

    Args:
        template_path: Path to the template environment to clone
        target_path: Path where the cloned environment should be created

    Returns:
        True if cloning succeeded, False otherwise
    """
    try:
        if sys.platform == "darwin":
            # macOS: APFS copy-on-write
            result = subprocess.run(
                ["cp", "-cR", str(template_path), str(target_path)],
                capture_output=True,
            )
            if result.returncode == 0:
                return True
            # Fall through to shutil.copytree if APFS clone fails

        elif sys.platform.startswith("linux"):
            # Linux: try reflink (works on btrfs, xfs with reflink support)
            # --reflink=auto falls back to regular copy if not supported
            result = subprocess.run(
                ["cp", "-R", "--reflink=auto", str(template_path), str(target_path)],
                capture_output=True,
            )
            if result.returncode == 0:
                return True
            # Fall through to shutil.copytree if cp fails

        elif sys.platform == "win32":
            # Windows: use robocopy for faster multi-threaded copying
            # /e = copy subdirectories including empty ones
            # /mt:8 = multi-threaded with 8 threads
            # /nfl /ndl /njh /njs = suppress output for speed
            # robocopy returns 0-7 for success, 8+ for errors
            result = subprocess.run(
                [
                    "robocopy",
                    str(template_path),
                    str(target_path),
                    "/e",
                    "/mt:8",
                    "/nfl",
                    "/ndl",
                    "/njh",
                    "/njs",
                ],
                capture_output=True,
            )
            # robocopy exit codes: 0-7 = success, 8+ = error
            if result.returncode < 8:
                return True
            # Fall through to shutil.copytree if robocopy fails

        # Fallback: use Python's cross-platform copy
        shutil.copytree(template_path, target_path)
        return True

    except (OSError, shutil.Error, subprocess.SubprocessError):
        # If clone fails, clean up and return False
        if target_path.exists():
            shutil.rmtree(target_path, ignore_errors=True)
        return False


@pytest.fixture(scope="session")
def python_template_env(session_tmp_env: TmpEnvFixture):
    """Create a session-scoped template Python environment.

    This template environment is created once at the start of the test session
    using conda's built-in session_tmp_env fixture. It can be cloned for
    individual tests instead of running `conda create` each time, significantly
    speeding up tests that need Python environments.

    The template contains only Python, which is sufficient for most benchmark
    tests that just need a Python interpreter.

    Yields:
        Path to the template environment, or None if creation failed.
    """
    try:
        # Use conda's session_tmp_env fixture to create the template
        # This leverages the official conda testing infrastructure
        with session_tmp_env(f"python={PYTHON_VERSION}") as template_path:
            # Yield the template path for the entire session
            yield template_path
    except Exception as e:
        # Don't fail tests if template creation fails
        import warnings

        warnings.warn(f"Failed to create template environment: {e}")
        yield None


@pytest.fixture(autouse=True)
def do_not_register_envs(monkeypatch):
    """Do not register environments created during tests"""
    monkeypatch.setenv("CONDA_REGISTER_ENVS", "false")


@pytest.fixture(autouse=True)
def do_not_notify_outdated_conda(monkeypatch):
    """Do not notify about outdated conda during tests"""
    monkeypatch.setenv("CONDA_NOTIFY_OUTDATED_CONDA", "false")


@pytest.fixture(scope="session")
def pypi_demo_package_wheel_path() -> Path:
    return HERE / "pypi_local_index" / "demo-package" / "demo_package-0.1.0-py3-none-any.whl"


@pytest.fixture(scope="session")
def pypi_local_index(xprocess):
    """
    Runs a local PyPI index by serving the folder "tests/pypi_local_index"
    """
    port = "8035"

    class Starter(ProcessStarter):
        pattern = "Serving HTTP on"
        timeout = 10
        args = [sys.executable, "-m", "http.server", "-d", HERE / "pypi_local_index", port]
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

    # ensure process is running and return its logfile
    xprocess.ensure("pypi_local_index", Starter)

    yield f"http://localhost:{port}"

    xprocess.getinfo("pypi_local_index").terminate()
