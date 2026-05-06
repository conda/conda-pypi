"""Tests for conda_pypi.pypi_metadata."""

import json

from conda_pypi.pypi_metadata import pypi_to_repodata


def test_pypi_to_repodata_requires_none_any_wheel():
    pypi_data = {
        "urls": [
            {
                "packagetype": "bdist_wheel",
                "filename": "numpy-2.2.5-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
                "url": "https://files.pythonhosted.org/packages/numpy-2.2.5-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
            }
        ],
        "info": {"name": "numpy", "version": "2.2.5"},
    }
    assert pypi_to_repodata(pypi_data) is None


def test_pypi_to_repodata_includes_pep508_dependency_extras():
    pypi_data = {
        "urls": [
            {
                "packagetype": "bdist_wheel",
                "filename": "certifi-2026.4.22-py3-none-any.whl",
                "url": "https://files.pythonhosted.org/packages/certifi-2026.4.22-py3-none-any.whl",
                "digests": {},
                "size": 0,
            }
        ],
        "info": {
            "name": "certifi",
            "version": "2026.4.22",
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
                "filename": "importlib_metadata-9.0.0-py3-none-any.whl",
                "url": "https://files.pythonhosted.org/packages/38/3d/2d244233ac4f76e38533cfcb2991c9eb4c7bf688ae0a036d30725b8faafe/importlib_metadata-9.0.0-py3-none-any.whl",
                "digests": {
                    "sha256": "2d21d1cc5a017bd0559e36150c21c830ab1dc304dedd1b7ea85d20f45ef3edd7"
                },
                "size": 27789,
                "upload_time": "2026-03-20T06:42:55",
            }
        ],
        "info": {
            "name": "importlib-metadata",
            "version": "9.0.0",
            "requires_dist": [
                "zipp>=3.20",
                'pytest!=8.1.*,>=6; extra == "test"',
                'packaging; extra == "test"',
                'sphinx>=3.5; extra == "doc"',
            ],
            "requires_python": ">=3.10",
        },
    }
    entry = pypi_to_repodata(pypi_data)
    assert entry is not None
    assert entry["name"] == "importlib-metadata"
    assert entry["version"] == "9.0.0"
    assert entry["subdir"] == "noarch"
    assert entry["noarch"] == "python"
    assert entry["fn"] == "importlib_metadata-9.0.0-py3-none-any.whl"
    assert entry["sha256"] == "2d21d1cc5a017bd0559e36150c21c830ab1dc304dedd1b7ea85d20f45ef3edd7"
    assert entry["size"] == 27789
    assert entry["timestamp"] == 1773988975000
    assert (
        entry["url"]
        == "https://files.pythonhosted.org/packages/38/3d/2d244233ac4f76e38533cfcb2991c9eb4c7bf688ae0a036d30725b8faafe/importlib_metadata-9.0.0-py3-none-any.whl"
    )

    assert "zipp>=3.20" in entry["depends"]
    assert any(d.startswith("python >=3.10") for d in entry["depends"])

    test_extra = entry["extra_depends"]["test"]
    assert any(d.startswith("pytest") for d in test_extra)
    assert any(d.startswith("packaging") for d in test_extra)


def test_pypi_to_repodata_timestamp_missing_upload_time():
    pypi_data = {
        "urls": [
            {
                "packagetype": "bdist_wheel",
                "filename": "certifi-2026.4.22-py3-none-any.whl",
                "url": "https://files.pythonhosted.org/packages/certifi-2026.4.22-py3-none-any.whl",
                "digests": {"sha256": "abc"},
                "size": 42,
            }
        ],
        "info": {"name": "certifi", "version": "2026.4.22"},
    }
    entry = pypi_to_repodata(pypi_data)
    assert entry is not None
    assert entry["timestamp"] == 0


def test_pypi_to_repodata_appends_python_when_requires_python_missing():
    pypi_data = {
        "urls": [
            {
                "packagetype": "bdist_wheel",
                "filename": "pytz-2026.2-py2.py3-none-any.whl",
                "url": "https://files.pythonhosted.org/packages/pytz-2026.2-py2.py3-none-any.whl",
                "digests": {},
                "size": 1,
            }
        ],
        "info": {"name": "pytz", "version": "2026.2", "requires_dist": []},
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
                "filename": "build-1.5.0-py3-none-any.whl",
                "url": "https://files.pythonhosted.org/packages/build-1.5.0-py3-none-any.whl",
                "digests": {},
                "size": 0,
            }
        ],
        "info": {
            "name": "build",
            "version": "1.5.0",
            "requires_dist": ['tomli>=1.1.0; python_version < "3.11"'],
        },
    }
    entry = pypi_to_repodata(pypi_data)
    assert entry is not None
    dep = next(d for d in entry["depends"] if d.startswith("tomli"))
    prefix, when_part = dep.split("[when=", 1)
    assert prefix.startswith("tomli")
    when_inner = when_part.rstrip("]")
    # json.loads verifies quoting matches json.dumps in markers.py
    assert json.loads(when_inner) == "python<3.11"
