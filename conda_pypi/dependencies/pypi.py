"""Check and install Python build requirements in a target conda environment."""

import importlib.resources
import json
import subprocess
from collections.abc import Iterable
from importlib.metadata import Distribution
from pathlib import Path

from conda.cli.main import main_subshell
from packaging.requirements import Requirement

from conda_pypi import paths
from conda_pypi.exceptions import CondaPypiError
from conda_pypi.translate import requires_to_conda


class MissingDependencyError(CondaPypiError):
    """The target environment does not satisfy the project's build requirements."""

    def __init__(self, dependencies: list[str]):
        self.dependencies = dependencies
        super().__init__(
            "The target environment is missing %(requirements)s",
            requirements=", ".join(dependencies),
        )


def check_dependencies(requirements: Iterable[str], prefix: Path) -> list[str]:
    """Check target metadata using conda-pypi's copy of packaging."""
    requirements = sorted(requirements)
    if not requirements:
        return []

    script = (
        importlib.resources.files("conda_pypi").joinpath("dependencies_subprocess.py").read_text()
    )
    result = subprocess.run(
        [str(paths.get_python_executable(prefix)), "-I", "-"],
        encoding="utf-8",
        input=script,
        capture_output=True,
        check=True,
    )
    target = json.loads(result.stdout)
    checked = set()
    missing = []

    def check(requirement_text: str, parent_extras: Iterable[str]) -> None:
        requirement = Requirement(requirement_text)
        if requirement.marker and not any(
            requirement.marker.evaluate({**target["markers"], "extra": extra})
            for extra in ("", *parent_extras)
        ):
            return
        if requirement in checked:
            return
        checked.add(requirement)
        distribution = next(
            Distribution.discover(name=requirement.name, path=target["sys_path"]), None
        )
        if distribution is None or (
            requirement.specifier
            and not requirement.specifier.contains(distribution.version, prereleases=True)
        ):
            missing.append(str(requirement))
            return
        for child in distribution.requires or ():
            check(child, requirement.extras)

    for requirement in requirements:
        check(requirement, ())
    return missing


def ensure_requirements(requirements: list[str], prefix: Path, yes: bool = True):
    if requirements:
        conda_requirements, _ = requires_to_conda(requirements)
        command = ["install", "--prefix", str(prefix)]
        if yes:
            command.append("--yes")
        command.extend(conda_requirements)
        main_subshell(*command)
