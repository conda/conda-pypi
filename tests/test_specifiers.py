"""Tests for the specifiers module."""

import pytest
from conda.models.version import VersionSpec
from packaging.specifiers import SpecifierSet

from conda_pypi.specifiers import specifier_bounds_to_conda, specifier_bounds_to_pep440


def test_converted_exclusive_upper_bound_excludes_prereleases():
    """Appending ``a0`` to exclusive upper bounds causes conda version to exclude pre-releases consistent with PEP 440."""
    pep_spec = VersionSpec(">=2.0,<3.12")
    assert pep_spec.match("3.12.0rc1")
    conda_spec = VersionSpec(">=2.0,<3.12a0")
    assert not conda_spec.match("3.12.0rc1")


def test_specifier_bounds_to_conda_appends_to_exclusive_upper_bound():
    spec = SpecifierSet("<3.12,>=2.0")
    new_bounds = specifier_bounds_to_conda(spec)
    assert new_bounds == "<3.12a0,>=2.0"


def test_specifier_bounds_to_conda_ignores_prereleases():
    spec = SpecifierSet("<3.12.0rc1,>=2.0")
    new_bounds = specifier_bounds_to_conda(spec)
    assert new_bounds == "<3.12.0rc1,>=2.0"


def test_specifier_bounds_to_conda_ignores_inclusive_upper_bound():
    spec = SpecifierSet("<=3.12.0rc1,>=2.0")
    new_bounds = specifier_bounds_to_conda(spec)
    assert new_bounds == "<=3.12.0rc1,>=2.0"


@pytest.mark.parametrize(
    "spec, version, expected",
    [
        # ~=X.Y.Z means >=X.Y.Z, ==X.Y.* in PEP 440
        pytest.param("~=2.2.1", "2.2.1", True, id="exact-match"),
        pytest.param("~=2.2.1", "2.2.9", True, id="newer-last-component"),
        pytest.param("~=2.2.1", "2.2.0", False, id="too-low"),
        pytest.param("~=2.2.1", "2.3.0", False, id="too-high"),
        pytest.param("~=2.2.1", "3.0.0", False, id="too-high-major"),
        # Prereleases: where they fall relative to the range
        pytest.param("~=2.2.1", "2.2.5rc1", True, id="prerelease-inside-range"),
        pytest.param("~=2.2.1", "2.2.1rc1", False, id="prerelease-of-lower-bound"),
        pytest.param("~=2.2.1", "2.3.0rc1", False, id="prerelease-of-upper-boundary"),
        # Dev releases sort before all prereleases of the same version
        pytest.param("~=2.2.1", "2.2.5.dev1", True, id="dev-inside-range"),
        pytest.param("~=2.2.1", "2.2.1.dev1", False, id="dev-of-lower-bound"),
        pytest.param("~=2.2.1", "2.3.0.dev1", False, id="dev-of-upper-boundary"),
        # Two components: only the last one may change
        pytest.param("~=2.2", "2.9", True, id="two-components-newer"),
        pytest.param("~=2.2", "3.0", False, id="two-components-too-high"),
        pytest.param("~=2.2", "3.0rc1", False, id="two-components-prerelease-of-boundary"),
        pytest.param("~=2.2.1.post1", "2.2.6", True, id="post-spec-newer-last-component"),
        # Epoch should carry through conversion
        pytest.param("~=1!2.2.1", "1!2.2.2", True, id="epoch-inside-range"),
        pytest.param("~=1!2.2.1", "2.2.1", False, id="epoch-0-version"),
        pytest.param("~=1!2.2.1", "1!2.2.0", False, id="epoch-too-low"),
        pytest.param("~=1!2.2.1", "1!2.3.0", False, id="epoch-too-high"),
        pytest.param("~=1!2.2.1", "1!2.3.0rc1", False, id="epoch-prerelease-of-upper-boundary"),
    ],
)
def test_compatible_releases_match_pep_440(spec, version, expected):
    pep440 = SpecifierSet(spec, prereleases=True)
    conda = VersionSpec(specifier_bounds_to_conda(SpecifierSet(spec)))
    assert pep440.contains(version) is expected
    assert conda.match(version) is expected


def test_specifier_bounds_to_conda_compatible_release_with_epoch():
    assert specifier_bounds_to_conda(SpecifierSet("~=1!2.2.1")) == "<1!2.3.0a0,>=1!2.2.1"


def test_specifier_bounds_to_conda_compatible_release_without_epoch():
    assert specifier_bounds_to_conda(SpecifierSet("~=2.2.1")) == "<2.3.0a0,>=2.2.1"


def test_specifier_bounds_to_pep_440_ignores_real_prerelease():
    spec = SpecifierSet("<2.0a1")
    new_bounds = specifier_bounds_to_pep440(spec)
    assert new_bounds == "<2.0a1"


def test_specifier_bounds_to_pep_440_ignores_inclusive_upper_bound():
    spec = SpecifierSet("<=3.12.0a0,>=2.0")
    new_bounds = specifier_bounds_to_pep440(spec)
    assert new_bounds == "<=3.12.0a0,>=2.0"


def test_specifier_bounds_to_pep_440_ignores_lower_bounds():
    spec = SpecifierSet(">=2.0a0,>1.0a0")
    new_bounds = specifier_bounds_to_pep440(spec)
    assert new_bounds == ">1.0a0,>=2.0a0"
