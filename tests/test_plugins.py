from pathlib import Path
from types import SimpleNamespace

import pytest
from conda.base.context import context, reset_context
from conda.cli.conda_argparse import generate_parser
from conda.core.prefix_data import PrefixData
from conda.models.environment import Environment
from conda.plugins.types import CondaSetting
from conda.testing.fixtures import CondaCLIFixture, TmpEnvFixture
from pytest_mock import MockerFixture

import conda_pypi.main
from conda_pypi.main import notify_conda_pypi_tip, pip_newly_linked
from conda_pypi.package_extractors import whl
from conda_pypi.plugin import conda_settings

WHL_HTTP_URL = "https://files.pythonhosted.org/packages/45/7f/0e961cf3908bc4c1c3e027de2794f867c6c89fb4916fc7dba295a0e80a2d/boltons-25.0.0-py3-none-any.whl"
CONDA_URL = "https://repo.anaconda.com/pkgs/main/osx-arm64/boltons-25.0.0-py314hca03da5_0.conda"


@pytest.mark.parametrize(
    "package,call_count",
    [
        pytest.param(WHL_HTTP_URL, 1, id=".whl url"),
        pytest.param("{file}", 1, id=".whl file"),
        pytest.param("file:///{file}", 1, id=".whl file url"),
        pytest.param(CONDA_URL, 0, id=".conda url"),
    ],
)
def test_extract_whl_as_conda_called(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
    mocker: MockerFixture,
    pypi_demo_package_wheel_path: Path,
    tmp_pkgs_dir: Path,  # use empty package cache directory
    tmp_path: Path,
    package: str,
    call_count: int,
):
    # Check .whl extractor is registered
    assert context.plugin_manager.get_package_extractor(".whl")

    package = package.format(file=pypi_demo_package_wheel_path)
    with tmp_env() as prefix:
        # mock python installed in prefix
        mocker.patch(
            "conda.core.link.UnlinkLinkTransaction._get_python_info",
            return_value=("3.10", str(tmp_path)),
        )

        # spy on the wheel extractor function
        spy = mocker.spy(whl, "extract_whl_as_conda_pkg")

        # install package
        _, _, err = conda_cli("install", f"--prefix={prefix}", package)
        assert not err

        # wheel extraction only happens for .whl
        assert spy.call_count == call_count


def test_extract_whl_as_conda_pkg(
    pypi_demo_package_wheel_path: Path,
    tmp_path: Path,
):
    whl.extract_whl_as_conda_pkg(pypi_demo_package_wheel_path, tmp_path)
    assert (tmp_path / "info" / "index.json").is_file()


def _prec(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


@pytest.fixture
def notify_with_condarc(isolated_conda_context, mocker: MockerFixture, tmp_path: Path):
    """Factory fixture to run notify_conda_pypi_tip under a real condarc configuration."""

    def _run(
        condarc_yaml: str,
        *,
        link: tuple[str, ...] = ("pip",),
        unlink: tuple[str, ...] = (),
        target: str = "env",
        argparse_args: object = None,
    ):
        condarc_file = tmp_path / "condarc.yaml"
        condarc_file.write_text(condarc_yaml, encoding="utf-8")
        search_path = [str(condarc_file)]
        reset_context(search_path)
        if argparse_args is not None:
            context.__init__(argparse_args=argparse_args, search_path=search_path)
        target_path = str(context.conda_prefix) if target == "base" else str(tmp_path / target)
        mock_logger = mocker.patch("conda_pypi.main.logger")
        notify_conda_pypi_tip(
            target_prefix=target_path,
            link_precs=[_prec(name) for name in link],
            unlink_precs=[_prec(name) for name in unlink],
        )
        return mock_logger

    return _run


@pytest.mark.parametrize(
    "link,unlink,expected",
    [
        (("pip",), (), True),
        (("pip", "python"), (), True),
        (("pip",), ("pip",), False),
        (("python",), (), False),
        ((), (), False),
        (("python",), ("pip",), False),
    ],
)
def test_pip_newly_linked(link, unlink, expected):
    assert (
        pip_newly_linked([_prec(name) for name in link], [_prec(name) for name in unlink])
        is expected
    )


def test_notify_logs_tip_when_pip_newly_linked(notify_with_condarc):
    """Happy path: pip linked with unrelated channel shows tip."""
    mock_logger = notify_with_condarc("channels:\n  - conda-forge\n")
    mock_logger.warning.assert_called_once()


def test_notify_skips_build_env(notify_with_condarc, monkeypatch):
    """pip linked but CONDA_BUILD_STATE set to BUILD, no tip shown."""
    monkeypatch.setenv("CONDA_BUILD_STATE", "BUILD")
    mock_logger = notify_with_condarc("channels:\n  - conda-forge\n")
    mock_logger.warning.assert_not_called()


def test_notify_skips_base_prefix(notify_with_condarc):
    """pip linked but env is base, no tip shown."""
    mock_logger = notify_with_condarc("channels:\n  - conda-forge\n", target="base")
    mock_logger.warning.assert_not_called()


def test_notify_skips_when_pip_not_in_transaction(notify_with_condarc):
    """no pip linked, no tip shown."""
    mock_logger = notify_with_condarc("channels:\n  - conda-forge\n", link=("python", "numpy"))
    mock_logger.warning.assert_not_called()


def test_notify_skips_pip_upgrade(notify_with_condarc):
    """pip was upgraded, not newly installed, no tip shown."""
    mock_logger = notify_with_condarc(
        "channels:\n  - conda-forge\n", link=("pip",), unlink=("pip",)
    )
    mock_logger.warning.assert_not_called()


def test_notify_skips_when_pip_warning_disabled(
    notify_with_condarc, mocker: MockerFixture, monkeypatch
):
    """When conda_pypi_pip_warning is False the tip must not be emitted and channels not checked."""
    monkeypatch.setenv("CONDA_PLUGINS_CONDA_PYPI_PIP_WARNING", "false")
    spy_channel_check = mocker.spy(conda_pypi.main, "_has_conda_pypi_channel")
    mock_logger = notify_with_condarc("channels:\n  - conda-forge\n")

    spy_channel_check.assert_not_called()
    mock_logger.warning.assert_not_called()


def test_tip_failure_does_not_block_install(
    conda_cli: CondaCLIFixture,
    mocker: MockerFixture,
    tmp_path: Path,
):
    """A failure while emitting the tip must not roll back the conda transaction."""
    mocker.patch(
        "conda_pypi.main.notify_conda_pypi_tip",
        side_effect=RuntimeError("boom"),
    )
    prefix = tmp_path / "env"
    _, _, rc = conda_cli("create", "--prefix", str(prefix), "--yes", "python", "pip")
    assert rc == 0
    assert list(PrefixData(prefix).query("pip"))


def test_pip_tip_shows_once_on_new_install(
    conda_cli: CondaCLIFixture,
    tmp_path: Path,
):
    """Later pip upgrades must not show the tip again."""
    prefix = tmp_path / "env"
    _, err, rc = conda_cli("create", "--prefix", str(prefix), "--yes", "python", "pip")
    assert rc == 0
    assert "Did you know?" in err

    _, err, rc = conda_cli("install", "--prefix", str(prefix), "--yes", "--force-reinstall", "pip")
    assert rc == 0
    assert "Did you know?" not in err


def test_pip_warning_setting_defaults_to_true():
    """The conda_pypi_pip_warning setting must default to True."""

    settings = list(conda_settings())
    assert len(settings) == 1
    setting = settings[0]
    assert isinstance(setting, CondaSetting)
    assert setting.name == "conda_pypi_pip_warning"
    assert setting.parameter.default.value is True


def test_pip_warning_setting_in_context(monkeypatch, tmp_path: Path):
    """Verify that setting the plugin setting is refelcted in the context object."""
    # Test with a non-default value first
    monkeypatch.setenv("CONDA_PLUGINS_CONDA_PYPI_PIP_WARNING", 0)
    reset_context(())
    assert context.plugins.conda_pypi_pip_warning is False

    monkeypatch.setenv("CONDA_PLUGINS_CONDA_PYPI_PIP_WARNING", 1)
    reset_context(())
    assert context.plugins.conda_pypi_pip_warning is True


def test_conda_context_exposes_custom_channels_mapping(isolated_conda_context, tmp_path: Path):
    """Ensure supported Conda context exposes _custom_channels mapping for short-name resolution."""
    condarc = tmp_path / "condarc.yaml"
    condarc.write_text(
        "custom_channels:\n  conda-pypi: https://custom-channel.repo.org\n",
        encoding="utf-8",
    )
    reset_context([str(condarc)])
    custom_channels = getattr(context, "_custom_channels", {})
    assert custom_channels.get("conda-pypi") == "https://custom-channel.repo.org"


@pytest.mark.parametrize(
    "condarc_yaml,should_suppress",
    [
        pytest.param("channels:\n  - conda-pypi\n", True, id="short-name"),
        pytest.param(
            "channels:\n  - https://conda.anaconda.org/conda-pypi\n",
            True,
            id="public-url",
        ),
        pytest.param(
            "channels:\n  - https://conda.anaconda.org/conda-pypi/\n",
            True,
            id="public-url-trailing-slash",
        ),
        pytest.param(
            "channels:\n  - https://conda.anaconda.org/conda-pypi/linux-64\n",
            True,
            id="public-url-subdir-linux64",
        ),
        pytest.param(
            "channels:\n  - https://conda.anaconda.org/conda-pypi/noarch\n",
            True,
            id="public-url-subdir-noarch",
        ),
        pytest.param(
            "channels:\n  - conda-pypi/linux-64\n",
            True,
            id="short-name-subdir-linux64",
        ),
        pytest.param(
            "channels:\n  - conda-pypi/noarch\n",
            True,
            id="short-name-subdir-noarch",
        ),
        pytest.param("channels: []\n", False, id="empty-channels"),
        pytest.param("channels:\n  - conda-forge\n", False, id="unrelated-channel"),
        pytest.param(
            "channels:\n  - conda-pypi-extra\n",
            False,
            id="extended-name-prefix",
        ),
        pytest.param(
            "channels:\n  - https://example.invalid/conda-pypi\n",
            False,
            id="unrelated-host-same-name",
        ),
        pytest.param(
            "channels:\n  - https://example.invalid/conda-pypi/linux-64\n",
            False,
            id="unrelated-host-same-name-linux64",
        ),
        pytest.param(
            "channel_alias: https://custom.internal.org\nchannels:\n  - conda-pypi\n",
            True,
            id="alias-short-name",
        ),
        pytest.param(
            "channel_alias: https://custom.internal.org\nchannels:\n  - https://custom.internal.org/conda-pypi\n",
            True,
            id="alias-explicit-url",
        ),
        pytest.param(
            "channel_alias: https://custom.internal.org\nchannels:\n  - https://conda.anaconda.org/conda-pypi\n",
            True,
            id="alias-public-url",
        ),
        pytest.param(
            "channel_alias: https://custom.internal.org\nchannels:\n  - https://example.invalid/conda-pypi\n",
            False,
            id="alias-unrelated-host",
        ),
        pytest.param(
            "custom_channels:\n  conda-pypi: https://custom-channel.repo.org\nchannels:\n  - conda-pypi\n",
            True,
            id="custom-mapping-short-name",
        ),
        pytest.param(
            "custom_channels:\n  conda-pypi: https://custom-channel.repo.org\nchannels:\n  - https://custom-channel.repo.org/conda-pypi\n",
            True,
            id="custom-mapping-explicit-url",
        ),
        pytest.param(
            "custom_channels:\n  conda-pypi: https://custom-channel.repo.org\nchannels:\n  - https://conda.anaconda.org/conda-pypi\n",
            True,
            id="custom-mapping-public-url",
        ),
        pytest.param(
            "custom_channels:\n  conda-pypi: https://custom-channel.repo.org\nchannels:\n  - https://example.invalid/conda-pypi\n",
            False,
            id="custom-mapping-unrelated-host",
        ),
        pytest.param(
            "custom_multichannels:\n  my_mc:\n    - https://conda.anaconda.org/conda-pypi\n    - conda-forge\nchannels:\n  - my_mc\n",
            True,
            id="multichannel-recognized-member",
        ),
        pytest.param(
            "custom_multichannels:\n  unrelated_mc:\n    - https://example.invalid/conda-pypi\nchannels:\n  - unrelated_mc\n",
            False,
            id="multichannel-unrelated-host-member",
        ),
        pytest.param(
            "custom_channels:\n  conda-pypi: https://custom-channel.repo.org\ncustom_multichannels:\n  wrong_host_mc:\n    - https://example.invalid/conda-pypi\nchannels:\n  - wrong_host_mc\n",
            False,
            id="custom-mapping-with-wrong-host-mc-select-mc",
        ),
        pytest.param(
            "custom_channels:\n  conda-pypi: https://custom-channel.repo.org\ncustom_multichannels:\n  wrong_host_mc:\n    - https://example.invalid/conda-pypi\nchannels:\n  - conda-pypi\n",
            True,
            id="custom-mapping-with-wrong-host-mc-select-short-name",
        ),
    ],
)
def test_notify_channel_scenarios(notify_with_condarc, condarc_yaml: str, should_suppress: bool):
    """Test notification suppression behavior across channel configuration scenarios."""
    mock_logger = notify_with_condarc(condarc_yaml)
    if should_suppress:
        mock_logger.warning.assert_not_called()
    else:
        mock_logger.warning.assert_called_once()


def test_real_parser_local_yaml_reproduction_and_resolution(notify_with_condarc, tmp_path: Path):
    """Real argument and YAML parsers suppress the tip when conda-pypi is declared in YAML or CLI."""
    condarc = "channels:\n  - conda-forge\n"

    # 1. Normal YAML positive case: environment.yml declares conda-pypi, condarc does not
    env_pypi = tmp_path / "env_pypi.yml"
    env_pypi.write_text(
        "name: demo-pypi\nchannels:\n  - conda-forge\n  - conda-pypi\ndependencies:\n  - python\n  - pip\n",
        encoding="utf-8",
    )
    parser = generate_parser()
    args_pypi = parser.parse_args(["create", "-f", str(env_pypi)])
    if not hasattr(args_pypi, "packages"):
        args_pypi.packages = []

    # Test oracle: verify Environment model derived from real CLI parser includes conda-pypi
    oracle_pypi, _ = Environment.from_cli_with_file_envs(args_pypi, add_default_packages=False)
    assert "conda-pypi" in oracle_pypi.config.channels

    mock_logger_pypi = notify_with_condarc(condarc, argparse_args=args_pypi)
    mock_logger_pypi.warning.assert_not_called()

    # 2. Normal YAML control case: environment.yml without conda-pypi emits the tip
    env_control = tmp_path / "env_control.yml"
    env_control.write_text(
        "name: demo-control\nchannels:\n  - conda-forge\ndependencies:\n  - python\n  - pip\n",
        encoding="utf-8",
    )
    args_control = parser.parse_args(["create", "-f", str(env_control)])
    if not hasattr(args_control, "packages"):
        args_control.packages = []

    oracle_control, _ = Environment.from_cli_with_file_envs(
        args_control, add_default_packages=False
    )
    assert "conda-pypi" not in oracle_control.config.channels

    mock_logger_control = notify_with_condarc(condarc, argparse_args=args_control)
    mock_logger_control.warning.assert_called_once()

    # 3. CLI addition: create -f env_control.yml -c conda-pypi adds channel and suppresses tip
    args_cli = parser.parse_args(["create", "-f", str(env_control), "-c", "conda-pypi"])
    if not hasattr(args_cli, "packages"):
        args_cli.packages = []

    oracle_cli, _ = Environment.from_cli_with_file_envs(args_cli, add_default_packages=False)
    assert "conda-pypi" in oracle_cli.config.channels

    mock_logger_cli = notify_with_condarc(condarc, argparse_args=args_cli)
    mock_logger_cli.warning.assert_not_called()

    # 4. CLI override: create -f env_pypi.yml -c conda-forge --override-channels excludes file channel
    args_override = parser.parse_args(
        ["create", "-f", str(env_pypi), "-c", "conda-forge", "--override-channels"]
    )
    if not hasattr(args_override, "packages"):
        args_override.packages = []

    oracle_override, _ = Environment.from_cli_with_file_envs(
        args_override, add_default_packages=False
    )
    assert "conda-pypi" not in oracle_override.config.channels

    mock_logger_override = notify_with_condarc(condarc, argparse_args=args_override)
    mock_logger_override.warning.assert_called_once()

    # 5. Multifile interaction: create -f env_control.yml -f env_pypi.yml retains both
    args_multi = parser.parse_args(["create", "-f", str(env_control), "-f", str(env_pypi)])
    if not hasattr(args_multi, "packages"):
        args_multi.packages = []

    oracle_multi, _ = Environment.from_cli_with_file_envs(args_multi, add_default_packages=False)
    assert "conda-pypi" in oracle_multi.config.channels

    mock_logger_multi = notify_with_condarc(condarc, argparse_args=args_multi)
    mock_logger_multi.warning.assert_not_called()

    # 6. Combined nodefaults with configured-only conda-pypi:
    # Conda releases differ on whether nodefaults excludes configured channels in solve
    # (retained in 26.7.2 create, stripped in legacy 26.3.2 scalar env create and CEP-24 main).
    # Plugin safely treats this ambiguous boundary as UNKNOWN and leaves the tip visible.
    env_nd = tmp_path / "env_nd.yml"
    env_nd.write_text(
        "name: demo-nd\nchannels:\n  - conda-forge\n  - nodefaults\ndependencies:\n  - python\n  - pip\n",
        encoding="utf-8",
    )
    args_nd = parser.parse_args(["create", "-f", str(env_nd)])
    if not hasattr(args_nd, "packages"):
        args_nd.packages = []

    mock_logger_nd = notify_with_condarc("channels:\n  - conda-pypi\n", argparse_args=args_nd)
    mock_logger_nd.warning.assert_called_once()


def test_diagnostic_solver_constructor_channel_alignment(
    isolated_conda_context, mocker: MockerFixture, tmp_path: Path
):
    """Diagnostic check: real create command passes local YAML channels to solver constructor without solving."""
    env_file = tmp_path / "diagnostic.yml"
    env_file.write_text(
        "name: diag\nchannels:\n  - conda-pypi\n  - conda-forge\ndependencies:\n  - python\n",
        encoding="utf-8",
    )
    parser = generate_parser()
    args = parser.parse_args(["create", "-f", str(env_file), "-y", "--dry-run"])

    mock_solver_backend = mocker.MagicMock()
    mock_solver_instance = mocker.MagicMock()
    mock_solver_backend.return_value = mock_solver_instance
    mock_solver_instance.solve_for_transaction.side_effect = RuntimeError(
        "intercepted_without_solving"
    )

    mocker.patch.object(
        context.plugin_manager, "get_cached_solver_backend", return_value=mock_solver_backend
    )

    from conda.cli import install

    with pytest.raises(RuntimeError, match="intercepted_without_solving"):
        install.install(args, parser, "create")

    # Verify Conda's actual solver constructor received the local YAML channels
    called_channels = mock_solver_backend.call_args[0][1]
    assert "conda-pypi" in called_channels
    assert "conda-forge" in called_channels

    # Verify notification suppression matches this solver channel selection
    context.__init__(argparse_args=args)
    assert conda_pypi.main._should_suppress_conda_pypi_tip() is True


def test_early_guards_do_not_read_files(
    notify_with_condarc, mocker: MockerFixture, monkeypatch, tmp_path: Path
):
    """Build, base, pip upgrade, and opt-out guards must return before reading environment files."""
    env_file = tmp_path / "early_guard.yml"
    env_file.write_text("channels:\n  - conda-pypi\n", encoding="utf-8")
    parser = generate_parser()
    args = parser.parse_args(["env", "create", "-f", str(env_file)])

    spy_loader = mocker.spy(conda_pypi.main, "_load_local_yaml_channels")

    # 1. Build environment guard
    monkeypatch.setenv("CONDA_BUILD_STATE", "BUILD")
    mock_logger = notify_with_condarc("channels:\n  - conda-forge\n", argparse_args=args)
    spy_loader.assert_not_called()
    mock_logger.warning.assert_not_called()
    monkeypatch.delenv("CONDA_BUILD_STATE")

    # 2. Base environment guard
    mock_logger = notify_with_condarc(
        "channels:\n  - conda-forge\n", target="base", argparse_args=args
    )
    spy_loader.assert_not_called()
    mock_logger.warning.assert_not_called()

    # 3. Pip upgrade guard (pip in unlink precs)
    mock_logger = notify_with_condarc(
        "channels:\n  - conda-forge\n", link=("pip",), unlink=("pip",), argparse_args=args
    )
    spy_loader.assert_not_called()
    mock_logger.warning.assert_not_called()

    # 4. Opt-out guard
    monkeypatch.setenv("CONDA_PLUGINS_CONDA_PYPI_PIP_WARNING", "false")
    mock_logger = notify_with_condarc("channels:\n  - conda-forge\n", argparse_args=args)
    spy_loader.assert_not_called()
    mock_logger.warning.assert_not_called()


def test_remote_file_does_not_invoke_network(notify_with_condarc, mocker: MockerFixture):
    """Remote URL environment definitions must not trigger network downloads; tip remains visible."""
    mock_download = mocker.patch("conda.gateways.connection.download.download_text")
    args = SimpleNamespace(
        file=["https://example.invalid/environment.yml"],
        channel=None,
        override_channels=False,
    )
    # Even if conda-pypi is in condarc, file-aware unknown must not accidentally suppress
    mock_logger = notify_with_condarc("channels:\n  - conda-pypi\n", argparse_args=args)
    mock_download.assert_not_called()
    mock_logger.warning.assert_called_once()


@pytest.mark.parametrize(
    "condarc_yaml,file_defs,cli_channels,override,custom_args,should_suppress",
    [
        pytest.param(
            "channels:\n  - conda-forge\n",
            {"env.yml": "channels:\n  - conda-forge\n  - conda-pypi\n"},
            None,
            False,
            None,
            True,
            id="yaml-only-conda-pypi-suppresses",
        ),
        pytest.param(
            "channels:\n  - defaults\n",
            {"env.yml": "channels:\n  - conda-forge\n"},
            None,
            False,
            None,
            False,
            id="yaml-without-conda-pypi-emits",
        ),
        pytest.param(
            "channels:\n  - defaults\n",
            {"env.yml": "channels:\n  - conda-pypi\n"},
            ["other-channel"],
            False,
            None,
            True,
            id="cli-addition-preserves-yaml-conda-pypi",
        ),
        pytest.param(
            "channels:\n  - defaults\n",
            {"env.yml": "channels:\n  - conda-forge\n"},
            ["conda-pypi"],
            False,
            None,
            True,
            id="cli-addition-suppresses-with-yaml-control",
        ),
        pytest.param(
            "channels:\n  - defaults\n",
            {"env.yml": "channels:\n  - conda-pypi\n"},
            ["other-channel"],
            True,
            None,
            False,
            id="cli-override-excludes-yaml-conda-pypi",
        ),
        pytest.param(
            "channels:\n  - defaults\n",
            {"env.yml": "channels:\n  - conda-forge\n"},
            ["conda-pypi"],
            True,
            None,
            True,
            id="cli-override-explicit-conda-pypi-suppresses",
        ),
        pytest.param(
            "channels:\n  - defaults\n",
            {"env.yml": "channels:\n  - conda-forge\n  - nodefaults\n"},
            ["conda-pypi"],
            False,
            None,
            True,
            id="cli-explicit-conda-pypi-retained-with-nodefaults",
        ),
        pytest.param(
            "channels:\n  - defaults\n",
            {"env.yml": "channels:\n  - conda-pypi\n  - nodefaults\n"},
            None,
            False,
            None,
            True,
            id="yaml-explicit-conda-pypi-retained-with-nodefaults",
        ),
        pytest.param(
            "channels:\n  - conda-pypi\n",
            {"env.yml": "channels:\n  - conda-forge\n  - nodefaults\n"},
            None,
            False,
            None,
            False,
            id="nodefaults-configured-conda-pypi-unknown-emits",
        ),
        pytest.param(
            "channels:\n  - conda-pypi\n",
            {"env.yml": "channels:\n  - nodefaults\n"},
            None,
            False,
            None,
            False,
            id="singleton-nodefaults-visible",
        ),
        pytest.param(
            "channels:\n  - conda-pypi\n",
            {"env.yml": "name: test\ndependencies:\n  - python\n"},
            None,
            False,
            None,
            True,
            id="omitted-channels-valid-env-falls-back-to-context",
        ),
        pytest.param(
            "channels:\n  - conda-forge\n",
            {"env.yml": "name: test\ndependencies:\n  - python\n"},
            None,
            False,
            None,
            False,
            id="omitted-channels-without-conda-pypi-emits",
        ),
        pytest.param(
            "channels:\n  - conda-pypi\n",
            {"env.yml": "foo: bar\nhello: world\n"},
            None,
            False,
            None,
            False,
            id="non-environment-yaml-unknown-emits",
        ),
        pytest.param(
            "channels:\n  - conda-pypi\n",
            {"env.yml": "channels:\n  - conda-pypi\n"},
            None,
            False,
            {"environment_specifier": "cep-24"},
            False,
            id="custom-environment-specifier-unknown-emits",
        ),
        pytest.param(
            "channels:\n  - conda-pypi\n",
            {
                "env1.yml": "channels:\n  - other-channel\n  - nodefaults\n",
                "env2.yml": "channels:\n  - third-channel\n",
            },
            None,
            False,
            None,
            False,
            id="multiple-files-with-nodefaults-configured-conda-pypi-stays-visible",
        ),
        pytest.param(
            "channels:\n  - defaults\n",
            {
                "env1.yml": "channels:\n  - conda-forge\n",
                "env2.yml": "channels:\n  - ${CUSTOM_CH}\n",
            },
            None,
            False,
            None,
            True,
            id="multiple-files-with-envvar-expansion",
        ),
        pytest.param(
            "channel_alias: https://custom.internal.org\nchannels:\n  - defaults\n",
            {"env.yml": "channels:\n  - https://custom.internal.org/conda-pypi\n"},
            None,
            False,
            None,
            True,
            id="yaml-with-alias-and-custom-channel",
        ),
        pytest.param(
            "channels:\n  - conda-pypi\n",
            "missing-file",
            None,
            False,
            None,
            False,
            id="unreadable-file-falls-back-safely",
        ),
        pytest.param(
            "channels:\n  - conda-pypi\n",
            {"env.yml": "invalid: [unclosed yaml\n"},
            None,
            False,
            None,
            False,
            id="malformed-yaml-syntax-falls-back-safely",
        ),
        pytest.param(
            "channels:\n  - conda-pypi\n",
            {"env.yml": "channels: 'not-a-list'\n"},
            None,
            False,
            None,
            False,
            id="malformed-channels-type-falls-back-safely",
        ),
        pytest.param(
            "channels:\n  - conda-forge\n",
            "scalar-file",
            None,
            False,
            None,
            True,
            id="scalar-file-arg-compatibility",
        ),
        pytest.param(
            "channels:\n  - conda-pypi\n",
            "unsupported-shape",
            None,
            False,
            None,
            False,
            id="unsupported-file-arg-shape-falls-back-safely",
        ),
    ],
)
def test_notify_environment_file_scenarios(
    notify_with_condarc,
    monkeypatch,
    tmp_path: Path,
    condarc_yaml: str,
    file_defs: dict[str, str] | str,
    cli_channels: list[str] | None,
    override: bool,
    custom_args: dict[str, str] | None,
    should_suppress: bool,
):
    """Compact matrix testing interacting CLI, YAML, nodefaults, multi-file, and error fallbacks."""
    monkeypatch.setenv("CUSTOM_CH", "conda-pypi")

    if file_defs == "missing-file":
        file_arg = [str(tmp_path / "nonexistent.yml")]
    elif file_defs == "scalar-file":
        f = tmp_path / "scalar.yml"
        f.write_text("channels:\n  - conda-pypi\n", encoding="utf-8")
        file_arg = str(f)
    elif file_defs == "unsupported-shape":
        file_arg = 12345
    else:
        file_paths = []
        for name, content in file_defs.items():
            f = tmp_path / name
            f.write_text(content, encoding="utf-8")
            file_paths.append(str(f))
        file_arg = file_paths

    args_dict = {
        "file": file_arg,
        "channel": cli_channels,
        "override_channels": override,
    }
    if custom_args:
        args_dict.update(custom_args)
    args = SimpleNamespace(**args_dict)

    mock_logger = notify_with_condarc(condarc_yaml, argparse_args=args)
    if should_suppress:
        mock_logger.warning.assert_not_called()
    else:
        mock_logger.warning.assert_called_once()
