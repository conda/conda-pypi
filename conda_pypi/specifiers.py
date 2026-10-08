"""
Responsible for PEP 440 <=> Conda Version conversions
"""

from packaging.specifiers import SpecifierSet
from packaging.version import Version


def specifier_bounds_to_conda(specifier: SpecifierSet) -> str:
    """Return a conda MatchSpec version string built from PEP 440 specifiers.

    Exclusive upper bounds (``<V``) that are not themselves pre-releases get ``a0``
    appended. PEP 440's ``<V`` excludes pre-releases of ``V``, but conda's ``<`` only
    compares versions, and pre-releases sort below ``V``, so ``<3.12`` would match
    ``3.12.0rc1``. ``<3.12a0`` excludes them.

    Bounds are sorted the same way as ``str(SpecifierSet)`` so the output is deterministic.
    """
    bounds = []
    for spec in sorted(specifier, key=str):
        new_bound = f"{spec.operator}{spec.version}"
        if spec.operator == "<" and not Version(spec.version).is_prerelease:
            new_bound += "a0"
        bounds.append(new_bound)

    return ",".join(bounds)


def specifier_bounds_to_pep440(specifier: SpecifierSet) -> str:
    """Return a PEP 440 version string from a converted conda MatchSpec version string.

    PEP 440 exclusive upper bounds that have ``a0`` appended will enable matching prereleases.
    Removing the ``a0`` added from specifier_bounds_to_conda ensures that the PEP 440 compares specifications as intended.
    """
    bounds = []
    for spec in sorted(specifier, key=str):
        version = spec.version
        if spec.operator == "<" and version.endswith("a0"):
            version = version.removesuffix("a0")
        bounds.append(f"{spec.operator}{version}")

    return ",".join(bounds)
