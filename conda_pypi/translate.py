"""
Convert Python `*.dist-info/METADATA` to conda `info/index.json`
"""

import dataclasses
import logging
import sys
import time
from importlib.metadata import Distribution, PackageMetadata, PathDistribution
from pathlib import Path
from typing import Any, Optional, List, Dict, Callable

from conda.exceptions import ArgumentError
from conda.models.match_spec import MatchSpec
from packaging.requirements import Requirement

from conda_pypi.name_mapping import conda_to_pypi_name, pypi_to_conda_name

log = logging.getLogger(__name__)


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
        cls, distribution: Distribution, pypi_to_conda_name_mapping: dict | None = None
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

        about = {
            "summary": metadata.get("summary") or "",
            "description": metadata.get("description") or "",
            # https://packaging.python.org/en/latest/specifications/core-metadata/#license-expression
            "license": metadata.get("license_expression") or metadata.get("license") or "",
        }

        import_names = metadata.get_all("import-name")
        import_namespaces = metadata.get_all("import-namespace")
        if import_names is not None:
            about["import_names"] = import_names
        if import_namespaces is not None:
            about["import_namespaces"] = import_namespaces

        if project_urls := metadata.get_all("project-url"):
            urls = dict(url.split(", ", 1) for url in project_urls)
            for py_name, conda_name in (
                ("Home", "home"),
                ("Development", "dev_url"),
                ("Documentation", "doc_url"),
            ):
                if py_name in urls:
                    about[conda_name] = urls[py_name]

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


def _strip_private(entry: str) -> str:
    """Strip the optional ``; private`` modifier from an Import-Name/Namespace entry."""
    return entry.split(";")[0].strip()


def check_import_name_conflicts(
    package_import_names: Dict[str, List[str]],
    package_import_namespaces: Optional[Dict[str, List[str]]] = None,
) -> List[tuple]:
    """Check for Import-Name conflicts between packages (PEP 794).

    Per PEP 794 (SHOULD level):

    * Two packages sharing the same ``Import-Name`` entry would shadow each
      other's modules: this is an error.
    * A package whose ``Import-Name`` overlaps with another package's
      ``Import-Namespace`` entry is also an error, because the exclusive name
      would shadow the namespace package.
    * Overlapping ``Import-Namespace`` entries are intentionally allowed
      (that is the whole point of namespace packages) and are not checked here.

    Args:
        package_import_names: Mapping of ``{package_name: [import_name_entries]}``.
        package_import_namespaces: Optional mapping of
            ``{package_name: [import_namespace_entries]}``.  Pass ``None`` (or
            omit) when namespace data is unavailable.

    Returns:
        List of ``(import_name, first_package, second_package, conflict_kind)``
        4-tuples, one per detected conflict.  *conflict_kind* is either
        ``"exclusive"`` (Import-Name vs Import-Name) or
        ``"exclusive-vs-namespace"`` (Import-Name vs Import-Namespace).
        Empty list when there are no conflicts.
    """
    if package_import_namespaces is None:
        package_import_namespaces = {}

    # --- MUST checks from PEP 794 -------------------------------------------------
    # A single project MUST NOT list the same name in both Import-Name and
    # Import-Namespace. Tools MUST raise an error for that ambiguity.
    all_pkg_names = set(package_import_names) | set(package_import_namespaces)
    conflicts = []
    for pkg_name in sorted(all_pkg_names):
        exclusive_set = {_strip_private(e) for e in package_import_names.get(pkg_name, [])} - {""}
        namespace_set = {
            _strip_private(e) for e in package_import_namespaces.get(pkg_name, [])
        } - {""}
        for bare in sorted(exclusive_set & namespace_set):
            conflicts.append((bare, pkg_name, pkg_name, "ambiguous-in-both"))

    # --- Cross-package checks -----------------------------------------------------
    # Index all namespace names first so our exclusive-vs-namespace checks can see them.
    namespace: Dict[str, str] = {}  # bare name --> first pkg that lists it as namespace
    for pkg_name, ns_entries in package_import_namespaces.items():
        for entry in ns_entries:
            bare = _strip_private(entry)
            if bare and bare not in namespace:
                namespace[bare] = pkg_name

    exclusive: Dict[str, str] = {}  # bare name --> pkg that owns it exclusively

    for pkg_name, name_entries in package_import_names.items():
        for entry in name_entries:
            bare = _strip_private(entry)
            if not bare:
                # An explicitly-empty Import-Name means that the project has no import names.
                continue

            # Import-Name vs Import-Name (both exclusive: SHOULD error per PEP 794)
            if bare in exclusive:
                conflicts.append((bare, exclusive[bare], pkg_name, "exclusive"))
            else:
                exclusive[bare] = pkg_name

            # Import-Name vs Import-Namespace cross-conflicts (also SHOULD error per PEP 794)
            if bare in namespace and namespace[bare] != pkg_name:
                conflicts.append((bare, namespace[bare], pkg_name, "exclusive-vs-namespace"))

    return conflicts


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
