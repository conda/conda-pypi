"""
Test converting a dependency tree to conda.
"""

import json
import os
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from conda.models.match_spec import MatchSpec
from conda.testing.fixtures import TmpEnvFixture
from pytest_mock import MockerFixture

from conda_pypi.convert_tree import (
    ConvertTree,
    _format_conflict_line,
    parse_libmamba_solver_error,
    parse_rattler_solver_error,
)
from conda_pypi.downloader import get_package_finder
from conda_pypi.exceptions import CondaPypiError

REPO = Path(__file__).parents[1] / "synthetic_repo"


def test_multiple(tmp_env: TmpEnvFixture, tmp_path: Path, monkeypatch: MockerFixture):
    """
    Install multiple only-available-from-pypi dependencies into an environment.
    """
    CONDA_PKGS_DIRS = tmp_path / "conda-pkgs"
    CONDA_PKGS_DIRS.mkdir()

    WHEEL_DIR = tmp_path / "wheels"
    WHEEL_DIR.mkdir(exist_ok=True)

    REPO.mkdir(parents=True, exist_ok=True)

    TARGET_DEP = MatchSpec("twine==5.1.1")  # type: ignore

    # Defeat package cache for ConvertTree
    monkeypatch.setitem(os.environ, "CONDA_PKGS_DIRS", str(CONDA_PKGS_DIRS))

    with tmp_env("python=3.12", "pip") as prefix:
        converter = ConvertTree(prefix, repo=REPO, override_channels=True)
        converter.convert_tree([TARGET_DEP])


def test_convert_local_pypi_package(
    tmp_env: TmpEnvFixture,
    tmp_path: Path,
    monkeypatch: MockerFixture,
    pypi_local_index: str,
):
    """
    Convert a local pypi package
    """
    CONDA_PKGS_DIRS = tmp_path / "conda-pkgs"
    CONDA_PKGS_DIRS.mkdir()

    WHEEL_DIR = tmp_path / "wheels"
    WHEEL_DIR.mkdir(exist_ok=True)

    REPO.mkdir(parents=True, exist_ok=True)

    TARGET_DEP = MatchSpec("demo-package")  # type: ignore

    # Defeat package cache for ConvertTree
    monkeypatch.setitem(os.environ, "CONDA_PKGS_DIRS", str(CONDA_PKGS_DIRS))

    with tmp_env("python=3.12", "pip") as prefix:
        finder = get_package_finder(prefix, (pypi_local_index,))
        converter = ConvertTree(prefix, repo=REPO, override_channels=True, finder=finder)
        changes = converter.convert_tree([TARGET_DEP])

        assert len(changes[0]) == 0
        assert len(changes[1]) == 1
        assert changes[1][0].name == "demo-package"


def test_package_without_wheel_should_fail_early(
    tmp_env: TmpEnvFixture, tmp_path: Path, monkeypatch
):
    """
    Test that when a package has no wheel available, the convert_tree method
    raises CondaPypiError with a meaningful message rather than looping for max_attempts.

    This verifies the fix for issue #121.
    """
    CONDA_PKGS_DIRS = tmp_path / "conda-pkgs"
    CONDA_PKGS_DIRS.mkdir()

    REPO.mkdir(parents=True, exist_ok=True)

    # "ach" is mentioned in the issue as an example package that only has source distributions
    TARGET_PKG = MatchSpec("ach")  # type: ignore

    # Defeat package cache for ConvertTree
    monkeypatch.setitem(os.environ, "CONDA_PKGS_DIRS", str(CONDA_PKGS_DIRS))

    with tmp_env("python=3.12", "pip") as prefix:
        converter = ConvertTree(prefix, repo=REPO, override_channels=True)

        # Should raise CondaPypiError immediately instead of looping
        with pytest.raises(CondaPypiError) as exc_info:
            converter.convert_tree([TARGET_PKG], max_attempts=5)

        # Verify we get a meaningful error message
        error_msg = str(exc_info.value).lower()
        assert "wheel" in error_msg


def test_parse_libmamba_solver_error():
    error_message = "'Encountered problems while solving:\n  - nothing provides numpy <2.6,>=1.25.2 needed by scipy-1.16.3-pypi_0\n\nCould not solve for environment specs\nThe following package could not be installed\n└─ \x1b[31mscipy =* *\x1b[0m is not installable because it requires\n   └─ \x1b[31mnumpy <2.6,>=1.25.2 *\x1b[0m, which does not exist (perhaps a missing channel).'"
    assert set(parse_libmamba_solver_error(error_message)) == {"numpy <2.6,>=1.25.2"}


def test_parse_rattler_solver_error():
    error_message = "'Cannot solve the request because of: scipy * cannot be installed because there are no viable options:\n└─ scipy 1.16.3 would require\n   └─ numpy <2.6,>=1.25.2, for which no candidates were found.\n'"
    assert set(parse_rattler_solver_error(error_message)) == {"numpy <2.6,>=1.25.2"}


def test_format_conflict_line_exclusive_batch():
    line = _format_conflict_line(("utils", "pkg-a", "pkg-b", "exclusive"))
    assert "utils" in line
    assert "pkg-a" in line
    assert "pkg-b" in line
    assert "exclusively" in line


def test_format_conflict_line_exclusive_vs_namespace_batch():
    line = _format_conflict_line(("azure", "azure-mgmt-search", "pkg-b", "exclusive-vs-namespace"))
    assert "azure" in line
    assert "pkg-b" in line
    assert "azure-mgmt-search" in line
    assert "namespace" in line


def test_format_conflict_line_cross_install_exclusive():
    new_pkgs = {"pkg-b"}
    line = _format_conflict_line(("utils", "pkg-a", "pkg-b", "exclusive"), new_pkgs=new_pkgs)
    assert "pkg-b" in line
    assert "pkg-a" in line
    # pkg-b is incoming, pkg-a is already installed
    assert line.index("incoming") < line.index("pkg-b") or "incoming" in line
    assert "shadow" in line or "conflict" in line


def test_format_conflict_line_cross_install_exclusive_vs_namespace():
    new_pkgs = {"pkg-b"}
    line = _format_conflict_line(
        ("azure", "azure-mgmt-search", "pkg-b", "exclusive-vs-namespace"), new_pkgs=new_pkgs
    )
    assert "azure" in line
    assert "namespace" in line


def _make_wheel(
    tmp_path: Path,
    pkg_name: str,
    version: str = "1.0.0",
    import_names=None,
    import_namespaces=None,
) -> Path:
    lines = ["Metadata-Version: 2.5", f"Name: {pkg_name}", f"Version: {version}"]
    for n in import_names or []:
        lines.append(f"Import-Name: {n}")
    for ns in import_namespaces or []:
        lines.append(f"Import-Namespace: {ns}")
    normalized = pkg_name.replace("-", "_")
    dist_info = f"{normalized}-{version}.dist-info"
    wheel_path = tmp_path / f"{normalized}-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel_path, "w") as zf:
        zf.writestr(f"{dist_info}/METADATA", "\n".join(lines) + "\n")
        zf.writestr(
            f"{dist_info}/WHEEL",
            "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        )
        zf.writestr(f"{dist_info}/RECORD", "")
    return wheel_path


def _bare_convert_tree(prefix=None) -> ConvertTree:
    # Bypass __init__ so tests don't need a real conda prefix
    obj = object.__new__(ConvertTree)
    obj.prefix = Path(prefix or "/nonexistent")
    return obj


def test_collect_import_names_from_wheels_reads_metadata(tmp_path: Path):
    _make_wheel(tmp_path, "mylib", import_names=["mylib"])
    _make_wheel(
        tmp_path,
        "azure-mgmt-search",
        import_names=["azure.mgmt.search"],
        import_namespaces=["azure", "azure.mgmt"],
    )
    ct = _bare_convert_tree()
    names, namespaces = ct._collect_import_names_from_wheels(tmp_path)
    all_names = [name for name_list in names.values() for name in name_list]
    all_namespaces = [name for name_list in namespaces.values() for name in name_list]
    assert names["mylib"] == ["mylib"]
    assert "azure.mgmt.search" in all_names
    assert "azure" in all_namespaces
    assert "azure.mgmt" in all_namespaces


def test_collect_import_names_from_wheels_skips_wheel_without_pep794(tmp_path: Path):
    _make_wheel(tmp_path, "legacy-pkg")
    ct = _bare_convert_tree()
    names, namespaces = ct._collect_import_names_from_wheels(tmp_path)
    assert names == {}
    assert namespaces == {}


def test_collect_import_names_from_prefix_reads_about_json(tmp_path: Path, monkeypatch):
    epd = tmp_path / "pkg-cache"
    (epd / "info").mkdir(parents=True)
    (epd / "info" / "about.json").write_text(
        json.dumps({"import_names": ["mylib"], "import_namespaces": ["myns"]})
    )

    fake_record = MagicMock()
    fake_record.name = "mylib"
    fake_record.extracted_package_dir = str(epd)

    import conda.core.prefix_data as _pd_mod

    monkeypatch.setattr(
        _pd_mod, "PrefixData", lambda prefix: MagicMock(iter_records=lambda: iter([fake_record]))
    )

    ct = _bare_convert_tree(tmp_path)
    names, namespaces = ct._collect_import_names_from_prefix()
    assert names == {"mylib": ["mylib"]}
    assert namespaces == {"mylib": ["myns"]}


def test_check_import_name_conflicts_raises_on_batch_conflict(tmp_path: Path, monkeypatch):
    from conda.exceptions import CondaError

    ct = _bare_convert_tree()
    monkeypatch.setattr(
        ct,
        "_collect_import_names_from_wheels",
        lambda _: ({"pkg-a": ["utils"], "pkg-b": ["utils"]}, {}),
    )
    monkeypatch.setattr(ct, "_collect_import_names_from_prefix", lambda: ({}, {}))

    with pytest.raises(CondaError, match="Import name conflicts"):
        ct._check_import_name_conflicts(tmp_path)


def test_check_import_name_conflicts_warns_on_cross_install_conflict(
    tmp_path: Path, monkeypatch, caplog
):
    import logging

    ct = _bare_convert_tree()
    monkeypatch.setattr(
        ct, "_collect_import_names_from_wheels", lambda _: ({"pkg-new": ["utils"]}, {})
    )
    monkeypatch.setattr(
        ct, "_collect_import_names_from_prefix", lambda: ({"pkg-installed": ["utils"]}, {})
    )

    with caplog.at_level(logging.WARNING, logger="conda_pypi.convert_tree"):
        ct._check_import_name_conflicts(tmp_path)

    assert any(
        "overlap" in r.message.lower() or "conflict" in r.message.lower() for r in caplog.records
    )


def test_check_import_name_conflicts_no_false_conflict_on_update(tmp_path: Path, monkeypatch):
    # Updating a package means the same key appears in both prefix and incoming wheels.
    # The dict merge ({**installed, **new}) overwrites the old entry, so
    # check_import_name_conflicts only sees one entry and raises no conflict.
    ct = _bare_convert_tree()
    monkeypatch.setattr(
        ct, "_collect_import_names_from_wheels", lambda _: ({"python-dateutil": ["dateutil"]}, {})
    )
    monkeypatch.setattr(
        ct, "_collect_import_names_from_prefix", lambda: ({"python-dateutil": ["dateutil"]}, {})
    )
    ct._check_import_name_conflicts(tmp_path)


def test_check_import_name_conflicts_batch_conflicts_not_re_reported_as_cross(
    tmp_path: Path, monkeypatch, caplog
):
    # Batch conflicts (both packages are incoming) should raise immediately and
    # not also appear as cross-install warnings via the XOR filter.
    from conda.exceptions import CondaError

    ct = _bare_convert_tree()
    monkeypatch.setattr(
        ct,
        "_collect_import_names_from_wheels",
        lambda _: ({"pkg-a": ["utils"], "pkg-b": ["utils"]}, {}),
    )
    monkeypatch.setattr(ct, "_collect_import_names_from_prefix", lambda: ({}, {}))

    with pytest.raises(CondaError):
        ct._check_import_name_conflicts(tmp_path)
    assert not any("overlap" in r.message.lower() for r in caplog.records)
