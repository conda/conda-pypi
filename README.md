# conda-pypi

<p align="center">
  <img src="./docs/_static/img/logo.png" alt="conda-pypi logo"/>
</p>

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

The `conda-pypi` plugin improves conda's integration with Python packaging tools. The most
important feature is the `conda-pypi` channel, hosted by Anaconda, which makes pure
Python wheels from PyPI available to users natively through `conda install`.

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

During the beta, the `conda-pypi` channel might not appear in the
Anaconda.org web UI and some commands such as `conda search` can fail because
they request classic `repodata.json` metadata. Use `conda install` or
`conda create --dry-run` to check whether the solver can use the channel.

After configuring, you can use packages from PyPI alongside conda packages in
your normal conda workflows, without needing to convert the wheel files
to conda files.

## Advanced options

`conda-pypi` includes more advanced subcommand controls for working with Python
packages. These options are recommended for users who want to experiment with
conda and wheels and work with cutting-edge plugin features.

You can use the following commands with the `conda pypi` subcommand to do more
with the `conda-pypi` plugin:

- `conda pypi install`: Converts wheels from PyPI and other package indexes to `.conda` format for safer installation. PyPI is the default index. Use `--index-url` to select another index.
- `conda pypi install -e .`: Converts a path to an editable `.conda` format package.
- `conda pypi convert`: Convert Python projects to `.conda` format without installing them.
- `conda pypi index`: Index a local directory of `.whl` files to create a local conda channel.
- `conda install` from wheel channels (experimental): channels can serve pure Python wheels directly in `repodata.json`.
- A warning when running `conda create` or `conda install` with `pip` in the environment.

## Why?

Mixing conda packages and packages installed with pip is often discouraged in the conda ecosystem.
There are only a handful patterns that are safe to run. This tool
aims to provide a safer way of keeping your conda environments functional
while adding Python distribution packages. Refer to the [documentation](docs/)
for more details.

## Attribution

- This project now incorporates [conda-pupa](https://github.com/dholth/conda-pupa)
by Daniel Holth, which provides the core wheel-to-conda conversion functionality.
- The conda-pypi platypus logo is by [James Turner](http://www.eruditebaboon.co.uk/).

## Contributing

Please refer to [`CONTRIBUTING.md`](/CONTRIBUTING.md).
