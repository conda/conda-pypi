"""Tests for conda_pypi.translate module."""

import pytest
from conda.exceptions import ArgumentError

from conda_pypi.translate import validate_name_mapping_format


def test_validate_name_mapping_format_valid():
    """Test that valid mapping format passes validation."""
    valid_mapping = {
        "requests": {
            "pypi_name": "requests",
            "conda_name": "requests",
            "import_name": "requests",
            "mapping_source": "regro-bot",
        },
        "numpy": {
            "conda_name": "numpy",
        },
    }
    # Should not raise
    validate_name_mapping_format(valid_mapping)


def test_validate_name_mapping_format_empty():
    """Test that empty dict is allowed."""
    # Should not raise
    validate_name_mapping_format({})


def test_validate_name_mapping_format_not_dict():
    """Test that non-dict raises ArgumentError."""
    with pytest.raises(ArgumentError, match="must be a dictionary"):
        validate_name_mapping_format([])

    with pytest.raises(ArgumentError, match="must be a dictionary"):
        validate_name_mapping_format("not a dict")

    with pytest.raises(ArgumentError, match="must be a dictionary"):
        validate_name_mapping_format(None)

    # Test that objects without .items() method raise ArgumentError
    class NoItems:
        pass

    with pytest.raises(ArgumentError, match="must be a dictionary"):
        validate_name_mapping_format(NoItems())


def test_validate_name_mapping_format_non_string_key():
    """Test that non-string keys raise ArgumentError."""
    with pytest.raises(ArgumentError, match="keys must be strings"):
        validate_name_mapping_format({123: {"conda_name": "test"}})

    with pytest.raises(ArgumentError, match="keys must be strings"):
        validate_name_mapping_format({None: {"conda_name": "test"}})


def test_validate_name_mapping_format_non_dict_value():
    """Test that non-dict values raise ArgumentError."""
    with pytest.raises(ArgumentError, match="must be dictionaries"):
        validate_name_mapping_format({"requests": "not a dict"})

    with pytest.raises(ArgumentError, match="must be dictionaries"):
        validate_name_mapping_format({"requests": []})


def test_validate_name_mapping_format_missing_conda_name():
    """Test that missing conda_name key raises ArgumentError."""
    with pytest.raises(ArgumentError, match="missing required key 'conda_name'"):
        validate_name_mapping_format({"requests": {"pypi_name": "requests"}})

    with pytest.raises(ArgumentError, match="missing required key 'conda_name'"):
        validate_name_mapping_format({"requests": {}})


def test_validate_name_mapping_format_non_string_conda_name():
    """Test that non-string conda_name raises ArgumentError."""
    with pytest.raises(ArgumentError, match="invalid 'conda_name' type"):
        validate_name_mapping_format({"requests": {"conda_name": 123}})

    with pytest.raises(ArgumentError, match="invalid 'conda_name' type"):
        validate_name_mapping_format({"requests": {"conda_name": None}})

    with pytest.raises(ArgumentError, match="invalid 'conda_name' type"):
        validate_name_mapping_format({"requests": {"conda_name": []}})


def test_validate_name_mapping_format_multiple_errors():
    """Test that validation catches first error."""
    # First error: non-string key
    with pytest.raises(ArgumentError, match="keys must be strings"):
        validate_name_mapping_format(
            {123: {"conda_name": "test"}, "valid": {"conda_name": "test"}}
        )
