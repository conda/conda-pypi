"""Tests for conda_pypi.pypi_metadata."""

import json

from conda_pypi.pypi_metadata import pypi_to_repodata


def test_pypi_to_repodata_requires_none_any_wheel():
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
    assert pypi_to_repodata(pypi_data) is None


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
    entry = pypi_to_repodata(pypi_data)
    assert entry is not None
    assert any("httpx[cli]>=" in d for d in entry["depends"])


def test_pypi_to_repodata_entry_minimal():
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
    entry = pypi_to_repodata(pypi_data)
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
    entry = pypi_to_repodata(pypi_data)
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
    entry = pypi_to_repodata(pypi_data)
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
    entry = pypi_to_repodata(pypi_data)
    assert entry is not None
    dep = entry["depends"][0]
    prefix, when_part = dep.split("[when=", 1)
    assert prefix.startswith("y")
    when_inner = when_part.rstrip("]")
    # json.loads verifies quoting matches json.dumps in markers.py
    assert json.loads(when_inner) == "python<3.11"
