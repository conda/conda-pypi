"""Public dependency-checking API."""

from .pypi import (
    MissingDependencyError,
    check_dependencies,
    ensure_requirements,
)

__all__ = [
    "MissingDependencyError",
    "check_dependencies",
    "ensure_requirements",
]
