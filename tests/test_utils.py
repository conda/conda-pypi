"""Tests for the utils module."""

from __future__ import annotations

import base64

import hashlib

import pytest

from conda_pypi.utils import (
    hash_as_base64url,
    pypi_spec_variants,
    sha256_as_base64url,
    sha256_base64url_to_hex,
)


@pytest.mark.parametrize(
    "input_spec,expected_count",
    [
        ("setuptools-scm", 2),
        ("setuptools_scm", 2),
        ("numpy", 1),
        ("setuptools-scm>=1.0", 3),
        ("a-b_c", 3),
    ],
)
def test_pypi_spec_variants_generates_correct_count(input_spec: str, expected_count: int):
    """Test that pypi_spec_variants generates the expected number of variants."""
    variants = list(pypi_spec_variants(input_spec))
    assert len(variants) == expected_count
    assert len(variants) == len(set(variants))


def test_pypi_spec_variants_preserves_original():
    """Test that the original specification is always the first variant."""
    assert list(pypi_spec_variants("setuptools-scm"))[0] == "setuptools-scm"
    assert list(pypi_spec_variants("setuptools_scm"))[0] == "setuptools_scm"


def test_pypi_spec_variants_creates_name_variants():
    """Test that pypi_spec_variants creates hyphen/underscore variants."""
    variants = list(pypi_spec_variants("setuptools-scm"))
    assert "setuptools-scm" in variants
    assert "setuptools_scm" in variants


def test_hash_as_base64url_uses_specified_algorithm():
    """hash_as_base64url uses the given algorithm, not SHA-256."""
    data = b"hello"
    result = hash_as_base64url(data, "md5")
    expected = base64.urlsafe_b64encode(hashlib.md5(data).digest()).decode("ascii").rstrip("=")
    assert result == expected
    assert result != hash_as_base64url(data, "sha256")


def test_sha256_as_base64url_has_no_padding():
    """sha256_as_base64url returns base64url with no padding (PEP 376 RECORD)."""
    out = sha256_as_base64url(b"hello")
    assert "=" not in out


def test_sha256_base64url_to_hex_matches_digest_hex():
    """sha256_base64url_to_hex(base64url) equals the digest as hex."""
    data = b"hello"
    digest = hashlib.sha256(data).digest()

    base64url = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    assert sha256_base64url_to_hex(base64url) == digest.hex()


def test_sha256_base64url_to_hex_returns_64_hex_chars():
    """sha256_base64url_to_hex returns a 64-character hex string."""
    data = b"x"
    digest = hashlib.sha256(data).digest()

    base64url = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    hex_out = sha256_base64url_to_hex(base64url)
    assert hex_out is not None
    assert len(hex_out) == 64
    assert all(c in "0123456789abcdef" for c in hex_out)


@pytest.mark.parametrize("value", [None, "", "   "])
def test_sha256_base64url_to_hex_returns_none_for_falsy(value):
    """sha256_base64url_to_hex returns None for None or empty/whitespace string."""
    assert sha256_base64url_to_hex(value) is None


def test_sha256_base64url_to_hex_hex_acceptable_by_bytes_fromhex():
    """Hex from sha256_base64url_to_hex is valid for bytes.fromhex (conda solver)."""
    base64url = sha256_as_base64url(b"any content")
    hex_str = sha256_base64url_to_hex(base64url)
    assert hex_str is not None
    decoded = bytes.fromhex(hex_str)
    assert decoded == hashlib.sha256(b"any content").digest()
