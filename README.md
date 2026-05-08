# conda-pypi

Better PyPI interoperability for the conda ecosystem.

> [!IMPORTANT]
> This project is currently in beta. Use with caution in production environments.
> We welcome feedback. If something doesn't work as expected, please let us know!

## Project Status

This is a **community-maintained** project under the [conda](https://github.com/conda) organization.

### Getting Help

- **Bug reports & feature requests**: [GitHub Issues](https://github.com/conda/conda-pypi/issues)
- **Real-time chat**: [conda Zulip](https://conda.zulipchat.com/)

## What is this?

Native support for installing wheels from PyPI using `conda install`:
1. `conda config --set solver rattler`
2. `conda config --set channel_priority flexible`
3. `conda install <package>`

Also includes:

- `conda pypi install`: Converts PyPI packages to `.conda` format for safer installation.
- `conda pypi install -e .`: Converts a path to an editable `.conda` format package.
- `conda pypi convert`: Convert PyPI packages to `.conda` format without installing them.
- A warning when running `conda create` or `conda install` with `pip` in the environment.

## Why?

Mixing conda and PyPI is often discouraged in the conda ecosystem.
There are only a handful patterns that are safe to run. This tool
aims to provide a safer way of keeping your conda environments functional
while mixing it with PyPI dependencies. Refer to the [documentation](docs/)
for more details.

## Attribution

This project now incorporates [conda-pupa](https://github.com/dholth/conda-pupa)
by Daniel Holth, which provides the core PyPI-to-conda conversion functionality.

## Contributing

Please refer to [`CONTRIBUTING.md`](/CONTRIBUTING.md).
