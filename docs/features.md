# Features

`conda-pypi` uses the `conda` plugin system to implement several features
that better improve the `conda` integration with the PyPI ecosystem. This
page is divided into basic and advanced sections to help you discover
which features are best for you.

- **Basic**: For users who just want to use conda and wheels packages
  together with no changes to their overall workflow.
- **Advanced**: For users who want to experiment with conda and wheels
  and work with cutting-edge plugin features.

## Basic features

(conda-pypi-channel)=

### The conda-pypi channel

:::{note}
The `conda-pypi` channel is free to use for all users. This channel is not subject
to the licensing requirements or payment obligations described in Section 1
of the [Anaconda Terms of Service](https://www.anaconda.com/legal/terms/terms-of-service).
:::

The `conda-pypi` channel is a public channel hosted by Anaconda
that makes pure Python packages from PyPI available through `conda install`.
After you add this channel, conda's solver can find and install these packages
alongside your regular conda packages in a single step.

For instructions on how to set up the `conda-pypi` channel, see
the {doc}`quickstart`.

:::{admonition} Limitations
:class: warning

The conda-pypi channel is designed to supplement existing conda channels,
not replace them. Users should continue to rely on channels such as `conda-forge`
for most packages. The wheel channel expands package availability
for packages that do not exist in the conda format.

Other limitations include:

- Only pure Python wheels are available. Compiled wheels are not supported.
- The security posture is the same as installing from public PyPI. Packages
are not independently vetted or scanned.
- The channel hosts metadata only. Wheel artifacts are fetched directly from
pypi.org.
:::

## Advanced features

### The `conda pypi` subcommand

This subcommand provides a safer way to install PyPI packages in conda
environments by converting them to `.conda` format when possible. It offers two
main subcommands that handle different aspects of PyPI integration.

#### `conda pypi install`

The install command takes PyPI packages and converts them to `.conda` format.
Explicitly requested packages are always installed from PyPI and converted
to `.conda` format to ensure you get exactly what you asked for. For
dependencies, `conda-pypi` chooses the best source using a
conda-first approach. If a dependency is available on conda channels, it will
be installed with `conda` directly. If not available on conda channels, the
dependency is converted from PyPI to `.conda` format.

PyPI names are mapped to conda names with a bundled Grayskull table, plus a
simple normalization rule when a package is not listed. `conda pypi convert`
can load a replacement table from a JSON file via `--name-mapping`. With
`-e` / `--editable`, a local project directory is built into a `.conda`
package and installed.

You can preview what would be installed without making changes using
`--dry-run`, install packages in editable development mode with `--editable`
or `-e`, and force dependency resolution from PyPI without using conda
channels using `--ignore-channels`.

#### `conda pypi convert`

The convert command transforms PyPI packages to `.conda` format without
installing them, which is useful for creating conda packages from PyPI
distributions or preparing packages for offline installation. You can specify
where to save the converted packages using `-d`, `--dest`, or `--output-dir`.
The command supports converting multiple packages at once and can skip conda
channel checks entirely with `--ignore-channels` to convert directly from
PyPI.

Here are some common usage patterns:

```bash
# Convert packages to current directory
conda pypi convert httpx cowsay

# Convert to specific directory
conda pypi convert -d ./my_packages httpx cowsay

# Convert without checking conda channels first
conda pypi convert --ignore-channels some-pypi-only-package

# Convert with custom name mapping
conda pypi convert --name-mapping ./mapping.json ./my-package-1.0.0-py3-none-any.whl
```

#### `conda pypi migrate-env`

The migrate-env command rewrites an `environment.yaml` file by replacing pip dependencies with equivalent conda packages sourced from a wheels channel. This is useful for transitioning existing conda environments away from pip dependencies without changing the rest of the environment definition.

By default the result is written to stdout, but you can write to a file with `--file` or rewrite the input file in-place with `--in-place`. The wheels channel to query can be overridden with `-c` / `--channel`.

Here are some common usage patterns:

```bash
# Migrate environment.yaml and print result to stdout
conda pypi migrate-env environment.yaml

# Rewrite the file in-place
conda pypi migrate-env --in-place environment.yaml

# Write to a new file
conda pypi migrate-env --file migrated.yaml environment.yaml

# Use a custom wheels channel
conda pypi migrate-env -c https://my-org.example.com/wheels environment.yaml

# Use a custom PyPI-to-conda name mapping
conda pypi migrate-env --name-mapping ./mapping.json environment.yaml
```

### PyPI-to-conda conversion engine

`conda-pypi` includes a powerful conversion engine that enables direct
conversion of pure Python wheels to `.conda` packages with proper translation of
Python package metadata to conda format. The system includes name
mapping of PyPI dependencies to conda equivalents and provides cross-platform
support for package conversion, ensuring that converted packages work
across different operating systems and architectures.

The wheel's SPDX-style `License-Expression` (or legacy `License` field) is
copied into conda metadata (`license` in `info/index.json` and `about.json`).
When the wheel lists files under PEP 639 `License-File`, those files are also
copied into `info/licenses/` in the `.conda` package (CEP 34). Resolution
checks `.dist-info/<path>` (pre-PEP 639 wheels) and `.dist-info/licenses/<path>`
(PEP 639, Metadata-Version 2.4+).

#### Dependency environment markers (PEP 508)

PyPI [environment markers](https://packaging.python.org/en/latest/specifications/dependency-specifiers/#environment-markers) are translated for the solver where possible. When building installable .conda packages from wheels, `[when="…"]` is not attached to dependency strings. The `extra == "…"` marker is split into per-extra tables, and other marker conditions are omitted from depends. See {doc}`developer/marker-conversion`.

### Wheel channels

:::{admonition} Experimental
:class: warning

This feature is experimental. It is based on a [draft CEP for Repodata Wheel
Support](https://github.com/conda/ceps/pull/145) that is still under active
discussion and subject to change.
:::

Wheel channels allow conda to resolve and install pure Python wheels directly
from channel repodata, without a separate conversion step. Each wheel appears
as a conda-compatible metadata record in the channel's repodata, and the
Rattler solver resolves dependencies across both conda packages and wheel
packages in a single solve.

If you maintain a conda channel, you can now serve Python wheels directly
alongside regular conda packages. Add your wheels to a `v3.whl` section
in `repodata.json` and point each entry at the wheel URL. `conda install`
will pick them up, resolve their dependencies, and extract them correctly,
with no pre-conversion step required.

```bash
conda install -c https://my-wheel-channel requests
```

Wheels served this way behave like any other conda package.

#### Extras and markers

Wheels in a channel can declare [dependency specifier extras](https://packaging.python.org/en/latest/specifications/dependency-specifiers/#extras)
via an `extra_depends` field in the repodata entry.

In the PyPA grammar, extras are a comma-separated list of names. Multiple extras union their requirements, and there is no reserved name meaning “all extras.” Optional extras in `extra_depends` are resolved by the Rattler solver.

### Editable package support

`conda-pypi` supports editable (development) installs for local project
directories: the project is built into a `.conda` package and installed into
the environment. This is intended for workflows where you edit code in a
checkout on disk.

Here are some common usage patterns for editable installations:

```bash
# Install local project in editable mode
conda pypi install -e ./my-project/

# Multiple local editable packages
conda pypi install -e ./package1/ -e ./package2/
```

(externally-managed)=

### Environment marker files

`conda-pypi` adds support for
[PEP-668](https://peps.python.org/pep-0668/)'s
[`EXTERNALLY-MANAGED`](https://packaging.python.org/en/latest/specifications/externally-managed-environments/)
environment marker files. These files tell `pip` and other PyPI installers
not to install or remove any packages in that environment, guiding users
towards safer alternatives.

When these marker files are present, they display a message letting users
know that the `conda pypi` subcommand is available as a safer alternative. The
primary goal is to avoid accidental overwrites that could break your conda
environment. If you need to use `pip` directly, you can still do so by adding
the `--break-system-packages` flag, though this is generally not recommended
in conda environments.
