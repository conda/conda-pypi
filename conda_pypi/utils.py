from __future__ import annotations

import base64
import hashlib
import os
import sys

from logging import getLogger
from pathlib import Path
from typing import Iterator

from conda.base.context import context, locate_prefix_by_name
from conda.models.match_spec import MatchSpec


logger = getLogger(f"conda.{__name__}")


def hash_as_base64url(data: bytes, algorithm: str = "sha256") -> str:
    """Digest as PEP 376 RECORD style base64url (no padding)."""
    return (
        base64.urlsafe_b64encode(hashlib.new(algorithm, data).digest()).decode("ascii").rstrip("=")
    )


def sha256_as_base64url(data: bytes) -> str:
    """SHA256 digest as PEP 376 RECORD style base64url (no padding)."""
    return hash_as_base64url(data)


def sha256_base64url_to_hex(value: str | None) -> str | None:
    """Convert base64url hash (e.g. from installer) to hex for conda paths.json."""
    if not value or not value.strip():
        return None
    try:
        value = value.strip()
        # Ensure value is padded to a multiple of 4 since installer strips padding
        value += "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(value).hex()
    except ValueError:
        return None


def get_prefix(prefix: os.PathLike = None, name: str = None) -> Path:
    if prefix:
        return Path(prefix)
    elif name:
        return Path(locate_prefix_by_name(name))
    else:
        return Path(context.target_prefix)


def pypi_spec_variants(spec_str: str) -> Iterator[str]:
    yield spec_str
    spec = MatchSpec(spec_str)
    seen = {spec_str}
    for name_variant in (
        spec.name.replace("-", "_"),
        spec.name.replace("_", "-"),
    ):
        if name_variant not in seen:  # only yield if actually different
            yield str(MatchSpec(spec, name=name_variant))
            seen.add(name_variant)


class SuppressOutput:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout
