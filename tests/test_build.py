from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from conda.common.path import get_python_short_path
from conda.testing.fixtures import TmpEnvFixture
from conda_package_streaming import package_streaming

from conda_pypi import dependencies
from conda_pypi.build import build_conda, build_pypa, pypa_to_conda
from conda_pypi.package_extractors.whl import extract_whl_as_conda_pkg


@pytest.fixture
def local_build_project(
    tmp_path: Path,
    pypi_demo_package_wheel_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[list[str], list[str]], Path]:
    def forbid_install(*args: object, **kwargs: object) -> None:
        pytest.fail("Build unexpectedly tried to install dependencies")

    monkeypatch.setattr(dependencies, "ensure_requirements", forbid_install)

    def create(build_system: list[str], backend: list[str]) -> Path:
        project = tmp_path / "project"
        project.mkdir()
        (project / "pyproject.toml").write_text(
            f"[build-system]\nrequires = {build_system!r}\n"
            'build-backend = "backend"\nbackend-path = ["."]\n',
            encoding="utf-8",
        )
        (project / "backend.py").write_text(
            "import shutil\nfrom pathlib import Path\n"
            "def get_requires_for_build_wheel(config_settings=None):\n"
            f"    return {backend!r}\n"
            "def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):\n"
            f"    source = Path({str(pypi_demo_package_wheel_path)!r})\n"
            "    shutil.copyfile(source, Path(wheel_directory) / source.name)\n"
            "    return source.name\n"
            "get_requires_for_build_editable = get_requires_for_build_wheel\n"
            "build_editable = build_wheel\n",
            encoding="utf-8",
        )
        return project

    return create


@pytest.mark.parametrize("build_function", [build_pypa, pypa_to_conda])
@pytest.mark.parametrize("phase", ["build-system", "backend", "build-package"])
@pytest.mark.parametrize(
    "distribution_options", [{"distribution": "wheel"}, {}], ids=["wheel", "editable-default"]
)
def test_local_build_rejects_missing_dependencies_without_installing(
    local_build_project: Callable[[list[str], list[str]], Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    build_function: Callable[..., str | Path],
    phase: str,
    distribution_options: dict[str, str],
) -> None:
    missing = "missing-build-dependency>=1"
    project = local_build_project(
        [missing] if phase == "build-system" else [],
        [missing] if phase == "backend" else [],
    )
    if phase == "build-package":
        missing = "build"

        def cannot_check(*args: object, **kwargs: object) -> None:
            raise dependencies.MissingDependencyError([missing])

        monkeypatch.setattr(dependencies, "check_dependencies", cannot_check)

    with pytest.raises(dependencies.MissingDependencyError) as exc:
        build_function(
            project,
            output_path=tmp_path / "output",
            prefix=Path(sys.prefix),
            install_build_dependencies=False,
            **distribution_options,
        )
    assert exc.value.dependencies == [missing]


@pytest.mark.parametrize("build_function", [build_pypa, pypa_to_conda])
@pytest.mark.parametrize(
    "options", [{}, {"install_build_dependencies": False}], ids=["default", "preinstalled-only"]
)
@pytest.mark.parametrize(
    "distribution_options", [{"distribution": "wheel"}, {}], ids=["wheel", "editable-default"]
)
def test_local_build_uses_preinstalled_dependencies(
    local_build_project: Callable[[list[str], list[str]], Path],
    tmp_path: Path,
    build_function: Callable[..., str | Path],
    options: dict[str, bool],
    distribution_options: dict[str, str],
) -> None:
    project = local_build_project(["packaging"], ["build"])
    output = tmp_path / "output"
    output.mkdir()
    package = build_function(
        project,
        output_path=output,
        prefix=Path(sys.prefix),
        **options,
        **distribution_options,
    )
    assert Path(package).is_file()


def _build_demo_conda_and_paths(
    tmp_env: TmpEnvFixture,
    pypi_demo_package_wheel_path: Path,
    tmp_path: Path,
):
    """Build demo package from wheel and return (target_package_path, paths_json)."""
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

    # Paths in paths.json match package. No __pycache__ or .pyc.
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


def test_build_conda_copies_licenses_to_info_licenses(
    tmp_env: TmpEnvFixture,
    pypi_license_file_wheel_path: Path,
    tmp_path: Path,
):
    """License files from .dist-info are copied to info/licenses."""
    build_path = tmp_path / "build"
    build_path.mkdir()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    out_conda = repo_path / "lwt-0.0.1-pypi_0.conda"

    with tmp_env("python=3.12", "pip") as prefix:
        build_conda(
            pypi_license_file_wheel_path,
            build_path,
            repo_path,
            Path(prefix, get_python_short_path()),
            is_editable=False,
        )

    assert out_conda.is_file()

    info_names = {mm.name for _, mm in package_streaming.stream_conda_info(out_conda)}
    assert "info/licenses/LICENSE" in info_names

    about = None
    lic_payload = None
    for tar, member in package_streaming.stream_conda_info(out_conda):
        if member.name == "info/about.json":
            about = json.load(tar.extractfile(member))
        elif member.name == "info/licenses/LICENSE":
            lic_payload = tar.extractfile(member).read()
    assert about is not None
    assert "license_file" not in about
    assert lic_payload == b"BSD-3-Clause placeholder license text\n"


def test_build_conda_records_channels_in_about_json(
    tmp_env: TmpEnvFixture,
    pypi_demo_package_wheel_path: Path,
    tmp_path: Path,
):
    """Channels passed to build_conda are recorded in info/about.json (#343)."""
    build_path = tmp_path / "build"
    build_path.mkdir()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    target = repo_path / "demo-package-0.1.0-pypi_0.conda"

    with tmp_env("python=3.12", "pip") as prefix:
        build_conda(
            pypi_demo_package_wheel_path,
            build_path,
            repo_path,
            Path(prefix, get_python_short_path()),
            is_editable=False,
            channels=("conda-forge", "bioconda"),
        )

    about = None
    for tar, member in package_streaming.stream_conda_info(target):
        if member.name == "info/about.json":
            about = json.load(tar.extractfile(member))
            break
    assert about is not None
    assert about["channels"] == ["conda-forge", "bioconda"]
    assert about["extra"]["generator"] == "conda-pypi"
    assert about["extra"]["recipe"]["name"] == "demo-package"
    assert about["extra"]["recipe"]["build"] == "pypi_0"


def test_build_conda_members_stay_in_info_component(
    pypi_demo_package_wheel_path: Path,
    tmp_path: Path,
):
    build_path = tmp_path / "build"
    build_path.mkdir()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    out_conda = repo_path / "demo-package-0.1.0-pypi_0.conda"

    build_conda(
        pypi_demo_package_wheel_path,
        build_path,
        repo_path,
        sys.executable,
        is_editable=False,
    )

    assert out_conda.is_file()

    pkg_names = {member.name for _, member in package_streaming.stream_conda_component(out_conda)}
    info_names = {member.name for _, member in package_streaming.stream_conda_info(out_conda)}

    assert "/" not in pkg_names
    assert "/" not in info_names
    assert "info/" not in pkg_names
    assert "info/" not in info_names
    assert not any(name.startswith("info/") for name in pkg_names)

    # True for our test demo_package but not universally true. Meant to catch
    # user's homedir or /tmp/ sneaking into pkg_names:
    assert all(name.startswith("site-packages") for name in pkg_names)


def test_conda_package_conforms_to_cep_34_35(
    tmp_env: TmpEnvFixture,
    pypi_demo_package_wheel_path: Path,
    tmp_path: Path,
):
    """Validate package conforms to CEP 34 (contents) and CEP 35 (file format).

    CEP 35 MUST requirements tested:
    - info-* tarball MUST contain the full info/ folder
    - pkg-* tarball MUST carry everything else
    - Root level of tarballs MUST match target location (no intermediate subdirectories)

    CEP 34 MUST requirements tested:
    - Package MUST include info/index.json and info/paths.json
    - info/paths.json MUST NOT list contents of info/ folder
    - conda-meta/ MUST NOT be present
    - info/repodata_record.json MUST NOT be present
    """
    target_package_path, paths_json = _build_demo_conda_and_paths(
        tmp_env, pypi_demo_package_wheel_path, tmp_path
    )

    # Collect all entries from both archives
    info_entries = [m.name for _, m in package_streaming.stream_conda_info(target_package_path)]
    pkg_entries = [
        m.name for _, m in package_streaming.stream_conda_component(target_package_path)
    ]

    # === CEP 35: Archive structure requirements ===

    # "info-* tarball MUST contain the full info/ folder"
    # All info archive entries must start with 'info/'
    invalid_info = [e for e in info_entries if not e.startswith("info/")]
    assert not invalid_info, (
        f"CEP 35 violation: info archive has entries not under info/: {invalid_info}"
    )

    # "pkg-* tarball MUST carry everything else"
    # No pkg entries should be info/ content
    misplaced_info = [e for e in pkg_entries if e.startswith("info/")]
    assert not misplaced_info, f"CEP 35 violation: pkg archive has info/ entries: {misplaced_info}"

    # "Root level MUST match target location (no intermediate subdirectories)"
    # No absolute paths (leading /) or empty strings representing root
    all_entries = info_entries + pkg_entries
    invalid_roots = [e for e in all_entries if e.startswith("/") or e == ""]
    assert not invalid_roots, (
        f"CEP 35 violation: archive has intermediate subdirectories or absolute paths: {invalid_roots}"
    )

    # === CEP 34: Package contents requirements ===

    # "Package MUST include info/index.json and info/paths.json"
    assert "info/index.json" in info_entries, "CEP 34 violation: info/index.json missing"
    assert "info/paths.json" in info_entries, "CEP 34 violation: info/paths.json missing"

    # "info/paths.json MUST NOT list contents of info/ folder"
    paths_in_paths_json = [p["_path"] for p in paths_json.get("paths", [])]
    info_in_paths = [p for p in paths_in_paths_json if p.startswith("info/") or p == "info"]
    assert not info_in_paths, (
        f"CEP 34 violation: info/paths.json lists info/ contents: {info_in_paths}"
    )

    # "conda-meta/ directory MUST NOT be populated by conda packages"
    conda_meta = [e for e in all_entries if e.startswith("conda-meta/") or e == "conda-meta"]
    assert not conda_meta, f"CEP 34 violation: package contains conda-meta/: {conda_meta}"

    # "info/repodata_record.json MUST NOT be present in distributed artifacts"
    assert "info/repodata_record.json" not in info_entries, (
        "CEP 34 violation: info/repodata_record.json must not be in distributed artifacts"
    )


def test_extract_whl_copies_licenses_to_info_licenses(
    pypi_license_file_wheel_path: Path,
    tmp_path: Path,
):
    """Wheel extractor also populates info/licenses (no about.json in this layout)."""
    dest = tmp_path / "pkg"
    dest.mkdir()
    extract_whl_as_conda_pkg(pypi_license_file_wheel_path, dest)
    lic = dest / "info" / "licenses" / "LICENSE"
    assert lic.is_file()
    assert lic.read_bytes() == b"BSD-3-Clause placeholder license text\n"
