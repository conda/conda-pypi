from pathlib import Path

import pytest
from conda.common.path import get_python_short_path
from conda.models.match_spec import MatchSpec
from conda.testing.fixtures import CondaCLIFixture

from conda_pypi.build import build_conda
from conda_pypi.convert_tree import ConvertTree
from conda_pypi.downloader import get_package_finder
from tests import PYPI_LOCAL_INDEX


@pytest.mark.benchmark
@pytest.mark.parametrize(
    "packages",
    [
        pytest.param(("demo-package",), id="demo-package"),
        pytest.param(("entrypoint-pkg",), id="entrypoint-pkg"),
        pytest.param(("script-pkg",), id="script-pkg"),
    ],
)
def test_convert_local_tree(
    tmp_path_factory,
    conda_cli: CondaCLIFixture,
    python_template_env: Path,
    packages: tuple[str],
    pypi_local_index: str,
    benchmark,
):
    """Convert fixed local wheels with a fresh prefix and repository per round."""
    setup_counter = 0

    def setup():
        nonlocal setup_counter
        setup_counter += 1
        repo_dir = tmp_path_factory.mktemp(f"{'-'.join(packages)}-pkg-repo-{setup_counter}")
        prefix = str(tmp_path_factory.mktemp(f"{'-'.join(packages)}-{setup_counter}"))

        conda_cli("create", "--clone", str(python_template_env), "--prefix", prefix, "--yes")

        finder = get_package_finder(prefix, (pypi_local_index,))
        tree_converter = ConvertTree(prefix, True, repo_dir, finder=finder)
        return (tree_converter,), {}

    def target(tree_converter):
        match_specs = [MatchSpec(pkg) for pkg in packages]
        tree_converter.convert_tree(match_specs)

    benchmark.pedantic(
        target,
        setup=setup,
        rounds=5,
        warmup_rounds=1,
    )


@pytest.mark.benchmark
@pytest.mark.parametrize(
    "wheel",
    [
        pytest.param("demo-package/demo_package-0.1.0-py3-none-any.whl", id="demo-package"),
        pytest.param("entrypoint-pkg/entrypoint_pkg-1.0.0-py3-none-any.whl", id="entrypoint-pkg"),
    ],
)
def test_build_local_wheel(
    tmp_path_factory,
    conda_cli: CondaCLIFixture,
    python_template_env: Path,
    wheel: str,
    benchmark,
):
    """Build a fixed local wheel with fresh prefix, build, and output directories."""
    wheel_path = PYPI_LOCAL_INDEX / wheel
    package = wheel_path.parent.name
    setup_counter = 0

    def setup():
        nonlocal setup_counter
        setup_counter += 1
        prefix = str(tmp_path_factory.mktemp(f"{package}-{setup_counter}"))
        build_path = tmp_path_factory.mktemp(f"build-{package}-{setup_counter}")
        output_path = tmp_path_factory.mktemp(f"output-{package}-{setup_counter}")

        conda_cli("create", "--clone", str(python_template_env), "--prefix", prefix, "--yes")

        python_exe = Path(prefix, get_python_short_path())

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
        rounds=5,
        warmup_rounds=1,
    )
