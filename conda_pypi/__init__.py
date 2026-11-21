"""
conda-pypi
"""

try:
    from ._version import __version__
except ImportError:
    # _version.py is only created after running `pip install`
    try:
        from setuptools_scm import get_version

        __version__ = get_version(root="..", relative_to=__file__)
    except (ImportError, OSError, LookupError):
        # ImportError: setuptools_scm isn't installed
        # OSError: git isn't installed
        # LookupError: setuptools_scm unable to detect version
        __version__ = "0.0.0.dev0+placeholder"
