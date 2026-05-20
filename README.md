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

The `conda-pypi` plugin improves conda's integration with the PyPI ecosystem. The most
important feature is the `conda-pypi` channel, hosted by Anaconda, which makes pure
Python pacakges from PyPi available to users natively through `conda install`.

## Using `conda-pypi`

`conda-pypi` is available in conda 26.5 or later. To update:

```bash
conda install --name base "conda>=26.5"
```

To opt in, enable the Rattler solver and add the `conda-pypi` channel:

```bash
conda config --set solver rattler
conda config --append channels conda-pypi
```

After configuring, you can use PyPI packages alongside conda packages in
your normal conda workflows, without needing to convert PyPI's wheel files
to conda files.

## Advanced options

`conda-pypi` includes more advanced subcommand controls for working with PyPI
packages. These options are recommended for users who want to experiment with
conda and wheels and work with cutting-edge plugin features.

You can use the following commands with the `conda pypi` subcommand to do more
with the `conda-pypi` plugin:

- `conda pypi install`: Converts PyPI packages to `.conda` format for safer installation.
- `conda pypi install -e .`: Converts a path to an editable `.conda` format package.
- `conda pypi convert`: Convert PyPI packages to `.conda` format without installing them.
- `conda pypi migrate-env`: Rewrite an `environment.yaml` by replacing pip dependencies with conda packages from a wheels channel.
- `conda install` from wheel channels (experimental): channels can serve pure Python wheels directly in `repodata.json`.
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
