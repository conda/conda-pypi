from tempfile import TemporaryDirectory
from argparse import Namespace, _SubParsersAction
from pathlib import Path
import json

from conda.auxlib.ish import dals
from conda.base.context import context
from conda.exceptions import ArgumentError

from conda_pypi import build, paths
from conda_pypi.translate import validate_name_mapping_format


def configure_parser(parser: _SubParsersAction) -> None:
    """
    Configure all subcommand arguments and options via argparse
    """
    # convert subcommand
    summary = "Build and convert local Python sdists, wheels or projects to conda packages"
    description = summary
    epilog = dals(
        """
        Examples:

        Convert a PyPI package to conda format without installing::

            conda pypi convert ./requests-2.32.5-py3-none-any.whl

        Convert a local Python project to conda package::

            conda pypi convert ./my-python-project

        Convert a package and save to a specific output folder::

            conda pypi convert --output-folder ./conda-packages ./numpy-2.3.3-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl

        Convert a local Python project to an editable package::

            conda pypi convert -e . --output-folder ./conda-packages

        Convert a package from a Git repository::

            git clone https://github.com/user/repo.git
            conda pypi convert ./repo

        Convert a package and inject test files::

            conda pypi convert --test-dir ./my-tests-dir ./my-python-project

        """
    )

    convert = parser.add_parser(
        "convert",
        help=summary,
        description=description,
        epilog=epilog,
    )

    convert.add_argument(
        "--output-folder",
        help="Folder to write output package(s)",
        type=Path,
        required=False,
        default=Path.cwd() / "conda-pypi-output",
    )
    convert.add_argument(
        "project_path",
        metavar="PROJECT",
        help="Convert named path as conda package.",
    )
    convert.add_argument(
        "-e",
        "--editable",
        action="store_true",
        help="Build PROJECT as an editable package.",
    )
    convert.add_argument(
        "-t",
        "--test-dir",
        type=Path,
        required=False,
        default=None,
        help="Directory containing test files to inject into the conda package. "
        "Must be structured as a conda test directory for the tests to work.",
    )
    convert.add_argument(
        "--name-mapping",
        help="Path to json file containing pypi to conda name mapping",
        type=Path,
        required=False,
        default=None,
    )


def execute(args: Namespace) -> int:
    """
    Entry point for the `conda pypi convert` subcommand
    """
    prefix_path = Path(context.target_prefix)
    if not Path(args.project_path).exists():
        raise ArgumentError("PROJECT must be a local path to a sdist, wheel or directory.")
    project_path = Path(args.project_path).expanduser()
    test_dir = args.test_dir.expanduser() if args.test_dir else None

    if test_dir:
        if not test_dir.exists():
            raise FileNotFoundError(f"Test directory does not exist: {test_dir}")
        if not test_dir.is_dir():
            raise NotADirectoryError(f"Test path is not a directory: {test_dir}")
        run_test_files = list(test_dir.glob("run_test.*"))
        if not run_test_files:
            raise ValueError(
                f"Test directory must contain at least one run_test.* file: {test_dir}"
            )

    output_folder = Path(args.output_folder).expanduser()
    output_folder.mkdir(parents=True, exist_ok=True)

    # Load name mapping if overriden
    # Use built-in by default
    pypi_to_conda_name_mapping = None
    if args.name_mapping is not None:
        if not args.name_mapping.exists():
            raise ArgumentError(f"Could not open {args.name_mapping}")
        with open(args.name_mapping, "r") as f:
            pypi_to_conda_name_mapping = json.load(f)
        # Check the dict has correct format
        validate_name_mapping_format(pypi_to_conda_name_mapping)

    # Handle wheel files directly without building
    if project_path.suffix == ".whl":
        if args.editable:
            raise ArgumentError("Cannot create editable package from a wheel file.")

        python_executable = str(paths.get_python_executable(prefix_path))
        with TemporaryDirectory(prefix="conda") as build_path:
            package_path = build.build_conda(
                project_path,
                Path(build_path),
                output_folder,
                python_executable,
                test_dir=test_dir,
                pypi_to_conda_name_mapping=pypi_to_conda_name_mapping,
            )
    else:
        # Build from source (project directory or sdist)
        distribution = "editable" if args.editable else "wheel"
        package_path = build.pypa_to_conda(
            project_path,
            distribution=distribution,
            output_path=output_folder,
            prefix=prefix_path,
            test_dir=test_dir,
            pypi_to_conda_name_mapping=pypi_to_conda_name_mapping,
        )

    print(f"Conda package at {package_path} built successfully. Output folder: {output_folder}.")
    return 0
