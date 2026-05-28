from pathlib import Path

import pytest
from conda.base.context import context, reset_context
from conda.plugins.types import CondaSetting
from conda.testing.fixtures import CondaCLIFixture, TmpEnvFixture
from pytest_mock import MockerFixture

from conda_pypi import plugin
from conda_pypi.main import notify_externally_managed_future
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

        # spy on the wheel extractor function in the plugin module
        spy = mocker.spy(plugin, "extract_whl_as_conda_pkg")

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


@pytest.mark.parametrize("command", ["install", "create", "env_create"])
def test_notify_logs_tip_when_pip_installed(
    mocker: MockerFixture,
    tmp_path: Path,
    command: str,
):
    ctx = mocker.patch("conda_pypi.main.context")
    ctx.conda_prefix = str(tmp_path / "base")
    ctx.target_prefix = str(tmp_path / "env")
    mocker.patch("conda_pypi.main.PrefixData").return_value.query.return_value = [
        mocker.MagicMock()
    ]
    mock_logger = mocker.patch("conda_pypi.main.logger")

    notify_externally_managed_future(command)

    mock_logger.info.assert_called_once()
    mock_logger.warning.assert_not_called()


def test_notify_skips_build_env(
    mocker: MockerFixture,
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CONDA_BUILD_STATE", "BUILD")
    ctx = mocker.patch("conda_pypi.main.context")
    ctx.conda_prefix = str(tmp_path / "base")
    ctx.target_prefix = str(tmp_path / "env")
    mocker.patch("conda_pypi.main.PrefixData").return_value.query.return_value = [
        mocker.MagicMock()
    ]
    mock_logger = mocker.patch("conda_pypi.main.logger")

    notify_externally_managed_future("install")

    mock_logger.info.assert_not_called()


def test_notify_skips_base_prefix(
    mocker: MockerFixture,
    tmp_path: Path,
):
    ctx = mocker.patch("conda_pypi.main.context")
    ctx.conda_prefix = str(tmp_path / "base")
    ctx.target_prefix = str(tmp_path / "base")
    mocker.patch("conda_pypi.main.PrefixData").return_value.query.return_value = [
        mocker.MagicMock()
    ]
    mock_logger = mocker.patch("conda_pypi.main.logger")

    notify_externally_managed_future("install")

    mock_logger.info.assert_not_called()


def test_notify_skips_no_pip(
    mocker: MockerFixture,
    tmp_path: Path,
):
    ctx = mocker.patch("conda_pypi.main.context")
    ctx.conda_prefix = str(tmp_path / "base")
    ctx.target_prefix = str(tmp_path / "env")
    mocker.patch("conda_pypi.main.PrefixData").return_value.query.return_value = []
    mock_logger = mocker.patch("conda_pypi.main.logger")

    notify_externally_managed_future("install")

    mock_logger.info.assert_not_called()


def test_notify_skips_when_pip_warning_disabled(
    mocker: MockerFixture,
    tmp_path: Path,
):
    """When conda_pypi_pip_warning is False the tip must not be emitted."""
    ctx = mocker.patch("conda_pypi.main.context")
    ctx.conda_prefix = str(tmp_path / "base")
    ctx.target_prefix = str(tmp_path / "env")
    ctx.plugins.conda_pypi_pip_warning = False
    mocker.patch("conda_pypi.main.PrefixData").return_value.query.return_value = [
        mocker.MagicMock()
    ]
    mock_logger = mocker.patch("conda_pypi.main.logger")

    notify_externally_managed_future("install")

    mock_logger.info.assert_not_called()


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
