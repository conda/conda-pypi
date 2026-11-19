import importlib
import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path
from types import SimpleNamespace

import build
import pytest
from conda.base.context import context, reset_context
from conda.cli.main import main_subshell
from conda.core.prefix_data import PrefixData
from packaging.markers import default_environment
from packaging.requirements import InvalidRequirement

import conda_pypi.dependencies.pypi as pypi_dependencies
import conda_pypi.dependencies_subprocess
from conda_pypi import installer
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
    return [p.name for p in Path(here, "build", "tests", "packages").glob("*")]


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


@pytest.mark.parametrize(
    ("yes", "expected_command"),
    [
        (True, ("install", "--prefix", ".", "--yes", "flit-core")),
        (False, ("install", "--prefix", ".", "flit-core")),
    ],
)
def test_ensure_requirements_prompt_state(yes, expected_command, monkeypatch, mocker):
    mock = mocker.Mock()
    monkeypatch.setattr(pypi_dependencies, "main_subshell", mock)
    ensure_requirements(["flit_core"], prefix=Path(), yes=yes)
    # normalizes/converts the underscore flit_core->flit-core
    assert mock.call_args.args == expected_command


@pytest.mark.parametrize(
    ("yes", "source"),
    [
        (False, Path("/src/project")),
        (True, None),
    ],
)
def test_install_ephemeral_conda_prompt_state(yes, source, monkeypatch, mocker, tmp_path):
    cache = SimpleNamespace(pkgs_dir=tmp_path)
    prefix = Path("/prefix")
    package = Path("/tmp/editable.conda")

    confirm = mocker.Mock()
    install = mocker.Mock()
    calls = mocker.Mock()
    calls.attach_mock(confirm, "confirm")
    calls.attach_mock(install, "install")
    monkeypatch.setattr(
        installer.PackageCacheData,
        "first_writable",
        staticmethod(lambda: cache),
    )
    monkeypatch.setattr(installer, "confirm_yn", confirm)
    monkeypatch.setattr(installer.subprocess, "run", install)

    installer.install_ephemeral_conda(
        prefix,
        package,
        yes=yes,
        source=source,
    )

    command = [
        sys.executable,
        "-m",
        "conda",
        "install",
        "--offline",
        "--prefix",
        str(prefix),
        str(package),
    ]
    expected_calls = [mocker.call.install(command, env=mocker.ANY, check=True)]
    if not yes:
        expected_calls.insert(
            0, mocker.call.confirm(f"Install editable package from {source} into {prefix}")
        )
    assert calls.mock_calls == expected_calls


def test_check_dependencies_checks_target_versions_markers_and_extras(tmp_path, mocker):
    def install_metadata(name, version, *requires):
        metadata_dir = tmp_path / f"{name}-{version}.dist-info"
        metadata_dir.mkdir()
        (metadata_dir / "METADATA").write_text(
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
            + "".join(f"Requires-Dist: {requirement}\n" for requirement in requires)
        )

    install_metadata(
        "backend",
        "2.0",
        "ordinary>=2",
        "backport; python_version < '3.9'",
        "future; python_version >= '3.9'",
        "optional; extra == 'tools'",
        "unrequested; extra == 'docs'",
        "cycle",
    )
    install_metadata("ordinary", "1.0")
    install_metadata("cycle", "1.0", "backend")
    target = {"sys_path": [str(tmp_path)], "markers": {"python_version": "3.8"}}
    mocker.patch.object(
        pypi_dependencies.subprocess,
        "run",
        return_value=SimpleNamespace(stdout=json.dumps(target)),
    )

    # packaging is installed alongside conda-pypi, but absent from this prefix.
    assert check_dependencies(["backend[tools]>=2", "packaging"], prefix=tmp_path) == [
        "ordinary>=2",
        'backport; python_version < "3.9"',
        'optional; extra == "tools"',
        "packaging",
    ]


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
        "--yes",
        "--prefix",
        prefix,
        "-e",
        str(Path(__file__).parent / "packages" / "has-build-dep"),
    )

    prefix_data = PrefixData(prefix, interoperability=True)
    installed = [record.name for record in prefix_data.iter_records()]

    assert "packaging" in installed


def test_dependencies_subprocess():
    assert conda_pypi.dependencies_subprocess.marker_environment() == default_environment()


@pytest.fixture
def ephemeral_package(tmp_path):
    package = tmp_path / "editable-demo-1.0-0.tar.bz2"
    index = {
        "name": "editable-demo",
        "version": "1.0",
        "build": "0",
        "build_number": 0,
        "subdir": "noarch",
        "depends": [],
    }
    with tarfile.open(package, "w:bz2") as archive:
        for name, content in {
            "info/index.json": json.dumps(index).encode(),
            "info/files": b"editable-demo.txt\n",
            "editable-demo.txt": b"installed\n",
        }.items():
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
    return package


@pytest.fixture
def ephemeral_environment(tmp_path, monkeypatch):
    cache = tmp_path / "pkgs"
    cache.mkdir()
    prefix = tmp_path / "env"
    (prefix / "conda-meta").mkdir(parents=True)
    (prefix / "conda-meta" / "history").touch()
    try:
        with monkeypatch.context() as env:
            env.setenv("CONDA_PKGS_DIRS", str(cache))
            env.setenv("CONDA_OFFLINE", "false")
            reset_context()
            yield prefix, cache
    finally:
        reset_context()


@pytest.mark.parametrize("valid_package", [True, False])
def test_install_ephemeral_conda_preserves_package_cache(
    valid_package, ephemeral_package, ephemeral_environment
):
    prefix, cache = ephemeral_environment
    if valid_package:
        installer.install_ephemeral_conda(prefix, ephemeral_package)
        assert (prefix / "editable-demo.txt").read_text() == "installed\n"
    else:
        ephemeral_package.write_bytes(b"not a package archive")
        with pytest.raises(SystemExit) as exc_info:
            installer.install_ephemeral_conda(prefix, ephemeral_package)
        assert exc_info.value.code != 0
        assert not (prefix / "editable-demo.txt").exists()
    assert context.pkgs_dirs == (str(cache),)
    assert context.offline is False
    assert not list(cache.glob("ephemeral*"))


def test_install_ephemeral_conda_disables_network_prefetch(
    ephemeral_package, ephemeral_environment, tmp_path, monkeypatch
):
    prefix, cache = ephemeral_environment
    plugin_source = """
import json
import os
from pathlib import Path
from conda.base.context import context
from conda.plugins import hookimpl
from conda.plugins.types import CondaPreCommand

def prefetch(command):
    assert context.offline, "Repodata prefetch can outlive the temporary package cache"
    Path(os.environ["PREFETCH_RECORD"]).write_text(json.dumps(context.pkgs_dirs))

@hookimpl
def conda_pre_commands():
    yield CondaPreCommand(name="test-prefetch", action=prefetch, run_for={"install"})
"""
    (tmp_path / "ephemeral_install_guard.py").write_text(plugin_source)
    metadata = tmp_path / "ephemeral_install_guard-1.0.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text("Name: ephemeral-install-guard\nVersion: 1.0\n")
    (metadata / "entry_points.txt").write_text(
        "[conda]\nephemeral-install-guard = ephemeral_install_guard\n"
    )
    monkeypatch.setenv(
        "PYTHONPATH",
        os.pathsep.join(value for value in [str(tmp_path), os.getenv("PYTHONPATH")] if value),
    )
    record = tmp_path / "prefetch.json"
    monkeypatch.setenv("PREFETCH_RECORD", str(record))
    monkeypatch.syspath_prepend(str(tmp_path))
    plugin = importlib.import_module("ephemeral_install_guard")
    manager = context.plugin_manager
    manager.register(plugin)
    try:
        installer.install_ephemeral_conda(prefix, ephemeral_package)

        assert (prefix / "editable-demo.txt").read_text() == "installed\n"
        (temporary_cache,) = json.loads(record.read_text())
        assert Path(temporary_cache).parent == cache
        assert not Path(temporary_cache).exists()
        assert context.offline is False
        assert context.pkgs_dirs == (str(cache),)
    finally:
        manager.unregister(plugin)
        sys.modules.pop("ephemeral_install_guard", None)
