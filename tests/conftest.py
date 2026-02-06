import sys
from pathlib import Path

import pytest
from conda.base.context import context, reset_context
from conda.testing import http_test_server
from conda.testing.fixtures import CondaCLIFixture

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
        Path to the template environment.
    """
    template_path = tmp_path_factory.mktemp("python-template-env")
    session_conda_cli(
        "create", "--yes", "--prefix", str(template_path), f"python={PYTHON_VERSION}"
    )
    yield template_path


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
def pypi_local_index():
    """
    Runs a local PyPI index by serving the folder "tests/pypi_local_index"
    """
    base = HERE / "pypi_local_index"
    http = http_test_server.run_test_server(str(base))

    http_sock_name = http.socket.getsockname()
    yield f"http://{http_sock_name[0]}:{http_sock_name[1]}"

    http.shutdown()


@pytest.fixture(scope="session")
def conda_local_channel():
    """
    Runs a local conda channel by serving the folder "tests/conda_local_channel"
    This provides a mock conda channel with pre-converted packages for testing
    dependency resolution without requiring network access.
    """
    base = HERE / "conda_local_channel"
    http = http_test_server.run_test_server(str(base))

    http_sock_name = http.socket.getsockname()
    yield f"http://{http_sock_name[0]}:{http_sock_name[1]}"

    http.shutdown()


@pytest.fixture()
def with_rattler_solver(monkeypatch):
    """Clear the plugin manager's solver backend cache and set rattler as the solver."""
    context.plugin_manager.get_cached_solver_backend.cache_clear()
    monkeypatch.setenv("CONDA_SOLVER", "rattler")
    reset_context()
    assert context.solver == "rattler"
