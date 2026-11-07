from __future__ import annotations

import argparse
import os
import shutil
import time
from pathlib import Path

from agent_router.doctor import check_agents
from agent_router.config import load_config, resolve_config_path
from agent_router.exhaustion_state import ExhaustionState
from agent_router.ledger import Ledger
from agent_router.models import EFFORTS, TIERS, DispatchRequest, RouterConfig
from agent_router.process_runner import ProcessRunner
from agent_router.router import AgentRouter
from agent_router.upstream import find_drift, resolve_skills_dir, write_lock

SKILL_ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = load_config(resolve_config_path(SKILL_ROOT, Path.home()))
    if args.command == "run":
        return _run(args, config)
    if args.command == "upstream-path":
        print(resolve_skills_dir(Path.home(), os.environ))
        return 0
    if args.command == "upstream-check":
        return _upstream_check(args.accept)
    if args.command == "doctor":
        return _doctor(config, args.host, args.smoke)
    print(config.git_policy)
    return 0


def _run(args: argparse.Namespace, config: RouterConfig) -> int:
    workspace = Path(args.workspace).resolve()
    guard = SKILL_ROOT / "scripts" / "git-guard" if config.git_policy == "no-commit" else None
    router = AgentRouter(
        config,
        ProcessRunner(),
        ExhaustionState(workspace / "router-state.json", time.time),
        Ledger(workspace / "progress.md", time.time),
        guard,
        Path.home(),
        dict(os.environ),
    )
    result = router.dispatch(
        DispatchRequest(
            host=args.host, role=args.role, task=args.task, tier=args.tier, effort=args.effort,
            cwd=Path(args.cwd).resolve(), workspace=workspace,
            prompt_file=Path(args.prompt_file).resolve(),
            report_file=Path(args.report_file).resolve(),
        )
    )
    print(f"Status: {result.status}")
    print(f"runner={result.runner} model={result.model} log={result.log}")
    return result.exit_code


def _upstream_check(accept: bool) -> int:
    skills = resolve_skills_dir(Path.home(), os.environ)
    lock = SKILL_ROOT / "config" / "upstream-lock.json"
    if accept:
        write_lock(skills, lock)
        print(f"accepted {skills}")
        return 0
    drift = find_drift(skills, lock)
    for name in drift:
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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-router")
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
    commands.add_parser("git-policy", help="print the configured git policy")
    commands.add_parser("upstream-path", help="print the superpowers skills directory")
    upstream = commands.add_parser("upstream-check", help="warn if upstream changed since review")
    upstream.add_argument("--accept", action="store_true")
    doctor = commands.add_parser("doctor", help="check prerequisites")
    doctor.add_argument("--host", required=True)
    doctor.add_argument("--smoke", action="store_true")
    return parser
