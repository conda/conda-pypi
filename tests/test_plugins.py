from pathlib import Path
from types import SimpleNamespace

import pytest
from conda.base.context import context, reset_context
from conda.core.prefix_data import PrefixData
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
    ):
        condarc_file = tmp_path / "condarc.yaml"
        condarc_file.write_text(condarc_yaml, encoding="utf-8")
        reset_context([str(condarc_file)])
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
