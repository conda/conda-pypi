from __future__ import annotations

from conda.plugins import hookimpl
from conda.plugins.types import (
    CondaHealthCheck,
    CondaPackageExtractor,
    CondaPostTransactionAction,
    CondaSetting,
    CondaSubcommand,
)


@hookimpl
def conda_subcommands():
    from conda_pypi import cli

    yield CondaSubcommand(
        name="pypi",
        action=cli.main.execute,
        configure_parser=cli.main.configure_parser,
        summary="Install PyPI packages as conda packages",
    )


@hookimpl
def conda_post_transaction_actions():
    from conda_pypi.main import NotifyCondaPypiTipAction

    yield CondaPostTransactionAction(
        name="conda-pypi-notify-pip-beta",
        action=NotifyCondaPypiTipAction,
    )


@hookimpl
def conda_package_extractors():
    from conda_pypi.package_extractors.whl import extract_whl_as_conda_pkg

    yield CondaPackageExtractor(
        name="wheel-package",
        extensions=[".whl"],
        extract=extract_whl_as_conda_pkg,
    )


@hookimpl
def conda_health_checks():
    from conda_pypi.health_checks.external_packages import (
        migrate_to_conda,
        print_external_packages,
    )

    yield CondaHealthCheck(
        name="external-packages",
        action=print_external_packages,
        fixer=migrate_to_conda,
        summary="List packages not installed by conda.",
    )


@hookimpl
def conda_settings():
    from conda.common.configuration import PrimitiveParameter

    yield CondaSetting(
        name="conda_pypi_pip_warning",
        description="Enable or disable the conda-pypi beta tip shown when pip is newly installed",
        parameter=PrimitiveParameter(True),
    )
