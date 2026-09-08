# conda-pypi

```{image} _static/img/logo.png
:alt: conda-pypi logo
:align: center
:class: conda-pypi-logo
```

Welcome to the `conda-pypi` documentation!

`conda-pypi` provides better PyPI interoperability for the conda ecosystem.
It allows you to safely install Python distribution packages in conda environments by
converting them to conda format when possible, while falling back to
traditional pip installation when needed.

The tool is available in conda versions 26.5 and newer. When configured
with the `conda-pypi` channel (hosted by Anaconda) and the Rattler solver,
the tool makes pure Python packages from PyPI available through
the `conda install` command, with no extra conversion needed.

The tool also offers three commands for more advanced usage: `conda pypi install`
for safer installation of Python distribution packages with an intelligent hybrid approach,
and `conda pypi convert` for converting Python projects to `.conda` format
without installing them. The installation strategy fetches missing wheels from
PyPI and other package indexes while using packages from conda channels when available.
PyPI is the default index, and `--index-url` selects an alternative for
`conda pypi install`. The `conda pypi index` command is provided
for indexing a local directory of `.whl` files to create a local conda channel.

`conda-pypi` includes support for development workflows through editable
installations with the `-e` flag for local project directories.

`conda-pypi` also installs `EXTERNALLY-MANAGED` marker files when you install
the plugin, discouraging direct `pip` use that can destabilize conda-managed
environments.

::::{grid} 2

:::{grid-item-card} 🏡 Getting started
:link: quickstart
:link-type: doc
New to `conda-pypi`? Start here to learn the essentials
:::

:::{grid-item-card} 💡 Motivation and vision
:link: why/index
:link-type: doc
Read about why `conda-pypi` exists and when you should use it
:::
::::

::::{grid} 2

:::{grid-item-card} 🍱 Features
:link: features
:link-type: doc
Overview of what `conda-pypi` can do for you
:::

:::{grid-item-card} 📚 Commands
:link: reference/commands/index
:link-type: doc
Complete command-line interface documentation
:::

::::

::::{grid} 2

:::{grid-item-card} 🔧 Troubleshooting
:link: reference/troubleshooting
:link-type: doc
Common issues and how to resolve them
:::

:::{grid-item-card} 👩‍💻 Developer Guide
:link: developer/index
:link-type: doc
Architecture, testing, and contribution guidelines
:::

::::

```{toctree}
:hidden:

quickstart
why/index
features
modules
changelog
developer/index
reference/commands/index
reference/troubleshooting
reference/conda-channels-naming-analysis
```
