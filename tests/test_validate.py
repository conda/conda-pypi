import sys
from subprocess import run

import pytest
from conda.testing.fixtures import CondaCLIFixture, TmpEnvFixture
from pytest_mock import MockerFixture

from conda_pypi.python_paths import get_env_python, get_externally_managed_path


@pytest.mark.skip(reason="conda-pypi install needs to do more work to support this test.")
def test_externally_managed(
    tmp_env: TmpEnvFixture, conda_cli: CondaCLIFixture, monkeypatch: MockerFixture
):
    """
    conda-pypi places its own EXTERNALLY-MANAGED file when it is installed in an environment.
    We also need to place it in _new_ environments created by conda.
    """
    monkeypatch.setenv("CONDA_ADD_PIP_AS_PYTHON_DEPENDENCY", "0")
    text = get_externally_managed_path(sys.prefix).read_text().strip()
    assert text.startswith("[externally-managed]")
    assert "conda pypi" in text
    with tmp_env("python", "pip>=23.0.1") as prefix:
        conda_cli("pypi", "-p", prefix, "--yes", "install", "requests")
        externally_managed_file = get_externally_managed_path(prefix)

        # Check if EXTERNALLY-MANAGED file was created by conda-pip
        assert externally_managed_file.exists()

        text = (externally_managed_file).read_text().strip()
        assert text.startswith("[externally-managed]")
        assert "conda pypi" in text
        run(
            [get_env_python(prefix), "-m", "pip", "uninstall", "--isolated", "certifi", "-y"],
            capture_output=True,
        )
        p = run(
            [get_env_python(prefix), "-m", "pip", "install", "--isolated", "certifi"],
            capture_output=True,
            text=True,
        )
        print(p.stdout)
        print(p.stderr, file=sys.stderr)
        assert p.returncode != 0
        all_text = p.stderr + p.stdout
        assert "externally-managed-environment" in all_text
        assert "conda pypi" in all_text
        assert "--break-system-packages" in all_text
        p = run(
            [
                get_env_python(prefix),
                "-m",
                "pip",
                "install",
                "--isolated",
                "certifi",
                "--break-system-packages",
            ],
            capture_output=True,
            text=True,
        )
        assert p.returncode == 0
        all_text = p.stderr + p.stdout
        assert (
            "Requirement already satisfied: certifi" in all_text
            or "Successfully installed certifi" in all_text
        )

        # EXTERNALLY-MANAGED is removed when pip is removed
        conda_cli("remove", "-p", prefix, "--yes", "pip")

        # EXTERNALLY-MANAGED is automatically added when pip is reinstalled by the plugin hook
        conda_cli("install", "-p", prefix, "--yes", "pip")
        assert externally_managed_file.exists()
