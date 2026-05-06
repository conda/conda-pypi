"""
PyPI dependency resolver using resolvelib + unearth.

Replaces the pip subprocess (--dry-run --report) with a pure-library
approach for resolving PyPI dependencies and obtaining wheel URLs.
"""

from __future__ import annotations

import io
import logging
import os
import zipfile
from email.parser import BytesParser
from pathlib import Path

import requests as _requests
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version
from resolvelib import BaseReporter, Resolver
from resolvelib.providers import AbstractProvider
from unearth import PackageFinder
from unearth.evaluator import Package

from conda_pypi.downloader import DEFAULT_INDEX_URLS, get_package_finder

log = logging.getLogger(f"conda.{__name__}")


class Candidate:
    """A concrete package version backed by an unearth Package link."""

    __slots__ = ("name", "version", "link", "_deps")

    def __init__(self, name: str, version: Version, link) -> None:
        self.name = name
        self.version = version
        self.link = link
        self._deps: list[Requirement] | None = None

    @property
    def url(self) -> str:
        return self.link.url_without_fragment

    @property
    def dependencies(self) -> list[Requirement]:
        if self._deps is None:
            self._deps = _fetch_requires_dist(self.link)
        return self._deps

    def __repr__(self) -> str:
        return f"Candidate({self.name}=={self.version})"


def _fetch_requires_dist(link) -> list[Requirement]:
    """Extract Requires-Dist from PEP 658 metadata or wheel METADATA."""
    raw = _fetch_metadata_bytes(link)
    msg = BytesParser().parsebytes(raw)
    return [Requirement(r) for r in (msg.get_all("Requires-Dist") or [])]


def _fetch_metadata_bytes(link) -> bytes:
    if link.dist_info_metadata:
        url = link.url_without_fragment + ".metadata"
        resp = _requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.content

    resp = _requests.get(link.url_without_fragment, timeout=120, stream=True)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        for entry in zf.namelist():
            if entry.endswith(".dist-info/METADATA"):
                return zf.read(entry)
    raise RuntimeError(f"No METADATA found in wheel at {link.url_without_fragment}")


class PyPIProvider(AbstractProvider):
    """resolvelib provider backed by an unearth ``PackageFinder``."""

    def __init__(self, finder: PackageFinder) -> None:
        self._finder = finder
        self._packages_cache: dict[str, list[Package]] = {}
        self._extras: dict[str, set[str]] = {}

    def identify(self, requirement_or_candidate: Requirement | Candidate) -> str:
        if isinstance(requirement_or_candidate, Candidate):
            return requirement_or_candidate.name
        name = canonicalize_name(requirement_or_candidate.name)
        if requirement_or_candidate.extras:
            self._extras.setdefault(name, set()).update(requirement_or_candidate.extras)
        return name

    def get_preference(self, identifier, resolutions, candidates, information, backtrack_causes):
        if identifier in resolutions:
            return (-2, identifier)
        is_direct = any(
            info.parent is None for info in information.get(identifier, ())
        )
        return (-1 if is_direct else 0, identifier)

    def find_matches(self, identifier, requirements, incompatibilities):
        reqs = list(requirements[identifier])
        bad = {c.version for c in incompatibilities.get(identifier, ())}

        if identifier not in self._packages_cache:
            self._packages_cache[identifier] = list(
                self._finder.find_all_packages(str(identifier))
            )

        for pkg in self._packages_cache[identifier]:
            if pkg.version is None:
                continue
            ver = Version(pkg.version)
            if ver in bad:
                continue
            if all(ver in r.specifier for r in reqs):
                yield Candidate(canonicalize_name(pkg.name), ver, pkg.link)

    def is_satisfied_by(self, requirement: Requirement, candidate: Candidate) -> bool:
        return (
            canonicalize_name(requirement.name) == candidate.name
            and candidate.version in requirement.specifier
        )

    def get_dependencies(self, candidate: Candidate) -> list[Requirement]:
        extras = self._extras.get(candidate.name, set())
        deps: list[Requirement] = []
        for dep in candidate.dependencies:
            if dep.marker is None:
                deps.append(dep)
            elif extras and any(
                dep.marker.evaluate({"extra": e}) for e in extras
            ):
                deps.append(dep)
            elif dep.marker.evaluate():
                deps.append(dep)
        return deps


def get_index_urls() -> list[str]:
    """Collect PyPI index URLs from environment (PIP_INDEX_URL, etc.)."""
    urls: list[str] = []
    index_url = os.environ.get("PIP_INDEX_URL")
    if index_url:
        urls.append(index_url)
    else:
        urls.extend(DEFAULT_INDEX_URLS)
    extra = os.environ.get("PIP_EXTRA_INDEX_URL", "")
    urls.extend(u for u in extra.split() if u)
    return urls


def make_finder(prefix: str | Path) -> PackageFinder:
    """Build a ``PackageFinder`` for *prefix*'s Python, respecting env vars."""
    return get_package_finder(prefix, index_urls=get_index_urls())


def resolve(specs: list[str], finder: PackageFinder) -> list[dict[str, str]]:
    """
    Resolve PyPI requirement strings into a list of ``{name, version, url}``
    dicts suitable for passing to ``conda install``.

    Specs that cannot be parsed as PEP 508 requirements (URLs, paths) are
    returned as-is with empty *name* and *version*.
    """
    requirements: list[Requirement] = []
    passthrough_urls: list[str] = []

    for spec in specs:
        try:
            requirements.append(Requirement(spec))
        except InvalidRequirement:
            passthrough_urls.append(spec)

    result: list[dict[str, str]] = [
        {"name": "", "version": "", "url": u} for u in passthrough_urls
    ]

    if requirements:
        provider = PyPIProvider(finder)
        resolved = Resolver(provider, BaseReporter()).resolve(requirements)
        result.extend(
            {
                "name": str(c.name),
                "version": str(c.version),
                "url": c.url,
            }
            for c in resolved.mapping.values()
        )

    return result
