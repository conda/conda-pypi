import json
import os

import pytest
from conda.cli.main import main_subshell
from conda.common.compat import on_win
from conda.exceptions import ArgumentError
import conda_package_streaming.package_streaming as cps

# Test input paths
DEMO_WHEEL = "tests/pypi_local_index/demo-package/demo_package-0.1.0-py3-none-any.whl"
PKG_HAS_BUILD_DEP = "tests/packages/has-build-dep"
PKG_TEST_DIR = "tests/packages/has-test-dir/test"

# Expected output paths
EXPECTED_TEST_SCRIPT = "info/test/run_test.bat" if on_win else "info/test/run_test.sh"


@pytest.mark.parametrize(
    "source, editable",
    [
        (PKG_HAS_BUILD_DEP, False),
        (PKG_HAS_BUILD_DEP, True),
    ],
)
def test_convert_writes_output(tmp_path, source, editable):
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    args = ["pypi", "convert", "--output-folder", str(out_dir)]
    if editable:
        args.append("-e")
    args.append(source)
    main_subshell(*args)

    files = list(out_dir.glob("*.conda"))
    assert files, f"No .conda artifacts found in {out_dir}"

    assert files[0].is_file()
    assert os.path.getsize(files[0]) > 0


def test_convert_wheel(tmp_path):
    """Test converting an existing wheel file to conda package."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    args = ["pypi", "convert", "--output-folder", str(out_dir), DEMO_WHEEL]
    main_subshell(*args)

    files = list(out_dir.glob("*.conda"))
    assert files, f"No .conda artifacts found in {out_dir}"

    assert files[0].is_file()
    assert os.path.getsize(files[0]) > 0
    assert "demo-package" in files[0].name


def test_convert_wheel_with_tests(tmp_path):
    """Test converting an existing wheel file to conda package and injecting a test directory."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    args = [
        "pypi",
        "convert",
        "--output-folder",
        str(out_dir),
        "--test-dir",
        PKG_TEST_DIR,
        DEMO_WHEEL,
    ]
    main_subshell(*args)

    files = list(out_dir.glob("*.conda"))
    assert files, f"No .conda artifacts found in {out_dir}"

    assert files[0].is_file()
    assert os.path.getsize(files[0]) > 0
    assert "demo-package" in files[0].name

    # Unpack and verify test files exist
    test_files = [
        m.name for _, m in cps.stream_conda_info(str(files[0])) if m.name.startswith("info/test/")
    ]
    assert "info/test/run_test.py" in test_files
    assert EXPECTED_TEST_SCRIPT in test_files
    assert "info/test/test_time_dependencies.json" in test_files


def test_convert_source_with_tests(tmp_path):
    """Test converting a source package to conda package and injecting a test directory."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    args = [
        "pypi",
        "convert",
        "--output-folder",
        str(out_dir),
        "--test-dir",
        PKG_TEST_DIR,
        PKG_HAS_BUILD_DEP,
    ]
    main_subshell(*args)

    files = list(out_dir.glob("*.conda"))
    assert files, f"No .conda artifacts found in {out_dir}"

    assert files[0].is_file()
    assert os.path.getsize(files[0]) > 0

    # Unpack and verify test files exist
    test_files = [
        m.name for _, m in cps.stream_conda_info(str(files[0])) if m.name.startswith("info/test/")
    ]
    assert "info/test/run_test.py" in test_files
    assert EXPECTED_TEST_SCRIPT in test_files
    assert "info/test/test_time_dependencies.json" in test_files


def test_convert_with_invalid_test_dir(tmp_path):
    """Test that invalid test directory raises an appropriate error."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    nonexistent_dir = tmp_path / "nonexistent"

    args = [
        "pypi",
        "convert",
        "--output-folder",
        str(out_dir),
        "--test-dir",
        str(nonexistent_dir),
        DEMO_WHEEL,
    ]

    with pytest.raises(FileNotFoundError, match="Test directory does not exist"):
        main_subshell(*args)


def test_convert_with_test_dir_missing_run_test(tmp_path):
    """Test that test directory without run_test.* file raises an error."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    test_dir = tmp_path / "test"
    test_dir.mkdir()

    # Create a file that doesn't match run_test.*
    with open(test_dir / "other_file.txt", "w") as f:
        f.write("some content")

    args = [
        "pypi",
        "convert",
        "--output-folder",
        str(out_dir),
        "--test-dir",
        str(test_dir),
        DEMO_WHEEL,
    ]

    with pytest.raises(ValueError, match="Test directory must contain at least one run_test"):
        main_subshell(*args)


def test_convert_with_name_mapping_empty(tmp_path):
    """Test that empty mapping is allowed."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    # Create empty mapping file
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text("{}")

    wheel_path = "tests/pypi_local_index/demo-package/demo_package-0.1.0-py3-none-any.whl"
    args = [
        "pypi",
        "convert",
        "--output-folder",
        str(out_dir),
        "--name-mapping",
        str(mapping_file),
        wheel_path,
    ]

    # Should not raise
    main_subshell(*args)

    files = list(out_dir.glob("*.conda"))
    assert files, f"No .conda artifacts found in {out_dir}"
    assert files[0].is_file()


def test_convert_with_name_mapping_not_dict(tmp_path):
    """Test that non-dict JSON raises ArgumentError."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    # Create invalid mapping file (list instead of dict)
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('["not", "a", "dict"]')

    wheel_path = "tests/pypi_local_index/demo-package/demo_package-0.1.0-py3-none-any.whl"
    args = [
        "pypi",
        "convert",
        "--output-folder",
        str(out_dir),
        "--name-mapping",
        str(mapping_file),
        wheel_path,
    ]

    with pytest.raises(ArgumentError, match="must be a dictionary"):
        main_subshell(*args)


def test_convert_with_name_mapping_invalid_format_missing_conda_name(tmp_path):
    """Test that mapping missing conda_name raises ArgumentError."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    # Create invalid mapping file (missing conda_name)
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"requests": {"pypi_name": "requests"}}')

    wheel_path = "tests/pypi_local_index/demo-package/demo_package-0.1.0-py3-none-any.whl"
    args = [
        "pypi",
        "convert",
        "--output-folder",
        str(out_dir),
        "--name-mapping",
        str(mapping_file),
        wheel_path,
    ]

    with pytest.raises(ArgumentError, match="missing required key 'conda_name'"):
        main_subshell(*args)


def test_convert_with_name_mapping_invalid_format_non_string_conda_name(tmp_path):
    """Test that non-string conda_name raises ArgumentError."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    # Create invalid mapping file (conda_name is not a string)
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"requests": {"conda_name": 123}}')

    wheel_path = "tests/pypi_local_index/demo-package/demo_package-0.1.0-py3-none-any.whl"
    args = [
        "pypi",
        "convert",
        "--output-folder",
        str(out_dir),
        "--name-mapping",
        str(mapping_file),
        wheel_path,
    ]

    with pytest.raises(ArgumentError, match="invalid 'conda_name' type"):
        main_subshell(*args)


def test_convert_with_name_mapping_valid(tmp_path):
    """Test that valid mapping file works correctly and mapping is applied."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    # Create valid mapping file
    mapping_file = tmp_path / "mapping.json"
    valid_mapping = {
        "demo-package": {
            "pypi_name": "demo-package",
            "conda_name": "demo-package-mapped",
            "import_name": "demo_package",
            "mapping_source": "test",
        }
    }
    mapping_file.write_text(json.dumps(valid_mapping))

    wheel_path = "tests/pypi_local_index/demo-package/demo_package-0.1.0-py3-none-any.whl"
    args = [
        "pypi",
        "convert",
        "--output-folder",
        str(out_dir),
        "--name-mapping",
        str(mapping_file),
        wheel_path,
    ]

    # Should not raise
    main_subshell(*args)

    files = list(out_dir.glob("*.conda"))
    assert files, f"No .conda artifacts found in {out_dir}"
    assert files[0].is_file()
    assert os.path.getsize(files[0]) > 0
    # Verify that mapping was applied - package name should be "demo-package-mapped"
    assert "demo-package-mapped" in files[0].name, (
        f"Expected 'demo-package-mapped' in filename {files[0].name}, but mapping was not applied"
    )


def test_convert_with_name_mapping_nonexistent_file(tmp_path):
    """Test that nonexistent mapping file raises ArgumentError."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    mapping_file = tmp_path / "nonexistent.json"
    wheel_path = "tests/pypi_local_index/demo-package/demo_package-0.1.0-py3-none-any.whl"
    args = [
        "pypi",
        "convert",
        "--output-folder",
        str(out_dir),
        "--name-mapping",
        str(mapping_file),
        wheel_path,
    ]

    with pytest.raises(ArgumentError, match="Could not open"):
        main_subshell(*args)
