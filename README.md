# conda-pypi

Better PyPI interoperability for the conda ecosystem.

> [!IMPORTANT]
> This project is still in early stages of development. Don't use it in production (yet).
> We do welcome feedback on what the expected behaviour should have been if something doesn't work!

## Project Status

This is a **community-maintained** project under the [conda](https://github.com/conda) organization.

### Getting Help

- **Bug reports & feature requests**: [GitHub Issues](https://github.com/conda/conda-pypi/issues)
- **Real-time chat**: [conda Zulip](https://conda.zulipchat.com/)

## What is this?

Includes:

- `conda pypi install`: Converts PyPI packages to `.conda` format for safer installation.
- `conda pypi install -e .`: Converts a path to an editable `.conda` format package.
- `conda pypi convert`: Convert PyPI packages to `.conda` format without installing them.
- `conda install` from wheel channels (experimental): channels can serve pure Python wheels directly in `repodata.json`.
- Adds `EXTERNALLY-MANAGED` to your environments.

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
