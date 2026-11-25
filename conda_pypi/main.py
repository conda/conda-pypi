from __future__ import annotations

import os
from collections.abc import Iterable
from logging import getLogger
from pathlib import Path

from conda.base.context import context
from conda.cli.main import main_subshell
from conda.common.serialize import yaml
from conda.core.path_actions import Action
from conda.core.prefix_data import PrefixData
from conda.exceptions import CondaError
from conda.models.channel import Channel
from conda.models.match_spec import MatchSpec
from conda.models.records import PackageRecord
from packaging.version import Version
from ruamel.yaml.error import YAMLError

from .python_paths import (
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


def _package_names(precs: Iterable[PackageRecord] | None) -> set[str]:
    if not precs:
        return set()
    return {prec.name for prec in precs}


def pip_newly_linked(
    link_precs: Iterable[PackageRecord] | None, unlink_precs: Iterable[PackageRecord] | None
) -> bool:
    """True when this transaction links pip without unlinking an existing pip."""
    return "pip" in _package_names(link_precs) and "pip" not in _package_names(unlink_precs)


def _has_conda_pypi_channel(channels: Iterable[str | Channel] | None = None) -> bool:
    """True if conda-pypi is enabled in the provided channels (defaults to context.channels)."""
    if channels is None:
        channels = context.channels
    if not channels:
        return False

    public_pypi = Channel("https://conda.anaconda.org/conda-pypi")
    # Read configured custom_channels mapping directly to avoid Conda's
    # custom_channels property deriving short names from unrelated multichannels.
    # Guard against private attribute changes across conda releases.
    custom_url = getattr(context, "_custom_channels", {}).get("conda-pypi")
    short_pypi = Channel.make_simple_channel(context.channel_alias, custom_url, "conda-pypi")

    recognized = {
        (public_pypi.location, public_pypi.name),
        (short_pypi.location, short_pypi.name),
    }

    # Mirrors with different paths (e.g. Artifactory remotes) cannot be reliably
    # identified without network calls, so they may still show the harmless tip.
    for ch in channels:
        channel = ch if isinstance(ch, Channel) else Channel(ch)
        for sub_channel in channel.channels:
            if (sub_channel.location, sub_channel.name) in recognized:
                return True
    return False


def _load_local_yaml_channels(path_str: str) -> list[str] | None:
    """Read channel declarations from a local environment YAML file, expanding environment variables.

    Returns a list of channel strings (empty list when 'channels' is omitted from a valid environment YAML),
    or None if the path is remote, missing, unreadable, invalid YAML, or not a recognized environment specification.
    """
    if "://" in path_str:
        return None
    try:
        p = Path(path_str)
        if not p.is_file():
            return None
        content = p.read_bytes()
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("utf-16")
        data = yaml.loads(text)
    except (OSError, UnicodeDecodeError, YAMLError, ValueError, TypeError, CondaError):
        return None

    if not isinstance(data, dict):
        return None

    if "channels" in data:
        raw_channels = data["channels"]
        if not isinstance(raw_channels, (list, tuple)) or not all(
            isinstance(c, str) for c in raw_channels
        ):
            return None
        return [os.path.expandvars(c) for c in raw_channels]

    # When 'channels' is omitted, only treat as known environment YAML if
    # standard environment specification keys (such as 'dependencies') are present.
    deps = data.get("dependencies")
    if deps is not None and isinstance(deps, (list, tuple, dict)):
        return []

    return None


def _should_suppress_conda_pypi_tip() -> bool:
    """True if conda-pypi channel is enabled in effective CLI/file/context channels."""
    args = getattr(context, "_argparse_args", None)
    if args is None:
        return _has_conda_pypi_channel(context.channels)

    # Custom environment specifier is unsupported; leave tip visible.
    if bool(getattr(args, "environment_specifier", None)):
        return False
    if bool(getattr(context, "environment_specifier", None)):
        return False

    raw_files = getattr(args, "file", None)
    if raw_files is None or (isinstance(raw_files, (list, tuple)) and len(raw_files) == 0):
        return _has_conda_pypi_channel(context.channels)

    if isinstance(raw_files, (str, os.PathLike)):
        filenames = [str(raw_files)]
    elif isinstance(raw_files, (list, tuple)) and all(
        isinstance(f, (str, os.PathLike)) for f in raw_files
    ):
        filenames = [str(f) for f in raw_files]
    else:
        # Unsupported argument shape; leave tip visible.
        return False

    cli_channels = list(getattr(args, "channel", None) or [])
    if getattr(args, "override_channels", False):
        return _has_conda_pypi_channel(cli_channels)

    all_file_channels: list[list[str]] = []
    for f in filenames:
        chans = _load_local_yaml_channels(f)
        if chans is None:
            # File unreadable, malformed, remote, or not valid environment YAML; leave tip visible.
            return False
        all_file_channels.append(chans)

    file_channels = [c for chans in all_file_channels for c in chans if c != "nodefaults"]

    if _has_conda_pypi_channel(cli_channels) or _has_conda_pypi_channel(file_channels):
        return True

    has_nodefaults = any("nodefaults" in chans for chans in all_file_channels)
    if has_nodefaults:
        # When nodefaults is declared in YAML, configured channel retention is command-
        # and version-dependent across Conda releases (e.g. 26.7.2 create retains context
        # channels, while legacy 26.3.2 scalar env create and CEP-24 main exclude them).
        # Without executing full solve or version-sniffing, this boundary is ambiguous;
        # return False (UNKNOWN) to leave the tip visible safely.
        return False

    return _has_conda_pypi_channel(context.channels)


def notify_conda_pypi_tip(
    target_prefix: str | None = None,
    link_precs: Iterable[PackageRecord] | None = None,
    unlink_precs: Iterable[PackageRecord] | None = None,
) -> None:
    """
    Notice that points users to conda-pypi when pip is newly installed.
    """
    # Build environments are ephemeral; never show user-facing notices.
    if os.environ.get("CONDA_BUILD_STATE") == "BUILD":
        return
    # Only notify in non-base environments where pip interop is relevant.
    base_prefix = Path(context.conda_prefix)
    prefix = Path(target_prefix or context.target_prefix)
    if base_prefix == prefix or base_prefix.resolve() == prefix.resolve():
        return
    # Only when this transaction newly links pip (not upgrades or already-present pip).
    if not pip_newly_linked(link_precs, unlink_precs):
        return
    # Opt-out disables the tip; do not inspect channels if warning is disabled.
    if not context.plugins.conda_pypi_pip_warning:
        return
    # Suppress tip when conda-pypi is enabled in effective command channels.
    if _should_suppress_conda_pypi_tip():
        return

    logger.warning(
        "\n"
        "  Did you know? You can install many PyPI packages with conda\n"
        "  using conda-pypi. Get started:\n"
        "    https://bit.ly/4xXYt0B\n"
    )


class NotifyCondaPypiTipAction(Action):
    """Post-transaction action that shows the conda-pypi usage tip."""

    def verify(self):
        self._verified = True

    def execute(self):
        # A notice must never fail or reverse a successful install.
        try:
            notify_conda_pypi_tip(
                target_prefix=self.target_prefix,
                link_precs=self.link_precs,
                unlink_precs=self.unlink_precs,
            )
        except Exception:
            logger.debug("Failed to emit conda-pypi tip", exc_info=True)

    def reverse(self):
        return None

    def cleanup(self):
        return None
