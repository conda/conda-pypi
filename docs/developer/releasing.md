# Releasing conda-pypi

Here are the steps for creating a new conda-pypi release. Before
you start, make sure that you have access to create tags and
releases on the conda/conda-pypi repo. If you have the ability
to merge pull requests, then you are probably good to go.

## 1. Cut the release on Github

Navigate to the github release page for the repo: https://github.com/conda/conda-pypi/releases/new.

Input the following information:
**Tag**: select create tag, and add the target version (for example `0.4.0`)
**Target**: should be the `main` branch
**Release title**: should the the version number (for example `0.4.0`)
**Release notes**: can select the `Generate release notes` button. Be sure to edit the generated notes for brevity and clarity. For example, remove all the pre-commit bot changes.

Ensure the `Set as the latest release` check box is ticked. And ensure the `Set as a pre-release` check box **is not** ticked.

Click the green `Publish release` button.

### 1.b Ensure the build completed successfully

Navigate to the [actions tab](https://github.com/conda/conda-pypi/actions).
You should be able to see the `Publish to PyPI` workflow with title matching
the release number from earlier. Ensure that this workflow completes successfully.

### 1.c Ensure the package is available on PyPI

Check that the PyPI package has been updated at https://pypi.org/project/conda-pypi/.
You should see that version matches the release version and that the wheel is available
in the [download files](https://pypi.org/project/conda-pypi/#files) section.

Try out installing it locally:
```
# create an activate a fresh conda environment
$ conda create -n test-conda-pypi python=3.13
$ conda activate test-conda-pypi

# install the conda-pypi package with pip
$ pip install conda-pypi==<version>

# ensure that we have the right version
$ pip list | grep conda-pypi
conda-pypi              0.4.0

$ python -c "import conda_pypi; print(conda_pypi._version.version)"
0.4.0
```

## 2. Update the conda-forge/conda-pypi-feedstock

Next we'll need to make sure the newest version is available on
conda-forge. This happens on the conda forge repo [conda-pypi-feedstock](https://github.com/conda-forge/conda-pypi-feedstock).

There are 2 options here:
  1. Wait for the conda-forge bot to automatically submit a pull request to update the package.
  2. If the release also requires updates to the recipe, submit a new PR to the feedstock to update the recipe accordingly.
