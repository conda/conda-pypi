"""
Conversion from PyPI metadata to repodata.json v3.whl entries.
"""

import sys
from datetime import datetime, timezone
from typing import Any

from packaging.requirements import Requirement

from conda_pypi.markers import (
    dependency_extras_suffix,
    dependency_when,
    extract_marker_condition_and_extras,
)
from conda_pypi.name_mapping import pypi_to_conda_name


def pypi_to_repodata(
    pypi_data: dict[str, Any],
    pypi_to_conda_name_mapping: dict | None = None,
) -> dict[str, Any] | None:
    """Convert PyPI JSON API payload to a repodata.json v3.whl entry for a pure-Python wheel.

    Dependency and record names use ``pypi_to_conda_name`` (same default table and
    unmapped-name fallback as :func:`conda_pypi.translate.requires_to_conda`).
    ``depends`` / ``extra_depends`` strings keep PEP 508 optional extras and specifier
    spelling. ``.whl`` → ``.conda`` conversion uses :func:`conda_dep_string_from_pep508_requirement`
    instead. This repodata path may emit ``[when=…]``, wheel conversion does not until conda has
    support for `[when="…"]` syntax in MatchSpec.
    """
    # Find a pure Python wheel (platform tag "none-any")
    for wheel_url in pypi_data.get("urls", []):
        if wheel_url.get("packagetype") != "bdist_wheel":
            continue
        if not wheel_url.get("filename", "").endswith("-none-any.whl"):
            continue
        # found valid wheel_url
        break
    else:
        # no wheel_url found
        return None

    pypi_info = pypi_data.get("info")

    depends_list: list[str] = []
    extra_depends_dict: dict[str, list[str]] = {}
    for dep in pypi_info.get("requires_dist") or []:
        req = Requirement(dep)
        req.name = pypi_to_conda_name(req.name, pypi_to_conda_name_mapping)
        # Preserve PEP 508 spelling (including optional dependency extras). Rattler-safe
        # normalization applies only to wheel → .conda :func:`conda_pypi.translate.requires_to_conda`.
        conda_dep = req.name + dependency_extras_suffix(req.extras) + str(req.specifier)

        non_extra_condition, extra_names = (
            extract_marker_condition_and_extras(req.marker) if req.marker else (None, [])
        )
        full_dep = dependency_when(conda_dep, non_extra_condition)

        if extra_names:
            for extra_name in extra_names:
                extra_depends_dict.setdefault(extra_name, []).append(full_dep)
        else:
            depends_list.append(full_dep)

    python_requires = pypi_info.get("requires_python")
    if python_requires:
        depends_list.append(f"python {python_requires}")
    else:
        # Noarch python packages should still depend on python when PyPI omits requires_python
        depends_list.append("python")

    # Build the repodata entry
    entry = {
        "url": wheel_url.get("url", ""),
        "name": pypi_to_conda_name(pypi_info.get("name") or "", pypi_to_conda_name_mapping),
        "version": pypi_info.get("version"),
        "build": "py3_none_any_0",
        "build_number": 0,
        "depends": depends_list,
        "extra_depends": extra_depends_dict,
        "fn": f"{pypi_info.get('name')}-{pypi_info.get('version')}-py3-none-any.whl",
        "sha256": wheel_url.get("digests", {}).get("sha256", ""),
        "size": wheel_url.get("size", 0),
        "subdir": "noarch",
        "timestamp": _upload_time_to_ms(wheel_url.get("upload_time")),
        "noarch": "python",
    }

    return entry


def _upload_time_to_ms(upload_time: str | None) -> int:
    """Convert a PyPI upload_time ISO string to Unix milliseconds."""
    if not upload_time:
        return 0
    if sys.version_info >= (3, 11):
        dt = datetime.fromisoformat(upload_time).replace(tzinfo=timezone.utc)
    else:
        dt = datetime.strptime(upload_time, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)
