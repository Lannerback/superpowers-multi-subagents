from __future__ import annotations

import argparse
import os
import shutil
import time
from pathlib import Path
from typing import NoReturn

from agent_router.config import load_config, resolve_config_path
from agent_router.doctor import check_agents
from agent_router.exhaustion_state import ExhaustionState
from agent_router.ledger import Ledger
from agent_router.models import EFFORTS, OTHER_HOST, TIERS, DispatchRequest, RouterConfig
from agent_router.process_runner import ProcessRunner, raise_on_termination_signals
from agent_router.router import AgentRouter
from agent_router.upstream import find_drift, resolve_skills_dir, write_lock

SKILL_ROOT = Path(__file__).resolve().parent.parent
EXIT_ERROR = 2


def main(argv: list[str] | None = None) -> int:
    raise_on_termination_signals()
    try:
        return _execute(_parser().parse_args(argv))
    except (ValueError, LookupError, OSError) as error:
        return _report_error(str(error))


def _execute(args: argparse.Namespace) -> int:
    config = load_config(resolve_config_path(SKILL_ROOT, Path.home()))
    if args.command == "run":
        _require_known_host(args.host, config)
        return _run(args, config)
    if args.command == "upstream-path":
        print(resolve_skills_dir(Path.home(), os.environ))
        return 0
    if args.command == "upstream-check":
        return _upstream_check(args.accept)
    if args.command == "doctor":
        _require_known_host(args.host, config)
        return _doctor(config, args.host, args.smoke)
    print(config.git_policy)
    return 0


def _report_error(message: str) -> int:
    print("Status: ERROR")
    print(message)
    return EXIT_ERROR


def _require_known_host(host: str, config: RouterConfig) -> None:
    if host != OTHER_HOST and host not in config.agents:
        known = ", ".join((*config.agents, OTHER_HOST))
        raise ValueError(f"unknown --host {host!r}: use one of {known}")


def _run(args: argparse.Namespace, config: RouterConfig) -> int:
    request = _request(args)
    guard = SKILL_ROOT / "scripts" / "git-guard" if config.git_policy != "allow" else None
    router = AgentRouter(
        config,
        ProcessRunner(),
        ExhaustionState(request.workspace / "router-state.json", time.time),
        Ledger(request.workspace / "progress.md", time.time),
        guard,
        Path.home(),
        dict(os.environ),
    )
    result = router.dispatch(request)
    print(f"Status: {result.status}")
    print(f"runner={result.runner} model={result.model} log={result.log}")
    if result.note:
        print(result.note)
    if result.host_prompt is not None:
        print(f"host_prompt={result.host_prompt}")
    return result.exit_code


def _request(args: argparse.Namespace) -> DispatchRequest:
    request = DispatchRequest(
        host=args.host, role=args.role, task=args.task, tier=args.tier, effort=args.effort,
        cwd=Path(args.cwd).resolve(), workspace=Path(args.workspace).resolve(),
        prompt_file=Path(args.prompt_file).resolve(), report_file=Path(args.report_file).resolve(),
        git_grants=tuple(args.git_grant),
    )
    for flag, folder in (
        ("--cwd", request.cwd),
        ("--workspace", request.workspace),
        ("--report-file folder", request.report_file.parent),
    ):
        if not folder.is_dir():
            raise ValueError(f"{flag} is not a directory: {folder}")
    if not request.prompt_file.is_file():
        raise ValueError(f"--prompt-file is not a file: {request.prompt_file}")
    return request


def _upstream_check(accept: bool) -> int:
    skills = resolve_skills_dir(Path.home(), os.environ)
    lock = SKILL_ROOT / "config" / "upstream-lock.json"
    if accept:
        write_lock(skills, lock)
        print(f"accepted {skills}")
        return 0
    for name in find_drift(skills, lock):
        print(f"upstream changed since last review: {name}")
    return 0


def _doctor(config: RouterConfig, host: str, smoke: bool) -> int:
    results = check_agents(config, host, shutil.which, smoke)
    for result in results:
        print(f"{'ok  ' if result.ok else 'FAIL'} {result.name}: {result.detail}")
    try:
        print(f"ok   superpowers: {resolve_skills_dir(Path.home(), os.environ)}")
    except LookupError as error:
        print(f"FAIL superpowers: {error}")
        return 1
    return 0 if all(result.ok for result in results) else 1


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise SystemExit(_report_error(f"{self.prog}: {message}"))


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="agent-router")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="dispatch one prompt through the agent chain")
    run.add_argument("--host", required=True)
    run.add_argument("--role", required=True)
    run.add_argument("--task", required=True)
    run.add_argument("--tier", required=True, choices=TIERS)
    run.add_argument("--effort", required=True, choices=EFFORTS)
    run.add_argument("--cwd", required=True)
    run.add_argument("--workspace", required=True)
    run.add_argument("--prompt-file", required=True)
    run.add_argument("--report-file", required=True)
    run.add_argument(
        "--git-grant", action="append", default=[], metavar="ARGS",
        help="one exact git command the user approved, e.g. \"push origin feature\"; repeatable",
    )
    commands.add_parser("git-policy", help="print the configured git policy")
    commands.add_parser("upstream-path", help="print the superpowers skills directory")
    upstream = commands.add_parser("upstream-check", help="warn if upstream changed since review")
    upstream.add_argument("--accept", action="store_true")
    doctor = commands.add_parser("doctor", help="check prerequisites")
    doctor.add_argument("--host", required=True)
    doctor.add_argument("--smoke", action="store_true")
    return parser
