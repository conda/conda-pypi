# Existing strategies

There are currently only a handful of patterns that are considered safe
when installing PyPI packages inside a conda environment. We list these
scenarios below:

## Only install Python & pip inside conda environments

In this scenario, you only install Python and `pip` inside of a clean
conda environment. Here, we simply use conda as an environment manager and
let `pip` manage the project dependencies.

This is what that typically looks like:

```console
$ conda create -n pip-environment python=3.10 pip
$ conda activate pip-environment
$ pip install ...
```

## Editable installs

In this scenario, `conda` provides all the dependencies of a given package.
Then that package is installed on top in editable mode, without addressing dependencies
to make sure we don't accidentally overwrite conda files:

```console
$ git clone git@github.com:owner/package.git
$ conda create -n editable-install package --deps-only
$ conda activate editable-install
$ pip install -e . --no-deps
```

## Package your PyPI dependencies as conda packages

This is the safest option in terms of ensuring maximum stability, but it is
also the most time-consuming. Maintaining a separate conda package can be a cumbersome
process and requires continued attention as the newer versions of the package
are released.

For those who want to choose this approach, tools like [Grayskull](https://conda.github.io/grayskull/)
exist to make it easier to transform a Python package into a conda package recipe.
