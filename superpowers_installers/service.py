from __future__ import annotations

import shlex
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from agent_router.upstream import find_drift
from superpowers_installers.base import CommandRunner, HostInstaller, HostResult

COMMAND_TIMEOUT_SECONDS = 300.0
Log = Callable[[str], None]


def install_missing(
    hosts: Sequence[str],
    home: Path,
    installers: Mapping[str, HostInstaller],
    runner: CommandRunner,
    log: Log,
) -> list[HostResult]:
    """Install superpowers for each selected host that lacks it, then re-check each one."""
    results = [_install_host(installers[host], home, runner, log) for host in dict.fromkeys(hosts)]
    for result in results:
        log(f"host={result.host} result={result.outcome}" + (f" detail={result.detail}" if result.detail else ""))
    return results


def drift_warnings(skills_dir: Path, lock_path: Path) -> list[str]:
    """Upstream files that differ from the reviewed lock. A warning only, never a failure."""
    return [f"upstream changed since last review: {name}" for name in find_drift(skills_dir, lock_path)]


def _install_host(installer: HostInstaller, home: Path, runner: CommandRunner, log: Log) -> HostResult:
    if installer.is_installed(home):
        return HostResult(installer.host, "present")
    if not installer.commands:
        return HostResult(installer.host, "manual", "no scriptable install")
    for argv in installer.commands:
        log(f"host={installer.host} run: {shlex.join(argv)}")
        failure = _run(runner, argv)
        if failure:
            return HostResult(installer.host, "failed", failure)
    if installer.is_installed(home):
        return HostResult(installer.host, "installed")
    return HostResult(installer.host, "not-detected", "install finished but no superpowers copy was found")


def _run(runner: CommandRunner, argv: Sequence[str]) -> str:
    """Empty string on success, else the reason."""
    try:
        done = runner.run(argv, COMMAND_TIMEOUT_SECONDS)
    except (LookupError, TimeoutError) as error:
        return str(error)
    if done.returncode == 0:
        return ""
    tail = " | ".join((done.stderr or done.stdout).strip().splitlines()[-3:])
    return f"exit {done.returncode}: {tail}" if tail else f"exit {done.returncode}"
