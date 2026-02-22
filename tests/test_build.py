from pathlib import Path
import json

from conda_package_streaming import package_streaming

from conda.testing.fixtures import TmpEnvFixture
from conda.common.path import get_python_short_path

from conda_pypi.build import build_conda


def _build_demo_conda_and_paths(
    tmp_env: TmpEnvFixture,
    pypi_demo_package_wheel_path: Path,
    tmp_path: Path,
):
    """Build demo package from wheel; return (target_package_path, paths_json)."""
    build_path = tmp_path / "build"
    build_path.mkdir()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    target_package_path = repo_path / "demo-package-0.1.0-pypi_0.conda"

    with tmp_env("python=3.12", "pip") as prefix:
        build_conda(
            pypi_demo_package_wheel_path,
            build_path,
            repo_path,
            Path(prefix, get_python_short_path()),
            is_editable=False,
        )

    paths_json = None
    for tar, member in package_streaming.stream_conda_info(target_package_path):
        if member.name == "info/paths.json":
            paths_json = json.load(tar.extractfile(member))
            break
    assert paths_json is not None
    return target_package_path, paths_json


def test_build_conda_package_paths_and_sha256_format(
    tmp_env: TmpEnvFixture,
    pypi_demo_package_wheel_path: Path,
    tmp_path: Path,
):
    """Ensure paths match package and no pyc, and paths.json sha256 is hex."""
    target_package_path, paths_json = _build_demo_conda_and_paths(
        tmp_env, pypi_demo_package_wheel_path, tmp_path
    )
    paths_json_paths = [p.get("_path") for p in paths_json.get("paths", [])]
    included_package_paths = {
        mm.name for _, mm in package_streaming.stream_conda_component(target_package_path)
    }

    # Paths in paths.json match package; no __pycache__ or .pyc
    missing = [p for p in paths_json_paths if p not in included_package_paths]
    assert not missing, f"paths.json paths not in package: {missing}"
    with_pycache = [p for p in paths_json_paths if "__pycache__" in p]
    assert not with_pycache, f"build_conda should not create __pycache__: {with_pycache}"
    with_pyc = [p for p in paths_json_paths if p.endswith(".pyc")]
    assert not with_pyc, f"build_conda should not create .pyc files: {with_pyc}"

    # Conda/solver expect sha256 in hex (not base64url from installer)
    def is_hex_64(s):
        return s and len(s) == 64 and all(c in "0123456789abcdef" for c in s.lower())

    bad = [
        (p.get("_path"), p.get("sha256"))
        for p in paths_json.get("paths", [])
        if p.get("sha256") and not is_hex_64(p["sha256"])
    ]
    assert not bad, f"path sha256 must be 64-char hex: {bad}"
