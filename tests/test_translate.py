"""Tests for conda_pypi.translate module."""

import pytest
from conda.exceptions import ArgumentError

from conda_pypi import __version__
from conda_pypi.translate import (
    CondaMetadata,
    FileDistribution,
    requires_to_conda,
    validate_name_mapping_format,
)


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


def test_requires_to_conda_marker_without_extra_omitted_from_depends():
    """Wheel path matches main: non-extra PEP 508 markers are not added to depends."""
    requires, extras = requires_to_conda(
        ['typing-extensions>=4; python_version < "3.9"'],
    )
    assert not extras
    assert requires == []


def test_requires_to_conda_unmapped_dotted_name_preserves_dots():
    """Unmapped PyPI names with dots must not be turned into canonical hyphen form."""
    requires, extras = requires_to_conda(["jaraco.tidelift>=1"])
    assert not extras
    assert requires[0] == "jaraco.tidelift>=1"


def test_requires_to_conda_omits_pep508_dependency_extras_for_rattler():
    """PEP 508 optional dependency extras are omitted from depends (Rattler cannot parse them)."""
    requires, extras_map = requires_to_conda(
        ["httpx[cli,http2]>=0.24.0", 'requests[socks]>=2.0; extra == "dev"'],
    )
    assert requires == ["httpx>=0.24.0"]
    assert "dev" in extras_map
    assert extras_map["dev"] == ["requests>=2.0"]


def test_requires_to_conda_marker_extra_and_platform():
    """Extras go to extras map; platform markers are omitted from depends (no [when=…])."""
    requires, extras = requires_to_conda(
        [
            'requests>=2; extra == "dev"',
            'colorama>=0.4; sys_platform == "win32"',
        ],
    )
    assert "dev" in extras
    assert any(x.startswith("requests>=") for x in extras["dev"])
    assert requires == []


def _distribution(project_urls=(), description=None):
    """Build a FileDistribution with the given Project-URL labels."""
    header = [
        "Metadata-Version: 2.1\n",
        "Name: demo\n",
        "Version: 1.0.0\n",
        "Summary: short summary\n",
    ]
    if description is not None:
        header.append("Description: " + description.replace("\n", "\n        ") + "\n")
    urls = "".join(f"Project-URL: {label}, {url}\n" for label, url in project_urls)
    return FileDistribution("".join(header) + urls + "\n")


@pytest.mark.parametrize(
    ("label", "field", "url"),
    [
        ("Homepage", "home", "https://example.com/"),
        ("Home", "home", "https://example.com/"),
        ("HOMEPAGE", "home", "https://example.com/"),
        ("Source", "dev_url", "https://github.com/example/demo"),
        ("Repository", "dev_url", "https://github.com/example/demo"),
        ("Documentation", "doc_url", "https://demo.readthedocs.io"),
        ("Docs", "doc_url", "https://demo.readthedocs.io"),
    ],
)
def test_about_url_fields_from_project_url_labels(label, field, url):
    dist = _distribution(project_urls=[(label, url)])
    about = CondaMetadata.from_distribution(dist).about
    assert about[field] == url


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("Demo project.\n\n## Changelog\n\n- 1.0.0: initial release\n", "Demo project."),
        ("Demo project.\n# Heading\nMore text.\n", "Demo project."),
        ("Demo project.\nHeading\n---\nMore text.\n", "Demo project."),
        ("One line of prose.", "One line of prose."),
    ],
)
def test_about_description_is_shortened(description, expected):
    dist = _distribution(description=description)
    about = CondaMetadata.from_distribution(dist).about
    assert about["description"] == expected


def test_about_channels_recorded_when_passed():
    """Channels passed to from_distribution land in about.channels."""
    dist = _distribution()
    about = CondaMetadata.from_distribution(dist, channels=("conda-forge", "bioconda")).about
    assert about["channels"] == ["conda-forge", "bioconda"]


def test_about_channels_omitted_when_empty():
    """No channels means about.channels is absent (CEP 34 allows it)."""
    dist = _distribution()
    about = CondaMetadata.from_distribution(dist).about
    assert "channels" not in about


def test_about_extra_recipe_records_name_version_build():
    """about.extra.recipe carries name/version/build for provenance."""
    dist = _distribution()
    about = CondaMetadata.from_distribution(dist).about
    assert about["extra"]["recipe"]["name"] == "demo"
    assert about["extra"]["recipe"]["version"] == "1.0.0"
    assert about["extra"]["recipe"]["build"] == "pypi_0"


def test_about_extra_generator_records_conda_pypi_version():
    """about.extra.generator records 'conda-pypi' and its version."""
    dist = _distribution()
    about = CondaMetadata.from_distribution(dist).about
    assert about["extra"]["generator"] == "conda-pypi"
    assert about["extra"]["generator_version"] == __version__
