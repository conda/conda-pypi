import sys
from pathlib import Path

HERE = Path(__file__).parent

PYPI_LOCAL_INDEX = HERE / "pypi_local_index"
CONDA_LOCAL_CHANNEL = HERE / "conda_local_channel"

# Use the same Python version as the test environment
PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"


def conda_drops_v3_records() -> bool:
    """Detect conda#16676, including in development and backport builds."""
    try:
        from conda._private.shards.shards import ShardLike
    except ImportError:
        return False

    repodata = {
        "repodata_version": 3,
        "v3": {"whl": {"demo_package-0.1.0-py3-none-any.whl": {"name": "demo-package"}}},
    }
    return "demo-package" not in ShardLike(repodata).shards
