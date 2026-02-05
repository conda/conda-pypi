import os
import sys
from pathlib import Path

import pytest
from conda.testing.fixtures import CondaCLIFixture
from xprocess import ProcessStarter

pytest_plugins = (
    # Add testing fixtures and internal pytest plugins here
    "conda.testing",
    "conda.testing.fixtures",
)
HERE = Path(__file__).parent

# Use the same Python version as the test environment
PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"


@pytest.fixture(scope="session")
def python_template_env(tmp_path_factory, session_conda_cli: CondaCLIFixture):
    """Create a session-scoped template Python environment for cloning.

    This template environment is created once at the start of the test session.
    Individual tests can clone it using `conda create --clone` instead of
    running a full `conda create` each time, which is faster because it:
    - Skips the solver (no SAT solving needed)
    - Skips downloading (packages already cached)
    - Properly relocates prefixes in metadata and scripts

    Yields:
        Path to the template environment, or None if creation failed.
    """
    template_path = tmp_path_factory.mktemp("python-template-env")
    try:
        session_conda_cli(
            "create", "--yes", "--prefix", str(template_path), f"python={PYTHON_VERSION}"
        )
        yield template_path
    except Exception as e:
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
