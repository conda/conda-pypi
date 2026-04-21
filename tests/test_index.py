from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from conda_pypi.exceptions import UnableToConvertToRepodataEntry
from conda_pypi.index import store_pypi_metadata

HERE = Path(__file__).parent
PYPI_JSON_FIXTURES = HERE / "data" / "pypi_json"

if TYPE_CHECKING:
    from conda_index.index import ChannelIndex


def test_store_pypi_metadata(channel_index_with_wheels: ChannelIndex):
    cache = channel_index_with_wheels.cache_for_subdir("noarch")

    pypi_data = json.loads(
        (PYPI_JSON_FIXTURES / "fastapi-0.116.1.json").read_text(encoding="utf-8")
    )
    store_pypi_metadata(cache, pypi_data)

    # packages from database
    packages = cache.indexed_packages()

    assert len(packages.packages_whl) == 1
    assert "fastapi" in [pkg.get("name") for pkg in packages.packages_whl.values()]


def test_store_pypi_metadata_no_repodata(channel_index_with_wheels: ChannelIndex):
    """`pypi_to_repodata_noarch_whl_entry` may sometimes produce a `None` result.
    This test ensures that an appropriate error is raised."""
    pypi_data = {
        "urls": [
            {
                "packagetype": "bdist_wheel",
                "filename": "foo-1.0-cp312-cp312-manylinux_x86_64.whl",
                "url": "https://example.com/wheel.whl",
            }
        ],
        "info": {"name": "foo", "version": "1.0"},
    }
    cache = channel_index_with_wheels.cache_for_subdir("noarch")
    with pytest.raises(UnableToConvertToRepodataEntry):
        store_pypi_metadata(cache, pypi_data)


def test_store_pypi_metadata_no_sha256(channel_index_with_wheels: ChannelIndex):
    """Test that an error is raised if a repodata entry is missing it's sha256."""
    pypi_data = {
        "urls": [
            {
                "packagetype": "bdist_wheel",
                "filename": "foo-bar-1.0-py3-none-any.whl",
            }
        ],
        "info": {
            "name": "foo_bar",
            "version": "1.0",
        },
    }
    cache = channel_index_with_wheels.cache_for_subdir("noarch")

    with pytest.raises(ValueError, match="PyPI payload for 'foo-bar' is missing a sha256 digest"):
        store_pypi_metadata(cache, pypi_data)
