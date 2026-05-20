"""Tests for `conda pypi migrate-env`."""

from pathlib import Path
from textwrap import dedent

import pytest
from conda.cli.main import main_subshell
from conda.exceptions import ArgumentError, DryRunExit, PackagesNotFoundError
from pytest_mock import MockerFixture
from ruamel.yaml import YAML

from conda_pypi.migrate_env import (
    DEFAULT_WHEELS_CHANNEL,
    _dry_run_solve,
    migrate_environment,
)

_YAML = YAML()
_YAML.default_flow_style = False


def _load(text: str) -> dict:
    return _YAML.load(dedent(text))


def _write_env(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "environment.yaml"
    path.write_text(dedent(content))
    return path


def _mock_solve_success(mocker: MockerFixture) -> None:
    """Patch _dry_run_solve to return an empty set (all packages resolved)."""
    mocker.patch("conda_pypi.migrate_env._dry_run_solve", return_value=set())


def _mock_solve_missing(mocker: MockerFixture, *conda_names: str) -> None:
    """Patch _dry_run_solve to report *conda_names* as unresolvable."""
    mocker.patch(
        "conda_pypi.migrate_env._dry_run_solve",
        return_value={n.lower() for n in conda_names},
    )


def test_migrate_promotes_all_when_solve_succeeds(mocker):
    """When the solver succeeds, all pip packages move to conda deps."""
    _mock_solve_success(mocker)
    env = _load(
        """
        name: myenv
        channels:
          - conda-forge
        dependencies:
          - numpy
          - pip:
            - requests>=2.28.0
            - flask
        """
    )
    result, warnings = migrate_environment(env, ["https://example.com/wheels"])

    deps = result["dependencies"]
    assert "requests>=2.28.0" in deps
    assert "flask" in deps
    pip_blocks = [d for d in deps if isinstance(d, dict) and "pip" in d]
    assert not pip_blocks
    assert not warnings


def test_migrate_removes_bare_pip_dep_when_pip_block_cleared(mocker):
    """Bare 'pip' conda dep is removed when the pip: block is fully promoted."""
    _mock_solve_success(mocker)
    env = _load(
        """
        name: myenv
        dependencies:
          - python=3.12
          - pip
          - pip:
            - requests
        """
    )
    result, _ = migrate_environment(env, ["https://example.com/wheels"])

    deps = result["dependencies"]
    assert "requests" in deps
    # bare pip dep should be removed when pip block is gone
    assert "pip" not in deps


def test_migrate_keeps_versioned_pip_dep(mocker):
    """Version-constrained 'pip>=X' entry is preserved even when pip block is cleared."""
    _mock_solve_success(mocker)
    env = _load(
        """
        name: myenv
        dependencies:
          - pip>=23
          - pip:
            - requests
        """
    )
    result, _ = migrate_environment(env, ["https://example.com/wheels"])

    assert "pip>=23" in result["dependencies"]


def test_migrate_keeps_pip_dep_when_pip_block_remains(mocker):
    """Bare 'pip' conda dep is kept when some packages still need the pip block."""
    _mock_solve_missing(mocker, "some-private-pkg")
    env = _load(
        """
        name: myenv
        dependencies:
          - pip
          - pip:
            - requests
            - some-private-pkg
        """
    )
    result, _ = migrate_environment(env, ["https://example.com/wheels"])

    # pip dep should stay when pip block still has entries
    assert "pip" in result["dependencies"]


def test_migrate_demotes_missing_packages(mocker):
    """Packages the solver cannot find are put back in the pip block with a warning."""
    _mock_solve_missing(mocker, "some-private-pkg")
    env = _load(
        """
        name: myenv
        channels:
          - conda-forge
        dependencies:
          - numpy
          - pip:
            - requests
            - some-private-pkg
        """
    )
    result, warnings = migrate_environment(env, ["https://example.com/wheels"])

    deps = result["dependencies"]
    assert "requests" in deps
    pip_blocks = [d for d in deps if isinstance(d, dict) and "pip" in d]
    assert pip_blocks
    assert "some-private-pkg" in pip_blocks[0]["pip"]
    assert len(warnings) == 1
    assert "some-private-pkg" in warnings[0]


def test_migrate_adds_channel_when_packages_promoted(mocker):
    """The wheels channel URL is appended to channels: when promotions occurred."""
    _mock_solve_success(mocker)
    channel_url = "https://example.com/wheels"
    env = _load(
        """
        name: myenv
        channels:
          - conda-forge
        dependencies:
          - pip:
            - requests
        """
    )
    result, _ = migrate_environment(env, [channel_url])

    assert channel_url in result["channels"]


def test_migrate_does_not_add_channel_when_nothing_promoted(mocker):
    """Channel is not added when no packages were promoted."""
    _mock_solve_missing(mocker, "some-private-pkg")
    channel_url = "https://example.com/wheels"
    env = _load(
        """
        name: myenv
        channels:
          - conda-forge
        dependencies:
          - pip:
            - some-private-pkg
        """
    )
    result, _ = migrate_environment(env, [channel_url])

    assert channel_url not in result.get("channels", [])


def test_migrate_does_not_duplicate_channel(mocker):
    """Channel is not added twice when already present in channels:."""
    _mock_solve_success(mocker)
    channel_url = "https://example.com/wheels"
    env = _load(
        f"""
        name: myenv
        channels:
          - conda-forge
          - {channel_url}
        dependencies:
          - pip:
            - requests
        """
    )
    result, _ = migrate_environment(env, [channel_url])

    assert result["channels"].count(channel_url) == 1


def test_migrate_no_pip_section(mocker):
    """Environment file without a pip block returns unchanged with no warnings."""
    _mock_solve_success(mocker)
    env = _load(
        """
        name: myenv
        channels:
          - conda-forge
        dependencies:
          - numpy
          - pandas
        """
    )
    result, warnings = migrate_environment(env, ["https://example.com/wheels"])

    assert result["dependencies"] == ["numpy", "pandas"]
    assert not warnings


def test_migrate_preserves_version_specifier(mocker):
    """Version specifiers from pip deps are preserved in the promoted conda dep."""
    _mock_solve_success(mocker)
    env = _load(
        """
        name: myenv
        dependencies:
          - pip:
            - "flask>=2.0,<3"
        """
    )
    result, _ = migrate_environment(env, ["https://example.com/wheels"])

    # packaging may reorder specifiers (e.g. ">=2.0,<3" → "<3,>=2.0")
    flask_deps = [d for d in result["dependencies"] if str(d).startswith("flask")]
    assert flask_deps
    assert ">=2.0" in flask_deps[0]
    assert "<3" in flask_deps[0]


def test_migrate_pip_only_editable_kept_silently(mocker):
    """Editable installs (-e .) are recognised as pip-only and kept without a warning."""
    _mock_solve_success(mocker)
    env = _load(
        """
        name: myenv
        dependencies:
          - pip:
            - requests
            - -e .
        """
    )
    result, warnings = migrate_environment(env, ["https://example.com/wheels"])

    pip_blocks = [d for d in result["dependencies"] if isinstance(d, dict) and "pip" in d]
    assert pip_blocks
    assert "-e ." in pip_blocks[0]["pip"]
    assert not warnings


def test_migrate_pip_only_local_path_kept_silently(mocker):
    """Local path deps (./pkg.whl, git+...) are kept in pip without a warning."""
    _mock_solve_success(mocker)
    env = _load(
        """
        name: myenv
        dependencies:
          - pip:
            - requests
            - ./local/path/package.whl
            - git+https://github.com/example/repo.git
        """
    )
    result, warnings = migrate_environment(env, ["https://example.com/wheels"])

    pip_blocks = [d for d in result["dependencies"] if isinstance(d, dict) and "pip" in d]
    assert pip_blocks
    pip_section = pip_blocks[0]["pip"]
    assert "./local/path/package.whl" in pip_section
    assert "git+https://github.com/example/repo.git" in pip_section
    assert not warnings


def test_migrate_unsatisfiable_demotes_to_pip(mocker):
    """Packages reported as unresolvable are demoted back to pip."""
    _mock_solve_missing(mocker, "conflicting-pkg")
    env = _load(
        """
        name: myenv
        dependencies:
          - pip:
            - requests
            - conflicting-pkg
        """
    )
    result, _ = migrate_environment(env, ["https://example.com/wheels"])

    deps = result["dependencies"]
    assert "requests" in deps
    pip_blocks = [d for d in deps if isinstance(d, dict) and "pip" in d]
    assert pip_blocks
    assert "conflicting-pkg" in pip_blocks[0]["pip"]


def test_dry_run_solve_returns_empty_on_dry_run_exit(mocker):
    """_dry_run_solve returns empty set when main_subshell raises DryRunExit."""
    mocker.patch("conda_pypi.migrate_env.main_subshell", side_effect=DryRunExit())
    assert _dry_run_solve(["python"], ["conda-forge"]) == set()


def test_dry_run_solve_returns_missing_on_packages_not_found(mocker):
    """_dry_run_solve extracts missing names from PackagesNotFoundError."""
    mocker.patch(
        "conda_pypi.migrate_env.main_subshell",
        side_effect=PackagesNotFoundError(["some-private-pkg"]),
    )
    assert "some-private-pkg" in _dry_run_solve(["python"], ["conda-forge"])


def test_dry_run_solve_returns_empty_on_unexpected_error(mocker):
    """_dry_run_solve returns empty set (and warns) on unexpected exceptions."""
    mocker.patch("conda_pypi.migrate_env.main_subshell", side_effect=RuntimeError("boom"))
    assert _dry_run_solve(["python"], ["conda-forge"]) == set()


def test_cli_migrate_env_stdout(tmp_path, mocker, capsys):
    """migrate-env writes YAML to stdout by default."""
    _mock_solve_success(mocker)
    env_file = _write_env(
        tmp_path,
        """
        name: myenv
        channels:
          - conda-forge
        dependencies:
          - numpy
          - pip:
            - requests
        """,
    )
    main_subshell("pypi", "migrate-env", str(env_file))

    out = capsys.readouterr().out
    assert "requests" in out
    assert "pip:" not in out


def test_cli_migrate_env_output_to_file(tmp_path, mocker):
    """--file writes the rewritten file to the given path."""
    _mock_solve_success(mocker)
    env_file = _write_env(
        tmp_path,
        """
        name: myenv
        dependencies:
          - pip:
            - requests
        """,
    )
    out_file = tmp_path / "out.yaml"
    main_subshell("pypi", "migrate-env", "--file", str(out_file), str(env_file))

    assert out_file.exists()
    assert "requests" in out_file.read_text()


def test_cli_migrate_env_in_place(tmp_path, mocker):
    """--in-place overwrites the input file."""
    _mock_solve_success(mocker)
    env_file = _write_env(
        tmp_path,
        """
        name: myenv
        dependencies:
          - pip:
            - requests
        """,
    )
    main_subshell("pypi", "migrate-env", "--in-place", str(env_file))

    content = env_file.read_text()
    assert "requests" in content
    assert "pip:" not in content


def test_cli_migrate_env_missing_file(tmp_path):
    """migrate-env raises an error when ENV_FILE does not exist."""
    with pytest.raises((ArgumentError, SystemExit)):
        main_subshell("pypi", "migrate-env", str(tmp_path / "nonexistent.yaml"))


def test_cli_migrate_env_custom_channel(tmp_path, mocker):
    """--channel is passed through to the solver; DEFAULT_WHEELS_CHANNEL is not used."""
    custom_channel = "https://custom.example.com/wheels"
    captured_calls: list[tuple[list[str], list[str]]] = []

    def _capture(specs: list[str], channels: list[str]) -> set[str]:
        captured_calls.append((specs, channels))
        return set()

    mocker.patch("conda_pypi.migrate_env._dry_run_solve", side_effect=_capture)
    env_file = _write_env(
        tmp_path,
        """
        name: myenv
        dependencies:
          - pip:
            - requests
        """,
    )
    main_subshell("pypi", "migrate-env", "-c", custom_channel, str(env_file))

    assert captured_calls
    _, channels_used = captured_calls[0]
    assert custom_channel in channels_used
    assert DEFAULT_WHEELS_CHANNEL not in channels_used
