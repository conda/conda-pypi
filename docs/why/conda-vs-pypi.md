# Key differences between conda and PyPI

Below, we'll go over the two key differences between conda and PyPI packaging and why
this leads to issues for users. The first problem is related to how binary distributions
are packaged and distributed and the second problem is related to the package index
and how each tool tracks what is currently installed.

## Summary

- Conda and PyPI use different strategies for building binary distributions; when
  using these packaging formats together, it can lead to difficult to debug issues.
- PyPI tools are aware of what is installed in a conda environment but when these
  tools make changes to the environment conda loses track of what is installed.
- conda relies on all packaging metadata (available packages, their dependencies, etc)
  being available upfront. PyPI only lists the available packages, but their dependencies
  need to be fetched on a package-per-package basis. This means that the solvers are
  designed to work differently; a conda solver won't easily take the PyPI metadata
  because it is not designed to work iteratively.
- PyPI names are not always the same in a conda channel. They might have a different name,
  or use a different packaging approach altogether.

## Differences in binary distributions

Conda and PyPI are separate packaging ecosystems with different packaging
formats and philosophies. Conda distributes packages as .conda and .tar.bz2
files, which can include Python libraries and pre-compiled binaries with dynamic
links to other dependencies. In contrast, PyPI provides .whl files (as defined
in [PEP 427](https://peps.python.org/pep-0427/)), which typically bundle all
required binaries or rely on system-level dependencies, as it lacks support for
non-Python dependency declarations [^1]. PyPI also supports source distributions,
though these require building during installation.

With that in mind, what are some potential ways this could break when combining the two
ecosystems together? Because wheels typically include all of their pre-compiled binaries inside
the wheel itself, this can lead to incompatibilities when used with conda packages containing
pre-compiled binaries. In the conda ecosystem, these dependencies are normally tested with
each other before being published during the build process, but the PyPI ecosystem does not test
its wheels with conda packages and therefore users are typically the first to encounter these
errors.

Some examples of these incompatibilities include symbol errors, segfaults and other difficult to debug
issues. Refer to the excellent [pypackaging-native key issues](https://pypackaging-native.github.io/#key-issues)
for even more information on this topic and specific examples.

## Differences in metadata concerning installed packages

The second relevant difference regarding how these two packaging ecosystems interact with
each other deals with how they track which packages are installed into an environment.
Inside conda environments, package metadata is saved in JSON files in a folder called
`conda-meta`. This serves as a way to easily identify everything that is currently installed
because each JSON file represents a package installed in that environment.

Tools such as `pip` that follow the Database of Installed Python Distributions
standard ([PEP 376](https://peps.python.org/pep-0376/)) do not store metadata
about installed packages in a single central database like `conda-meta`.
Instead, each installed distribution has its own `.dist-info` directory located
in `lib/<python-version>/site-packages/`, containing metadata files like
METADATA, RECORD, and INSTALLER that track the distribution's files and
installation details.

The good thing is that conda Python packages will normally install this directory
when the package is installed. This means that `pip` installations on top of an existing
conda environment will be able to tell what is already installed and resolve its dependencies
relatively well. But, after you have installed something with `pip` in that environment,
conda no longer knows exactly what is installed because `pip` did not update the contents
of the `conda-meta` folder.

This ultimately means that conda begins to lose track of what is installed in a given environment.
Not only that, `pip` and `conda` can begin to overwrite what each has placed in the
`lib/<python-version>/site-packages` folder. The more you run each tool independently,
the more likely it is that this will happen, and the more this happens, the more unstable
and prone to errors this environment becomes.

## Package metadata differences

PyPI and conda expose their packaging metadata in different ways, which results in their
solvers working differently too:

In the conda ecosystem, packages are published to a *channel*. The metadata in
each package is extracted and aggregated into a per-platform JSON file
(`repodata.json`) upon package publication. `repodata.json` contains all the
packaging metadata needed for the solver to operate, and it's typically fetched
and updated every time the user tries to install something.

In PyPI, packages are published to an *index* following the Simple Repository
API standard ([PEP 503](https://peps.python.org/pep-0503/)). The index provides
a list of all the available wheel files, with their filenames encoding some
packaging metadata (like Python version and platform compatibility). Other
metadata like the dependencies for that package need to be fetched on a
per-wheel basis. As a result, the solver fetches metadata as it goes. Modern
PyPI implementations can serve this index data in either HTML (the original PEP
503 format) or JSON ([PEP 691](https://peps.python.org/pep-0691/)) using HTTP
content negotiation.

In a nutshell:

- Conda's metadata is aggregated upfront in `repodata.json` files, providing
  solvers with comprehensive dependency information before package resolution
  begins.
- PyPI's approach has traditionally required per-package metadata fetching
  during solving, though the JSON-based Simple API for Python Package Indexes
  ([PEP 691](https://peps.python.org/pep-0691/)) now provides more structured
  metadata access that reduces this need.
- The conda solvers can work entirely from the aggregated metadata, while
  PyPI-focused solvers have typically needed to fetch additional metadata as
  solutions are explored, though this pattern is evolving with newer API
  capabilities.

So, if we wanted to integrate PyPI with conda, this represents an architectural
difference: how to adapt PyPI's per-package metadata model to conda's
expectation of comprehensive upfront metadata aggregation.

```{note}
Some solver backends (e.g. [`resolvo`](https://github.com/prefix-dev/resolvo)) do support iterative solving like in the PyPI model, but they have not been adapted for conda+PyPI interoperability.
```

## Mappings and names

Even if we had all the necessary metadata available upfront, we would face one more problem: given a Python project, the name in PyPI does not necessarily match its names in a conda channel. It's true that in a good percentage of cases they would match, but the problem arises in the edge cases. Some examples:

- A package being published with different names: [`pypa/build`](https://github.com/pypa/build) is published to PyPI as `build` but it's `python-build` in conda-forge.
- A package with names encoding versions: `PyQt` v5 is published in PyPI as `pyqt5`, but in conda-forge is simply `pyqt` with version `5` (`pyqt=5`).
- Different packages with the same name: `art` is a [popular ASCII art package](https://github.com/sepandhaghighi/art/) in PyPI but a [genomics project](https://www.niehs.nih.gov/research/resources/software/biostatistics/art) in `bioconda`.

Additionally there are other challenges like name normalization: in PyPI dashes and underscores are treated in the same way, but conda packaging considers them separate. This leads to efforts like publishing two conda packages for a given PyPI project if it contains any of these separators: PyPI's `typing-extensions` is available as both `typing-extensions` and `typing_extensions`. However these alias packages are not always published, and the separator flavor you get on the conda side is not always consistent.

## More on this topic

For an excellent overview of how Python packaging works:

- [Python Packaging - packaging.python.org](https://packaging.python.org/en/latest/overview/)

For an excellent overview of what a conda package actually is:

- [What is a conda package? - prefix.dev](https://prefix.dev/blog/what-is-a-conda-package)

[^1]: At least as of August 2025. Check [PEP 725](https://peps.python.org/pep-0725/) for a proposal external dependency metadata.
