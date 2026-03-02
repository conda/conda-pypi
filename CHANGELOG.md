# Changelog

[//]: # (current developments)

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
