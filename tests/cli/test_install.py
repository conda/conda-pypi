"""
Tests that use run `conda pypi install` use `conda_cli` as the primary caller
"""

from __future__ import annotations

from conda.base.context import reset_context
from conda.testing.fixtures import CondaCLIFixture

import json
import re
import pytest


def test_cli(conda_cli):
    """
    Test that pypi subcommands exist by checking their help output.
    """
    # Test that install subcommand exists and help works
    # Help commands raise SystemExit, so we need to handle that
    out, err, rc = conda_cli("pypi", "install", "--help", raises=SystemExit)
    assert rc.value.code == 0  # SystemExit(0) means success
    assert "PyPI packages to install" in out

    # Test that convert subcommand exists and help works
    out, err, rc = conda_cli("pypi", "convert", "--help", raises=SystemExit)
    assert rc.value.code == 0
    assert "Convert named path as conda package" in out


def test_cli_plugin():
    # Test that the plugin can be loaded and the subcommand is registered
    from conda_pypi.plugin import conda_subcommands

    subcommands = list(conda_subcommands())
    pypi_subcommand = next((sub for sub in subcommands if sub.name == "pypi"), None)

    assert pypi_subcommand is not None
    assert pypi_subcommand.summary == "Install PyPI packages as conda packages"
    assert pypi_subcommand.action is not None
    assert pypi_subcommand.configure_parser is not None


def test_index_urls(tmp_env, conda_cli, pypi_local_index):
    with tmp_env("python=3.10") as prefix:
        out, err, rc = conda_cli(
            "pypi",
            "--yes",
            "install",
            "--ignore-channels",
            "--prefix",
            prefix,
            "--index-url",
            pypi_local_index,
            "demo-package",
        )
        assert "Converted packages\n - demo-package==0.1.0" in out
        assert rc == 0


def test_install_output(tmp_env, conda_cli):
    with tmp_env("python=3.12") as prefix:
        out, err, rc = conda_cli(
            "pypi",
            "--yes",
            "install",
            "--ignore-channels",
            "--prefix",
            prefix,
            "scipy",
        )

        assert rc == 0

        # strip spinner characters
        out = out.replace(" \x08\x08/", "")
        out = out.replace(" \x08\x08-", "")
        out = out.replace(" \x08\x08\\", "")
        out = out.replace(" \x08\x08|", "")
        out = out.replace(" \x08\x08", "")

        # Ensure a message about the converted packages is shown
        assert "Converted packages" in out

        # Ensure the solver messaging is only showed once when the final solve/install happens
        assert len(re.findall(r"Solving environment:", out)) == 1


def test_install_jupyterlab_package(tmp_env, conda_cli):
    with tmp_env("python=3.10") as prefix:
        out, err, rc = conda_cli(
            "pypi",
            "--yes",
            "install",
            "--ignore-channels",
            "--prefix",
            prefix,
            "jupyterlab",
        )
        assert rc == 0


def test_install_requires_package_without_editable(conda_cli: CondaCLIFixture):
    with pytest.raises(SystemExit) as exc:
        conda_cli("pypi", "install")
    assert exc.value.code == 2


def test_install_editable_without_packages_succeeds(conda_cli: CondaCLIFixture):
    project = "tests/packages/has-build-dep"
    out, err, rc = conda_cli("pypi", "install", "-e", project)
    assert rc == 0


def test_json_output(tmp_env, monkeypatch, conda_cli):
    """Ensure that conda-pypi output respects conda's `--json` config"""
    monkeypatch.setenv("CONDA_JSON", True)
    reset_context()

    with tmp_env("python=3.10") as prefix:
        out, err, rc = conda_cli(
            "pypi",
            "--yes",
            "install",
            "--prefix",
            prefix,
            "imagesize",
        )
        json_actions = json.loads(out)
        assert rc == 0
        assert json_actions["prefix"] == str(prefix)
        assert json_actions["success"]


def test_install_package_with_hyphens(tmp_env, conda_cli):
    """Test that PyPI packages with hyphens in names are correctly translated.

    This ensures packages like 'huggingface-hub' are converted to 'huggingface_hub'
    and can be found by the solver after conversion.
    """
    with tmp_env("python=3.10") as prefix:
        # Use a simple package with hyphens in the name
        out, err, rc = conda_cli(
            "pypi",
            "--yes",
            "install",
            "--ignore-channels",
            "--prefix",
            prefix,
            "typing-extensions",  # PyPI name with hyphen
        )

        # Should succeed without PackagesNotFoundError
        assert rc == 0

        # The converted package should use underscores
        assert "typing_extensions" in out or "typing-extensions" in out


def test_install_from_whl_augmented_repodata(
    tmp_env, monkeypatch, conda_cli, conda_local_channel, with_rattler_solver
):
    monkeypatch.setenv("CONDA_JSON", "True")
    reset_context()

    with tmp_env("python=3.12") as prefix:
        out, err, rc = conda_cli(
            "install",
            "--prefix",
            prefix,
            "--channel",
            conda_local_channel,
            "--override-channels",
            "idna",
            "--yes",
        )
        assert rc == 0, f"Failed to install from wheel channel: {err}"

        json_actions = json.loads(out)
        installed = [act["name"] for act in json_actions["actions"]["LINK"]]
        assert "idna" in installed, f"idna should be installed, got: {installed}"

        idna_action = next(act for act in json_actions["actions"]["LINK"] if act["name"] == "idna")
        assert conda_local_channel in idna_action.get("base_url", ""), (
            f"idna should come from {conda_local_channel}"
        )
