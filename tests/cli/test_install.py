"""
Tests that use run `conda pypi install` use `conda_cli` as the primary caller
"""

from __future__ import annotations

import json
import re
from argparse import Namespace
from pathlib import Path

import pytest
from conda.base.context import reset_context
from conda.exceptions import ArgumentError
from conda.testing.fixtures import CondaCLIFixture

import conda_pypi.cli.install as install_cli


def test_cli(conda_cli):
    """
    Test that pypi subcommands exist by checking their help output.
    """
    # Test that install subcommand exists and help works
    # Help commands raise SystemExit, so we need to handle that
    out, err, rc = conda_cli("pypi", "install", "--help", raises=SystemExit)
    assert rc.value.code == 0  # SystemExit(0) means success
    assert "PyPI packages to install" in out
    assert "--dry-run" in out
    assert "--yes" in out

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


@pytest.fixture
def editable_args():
    def factory(project: Path, **overrides) -> Namespace:
        values = {
            "editable": [str(project)],
            "packages": (),
            "dry_run": False,
            "yes": False,
            "ignore_channels": False,
            "index_urls": None,
            "quiet": False,
            "verbosity": 0,
            "prefix": None,
            "name": None,
        }
        values.update(overrides)
        return Namespace(**values)

    return factory


def test_install_editable_dry_run_reports_each_project(
    tmp_path, monkeypatch, mocker, capsys, editable_args
):
    first = tmp_path / "first"
    second = tmp_path / "second"
    prefix = tmp_path / "prefix"
    first.mkdir()
    second.mkdir()

    monkeypatch.setenv("CONDA_JSON", "false")
    reset_context()
    # monkeypatch.setattr("conda.base.context.context", SimpleNamespace(json=False, channels=()))
    build_editable = mocker.Mock()
    install_package = mocker.Mock()
    monkeypatch.setattr("conda_pypi.build.pypa_to_conda", build_editable)
    monkeypatch.setattr("conda_pypi.installer.install_ephemeral_conda", install_package)

    assert (
        install_cli.execute(
            editable_args(
                first,
                editable=[str(first), str(second)],
                dry_run=True,
                prefix=prefix,
            )
        )
        == 0
    )

    build_editable.assert_not_called()
    install_package.assert_not_called()
    output = capsys.readouterr().out
    assert f"from {first} into {prefix}" in output
    assert f"from {second} into {prefix}" in output


@pytest.mark.parametrize(
    "args",
    [
        ("pypi", "install", "--dry-run", "--yes", "-e", "tests/packages/has-build-dep"),
        ("pypi", "--dry-run", "--yes", "install", "-e", "tests/packages/has-build-dep"),
    ],
)
def test_install_editable_dry_run_accepts_output_options(args, conda_cli: CondaCLIFixture):
    out, err, rc = conda_cli(*args)

    assert rc == 0, err
    assert "Dry run: would build and install editable package" in out


def test_install_editable_dry_run_accepts_subcommand_json(conda_cli: CondaCLIFixture):
    out, err, rc = conda_cli(
        "pypi",
        "install",
        "--dry-run",
        "--json",
        "-e",
        "tests/packages/has-build-dep",
    )

    assert rc == 0, err
    json_actions = json.loads(out)
    assert json_actions["success"]
    assert json_actions["dry_run"]
    assert json_actions["editables"] == [str(Path("tests/packages/has-build-dep"))]


def test_install_editable_rejects_package_specs(tmp_path, editable_args):
    project = tmp_path / "project"
    project.mkdir()

    with pytest.raises(ArgumentError, match="Cannot combine --editable"):
        install_cli.execute(editable_args(project, packages=("requests",)))


@pytest.mark.parametrize("yes", [False, True])
def test_install_editable_passes_prompt_state_to_mutating_steps(
    yes, tmp_path, monkeypatch, mocker, editable_args
):
    project = tmp_path / "project"
    prefix = tmp_path / "prefix"
    package = tmp_path / "editable.conda"
    project.mkdir()

    monkeypatch.setenv("CONDA_JSON", "false")
    reset_context()
    # monkeypatch.setattr("conda.base.context.context", SimpleNamespace(json=False, channels=()))
    build_editable = mocker.Mock(return_value=package)
    install_package = mocker.Mock()
    monkeypatch.setattr("conda_pypi.build.pypa_to_conda", build_editable)
    monkeypatch.setattr("conda_pypi.installer.install_ephemeral_conda", install_package)

    assert install_cli.execute(editable_args(project, yes=yes, prefix=prefix)) == 0

    build_editable.assert_called_once()
    assert build_editable.call_args.kwargs["yes"] is yes
    install_package.assert_called_once_with(prefix, package, yes=yes, source=project)


def test_install_editable_installs_multiple_projects_in_order(
    tmp_path, monkeypatch, mocker, editable_args
):
    first = tmp_path / "first"
    second = tmp_path / "second"
    prefix = tmp_path / "prefix"
    first_package = tmp_path / "first.conda"
    second_package = tmp_path / "second.conda"
    first.mkdir()
    second.mkdir()

    monkeypatch.setenv("CONDA_JSON", "false")
    reset_context()
    # monkeypatch.setattr("conda.base.context.context", SimpleNamespace(json=False, channels=()))
    build_editable = mocker.Mock(side_effect=[first_package, second_package])
    install_package = mocker.Mock()
    monkeypatch.setattr("conda_pypi.build.pypa_to_conda", build_editable)
    monkeypatch.setattr("conda_pypi.installer.install_ephemeral_conda", install_package)
    calls = mocker.Mock()
    calls.attach_mock(build_editable, "build")
    calls.attach_mock(install_package, "install")

    assert (
        install_cli.execute(
            editable_args(
                first,
                editable=[str(first), str(second)],
                ignore_channels=True,
                prefix=prefix,
            )
        )
        == 0
    )

    assert calls.mock_calls == [
        mocker.call.build(
            first,
            distribution="editable",
            output_path=mocker.ANY,
            prefix=prefix,
            channels=(),
            yes=False,
        ),
        mocker.call.install(prefix, first_package, yes=False, source=first),
        mocker.call.build(
            second,
            distribution="editable",
            output_path=mocker.ANY,
            prefix=prefix,
            channels=(),
            yes=False,
        ),
        mocker.call.install(prefix, second_package, yes=False, source=second),
    ]


def test_index_urls(tmp_env, conda_cli, pypi_local_index):
    with tmp_env("python=3.10") as prefix:
        with pytest.deprecated_call(match=r"`conda pypi install` for package installs"):
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
        with pytest.deprecated_call(match=r"`conda pypi install` for package installs"):
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
        with pytest.deprecated_call(match=r"`conda pypi install` for package installs"):
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


def test_install_editable_without_packages_succeeds(tmp_env, conda_cli: CondaCLIFixture):
    project = "tests/packages/has-build-dep"
    with tmp_env("python=3.11") as prefix:
        out, err, rc = conda_cli(
            "pypi",
            "--prefix",
            prefix,
            "--yes",
            "install",
            "-e",
            project,
        )
        assert rc == 0
        assert list((prefix / "conda-meta").glob("has-dep-*.json"))


def test_json_output(tmp_env, monkeypatch, conda_cli):
    """Ensure that conda-pypi output respects conda's `--json` config"""
    monkeypatch.setenv("CONDA_JSON", "true")
    reset_context()

    with tmp_env("python=3.10") as prefix:
        with pytest.deprecated_call(match=r"`conda pypi install` for package installs"):
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
        with pytest.deprecated_call(match=r"`conda pypi install` for package installs"):
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
    monkeypatch.setenv("CONDA_JSON", "true")
    reset_context()

    with tmp_env("python=3.12") as prefix:
        out, err, rc = conda_cli(
            "install",
            "--prefix",
            prefix,
            "--channel",
            conda_local_channel,
            "--channel",
            "conda-forge",
            "--override-channels",
            "--strict-channel-priority",
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
