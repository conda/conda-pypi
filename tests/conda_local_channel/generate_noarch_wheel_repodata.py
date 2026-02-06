# This is a utility for generating test specific data in conda-pypi
# only. It is not appropriate to use this to generate production level
# repodata.

import requests
import json
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed


def pypi_to_repodata_whl_entry(
    pypi_data: Dict[str, Any], url_index: int = 0
) -> Optional[Dict[str, Any]]:
    """
    Convert PyPI JSON endpoint data to a repodata.json packages.whl entry.

    Args:
        pypi_info: Dictionary containing the complete info section from PyPI JSON endpoint
        url_index: Index of the wheel URL to use (typically the first one is the wheel)

    Returns:
        Dictionary representing the entry for packages.whl, or None if wheel not found
    """
    # Find the wheel URL (bdist_wheel package type)
    wheel_url = None

    # import pdb; pdb.set_trace()
    for url_entry in pypi_data.get("urls", []):
        if url_entry.get("packagetype") == "bdist_wheel":
            wheel_url = url_entry
            break

    if not wheel_url:
        return None

    pypi_info = pypi_data.get("info")

    depends_list = []
    for dep in pypi_info.get("requires_dist") or []:
        if "extra" not in dep:
            depends_list.append(dep.split(";")[0])
    depends_list.append(f"python {pypi_info.get('requires_python')}")

    # Build the repodata entry
    entry = {
        "url": wheel_url.get("url", ""),
        "record_version": 3,
        "name": pypi_info.get("name"),
        "version": pypi_info.get("version"),
        "build": "py3_none_any_0",
        "build_number": 0,
        "depends": depends_list,
        "fn": f"{pypi_info.get('name')}-{pypi_info.get('version')}-py3-none-any.whl",
        "sha256": wheel_url.get("digests", {}).get("sha256", ""),
        "size": wheel_url.get("size", 0),
        "subdir": "noarch",
        # "timestamp": wheel_url.get("upload_time", 0),
        "noarch": "python",
    }

    return entry


def get_repodata_entry(name: str, version: str):
    pypi_endpoint = f"https://pypi.org/pypi/{name}/{version}/json"
    pypi_data = requests.get(pypi_endpoint)
    if pypi_data.json() is None:
        raise Exception(f"unable to process {name} {version}")
    return pypi_to_repodata_whl_entry(pypi_data.json())


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
                    pkg_whls[f"{name}-{version}-py3_none_any_0"] = result
            except Exception as e:
                print(f"Error processing {name} {version}: {e}")

    repodata_output = {
        "info": {"subdir": "noarch"},
        "packages": {},
        "packages.conda": {},
        "removed": [],
        "repodata_version": 1,
        "signatures": {},
        "packages.whl": {key: value for key, value in sorted(pkg_whls.items())},
    }

    with open(wheel_repodata, "w") as f:
        json.dump(repodata_output, f, indent=4)
