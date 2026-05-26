"""
Convert Python `*.dist-info/METADATA` to conda `info/index.json`
"""

import dataclasses
import logging
import re
import sys
import time
from importlib.metadata import Distribution, PackageMetadata, PathDistribution
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from conda.exceptions import ArgumentError
from conda.models.match_spec import MatchSpec
from packaging.requirements import Requirement

from conda_pypi import __version__
from conda_pypi.name_mapping import conda_to_pypi_name, pypi_to_conda_name

log = logging.getLogger(__name__)

# Project-URL label (case-insensitive) → about.json field.
# First matching label wins.
URL_LABEL_MAP: Dict[str, tuple] = {
    "home": ("homepage", "home", "home-page"),
    "dev_url": ("source", "repository", "source code", "development", "github"),
    "doc_url": ("documentation", "docs"),
}


def short_description(text: str) -> str:
    """
    Truncate a long Description to its first paragraph.

    Stops at the first blank line or the first Markdown heading
    (`#`, setext underline of `=` or `-`), so README+CHANGELOG dumps
    don't end up in about.json.
    """
    if not text:
        return ""
    # email.parser un-indents the continuation lines but may leave a leading
    # space on each line; strip uniformly.
    lines: List[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.lstrip()
        if not stripped:
            break
        if stripped.startswith("#"):
            break
        if lines and re.fullmatch(r"[=\-]{3,}", stripped):
            # setext heading underline for the previous line
            lines.pop()
            break
        lines.append(stripped)
    return "\n".join(lines).strip()


def url_from_project_urls(metadata: PackageMetadata, labels: Iterable[str]) -> Optional[str]:
    """Return the first Project-URL value whose label (case-insensitive) is in `labels`."""
    wanted = {label.lower() for label in labels}
    for entry in metadata.get_all("project-url") or ():
        label, _, url = entry.partition(", ")
        if label.strip().lower() in wanted:
            return url.strip()
    return None


class FileDistribution(Distribution):
    """
    From a file e.g. a single `.metadata` fetched from pypi instead of a
    `*.dist-info` folder.
    """

    def __init__(self, raw_text):
        self.raw_text = raw_text

    def read_text(self, filename: str) -> Optional[str]:
        if filename == "METADATA":
            return self.raw_text
        else:
            return None

    def locate_file(self, path):
        """
        Given a path to a file in this distribution, return a path
        to it.
        """
        return None


@dataclasses.dataclass
class PackageRecord:
    # what goes in info/index.json
    name: str
    version: str
    subdir: str
    depends: List[str]
    extras: Dict[str, List[str]]
    build_number: int = 0
    build_text: str = "pypi"  # e.g. hash
    license_family: str = ""
    license: str = ""
    noarch: str = ""
    timestamp: int = 0

    def to_index_json(self):
        return {
            "build_number": self.build_number,
            "build": self.build,
            "depends": self.depends,
            "extras": self.extras,
            "license_family": self.license_family,
            "license": self.license,
            "name": self.name,
            "noarch": self.noarch,
            "subdir": self.subdir,
            "timestamp": self.timestamp,
            "version": self.version,
        }

    @property
    def build(self):
        return f"{self.build_text}_{self.build_number}"

    @property
    def stem(self):
        return f"{self.name}-{self.version}-{self.build}"


@dataclasses.dataclass
class CondaMetadata:
    metadata: PackageMetadata
    console_scripts: List[str]
    package_record: PackageRecord
    about: Dict[str, Any]

    def link_json(self) -> Optional[dict]:
        """
        info/link.json used for console scripts; None if empty.

        Note the METADATA file aka PackageRecord does not list console scripts.
        """
        # XXX gui scripts?
        return {
            "noarch": {"entry_points": self.console_scripts, "type": "python"},
            "package_metadata_version": 1,
        }

    @classmethod
    def from_distribution(
        cls,
        distribution: Distribution,
        pypi_to_conda_name_mapping: dict | None = None,
        channels: Iterable[str] = (),
    ):
        metadata = distribution.metadata

        python_version = metadata.get("requires-python")
        requires_python = "python"
        if python_version:
            requires_python = f"python {python_version}"

        requirements, extras = requires_to_conda(distribution.requires, pypi_to_conda_name_mapping)

        # conda does support ~=3.0.0 "compatibility release" matches
        depends = [requires_python] + requirements

        console_scripts = [
            f"{ep.name} = {ep.value}"
            for ep in distribution.entry_points
            if ep.group == "console_scripts"
        ]

        noarch = "python"

        # Common "about" keys
        # ['channels', 'conda_build_version', 'conda_version', 'description',
        # 'dev_url', 'doc_url', 'env_vars', 'extra', 'home', 'identifiers',
        # 'keywords', 'license', 'license_family', 'license_file', 'root_pkgs',
        # 'summary', 'tags', 'conda_private', 'doc_source_url', 'license_url']

        about: Dict[str, Any] = {
            "summary": metadata.get("summary") or "",
            "description": short_description(metadata.get("description") or ""),
            # https://packaging.python.org/en/latest/specifications/core-metadata/#license-expression
            "license": metadata.get("License-Expression") or metadata.get("License") or "",
        }

        for conda_field, labels in URL_LABEL_MAP.items():
            url = url_from_project_urls(metadata, labels)
            if url:
                about[conda_field] = url

        channels_list = list(channels)
        if channels_list:
            about["channels"] = channels_list

        name = pypi_to_conda_name(
            getattr(distribution, "name", None) or distribution.metadata.get("name"),
            pypi_to_conda_name_mapping,
        )
        version = getattr(distribution, "version", None) or distribution.metadata.get("version")

        package_record = PackageRecord(
            build_number=0,
            depends=depends,
            extras=extras,
            license=about["license"] or "",
            license_family="",
            name=name,
            version=version,
            subdir="noarch",
            noarch=noarch,
            timestamp=time.time_ns() // 1000000,
        )

        about["extra"] = {
            "recipe": {
                "name": package_record.name,
                "version": package_record.version,
                "build": package_record.build,
            },
            "generator": "conda-pypi",
            "generator_version": __version__,
        }

        return cls(
            metadata=metadata,
            package_record=package_record,
            console_scripts=console_scripts,
            about=about,
        )


def requires_to_conda(
    requires: Optional[List[str]], pypi_to_conda_name_mapping: dict | None = None
):
    from collections import defaultdict

    extras: Dict[str, List[str]] = defaultdict(list)
    requirements = []
    for requirement in [Requirement(dep) for dep in requires or []]:
        # Use parsed Requirement.name so unmapped conda names preserve dots (lookup still canonicalizes).
        requirement.name = pypi_to_conda_name(requirement.name, pypi_to_conda_name_mapping)
        # PEP 508 optional dependency extras (e.g. requests[security]) are intentionally
        # omitted: conda MatchSpec does not support the name[extras] bracket syntax yet
        as_conda = requirement.name + str(requirement.specifier)

        # Wheel METADATA → conda depends: do not emit ``[when=…]`` (conda MatchSpec does not
        # parse it yet). Match main: only ``extra == …`` is routed to the extras map.
        # Other markers are omitted from depends.
        if (marker := requirement.marker) is not None:
            for mark in marker._markers:
                if isinstance(mark, tuple):
                    var, _, value = mark
                    if str(var) == "extra":
                        extras[str(value)].append(as_conda)
        else:
            requirements.append(as_conda)

    return requirements, dict(extras)

    # if there is a url or extras= here we have extra work, may need to
    # yield Requirement not str
    # sorted(packaging.requirements.SpecifierSet("<5,>3")._specs, key=lambda x: x.version)
    # or just sorted lexicographically in str(SpecifierSet)
    # yield f"{requirement.name} {requirement.specifier}"


def conda_to_requires(match_spec: MatchSpec) -> Requirement | None:
    match_spec = remap_match_spec_name(match_spec, conda_to_pypi_name)

    name = match_spec.name
    if name == "*":
        return None
    version = match_spec.version
    if version:
        version_str = str(version)
        if version_str == "*":
            return Requirement(name)
        if version_str.endswith(".*"):
            version_str = version_str[:-2]
        if version_str and version_str[0] not in "<>=!~":
            version_str = f"=={version_str}"
        return Requirement(f"{name}{version_str}")

    return Requirement(name)


def remap_match_spec_name(match_spec: MatchSpec, name_map: Callable[[str], str]) -> MatchSpec:
    name = match_spec.name
    if name == "*":
        return match_spec

    mapped_name = name_map(name)
    if mapped_name == name:
        return match_spec

    return MatchSpec(match_spec, name=mapped_name)


def validate_name_mapping_format(mapping: dict) -> None:
    """
    Validate that the name mapping dict has the correct format.

    Expected format:
    - A dict where keys are PyPI package names (strings)
    - Values are dicts with at least "conda_name" key (string)
    - Optionally can have "pypi_name", "import_name", "mapping_source" keys
    - Empty dict is allowed

    Raises ArgumentError if format is invalid.
    """

    # Check that mapping is a dict and has .items() method
    if not isinstance(mapping, dict):
        raise ArgumentError(f"Name mapping must be a dictionary, got {type(mapping).__name__}")

    try:
        items = mapping.items()
    except AttributeError:
        raise ArgumentError(
            f"Name mapping must be a dictionary with .items() method, got {type(mapping).__name__}"
        )

    for pypi_name, value in items:
        if not isinstance(pypi_name, str):
            raise ArgumentError(
                f"Name mapping keys must be strings, got {type(pypi_name).__name__} for key: {pypi_name!r}"
            )

        if not isinstance(value, dict):
            raise ArgumentError(
                f"Name mapping values must be dictionaries, got {type(value).__name__} for key {pypi_name!r}"
            )

        if "conda_name" not in value:
            raise ArgumentError(
                f"Name mapping entry for {pypi_name!r} is missing required key 'conda_name'"
            )

        if not isinstance(value["conda_name"], str):
            raise ArgumentError(
                f"Name mapping entry for {pypi_name!r} has invalid 'conda_name' type: expected str, got {type(value['conda_name']).__name__}"
            )


if __name__ == "__main__":  # pragma: no cover
    base = sys.argv[1]
    for path in Path(base).glob("*.dist-info"):
        print(CondaMetadata.from_distribution(PathDistribution(path)))
