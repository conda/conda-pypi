"""Tests for conda_pypi.markers."""

import pytest
from packaging.markers import Marker

from conda_pypi.markers import (
    extract_marker_condition_and_extras,
)


@pytest.mark.parametrize(
    ("marker_expr", "expected_condition", "expected_extras"),
    [
        ('extra == "docs"', None, ["docs"]),
        ('python_version < "3.11"', "python<3.11", []),
        ('python_full_version < "3.11.0"', "python<3.11.0", []),
        (
            'python_version not in "3.0, 3.1"',
            "(python!=3.0 and python!=3.1)",
            [],
        ),
        ('sys_platform == "win32"', "__win", []),
        ('sys_platform == "linux"', "__linux", []),
        ('platform_system == "darwin"', "__osx", []),
        ('os_name == "nt"', "__win", []),
        ('os_name == "posix"', "__unix", []),
        ('sys_platform != "win32"', "__unix", []),
        (
            'python_version < "3.11" and extra == "test"',
            "python<3.11",
            ["test"],
        ),
        ('implementation_name == "cpython"', None, []),
        ('platform_machine == "x86_64"', None, []),
        (
            'extra == "socks" or extra == "socks"',
            None,
            ["socks"],
        ),
    ],
)
def test_extract_marker_condition_and_extras(marker_expr, expected_condition, expected_extras):
    condition, extras = extract_marker_condition_and_extras(Marker(marker_expr))
    assert condition == expected_condition
    assert extras == expected_extras


def test_extract_marker_combines_or_platforms():
    """Both sides contribute when neither operand is absorbed as None-only."""
    condition, extras = extract_marker_condition_and_extras(
        Marker('sys_platform == "linux" or sys_platform == "darwin"')
    )
    assert extras == []
    assert condition is not None
    assert "__linux" in condition
    assert "__osx" in condition
    assert " or " in condition
