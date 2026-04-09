"""
Copy wheel license files into conda package info/licenses/ (CEP 34).

Only ``License-File`` entries from METADATA (PEP 639) are used. Wheels without
those lines get no ``info/licenses/`` content from this module.
"""

from __future__ import annotations

import shutil
from importlib.metadata import PackageMetadata
from pathlib import Path
from typing import Any


def _license_file_lookup_paths(dist_info_dir: Path, listed_path: Path) -> list[Path]:
    """
    Paths to try for one ``License-File`` value: ``.dist-info/<path>``, then (if
    ``listed_path`` is a single segment) ``.dist-info/licenses/<name>``, then
    ``site-packages/<path>`` via the parent of ``.dist-info``.
    """
    dist_info_dir = dist_info_dir.resolve()
    candidates: list[Path] = [dist_info_dir / listed_path]
    if len(listed_path.parts) == 1:
        candidates.append(dist_info_dir / "licenses" / listed_path)
    candidates.append(dist_info_dir.parent / listed_path)
    return candidates


def copy_into_info_licenses(
    dist_info_dir: Path,
    info_dir: Path,
    metadata: PackageMetadata,
    about: dict[str, Any] | None = None,
) -> list[str]:
    """
    Copy ``License-File`` payloads from an installed wheel into
    ``<info_dir>/licenses/`` (conda package ``info/``). Optionally set
    ``about['license_file']`` to ``info/licenses/...`` paths.

    Returns those relative paths, or an empty list if nothing resolved.
    """
    resolved: list[Path] = []
    seen: set[Path] = set()
    for raw_line in metadata.get_all("License-File") or []:
        entry = raw_line.strip()
        if not entry:
            continue
        listed_path = Path(entry)
        for candidate in _license_file_lookup_paths(dist_info_dir, listed_path):
            path = candidate.resolve()
            if path.is_file() and path not in seen:
                seen.add(path)
                resolved.append(path)
                break

    if not resolved:
        return []

    dest_dir = info_dir / "licenses"
    dest_dir.mkdir(parents=True, exist_ok=True)

    def flatten_name(src: Path) -> str:
        try:
            rel = src.resolve().relative_to(dist_info_dir.resolve())
            return str(rel).replace("\\", "/").replace("/", "__")
        except ValueError:
            return src.name

    flat_names = [flatten_name(f) for f in resolved]
    counts: dict[str, int] = {}
    dest_names: list[str] = []
    for flat in flat_names:
        n = counts.get(flat, 0)
        counts[flat] = n + 1
        if n == 0:
            dest_names.append(flat)
        else:
            p = Path(flat)
            dest_names.append(f"{p.stem}__{n}{p.suffix}")

    rel_paths: list[str] = []
    for src, name in zip(resolved, dest_names, strict=True):
        dest = dest_dir / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        rel_paths.append(f"info/licenses/{name}")

    if about is not None:
        about["license_file"] = rel_paths[0] if len(rel_paths) == 1 else rel_paths
    return rel_paths
