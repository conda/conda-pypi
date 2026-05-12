"""
Environment installer plugin for handling pip: section packages.

Resolves PyPI dependencies using resolvelib + unearth, then installs the
resolved wheels via ``conda install`` (using the registered .whl package
extractor).  No pip subprocess is involved at any point.
"""

from __future__ import annotations

from logging import getLogger

from conda.base.context import context
from conda.reporters import get_spinner

from conda_pypi.main import run_conda_cli
from conda_pypi.resolver import make_finder, resolve

log = getLogger(f"conda.{__name__}")


def install(prefix, specs, args, *_, workdir=None, **kwargs):
    """
    Install pip-section packages via resolvelib + conda wheel extractor.
    """
    if not specs:
        return None

    finder = make_finder(prefix)

    with get_spinner("Resolving PyPI dependencies"):
        installs = resolve(list(specs), finder)

    if not installs:
        return None

    wheel_urls = [item["url"] for item in installs if item["url"]]
    if not wheel_urls:
        return None

    if not context.quiet and not context.json:
        log.info("Installing %d PyPI packages via conda wheel extractor", len(wheel_urls))

    rc = run_conda_cli(
        "install",
        "--prefix",
        str(prefix),
        "--yes",
        "--quiet",
        *wheel_urls,
    )

    if rc != 0:
        return None

    return [item["name"] for item in installs if item["name"]]
