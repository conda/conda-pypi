"""
Environment installer plugin for handling pip: section packages.

Uses pip as a resolver only (--dry-run --report) to determine wheel URLs,
then passes those URLs to conda install where the registered .whl package
extractor handles the actual installation. This avoids calling pip install
directly and sidesteps EXTERNALLY-MANAGED (PEP 668) entirely.
"""

from __future__ import annotations

from logging import getLogger

from conda.base.context import context
from conda.reporters import get_spinner

from conda_pypi.main import dry_run_pip_json, run_conda_cli

log = getLogger(f"conda.{__name__}")


def install(prefix, specs, args, *_, workdir=None, **kwargs):
    """
    Install pip-section packages using pip as resolver + conda as installer.

    Uses pip's --dry-run --report to resolve packages and obtain wheel URLs,
    then installs those wheels via conda (which uses the .whl package extractor
    registered by conda-pypi). No pip install subprocess is ever executed
    against the target environment.
    """
    if not specs:
        return None

    with get_spinner("Resolving PyPI dependencies"):
        report = dry_run_pip_json(list(specs))

    installs = report.get("install", [])
    if not installs:
        return None

    wheel_urls = []
    for item in installs:
        url = item.get("download_info", {}).get("url")
        if url:
            wheel_urls.append(url)

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

    return [item["metadata"]["name"] for item in installs if "metadata" in item]
