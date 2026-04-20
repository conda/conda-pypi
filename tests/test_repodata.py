"""
Test functions for transforming repodata.
"""

import tempfile
from importlib.metadata import PathDistribution
from pathlib import Path

from conda_pypi.translate import (
    CondaMetadata,
    FileDistribution,
    MatchSpec,
    conda_to_requires,
    pypi_to_conda_name,
    remap_match_spec_name,
)


def test_file_distribution():
    dist = FileDistribution(
        """\
Metadata-Version: 2.1
Name: conda_pypi
Version: 0.0.1
"""
    )
    metadata = dist.read_text("METADATA") or ""
    assert "conda_pypi" in metadata
    assert dist.read_text("missing") is None
    assert dist.locate_file("always None") is None


def test_translate_twine():
    requirement = conda_to_requires(MatchSpec("twine==6.0.0"))
    assert requirement.name == "twine"


def test_conda_to_requires_remaps_names():
    requirement = conda_to_requires(MatchSpec("typing_extensions"))
    assert requirement.name == "typing-extensions"


def test_conda_to_requires_formats_exact_versions():
    requirement = conda_to_requires(MatchSpec("twine=6.0.0"))
    assert str(requirement) == "twine==6.0.0"


def test_remap_matchspec_name_noop_for_unmapped():
    spec = MatchSpec("requests")
    remapped = remap_match_spec_name(spec, pypi_to_conda_name)
    assert remapped == spec


def test_remap_matchspec_name_maps_when_needed():
    spec = MatchSpec("typing-extensions")
    remapped = remap_match_spec_name(spec, pypi_to_conda_name)
    assert remapped.name == "typing_extensions"


def test_pypi_to_conda_name_with_hyphens():
    """Test that PyPI names are translated using the grayskull mapping.

    The function uses a curated mapping from the grayskull project.
    Packages in the mapping get their conda name, others keep their PyPI name.
    """
    assert pypi_to_conda_name("huggingface-hub") == "huggingface_hub"
    assert pypi_to_conda_name("typing-extensions") == "typing_extensions"
    assert pypi_to_conda_name("scikit-learn") == "scikit-learn"

    # conda-forge dot names: unmapped fallback preserves dots (not PEP 503 canonical)
    assert pypi_to_conda_name("jaraco.tidelift") == "jaraco.tidelift"
    assert pypi_to_conda_name("jaraco.path") == "jaraco.path"
    # If the only spelling available is already canonical, dots cannot be recovered
    assert pypi_to_conda_name("jaraco-tidelift") == "jaraco-tidelift"

    # Unmapped: lowercase, _ → -, otherwise unchanged spelling (minus strip)
    assert pypi_to_conda_name("unknown-package") == "unknown-package"
    assert pypi_to_conda_name("Some_Unknown.Dot") == "some-unknown.dot"


def test_metadata_fields_never_none():
    """Test that metadata fields are always strings, never None.

    This prevents conda-index from failing with:
    'Could not _clear_newline_chars from field description'
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        dist_info = Path(tmpdir) / "test-1.0.0.dist-info"
        dist_info.mkdir()

        # Create METADATA without optional fields
        metadata_content = """\
Metadata-Version: 2.1
Name: test
Version: 1.0.0
"""
        (dist_info / "METADATA").write_text(metadata_content)

        # Process the metadata
        cm = CondaMetadata.from_distribution(PathDistribution(dist_info))

        # Verify all fields are strings, not None
        assert isinstance(cm.about["description"], str)
        assert isinstance(cm.about["summary"], str)
        assert isinstance(cm.about["license"], str)

        # Verify they're empty strings when not provided
        assert cm.about["description"] == ""
        assert cm.about["summary"] == ""
        assert cm.about["license"] == ""


def test_metadata_description_with_content():
    """Test that description content is preserved when present."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dist_info = Path(tmpdir) / "test-1.0.0.dist-info"
        dist_info.mkdir()

        metadata_content = """\
Metadata-Version: 2.1
Name: test
Version: 1.0.0
Summary: A test package
License: MIT
Description: This is a test description
"""
        (dist_info / "METADATA").write_text(metadata_content)

        cm = CondaMetadata.from_distribution(PathDistribution(dist_info))

        assert cm.about["summary"] == "A test package"
        assert cm.about["description"] == "This is a test description"
        assert cm.about["license"] == "MIT"
