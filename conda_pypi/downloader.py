"""
Fetch matching wheels from pypi.
"""

import logging
from collections.abc import Iterable
from pathlib import Path

from conda.core.prefix_data import PrefixData
from conda.gateways.connection.download import download
from conda.models.match_spec import MatchSpec
from unearth import PackageFinder, TargetPython

from conda_pypi.exceptions import CondaPypiError
from conda_pypi.translate import conda_to_requires

log = logging.getLogger(__name__)

DEFAULT_INDEX_URLS = ("https://pypi.org/simple/",)


def get_package_finder(
    prefix: Path,
    index_urls: Iterable[str] = DEFAULT_INDEX_URLS,
) -> PackageFinder:
    """
    Finder with prefix's Python, not our Python.
    """
    prefix_data = PrefixData(prefix)
    python_records = list(prefix_data.query("python"))
    if not python_records:
        raise CondaPypiError(f"Python not found in {prefix}")
    py_ver = python_records[0].version
    py_ver = tuple(map(int, py_ver.split(".")))
    target_python = TargetPython(py_ver=py_ver)
    return PackageFinder(
        target_python=target_python,
        only_binary=":all:",
        index_urls=index_urls,
    )


def find_package(finder: PackageFinder, package: str):
    """
    Convert :package: to `MatchSpec`; return best `Link`.
    """
    spec = MatchSpec(package)  # type: ignore # metaclass confuses type checker
    requirement = conda_to_requires(spec)
    if not requirement:
        raise RuntimeError(f"Could not convert {package} to Python Requirement()!")
    return finder.find_best_match(requirement)


def find_and_fetch(finder: PackageFinder, target: Path, package: str) -> Path:
    """
    Find package on PyPI, download best link to target.
    """
    result = find_package(finder, package)
    link = result.best and result.best.link
    if not link:
        raise CondaPypiError(f"No PyPI link for {package}")

    # Check if the file is a wheel (.whl)
    filename = link.url_without_fragment.rsplit("/", 1)[-1]
    if not filename.endswith(".whl"):
        raise CondaPypiError(
            f"No wheel file available for {package}. "
            f"Only source distributions are available. "
            f"conda-pypi requires wheel files for conversion."
        )

    log.info(f"Fetch {package} as {filename}")
    target_path = target / filename
    download(link.url, target_path)
    return target_path
