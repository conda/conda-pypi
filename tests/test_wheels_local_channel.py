import requests
from conda.testing.fixtures import TmpEnvFixture


def test_wheels_local_channel_repodata(wheels_local_channel):
    """Repodata is served and contains v3.whl entries."""
    resp = requests.get(f"{wheels_local_channel}/noarch/repodata.json")
    assert resp.status_code == 200
    data = resp.json()
    assert "v3" in data
    assert data["v3"]["whl"]


def test_wheels_local_channel_urls_are_local(wheels_local_channel):
    """All wheel URLs in repodata point back to the local server."""
    data = requests.get(f"{wheels_local_channel}/noarch/repodata.json").json()
    for name, entry in data["v3"]["whl"].items():
        assert entry["url"].startswith(wheels_local_channel), (
            f"{name} has non-local URL: {entry['url']}"
        )


def test_install_demo_package_from_wheels_local_channel(
    wheels_local_channel,
    with_rattler_solver,
    tmp_env: TmpEnvFixture,
    conda_cli,
):
    """
    Test that demo-package can be installed from the local wheel channel using Rattler.
    """
    with tmp_env("python=3.12") as prefix:
        _out, err, rc = conda_cli(
            "install",
            "demo-package",
            "--prefix",
            prefix,
            "--channel",
            wheels_local_channel,
            "--yes",
        )
        assert rc == 0, f"Failed to install from wheel channel: {err}"
        assert (prefix / "conda-meta").is_dir()
        records = list((prefix / "conda-meta").glob("demo-package-*.json"))
        assert records, "demo-package was not installed"
