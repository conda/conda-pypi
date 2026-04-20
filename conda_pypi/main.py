from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from csv import reader as csv_reader
from email.parser import HeaderParser
from logging import getLogger
from pathlib import Path
from subprocess import CompletedProcess, run
from tempfile import NamedTemporaryFile
from typing import Any, Iterable, Literal

from conda.base.context import context
from conda.cli.main import main_subshell
from conda.core.prefix_data import PrefixData
from conda.exceptions import CondaError, InvalidVersionSpec
from conda.gateways.disk.read import compute_sum
from conda.models.enums import PackageType
from conda.models.match_spec import MatchSpec
from conda.models.records import PackageRecord
from conda.plugins.prefix_data_loaders.pypi.pkg_format import PythonDistribution
from packaging.requirements import Requirement
from packaging.tags import parse_tag
from packaging.version import Version

from conda_pypi.python_paths import (
    ensure_externally_managed,
    get_env_python,
    get_env_site_packages,
    get_externally_managed_paths,
)

logger = getLogger(f"conda.{__name__}")
HERE = Path(__file__).parent.resolve()


def run_conda_cli(*cli_args, **env_kwargs) -> int:
    logger.info("conda command: '%s'", " ".join(cli_args))
    try:
        main_subshell(*cli_args)
    except SystemExit as exc:
        logger.info("conda command system exit:", exc_info=True)
        return exc.code
    else:
        return 0


def run_conda_install(
    prefix: Path,
    specs: Iterable[MatchSpec],
    dry_run: bool = False,
    quiet: bool = False,
    verbosity: int = 0,
    force_reinstall: bool = False,
    yes: bool = False,
    json: bool = False,
    channels: Iterable[str] = (),
    override_channels: bool = False,
) -> int:
    command = ["install", "--prefix", str(prefix)]
    if dry_run:
        command.append("--dry-run")
    if quiet:
        command.append("--quiet")
    if verbosity:
        command.append("-" + ("v" * verbosity))
    if force_reinstall:
        command.append("--force-reinstall")
    if yes:
        command.append("--yes")
    if json:
        command.append("--json")
    if channels:
        for channel in channels:
            command.append("--channel")
            command.append(channel)
    if override_channels:
        command.append("--override-channels")

    command.extend(str(spec) for spec in specs)

    return run_conda_cli(*command)


def run_pip_install(
    prefix: Path,
    args: Iterable[str],
    upgrade: bool = False,
    dry_run: bool = False,
    quiet: bool = False,
    verbosity: int = 0,
    force_reinstall: bool = False,
    yes: bool = False,
    capture_output: bool = False,
    check: bool = True,
) -> CompletedProcess:
    if not args:
        return 0
    command = [
        get_env_python(prefix),
        "-mpip",
        "install",
        "--no-deps",
    ]
    if any(
        flag in args for flag in ("--platform", "--abi", "--implementation", "--python-version")
    ):
        command += ["--target", str(get_env_site_packages(prefix))]
    else:
        command += ["--prefix", str(prefix)]
    if dry_run:
        command.append("--dry-run")
    if quiet:
        command.append("--quiet")
    if verbosity:
        command.append("-" + ("v" * verbosity))
    if force_reinstall:
        command.append("--force-reinstall")
    if upgrade:
        command.append("--upgrade")
    command.extend(args)

    logger.info("pip install command: %s", command)
    process = run(command, capture_output=capture_output or check, text=capture_output or check)
    if check and process.returncode:
        raise CondaError(
            f"Failed to run pip:\n"
            f"  command: {shlex.join(map(str, command))}\n"
            f"  exit code: {process.returncode}\n"
            f"  stderr:\n{process.stderr}\n"
            f"  stdout:\n{process.stdout}"
        )
    logger.debug("pip install stdout:\n%s", process.stdout)
    logger.debug("pip install stderr:\n%s", process.stderr)
    return process


def ensure_target_env_has_externally_managed(command: str):
    """
    post-command hook to ensure that the target env has the EXTERNALLY-MANAGED file
    even when it is created by conda, not 'conda-pypi'.
    """
    if os.environ.get("CONDA_BUILD_STATE") == "BUILD":
        return
    base_prefix = Path(context.conda_prefix)
    target_prefix = Path(context.target_prefix)
    if base_prefix == target_prefix or base_prefix.resolve() == target_prefix.resolve():
        return
    # Check if conda-pypi is available in the base environment
    # This is more lenient than checking if it was explicitly installed
    try:
        base_prefix_data = PrefixData(base_prefix)
        if not list(base_prefix_data.query("conda-pypi")):
            return
    except Exception:
        # If we can't determine conda-pypi availability, be conservative and return
        return
    prefix_data = PrefixData(target_prefix)
    if command in {"create", "install", "update"}:
        # ensure target env has pip installed
        if not list(prefix_data.query("pip")):
            return

        # Get Python version from the installed packages
        python_version = None
        python_records = list(prefix_data.query("python"))
        if python_records:
            version = Version(python_records[0].version)
            python_version = f"{version.major}.{version.minor}"

        # Check if there are some leftover EXTERNALLY-MANAGED files from other Python versions
        if command != "create" and os.name != "nt":
            for path in get_externally_managed_paths(target_prefix):
                if path.exists():
                    path.unlink()

        ensure_externally_managed(target_prefix, python_version=python_version)
    elif command == "remove":
        if list(prefix_data.query("pip")):
            # leave in place if pip is still installed
            return
        for path in get_externally_managed_paths(target_prefix):
            if path.exists():
                path.unlink()
    else:
        raise ValueError(f"command {command} not recognized.")


def pypi_lines_for_explicit_lockfile(
    prefix: Path | str, checksums: Iterable[Literal["md5", "sha256"]] | None = None
) -> list[str]:
    """
    Write pip install pseudo commands for each non-conda-installed Python package in prefix.
    See `PyPIDistribution.to_lockfile_line()` for more details.
    """
    PrefixData._cache_.clear()
    pd = PrefixData(str(prefix), interoperability=True)
    pd.load()
    lines = []
    python_record = list(pd.query("python"))
    assert len(python_record) == 1
    python_record = python_record[0]
    for record in pd.iter_records():
        if record.package_type != PackageType.VIRTUAL_PYTHON_WHEEL:
            continue
        pypi_dist = PyPIDistribution.from_conda_record(
            record, python_record, prefix, checksums=checksums
        )
        if pypi_dist.editable:
            continue
        lines.append(pypi_dist.to_lockfile_line())
    return lines


def dry_run_pip_json(
    args: Iterable[str],
    ignore_installed: bool = True,
    force_reinstall: bool = False,
    python_version: str = "",
    implementation: str = "",
    abi: Iterable[str] = (),
    platform: Iterable[str] = (),
) -> dict[str, Any]:
    """
    Runs pip in dry-run mode with the goal of obtaining a JSON report that encodes
    what would have been done. This is useful to invoke pip as a solver only, or
    to obtain the URL of which wheel would have been installed for a particular set of constraints.

    It returns the parsed JSON payload as a dict.
    """
    # pip can output to stdout via `--report -` (dash), but this
    # creates issues on Windows due to undecodable characters on some
    # project descriptions (e.g. charset-normalizer, amusingly), which
    # makes pip crash internally. Probably a bug on their end.
    # So we use a temporary file instead to work with bytes.
    json_output = NamedTemporaryFile(suffix=".json", delete=False)
    json_output.close()  # Prevent access errors on Windows

    try:
        cmd = [
            sys.executable,
            "-mpip",
            "install",
            "--dry-run",
            "--report",
            json_output.name,
            "--target",
            json_output.name + ".dir",  # This won't be created
        ]
        if ignore_installed:
            cmd.append("--ignore-installed")
        if force_reinstall:
            cmd.append("--force-reinstall")
        if python_version:
            cmd += ["--python-version", python_version, "--no-deps"]
        if implementation:
            cmd += ["--implementation", implementation]
        for tag in abi:
            cmd += ["--abi", tag]
        for tag in platform:
            cmd += ["--platform", tag]
        cmd += args
        logger.info("pip dry-run command: %s", cmd)
        process = run(cmd, capture_output=True, text=True)
        if process.returncode != 0:
            raise CondaError(
                f"Failed to dry-run pip:\n"
                f"  command: {shlex.join(map(str, cmd))}\n"
                f"  exit code: {process.returncode}\n"
                f"  stderr:\n{process.stderr}\n"
                f"  stdout:\n{process.stdout}"
            )
        logger.debug("pip dry-run stdout:\n%s", process.stdout)
        logger.debug("pip dry-run stderr:\n%s", process.stderr)
        with open(json_output.name, "rb") as f:
            # We need binary mode because the JSON output might
            # contain weird unicode stuff (as part of the project
            # description or README).
            return json.loads(f.read())
    finally:
        os.unlink(json_output.name)


class PyPIDistribution:
    _line_prefix = "# pypi: "
    _arg_parser = None

    def __init__(
        self,
        name: str,
        version: str,
        python_version: str | None = None,
        python_implementation: str | None = None,
        python_abi_tags: Iterable[str] = (),
        python_platform_tags: Iterable[str] = (),
        record_checksums: dict[str, str] | None = None,
        editable: bool = False,
    ):
        self.name = name
        self.version = version
        self.python_version = python_version
        self.python_implementation = python_implementation
        self.python_abi_tags = python_abi_tags or ()
        self.python_platform_tags = python_platform_tags or ()
        self.record_checksums = record_checksums or {}
        self.editable = editable
        self.url = None  # currently no way to know, use .find_wheel_url()

    @classmethod
    def from_conda_record(
        cls,
        record: PackageRecord,
        python_record: PackageRecord,
        prefix: str | Path,
        checksums: Iterable[Literal["md5", "sha256"]] | None = None,
    ) -> PyPIDistribution:
        # Locate anchor file
        sitepackages = get_env_site_packages(prefix)
        if record.fn.endswith(".dist-info"):
            anchor = sitepackages / record.fn / "METADATA"
        elif record.fn.endswith(".egg-info"):
            anchor = sitepackages / record.fn
            if anchor.is_dir():
                anchor = anchor / "PKG-INFO"
        else:
            raise ValueError("Unrecognized anchor file for Python metadata")

        # Estimate python implementation out of build strings
        python_version = ".".join(python_record.version.split(".")[:3])
        if "pypy" in python_record.build:
            python_impl = "pp"
        elif "cpython" in python_record.build:
            python_impl = "cp"
        else:
            python_impl = None

        # Find the hash for the RECORD file
        python_dist = PythonDistribution.init(prefix, str(anchor), python_record.version)
        if checksums:
            manifest = python_dist.manifest_full_path
            record_checksums = compute_record_sum(manifest, checksums)
        else:
            record_checksums = None

        # Scan files for editable markers and wheel metadata
        files = python_dist.get_paths()
        editable = cls._is_record_editable(files)
        wheel_file = next((path for path, *_ in files if path.endswith(".dist-info/WHEEL")), None)
        if wheel_file:
            wheel_details = cls._parse_wheel_file(Path(prefix, wheel_file))
            abi_tags, platform_tags = cls._tags_from_wheel(wheel_details)
        else:
            abi_tags, platform_tags = (), ()

        return cls(
            name=record.name,
            version=record.version,
            python_version=python_version,
            python_implementation=python_impl,
            record_checksums=record_checksums,
            python_abi_tags=abi_tags,
            python_platform_tags=platform_tags,
            editable=editable,
        )

    @classmethod
    def from_lockfile_line(cls, line: str | Iterable[str]):
        if isinstance(line, str):
            if line.startswith(cls._line_prefix):
                line = line[len(cls._line_prefix) :]
            line = shlex.split(line.strip())
        if cls._arg_parser is None:
            cls._arg_parser = cls._build_arg_parser()
        args = cls._arg_parser.parse_args(line)
        requirement = Requirement(args.spec)
        specifiers = list(requirement.specifier)
        if len(specifiers) != 1 or specifiers[0].operator != "==":
            raise InvalidVersionSpec(
                f"{args.spec} is not a valid requirement. "
                "PyPI requirements must be exact; i.e. 'name==version'."
            )
        pkg_name = requirement.name
        version = specifiers[0].version
        return cls(
            name=pkg_name,
            version=version,
            python_version=args.python_version,
            python_implementation=args.implementation,
            python_abi_tags=args.abi,
            python_platform_tags=args.platform,
        )

    def to_lockfile_line(self) -> list[str]:
        """
        Builds a pseudo command-line input for a pip-like interface, with the goal of providing
        enough information to retrieve a single wheel or sdist providing the package. The format is:

        ```
        # pypi: <name>[==<version>] [--python-version str] [--implementation str] [--abi str ...]
                [--platform str ...] [--record-checksum <algorithm>=<value>]
        ```

        All fields above should be part of the same line. The CLI mimics what `pip` currently
        accepts, with the exception of `--record-checksum`, which is a custom addition.

        The value of `--record-checksum` is given by `compute_record_sum()`.
        """
        if self.url:
            return f"{self._line_prefix}{self.url}"

        line = (
            f"{self._line_prefix}{self.name}=={self.version}"
            f" --python-version {self.python_version}"
            f" --implementation {self.python_implementation}"
        )
        for abi in self.python_abi_tags:
            line += f" --abi {abi}"
        for platform in self.python_platform_tags:
            line += f" --platform {platform}"
        for algo, checksum in self.record_checksums.items():
            line += f" --record-checksum={algo}:{checksum}"

        # Here we could invoke self.find_wheel_url() to get the resolved URL but I'm not sure it's
        # guaranteed we get the exact same source so for now we defer to install time, which at
        # least will give something compatible with the target machine

        return line

    def find_wheel_url(self) -> list[str]:
        report = dry_run_pip_json(
            ["--no-deps", f"{self.name}=={self.version}"],
            python_version=self.python_version,
            implementation=self.python_implementation,
            abi=self.python_abi_tags,
            platform=self.python_platform_tags,
        )
        return report["install"][0]["download_info"]["url"]

    @staticmethod
    def _parse_wheel_file(path) -> dict[str, list[str]]:
        path = Path(path)
        if not path.is_file():
            return {}
        with open(path) as f:
            parsed = HeaderParser().parse(f)
        data = {}
        for key, value in parsed.items():
            data.setdefault(key, []).append(value)
        return data

    @staticmethod
    def _tags_from_wheel(data: dict[str, Any]) -> tuple[tuple[str], tuple[str]]:
        abi_tags = set()
        platform_tags = set()
        for tag_str in data.get("Tag", ()):
            for tag in parse_tag(tag_str):
                if tag.abi != "none":
                    abi_tags.add(tag.abi)
                if tag.platform != "any":
                    platform_tags.add(tag.platform)
        return tuple(abi_tags), tuple(platform_tags)

    @staticmethod
    def _is_record_editable(files: tuple[str, str, int]) -> bool:
        for path, *_ in files:
            path = Path(path)
            if "__editable__" in path.stem:
                return True
            if path.name == "direct_url.json" and path.parent.suffix == ".dist-info":
                if path.is_file():
                    data = json.loads(path.read_text())
                    if data.get("dir_info", {}).get("editable"):
                        return True
        return False

    @staticmethod
    def _build_arg_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser()
        parser.add_argument("spec")
        parser.add_argument("--python-version")
        parser.add_argument("--implementation")
        parser.add_argument("--abi", action="append", default=[])
        parser.add_argument("--platform", action="append", default=[])
        parser.add_argument("--record-checksum", action="append", default=[])
        return parser


def compute_record_sum(manifest: str, algos: Iterable[str] = ("sha256",)) -> dict[str, str]:
    """
    Given a `RECORD` file, compute hashes out of a subset of its sorted contents.

    We skip `*.dist-info` files other than `METADATA` and `WHEEL`.
    For non site-packages files, we only keep the path for those than fall in `bin`, `lib`
    and `Scripts` because their hash and size might change with path relocation.

    The list of tuples `(path, hash, size)` is then sorted and written as JSON with no spaces or
    indentation. This output is what gets hashed.
    """
    contents = []
    try:
        with open(manifest) as f:
            reader = csv_reader(f, delimiter=",", quotechar='"')
            for row in reader:
                path, hash_, size = row
                path = Path(path)
                if size:
                    size = int(size)
                if path.parts[0].endswith(".dist-info") and path.name not in ("METADATA", "WHEEL"):
                    # we only want to check the metadata and wheel parts of dist-info; everything else
                    # is not deterministic or useful
                    continue
                if path.parts[0] == ".." and any(
                    part in path.parts for part in ("bin", "lib", "Scripts")
                ):
                    # entry points are autogenerated and can have different hashes/size
                    # depending on prefix
                    hash_, size = "", 0
                contents.append((str(path), hash_, size))
    except OSError as exc:
        logger.warning("Could not compute RECORD checksum for %s", manifest)
        logger.debug("Could not open %s", manifest, exc_info=exc)
        return

    try:
        with NamedTemporaryFile("w", delete=False) as tmp:
            tmp.write(json.dumps(contents, indent=0, separators=(",", ":")))
        return {algo: compute_sum(tmp.name, algo) for algo in algos}
    finally:
        os.unlink(tmp.name)
