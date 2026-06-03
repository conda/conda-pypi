"""
Test functions for transforming repodata.
"""

from conda_pypi.translate import (
    CondaMetadata,
    FileDistribution,
    MatchSpec,
    check_import_name_conflicts,
    conda_to_requires,
    pypi_to_conda_name,
    remap_match_spec_name,
)
from importlib.metadata import PathDistribution
from pathlib import Path
import tempfile


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


def test_import_names_absent_when_not_declared():
    with tempfile.TemporaryDirectory() as tmpdir:
        dist_info = Path(tmpdir) / "test-1.0.0.dist-info"
        dist_info.mkdir()
        (dist_info / "METADATA").write_text(
            "Metadata-Version: 2.1\nName: test\nVersion: 1.0.0\n"
        )
        cm = CondaMetadata.from_distribution(PathDistribution(dist_info))
        assert "import_names" not in cm.about
        assert "import_namespaces" not in cm.about


def test_import_names_read_from_metadata():
    """Import-Name entries are stored in about['import_names'] (PEP 794)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dist_info = Path(tmpdir) / "scikit_learn-1.7.0.dist-info"
        dist_info.mkdir()
        (dist_info / "METADATA").write_text(
            "Metadata-Version: 2.5\n"
            "Name: scikit-learn\n"
            "Version: 1.7.0\n"
            "Import-Name: sklearn\n"
        )
        cm = CondaMetadata.from_distribution(PathDistribution(dist_info))
        assert cm.about["import_names"] == ["sklearn"]
        assert "import_namespaces" not in cm.about


def test_import_namespaces_read_from_metadata():
    """Import-Namespace entries are stored in about['import_namespaces'] (PEP 794)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dist_info = Path(tmpdir) / "azure_mgmt_search-9.1.0.dist-info"
        dist_info.mkdir()
        (dist_info / "METADATA").write_text(
            "Metadata-Version: 2.5\n"
            "Name: azure-mgmt-search\n"
            "Version: 9.1.0\n"
            "Import-Name: azure.mgmt.search\n"
            "Import-Namespace: azure\n"
            "Import-Namespace: azure.mgmt\n"
        )
        cm = CondaMetadata.from_distribution(PathDistribution(dist_info))
        assert cm.about["import_names"] == ["azure.mgmt.search"]
        assert cm.about["import_namespaces"] == ["azure", "azure.mgmt"]


def test_import_name_private_modifier_preserved():
    with tempfile.TemporaryDirectory() as tmpdir:
        dist_info = Path(tmpdir) / "pytest-8.3.5.dist-info"
        dist_info.mkdir()
        (dist_info / "METADATA").write_text(
            "Metadata-Version: 2.5\n"
            "Name: pytest\n"
            "Version: 8.3.5\n"
            "Import-Name: _pytest ; private\n"
            "Import-Name: py\n"
            "Import-Name: pytest\n"
        )
        cm = CondaMetadata.from_distribution(PathDistribution(dist_info))
        assert "_pytest ; private" in cm.about["import_names"]
        assert "py" in cm.about["import_names"]
        assert "pytest" in cm.about["import_names"]


def test_empty_import_names_declaration():
    with tempfile.TemporaryDirectory() as tmpdir:
        dist_info = Path(tmpdir) / "data_only-1.0.dist-info"
        dist_info.mkdir()
        (dist_info / "METADATA").write_text(
            "Metadata-Version: 2.5\n"
            "Name: data-only\n"
            "Version: 1.0\n"
            "Import-Name: \n"
        )
        cm = CondaMetadata.from_distribution(PathDistribution(dist_info))
        # Field is present (declared), list must exist even if it contains an empty string
        assert "import_names" in cm.about


def test_check_import_name_conflicts_no_conflict():
    result = check_import_name_conflicts(
        {"pillow": ["PIL"], "requests": ["requests", "urllib3"]}
    )
    assert result == []


def test_check_import_name_conflicts_detects_overlap():
    conflicts = check_import_name_conflicts(
        {"pkg-a": ["utils"], "pkg-b": ["utils"]}
    )
    assert len(conflicts) == 1
    name, first, second, kind = conflicts[0]
    assert name == "utils"
    assert first == "pkg-a"
    assert second == "pkg-b"
    assert kind == "exclusive"


def test_check_import_name_conflicts_ignores_private_modifier():
    conflicts = check_import_name_conflicts(
        {"pkg-a": ["_internals ; private"], "pkg-b": ["_internals; private"]}
    )
    assert len(conflicts) == 1
    assert conflicts[0][0] == "_internals"
    assert conflicts[0][3] == "exclusive"


def test_check_import_name_conflicts_empty_entry_skipped():
    result = check_import_name_conflicts(
        {"data-only": [""], "other": [""]}
    )
    assert result == []


def test_check_import_name_conflicts_multiple_conflicts():
    conflicts = check_import_name_conflicts(
        {
            "pkg-a": ["foo", "bar"],
            "pkg-b": ["foo", "baz"],
            "pkg-c": ["bar"],
        }
    )
    conflict_names = {c[0] for c in conflicts}
    assert "foo" in conflict_names
    assert "bar" in conflict_names


def test_check_import_name_conflicts_namespace_allowed():
    result = check_import_name_conflicts(
        {},
        package_import_namespaces={"azure-mgmt-search": ["azure", "azure.mgmt"],
                                    "azure-mgmt-compute": ["azure", "azure.mgmt"]},
    )
    assert result == []


def test_check_import_name_conflicts_name_vs_namespace():
    conflicts = check_import_name_conflicts(
        # pkg-b claims 'azure' exclusively
        {"pkg-b": ["azure"]},
        package_import_namespaces={"azure-mgmt-search": ["azure", "azure.mgmt"]},
    )
    assert len(conflicts) == 1
    name, first, second, kind = conflicts[0]
    assert name == "azure"
    assert kind == "exclusive-vs-namespace"


def test_check_import_name_conflicts_same_name_in_both_fields_must_error():
    conflicts = check_import_name_conflicts(
        {"pkg-a": ["azure"]},
        package_import_namespaces={"pkg-a": ["azure"]},
    )
    assert len(conflicts) == 1
    name, pkg1, pkg2, kind = conflicts[0]
    assert name == "azure"
    assert pkg1 == "pkg-a"
    assert pkg2 == "pkg-a"  # same package, self-conflict
    assert kind == "ambiguous-in-both"


def test_check_import_name_conflicts_same_name_in_both_fields_does_not_double_report():
    conflicts = check_import_name_conflicts(
        {"pkg-a": ["azure"]},
        package_import_namespaces={"pkg-a": ["azure"]},
    )
    # Only the ambiguous-in-both conflict, not a spurious exclusive-vs-namespace for the same pkg
    kinds = {c[3] for c in conflicts}
    assert kinds == {"ambiguous-in-both"}


def test_from_distribution_raises_on_ambiguous_import_names():
    with tempfile.TemporaryDirectory() as tmpdir:
        dist_info = Path(tmpdir) / "bad_pkg-1.0.dist-info"
        dist_info.mkdir()
        (dist_info / "METADATA").write_text(
            "Metadata-Version: 2.5\n"
            "Name: bad-pkg\n"
            "Version: 1.0\n"
            "Import-Name: azure\n"
            "Import-Namespace: azure\n"
        )
        with pytest.raises(ValueError, match="both Import-Name and Import-Namespace"):
            CondaMetadata.from_distribution(PathDistribution(dist_info))
