import sys
from argparse import Namespace, _SubParsersAction
from pathlib import Path

from conda.auxlib.ish import dals
from conda.exceptions import ArgumentError

from conda_pypi.migrate_env import (
    DEFAULT_WHEELS_CHANNEL,
    dump_env,
    load_env_file,
    migrate_environment,
)
from conda_pypi.translate import load_name_mapping


def configure_parser(parser: _SubParsersAction) -> None:
    """
    Configure all subcommand arguments and options via argparse
    """
    summary = "Rewrite an environment.yaml by replacing pip dependencies with conda packages from a wheels channel"
    description = summary
    epilog = dals(
        """
        Examples:

        Migrate environment.yaml using the default conda-pypi wheels channel::

            conda pypi migrate-env environment.yaml

        Migrate using a custom wheels channel::

            conda pypi migrate-env -c https://my-org.example.com/wheels environment.yaml

        Write the result to a new file instead of stdout::

            conda pypi migrate-env --file migrated.yaml environment.yaml

        Rewrite the file in-place::

            conda pypi migrate-env --in-place environment.yaml

        """
    )

    migrate = parser.add_parser(
        "migrate-env",
        help=summary,
        description=description,
        epilog=epilog,
    )

    migrate.add_argument(
        "env_file",
        metavar="ENV_FILE",
        nargs="?",
        default="environment.yaml",
        help="Path to the environment.yaml file to migrate (default: environment.yaml).",
    )
    migrate.add_argument(
        "-c",
        "--channel",
        dest="channels",
        action="append",
        metavar="CHANNEL",
        help=(
            f"Wheels channel URL to query for available packages. "
            f"Can be used multiple times. Defaults to '{DEFAULT_WHEELS_CHANNEL}'."
        ),
    )
    output_group = migrate.add_mutually_exclusive_group()
    output_group.add_argument(
        "-f",
        "--file",
        dest="file",
        type=Path,
        default=None,
        metavar="FILE",
        help="Write the rewritten environment file to FILE instead of stdout.",
    )
    output_group.add_argument(
        "--in-place",
        action="store_true",
        default=False,
        help="Rewrite ENV_FILE in-place.",
    )
    migrate.add_argument(
        "--name-mapping",
        type=Path,
        default=None,
        help="Path to a JSON file with a custom PyPI-to-conda name mapping.",
    )


def execute(args: Namespace) -> int:
    """
    Entry point for the `conda pypi migrate-env` subcommand.
    """
    env_path = Path(args.env_file).expanduser()
    if not env_path.exists():
        raise ArgumentError(f"Environment file not found: {env_path}")

    channel_urls: list[str] = args.channels or [DEFAULT_WHEELS_CHANNEL]

    name_mapping = load_name_mapping(args.name_mapping)

    env_data = load_env_file(env_path)
    env_data, warnings = migrate_environment(env_data, channel_urls, name_mapping)

    for warning in warnings:
        print(f"Warning: {warning}", file=sys.stderr)

    output_path: Path | None
    if args.in_place:
        output_path = env_path
    else:
        output_path = args.file  # None → stdout

    dump_env(env_data, output_path)
    return 0
