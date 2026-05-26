"""Tests for conda_pypi.translate module."""

import pytest
from conda.exceptions import ArgumentError

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


# --- about.json improvements (issue #343) ---


def _distribution(**project_urls):
    """Build a FileDistribution with the given Project-URL labels."""
    header = "Metadata-Version: 2.1\nName: demo\nVersion: 1.0.0\nSummary: short summary\n"
    urls = "".join(f"Project-URL: {label}, {url}\n" for label, url in project_urls.items())
    return FileDistribution(header + urls + "\n")


def test_about_home_from_homepage_label():
    """`Homepage` (PEP 621) maps to about.home."""
    dist = _distribution(Homepage="https://example.com/")
    about = CondaMetadata.from_distribution(dist).about
    assert about["home"] == "https://example.com/"


def test_about_home_from_legacy_home_label():
    """Legacy `Home` label still maps to about.home."""
    dist = _distribution(Home="https://example.com/")
    about = CondaMetadata.from_distribution(dist).about
    assert about["home"] == "https://example.com/"


def test_about_home_label_is_case_insensitive():
    """Label lookup ignores case (`HOMEPAGE`, `homepage`, `Homepage` are equivalent)."""
    dist = _distribution(HOMEPAGE="https://example.com/")
    about = CondaMetadata.from_distribution(dist).about
    assert about["home"] == "https://example.com/"


def test_about_dev_url_from_source_label():
    """`Source` maps to about.dev_url."""
    dist = _distribution(Source="https://github.com/example/demo")
    about = CondaMetadata.from_distribution(dist).about
    assert about["dev_url"] == "https://github.com/example/demo"


def test_about_dev_url_from_repository_label():
    """`Repository` maps to about.dev_url."""
    dist = _distribution(Repository="https://github.com/example/demo")
    about = CondaMetadata.from_distribution(dist).about
    assert about["dev_url"] == "https://github.com/example/demo"


def test_about_doc_url_from_documentation_label():
    """`Documentation` maps to about.doc_url."""
    dist = _distribution(Documentation="https://demo.readthedocs.io")
    about = CondaMetadata.from_distribution(dist).about
    assert about["doc_url"] == "https://demo.readthedocs.io"


def test_about_doc_url_from_docs_label():
    """`Docs` (short form) maps to about.doc_url."""
    dist = _distribution(Docs="https://demo.readthedocs.io")
    about = CondaMetadata.from_distribution(dist).about
    assert about["doc_url"] == "https://demo.readthedocs.io"


def test_about_description_truncates_at_first_blank_line():
    """A multi-paragraph description is truncated to the first paragraph."""
    description = "Demo project.\n\n## Changelog\n\n- 1.0.0: initial release\n"
    dist = FileDistribution(
        "Metadata-Version: 2.1\n"
        "Name: demo\n"
        "Version: 1.0.0\n"
        "Description: " + description.replace("\n", "\n        ") + "\n"
    )
    about = CondaMetadata.from_distribution(dist).about
    assert about["description"] == "Demo project."


def test_about_description_truncates_at_markdown_heading():
    """A description with an inline Markdown heading stops at the heading."""
    description = "Demo project.\n# Heading\nMore text.\n"
    dist = FileDistribution(
        "Metadata-Version: 2.1\n"
        "Name: demo\n"
        "Version: 1.0.0\n"
        "Description: " + description.replace("\n", "\n        ") + "\n"
    )
    about = CondaMetadata.from_distribution(dist).about
    assert about["description"] == "Demo project."


def test_about_description_single_paragraph_unchanged():
    """A single-paragraph description survives truncation unchanged."""
    dist = FileDistribution(
        "Metadata-Version: 2.1\nName: demo\nVersion: 1.0.0\nDescription: One line of prose.\n"
    )
    about = CondaMetadata.from_distribution(dist).about
    assert about["description"] == "One line of prose."


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
    import conda_pypi

    dist = _distribution()
    about = CondaMetadata.from_distribution(dist).about
    assert about["extra"]["generator"] == "conda-pypi"
    assert about["extra"]["generator_version"] == conda_pypi.__version__
