``conda pypi migrate-env``
**************************

.. argparse::
   :module: conda_pypi.cli.main
   :func: generate_parser
   :prog: conda pypi
   :path: migrate-env
   :nodefault:
   :nodefaultconst:

Output Modes
============

The command supports three mutually exclusive output destinations.

**Standard output (default)**

When neither ``--file`` nor ``--in-place`` is given, the rewritten environment file is printed to stdout. This is useful for previewing the result or piping it to another tool:

.. code-block:: bash

   conda pypi migrate-env environment.yaml

**Write to a new file** (``-f`` / ``--file``)

Writes the result to a new file, leaving the original untouched:

.. code-block:: bash

   conda pypi migrate-env --file migrated.yaml environment.yaml

**Rewrite in-place** (``--in-place``)

Overwrites the input file directly. Make sure the original is under version control or otherwise backed up before using this option:

.. code-block:: bash

   conda pypi migrate-env --in-place environment.yaml

Wheels Channel
==============

By default, ``migrate-env`` queries the public ``conda-pypi`` wheels channel to determine which pip dependencies have conda equivalents available. Use ``-c`` / ``--channel`` to override this with one or more alternative channel URLs.  The option can be repeated to query multiple channels — they are checked in the order given:

.. code-block:: bash

   # Use a single private channel
   conda pypi migrate-env -c https://my-org.example.com/wheels environment.yaml

   # Query two channels
   conda pypi migrate-env \
       -c https://my-org.example.com/wheels \
       -c https://mirror.example.com/wheels \
       environment.yaml

Custom Name Mapping
===================

The ``--name-mapping`` option allows you to provide a custom JSON file that maps PyPI package names to conda package names. This is useful when you need to replace the built-in grayskull mapping with your own mapping file.

When ``--name-mapping`` is provided, the built-in mapping is not used for that migration. The JSON file is treated as the complete mapping source.

The mapping file should be a JSON object where:

- Keys are PyPI package names (canonicalized, lowercase)
- Values are dictionaries with at least a ``conda_name`` key (string)
- Optionally can include ``pypi_name``, ``import_name``, and ``mapping_source`` keys

Example mapping file (``mapping.json``):

.. code-block:: json

   {
     "requests": {
       "pypi_name": "requests",
       "conda_name": "requests",
       "import_name": "requests",
       "mapping_source": "custom"
     },
     "my-package": {
       "conda_name": "my-package-conda"
     }
   }

Usage example:

.. code-block:: bash

   conda pypi migrate-env --name-mapping ./mapping.json environment.yaml

The mapping will be used during migration to determine the conda package name when replacing pip dependencies with conda equivalents.

Examples
========

Migrate ``environment.yaml`` using the default ``conda-pypi`` wheels channel and print the result to stdout:

.. code-block:: bash

   conda pypi migrate-env environment.yaml

Write the migrated file to a new file:

.. code-block:: bash

   conda pypi migrate-env --file migrated.yaml environment.yaml

Rewrite the file in-place:

.. code-block:: bash

   conda pypi migrate-env --in-place environment.yaml

Use a custom (self-hosted) wheels channel:

.. code-block:: bash

   conda pypi migrate-env -c https://my-org.example.com/wheels environment.yaml

Use a custom PyPI-to-conda name mapping:

.. code-block:: bash

   conda pypi migrate-env --name-mapping ./mapping.json environment.yaml
