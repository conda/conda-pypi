# conda-pypi

<p align="center">
  <img src="https://raw.githubusercontent.com/conda/conda-pypi/refs/heads/main/docs/_static/img/logo.png" alt="conda-pypi logo"/>
</p>

Better PyPI interoperability for the conda ecosystem.

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

For the best experience with `conda-pypi`, update to conda 26.9 or later. To update:

```bash
conda self update
```

or if updating from older versions of conda without `conda-self` you can also run:

```bash
conda install --name base "conda>=26.9"
```

To opt in, enable the Rattler solver and add the `conda-pypi` channel:

```bash
conda config --set solver rattler
conda config --append channels conda-pypi
```

After configuring, you can use packages from PyPI alongside conda packages in
your normal conda workflows, without needing to convert the wheel files
to conda files.

`conda install` uses conda package names, which sometimes differ from the PyPI
project name. For example, conda-forge publishes the PyPI project
`jupyterlab-code-formatter` as `jupyterlab_code_formatter`, so run
`conda install jupyterlab_code_formatter`. The `conda pypi` subcommands accept
PyPI names and translate them.

## Advanced options

`conda-pypi` includes more advanced subcommand controls for working with Python
packages. These options are recommended for users who want to experiment with
conda and wheels and work with cutting-edge plugin features.

You can use the following commands with the `conda pypi` subcommand to do more
with the `conda-pypi` plugin:

- `conda pypi convert`: Convert Python projects to `.conda` format without installing them.
- `conda pypi index`: Index a local directory of `.whl` files to create a local conda channel.
- `conda install` from wheel channels (experimental): channels can serve pure Python wheels directly in `repodata.json`.
- A warning when running `conda create` or `conda install` with `pip` in the environment.

`conda pypi install` is pending deprecation. See the [features documentation](docs/features.md) for its remaining use cases, such as editable installs.

## Why?

Mixing conda packages and packages installed with pip is often discouraged in the conda ecosystem.
There are only a handful patterns that are safe to run. This tool
aims to provide a safer way of keeping your conda environments functional
while adding Python distribution packages. Refer to the [documentation](docs/)
for more details.

## Attribution

- This project incorporates [conda-pupa](https://github.com/dholth/conda-pupa)
by Daniel Holth, which provides the core wheel-to-conda conversion functionality.
- The conda-pypi platypus logo is by [James Turner](http://www.eruditebaboon.co.uk/).
- Ideas for improved version specifier conversion comes from [reroll](https://github.com/intentionally-left-nil/reroll) by Anil Kulkarni.

## Contributing

Please refer to [`CONTRIBUTING.md`](/CONTRIBUTING.md).
