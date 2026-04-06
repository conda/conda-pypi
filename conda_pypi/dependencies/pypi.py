"""
Check dependencies in a prefix, either by using Conda's functionality or
Python's in a subprocess.
"""

import importlib.resources
import json
import subprocess
from pathlib import Path
from typing import Iterable

from conda.cli.main import main_subshell

from conda_pypi import paths
from conda_pypi.translate import requires_to_conda


class MissingDependencyError(Exception):
    """
    When the dependency subprocess can't run.
    """

    def __init__(self, dependencies: list[str]):
        self.dependencies = dependencies


def check_dependencies(requirements: Iterable[str], prefix: Path):
    python_executable = str(paths.get_python_executable(prefix))
    dependency_getter = (
        importlib.resources.files("conda_pypi").joinpath("dependencies_subprocess.py").read_text()
    )
    try:
        result = subprocess.run(
            [
                python_executable,
                "-I",
                "-",
                "-r",
                json.dumps(sorted(requirements)),
            ],
            encoding="utf-8",
            input=dependency_getter,
            capture_output=True,
            check=True,
        )
        missing_raw = json.loads(result.stdout)
        missing = []
        for requirement in missing_raw:
            if isinstance(requirement, str):
                missing.append(requirement)
            elif isinstance(requirement, list) and requirement:
                missing.append(requirement[-1])
    except subprocess.CalledProcessError as e:
        if (
            "ModuleNotFound" in e.stderr
        ):  # Missing 'build' dependency aka 'python-build' in conda land
            raise MissingDependencyError(["build"]) from e
        else:
            raise

    return missing


def ensure_requirements(requirements: list[str], prefix: Path):
    if requirements:
        conda_requirements, _ = requires_to_conda(requirements)
        # -y may be appropriate during tests only
        main_subshell("install", "--prefix", str(prefix), "-y", *conda_requirements)
