"""Tests for conda_pypi.markers."""

import json

import pytest
from packaging.markers import Marker

from conda_pypi.markers import (
    extract_marker_condition_and_extras,
    pypi_to_repodata_noarch_whl_entry,
)


@pytest.mark.parametrize(
    ("marker_expr", "expected_condition", "expected_extras"),
    [
        ('extra == "docs"', None, ["docs"]),
        ('python_version < "3.11"', "python<3.11", []),
        ('python_full_version < "3.11.0"', "python<3.11.0", []),
        (
            'python_version not in "3.0, 3.1"',
            "(python!=3.0 and python!=3.1)",
            [],
        ),
        ('sys_platform == "win32"', "__win", []),
        ('sys_platform == "linux"', "__linux", []),
        ('platform_system == "darwin"', "__osx", []),
        ('os_name == "nt"', "__win", []),
        ('os_name == "posix"', "__unix", []),
        ('sys_platform != "win32"', "__unix", []),
        (
            'python_version < "3.11" and extra == "test"',
            "python<3.11",
            ["test"],
        ),
        ('implementation_name == "cpython"', None, []),
        ('platform_machine == "x86_64"', None, []),
        (
            'extra == "socks" or extra == "socks"',
            None,
            ["socks"],
        ),
    ],
)
def test_extract_marker_condition_and_extras(marker_expr, expected_condition, expected_extras):
    condition, extras = extract_marker_condition_and_extras(Marker(marker_expr))
    assert condition == expected_condition
    assert extras == expected_extras


def test_extract_marker_combines_or_platforms():
    """Both sides contribute when neither operand is absorbed as None-only."""
    condition, extras = extract_marker_condition_and_extras(
        Marker('sys_platform == "linux" or sys_platform == "darwin"')
    )
    assert extras == []
    assert condition is not None
    assert "__linux" in condition
    assert "__osx" in condition
    assert " or " in condition


def test_pypi_to_repodata_noarch_whl_entry_requires_none_any_wheel():
    pypi_data = {
        "urls": [
            {
                "packagetype": "bdist_wheel",
                "filename": "foo-1.0-cp312-cp312-manylinux_x86_64.whl",
                "url": "https://example.com/wheel.whl",
            }
        ],
        "info": {"name": "foo", "version": "1.0"},
    }
    assert pypi_to_repodata_noarch_whl_entry(pypi_data) is None


def test_pypi_to_repodata_includes_pep508_dependency_extras():
    pypi_data = {
        "urls": [
            {
                "packagetype": "bdist_wheel",
                "filename": "parent-1-py3-none-any.whl",
                "url": "",
                "digests": {},
                "size": 0,
            }
        ],
        "info": {
            "name": "parent",
            "version": "1",
            "requires_dist": ["httpx[cli]>=0.24"],
        },
    }
    entry = pypi_to_repodata_noarch_whl_entry(pypi_data)
    assert entry is not None
    assert any("httpx[cli]>=" in d for d in entry["depends"])


def test_pypi_to_repodata_noarch_whl_entry_minimal():
    pypi_data = {
        "urls": [
            {
                "packagetype": "bdist_wheel",
                "filename": "foo-bar-1.0-py3-none-any.whl",
                "url": "https://files.pythonhosted.org/foo.whl",
                "digests": {"sha256": "abc"},
                "size": 42,
                "upload_time": "2024-12-06T15:37:21",
            }
        ],
        "info": {
            "name": "foo_bar",
            "version": "1.0",
            "requires_dist": [
                'typing-extensions>=4; python_version < "3.9"',
                'colorama>=0.4.4; sys_platform == "win32"',
                'PySocks>=1.5.6,!=1.5.7; extra == "socks"',
            ],
            "requires_python": ">=3.8",
        },
    }
    entry = pypi_to_repodata_noarch_whl_entry(pypi_data)
    assert entry is not None
    assert entry["name"] == "foo-bar"
    assert entry["version"] == "1.0"
    assert entry["subdir"] == "noarch"
    assert entry["noarch"] == "python"
    assert entry["fn"] == "foo_bar-1.0-py3-none-any.whl"
    assert entry["timestamp"] == 1733499441000

    assert any(d.startswith("python >=") for d in entry["depends"])
    te_dep = next(d for d in entry["depends"] if d.startswith("typing_extensions"))
    assert '[when="python<3.9"]' in te_dep
    colorama_dep = next(d for d in entry["depends"] if d.startswith("colorama"))
    assert '[when="__win"]' in colorama_dep

    socks = entry["extra_depends"]["socks"]
    assert len(socks) == 1
    assert socks[0].startswith("pysocks")


def test_pypi_to_repodata_timestamp_missing_upload_time():
    pypi_data = {
        "urls": [
            {
                "packagetype": "bdist_wheel",
                "filename": "foo-1.0-py3-none-any.whl",
                "url": "https://files.pythonhosted.org/foo.whl",
                "digests": {"sha256": "abc"},
                "size": 42,
            }
        ],
        "info": {"name": "foo", "version": "1.0"},
    }
    entry = pypi_to_repodata_noarch_whl_entry(pypi_data)
    assert entry is not None
    assert entry["timestamp"] == 0


def test_pypi_to_repodata_appends_python_when_requires_python_missing():
    pypi_data = {
        "urls": [
            {
                "packagetype": "bdist_wheel",
                "filename": "solo-2.0-py3-none-any.whl",
                "url": "https://example.com/solo.whl",
                "digests": {},
                "size": 1,
            }
        ],
        "info": {"name": "solo", "version": "2.0", "requires_dist": []},
    }
    entry = pypi_to_repodata_noarch_whl_entry(pypi_data)
    assert entry is not None
    assert entry["depends"] == ["python"]


def test_pypi_to_repodata_when_condition_json_encoded():
    """When value must be safe inside MatchSpec metadata, condition is JSON-encoded."""
    pypi_data = {
        "urls": [
            {
                "packagetype": "bdist_wheel",
                "filename": "x-1-py3-none-any.whl",
                "url": "",
                "digests": {},
                "size": 0,
            }
        ],
        "info": {
            "name": "x",
            "version": "1",
            "requires_dist": ['y; python_version < "3.11"'],
        },
    }
    entry = pypi_to_repodata_noarch_whl_entry(pypi_data)
    assert entry is not None
    dep = entry["depends"][0]
    prefix, when_part = dep.split("[when=", 1)
    assert prefix.startswith("y")
    when_inner = when_part.rstrip("]")
    # json.loads verifies quoting matches json.dumps in markers.py
    assert json.loads(when_inner) == "python<3.11"
