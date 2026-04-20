"""
Convert a dependency tree from pypi into .conda packages
"""

from __future__ import annotations

import logging
import pathlib
import re
import tempfile
from pathlib import Path
from typing import List, Optional, Union

import conda.exceptions
import platformdirs
from conda.base.context import context, fresh_context
from conda.common.path import get_python_short_path
from conda.core.solve import Solver
from conda.exceptions import UnsatisfiableError
from conda.models.channel import Channel
from conda.models.match_spec import MatchSpec
from conda.models.records import PrefixRecord
from conda.reporters import get_spinner
from conda_rattler_solver.solver import RattlerSolver
from unearth import PackageFinder

from conda_pypi.build import build_conda
from conda_pypi.downloader import find_and_fetch, get_package_finder
from conda_pypi.index import update_index
from conda_pypi.utils import SuppressOutput

log = logging.getLogger(__name__)

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

            return changes
