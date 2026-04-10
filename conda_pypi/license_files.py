"""
Copy wheel license files into conda package info/licenses/ (CEP 34).

Only ``License-File`` entries from METADATA (PEP 639) are used. Wheels without
those lines get no ``info/licenses/`` content from this module.
"""

from __future__ import annotations

import logging
import shutil
from importlib.metadata import Distribution, PackageMetadata
from pathlib import Path

log = logging.getLogger(__name__)


class _MetadataBodyDistribution(Distribution):
    """Minimal :class:`~importlib.metadata.Distribution` backed by METADATA text only (no disk)."""

    __slots__ = ("_text",)

    def __init__(self, text: str) -> None:
        self._text = text

    def read_text(self, filename: str) -> str | None:
        if filename == "METADATA":
            return self._text
        return None

    def locate_file(self, path):  # noqa: ARG002
        return None


def package_metadata_from_metadata_body(body: str) -> PackageMetadata:
    """
    Parse core metadata from the body of a ``METADATA`` file without reading
    from the filesystem (e.g. ``WheelFile.read_dist_info('METADATA')``).
    """
    return _MetadataBodyDistribution(body).metadata


def _license_file_lookup_paths(dist_info_dir: Path, listed_path: Path) -> list[Path]:
    """
    Candidate paths for one ``License-File`` value.

    Order: ``.dist-info/<path>``, then (single segment only)
    ``.dist-info/licenses/<name>`` (many PEP 639 wheels, e.g. PyPI ``packaging``),
    then ``site-packages/<path>`` via the parent of ``.dist-info``.
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
) -> list[str]:
    """
    Copy ``License-File`` payloads from an installed wheel into
    ``<info_dir>/licenses/`` (conda package ``info/``).

    Returns ``info/licenses/...`` paths relative to the package root, or an
    empty list if nothing resolved.
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
            log.warning(
                "License-File %r declared in metadata but not found under %s",
                entry,
                dist_info_dir,
            )

    if not resolved:
        return []

    dest_dir = info_dir / "licenses"
    dest_dir.mkdir(parents=True, exist_ok=True)

    def flatten_under_dist_info(src: Path) -> str:
        try:
            rel = src.resolve().relative_to(dist_info_dir.resolve())
            return str(rel).replace("\\", "/").replace("/", "__")
        except ValueError:
            return src.name

    flat_names = [flatten_under_dist_info(f) for f in resolved]
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

    return rel_paths
