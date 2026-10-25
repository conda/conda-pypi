"""
Fetch matching wheels from pypi.
"""

import logging
from collections.abc import Iterable
from pathlib import Path

from conda.core.prefix_data import PrefixData
from conda.gateways.connection.download import download
from conda.models.match_spec import MatchSpec
from unearth import PackageFinder, TargetPython  # noqa: TID253

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


def fetch_pep658_wheel_metadata(wheel_url: str) -> str | None:
    """Fetch a wheel's METADATA file via PEP 658/714 without downloading the
    full archive.

    PEP 658 standardises a ``{wheel_url}.metadata`` endpoint on index servers.
    Returns the raw METADATA text on success. PyPI has served this for newly
    uploaded wheels since May 2023. Older wheels may not have this metadata
    available and the endpoint will be absent, in which case it returns None
    and the caller can fall back to downloading the wheel and extracting the
    METADATA file locally.
    """
    from conda.gateways.connection import Session

    metadata_url = wheel_url + ".metadata"
    try:
        with Session() as session:
            response = session.get(metadata_url, timeout=10)
        if response.ok:
            return response.text
        log.debug(
            "PEP 658 metadata endpoint returned %s for %s", response.status_code, metadata_url
        )
    except Exception:
        log.debug("Could not fetch PEP 658 metadata from %s", metadata_url, exc_info=True)
    return None


def _find_wheel_link(finder: PackageFinder, package: str):
    """
    Resolve package to its best wheel link, raising ``CondaPypiError`` if unavailable.
    """
    result = find_package(finder, package)
    link = result.best and result.best.link
    if not link:
        raise CondaPypiError(f"No PyPI link for {package}")
    filename = link.url_without_fragment.rsplit("/", 1)[-1]
    if not filename.endswith(".whl"):
        raise CondaPypiError(
            f"No wheel file available for {package}. "
            f"Only source distributions are available. "
            f"conda-pypi requires wheel files for conversion."
        )
    return link


def _download_wheel(link, target: Path) -> Path:
    """
    Download a wheel link into target directory and return the local path.
    """
    # Check if the file is a wheel (.whl)
    filename = link.url_without_fragment.rsplit("/", 1)[-1]
    target_path = target / filename
    log.info("Fetch %s", filename)
    download(link.url, target_path)
    return target_path


def find_and_fetch(finder: PackageFinder, target: Path, package: str) -> Path:
    """Find package on PyPI, download best link to target."""
    link = _find_wheel_link(finder, package)
    return _download_wheel(link, target)
