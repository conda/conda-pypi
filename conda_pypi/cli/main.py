"""
Entry point for all conda pypi subcommands

See `conda_pypi.plugin` to see how these are registered with conda
"""

from __future__ import annotations

import argparse
from logging import getLogger

from conda.cli.conda_argparse import (
    add_output_and_prompt_options,
    add_parser_prefix,
)
from conda.exceptions import ArgumentError

from . import convert, index, install

logger = getLogger(__name__)


def generate_parser():
    """
    Generate the main argument parser for conda pypi.

    This function is used by Sphinx's sphinxarg extension to automatically
    generate CLI documentation from the argparse configuration.
    """
    parser = argparse.ArgumentParser(
        prog="conda pypi",
        description="Better PyPI interoperability for the conda ecosystem.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    configure_parser(parser)
    return parser


def configure_parser(parser: argparse.ArgumentParser):
    """
    Entry point for all argparse configuration
    """

    # This adds --prefix/--name mutually exclusive options
    add_parser_prefix(parser)
    add_output_and_prompt_options(parser)

    sub_parsers = parser.add_subparsers(
        metavar="COMMAND",
        title="commands",
        description="The following subcommands are available.",
        dest="cmd",
        required=True,
    )

    install.configure_parser(sub_parsers)
    convert.configure_parser(sub_parsers)
    index.configure_parser(sub_parsers)


def execute(args: argparse.Namespace) -> int:
    if args.cmd == "install":
        return install.execute(args)
    elif args.cmd == "convert":
        return convert.execute(args)
    elif args.cmd == "index":
        return index.execute(args)
    else:
        raise ArgumentError(f"Unknown subcommand: {args.cmd}")
