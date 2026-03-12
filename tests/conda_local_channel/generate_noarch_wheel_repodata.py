"""
Utility for generating test-specific local channel repodata.

This is test data generation logic for conda-pypi only; it is not intended for
production repodata generation.

Marker conversion policy for this test channel:
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
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import StrEnum
from packaging.markers import Marker
from packaging.requirements import Requirement
from typing import Any


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


def normalize_name(name: str) -> str:
    """Normalize a package name to conda conventions (lowercase, _ -> -)."""
    return name.lower().replace("_", "-")


def _marker_value(token: Any) -> str:
    """Extract the textual value from packaging marker tokens."""
    return getattr(token, "value", str(token))


def _normalize_marker_atom(lhs: str, op: str, rhs: str) -> str | None:
    """Map a single PEP 508 marker atom to a MatchSpec-like fragment."""
    lhs_l = lhs.lower()
    rhs_l = rhs.lower()

    if lhs_l in {MarkerVar.PYTHON_VERSION, MarkerVar.PYTHON_FULL_VERSION}:
        if op == MarkerOp.NOT_IN:
            excluded_versions = [version.strip() for version in rhs.split(",") if version.strip()]
            if not excluded_versions:
                return None
            clauses = [f"python!={version}" for version in excluded_versions]
            if len(clauses) == 1:
                return clauses[0]
            return f"({' and '.join(clauses)})"
        return f"python{op}{rhs}"

    if lhs_l == MarkerVar.EXTRA and op == MarkerOp.EQ:
        return None

    if lhs_l in {MarkerVar.SYS_PLATFORM, MarkerVar.PLATFORM_SYSTEM}:
        mapped = SYSTEM_TO_VIRTUAL_PACKAGE.get(rhs_l)
        if op == MarkerOp.EQ and mapped:
            return mapped
        if op == MarkerOp.NE and rhs_l in {"win32", "windows", "cygwin"}:
            return "__unix"
        if op == MarkerOp.NE and rhs_l == "emscripten":
            return None
        return None

    if lhs_l == MarkerVar.OS_NAME:
        mapped = OS_NAME_TO_VIRTUAL_PACKAGE.get(rhs_l)
        if not mapped:
            return None
        if op == MarkerOp.EQ:
            return mapped
        if op == MarkerOp.NE:
            return "__unix" if mapped == "__win" else "__win"
        return None

    if lhs_l in {MarkerVar.IMPLEMENTATION_NAME, MarkerVar.PLATFORM_PYTHON_IMPLEMENTATION}:
        if rhs_l in {"cpython", "pypy", "jython"}:
            return None
        return None

    if lhs_l == MarkerVar.PLATFORM_MACHINE:
        return None

    return None


def _combine_expr(left: str | None, op: str, right: str | None) -> str | None:
    """Combine optional left/right expressions with a boolean operator."""
    if left is None:
        return right
    if right is None:
        return left
    if left == right:
        return left
    return f"({left} {op} {right})"


def extract_marker_condition_and_extras(marker: Marker) -> tuple[str | None, list[str]]:
    """Split a Marker into optional non-extra condition and extra group names."""
    extras: list[str] = []
    seen_extras: set[str] = set()

    def visit(node: Any) -> str | None:
        if isinstance(node, tuple) and len(node) == 3:
            lhs = _marker_value(node[0])
            op = _marker_value(node[1])
            rhs = _marker_value(node[2])

            if lhs.lower() == MarkerVar.EXTRA and op == MarkerOp.EQ:
                extra_name = rhs.lower()
                if extra_name not in seen_extras:
                    seen_extras.add(extra_name)
                    extras.append(extra_name)
                return None

            return _normalize_marker_atom(lhs, op, rhs)

        if isinstance(node, list):
            if not node:
                return None

            expr = visit(node[0])
            i = 1
            while i + 1 < len(node):
                op = str(node[i]).lower()
                rhs_expr = visit(node[i + 1])
                expr = _combine_expr(expr, op, rhs_expr)
                i += 2
            return expr

        return None

    # Marker._markers is a private packaging attribute; keep access isolated here.
    condition = visit(getattr(marker, "_markers", []))
    return condition, extras


def pypi_to_repodata_noarch_whl_entry(
    pypi_data: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Convert PyPI JSON endpoint data to a repodata.json v3.whl entry for a
    pure Python (noarch) wheel.

    Args:
        pypi_data: Dictionary containing the complete info from PyPI JSON endpoint

    Returns:
        Dictionary representing the entry for v3.whl, or None if no pure
        Python wheel (platform tag "none-any") is found
    """
    # Find a pure Python wheel (platform tag "none-any")
    wheel_url = None
    for url_entry in pypi_data.get("urls", []):
        if url_entry.get("packagetype") != "bdist_wheel":
            continue
        filename = url_entry.get("filename", "")
        if not filename.endswith("-none-any.whl"):
            continue
        wheel_url = url_entry
        break

    if not wheel_url:
        return None

    pypi_info = pypi_data.get("info")

    depends_list: list[str] = []
    extra_depends_dict: dict[str, list[str]] = {}
    for dep in pypi_info.get("requires_dist") or []:
        req = Requirement(dep)
        conda_dep = normalize_name(req.name) + str(req.specifier)

        if req.marker:
            non_extra_condition, extra_names = extract_marker_condition_and_extras(req.marker)
            if extra_names:
                for extra_name in extra_names:
                    extra_dep = conda_dep
                    if non_extra_condition:
                        marker_condition = json.dumps(non_extra_condition)
                        extra_dep = f"{extra_dep}[when={marker_condition}]"
                    extra_depends_dict.setdefault(extra_name, []).append(extra_dep)
            else:
                if non_extra_condition:
                    marker_condition = json.dumps(non_extra_condition)
                    depends_list.append(f"{conda_dep}[when={marker_condition}]")
                else:
                    depends_list.append(conda_dep)
        else:
            depends_list.append(conda_dep)

    python_requires = pypi_info.get("requires_python")
    if python_requires:
        depends_list.append(f"python {python_requires}")
    else:
        # Noarch python packages should still depend on python when PyPI omits requires_python
        depends_list.append("python")

    # Build the repodata entry
    entry = {
        "url": wheel_url.get("url", ""),
        "record_version": 3,
        "name": normalize_name(pypi_info.get("name", "")),
        "version": pypi_info.get("version"),
        "build": "py3_none_any_0",
        "build_number": 0,
        "depends": depends_list,
        "extra_depends": extra_depends_dict,
        "fn": f"{pypi_info.get('name')}-{pypi_info.get('version')}-py3-none-any.whl",
        "sha256": wheel_url.get("digests", {}).get("sha256", ""),
        "size": wheel_url.get("size", 0),
        "subdir": "noarch",
        # "timestamp": wheel_url.get("upload_time", 0),
        "noarch": "python",
    }

    return entry


def get_repodata_entry(name: str, version: str) -> dict[str, Any] | None:
    pypi_endpoint = f"https://pypi.org/pypi/{name}/{version}/json"
    pypi_data = requests.get(pypi_endpoint)
    if pypi_data.json() is None:
        raise Exception(f"unable to process {name} {version}")
    return pypi_to_repodata_noarch_whl_entry(pypi_data.json())


if __name__ == "__main__":
    from pathlib import Path

    HERE = Path(__file__).parent
    wheel_repodata = HERE / "noarch/repodata.json"

    pkg_whls = {}
    repodata_packages = []
    requested_wheel_packages_file = HERE / "wheel_packages.txt"
    with open(requested_wheel_packages_file) as f:
        pkgs_data = f.read()
        for pkg in pkgs_data.splitlines():
            repodata_packages.append(tuple(pkg.split("==")))

    # Run in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=25) as executor:
        # Map each package to its repodata entry
        futures = {
            executor.submit(get_repodata_entry, pkg_tuple[0], pkg_tuple[1]): pkg_tuple
            for pkg_tuple in repodata_packages
        }

        # Collect results as they complete
        for future in as_completed(futures):
            pkg_tuple = futures[future]
            name, version = pkg_tuple
            try:
                result = future.result()
                if result:
                    # Use the normalized name for the key
                    pkg_whls[f"{result['name']}-{version}-py3_none_any_0"] = result
            except Exception as e:
                print(f"Error processing {name} {version}: {e}")

    repodata_output = {
        "info": {"subdir": "noarch"},
        "packages": {},
        "packages.conda": {},
        "removed": [],
        "repodata_version": 3,
        "signatures": {},
        "v3": {"whl": {key: value for key, value in sorted(pkg_whls.items())}},
    }

    with open(wheel_repodata, "w") as f:
        json.dump(repodata_output, f, indent=4)
