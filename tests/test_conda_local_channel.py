"""
Tests for making sure the conda_local_channel fixture functions as we expect
"""

import urllib.request
import json


def test_conda_channel(conda_local_channel):
    """Verify the conda channel server is working."""
    url = f"{conda_local_channel}/noarch/repodata.json"
    with urllib.request.urlopen(url) as response:
        repodata = json.loads(response.read())

    assert "packages.whl" in repodata
    assert len(repodata["packages.whl"]) > 0
