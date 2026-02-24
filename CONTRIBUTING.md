# How to contribute

You'll need a copy of `pixi` and `git` in your machine. Then:

1. Clone this repo to disk.
2. Configure conda-forge to your channels if you haven't already:
   ```bash
   conda config --add channels conda-forge
   ```
   This ensures tests can find packages from conda-forge
3. `pixi run test` to run the tests. Choose your desired Python version by picking the adequate environment.
4. `pixi run docs` to build the docs and `pixi run serve` to serve them in your browser.
5. `pixi run lint` to run the pre-commit linters and formatters.

Note: Be sure to include updates to the changelog in your pull request.
