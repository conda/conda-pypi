# This is a utility for generating test specific data in conda-pypi
# only. It is not appropriate to use this to generate production level
# repodata.

import json
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from packaging.requirements import Requirement
from typing import Any

EXTRA_MATCH_RE = re.compile(r"""extra\s*==\s*(['"])([^'"]+)\1""")
PYTHON_VERSION_MARKER_RE = re.compile(r"""\bpython_version\s*([<>=!~]{1,2})\s*(['"])([^'"]+)\2""")
PYTHON_FULL_VERSION_MARKER_RE = re.compile(
    r"""\bpython_full_version\s*([<>=!~]{1,2})\s*(['"])([^'"]+)\2"""
)
PYTHON_VERSION_NOT_IN_RE = re.compile(r"""\bpython_version\s+not\s+in\s+(['"])[^'"]+\1""")
PLATFORM_SYSTEM_MARKER_RE = re.compile(r"""\bplatform_system\s*(==|!=)\s*(['"])([^'"]+)\2""")
SYS_PLATFORM_MARKER_RE = re.compile(r"""\bsys_platform\s*(==|!=)\s*(['"])([^'"]+)\2""")
CPYTHON_MARKER_RE = re.compile(r"""\bplatform_python_implementation\s*==\s*(['"])CPython\1""")
CPYTHON_NEGATION_MARKER_RE = re.compile(
    r"""\bplatform_python_implementation\s*!=\s*(['"])CPython\1"""
)
PYPY_NEGATION_MARKER_RE = re.compile(r"""\bplatform_python_implementation\s*!=\s*(['"])PyPy\1""")
CYGWIN_NEGATION_MARKER_RE = re.compile(r"""\bsys_platform\s*!=\s*(['"])cygwin\1""")
OS_NAME_MARKER_RE = re.compile(r"""\bos_name\s*(==|!=)\s*(['"])([^'"]+)\2""")
IMPL_NAME_MARKER_RE = re.compile(r"""\bimplementation_name\s*(==|!=)\s*(['"])([^'"]+)\2""")
PLATFORM_PY_IMPL_MARKER_RE = re.compile(
    r"""\bplatform_python_implementation\s*(==|!=)\s*(['"])([^'"]+)\2"""
)
PLATFORM_MACHINE_MARKER_RE = re.compile(r"""\bplatform_machine\s*(==|!=)\s*(['"])([^'"]+)\2""")

PLATFORM_SYSTEM_TO_VIRTUAL_PACKAGE = {
    "windows": "__win",
    "linux": "__linux",
    "darwin": "__osx",
}

SYS_PLATFORM_TO_VIRTUAL_PACKAGE = {
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


def split_marker_extras(marker: str) -> tuple[list[str], str | None]:
    """Split a PEP 508 marker into extra names and remaining non-extra condition."""
    extras = [match.group(2) for match in EXTRA_MATCH_RE.finditer(marker)]
    if not extras:
        return [], marker

    non_extra = marker
    non_extra = re.sub(r"""\(\s*extra\s*==\s*(['"]).*?\1\s*\)""", "", non_extra)
    non_extra = re.sub(r"""extra\s*==\s*(['"]).*?\1""", "", non_extra)
    non_extra = re.sub(r"""\s+(and|or)\s+\)""", ")", non_extra)
    non_extra = re.sub(r"""\(\s+(and|or)\s+""", "(", non_extra)
    non_extra = re.sub(r"""^\s*(and|or)\s+""", "", non_extra)
    non_extra = re.sub(r"""\s+(and|or)\s*$""", "", non_extra)
    non_extra = re.sub(r"""\(\s*\)""", "", non_extra)
    non_extra = re.sub(r"""\s+""", " ", non_extra).strip()

    if not non_extra:
        return extras, None
    return extras, non_extra


def normalize_when_condition(marker: str) -> str:
    """Normalize selected PEP 508 marker variables to MatchSpec-like terms."""
    marker = PYTHON_VERSION_MARKER_RE.sub(r"python\1\3", marker)
    marker = PYTHON_FULL_VERSION_MARKER_RE.sub(r"python\1\3", marker)
    marker = PYTHON_VERSION_NOT_IN_RE.sub("", marker)

    def replace_platform_system(match: re.Match[str]) -> str:
        op = match.group(1)
        value = match.group(3).lower()

        if op == "==":
            return PLATFORM_SYSTEM_TO_VIRTUAL_PACKAGE.get(value, match.group(0))
        if op == "!=" and value == "windows":
            # Broadly matches Linux/macOS for channel test cases.
            return "__unix"
        return match.group(0)

    marker = PLATFORM_SYSTEM_MARKER_RE.sub(replace_platform_system, marker)

    def replace_sys_platform(match: re.Match[str]) -> str:
        op = match.group(1)
        value = match.group(3).lower()

        if op == "==" and value in SYS_PLATFORM_TO_VIRTUAL_PACKAGE:
            return SYS_PLATFORM_TO_VIRTUAL_PACKAGE[value]
        if op == "!=" and value in {"win32", "cygwin"}:
            return "__unix"
        if op == "!=" and value == "emscripten":
            # Emscripten is not a target platform in these channel tests.
            return ""
        return match.group(0)

    marker = SYS_PLATFORM_MARKER_RE.sub(replace_sys_platform, marker)

    def replace_os_name(match: re.Match[str]) -> str:
        op = match.group(1)
        value = match.group(3).lower()
        mapped = OS_NAME_TO_VIRTUAL_PACKAGE.get(value)
        if not mapped:
            return match.group(0)
        if op == "==":
            return mapped
        if op == "!=":
            if mapped == "__win":
                return "__unix"
            return "__win"
        return match.group(0)

    marker = OS_NAME_MARKER_RE.sub(replace_os_name, marker)

    def replace_impl_name(match: re.Match[str]) -> str:
        op = match.group(1)
        value = match.group(3).lower()
        if op == "==" and value in {"cpython", "pypy"}:
            return ""
        if op == "!=" and value in {"cpython", "pypy", "jython"}:
            return ""
        return match.group(0)

    marker = IMPL_NAME_MARKER_RE.sub(replace_impl_name, marker)
    marker = PLATFORM_PY_IMPL_MARKER_RE.sub(replace_impl_name, marker)
    marker = PLATFORM_MACHINE_MARKER_RE.sub("", marker)
    marker = CPYTHON_MARKER_RE.sub("", marker)
    marker = CPYTHON_NEGATION_MARKER_RE.sub("", marker)
    marker = PYPY_NEGATION_MARKER_RE.sub("", marker)
    marker = CYGWIN_NEGATION_MARKER_RE.sub("", marker)

    # Clean up dangling operators and parentheses produced by marker rewriting.
    previous = None
    while previous != marker:
        previous = marker
        marker = re.sub(r"""\band\s+and\b""", "and", marker)
        marker = re.sub(r"""\bor\s+or\b""", "or", marker)
        marker = re.sub(
            r"""\(\s*(__[a-z0-9_]+)\s+and\s+\(\s*\1\s*\)\s*\)""",
            r"\1",
            marker,
        )
        marker = re.sub(
            r"""\(\s*(__[a-z0-9_]+)\s+or\s+\(\s*\1\s*\)\s*\)""",
            r"\1",
            marker,
        )
        marker = re.sub(r"""\b(__[a-z0-9_]+)\s+and\s+\1\b""", r"\1", marker)
        marker = re.sub(r"""\b(__[a-z0-9_]+)\s+or\s+\1\b""", r"\1", marker)
        marker = re.sub(r"""\(\s*(and|or)\s+""", "(", marker)
        marker = re.sub(r"""\s+(and|or)\s*\)""", ")", marker)
        marker = re.sub(r"""^\s*(and|or)\s+""", "", marker)
        marker = re.sub(r"""^\s*(and|or)\s*$""", "", marker)
        marker = re.sub(r"""\s+(and|or)\s*$""", "", marker)
        marker = re.sub(r"""\(\s*\)""", "", marker)
        marker = re.sub(r"""\(\s*(__[a-z0-9_]+)\s*\)""", r"\1", marker)
        marker = re.sub(r"""\s+""", " ", marker).strip()

    return marker


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
            marker = str(req.marker)
            extra_names, non_extra_condition = split_marker_extras(marker)
            if extra_names:
                for extra_name in extra_names:
                    extra_dep = conda_dep
                    if non_extra_condition:
                        normalized_condition = normalize_when_condition(non_extra_condition)
                        if normalized_condition:
                            marker_condition = json.dumps(normalized_condition)
                            extra_dep = f"{extra_dep}[when={marker_condition}]"
                    extra_depends_dict.setdefault(extra_name, []).append(extra_dep)
            else:
                normalized_condition = normalize_when_condition(marker)
                if normalized_condition:
                    marker_condition = json.dumps(normalized_condition)
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
