from __future__ import annotations

from conda.plugins import hookimpl
from conda.plugins.types import (
    CondaPackageExtractor,
    CondaPostCommand,
    CondaSubcommand,
)

from conda_pypi import cli, post_command
from conda_pypi.main import ensure_target_env_has_externally_managed
from conda_pypi.package_extractors.whl import extract_whl_as_conda_pkg

try:
    from conda.plugins.types import CondaExternalInstaller
except ImportError:
    CondaExternalInstaller = None


@hookimpl
def conda_subcommands():
    yield CondaSubcommand(
        name="pypi",
        action=cli.main.execute,
        configure_parser=cli.main.configure_parser,
        summary="Install PyPI packages as conda packages",
    )


@hookimpl
def conda_post_commands():
    yield CondaPostCommand(
        name="conda-pypi-ensure-target-env-has-externally-managed",
        action=ensure_target_env_has_externally_managed,
        run_for={"install", "create", "update", "remove"},
    )
    yield CondaPostCommand(
        name="conda-pypi-post-install-create",
        action=post_command.install.post_command,
        run_for={"install", "create"},
    )


@hookimpl
def conda_package_extractors():
    yield CondaPackageExtractor(
        name="wheel-package",
        extensions=[".whl"],
        extract=extract_whl_as_conda_pkg,
    )


if CondaExternalInstaller is not None:

    @hookimpl
    def conda_external_installers():
        from conda_pypi.env_installer import install

        yield CondaExternalInstaller(
            name="pypi",
            install=install,
            aliases=("pip",),
        )
