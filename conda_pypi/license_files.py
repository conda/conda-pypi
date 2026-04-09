"""
Copy wheel license files into conda package info/licenses/ (CEP 34).

Only ``License-File`` entries from METADATA (PEP 639) are used; wheels without
those lines get no ``info/licenses/`` content from this module.
"""

from __future__ import annotations

import shutil
from importlib.metadata import PackageMetadata
from pathlib import Path
from typing import Any


def _candidate_license_paths(dist_info: Path, rel: Path) -> list[Path]:
    """
    Map a ``License-File`` path from METADATA to possible on-disk locations.

    Wheels may ship payloads as ``.dist-info/<name>``, ``.dist-info/licenses/<name>``,
    or next to ``site-packages``.
    """
    dist_info = dist_info.resolve()
    out: list[Path] = [dist_info / rel]
    if len(rel.parts) == 1:
        out.append(dist_info / "licenses" / rel)
    out.append(dist_info.parent / rel)
    return out


def copy_licenses_into_info(
    dist_info: Path,
    info_dir: Path,
    metadata: PackageMetadata,
    about: dict[str, Any] | None = None,
) -> list[str]:
    """
    Copy files listed in ``License-File`` from the installed wheel's layout into
    ``info/licenses``. Optionally set ``about['license_file']`` to paths relative
    to the package root (``info/licenses/...``).

    Returns those relative paths; empty if no ``License-File`` entries resolve
    to existing files.
    """
    sources: list[Path] = []
    seen: set[Path] = set()
    for raw in metadata.get_all("License-File") or []:
        line = raw.strip()
        if not line:
            continue
        rel = Path(line)
        for cand in _candidate_license_paths(dist_info, rel):
            resolved = cand.resolve()
            if resolved.is_file() and resolved not in seen:
                seen.add(resolved)
                sources.append(resolved)
                break

    if not sources:
        return []

    dest_root = info_dir / "licenses"
    dest_root.mkdir(parents=True, exist_ok=True)

    def dest_name(src: Path) -> str:
        try:
            rel = src.resolve().relative_to(dist_info.resolve())
            return str(rel).replace("\\", "/").replace("/", "__")
        except ValueError:
            return src.name

    raw_names = [dest_name(s) for s in sources]
    counts: dict[str, int] = {}
    names: list[str] = []
    for r in raw_names:
        n = counts.get(r, 0)
        counts[r] = n + 1
        if n == 0:
            names.append(r)
        else:
            p = Path(r)
            names.append(f"{p.stem}__{n}{p.suffix}")

    rel_paths: list[str] = []
    for src, name in zip(sources, names, strict=True):
        dest = dest_root / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        rel_paths.append(f"info/licenses/{name}")

    if about is not None:
        about["license_file"] = rel_paths[0] if len(rel_paths) == 1 else rel_paths
    return rel_paths
