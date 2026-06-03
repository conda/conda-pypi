# Quickstart

## Installation

`conda-pypi` is a `conda` plugin that is available in your `base`
environment in conda versions 26.5 and newer.

Update your conda installation to get `conda-pypi`:

```bash
conda install --name base "conda>=26.5"
```

You can also install the plugin directly into your `base` environment:

```bash
conda install --name base conda-pypi
```

Once installed, the `conda pypi` subcommand becomes available across all your
conda environments.

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
During the beta, the `conda-pypi` channel might not appear in the Anaconda.org
web UI and some commands such as `conda search` can fail because they request
classic `repodata.json` metadata. This does not necessarily mean the channel is
down. To test the channel, use `conda install` or `conda create --dry-run` with
the Rattler solver enabled.
:::

:::{admonition} Beta
:class: warning
The conda-pypi channel is in public beta. It hosts metadata only, for pure Python wheels from PyPI. Compiled wheels are not supported at the moment.
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

## Advanced usage

You can also use the `conda pypi` command to install packages from
PyPI without using the `conda-pypi` channel. This method downloads
the package from PyPI and converts it to `.conda` format, then installs
it.

:::{note}
These instructions assume that you have done the following:

- Created and activated a conda environment
- Installed `python` and `pip` into that conda environment
:::

```bash
conda pypi install build
```

This will download and convert the `build` package from PyPI to `.conda`
format. Even though `python-build` exists on conda, the explicitly requested
Even though `python-build` exists on conda, the explicitly requested
package always comes from PyPI to ensure you get exactly what you asked for.
However, its dependencies will preferentially come from conda channels when
available.

```bash
conda pypi install some-package-with-many-deps
```

Here's where the hybrid approach really shines:
`some-package-with-many-deps` itself will be converted from PyPI, but
conda-pypi will analyze its dependency tree and:
- Install dependencies like `numpy`, `pandas`, etc. from the conda channel (if
  available)
- Convert only the dependencies that aren't available on conda channels from
  PyPI

```bash
conda pypi install --ignore-channels some-package
```

This command forces dependency resolution to use only PyPI, bypassing conda channel
checks for dependencies. The requested package is always converted from PyPI
regardless of this flag.

### Converting packages without installing

You can also convert PyPI packages to `.conda` format without installing
them:

```bash
# Convert to current directory
conda pypi convert niquests rope

# Convert to specific directory
conda pypi convert -d ./my_packages niquests rope
```

This is useful for creating conda packages from PyPI distributions or
preparing packages for offline installation.

### Development and editable installations

`conda-pypi` supports editable installations for development workflows:

```bash
# Install local project in editable mode
conda pypi install -e ./my-project/

# Preview what would be installed
conda pypi install --dry-run niquests pandas
```

### Environment protection

`conda-pypi` ships a special file called `EXTERNALLY-MANAGED` that helps
protect your conda environments from accidental pip usage that could break
their integrity. This file is automatically installed in the `base`
environment, all new environments, and existing environments that after running
a `conda pypi` command on them.

More details about this protection mechanism can be found at
{ref}`externally-managed`.

### Configuration settings

`conda-pypi` exposes conda configuration settings that can be managed with
`conda config`.

#### `conda_pypi_pip_warning`

By default, `conda-pypi` displays a warning when `pip` is detected in a conda
environment. This warning reminds you that future updates will protect environments
from using `pip` via the `EXTERNALLY-MANAGED` file defined by
[PEP 668](https://peps.python.org/pep-0668/).

To disable this warning:

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
