# Changelog

[//]: # (current developments)

## 0.11.0 (2026-07-03)

### Enhancements

* Add a `conda pypi index <dir>` subcommand that creates a conda channel from a collection of local wheel files. (#410)
* Add `wheels_local_channel` pytest fixture that builds and serves a fully offline
conda wheel channel from `tests/pypi_local_index/` using `conda pypi index`. (#433)

### Bug fixes

* Fix direct `.whl` install `info/index.json` metadata: `fn` is the wheel basename on disk and `build` is derived from WHEEL tags (normalizing noarch tags to `py3_none_any_0` to match repodata v3), fixing lockfile restore mismatches. (#417 via #420)
* Restore visibility of the conda-pypi beta tip at default conda verbosity by logging it at WARNING instead of INFO. (#442 via #443)

### Docs

* Switch to using the new on-demand release process, based on the release process that was being used for conda-pypi. (#414)
* Document installed wheel `index.json` `fn` and `build` fields in the wheel channels guide. (#420)
* Add documentation for the new `conda pypi index` command. (#430)

### Other

* Enable infrastructure-managed Dependabot configuration via conda/infrastructure templates. (#418)

### Contributors

* @danyeaw
* @jezdez
* @ForgottenProgramme
* @ryanskeith
* @conda-bot
* @dependabot[bot]
* @pre-commit-ci[bot]



## 0.10.1 (2026-06-12)

### Docs

* Update the docs landing page to focus on `conda install` workflows. (#398 via #405)

### Other

* Remove `conda-pypi-post-install-create` post install plugin. (#408)

### Contributors

* @kathatherine
* @soapy1
* @pre-commit-ci[bot]



## 0.10.0 (2026-06-09)

### Enhancements

* Populate additional `info/about.json` fields (`home`, `dev_url`, `doc_url`, `channels`, `extra.recipe`, `extra.generator`) when converting PyPI projects, and truncate `description` to the first paragraph to avoid embedding the full README + CHANGELOG. (#343)
* Add `external-packages` health check for `conda doctor` to detect packages installed from PyPI and offer `conda doctor --fix` to reinstall eligible packages from configured conda channels. (conda/conda#15582 via #347)
* Add descriptions to Pixi tasks for development. (#368)
* Remove the CLI entry point because a CLI doesn't make sense for a plugin. (#327 via #370)
* Add `conda_pypi_pip_warning` conda setting to enable or disable the warning shown when pip appears in conda environments. (#375 via #376)
* Refocus the pip warning into a short conda-pypi beta tip. (#385)
* Add `--dry-run`, `--yes`, and repeated `--editable` support to editable installs. (#392 via #401)

### Docs

* Clarify that the `conda-pypi` channel may not appear in the Anaconda.org web UI
  and that `conda search` can fail during the beta because it requests classic
  `repodata.json` metadata. (#382 via #384)
* Add Zulip instead of Element and Discourse links (#311 via #369).
* Update command line help text, documentation to clarify that `conda pypi
  install --editable PROJECT` creates and installs a `.conda` package with the
  contents of a [PEP 660 "editable wheel"](https://peps.python.org/pep-0660/),
  linking `PROJECT` into the target conda environment. (#390 via #391)
* Add conda-pypi platypus logo. (#394)

### Contributors

* @danyeaw
* @dholth
* @jaimergp
* @jezdez
* @ForgottenProgramme
* @pya made their first contribution in https://github.com/conda/conda-pypi/pull/368
* @travishathaway
* @conda-bot
* @dependabot[bot]
* @pre-commit-ci[bot]



## 0.9.0 (2026-05-14)

### Enhancements

* Add upload timestamps to PyPI metadata conversion to repodata. (#341 and #360)
* Disable `EXTERNALLY-MANAGED` file placement during the community beta period. Instead, log an informational notice about upcoming pip protection when environments with pip are created or updated. (#353 via #352)

### Bug fixes

* Add trailing newline in dist-info `INSTALLER`. (#338)
* Fix `store_pypi_metadata` causes re-extraction of all virtual wheel packages. (#340 via #341)
* Fix `pypi_to_repodata` using wrong source for `fn` field. The wheel filename is now taken from the URL entry instead of the package info dict. (#355 and #360)

### Deprecations

* The `EXTERNALLY-MANAGED` file will be re-enabled in a future release once migration tooling is available. (#353 via #352)

### Docs

* Update documentation to include information on the `conda-pypi` channel. (#356)
* Update documentation formatting for consistency. (#356)

### Other

* Drop the direct `conda-rattler-solver` dependency and use `context.plugin_manager.get_cached_solver_backend()` to delegate to whatever solver backend is configured. (#350)

### Contributors

* @danyeaw
* @dholth
* @jezdez
* @kathatherine made their first contribution in https://github.com/conda/conda-pypi/pull/356
* @conda-bot
* @dependabot[bot]
* @pre-commit-ci[bot]



## 0.8.0 (2026-04-21)

### Enhancements

* Add function to store pypi metadata in the conda-index cache. This will allow to seed the conda-index cache with PyPI packages to include in repodata. (#276 via #306)
* Bump `conda-index` to `>=0.11.0` and regenerate the wheel test channel using `ChannelIndex.index(...)` with `repodata_v3=True`. (#306)
* Convert wheel->conda directly without extracting the wheel to the temporary directory. Stricter separation of elements between `pkg-` and `info-` elements of the `.conda` archive. (#324)

### Bug fixes

* Fix license metadata extraction from wheel METADATA files. The code was using underscore keys (`license_expression`, `license`) but `email.message.Message` requires hyphen keys matching the actual METADATA headers (`License-Expression`, `License`). (#318)
* Fix nested license directory issue where license files ended up at `info/licenses/licenses/LICENSE` instead of `info/licenses/LICENSE` when wheels use the PEP 639 layout. (#322)
* Fix converted conda packages contain a root path. (#317 via #324)

### Other

* Enable "sort imports" lint. (#325)

### Contributors

* @agriyakhetarpal
* @danyeaw
* @dholth
* @jezdez
* @soapy1
* @conda-bot
* @danpetry
* @pre-commit-ci[bot]



## 0.7.1 (2026-04-16)

### Bug fixes

* Fix hardcoded Python paths in entry point scripts from `conda pypi convert`. Entry-point scripts are now handled exclusively via `info/link.json` (CEP-34), so conda generates them at install time with the correct prefix. (#310)

### Other

* Refactor wheel installation to use PyPA `installer` destination APIs directly (no custom subclass) and require `installer>=1`. (#307)

### Contributors

* @agriyakhetarpal
* @danyeaw
* @jezdez
* @pre-commit-ci[bot]



## 0.7.0 (2026-04-10)

### Enhancements

* Copy wheel files listed in PEP 639 ``License-File`` metadata into ``info/licenses/`` when building conda packages. (#300)

### Bug fixes

* Improve missing dependency `builder.get_requires_for_build(distribution)`
  detection, installation when building Python packages. (#281)
* Drop redundant per-wheel `record_version` from repodata package records. (#289)

### Docs

* Clarify that `conda pypi install -e` is for local project paths only, not pip-style VCS requirement URLs. (#295)

### Other

* Fix test workflow change detection on push and tag events by checking out the repo for paths-filter. (#287)
* Drop skipped tests that targeted `git+https` editable installs. (#295)

### Contributors

* @danyeaw
* @dholth
* @dependabot[bot]
* @pre-commit-ci[bot]



## 0.6.0 (2026-03-30)

### Enhancements

* Update local wheel-channel test repodata to `v3.whl`, `extra_depends`, and normalized `when` conditions. (#273)
* Add PEP 508 marker conversion for repodata (`v3.whl`) entries with `[when=…]`. (#279)

### Bug fixes

* Fix missing dependency on `conda-package-streaming`. (#272)

### Contributors

* @agriyakhetarpal
* @danyeaw
* @kenodegard
* @pre-commit-ci[bot]



## 0.5.0 (2026-03-02)

### Enhancements

* Add support for injecting tests for `conda pypi convert` (#242)
* Add `--name-mapping` option to supply a custom PyPI-to-conda name mapping file, overriding the built-in mapping (#253)
* Add tests for extra dependency specifiers in repodata (#259)

### Bug fixes

* Fix installing wheels that use the `headers` data scheme (#246)
* Fix wheel hashes stored in conda metadata being base64-encoded instead of hex, which caused errors with conda-rattler-solver (#250)
* Fix installing wheels that include `data` and `scripts` schemes (#256)

### Docs

* Add release process at RELEASE.md (#239)
* Add docs for `conda install` with a channel containing wheels (#259)

### Contributors

* @agriyakhetarpal made their first contribution in <https://github.com/conda/conda-pypi/pull/246>
* @danyeaw
* @jezdez
* @soapy1
* @tombenes made their first contribution in <https://github.com/conda/conda-pypi/pull/253>
* @conda-bot
* @danpetry made their first contribution in <https://github.com/conda/conda-pypi/pull/242>
* @dependabot[bot]
* @pre-commit-ci[bot]



## [0.4.0] - 2026-02-04

### Added

- Support converting wheels to conda packages from the CLI (#215)
- Add `conda pypi install --editable <path>` and `conda pypi convert` commands (#145)
- Add codspeed benchmarks for performance tracking (#163)
- Support Python 3.10, 3.11, 3.12, 3.13, and 3.14 (#148, #237)
- Add canary testing with conda development builds (#237)
- Add assertions for the absence of `.pyc` files in converted packages (#216)
- Add CODEOWNERS file for automatic team assignment (#172)
- Add test repodata server for testing installations with repodata v3 (#207)

### Changed

- Use rattler solver for faster dependency resolution (#176)
- Use `CondaPackageExtractor` plugin hook for wheel extraction (#217)
- Adopt code from `anaconda/conda-whl-support` into `conda-pypi` (#154)
- Replace pip subprocess with `installer` library for wheel unpacking (#149)
- Extend `installer` to also install data files from wheels (#153)
- Rename `--override-channels` to `--ignore-channels` for clarity (#178)
- Update URLs from `conda-incubator` to `conda` organization (#225)
- Call `add_whl_support` on its own, without a plugin (#165)
- Respect conda JSON output setting (#206)
- Require conda >=26.1.0 (#230)

### Fixed

- Fix `FileNotFoundError` during environment creation (#219)
- Fix install errors for packages requiring hyphen normalization e.g. `huggingface-hub` -> `huggingface_hub` .(#212)
- Fix conda-meta JSON filename format for wheel packages (#170)
- Fix "conda-index not found" error. Drop pypi-simple dependency. (#136)
- Fail fast when no compatible wheels are available (#157)
- Fix some deprecation warnings (#162)

### Removed

- Drop Python 3.9 support (#148)
- Remove `list` hook (#146)
- Remove unused dependencies (#196)
- Remove monkeypatched `PrefixData._load_single_record` (#177)

## [0.3.0] - 2025-10-07

See [GitHub Release](https://github.com/conda/conda-pypi/releases/tag/0.3.0) for details.

## [0.2.0] - 2024-05-15

See [GitHub Release](https://github.com/conda/conda-pypi/releases/tag/0.2.0) for details.

## [0.1.1] - 2024-03-20

See [GitHub Release](https://github.com/conda/conda-pypi/releases/tag/0.1.1) for details.

## [0.1.0] - 2024-03-15

Initial release.
