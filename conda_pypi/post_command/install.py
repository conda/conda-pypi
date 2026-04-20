from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

from conda.base.context import context
from conda.exceptions import CondaFileIOError, CondaVerificationError
from conda.reporters import get_spinner

from conda_pypi.main import PyPIDistribution, compute_record_sum, run_pip_install
from conda_pypi.python_paths import get_env_site_packages

if TYPE_CHECKING:
    from typing import Iterable, Literal

log = getLogger(f"conda.{__name__}")


def _prepare_pypi_transaction(lines: Iterable[str]) -> dict[str, dict[str, str]]:
    pkgs = {}
    for line in lines:
        dist = PyPIDistribution.from_lockfile_line(line)
        pkgs[(dist.name, dist.version)] = {
            "url": dist.find_wheel_url(),
            "hashes": dist.record_checksums,
        }
    return pkgs


def _verify_pypi_transaction(
    prefix: str,
    pkgs: dict[str, dict[str, str]],
    on_error: Literal["ignore", "warn", "error"] = "warn",
):
    site_packages = get_env_site_packages(prefix)
    errors = []
    dist_infos = [path for path in site_packages.glob("*.dist-info") if path.is_dir()]
    for (name, version), pkg in pkgs.items():
        norm_name = name.lower().replace("-", "_").replace(".", "_")
        dist_info = next(
            (
                d
                for d in dist_infos
                if d.stem.rsplit("-", 1) in ([name, version], [norm_name, version])
            ),
            None,
        )
        if not dist_info:
            errors.append(f"Could not find installation for {name}=={version}")
            continue

        expected_hashes = pkg.get("hashes")
        if expected_hashes:
            found_hashes = compute_record_sum(dist_info / "RECORD", expected_hashes.keys())
            log.info("Verifying %s==%s with %s", name, version, ", ".join(expected_hashes))
            for algo, expected_hash in expected_hashes.items():
                found_hash = found_hashes.get(algo)
                if found_hash and expected_hash != found_hash:
                    msg = (
                        "%s checksum for %s==%s didn't match! Expected=%s, found=%s",
                        algo,
                        name,
                        version,
                        expected_hash,
                        found_hash,
                    )
                    if on_error == "warn":
                        log.warning(*msg)
                    elif on_error == "error":
                        errors.append(msg[0] % msg[1:])
                    else:
                        log.debug(*msg)
    if errors:
        errors = "\n- ".join(errors)
        raise CondaVerificationError(f"PyPI packages checksum verification failed:\n- {errors}")


def post_command(command: str):
    if command not in ("install", "create"):
        return 0

    pypi_lines = _pypi_lines_from_paths()
    if not pypi_lines:
        return 0

    with get_spinner("\nPreparing PyPI transaction"):
        pkgs = _prepare_pypi_transaction(pypi_lines)

    with get_spinner("Executing PyPI transaction"):
        run_pip_install(
            context.target_prefix,
            args=[pkg["url"] for pkg in pkgs.values()],
            dry_run=context.dry_run,
            quiet=context.quiet,
            verbosity=context.verbosity,
            force_reinstall=context.force_reinstall,
            yes=context.always_yes,
            check=True,
        )

    with get_spinner("Verifying PyPI transaction"):
        on_error_dict = {"disabled": "ignore", "warn": "warn", "enabled": "error"}
        on_error = on_error_dict.get(context.safety_checks, "warn")
        _verify_pypi_transaction(context.target_prefix, pkgs, on_error=on_error)


def _pypi_lines_from_paths(paths: Iterable[str] | None = None) -> list[str]:
    if paths is None:
        file_arg = context.raw_data["cmd_line"].get("file")
        if file_arg is None:
            return []
        paths = file_arg.value(None)
    lines = []
    line_prefix = PyPIDistribution._line_prefix
    for path in paths:
        path = path.value(None)
        try:
            with open(path) as f:
                for line in f:
                    if line.startswith(line_prefix):
                        lines.append(line[len(line_prefix) :])
        except OSError as exc:
            raise CondaFileIOError(f"Could not process {path}") from exc
    return lines
