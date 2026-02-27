"""
Tests for making sure the conda_local_channel fixture functions as we expect
"""

import json
import urllib.request
from pathlib import Path

from conda.exceptions import DryRunExit

HERE = Path(__file__).parent


def test_conda_channel(conda_local_channel):
    """Verify the conda channel server is working."""
    url = f"{conda_local_channel}/noarch/repodata.json"
    with urllib.request.urlopen(url) as response:
        repodata = json.loads(response.read())

    assert "packages.whl" in repodata
    assert len(repodata["packages.whl"]) > 0


def test_conda_channel_extras_in_repodata():
    """Verify that wheel entries with extras are present in the repodata."""
    repodata = json.loads((HERE / "conda_local_channel" / "noarch" / "repodata.json").read_text())

    record = repodata["packages.whl"]["requests-2.32.5-py3_none_any_0"]
    assert "extras" in record
    assert record["extras"]["socks"] == ["pysocks >=1.5.6,!=1.5.7"]


def test_conda_install_with_extras_resolves_extra_deps(
    tmp_path,
    conda_cli,
    conda_local_channel,
):
    """Installing requests[socks] should pull pysocks into the solved set."""
    out, err, rc = conda_cli(
        "create",
        "--prefix",
        str(tmp_path / "env"),
        "--channel",
        str(conda_local_channel),
        "--dry-run",
        "--json",
        "requests[socks]",
        raises=DryRunExit,
    )
    out_json = json.loads(out)
    assert out_json["success"]
    package_names = {pkg["name"] for pkg in out_json.get("actions", {}).get("LINK", [])}
    assert "requests" in package_names
    assert "pysocks" in package_names
