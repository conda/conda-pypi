# PEP 508 marker conversion

This page documents how conda-pypi translates PEP 508 environment markers for repodata and for `.whl` → `.conda` conversion, and how that interacts with conda's `MatchSpec`. For stability expectations of wheel repodata and the `v3.whl` channel layout, see the Wheel channels section in {doc}`features`.

## Context

Conda does not yet support `[when="…"]` conditional syntax on dependency strings, nor serialized optional-extras forms on `MatchSpec` (for example bracket spellings such as `[extras=[…]]`).

PyPI [environment markers](https://packaging.python.org/en/latest/specifications/dependency-specifiers/#environment-markers) (`python_version`, `sys_platform`, `extra`, and related variables) are not valid conda `MatchSpec` syntax on their own. For wheel repodata from {py:func}`conda_pypi.pypi_metadata.pypi_to_repodata`, conda-pypi does emit `[when="…"]` on dependency strings and `extra_depends` tables so that the Rattler solver can use them. The inner condition is JSON-encoded (`json.dumps`) so nested quotes are safe.

When building `.conda` packages from wheel `METADATA` ({py:func}`conda_pypi.translate.requires_to_conda`), markers are not encoded as `[when="…"]` on `depends`. The PEP 508 marker `extra == "…"` is split into the per-extra requirement map. Other marker dimensions are omitted from `depends`.

Translation does not evaluate markers against the build machine at conversion time. Output is shaped for conda-style metadata and repodata.

Additionally, this topic only pertains to dependency markers, not marker files per [PEP 668 `EXTERNALLY-MANAGED`](../features.md#environment-marker-files).

## Optional dependency extras

In the context of environment markers above, one of them is called `extra`. For example, `extra == "dev"` in a condition such as `requests ; extra == "dev"` means the dependency is only active when the package's own dev optional group is installed. The separate concept of optional dependency extras is described below.

Syntax such as `httpx[cli]` denotes PEP 508 optional extras on the dependency name. This syntax means that we want `httpx` with an optional group of dependencies called `cli`. The [dependency specifier grammar](https://packaging.python.org/en/latest/specifications/dependency-specifiers/) allows a comma-separated list of extra names.

When doing wheel to conda package conversion, the brackets are dropped, for example `httpx[cli]>=0.24` becomes `httpx>=0.24`. {py:func}`conda_pypi.translate.requires_to_conda` keeps only the base package name and version specifier.

For creating repodata, the bracket syntax is supported, for example `httpx[cli]>=0.24` is kept as is. This is done by {py:func}`conda_pypi.pypi_metadata.pypi_to_repodata` which handles the bracket extras syntax (including {py:func}`conda_pypi.markers.dependency_extras_suffix` for optional dependency extras).

## PEP 508 variables

The table is ordered by how often each variable appears in PyPI dependency metadata (census from PyPI, January 2025). The Supported column summarizes whether `_normalize_marker_clause` in {py:mod}`conda_pypi.markers` emits a fragment for `when`, partially handles it, or omits it. The Notes column describes what is translated or why it is skipped.

| Marker variable | ~Uses on PyPI | Supported | Notes |
| --- | ---: | :--- | --- |
| `python_version` | 2,034,408 | Yes | Emits `python…` fragments. `not in "a, b"` becomes multiple `python!=…` terms. |
| `platform_system` | 243,706 | Yes | Maps known literals to virtual packages (`__win`, `__linux`, `__osx`, …). |
| `sys_platform` | 223,549 | Partial | Same mapping as `platform_system`. Partial handling of `!=` (e.g. `!= "win32"` → `__unix`). |
| `platform_machine` | 145,549 | No | No fragment. Limited alignment between PEP 508 arch strings and conda virtuals. |
| `platform_python_implementation` | 89,434 | Partial | Common interpreters omitted so noarch paths are not over-restricted. |
| `python_full_version` | 25,840 | Yes | Same rules as `python_version`. |
| `implementation_name` | 22,158 | Partial | Same general approach as `platform_python_implementation`. |
| `os_name` | 17,294 | Partial | `nt` / `windows` → `__win`, `posix` → `__unix`. Partial `!=` handling. |
| `platform_release` | 6,316 | No | Omitted. |
| `platform_version` | 241 | No | Omitted. |
| `implementation_version` | 44 | No | Omitted. |
| `extra` | — | Yes | Drives `extra_depends` / extras map. In that repodata path, remaining conditions may attach as `[when="…"]` on that dependency (not a conda `MatchSpec` feature). |

Variables not listed produce no fragment. Boolean `and` / `or` use `_combine_conditions` to retain a usable branch when one side cannot be translated.

Omissions are mostly intentional, for example virtual-package coverage is bounded, architecture strings map poorly to conda subdirs, and the default stance is slightly permissive on noarch-style metadata rather than incorrectly excluding dependencies.

## Where this runs in the codebase

| Location | Role |
| -------- | ---- |
| {py:mod}`conda_pypi.markers` | Marker AST walk and clause normalization. |
| {py:func}`conda_pypi.markers.extract_marker_condition_and_extras` | Splits a {py:class}`packaging.markers.Marker` into a condition string and `extra` names. |
| {py:func}`conda_pypi.pypi_metadata.pypi_to_repodata` | `v3.whl` repodata from PyPI JSON. Names use {py:func}`conda_pypi.name_mapping.pypi_to_conda_name`. |
| {py:func}`conda_pypi.translate.requires_to_conda` | `depends` / `extras` when building `.conda` packages from wheel `METADATA` (no `[when="…"]` on depends, extras-only marker routing). |

## MatchSpec and `[when="…"]`

Strings such as `pkg>=1[when="…"]` are not valid conda `MatchSpec` input, since `conda.models.match_spec.MatchSpec` does not yet expose a `when` field. Proposed standardization of conditional dependencies and a serialized `when` syntax lives in [CEP PR #111](https://github.com/conda/ceps/pull/111) (conditional dependencies, extras, and flags).

conda-pypi may emit `[when="…"]` only in repodata for solvers that accept that shape (for example Rattler). Wheel → `.conda` `index.json` does not put `[when="…"]` on dependency strings, because conda does not support that syntax.

If all marker conditions are untranslatable and there is no extra, the dependency is recorded without the `when`. For example, `cffi ; platform_machine == "x86_64"` becomes just `cffi` in the repodata, since `platform_machine` produces no fragment. Here we fallback to adding the dependecy unconditionally, which is more cautious than dropping it.
