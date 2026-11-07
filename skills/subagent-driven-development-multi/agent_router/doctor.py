from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from agent_router.command_builder import build_env, render_command
from agent_router.models import AgentConfig, RouterConfig
from agent_router.process_runner import ProcessRunner

_SMOKE_PROMPT = "Reply with exactly: ok"
_SMOKE_SECONDS = 180


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def check_agents(
    config: RouterConfig,
    host: str,
    which: Callable[[str], str | None],
    smoke: bool = False,
) -> list[CheckResult]:
    results = []
    for name in config.order:
        agent = config.agents[name]
        if not agent.enabled or name == host:
            continue
        path = which(agent.command[0])
        if path is None:
            results.append(CheckResult(name, False, f"{agent.command[0]} not on PATH"))
        elif smoke:
            results.append(_smoke(agent, config.host_session_env_prefixes))
        else:
            results.append(CheckResult(name, True, path))
    return results


def _smoke(agent: AgentConfig, host_session_prefixes: Sequence[str]) -> CheckResult:
    workdir = Path(tempfile.mkdtemp())
    model = agent.tiers["cheap"]
    argv = render_command(
        agent,
        {"model": model, "effort": "low", "cwd": str(workdir), "workspace": str(workdir),
         "title": "doctor-smoke", "prompt": _SMOKE_PROMPT},
        Path.home(),
    )
    log = workdir / "smoke.log"
    env = build_env(agent, os.environ, {}, None, host_session_prefixes)
    outcome = ProcessRunner().run(argv, workdir, env, log, (), _SMOKE_SECONDS, _SMOKE_SECONDS)
    ok = outcome.returncode == 0 and "ok" in log.read_text(errors="replace").lower()
    return CheckResult(agent.name, ok, f"{model}: {outcome.reason} rc={outcome.returncode} log={log}")
