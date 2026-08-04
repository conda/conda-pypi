"""Public dependency-checking API."""

from conda_pypi.dependencies.pypi import (
    MissingDependencyError,
    check_dependencies,
    ensure_requirements,
)

__all__ = [
    "MissingDependencyError",
    "check_dependencies",
    "ensure_requirements",
]
