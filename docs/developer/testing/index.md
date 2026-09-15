# Testing Guide

This guide covers everything you need to know about testing `conda-pypi`, including how to run tests, write new tests, and use the test infrastructure.

## Running Tests

`conda-pypi` uses [pytest](https://pytest.org/) for testing. All test commands should be run through pixi to ensure the correct environment is used.

### Basic Test Execution

Run the full test suite with the default Python version (3.10):

```bash
pixi run test
```

### Testing with Different Python Versions

The project supports Python 3.10 through 3.13. Test your changes across all supported versions:

```bash
# Python 3.11
pixi run -e test-py311 test

# Python 3.12
pixi run -e test-py312 test

# Python 3.13
pixi run -e test-py313 test
```

### Running Specific Tests

You can run specific test files or test functions:

```bash
# Run a specific test file
pixi run test tests/test_build.py

# Run a specific test function
pixi run test tests/test_build.py::test_indexable

# Run tests matching a pattern
pixi run test -k "test_conda"
```

### Test Markers

Tests are organized using pytest markers:

```bash
# Run only benchmark tests
pixi run benchmark

# Skip benchmark tests (default behavior)
pixi run test -m "not benchmark"
```

### Verbose Output

For more detailed test output:

```bash
# Show print statements
pixi run test -s

# Verbose pytest output
pixi run test -v

# Even more verbose
pixi run test -vv
```

## Running Benchmarks

Performance benchmarks use [pytest-benchmark](https://pytest-benchmark.readthedocs.io/) and are tracked in [Bencher](https://bencher.dev/). Run them locally with the Python 3.12 environment used in CI:

```bash
pixi run --locked -e test-py312 benchmark
```

To save the results in the JSON format uploaded by CI:

```bash
pixi run --locked -e test-py312 benchmark --benchmark-json benchmark_results.json
```

Benchmarks are marked with `@pytest.mark.benchmark` and are excluded from the regular test suite by default.

The `Test` workflow measures benchmarks on Ubuntu 24.04. Each case uses fixed local wheel fixtures, one warmup round, and five measured rounds with fresh prefixes and output directories. Environment creation happens outside the measured work. When changing the workload or fixture data, use a new benchmark name so historical timings remain comparable.

For pull requests, the workflow runs the base and head production code sequentially on the same runner with the same PR-head tests, fixtures, and resolved dependencies. This roughly doubles benchmark execution time. The reporter compares matching benchmark names using a fresh baseline branch for that workflow run, without changing the base branch's history. The initial alert tolerance is a 25% latency increase, following [Bencher's relative benchmarking example](https://bencher.dev/docs/how-to/track-benchmarks/#relative-continuous-benchmarking). Tune this tolerance as measurements accumulate. An incompatible baseline or no matching cases produces a neutral comparison check, with the head measurements retained as an artifact.

The separate `Track Benchmarks` workflow uploads results to Bencher. Testbeds combine the producer's Ubuntu version, architecture, Python major/minor version, and CPU model. These names separate environments but do not guarantee identical hardware or load. Artifacts record the runner image version, benchmark harness revision, dependency versions, and a best-effort [Bencher noise diagnostic](https://bencher.dev/docs/reference/bencher-noise/). Noise measurements are diagnostic only and do not adjust timings or decide whether a run passes.

Base branch uploads build a history for each testbed. Historical [regression detection](https://bencher.dev/docs/explanation/thresholds/) uses a t-test with a 0.99 probability setting and at least 10 historical measurements, up to 64. The 0.99 setting is not a 1% slowdown tolerance. A green historical check means no alert was raised, which can also happen before enough history exists.

Maintainers enable uploads by creating the `conda-pypi` project in Bencher and setting the `BENCHER_API_KEY` repository secret to its project API key. Local runs do not require Bencher credentials. Shared runner load, cache state, and dependency changes can still affect timings. Repeat unexpected results before treating them as regressions.

## Writing Tests

### Test Organization

Tests are organized in the `tests/` directory:

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── cli/                     # CLI-specific tests
├── pypi_local_index/        # Local package index data
├── conda_local_channel/     # Local conda channel data
└── test_*.py                # Test modules
```

### Test Structure

Follow these conventions when writing tests:

1. **File naming**: Test files should be named `test_*.py`
2. **Function naming**: Test functions should be named `test_*`
3. **Use fixtures**: Leverage pytest fixtures for setup and teardown
4. **Docstrings**: Add docstrings to explain what the test validates

Example test structure:

```python
import pytest
from conda_pypi.build import build_conda


def test_build_conda_package(tmp_path):
    """Test that a wheel can be converted to a conda package."""
    # Arrange
    wheel_path = tmp_path / "package-1.0.0-py3-none-any.whl"

    # Act
    result = build_conda(wheel_path, output_dir=tmp_path)

    # Assert
    assert result.exists()
    assert result.suffix == ".conda"
```

### Using Fixtures

Common fixtures are defined in `tests/conftest.py`:

(pypi-local-index)=

#### Local package index

The `pypi_local_index` fixture provides a local package index for testing without network access:

```python
def test_with_local_pypi(pypi_local_index):
    """Test using the local package index."""
    # pypi_local_index is a URL like "http://localhost:8035"
    # Use this in place of real PyPI for offline testing
    pass
```

#### Conda Local Channel

The `conda_local_channel` fixture provides a local conda channel server. See the [Mock Channel Server Guide](mock-channel-server.md) for details:

```python
def test_with_local_channel(conda_local_channel):
    """Test using the local conda channel."""
    # conda_local_channel is a URL like "http://localhost:8037"
    pass
```

#### Conda Testing Fixtures

The project uses `conda.testing` plugin which provides additional fixtures:

```python
def test_with_conda_env(tmp_env):
    """Test using a temporary conda environment."""
    # tmp_env provides a clean conda environment for testing
    pass
```

### Testing Best Practices

1. **Isolation**: Each test should be independent and not rely on other tests
2. **Cleanup**: Use fixtures and `tmp_path` to ensure proper cleanup
3. **Assertions**: Use descriptive assertion messages
4. **Coverage**: Aim for comprehensive coverage of both success and failure cases
5. **Performance**: Keep tests fast; use mocks for expensive operations
6. **Offline First**: Use local fixtures (`pypi_local_index`, `conda_local_channel`) instead of real network calls

### Example: Testing Package Conversion

```python
from pathlib import Path
from conda_pypi.translate import PackageRecord
from conda_pypi.build import build_conda


def test_wheel_to_conda_conversion(tmp_path, pypi_demo_package_wheel_path):
    """Test converting a wheel to conda package format.

    This test verifies that:
    1. The wheel is successfully converted to .conda format
    2. The package metadata is correctly translated
    3. The package can be indexed
    """
    # Convert wheel to conda
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    conda_pkg = build_conda(pypi_demo_package_wheel_path, output_dir=output_dir)

    # Verify the output
    assert conda_pkg.exists()
    assert conda_pkg.name.endswith(".conda")

    # Verify it can be indexed
    from conda_pypi.index import update_index

    update_index(output_dir.parent)
```

### Testing CLI Commands

For testing CLI commands, use the `conda_cli` test fixture:

```python
from conda.cli.main import main_subshell


def test_conda_pypi_install(conda_cli, tmp_env):
    """Test the conda pypi install command."""
    result = conda_cli("pypi", "install", "requests", "--prefix", str(tmp_env))
    assert result == 0
```

## Test Infrastructure

### Local Test Servers

The test suite uses local HTTP servers to avoid network dependencies:

- **Package index**: Serves packages from `tests/pypi_local_index/`
- **Conda Channel Server**: Serves packages from `tests/conda_local_channel/`

For more information on the conda channel server, see the [Mock Channel Server Guide](mock-channel-server.md).

### Test Data

- `tests/pypi_local_index/`: Wheel files and package metadata for offline PyPI testing
- `tests/conda_local_channel/`: Pre-converted conda packages for dependency resolution testing

## Continuous Integration

Tests run automatically on GitHub Actions for:

- All supported Python versions (3.10-3.13)
- Multiple operating systems (Linux, macOS, Windows)
- Pull requests and main branch commits

Ensure all tests pass locally before submitting a pull request.

## Troubleshooting

### Tests Are Slow

If tests are running slowly:

1. Run a subset of tests instead of the full suite
2. Check if benchmark tests are included (they should be excluded by default)
3. Consider using `-n auto` for parallel test execution (if pytest-xdist is available)

### Fixture Not Found

If you see "fixture not found" errors:

1. Check that `tests/conftest.py` is present
2. Verify the fixture name is correct
3. Ensure the pytest plugin is loaded (`pytest_plugins` in conftest.py)

```{toctree}
:hidden:
:maxdepth: 1

mock-channel-server
```
