import json
import subprocess
from pathlib import Path

import build
import pytest
from conda.base.context import context
from conda.cli.main import main_subshell
from conda.core.prefix_data import PrefixData
from packaging.requirements import InvalidRequirement

import conda_pypi.dependencies_subprocess
from conda_pypi.build import filter, pypa_to_conda
from conda_pypi.dependencies.pypi import check_dependencies, ensure_requirements


def test_editable(tmp_path):
    # Other tests can change context.target_prefix by calling "conda install
    # --prefix", so we use default_prefix; could alternatively reset context.
    pypa_to_conda(
        Path(__file__).parents[1],
        output_path=tmp_path,
        distribution="editable",
        prefix=Path(context.default_prefix),
    )


def pypa_build_packages():
    """
    Test packages from pypa/build repository.

    (Clone pypa/build into tests/)
    """
    here = Path(__file__).parent
    return list(p.name for p in Path(here, "build", "tests", "packages").glob("*"))


@pytest.fixture
def package_path():
    here = Path(__file__).parent
    return Path(here, "build", "tests", "packages")


@pytest.mark.parametrize("package", pypa_build_packages())
def test_build_wheel(package, package_path, tmp_path):
    # Some of these will not contain the editable hook; need to test building
    # regular wheels also. Some will require a "yes" for conda install
    # dependencies. Some are designed to fail.
    xfail = [
        "test-bad-backend",
        "test-bad-syntax",
        "test-bad-wheel",
        "test-cant-build-via-sdist",
        "test-invalid-requirements",
        "test-metadata",
        "test-no-project",
        "test-no-requires",
        "test-optional-hooks",
    ]

    try:
        pypa_to_conda(
            package_path / package,
            output_path=tmp_path,
            distribution="wheel",
            prefix=Path(context.default_prefix),
        )
    except (
        build.BuildException,
        build.BuildBackendException,
        subprocess.CalledProcessError,
        InvalidRequirement,
    ) as e:
        if package in xfail:
            pytest.xfail(reason=str(e))


def test_ensure_requirements(mocker):
    mock = mocker.patch("conda_pypi.dependencies.pypi.main_subshell")
    ensure_requirements(["flit_core"], prefix=Path())
    # normalizes/converts the underscore flit_core->flit-core
    assert mock.call_args.args == ("install", "--prefix", ".", "-y", "flit-core")


def test_check_dependencies_flattens_missing_dependencies(mocker):
    mocker.patch("conda_pypi.dependencies.pypi.paths.get_python_executable", return_value=Path())
    subprocess_run = mocker.patch("conda_pypi.dependencies.pypi.subprocess.run")
    subprocess_run.return_value.stdout = json.dumps(
        [["hatchling>=1.26"], ["setuptools>=65", "packaging>=23"]]
    )

    missing = check_dependencies(["hatchling>=1.26", "setuptools>=65"], prefix=Path())

    assert missing == ["hatchling>=1.26", "packaging>=23"]


def test_filter_coverage():
    class tarinfo:
        name = ".git"

    assert filter(tarinfo) is None  # type: ignore


def test_create_build_dir(tmp_path):
    # XXX should "create default output_path" logic live in pypa_to_conda?
    with pytest.raises(build.BuildException):
        pypa_to_conda(tmp_path, prefix=Path(context.default_prefix))


def test_build_in_env(tmp_path):
    """Test conda-pypi installed in different environment than editable package."""
    main_subshell(
        "create",
        "--prefix",
        str(tmp_path / "env"),
        "-y",
        "python=3.11",
        "python-build",
    )

    prefix = str(tmp_path / "env")

    main_subshell(
        "pypi",
        "install",
        "--prefix",
        prefix,
        "-e",
        str(Path(__file__).parent / "packages" / "has-build-dep"),
    )

    prefix_data = PrefixData(prefix, interoperability=True)
    installed = [record.name for record in prefix_data.iter_records()]

    assert "packaging" in installed


def test_dependencies_subprocess():
    """
    Normally called in a way that doesn't measure coverage.
    """
    dependencies = ["xyzzy", "conda"]
    missing_dependencies = conda_pypi.dependencies_subprocess.main(
        ["-", "-r", json.dumps(dependencies)]
    )
    # A list per checked dependency, if that dependency or its dependencies are
    # missing.
    assert json.loads(missing_dependencies) == [["xyzzy"]]
