"""
Convert a dependency tree from pypi into .conda packages
"""

from __future__ import annotations

import logging
import pathlib
import re
import tempfile
from pathlib import Path
from typing import Union, Optional, List

from conda_rattler_solver.solver import RattlerSolver

import conda.exceptions
import platformdirs
from conda.base.context import context, fresh_context
from conda.common.path import get_python_short_path
from conda.models.channel import Channel
from conda.models.match_spec import MatchSpec
from conda.models.records import PrefixRecord
from conda.reporters import get_spinner
from conda.core.solve import Solver
from conda.exceptions import UnsatisfiableError

from unearth import PackageFinder

from conda_pypi.build import build_conda
from conda_pypi.downloader import find_and_fetch, get_package_finder
from conda_pypi.index import update_index
from conda_pypi.translate import FileDistribution, check_import_name_conflicts
from conda_pypi.utils import SuppressOutput

log = logging.getLogger(__name__)


def _format_conflict_line(conflict: tuple, new_pkgs: set | None = None) -> str:
    """
    Return a human-readable description of a single PEP 794 conflict tuple
    """
    name, pkg1, pkg2, kind = conflict
    if kind == "ambiguous-in-both":
        return (
            f"  '{name}': package '{pkg1}' lists it in both "
            "Import-Name and Import-Namespace (ambiguous)"
        )
    if new_pkgs is not None:
        # In a cross-install context: identify which party is new vs already installed.
        incoming = pkg2 if pkg2 in new_pkgs else pkg1
        existing = pkg1 if pkg2 in new_pkgs else pkg2
        return f"  '{name}': incoming '{incoming}' conflicts with already-installed '{existing}' ({kind})"
    return f"  '{name}': '{pkg1}' and '{pkg2}' ({kind})"


NOTHING_PROVIDES_RE = re.compile(r"nothing provides (.*) needed by")
RATTLER_NOTHING_PROVIDES_RE = re.compile(r"\b(.*), (.)* (n|N)o candidates were found(.*)")


def parse_libmamba_solver_error(message: str):
    """
    Parse missing packages out of UnsatisfiableError message.
    """
    for line in message.splitlines():
        if match := NOTHING_PROVIDES_RE.search(line):
            yield match.group(1)


def parse_rattler_solver_error(message: str):
    """
    Parse missing packages out of UnsatisfiableError message.
    """
    for line in message.splitlines():
        if match := RATTLER_NOTHING_PROVIDES_RE.search(line):
            yield match.group(1)


# import / pupate / transmogrify / ...
class ConvertTree:
    def __init__(
        self,
        prefix: Optional[Union[pathlib.Path, str]],
        override_channels=False,
        repo: Optional[pathlib.Path] = None,
        finder: Optional[PackageFinder] = None,  # to change index_urls e.g.
    ):
        # platformdirs location has a space in it; ok?
        # will be expanded to %20 in "as uri" output, conda understands that.
        self.repo = repo or Path(platformdirs.user_data_dir("conda-pypi"))
        prefix = prefix or context.active_prefix
        if not prefix:
            raise ValueError("prefix is required")
        self.prefix = Path(prefix)
        self.override_channels = override_channels
        self.python_exe = Path(self.prefix, get_python_short_path())

        if not finder:
            finder = self.default_package_finder()
        self.finder = finder

    def _convert_loop(
        self,
        max_attempts: int,
        solver: Solver,
        tmp_path: Path,
    ) -> tuple[tuple[PrefixRecord, ...], tuple[PrefixRecord, ...]] | None:
        converted = set()
        fetched_packages = set()
        missing_packages = set()
        attempts = 0

        repo = self.repo
        wheel_dir = tmp_path / "wheels"
        wheel_dir.mkdir(exist_ok=True)

        while len(fetched_packages) < max_attempts and attempts < max_attempts:
            attempts += 1
            try:
                # suppress messages coming from the solver
                with SuppressOutput():
                    changes = solver.solve_for_diff()
                break
            except conda.exceptions.PackagesNotFoundError as e:
                missing_packages = set(e._kwargs["packages"])
                log.debug(f"Missing packages: {missing_packages}")
            except UnsatisfiableError as e:
                # parse message
                log.debug("Unsatisfiable: %r", e)
                missing_packages.update(set(parse_rattler_solver_error(e.message)))

            for package in sorted(missing_packages - fetched_packages):
                find_and_fetch(self.finder, wheel_dir, package)
                fetched_packages.add(package)

            for normal_wheel in wheel_dir.glob("*.whl"):
                if normal_wheel in converted:
                    continue

                log.debug(f"Converting '{normal_wheel}'")

                build_path = tmp_path / normal_wheel.stem
                build_path.mkdir()

                try:
                    package_conda = build_conda(
                        normal_wheel,
                        build_path,
                        repo / "noarch",  # XXX could be arch
                        self.python_exe,
                        is_editable=False,
                    )
                    log.debug("Conda at", package_conda)
                except FileExistsError:
                    log.debug(
                        f"Tried to convert wheel that is already conda-ized: {normal_wheel}",
                        exc_info=True,
                    )

                converted.add(normal_wheel)

            update_index(repo)
        else:
            log.debug(f"Exceeded maximum of {max_attempts} attempts")
            return None
        return changes

    def _collect_import_names_from_wheels(
        self, wheel_dir: pathlib.Path
    ) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        """Return a tuple of ``(names, namespaces)`` dicts from wheels in *wheel_dir*.

        Each key is the PyPI package name. The values are the raw Import-Name/Import-Namespace
        entries. The ``; private`` suffixes are preserved. Their stripping happens inside
        :func:`check_import_name_conflicts`.
        """
        from installer.sources import WheelFile

        from conda_pypi.name_mapping import pypi_to_conda_name

        names: dict[str, list[str]] = {}
        namespaces: dict[str, list[str]] = {}

        for wheel in wheel_dir.glob("*.whl"):
            try:
                with WheelFile.open(wheel) as source:
                    metadata_text = source.read_dist_info("METADATA")
                dist = FileDistribution(metadata_text)
                # Normalise to the conda package name (with the same transform used by
                # build_conda/CondaMetadata.from_distribution) so that wheel keys align with the
                # already-installed record names returned by _collect_import_names_from_prefix.
                # Without this, "Pillow" (from METADATA) and "pillow" (from PrefixRecord.name)
                # would be treated as different packages, causing spurious upgrade warnings.
                raw_name = dist.metadata.get("name") or wheel.stem
                pkg_name = pypi_to_conda_name(raw_name)
                if import_names := dist.metadata.get_all("import-name"):
                    names[pkg_name] = import_names
                if import_namespaces := dist.metadata.get_all("import-namespace"):
                    namespaces[pkg_name] = import_namespaces
            except Exception:
                log.debug("Could not read Import-Name from %s", wheel, exc_info=True)

        return names, namespaces

    def _collect_import_names_from_prefix(
        self,
    ) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        """Return a tuple of ``(names, namespaces)`` dicts for packages that are
        already installed in the prefix.

        Reads the ``info/about.json`` files from each package's extracted cache
        directory made available via ``PrefixRecord.extracted_package_dir``.
        Packages that predate PEP 794 and carry no ``import_names`` field are
        silently skipped as there is no data to check.

        Note: conda-forge packages never carry ``import_names`` because the conda
        package format has no equivalent of PEP 794 ``Import-Name`` metadata.
        Only packages previously installed via conda-pypi (which write
        ``import_names`` to ``info/about.json``) will appear here.
        """
        import json

        from conda.core.prefix_data import PrefixData

        names: dict[str, list[str]] = {}
        namespaces: dict[str, list[str]] = {}

        try:
            for record in PrefixData(self.prefix).iter_records():
                epd = getattr(record, "extracted_package_dir", None)
                if not epd:
                    continue
                about_path = pathlib.Path(epd) / "info" / "about.json"
                if not about_path.exists():
                    continue
                try:
                    about = json.loads(about_path.read_text(encoding="utf-8"))
                    if n := about.get("import_names"):
                        names[record.name] = n
                    if ns := about.get("import_namespaces"):
                        namespaces[record.name] = ns
                except Exception:
                    log.debug("Could not read import names from %s", about_path, exc_info=True)
        except Exception:
            log.debug("Could not scan prefix for already-installed import names", exc_info=True)

        return names, namespaces

    def _check_import_name_conflicts(self, wheel_dir: pathlib.Path) -> None:
        """Check for Import-Name conflicts among wheels being installed (PEP 794).

        Two conflict levels are handled here:

        1. Batch conflicts (SHOULD error per PEP 794): Two or more packages in
        *wheel_dir* share the same exclusive ``Import-Name``, or one package's
        ``Import-Name`` overlaps another's ``Import-Namespace``. Either case
        raises a ``CondaError``.

        2. Cross-install conflicts (MAY warn per PEP 794): A package being
        installed now shares an ``Import-Name`` or ``Import-Namespace``/
        ``Import-Name`` with a package that is already installed. This is logged
        as a warning rather than an error because some workflows intentionally
        replace a package's modules (e.g. multi-step installs with different
        tools). Only packages that carry PEP 794 metadata (i.e., installed
        previously via conda-pypi) are checked. conda-forge packages have no
        ``Import-Name`` metadata and are therefore invisible to this check.
        """
        from conda.exceptions import CondaError

        new_names, new_namespaces = self._collect_import_names_from_wheels(wheel_dir)

        if not new_names and not new_namespaces:
            return

        # Batch conflict check (SHOULD error)
        batch_conflicts = check_import_name_conflicts(new_names, new_namespaces)
        if batch_conflicts:
            lines = "\n".join(_format_conflict_line(c) for c in batch_conflicts)
            raise CondaError(
                f"Import name conflicts detected (PEP 794):\n{lines}\n"
                "Installing these packages together would cause one to shadow the other's "
                "modules at runtime.  Install them separately or choose non-conflicting packages."
            )

        # Cross-install conflict check (MAY warn)
        installed_names, installed_namespaces = self._collect_import_names_from_prefix()

        if not installed_names and not installed_namespaces:
            return

        # Merge: installed entries first so that new packages appear as the "second"
        # party in any returned conflict tuple, making messages easier to read.
        combined_names = {**installed_names, **new_names}
        combined_namespaces = {**installed_namespaces, **new_namespaces}
        all_conflicts = check_import_name_conflicts(combined_names, combined_namespaces)

        new_pkgs = set(new_names) | set(new_namespaces)

        cross_conflicts = [
            c
            for c in all_conflicts
            # Involves at least one newly-arriving package
            if (c[1] in new_pkgs or c[2] in new_pkgs)
            # but is not purely within the batch (already checked above)
            and not (c[1] in new_pkgs and c[2] in new_pkgs)
        ]

        if cross_conflicts:
            lines = "\n".join(_format_conflict_line(c, new_pkgs=new_pkgs) for c in cross_conflicts)
            log.warning(
                "Import name overlap with already-installed packages detected (PEP 794):\n%s\n"
                "This may cause one package's modules to shadow the other's at runtime. "
                "If this is intentional, you may ignore this warning.",
                lines,
            )

    def default_package_finder(self):
        return get_package_finder(self.prefix)

    def _get_converting_spinner_message(self, channels) -> str:
        pypi_index_names_dashed = "\n - ".join(
            s.get("url") for s in self.finder.sources if s.get("type") == "index"
        )

        canonical_names = list(dict.fromkeys([Channel(c).canonical_name for c in channels]))
        canonical_names_dashed = "\n - ".join(canonical_names)
        return (
            "Inspecting pypi and conda dependencies\n"
            "PYPI index channels:\n"
            f" - {pypi_index_names_dashed}\n"
            "Conda channels:\n"
            f" - {canonical_names_dashed}\n"
            "Converting required pypi packages"
        )

    def convert_tree(
        self, requested: List[MatchSpec], max_attempts: int = 80
    ) -> tuple[tuple[PrefixRecord, ...], tuple[PrefixRecord, ...]] | None:
        """
        Preform a solve on the list of requested packages and converts the full dependency
        tree to conda packages if required. The converted packages will be stored in the
        local conda-pypi channel.

        Args:
            requested: The list of requested packages.
            max_attempts: max number of times to try to execute the solve.

        Returns:
            A two-tuple of PackageRef sequences.  The first is the group of packages to
            remove from the environment, in sorted dependency order from leaves to roots.
            The second is the group of packages to add to the environment, in sorted
            dependency order from roots to leaves.

        """
        (self.repo / "noarch").mkdir(parents=True, exist_ok=True)
        if not (self.repo / "noarch" / "repodata.json").exists():
            update_index(self.repo)

        with tempfile.TemporaryDirectory() as tmp_path:
            tmp_path = pathlib.Path(tmp_path)

            WHEEL_DIR = tmp_path / "wheels"
            WHEEL_DIR.mkdir(exist_ok=True)

            prefix = pathlib.Path(self.prefix)
            assert prefix.exists()

            local_channel = Channel(self.repo.as_uri())

            if not self.override_channels:
                channels = [local_channel, *context.channels]
            else:  # more wheels for us to convert
                channels = [local_channel]

            solver = RattlerSolver(
                prefix=str(prefix),
                channels=channels,
                subdirs=context.subdirs,
                specs_to_add=requested,
                command="install",
            )

            context_env = {
                "CONDA_AGGRESSIVE_UPDATE_PACKAGES": "",
                "CONDA_AUTO_UPDATE_CONDA": "false",
            }

            with get_spinner(self._get_converting_spinner_message(channels)):
                with fresh_context(env=context_env):
                    changes = self._convert_loop(
                        max_attempts=max_attempts, solver=solver, tmp_path=tmp_path
                    )

            # PEP 794: raise an error if any two packages to be installed share an
            # Import-Name entry (as exclusive import names would shadow each other).
            wheel_dir = tmp_path / "wheels"
            if wheel_dir.exists():
                self._check_import_name_conflicts(wheel_dir)

            return changes
