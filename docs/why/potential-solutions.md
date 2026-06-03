# Potential solutions

So far, we have outlined why these packaging ecosystems do not always work together
well and a couple strategies users have used in the past to overcome them. How exactly
does the `conda-pypi` plugin plan on addressing them? Below are a couple of methods
we've discussed to address these issues.

## Native wheel installation from a conda channel

When a user configures the `conda-pypi` channel and uses the Rattler solver,
conda can install pure Python wheels directly without having to convert
them to `.conda` format first.

In this approach, wheel metadata is published directly in a conda channel's `repodata.json`
under a `v3.whl` section. Each wheel appears as a metadata record alongside regular conda
packages, so the solver sees both package types as a single dependency graph. When the
solver selects a wheel, conda downloads the artifact from PyPI and unpacks it into the
environment at install time using conda's package extraction hook. This means that
no local conversion to the `.conda` format is needed.

For setup instructions for the `conda-pypi` channel, see the {doc}`../quickstart`.

## On-the-fly conversion of PyPI wheels to conda packages

The inspiration for this approach initially started with the [conda-pupa](https://github.com/dholth/conda-pupa)
project. The philosophy used here is that we can simply convert a wheel from PyPI into a conda
package and cache it on the host locally. In conda, it's straightforward to configure multiple channels
to be used when installing packages, and by default, a "local" channel is included. As `conda-pypi`
is run, it will begin transforming and caching wheels from PyPI into the conda packages which
are then saved in this local channel.

This is the approach we currently feel most confident with implementing.

## Analyze the dependency tree of your PyPI package

In this approach, we run `pip` with the `--dry-run` option and analyze the proposed solution. Of those packages,
we see which ones are already available on the configured conda channels and install them with `conda` proper.
For the ones that are not available, we pass them to `pip install --no-deps` and hope for an ABI compatible setting.

This was an approach we initially tried but then abandoned in favor of the "conda-pupa" approach.
