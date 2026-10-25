"""
Fetch matching wheels from pypi.
"""

import atexit
import logging
import ssl
from collections.abc import Iterable
from pathlib import Path

import httpx
from conda.base.context import context
from conda.core.prefix_data import PrefixData
from conda.gateways.connection.download import download
from conda.models.match_spec import MatchSpec
from unearth import PackageFinder, TargetPython  # noqa: TID253
from unearth.auth import MultiDomainBasicAuth  # noqa: TID253
from unearth.fetchers import PyPIClient  # noqa: TID253

from conda_pypi.exceptions import CondaPypiError
from conda_pypi.translate import conda_to_requires

log = logging.getLogger(__name__)

DEFAULT_INDEX_URLS = ("https://pypi.org/simple/",)


def get_ssl_context() -> ssl.SSLContext:
    """
    An SSL context which follows conda's ``ssl_verify``, ``client_ssl_cert``, and
    ``client_ssl_cert_key`` settings in the same manner as ``CondaSession``.
    """
    ssl_verify = context.ssl_verify
    if ssl_verify == "truststore":
        try:
            import truststore
        except ImportError:
            raise CondaPypiError(
                "The `ssl_verify: truststore` setting requires the `truststore` "
                "package to be installed."
            )
        ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    elif isinstance(ssl_verify, str):
        if Path(ssl_verify).is_dir():
            ssl_context = ssl.create_default_context(capath=ssl_verify)
        else:
            ssl_context = ssl.create_default_context(cafile=ssl_verify)
    else:
        ssl_context = httpx.create_ssl_context(verify=ssl_verify)

    if context.client_ssl_cert:
        ssl_context.load_cert_chain(context.client_ssl_cert, context.client_ssl_cert_key or None)
    return ssl_context


def get_pypi_client_kwargs() -> dict:
    """
    Keyword arguments for ``PyPIClient``, that follow the settings for conda's
    sessions, for TLS verification, client certificates, proxy servers, timeouts,
    and user agents.
    """
    ssl_context = get_ssl_context()
    mounts = {}
    for key, proxy in context.proxy_servers.items():
        pattern = key if "://" in key else f"{key}://"
        mounts[pattern] = httpx.HTTPTransport(proxy=proxy, verify=ssl_context)
    return {
        "verify": ssl_context,
        "mounts": mounts,
        "headers": {"User-Agent": context.user_agent},
        "timeout": httpx.Timeout(
            context.remote_read_timeout_secs,
            connect=context.remote_connect_timeout_secs,
        ),
    }


def get_pypi_client(index_urls: Iterable[str]) -> PyPIClient:
    """
    An HTTP client for index lookups, configured according to conda's session.
    """
    client = PyPIClient(**get_pypi_client_kwargs())
    client.auth = MultiDomainBasicAuth(index_urls=index_urls)
    atexit.register(client.close)
    return client


def get_package_finder(
    prefix: Path,
    index_urls: Iterable[str] = DEFAULT_INDEX_URLS,
) -> PackageFinder:
    """
    Finder with prefix's Python, not our Python.
    """
    prefix_data = PrefixData(prefix)
    python_records = list(prefix_data.query("python"))
    if not python_records:
        raise CondaPypiError(f"Python not found in {prefix}")
    py_ver = python_records[0].version
    py_ver = tuple(map(int, py_ver.split(".")))
    target_python = TargetPython(py_ver=py_ver)
    index_urls = tuple(index_urls)
    return PackageFinder(
        session=get_pypi_client(index_urls),  # type: ignore # unearth's Fetcher protocol does not match httpx.Client
        target_python=target_python,
        only_binary=":all:",
        index_urls=index_urls,
    )


def find_package(finder: PackageFinder, package: str):
    """
    Convert :package: to `MatchSpec`; return best `Link`.
    """
    spec = MatchSpec(package)  # type: ignore # metaclass confuses type checker
    requirement = conda_to_requires(spec)
    if not requirement:
        raise RuntimeError(f"Could not convert {package} to Python Requirement()!")
    return finder.find_best_match(requirement)


def find_and_fetch(finder: PackageFinder, target: Path, package: str) -> Path:
    """
    Find package on PyPI, download best link to target.
    """
    result = find_package(finder, package)
    link = result.best and result.best.link
    if not link:
        raise CondaPypiError(f"No PyPI link for {package}")

    # Check if the file is a wheel (.whl)
    filename = link.url_without_fragment.rsplit("/", 1)[-1]
    if not filename.endswith(".whl"):
        raise CondaPypiError(
            f"No wheel file available for {package}. "
            f"Only source distributions are available. "
            f"conda-pypi requires wheel files for conversion."
        )

    log.info(f"Fetch {package} as {filename}")
    target_path = target / filename
    download(link.url, target_path)
    return target_path
