"""Marker conversion.

Marker conversion includes:
- Convert Python markers to `python...` matchspec fragments, including
  `python_version not in "x, y"` -> `(python!=x and python!=y)`.
- Convert platform/os markers to virtual packages when feasible
  (`__win`, `__linux`, `__osx`, `__unix`).
- Keep extras in `extra_depends`, with remaining non-extra marker logic
  encoded via `[when="..."]`.
- Drop unsupported marker dimensions (for example interpreter/machine-specific
  variants) for these noarch channel tests.
"""

import json
import sys
from typing import Any

from packaging.markers import Marker

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):
        pass


class MarkerVar(StrEnum):
    PYTHON_VERSION = "python_version"
    PYTHON_FULL_VERSION = "python_full_version"
    EXTRA = "extra"
    SYS_PLATFORM = "sys_platform"
    PLATFORM_SYSTEM = "platform_system"
    OS_NAME = "os_name"
    IMPLEMENTATION_NAME = "implementation_name"
    PLATFORM_PYTHON_IMPLEMENTATION = "platform_python_implementation"
    PLATFORM_MACHINE = "platform_machine"


class MarkerOp(StrEnum):
    EQ = "=="
    NE = "!="
    NOT_IN = "not in"


SYSTEM_TO_VIRTUAL_PACKAGE = {
    "windows": "__win",
    "win32": "__win",
    "linux": "__linux",
    "darwin": "__osx",
    "cygwin": "__unix",
}
OS_NAME_TO_VIRTUAL_PACKAGE = {
    "nt": "__win",
    "windows": "__win",
    "posix": "__unix",
}


def _normalize_marker_clause(marker_name: str, op: str, marker_value: str) -> str | None:
    """Map a single PEP 508 marker atom to a MatchSpec-like fragment.

    Examples:
    - ("sys_platform", "==", "win32") -> "__win"
    - ("python_version", "<", "3.11") -> "python<3.11"
    - ("python_version", "not in", "3.0, 3.1") -> "(python!=3.0 and python!=3.1)"
    - ("implementation_name", "==", "cpython") -> None

    The following marker_names are unsupported and return None:
    - "platform_machine"
    - "implementation_name"
    - "platform_python_implementation"
    - "extra"

    """
    if marker_name in {MarkerVar.PYTHON_VERSION, MarkerVar.PYTHON_FULL_VERSION}:
        if op == MarkerOp.NOT_IN:
            clauses = [
                f"python!={version}"
                for value in marker_value.split(",")
                if (version := value.strip())
            ]
            if not clauses:
                return None
            return clauses[0] if len(clauses) == 1 else f"({' and '.join(clauses)})"
        return f"python{op}{marker_value}"

    if marker_name in {MarkerVar.SYS_PLATFORM, MarkerVar.PLATFORM_SYSTEM}:
        mapped = SYSTEM_TO_VIRTUAL_PACKAGE.get(marker_value)
        if op == MarkerOp.EQ and mapped:
            return mapped
        if op == MarkerOp.NE and marker_value in {"win32", "windows", "cygwin"}:
            # != emscripten is unsupported
            return "__unix"
        return None

    if marker_name == MarkerVar.OS_NAME:
        mapped = OS_NAME_TO_VIRTUAL_PACKAGE.get(marker_value)
        if not mapped or op not in {MarkerOp.EQ, MarkerOp.NE}:
            return None
        if op == MarkerOp.EQ:
            return mapped
        return "__unix" if mapped == "__win" else "__win"

    return None


def extract_marker_condition_and_extras(marker: Marker) -> tuple[str | None, list[str]]:
    """Split a Marker into optional non-extra condition and extra group names.

    Examples:
    - `extra == "docs"` -> `(None, ["docs"])`
    - `python_version < "3.11" and extra == "test"` -> `("python<3.11", ["test"])`
    - `sys_platform == "win32"` -> `("__win", [])`
    """
    extras: list[str] = []

    def parse_marker_node(node: Any) -> str | None:
        if isinstance(node, tuple) and len(node) == 3:
            marker_name = _marker_value(node[0])
            op = _marker_value(node[1])
            marker_value = _marker_value(node[2]).lower()

            if marker_name == MarkerVar.EXTRA and op == MarkerOp.EQ:
                extras.append(marker_value)
                return None

            return _normalize_marker_clause(marker_name, op, marker_value)

        if isinstance(node, list) and node:
            condition_expr = parse_marker_node(node[0])
            for op, rhs in zip(node[1::2], node[2::2]):
                right_condition = parse_marker_node(rhs)
                condition_expr = _combine_conditions(condition_expr, op.lower(), right_condition)
            return condition_expr

        return None

    # Marker._markers is a private packaging attribute; keep access isolated here.
    condition = parse_marker_node(getattr(marker, "_markers", []))
    return condition, list(dict.fromkeys(extras))


def dependency_extras_suffix(requirement_extras: set[str] | frozenset[str]) -> str:
    """Bracket suffix for conda `MatchSpec` optional dependency extras (PEP 508 extras).

    Output order is sorted for stability.
    """
    if not requirement_extras:
        return ""
    return f"[{','.join(sorted(requirement_extras))}]"


def dependency_when(dependency: str, condition: str | None) -> str:
    if not condition:
        return dependency
    # ensure proper quoting
    condition = json.dumps(condition)
    return f"{dependency}[when={condition}]"


def _marker_value(token: Any) -> str:
    """Extract the textual value from packaging marker tokens."""
    return getattr(token, "value", str(token))


def _combine_conditions(left: str | None, op: str, right: str | None) -> str | None:
    """Combine optional left/right expressions with a boolean operator."""
    if left is None:
        return right
    if right is None:
        return left
    if left == right:
        return left
    return f"({left} {op} {right})"
