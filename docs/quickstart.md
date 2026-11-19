# Quickstart

## Installation

`conda-pypi` is a `conda` plugin that is available in your `base`
environment in conda versions 26.5 and newer.

Update your conda installation to get `conda-pypi`:

```bash
conda self update
```

## Set up the `conda-pypi` channel

:::{note}
The `conda-pypi` channel is free to use for all users. This channel is not subject
to the licensing requirements or payment obligations described in Section 1
of the [Anaconda Terms of Service](https://www.anaconda.com/legal/terms/terms-of-service).
:::

The `conda-pypi` channel is a public channel hosted by Anaconda
that makes pure Python packages from PyPI available through `conda install`.
When you add this channel, conda's solver can find and install these packages
alongside your regular conda packages in a single step.

To enable the `conda-pypi` channel, configure the Rattler solver, add the channel, and
reset channel priority to its default (flexible):

```bash
conda config --set solver rattler
conda config --append channels conda-pypi
conda config --set channel_priority flexible
```

With this configuration, `conda install` can resolve dependencies across both
regular conda packages and wheel packages in a single solve. When a wheel
package is selected, conda downloads the artifact directly from PyPI and
installs it into the environment while tracking it like any other conda
package.

:::{note}
Note that the `conda-pypi` channel is currently name-mapped to `conda-forge`, not `defaults`. You may need to add `conda-forge` to your channels list for some solves to succeed.
:::

:::{admonition} Limitations
:class: warning
The `conda-pypi` channel hosts metadata only, for pure Python wheels from PyPI. Compiled wheels are not supported at the moment.
The security posture is the same as installing from public PyPI. For more
details, see {ref}`conda-pypi-channel`.
:::

## Remove the `conda-pypi` channel

To disable access to the `conda-pypi` channel, run the following command:

```bash
conda config --remove channels conda-pypi
```

To view your current channels:

```bash
conda config --show channels
```

You can continue to use the Rattler solver without the `conda-pypi` channel,
but to change your solver back to the default solver (libmama), run the
following command:

```bash
conda config --set solver libmama
```

## Basic usage

`conda-pypi` provides several {doc}`features`. The most basic usage
involves using the `conda-pypi` channel and using `conda install`
to add packages.

:::{note}
These instructions assume that you have done the following:

- Created and activated a conda environment
- Added the `conda-pypi` channel to your `.condarc` file
- Configured your solver to be the rattler solver
- Have a conda channel in your `.condarc` file
:::

Use `conda install` to install a package (for example, `django-modern-rest`):

```bash
conda install django-modern-rest
```

This will download and unpack `django-modern-rest` from PyPI and
install it as a native wheel (`.whl`) file.
The dependencies of `django-modern-rest` will be installed from
the conda channel when available. For example, `django-modern-rest` depends on
`django` and `typing_extensions`. If both are available in your conda channel, those
dependencies will be installed from conda rather than PyPI.

### Package names

`conda install` uses conda package names, not PyPI project names. When a PyPI
project appears under a different conda name, install it by the conda
name. For example, conda-forge publishes the PyPI project
`jupyterlab-code-formatter` as `jupyterlab_code_formatter`:

```bash
conda install jupyterlab_code_formatter
```

If a solve fails with `PackagesNotFoundInChannelsError`, check the package name
on [anaconda.org](https://anaconda.org). The `conda pypi` subcommands accept
PyPI names and translate them; `conda install` requires the conda name.

## Advanced usage

:::{admonition} `conda pypi install` is pending deprecation
:class: warning

The `conda pypi install` command is pending deprecation and will be removed in version 27.9. Use `conda install` with `conda-pypi` channel configuration instead. The command remains the only way to install editable local projects with `-e`, and it supports `--index-url` and `--ignore-channels`.
:::

You can also use the `conda pypi install` command without the `conda-pypi`
channel. It downloads missing wheels from PyPI and other package indexes,
converts them to `.conda` format, and installs them. Use `--index-url` to select
another index for wheel downloads, including missing dependencies. Repeat the
option to search multiple indexes. This replaces the default
PyPI index list. Use `--ignore-channels` to fetch wheels without searching the
configured conda channels first.

:::{note}
These instructions assume that you have done the following:

- Created and activated a conda environment
- Installed `python` and `pip` into that conda environment
:::

```bash
# Use a private package index instead of PyPI
conda pypi install --index-url https://example.com/simple some-package

# Fetch a wheel without searching conda channels first
conda pypi install --ignore-channels some-package
```

### Converting packages without installing

You can also convert Python projects to `.conda` format without installing
them:

```bash
# Convert to current directory
conda pypi convert niquests rope

# Convert to specific directory
conda pypi convert -d ./my_packages niquests rope
```

This is useful for creating conda packages from Python distributions or
preparing packages for offline installation.

### Indexing a local wheel directory

If you have a collection of `.whl` files locally, you can turn the
directory into a conda channel using `conda pypi index`. Wheels must sit in per-package subdirectories (not directly in the channel root), and only pure Python (`py3-none-any`) wheels are indexed.

```
my_wheels/
  requests/
    requests-2.32.0-py3-none-any.whl
```

```bash
conda pypi index path/to/my_wheels/
```

Once indexed, use it as a regular local channel:

```bash
conda install -c file:///path/to/my_wheels some-package
```


### Development and editable installations

`conda-pypi` supports editable installations for development workflows:

```bash
# Install local project in editable mode
conda pypi install -e ./my-project/

# Preview an editable install without changing the environment
conda pypi install --dry-run -e ./my-project/

# Install multiple local projects in editable mode
conda pypi install -e ./package1/ -e ./package2/
```

### Environment protection

`conda-pypi` includes support for a special file called `EXTERNALLY-MANAGED`
that can help protect conda environments from accidental pip usage that could
break their integrity. `conda-pypi` does not automatically add this file to
conda environments, since doing so would break existing pip-based workflows.

More details about this protection mechanism can be found at
{ref}`externally-managed`.

### Configuration settings

`conda-pypi` exposes conda configuration settings that can be managed with
`conda config`.

#### `conda_pypi_pip_warning`

By default, `conda-pypi` displays a short tip when a conda transaction
newly installs `pip` into an environment. The tip is not shown on `pip`
upgrades, or on later installs into an environment that already has `pip`.
It points to the conda-pypi docs for installing packages from PyPI with conda.

To disable this tip:

```bash
conda config --set plugins.conda_pypi_pip_warning false
```

To re-enable it:

```bash
conda config --set plugins.conda_pypi_pip_warning true
```

You can also set this in your `.condarc` file:

```yaml
plugins:
  conda_pypi_pip_warning: false
```
