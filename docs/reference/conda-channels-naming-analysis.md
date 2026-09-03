# Conda channel naming discrepancies analysis report

## Executive summary

This report analyzes naming differences between the main conda channel and conda-forge channel for Python packages.  The analysis was done by comparing the PyPI mappings between main and conda-forge channel packages
and then identifying when they, the conda package names, are different.  This analysis was done mid August 2025.

## Study overview

Channel data was downloaded from cf-graph-countyfair (grayskull_pypi_mapping.json) for conda-forge
channel and an internal Anaconda metadata source for the main channel. With both sources, containing
the conda package name and the pypi name, the following analysis was done:

```python
# main_df: Pandas Dataframe from main channel
# cf_df: Pandas Dataframe from conda-forge channel

# Merging data by PyPi Name
# main_df stores the package name as name and cf_df as conda_name so there is no collision
mdf = pd.merge(main_df, cf_df, left_on="pypi_name", right_on="pypi_name")

not_found_df = mdf[mdf.name != mdf.conda_name].sort_values(by="name")

# Because there could be other names (aliases or older names) we should check
# if each of the discrepancies also exists.

conda_search_results = {}
for x in not_found_df.conda_name:
    if x in conda_search_results:
        continue
    print(f"Looking up {x} on main...")
    # Note: In the original jupyter notebook of the analysis
    # this is what was run: query = !conda search {x}
    query = subprocess.run(["conda", "search", x], capture_output=True, text=True)
    conda_search_results[x] = query

# Find any than are also found in main (these were noted belov)
found_on_main = [
    k
    for k, v in conda_search_results.items()
    if not any("PackagesNotFoundError" in l for l in v)
]
```

## Data overview

**72 packages** were found with discrepancies between main conda channel and conda-forge channel conda
package names.  This was done by collecting information main's packages (from an internal to Anaconda
data store) and comparing this against conda-forge's cf-graph-countyfair.  The cf-graph-county-fair
is the data repository for conda-forge's automation.  This repository stores the dependency graph
and its introspection. Prefix's parselmouth repository (which is used to store similar mapping data)
was not used in this comparison.

A few of these were not listed below as the data mapping was incorrect.

## Key findings

Discrepancies fall in several categories.  There are cases where the name of the package was changed
(This, of course, has it's own challenges by having to select the 'correct' conda package).

###  Naming pattern categories

#### **Prefix/suffix standardization differences**

|#| Main Channel Name | Conda-Forge Name | PyPI Name | Notes |
|-|-------------------|-------------------|-----------|-------|
|1| `astropy` | `astropy-base` | `astropy` | |
|2| `avro-python3` | `python-avro` | `avro-python3` |  |
|3| `cufflinks-py` | `python-cufflinks` | `cufflinks` |  |
|4| `duckdb` | `python-duckdb` | `duckdb` | |
|5| `pyct-core` | `pyct` | `pyct` | main also has `pyct` |
|6| `pandera` | `pandera-core` | `pandera` | main also has `pandera-core`|
|7| `qtconsole` | `qtconsole-base` | `qtconsole` | |
|8| `seaborn` | `seaborn-base` | `seaborn` | |
|9| `spyder` | `spyder-base` | `spyder` |  |
|10| `tables` | `pytables` | `tables` | main also has `pytables` |

#### **Vendor/project name clarification**

|#| Main Channel Name | Conda-Forge Name | PyPI Name | Notes |
|-|-------------------|-------------------|-----------|-------|
|1| `analytics-python` | `segment-analytics-python` | `segment-analytics-python` |  |
|2| `authzed` | `authzed-py` | `authzed` | main also has `authzed-py`|
|3| `jupyterlab-variableinspector` | `lckr_jupyterlab_variableinspector` | `lckr-jupyterlab-variableinspector` | |
|4| `performance` | `pyperformance` | `pyperformance` | main also has `pyperformance` |
|5| `prince` | `prince-factor-analysis` | `prince` | |
|6| `pywget` | `python-wget` | `wget` |  |
|7| `lit` | `lit-nlp` | `lit` ||

#### **Hyphen vs underscore standardization**

|#| Main Channel Name | Conda-Forge Name | PyPI Name | Notes |
|-|-------------------|-------------------|-----------|-------|
|1| `argon2_cffi` | `argon2-cffi` | `argon2-cffi` | main also has `argon2-cffi` |
|2| `cached-property` | `cached_property` | `cached-property` |  |
|3| `et_xmlfile` | `et-xmlfile` | `et-xmlfile` |  |
|4| `eval-type-backport` | `eval_type_backport` | `eval-type-backport` |  |
|5| `flask-json` | `flask_json` | `flask-json` |  |
|6| `importlib-resources` | `importlib_resources` | `importlib-resources` |  main also has `importlib_resources` |
|7| `lazy_loader` | `lazy-loader` | `lazy-loader` |  |
|8| `sarif_om` | `sarif-om` | `sarif-om` |  |
|9| `service_identity` | `service-identity` | `service-identity` |  |
|10| `setuptools-scm-git-archive` | `setuptools_scm_git_archive` | `setuptools-scm-git-archive` | main also has `setuptools_scm_git_archive` |
|11| `streamlit-option-menu` | `streamlit_option_menu` | `streamlit-option-menu` |  |
|12| `typing-extensions` | `typing_extensions` | `typing-extensions` |  |

#### **Package family consolidation**

|#| Main Channel Name | Conda-Forge Name | PyPI Name | Notes |
|-|-------------------|-------------------|-----------|-------|
|1| `diffusers-base` | `diffusers` | `diffusers` | main also has `diffusers` |
|2| `diffusers-torch` | `diffusers` | `diffusers` |  |
|3| `gql-with-aiohttp` | `gql` | `gql` |  |
|4| `gql-with-all` | `gql` | `gql` |  |
|5| `gql-with-botocore` | `gql` | `gql` |  |
|6| `gql-with-httpx` | `gql` | `gql` |  |
|7| `gql-with-requests` | `gql` | `gql` |  |
|8| `gql-with-websockets` | `gql` | `gql` |  |
|9| `keras-base` | `keras` | `keras` | main also has `keras` |
|10| `keras-gpu` | `keras` | `keras` | main also has `keras` |
|11| `pandera-base` | `pandera-core` | `pandera` | This is weird as conda-forge maintains both pandera and pandera-core which point to the same PyPI project pandera. |
|12| `pandera-dask` | `pandera-core` | `pandera` |  |
|13| `pandera-fastapi` | `pandera-core` | `pandera` |  |
|14| `pandera-geopandas` | `pandera-core` | `pandera` |  |
|15| `pandera-hypotheses` | `pandera-core` | `pandera` |  |
|16| `pandera-io` | `pandera-core` | `pandera` |  |
|17| `pandera-modin` | `pandera-core` | `pandera` |  |
|18| `pandera-modin-dask` | `pandera-core` | `pandera` |  |
|19| `pandera-modin-ray` | `pandera-core` | `pandera` |  |
|20| `pandera-mypy` | `pandera-core` | `pandera` |  |
|21| `pandera-pyspark` | `pandera-core` | `pandera` |  |
|22| `pandera-strategies` | `pandera-core` | `pandera` |  |
|23| `pytorch-cpu` | `pytorch` | `torch` | Old main variants, main now uses pytorch. |
|24| `pytorch-gpu` | `pytorch` | `torch` | Old main variants, main now uses pytorch. |
|25| `uvicorn-standard` | `uvicorn` | `uvicorn` | main also has `uvicorn` |


### Impact analysis

- There are discrepancies even within channels (pandera and pandera-core)
- There are very few discrepancies between the two channels.  Main has more than 2k different PyPI projects and there are only about 20 real differences.
- Because of main's longevity, there are older packages that are no longer maintained as main seems to be moving to use conda-forge package names whenever possible.

## Research questions for further investigation

- Is there disagreement among cf-graph-countyfair and parselmouth?
  - Would we expect it to be very significant if there was?
- Should there be an effort to identify packages that are no longer current?
  - This is for cases where the conda package name has changed within a channel.

## Recommendations

- Because of the few discrepancies, conda-pypi could get away with using conda-forge mapping with little impact.
- As we move forward to a sustainable solution (a continually updated ecosystem mapping), they should be on a channel by channel basis.
- For the short term MVP, conda-pypi should hard code as a long-term sustainable solution is decided on and implemented.

## Conclusion

There are very few instances of name differences between main and conda-forge.  Though it would be optimal to have an index by channel, in the short term
conda-pypi could just use conda-forge mappings.  For extra coverage, we could hard code, the small list of exceptions found by this report.
