from pathlib import Path
from types import SimpleNamespace

import pytest
from conda.base.context import context, reset_context
from conda.core.prefix_data import PrefixData
from conda.plugins.types import CondaSetting
from conda.testing.fixtures import CondaCLIFixture, TmpEnvFixture
from pytest_mock import MockerFixture

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
):
    ctx = mocker.patch("conda_pypi.main.context")
    ctx.conda_prefix = str(tmp_path / "base")
    ctx.target_prefix = str(tmp_path / target)
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
    """When conda_pypi_pip_warning is False the tip must not be emitted."""
    ctx = mocker.patch("conda_pypi.main.context")
    ctx.conda_prefix = str(tmp_path / "base")
    ctx.target_prefix = str(tmp_path / "env")
    ctx.plugins.conda_pypi_pip_warning = False
    mock_logger = mocker.patch("conda_pypi.main.logger")

    notify_conda_pypi_tip(
        target_prefix=str(tmp_path / "env"),
        link_precs=[_prec("pip")],
        unlink_precs=[],
    )

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
