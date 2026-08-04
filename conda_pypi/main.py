from __future__ import annotations

import os
from collections.abc import Iterable
from logging import getLogger
from pathlib import Path

from conda.base.context import context
from conda.cli.main import main_subshell
from conda.core.prefix_data import PrefixData
from conda.exceptions import CondaError
from conda.models.match_spec import MatchSpec
from packaging.version import Version

from conda_pypi.python_paths import (
    ensure_externally_managed,
    get_externally_managed_paths,
)

logger = getLogger(f"conda.{__name__}")


def run_conda_cli(*cli_args, **env_kwargs) -> int:
    logger.info("conda command: '%s'", " ".join(cli_args))
    try:
        main_subshell(*cli_args)
    except SystemExit as exc:
        logger.info("conda command system exit:", exc_info=True)
        return exc.code
    else:
        return 0


def run_conda_install(
    prefix: Path,
    specs: Iterable[MatchSpec],
    dry_run: bool = False,
    quiet: bool = False,
    verbosity: int = 0,
    force_reinstall: bool = False,
    yes: bool = False,
    json: bool = False,
    channels: Iterable[str] = (),
    override_channels: bool = False,
) -> int:
    command = ["install", "--prefix", str(prefix)]
    if dry_run:
        command.append("--dry-run")
    if quiet:
        command.append("--quiet")
    if verbosity:
        command.append("-" + ("v" * verbosity))
    if force_reinstall:
        command.append("--force-reinstall")
    if yes:
        command.append("--yes")
    if json:
        command.append("--json")
    if channels:
        for channel in channels:
            command.append("--channel")
            command.append(channel)
    if override_channels:
        command.append("--override-channels")

    command.extend(str(spec) for spec in specs)

    return run_conda_cli(*command)


def ensure_target_env_has_externally_managed(command: str):
    """
    post-command hook to ensure that the target env has the EXTERNALLY-MANAGED file
    even when it is created by conda, not 'conda-pypi'.
    """
    if os.environ.get("CONDA_BUILD_STATE") == "BUILD":
        return
    base_prefix = Path(context.conda_prefix)
    target_prefix = Path(context.target_prefix)
    if base_prefix == target_prefix or base_prefix.resolve() == target_prefix.resolve():
        return
    # Check if conda-pypi is available in the base environment
    # This is more lenient than checking if it was explicitly installed
    try:
        base_prefix_data = PrefixData(base_prefix)
        if not list(base_prefix_data.query("conda-pypi")):
            return
    except (OSError, CondaError):
        # If we can't determine conda-pypi availability, be conservative and return
        return
    prefix_data = PrefixData(target_prefix)
    if command in {"create", "install", "update"}:
        # ensure target env has pip installed
        if not list(prefix_data.query("pip")):
            return

        # Get Python version from the installed packages
        python_version = None
        python_records = list(prefix_data.query("python"))
        if python_records:
            version = Version(python_records[0].version)
            python_version = f"{version.major}.{version.minor}"

        # Check if there are some leftover EXTERNALLY-MANAGED files from other Python versions
        if command != "create" and os.name != "nt":
            for path in get_externally_managed_paths(target_prefix):
                if path.exists():
                    path.unlink()

        ensure_externally_managed(target_prefix, python_version=python_version)
    elif command == "remove":
        if list(prefix_data.query("pip")):
            # leave in place if pip is still installed
            return
        for path in get_externally_managed_paths(target_prefix):
            if path.exists():
                path.unlink()
    else:
        raise ValueError(f"command {command} not recognized.")


def notify_externally_managed_future(command: str):
    """
    Beta-period post-command hook that points pip users to the conda-pypi beta.
    """
    # Build environments are ephemeral; never show user-facing notices.
    if os.environ.get("CONDA_BUILD_STATE") == "BUILD":
        return
    # Only notify in non-base environments where pip interop is relevant.
    base_prefix = Path(context.conda_prefix)
    target_prefix = Path(context.target_prefix)
    if base_prefix == target_prefix or base_prefix.resolve() == target_prefix.resolve():
        return
    # No point showing the beta tip if pip isn't installed.
    prefix_data = PrefixData(target_prefix)
    if not list(prefix_data.query("pip")):
        return

    if context.plugins.conda_pypi_pip_warning:
        logger.warning(
            "\n"
            "  Did you know? You can install many PyPI packages with conda\n"
            "  using the conda-pypi beta. Get started:\n"
            "    https://docs.conda.io/projects/conda/en/stable/new-features.html\n"
        )
