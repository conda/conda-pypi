# Motivation and vision

Although very common among conda users, using `conda` and PyPI (i.e. `pip`) together
can under certain circumstances cause difficult to debug issues and is currently not
seen as 100% stable. `conda-pypi` exists as a solution for creating a better experience
when using these two packaging ecosystems together. Here, we give a high-level overview
of why this conda plugin exists and finish by outlining our strategies for combining
the use of both conda and PyPI.

## The vision

`conda-pypi` aims to make it easier and safer to add PyPI packages to existing conda environments.
We acknowledge that we cannot solve all problems, specifically as they relate to
binary distributions of packages, but we believe we can provide users with a way to safely
install pure Python packages in conda environments.

## The details

To provide a thorough explanation of the problem and our proposed solutions, we have organized
this section of the documentation into the following pages:

- [Key Differences between conda and PyPI](conda-vs-pypi.md)
  gives you a firm understanding of the problems that occur when using conda and PyPI together.
- [Existing Strategies](existing-strategies.md) shows how users currently deal with
  limitations of using conda and PyPI together.
- [Addressing these Issues with conda-pypi](potential-solutions.md)
  explains how this plugin can improve the user experience of mixing these two packaging
  ecosystems.

```{toctree}
:hidden:

conda-vs-pypi
existing-strategies
potential-solutions
```
