# Architecture

This page documents the technical architecture of `conda-pypi`, explaining
how it integrates with conda and the internal organization of its components.

## Plugin System Integration

`conda-pypi` is implemented as a conda plugin using `conda`'s official plugin
architecture. This design enables seamless integration with conda's existing
workflows without requiring modifications to conda itself.

The plugin registers several hooks with `conda`'s plugin system. The
subcommand hook adds the `conda pypi` subcommand to conda through
`conda_pypi.plugin.conda_subcommands()`, providing `conda pypi install`
for installing Python distribution packages with conversion (pending deprecation), `conda pypi convert` for
converting Python projects without installing them, and `conda pypi index` for indexing a local directory of `.whl` files to create a local conda channel.

The plugin also registers two post-command hooks that extend conda's
existing commands. The environment protection hook triggers after `install`,
`create`, `update`, and `remove` commands to automatically deploy
`EXTERNALLY-MANAGED` files that prevent accidental `pip` (or any other Python install tool) usage. This is
implemented through `ensure_target_env_has_externally_managed()`.

## Data Flow Architecture

### Installation Flow

```
conda pypi install package
         ↓
CLI Argument Parsing
         ↓
Environment Validation
         ↓
Package Classification
         ↓
    Editable (-e)? ----Yes---→ Build local project to .conda --> Install --> Deploy EXTERNALLY-MANAGED
         ↓ No
Dependency Resolution
         ↓
Channel Search for Dependencies
         ↓
Convert Missing Wheels from Package Indexes
         ↓
Install via conda
         ↓
Deploy EXTERNALLY-MANAGED
```

### Conversion Flow

```
conda pypi convert package
         ↓
Fetch from PyPI
         ↓
Download Wheels
         ↓
Convert to .conda
         ↓
Save to Output Directory
```

### Index Flow

```
conda pypi index <directory>
         ↓
Validate Directory Structure
         ↓
Scan for .whl Files
         ↓
Extract Wheel Metadata
         ↓
Generate repodata.json
         ↓
noarch/repodata.json Created
```

### Plugin Hook Flow

```
conda command executed
         ↓
Post-command hook?
    ↓           ↓
install/      install/create/
create        update/remove
    ↓           ↓
Process       Deploy
requirements  EXTERNALLY-
from indexes  MANAGED
    ↓           ↓
Install       Create marker
packages      files
from indexes
```

## Key Design Principles

The architecture of `conda-pypi` is built around several key design
principles that ensure effective integration between conda and Python
packaging tools.

Conda-native integration is achieved by using `conda`'s official plugin
system and leveraging `conda`'s existing infrastructure including solvers,
channels, and metadata systems. This approach maintains full compatibility
with existing conda workflows.

This hybrid approach resolves packages from conda channels and the local
conversion cache, then fetches missing wheels from package indexes
(PyPI by default). The system falls back to wheel conversion only
when needed.

This architecture enables conda-pypi to provide a seamless bridge between
conda and Python packaging tools while maintaining the integrity and benefits of
both package management systems.
