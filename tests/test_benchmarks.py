from pathlib import Path

import pytest
from conda.common.path import get_python_short_path
from conda.models.match_spec import MatchSpec
from conda.testing.fixtures import CondaCLIFixture

from conda_pypi.build import build_conda
from conda_pypi.convert_tree import ConvertTree
from conda_pypi.downloader import find_and_fetch, get_package_finder


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
    python_template_env: Path | None,
    packages: tuple[str],
    benchmark,
):
    """Benchmark convert_tree. This test overrides channels so the whole
    dependency tree is converted.

    Note: We use small packages to keep benchmark runtime reasonable.
    Larger packages like jupyterlab were removed as they took 2+ hours.

    Optimization: Uses `conda create --clone` from a session-scoped template
    instead of running a full `conda create` each time. This is faster because
    it skips the solver and package downloads while still properly handling
    prefix relocation.
    """
    # Track setup iteration for unique paths
    setup_counter = [0]

    def setup():
        setup_counter[0] += 1
        repo_dir = tmp_path_factory.mktemp(f"{'-'.join(packages)}-pkg-repo-{setup_counter[0]}")
        prefix = str(tmp_path_factory.mktemp(f"{'-'.join(packages)}-{setup_counter[0]}"))

        # Clone from template if available (faster), otherwise create from scratch
        if python_template_env:
            conda_cli("create", "--clone", str(python_template_env), "--prefix", prefix, "--yes")
        else:
            conda_cli("create", "--yes", "--prefix", prefix, "python")

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
    python_template_env: Path | None,
    package: str,
    benchmark,
):
    """Benchmark building the conda package from a wheel.

    Note: We use small packages to keep benchmark runtime reasonable.
    Larger packages like jupyterlab were removed as they took 2+ hours.

    Optimization: Uses `conda create --clone` from a session-scoped template
    instead of running a full `conda create` each time. This is faster because
    it skips the solver and package downloads while still properly handling
    prefix relocation.
    """
    wheel_dir = tmp_path_factory.mktemp("wheel_dir")
    # Track setup iteration for unique paths
    setup_counter = [0]

    def setup():
        setup_counter[0] += 1
        prefix = str(tmp_path_factory.mktemp(f"{package}-{setup_counter[0]}"))
        build_path = tmp_path_factory.mktemp(f"build-{package}-{setup_counter[0]}")
        output_path = tmp_path_factory.mktemp(f"output-{package}-{setup_counter[0]}")

        # Clone from template if available (faster), otherwise create from scratch
        if python_template_env:
            conda_cli("create", "--clone", str(python_template_env), "--prefix", prefix, "--yes")
        else:
            conda_cli("create", "--yes", "--prefix", prefix, "python")

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
