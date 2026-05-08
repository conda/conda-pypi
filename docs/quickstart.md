# Quick start

## Installation

`conda-pypi` is a `conda` plugin that needs to be installed next to
`conda` in the `base` environment. Starting with `conda` 26.5.0, it is installed
by default. However, you can also install it manually:

```bash
conda install -n base conda-pypi
```

The `conda-pypi` channel is configured automatically on install. For the main
functionality, set the solver:

```bash
conda config --set solver rattler
conda config --set channel_priority flexible
```

Once installed, the `conda pypi` subcommand also becomes available across all your
conda environments.

## Basic usage

`conda-pypi` provides several {doc}`features`. The main functionality is
accessed through the normal `conda install` command:

### Native PyPI package support

```bash
conda install django-modern-rest
```

This will natively install the wheels for `django-modern-rest` from PyPI to your current
environment. Since it is a native installation served by metadata from the `conda-pypi`
channel, all other features of conda should work the same as installing any other
`.conda` package.

### Installing PyPI packages through conversion

Assuming you have an activated conda environment named `my-python-env` that
includes `python` and `pip` installed, and a configured conda channel, you can
use `conda pypi install` like this:

```bash
conda pypi install niquests
```

This will download and convert `niquests` from PyPI to `.conda` format
(since it was explicitly requested), but install its dependencies from
the conda channel when available. For example, if `niquests` depends on
`urllib3` and `certifi`, and both are available on the conda channel, those
dependencies will be installed from conda rather than PyPI.

```bash
conda pypi install build
```

This will download and convert the `build` package from PyPI to `.conda`
format. Even though `python-build` exists on conda, the explicitly requested
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

This forces dependency resolution to use only PyPI, bypassing conda channel
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

## Uninstallation

The `conda-pypi` channel mapping is removed automatically when the package is
uninstalled. To also revert solver settings:

```bash
conda config --remove-key solver
conda config --remove-key channel_priority
```
