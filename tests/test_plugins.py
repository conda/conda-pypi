import contextlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from conda.base.context import context, reset_context
from conda.core.prefix_data import PrefixData
from conda.models.channel import Channel
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


def _notify(
    mocker: MockerFixture,
    tmp_path: Path,
    *,
    link: tuple[str, ...] = ("pip",),
    unlink: tuple[str, ...] = (),
    target: str = "env",
    channels: tuple[str | Channel, ...] = (),
):
    ctx = mocker.patch("conda_pypi.main.context")
    ctx.conda_prefix = str(tmp_path / "base")
    ctx.target_prefix = str(tmp_path / target)
    ctx.channels = channels
    ctx.channel_alias = Channel("https://conda.anaconda.org")
    ctx._custom_channels = {}
    ctx.plugins.conda_pypi_pip_warning = True
    mock_logger = mocker.patch("conda_pypi.main.logger")
    notify_conda_pypi_tip(
        target_prefix=str(tmp_path / target),
        link_precs=[_prec(name) for name in link],
        unlink_precs=[_prec(name) for name in unlink],
    )
    return mock_logger


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


def test_notify_logs_tip_when_pip_newly_linked(mocker: MockerFixture, tmp_path: Path):
    """Happy path: pip linked"""
    mock_logger = _notify(mocker, tmp_path)
    mock_logger.warning.assert_called_once()


def test_notify_skips_build_env(mocker: MockerFixture, monkeypatch, tmp_path: Path):
    """pip linked but CONDA_BUILD_STATE set to BUILD, no tip shown"""
    monkeypatch.setenv("CONDA_BUILD_STATE", "BUILD")
    mock_logger = _notify(mocker, tmp_path)
    mock_logger.warning.assert_not_called()


def test_notify_skips_base_prefix(mocker: MockerFixture, tmp_path: Path):
    """pip linked but env is base, no tip shown"""
    mock_logger = _notify(mocker, tmp_path, target="base")
    mock_logger.warning.assert_not_called()


def test_notify_skips_when_pip_not_in_transaction(mocker: MockerFixture, tmp_path: Path):
    """no pip linked, no tip shown"""
    mock_logger = _notify(
        mocker, tmp_path, link=("python", "numpy")
    )  # this transaction did not link pip

    mock_logger.warning.assert_not_called()


def test_notify_skips_pip_upgrade(mocker: MockerFixture, tmp_path: Path):
    """pip was upgraded, not newly installed, no tip shown"""
    mock_logger = _notify(mocker, tmp_path, link=("pip",), unlink=("pip",))
    mock_logger.warning.assert_not_called()


def test_notify_skips_when_pip_warning_disabled(mocker: MockerFixture, tmp_path: Path):
    """When conda_pypi_pip_warning is False the tip must not be emitted and channels not checked."""
    ctx = mocker.patch("conda_pypi.main.context")
    ctx.conda_prefix = str(tmp_path / "base")
    ctx.target_prefix = str(tmp_path / "env")
    ctx.channels = ()
    ctx.channel_alias = Channel("https://conda.anaconda.org")
    ctx._custom_channels = {}
    ctx.plugins.conda_pypi_pip_warning = False
    mock_logger = mocker.patch("conda_pypi.main.logger")
    spy_channel_check = mocker.spy(conda_pypi.main, "_has_conda_pypi_channel")

    notify_conda_pypi_tip(
        target_prefix=str(tmp_path / "env"),
        link_precs=[_prec("pip")],
        unlink_precs=[],
    )

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


@contextlib.contextmanager
def _conda_context_isolation(monkeypatch, tmp_path: Path):
    try:
        with monkeypatch.context() as m:
            m.delenv("CONDA_CHANNELS", raising=False)
            m.delenv("CONDA_CHANNEL_ALIAS", raising=False)
            m.delenv("CONDA_CUSTOM_CHANNELS", raising=False)
            m.delenv("CONDA_CUSTOM_MULTICHANNELS", raising=False)
            m.delenv("CONDA_DEFAULT_CHANNELS", raising=False)
            m.delenv("CONDA_BUILD_STATE", raising=False)
            m.setenv("CONDA_PLUGINS_CONDA_PYPI_PIP_WARNING", "true")
            yield tmp_path
    finally:
        reset_context()


@pytest.fixture
def isolated_conda_context(monkeypatch, tmp_path: Path):
    """Fixture that isolates conda config and restores context/channel caches after each case."""
    with _conda_context_isolation(monkeypatch, tmp_path) as path:
        yield path


def test_isolated_conda_context_restores_inherited_channels(monkeypatch, tmp_path: Path):
    """Prove inherited CONDA_CHANNELS is visible in Conda context after isolation scope exits."""
    try:
        with monkeypatch.context() as outer:
            outer.setenv("CONDA_CHANNELS", "conda-forge")
            reset_context()
            assert context.channels == ("conda-forge",)

            with _conda_context_isolation(outer, tmp_path) as isolated_path:
                assert isolated_path == tmp_path
                assert "CONDA_CHANNELS" not in os.environ

                # Simulate a test case that loaded a custom condarc
                condarc = isolated_path / "condarc.yaml"
                condarc.write_text("channels:\n  - conda-pypi\n", encoding="utf-8")
                reset_context(search_path=(str(condarc),))
                assert context.channels == ("conda-pypi",)

            # After isolation teardown, inherited CONDA_CHANNELS must be restored and visible in context
            assert os.environ.get("CONDA_CHANNELS") == "conda-forge"
            assert context.channels == ("conda-forge",)
    finally:
        reset_context()


def test_isolated_conda_context_restores_on_test_failure(monkeypatch, tmp_path: Path):
    """Prove inherited CONDA_CHANNELS is restored even if an exception occurs during the test."""
    try:
        with monkeypatch.context() as outer:
            outer.setenv("CONDA_CHANNELS", "conda-forge")
            reset_context()
            assert context.channels == ("conda-forge",)

            with (
                pytest.raises(RuntimeError, match="simulated failure"),
                _conda_context_isolation(outer, tmp_path),
            ):
                assert "CONDA_CHANNELS" not in os.environ
                raise RuntimeError("simulated failure")

            assert os.environ.get("CONDA_CHANNELS") == "conda-forge"
            assert context.channels == ("conda-forge",)
    finally:
        reset_context()


def test_isolated_conda_context_clears_build_and_opt_out(monkeypatch, tmp_path: Path):
    """Prove inherited CONDA_BUILD_STATE and warning opt-out are isolated so tests cannot silently skip."""
    try:
        with monkeypatch.context() as outer:
            outer.setenv("CONDA_BUILD_STATE", "BUILD")
            outer.setenv("CONDA_PLUGINS_CONDA_PYPI_PIP_WARNING", "false")

            with _conda_context_isolation(outer, tmp_path):
                assert "CONDA_BUILD_STATE" not in os.environ
                assert os.environ.get("CONDA_PLUGINS_CONDA_PYPI_PIP_WARNING") == "true"

            assert os.environ.get("CONDA_BUILD_STATE") == "BUILD"
            assert os.environ.get("CONDA_PLUGINS_CONDA_PYPI_PIP_WARNING") == "false"
    finally:
        reset_context()


def _run_notify_with_real_context(tmp_path: Path, mocker: MockerFixture, condarc_yaml: str):
    condarc_file = tmp_path / "condarc.yaml"
    condarc_file.write_text(condarc_yaml, encoding="utf-8")
    reset_context(search_path=(str(condarc_file),))
    mock_logger = mocker.patch("conda_pypi.main.logger")
    notify_conda_pypi_tip(
        target_prefix=str(tmp_path / "env"),
        link_precs=[_prec("pip")],
        unlink_precs=[],
    )
    return mock_logger


def test_notify_skips_when_channel_is_short_name(mocker: MockerFixture, tmp_path: Path):
    """Tip is suppressed when channels include conda-pypi by short name."""
    mock_logger = _notify(mocker, tmp_path, channels=("conda-pypi",))
    mock_logger.warning.assert_not_called()


@pytest.mark.parametrize(
    "channel",
    [
        "https://conda.anaconda.org/conda-pypi",
        "https://conda.anaconda.org/conda-pypi/",
        "https://conda.anaconda.org/conda-pypi/linux-64",
        "conda-pypi/linux-64",
        "conda-pypi/noarch",
        "https://conda.anaconda.org/conda-pypi/noarch",
    ],
)
def test_notify_skips_when_channel_is_public_url_variants(
    mocker: MockerFixture, tmp_path: Path, channel: str
):
    """Tip is suppressed for public URL, trailing-slash, and platform-qualified forms."""
    mock_logger = _notify(mocker, tmp_path, channels=(channel,))
    mock_logger.warning.assert_not_called()


@pytest.mark.parametrize(
    "channels",
    [
        (),
        ("conda-forge",),
        ("conda-pypi-extra",),
        ("https://example.invalid/conda-pypi",),
        ("https://example.invalid/conda-pypi/linux-64",),
    ],
)
def test_notify_warns_for_unrelated_or_absent_channels(
    mocker: MockerFixture, tmp_path: Path, channels: tuple[str, ...]
):
    """Tip warns once for absent, unrelated channels, conda-pypi-extra, or unrelated hosts."""
    mock_logger = _notify(mocker, tmp_path, channels=channels)
    mock_logger.warning.assert_called_once()


@pytest.mark.parametrize(
    "channel,should_suppress",
    [
        ("conda-pypi", True),
        ("https://conda.anaconda.org/conda-pypi", True),
        ("https://custom.internal.org/conda-pypi", True),
        ("https://example.invalid/conda-pypi", False),
    ],
)
def test_notify_custom_channel_alias(
    isolated_conda_context, mocker: MockerFixture, channel: str, should_suppress: bool
):
    """With custom channel_alias: short-name and public URL suppress, unrelated host warns."""
    condarc = f"""
channel_alias: https://custom.internal.org
channels:
  - {channel}
"""
    mock_logger = _run_notify_with_real_context(isolated_conda_context, mocker, condarc)
    if should_suppress:
        mock_logger.warning.assert_not_called()
    else:
        mock_logger.warning.assert_called_once()


def test_notify_multichannel_with_recognized_member(isolated_conda_context, mocker: MockerFixture):
    """A multichannel containing a recognized conda-pypi member suppresses the tip."""
    condarc = """
custom_multichannels:
  my_multichannel:
    - https://conda.anaconda.org/conda-pypi
    - conda-forge
channels:
  - my_multichannel
"""
    mock_logger = _run_notify_with_real_context(isolated_conda_context, mocker, condarc)
    mock_logger.warning.assert_not_called()


def test_notify_multichannel_with_unrelated_host_member(
    isolated_conda_context, mocker: MockerFixture
):
    """An unrelated multichannel with only a same-named channel on a different host warns."""
    condarc = """
custom_multichannels:
  unrelated_multichannel:
    - https://example.invalid/conda-pypi
channels:
  - unrelated_multichannel
"""
    mock_logger = _run_notify_with_real_context(isolated_conda_context, mocker, condarc)
    mock_logger.warning.assert_called_once()


def test_notify_real_config_short_name_suppresses(isolated_conda_context, mocker: MockerFixture):
    """Real condarc loading with short-name conda-pypi suppresses tip."""
    condarc = """
channels:
  - conda-pypi
"""
    mock_logger = _run_notify_with_real_context(isolated_conda_context, mocker, condarc)
    mock_logger.warning.assert_not_called()


def test_notify_real_config_public_url_suppresses(isolated_conda_context, mocker: MockerFixture):
    """Real condarc loading with public URL conda-pypi suppresses tip."""
    condarc = """
channels:
  - https://conda.anaconda.org/conda-pypi
"""
    mock_logger = _run_notify_with_real_context(isolated_conda_context, mocker, condarc)
    mock_logger.warning.assert_not_called()


def test_notify_real_config_unrelated_channel_warns(isolated_conda_context, mocker: MockerFixture):
    """Real condarc loading with unrelated channel warns once."""
    condarc = """
channels:
  - conda-forge
"""
    mock_logger = _run_notify_with_real_context(isolated_conda_context, mocker, condarc)
    mock_logger.warning.assert_called_once()


@pytest.mark.parametrize(
    "channel,should_suppress",
    [
        ("conda-pypi", True),
        ("https://custom-channel.repo.org/conda-pypi", True),
        ("https://conda.anaconda.org/conda-pypi", True),
        ("https://example.invalid/conda-pypi", False),
    ],
)
def test_notify_custom_channels_mapping(
    isolated_conda_context, mocker: MockerFixture, channel: str, should_suppress: bool
):
    """With custom_channels mapping: mapped short-name and public URL suppress, unrelated warns."""
    condarc = f"""
custom_channels:
  conda-pypi: https://custom-channel.repo.org
channels:
  - {channel}
"""
    mock_logger = _run_notify_with_real_context(isolated_conda_context, mocker, condarc)
    if should_suppress:
        mock_logger.warning.assert_not_called()
    else:
        mock_logger.warning.assert_called_once()


def test_notify_custom_channels_mapping_with_wrong_host_multichannel(
    isolated_conda_context, mocker: MockerFixture
):
    """Explicit custom_channels mapping combined with a wrong-host multichannel entry.

    The short-name conda-pypi and custom channel URL suppress the tip.
    The unrelated multichannel with the same-named channel on a different host warns.
    """
    condarc = """
custom_channels:
  conda-pypi: https://custom-channel.repo.org
custom_multichannels:
  wrong_host_mc:
    - https://example.invalid/conda-pypi
channels:
  - wrong_host_mc
"""
    mock_logger = _run_notify_with_real_context(isolated_conda_context, mocker, condarc)
    mock_logger.warning.assert_called_once()

    condarc_suppressed = """
custom_channels:
  conda-pypi: https://custom-channel.repo.org
custom_multichannels:
  wrong_host_mc:
    - https://example.invalid/conda-pypi
channels:
  - conda-pypi
"""
    mock_logger2 = _run_notify_with_real_context(
        isolated_conda_context, mocker, condarc_suppressed
    )
    mock_logger2.warning.assert_not_called()
