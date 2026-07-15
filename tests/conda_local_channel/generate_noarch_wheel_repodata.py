"""
Utility for generating test-specific local channel repodata.

Run this script to regenerate ``tests/conda_local_channel/noarch/repodata.json``
from the packages listed in ``wheel_packages.txt``. Not intended for production use.
"""

import logging
from typing import Any

import requests
from conda_index.index import BaseCondaIndexCache, ChannelIndex
from conda_index.utils import CONDA_PACKAGE_EXTENSIONS

from conda_pypi.exceptions import UnableToConvertToRepodataEntry
from conda_pypi.index import store_pypi_metadata

log = logging.getLogger(__name__)


def cache_repodata_entry(
    cache: BaseCondaIndexCache, name: str, version: str
) -> dict[str, Any] | None:
    pypi_endpoint = f"https://pypi.org/pypi/{name}/{version}/json"
    pypi_data = requests.get(pypi_endpoint)
    if pypi_data.json() is None:
        log.error(f"unable to process {name} {version}, no data found at {pypi_endpoint}")
        return None
    try:
        return store_pypi_metadata(cache, pypi_data.json())
    except UnableToConvertToRepodataEntry:
        log.error(
            f"unable to process {name} {version}, unable to convert pypi metadata to a repodata entry"
        )
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)

    from pathlib import Path

    HERE = Path(__file__).parent

    repodata_packages = []
    requested_wheel_packages_file = HERE / "wheel_packages.txt"
    with open(requested_wheel_packages_file) as f:
        pkgs_data = f.read()
        for pkg in pkgs_data.splitlines():
            repodata_packages.append(tuple(pkg.split("==")))

    channel_index = ChannelIndex(
        HERE,
        None,
        threads=1,
        write_zst=False,
        compact_json=False,
        write_current_repodata=False,
        repodata_v3=True,
        update_only=True,
        save_fs_state=False,
        cache_kwargs={
            "package_extensions": CONDA_PACKAGE_EXTENSIONS + (".whl",),
            "include_stages": ["md"],
        },
    )
    cache = channel_index.cache_for_subdir("noarch")

    md_entries = []
    for pkg_tuple in repodata_packages:
        entry = cache_repodata_entry(cache, pkg_tuple[0], pkg_tuple[1])
        if entry is not None:
            md_entries.append(entry)

    cache.store_stat_state("md", md_entries)

    channel_index.index(patch_generator=None)
