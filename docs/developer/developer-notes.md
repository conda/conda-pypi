# Developer notes

This section contains implementation notes, technical insights, and development considerations for conda-pypi.

## PyPI Package Analysis

Example: https://pypi.org/project/torch/#files

2.5.1 e.g., torch has only wheels, no sdists. Is called pytorch in conda-land.

## Conda Integration

LibMambaSolver (used to have) LibMambaIndexHelper.reload_local_channels() used
for conda-build, reloads all file:// indices.

(Can't figure out where this is used) See also reload_channel().

```
for channel in conda_build_channels:
    index.reload_channel(channel)
```

If we call the solver ourselves or if we use the post-solve hook, we could
handle "metadata but not package data converted" and generate the final .conda's
at that time. While generating repodata from the METADATA files downloaded
separately.

We could generate unpacked `<base env>/pkgs/<package>/` directories at the
post-solve hook and skip the `.conda` archive. Conda should think it has already
cached the new wheel -> conda packages.

In the twine example we wind up converting two versions of a package from wheel
to conda. One of them might have conflicted with the discovered solution.

Hash of a regular Python package is something like py312hca03da5_0

## Environment Markers

**Two different ideas** use the word “marker” in this project:

1. PEP 668 / `EXTERNALLY-MANAGED` — marker *files* that discourage naive `pip` use (user-facing docs: [Environment marker files](../features.md#environment-marker-files)).
2. PEP 508 dependency markers — boolean expressions on individual `Requires-Dist` lines. See {doc}`marker-conversion`.

The internal implementation walks the `Marker._markers` AST directly. The AST is a nested list of `(Variable, Op, Value)` tuples interleaved with "and" / "or" strings. For example, `python_version > "3.10"` or `(python_version == "3.11" and os_name == "unix")` parses to:

```python
[
    (Variable("python_version"), Op(">"), Value("3.10")),
    "or",
    [
        (Variable("python_version"), Op("=="), Value("3.11")),
        "and",
        (Variable("os_name"), Op("=="), Value("unix")),
    ],
]
```

`_normalize_marker_clause` in {py:mod}`conda_pypi.markers` recurses over this structure and emits conda fragments for known variables (`python`, `__win`, `__linux`, etc.), combining them with `_combine_conditions`. Unknown variables produce no fragment.

`Marker._markers` from the `packaging` library is private, however there aren't other methods of getting at the parsed AST structure without reimplementing it.

## Architecture Packages

"arch" packages should be allowed.

## Build System Design

A little bit like conda-build:

Build packages from wheels or sdists or checkouts, then keep them in the local
channel for later. (But what if we are in CI?)

## Editable Installation

'editable' command:

Modern replacement for conda-build develop. Works like `pip install -e . --no-build-isolation`
