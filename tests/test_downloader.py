"""
Test handling of packages without wheels (source distributions only).

This test verifies issue #121: when a package has no wheel available (only source
distributions), the conversion should fail early with a meaningful error rather
than looping until max attempts (20).
"""

import os
from pathlib import Path

import pytest
from conda.testing.fixtures import TmpEnvFixture

from conda_pypi.exceptions import CondaPypiError

REPO = Path(__file__).parents[1] / "synthetic_repo"


def test_downloader_detects_no_wheels(tmp_env: TmpEnvFixture, monkeypatch, tmp_path: Path):
    """
    Test that the downloader correctly raises an error when no wheels are available.
    """
    import tempfile

    from conda_pypi.downloader import find_and_fetch, get_package_finder

    CONDA_PKGS_DIRS = tmp_path / "test-pkgs"
    CONDA_PKGS_DIRS.mkdir(exist_ok=True)
    monkeypatch.setitem(os.environ, "CONDA_PKGS_DIRS", str(CONDA_PKGS_DIRS))

    with tmp_env("python=3.12", "pip") as prefix:
        finder = get_package_finder(prefix)

        # Package "ach" only has source distributions
        with (
            pytest.raises(CondaPypiError) as exc_info,
            tempfile.TemporaryDirectory() as tmpdir,
        ):
            find_and_fetch(finder, Path(tmpdir), "ach")

        # Verify we get a meaningful error message
        error_msg = str(exc_info.value).lower()
        assert "wheel" in error_msg, f"Expected error message to mention 'wheel', got: {error_msg}"
        assert "source distributions" in error_msg or "only source" in error_msg, (
            f"Expected error message to mention source distributions, got: {error_msg}"
        )


@pytest.fixture
def conda_config(monkeypatch, tmp_path: Path):
    """
    Load conda's settings from a throwaway condarc only, then restore them.
    """
    from conda.base.context import reset_context

    def load(condarc: str = "") -> None:
        rc = tmp_path / "condarc"
        rc.write_text(condarc)
        for name in ("CONDA_SSL_VERIFY", "CONDA_CLIENT_SSL_CERT", "CONDA_CLIENT_SSL_CERT_KEY"):
            monkeypatch.delenv(name, raising=False)
        reset_context((str(rc),))

    yield load
    reset_context()


def test_pypi_client_defaults(conda_config):
    import ssl

    from conda_pypi.downloader import get_pypi_client_kwargs

    conda_config()
    kwargs = get_pypi_client_kwargs()

    assert kwargs["verify"].verify_mode == ssl.CERT_REQUIRED
    assert kwargs["mounts"] == {}
    assert kwargs["headers"]["User-Agent"].startswith("conda/")


def test_pypi_client_ssl_verify_false(conda_config):
    import ssl

    from conda_pypi.downloader import get_pypi_client_kwargs

    conda_config("ssl_verify: false\n")

    assert get_pypi_client_kwargs()["verify"].verify_mode == ssl.CERT_NONE


def test_pypi_client_ssl_verify_bundle_path(conda_config, monkeypatch, tmp_path: Path):
    import ssl

    from conda_pypi.downloader import get_ssl_context

    seen = {}

    def fake_create_default_context(**kwargs):
        seen.update(kwargs)
        return ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    monkeypatch.setattr(ssl, "create_default_context", fake_create_default_context)

    bundle = tmp_path / "custom-ca.pem"
    bundle.write_text("")
    conda_config(f"ssl_verify: {bundle}\n")
    get_ssl_context()
    assert seen == {"cafile": str(bundle)}

    seen.clear()
    conda_config(f"ssl_verify: {tmp_path}\n")
    get_ssl_context()
    assert seen == {"capath": str(tmp_path)}


def test_pypi_client_ssl_verify_truststore(conda_config):
    truststore = pytest.importorskip("truststore")

    from conda_pypi.downloader import get_ssl_context

    conda_config("ssl_verify: truststore\n")

    assert isinstance(get_ssl_context(), truststore.SSLContext)


def test_pypi_client_client_certificate(conda_config, monkeypatch, tmp_path: Path):
    import ssl

    from conda_pypi.downloader import get_ssl_context

    seen = []
    monkeypatch.setattr(
        ssl.SSLContext,
        "load_cert_chain",
        lambda self, certfile, keyfile=None, password=None: seen.append((certfile, keyfile)),
    )
    conda_config(
        f"client_ssl_cert: {tmp_path / 'client.pem'}\nclient_ssl_cert_key: {tmp_path / 'client.key'}\n",
    )
    get_ssl_context()

    assert seen == [(str(tmp_path / "client.pem"), str(tmp_path / "client.key"))]


def test_pypi_client_proxy_servers(conda_config):
    import httpx

    from conda_pypi.downloader import get_pypi_client_kwargs

    conda_config(
        "proxy_servers:\n"
        "  https: http://proxy.example.com:3128\n"
        "  http://internal.example.com: http://proxy2.example.com:3128\n",
    )
    mounts = get_pypi_client_kwargs()["mounts"]

    assert set(mounts) == {"https://", "http://internal.example.com"}
    assert all(isinstance(transport, httpx.HTTPTransport) for transport in mounts.values())


def test_package_finder_uses_conda_client(conda_config, monkeypatch, tmp_path: Path):
    from unearth.auth import MultiDomainBasicAuth
    from unearth.fetchers import PyPIClient

    from conda_pypi import downloader

    class FakeRecord:
        version = "3.12.1"

    class FakePrefixData:
        def __init__(self, prefix):
            pass

        def query(self, name):
            return [FakeRecord()]

    monkeypatch.setattr(downloader, "PrefixData", FakePrefixData)
    conda_config()
    finder = downloader.get_package_finder(tmp_path, ("https://example.com/simple/",))

    assert isinstance(finder.session, PyPIClient)
    assert isinstance(finder.session.auth, MultiDomainBasicAuth)
    assert finder.target_python.py_ver == (3, 12, 1)
