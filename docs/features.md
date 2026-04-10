# Features

`conda-pypi` uses the `conda` plugin system to implement several features
that make `conda` integrate better with the PyPI ecosystem:

## The `conda pypi` subcommand

This subcommand provides a safer way to install PyPI packages in conda
environments by converting them to `.conda` format when possible. It offers two
main subcommands that handle different aspects of PyPI integration.

### `conda pypi install`

The install command takes PyPI packages and converts them to the `.conda` format.
Explicitly requested packages are always installed from PyPI and converted
to `.conda` format to ensure you get exactly what you asked for. For
dependencies, conda-pypi chooses the best source using a
conda-first approach. If a dependency is available on conda channels, it will
be installed with `conda` directly. If not available on conda channels, the
dependency will be converted from PyPI to `.conda` format.

PyPI names are mapped to conda names with a bundled Grayskull table, plus a
simple normalization rule when a package is not listed. `conda pypi convert`
can load a replacement table from a JSON file via `--name-mapping`. With
`-e` / `--editable`, a local project directory is built into a `.conda`
package and installed.

You can preview what would be installed without making changes using
`--dry-run`, install packages in editable development mode with `--editable`
or `-e`, and force dependency resolution from PyPI without using conda
channels using `--ignore-channels`.

### `conda pypi convert`

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

## PyPI-to-Conda Conversion Engine

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

### Dependency environment markers (PEP 508)

PyPI [environment markers](https://packaging.python.org/en/latest/specifications/dependency-specifiers/#environment-markers) are translated for the solver where possible. When building installable .conda packages from wheels, `[when="…"]` is not attached to dependency strings. The `extra == "…"` marker is split into per-extra tables, and other marker conditions are omitted from depends. See {doc}`developer/marker-conversion`.

## Wheel channels

:::{admonition} Experimental
:class: warning

This feature is experimental. It is based on a [draft CEP for Repodata Wheel
Support](https://github.com/conda/ceps/pull/145) that is still under active
discussion and subject to change.
:::

If you maintain a conda channel, you can now serve Python wheels directly
alongside regular conda packages. Add your wheels to a `v3.whl` section
in `repodata.json` and point each entry at the wheel URL. `conda install`
will pick them up, resolve their dependencies, and extract them correctly,
with no pre-conversion step required.

```bash
conda install -c https://my-wheel-channel requests
```

Wheels served this way behave like any other conda package.

### Extras and markers

Wheels in a channel can declare [dependency specifier extras](https://packaging.python.org/en/latest/specifications/dependency-specifiers/#extras)
via an `extra_depends` field in the repodata entry.

In the PyPA grammar, extras are a comma-separated list of names. Multiple extras union their requirements, and there is no reserved name meaning “all extras.” Optional extras in `extra_depends` are resolved by the Rattler solver.

## Editable Package Support

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

## `conda env` integrations

:::{admonition} Coming soon
:class: seealso

`environment.yml` files famously allow a `pip` subsection in their
`dependencies`. This is handled internally by `conda env` via a `pip`
subprocess. We are adding new plugin hooks so `conda-pypi` can handle these
in the same way we do with the `conda pypi` subcommand.
:::

(externally-managed)=

## Environment marker files

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
