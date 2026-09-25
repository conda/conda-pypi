# How to contribute

You'll need `pixi` and `git` on your machine. Then:

1. Clone this repo to disk.
2. Configure conda-forge to your channels if you haven't already:
   ```bash
   conda config --add channels conda-forge
   ```
   This ensures tests can find packages from conda-forge
3. `pixi run -e test-py310 test` to run the tests. Choose another Python version by selecting its `test-py311` through `test-py314` environment.
4. `pixi run -e docs build-docs` to build the docs and `pixi run -e docs serve-docs` to serve them in your browser.
5. `pixi run lint` to run the pre-commit linters and formatters.
6. `pixi run news` to create a news file for your Pull Request.
   ```bash
   pixi run news 476-deprecate-old-command --section "deprecations" --message "Mark old subcommand for deprecation. (#476)"
   ```

Note: Be sure to include updates to the changelog in your pull request.

The `dev` task installs this checkout in editable mode after Pixi resolves the
dependencies. Tests and docs run it automatically. Python 3.10 environments prioritize Anaconda's main channel, which still provides Python 3.10
builds of conda and conda-index. Other environments use conda-forge.
