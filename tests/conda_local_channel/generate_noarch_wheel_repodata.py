"""
Utility for generating test-specific local channel repodata.

Run this script to regenerate ``tests/conda_local_channel/noarch/repodata.json``
from the packages listed in ``wheel_packages.txt``. Not intended for production use.
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests

from conda_pypi.markers import pypi_to_repodata_noarch_whl_entry


def get_repodata_entry(name: str, version: str) -> dict[str, Any] | None:
    pypi_endpoint = f"https://pypi.org/pypi/{name}/{version}/json"
    pypi_data = requests.get(pypi_endpoint)
    if pypi_data.json() is None:
        raise Exception(f"unable to process {name} {version}")
    return pypi_to_repodata_noarch_whl_entry(pypi_data.json())


if __name__ == "__main__":
    from pathlib import Path

    HERE = Path(__file__).parent
    wheel_repodata = HERE / "noarch/repodata.json"

    pkg_whls = {}
    repodata_packages = []
    requested_wheel_packages_file = HERE / "wheel_packages.txt"
    with open(requested_wheel_packages_file) as f:
        pkgs_data = f.read()
        for pkg in pkgs_data.splitlines():
            repodata_packages.append(tuple(pkg.split("==")))

    # Run in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=25) as executor:
        # Map each package to its repodata entry
        futures = {
            executor.submit(get_repodata_entry, pkg_tuple[0], pkg_tuple[1]): pkg_tuple
            for pkg_tuple in repodata_packages
        }

        # Collect results as they complete
        for future in as_completed(futures):
            pkg_tuple = futures[future]
            name, version = pkg_tuple
            try:
                result = future.result()
                if result:
                    # Use the normalized name for the key
                    pkg_whls[f"{result['name']}-{version}-py3_none_any_0"] = result
            except Exception as e:
                print(f"Error processing {name} {version}: {e}")

    repodata_output = {
        "info": {"subdir": "noarch"},
        "packages": {},
        "packages.conda": {},
        "removed": [],
        "repodata_version": 3,
        "signatures": {},
        "v3": {"whl": {key: value for key, value in sorted(pkg_whls.items())}},
    }

    with open(wheel_repodata, "w") as f:
        json.dump(repodata_output, f, indent=4)
