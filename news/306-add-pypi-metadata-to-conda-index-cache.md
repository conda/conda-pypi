### Enhancements

* Add function to store pypi metadata in the conda-index cache. This will allow to seed the conda-index cache with pypi packages to include in repodata. (#276 via #306)
* Bump `conda-index` to `>=0.11.0` and regenerate the wheel test channel using `ChannelIndex.index(...)` with `repodata_v3=True`.
