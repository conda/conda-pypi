"""
Round trip a wheel through an explicit export.

See https://github.com/conda/conda-pypi/issues/527
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from conda.testing.fixtures import CondaCLIFixture

PACKAGE = "demo_package"


def _list_record(conda_cli: CondaCLIFixture, prefix: Path) -> dict:
    out, _, _ = conda_cli("list", "--prefix", str(prefix), "--json")
    return next(record for record in json.loads(out) if record["name"] == PACKAGE)


def _assert_conda_managed_noarch(record: dict) -> None:
    assert record["platform"] == "noarch"
    assert record["build_string"] == "py3_none_any_0"
    # Records with no python dependency get picked up by conda's site-packages
    # loader and shown as pypi_0/pypi instead.
    assert record["channel"] != "pypi"


def test_explicit_export_round_trip_keeps_wheel_record_fields(
    conda_cli: CondaCLIFixture,
    python_template_env: Path,
    pypi_demo_package_wheel_path: Path,
    tmp_path: Path,
):
    source = tmp_path / "source"
    conda_cli("create", "--clone", str(python_template_env), "--prefix", str(source), "--yes")
    conda_cli("install", "--prefix", str(source), "--yes", str(pypi_demo_package_wheel_path))
    _assert_conda_managed_noarch(_list_record(conda_cli, source))

    explicit = tmp_path / "explicit.txt"
    conda_cli("export", "--prefix", str(source), "--format", "explicit", "--file", str(explicit))
    assert pypi_demo_package_wheel_path.name in explicit.read_text()

    restored = tmp_path / "restored"
    conda_cli("create", "--prefix", str(restored), "--yes", "--file", str(explicit))
    _assert_conda_managed_noarch(_list_record(conda_cli, restored))

    (meta_path,) = (restored / "conda-meta").glob(f"{PACKAGE}-0.1.0-*.json")
    meta = json.loads(meta_path.read_text())
    assert meta["subdir"] == "noarch"
    assert meta["noarch"] == "python"
    assert meta["depends"] == ["python >=3.6"]
