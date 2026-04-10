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
    Candidate paths for one ``License-File`` value.

    Checks ``.dist-info/<path>`` (pre-PEP 639 / legacy wheels), then
    ``.dist-info/licenses/<path>`` (PEP 639, Metadata-Version 2.4+).
    """
    return [
        dist_info_dir / listed_path,
        dist_info_dir / "licenses" / listed_path,
    ]


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
        else:
            log.warning("License-File '%s' declared in metadata but not found in %s", entry, dist_info_dir)

    if not resolved:
        return []

    dest_dir = info_dir / "licenses"
    dest_dir.mkdir(parents=True, exist_ok=True)

    def dest_name(src: Path) -> str:
        licenses_dir = dist_info_dir / "licenses"
        try:
            return str(src.resolve().relative_to(licenses_dir.resolve()))
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
