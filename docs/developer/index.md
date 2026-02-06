# Developer Guide

Welcome to the `conda-pypi` developer guide! This section provides comprehensive documentation for contributors and developers working on `conda-pypi`.

## Overview

`conda-pypi` is built as a conda plugin that provides better PyPI interoperability for the conda ecosystem. Understanding the architecture and development workflow is essential for contributing to the project.

## Contents

::::{grid} 2

:::{grid-item-card} Architecture
:link: architecture
:link-type: doc
Technical architecture, plugin system design, and data flow
:::

:::{grid-item-card} Developer Notes
:link: developer-notes
:link-type: doc
Implementation details, technical insights, and development considerations
:::

::::

::::{grid} 1

:::{grid-item-card} Testing
:link: testing/index
:link-type: doc
Complete guide to running tests, writing tests, and using test infrastructure
:::

::::

## Getting Started with Development

This project uses [pixi](https://pixi.sh) for environment management. All development commands should be run through pixi.

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/conda-incubator/conda-pypi.git
cd conda-pypi

# Setup the development environment
pixi run dev
```

### Common Development Tasks

```bash
# Run tests (Python 3.10)
pixi run test

# Run tests with specific Python version
pixi run -e test-py311 test
pixi run -e test-py312 test
pixi run -e test-py313 test

# Run linting and formatting
pixi run pre-commit

# Build documentation
pixi run -e docs docs

# Run benchmarks
pixi run benchmark
```

## Project Structure

```
conda-pypi/
├── conda_pypi/          # Main package code
│   ├── plugin.py        # Conda plugin registration
│   ├── cli/             # Command-line interface
│   ├── build.py         # Wheel to conda conversion
│   ├── translate.py     # PyPI ↔ Conda metadata translation
│   ├── convert_tree.py  # Dependency resolution
│   └── ...
├── tests/               # Test suite
├── docs/                # Documentation (Sphinx)
├── recipe/              # Conda recipe for building the package
└── pixi.toml            # Project configuration
```

## Contributing

When contributing to `conda-pypi`:

1. **Test with Multiple Python Versions**: Use the provided pixi environments (`test-py310` through `test-py313`)
2. **Run Pre-commit Hooks**: Always run `pixi run pre-commit` before committing
3. **Update Documentation**: Keep documentation in sync with code changes
4. **Write Tests**: Add tests for new features and bug fixes
5. **Follow the Code Style**: The project uses `ruff` for linting and formatting

## Additional Resources

- [GitHub Repository](https://github.com/conda-incubator/conda-pypi)
- [Issue Tracker](https://github.com/conda-incubator/conda-pypi/issues)
- [Conda Plugin Documentation](https://docs.conda.io/projects/conda/en/latest/dev-guide/plugins/index.html)

```{toctree}
:hidden:
:maxdepth: 2

architecture
developer-notes
testing/index
```
