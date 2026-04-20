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


def _license_file_lookup_paths(dist_info_resolved: Path, listed_path: Path) -> list[Path]:
    """
    Candidate paths for one ``License-File`` value (under this ``.dist-info`` only).

    Tries ``.dist-info/<path>`` then ``.dist-info/licenses/<path>`` so both flat
    layouts and PEP 639 ``licenses/`` trees work, including multi-segment paths
    like ``docs/NOTICE``. Does not look under ``site-packages`` (avoids picking
    another distribution's files).
    """
    return [
        dist_info_resolved / listed_path,
        dist_info_resolved / "licenses" / listed_path,
    ]


def copy_into_info_licenses(
    dist_info_dir: Path,
    info_dir: Path,
    metadata: PackageMetadata,
) -> list[str]:
    """
    Copy ``License-File`` payloads from an installed wheel into
    ``<info_dir>/licenses/`` (conda package ``info/``).

    Returns ``info/licenses/...`` paths relative to the package root (using
    ``/``), or an empty list if nothing resolved.
    """
    dist_resolved = dist_info_dir.resolve()
    resolved: list[tuple[Path, Path]] = []  # (source_path, listed_path)
    seen: set[Path] = set()
    for raw_line in metadata.get_all("License-File") or []:
        entry = raw_line.strip()
        if not entry:
            continue
        listed_path = Path(entry)
        if listed_path.is_absolute() or ".." in listed_path.parts:
            raise ValueError(f"License-File {str(listed_path)!r} contains unsafe path segments")
        for candidate in _license_file_lookup_paths(dist_resolved, listed_path):
            if not candidate.is_file():
                continue
            canonical = candidate.resolve()
            if canonical not in seen:
                seen.add(canonical)
                resolved.append((canonical, listed_path))
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

    rel_paths: list[str] = []
    for src, listed_path in resolved:
        dest = dest_dir / listed_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        # conda package paths use forward slashes on all platforms
        rel_paths.append(f"info/licenses/{listed_path.as_posix()}")

    return rel_paths
