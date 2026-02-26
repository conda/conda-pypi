``conda pypi convert``
**********************

.. argparse::
   :module: conda_pypi.cli.main
   :func: generate_parser
   :prog: conda pypi
   :path: convert
   :nodefault:
   :nodefaultconst:

Custom Name Mapping
===================

The ``--name-mapping`` option allows you to provide a custom JSON file that maps
PyPI package names to conda package names. This is useful when you need to
replace the built-in grayskull mapping with your own mapping file.

When ``--name-mapping`` is provided, the built-in mapping is not used for that
conversion. The JSON file is treated as the complete mapping source.

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

   conda pypi convert --name-mapping ./mapping.json ./my-package-1.0.0-py3-none-any.whl

The mapping will be used during conversion to determine the conda package name
for dependencies and the main package being converted.
