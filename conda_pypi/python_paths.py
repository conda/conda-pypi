"""
Logic to place and find Python paths and EXTERNALLY-MANAGED in target (conda) environments.

Since functions in this module might be called to facilitate installation of the package,
this module MUST only use the Python stdlib. No 3rd party allowed (except for importlib-resources).
"""

import os
import sys
import sysconfig
from collections.abc import Iterator
from importlib.resources import files as importlib_files
from logging import getLogger
from pathlib import Path
from subprocess import check_output

on_win = sys.platform == "win32"


logger = getLogger(__name__)


def get_env_python(prefix: os.PathLike | None = None) -> Path:
    prefix = Path(prefix or sys.prefix)
    if on_win:
        return prefix / "python.exe"
    return prefix / "bin" / "python"


def _get_env_sysconfig_path(key: str, prefix: os.PathLike | None = None) -> Path:
    prefix = Path(prefix or sys.prefix)
    if str(prefix) == sys.prefix or prefix.resolve() == Path(sys.prefix).resolve():
        return Path(sysconfig.get_path(key))
    path = check_output(
        [get_env_python(prefix), "-c", f"import sysconfig as s; print(s.get_path('{key}'))"],
        text=True,
    ).strip()
    if not path:
        raise RuntimeError(f"Could not identify sysconfig path for '{key}' at '{prefix}'")
    return Path(path)


def get_env_stdlib(prefix: os.PathLike | None = None) -> Path:
    return _get_env_sysconfig_path("stdlib", prefix)


def get_env_site_packages(prefix: os.PathLike | None = None) -> Path:
    return _get_env_sysconfig_path("purelib", prefix)


def get_externally_managed_path(
    prefix: os.PathLike | None = None, python_version: str | None = None
) -> Path:
    """
    Returns the path for EXTERNALLY-MANAGED for the given Python installation in 'prefix'.
    Not guaranteed to exist.
    """
    prefix = Path(prefix or sys.prefix)

    # Get the Python version (either provided or from current Python)
    if python_version is None:
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"

    # Construct the path directly
    if on_win:
        return prefix / "Lib" / "EXTERNALLY-MANAGED"
    else:
        return prefix / "lib" / f"python{python_version}" / "EXTERNALLY-MANAGED"


def get_current_externally_managed_path(prefix: os.PathLike | None = None) -> Path:
    """
    Returns the path for EXTERNALLY-MANAGED for the given Python installation in 'prefix'.
    Not guaranteed to exist. There might be more EXTERNALLY-MANAGED files in 'prefix' for
    older Python versions. These are not returned.

    It assumes Python is installed in 'prefix' and will call it with a subprocess if needed.
    """
    prefix = Path(prefix or sys.prefix)
    return get_env_stdlib(prefix) / "EXTERNALLY-MANAGED"


def get_externally_managed_paths(prefix: os.PathLike | None = None) -> Iterator[Path]:
    """
    Returns all the possible EXTERNALLY-MANAGED paths in 'prefix', for all found
    Python (former) installations. The paths themselves are not guaranteed to exist.

    This does NOT invoke python's sysconfig because Python  might not be installed (anymore).
    """
    prefix = Path(prefix or sys.prefix)
    if on_win:
        yield prefix / "Lib" / "EXTERNALLY-MANAGED"
    else:
        for python_dir in sorted(Path(prefix, "lib").glob("python*")):
            if python_dir.is_dir():
                yield Path(python_dir, "EXTERNALLY-MANAGED")


def ensure_externally_managed(
    prefix: os.PathLike | None = None, python_version: str | None = None
) -> Path:
    """
    conda-pypi places its own EXTERNALLY-MANAGED file when it is installed in an environment.
    We also need to place it in _new_ environments created by conda. We do this by implementing
    some extra plugin hooks.
    """
    target_path = get_externally_managed_path(prefix, python_version)
    if not target_path.exists():
        logger.info("Placing EXTERNALLY-MANAGED in %s", target_path.parent)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        resource = importlib_files("conda_pypi") / "data" / "EXTERNALLY-MANAGED"
        target_path.write_text(resource.read_text())
    return target_path
