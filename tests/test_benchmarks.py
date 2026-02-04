import sys

import pytest
from pathlib import Path

from conda.testing.fixtures import CondaCLIFixture
from conda.models.match_spec import MatchSpec
from conda.common.path import get_python_short_path

from conda_pypi.convert_tree import ConvertTree
from conda_pypi.downloader import find_and_fetch, get_package_finder
from conda_pypi.build import build_conda

# Use the same Python version as the test environment
PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"


# @pytest.mark.benchmark
# @pytest.mark.parametrize(
#     "packages",
#     [
#         pytest.param(("imagesize",), id="imagesize"),  # small package, few dependencies
#         pytest.param(("scipy",), id="scipy"),  # slightly larger package
#         pytest.param(("jupyterlab",), id="jupyterlab"),
#     ],
# )
# def test_conda_pypi_install_basic(
#     tmp_path_factory,
#     conda_cli: CondaCLIFixture,
#     packages: tuple[str],
#     benchmark,
#     monkeypatch: MonkeyPatch,
# ):
#     """Benchmark basic conda pypi install functionality."""

#     def setup():
#         # Setup function is run every time. So, using benchmarks to run multiple
#         # iterations of the test will create new paths for repo_dir and
#         # prefix for each iteration. This ensures a clean test without any
#         # cached packages and in a clean environment.
#         repo_dir = tmp_path_factory.mktemp(f"{'-'.join(packages)}-pkg-repo")
#         prefix = str(tmp_path_factory.mktemp(f"{'-'.join(packages)}"))

#         monkeypatch.setattr("platformdirs.user_data_dir", lambda s: str(repo_dir))

#         conda_cli("create", "--yes", "--prefix", prefix, f"python={PYTHON_VERSION}")
#         return (prefix,), {}

#     def target(prefix):
#         _, _, rc = conda_cli(
#             "pypi",
#             "--yes",
#             "install",
#             "--prefix",
#             prefix,
#             *packages,
#         )
#         return rc

#     result = benchmark.pedantic(
#         target,
#         setup=setup,
#         rounds=2,
#         warmup_rounds=0,  # no warm up, cleaning the cache every time
#     )
#     assert result == 0


@pytest.mark.benchmark
@pytest.mark.parametrize(
    "packages",
    [
        pytest.param(("imagesize",), id="imagesize"),  # small package, few dependencies
        pytest.param(("certifi",), id="certifi"),  # another small package
        pytest.param(("click>=8.0",), id="click>=8.0"),  # package with version constraint
    ],
)
def test_convert_tree(
    tmp_path_factory,
    conda_cli: CondaCLIFixture,
    packages: tuple[str],
    benchmark,
):
    """Benchmark convert_tree. This test overrides channels so the whole
    dependency tree is converted.

    Note: We use small packages to keep benchmark runtime reasonable.
    Larger packages like jupyterlab were removed as they took 2+ hours.
    """

    def setup():
        repo_dir = tmp_path_factory.mktemp(f"{'-'.join(packages)}-pkg-repo")
        prefix = str(tmp_path_factory.mktemp(f"{'-'.join(packages)}"))
        conda_cli("create", "--yes", "--prefix", prefix, f"python={PYTHON_VERSION}")

        tree_converter = ConvertTree(prefix, True, repo_dir)
        return (tree_converter,), {}

    def target(tree_converter):
        match_specs = [MatchSpec(pkg) for pkg in packages]
        tree_converter.convert_tree(match_specs)

    benchmark.pedantic(
        target,
        setup=setup,
        rounds=1,
        warmup_rounds=0,  # no warm up, cleaning the cache every time
    )


@pytest.mark.benchmark
@pytest.mark.parametrize(
    "package",
    [
        pytest.param("imagesize", id="imagesize"),
        pytest.param("certifi", id="certifi"),
    ],
)
def test_build_conda(
    tmp_path_factory,
    conda_cli: CondaCLIFixture,
    package: str,
    benchmark,
):
    """Benchmark building the conda package from a wheel.

    Note: We use small packages to keep benchmark runtime reasonable.
    Larger packages like jupyterlab were removed as they took 2+ hours.
    """
    wheel_dir = tmp_path_factory.mktemp("wheel_dir")

    def setup():
        prefix = str(tmp_path_factory.mktemp(f"{package}"))
        build_path = tmp_path_factory.mktemp(f"build-{package}")
        output_path = tmp_path_factory.mktemp(f"output-{package}")

        conda_cli("create", "--yes", "--prefix", prefix, f"python={PYTHON_VERSION}")

        python_exe = Path(prefix, get_python_short_path())
        finder = get_package_finder(prefix)
        wheel_path = find_and_fetch(finder, wheel_dir, package)

        return (wheel_path, python_exe, build_path, output_path), {}

    def target(wheel_path, python_exe, build_path, output_path):
        build_conda(
            wheel_path,
            build_path,
            output_path,
            python_exe,
            is_editable=False,
        )

    benchmark.pedantic(
        target,
        setup=setup,
        rounds=1,
        warmup_rounds=0,  # no warm up, cleaning the cache every time
    )
