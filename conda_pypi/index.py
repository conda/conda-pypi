"""
Interface to conda-index.
"""

from typing import Any

from conda_index.index import ChannelIndex
from conda_index.index.cache import BaseCondaIndexCache

from .exceptions import UnableToConvertToRepodataEntry
from .markers import pypi_to_repodata_noarch_whl_entry


def update_index(path):
    channel_index = ChannelIndex(
        path,
        None,
        threads=1,
        debug=False,
        write_bz2=False,
        write_zst=True,
        write_run_exports=True,
        compact_json=True,
        write_current_repodata=False,
    )
    channel_index.index(patch_generator=None)
    channel_index.update_channeldata()


def store_pypi_metadata(cache: BaseCondaIndexCache, pypi_json: dict[str, Any]):
    """Convert and cache a single pypi package as a conda repodata entry.

    Starting in conda-index 0.11.0, conda index can output repodata v3, including
    wheel packages.

    This function takes the output from the PyPI API and converts it to a conda repodata entry.
    For example,

    ```
    def cache_repodata_entry(cache: BaseCondaIndexCache, name: str, version: str) -> dict[str, Any] | None:
        pypi_endpoint = f"https://pypi.org/pypi/{name}/{version}/json"
        pypi_data = requests.get(pypi_endpoint)
        if pypi_data.json() is None:
            raise Exception(f"unable to process {name} {version}")
        store_pypi_metadata(cache, pypi_data.json())
    ```
    """
    repodata_entry = pypi_to_repodata_noarch_whl_entry(pypi_json)
    if repodata_entry is None:
        raise UnableToConvertToRepodataEntry(
            "Unable to find a pure python wheel and convert it to a repodata entry"
        )
    path = f"{repodata_entry['name']}-{repodata_entry['version']}-py3_none_any_0.whl"

    cache.store_fs_state(
        [
            {
                "path": cache.database_path(path),
                "size": repodata_entry["size"],
                "mtime": repodata_entry.get("timestamp", 1),
            }
        ]
    )

    # must contain sha256 and md5 keys but values may be None
    if not repodata_entry.get("sha256"):
        raise ValueError(
            f"PyPI payload for {repodata_entry.get('name')!r} is missing a sha256 digest"
        )
    repodata_entry.setdefault("md5", None)

    cache.store(
        fn=path,
        size=repodata_entry["size"],
        mtime=repodata_entry.get("timestamp", 0),
        members={},
        index_json=repodata_entry,
    )
