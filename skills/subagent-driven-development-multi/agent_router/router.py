from __future__ import annotations

import json
import time
from collections.abc import Mapping
from pathlib import Path

from agent_router.command_builder import build_env, render_command
from agent_router.exhaustion_state import ExhaustionState
from agent_router.ledger import Ledger
from agent_router.models import AgentConfig, DispatchRequest, DispatchResult, RouterConfig
from agent_router.outcomes import is_token_error, read_report_status
from agent_router.process_runner import ProcessRunner

EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_EXHAUSTED = 75

_RETRY_NOTE = (
    "\n\nA previous attempt failed. The working tree may contain its partial edits: "
    "inspect them before you start, and keep or replace them as the task requires."
)


class AgentRouter:
    def __init__(
        self,
        config: RouterConfig,
        runner: ProcessRunner,
        state: ExhaustionState,
        ledger: Ledger,
        guard_dir: Path | None,
        home: Path,
        environ: Mapping[str, str],
    ) -> None:
        self._config = config
        self._runner = runner
        self._state = state
        self._ledger = ledger
        self._guard_dir = guard_dir
        self._home = home
        self._environ = environ
        self._failed_before = False

    def dispatch(self, request: DispatchRequest) -> DispatchResult:
        for agent in self._candidates(request.host):
            result = self._try_agent(agent, request)
            if result is not None:
                return result
        if self._config.host_fallback.get(request.host) == "subagent":
            return DispatchResult("EXHAUSTED", "none", "none", EXIT_EXHAUSTED, None)
        return DispatchResult("BLOCKED", "none", "none", EXIT_BLOCKED, None)

    def _candidates(self, host: str) -> list[AgentConfig]:
        agents = (self._config.agents[name] for name in self._config.order if name != host)
        return [a for a in agents if a.enabled and not self._state.is_exhausted(a.name)]

    def _try_agent(self, agent: AgentConfig, request: DispatchRequest) -> DispatchResult | None:
        model = agent.tiers[request.tier]
        if agent.efforts and request.effort not in agent.efforts:
            self._ledger.record(request, agent.name, model, 0, "effort_unsupported")
            return None
        for attempt in range(1, self._config.limits.error_attempts + 1):
            log = request.workspace / f"task-{request.task}-{request.role}-{agent.name}-{attempt}.log"
            started_at = time.time()
            outcome = self._runner.run(
                render_command(agent, self._values(model, request), self._home),
                request.cwd,
                build_env(agent, self._environ, self._agent_env(request), self._guard_dir),
                log,
                (request.workspace / "progress.md",),
                self._config.limits.run_seconds,
                self._config.limits.stall_seconds,
            )
            status = read_report_status(request.report_file, started_at)
            if outcome.returncode == 0 and status is not None:
                self._ledger.record(request, agent.name, model, attempt, "ok")
                return DispatchResult(status, agent.name, model, EXIT_OK, log)
            self._failed_before = True
            if is_token_error(log, self._config.token_error_patterns):
                self._ledger.record(request, agent.name, model, attempt, "token_error")
                self._state.mark(agent.name, self._config.limits.token_cooldown_seconds)
                return None
            self._ledger.record(request, agent.name, model, attempt, f"{outcome.reason}_rc_{outcome.returncode}")
            if outcome.reason == "not_found":
                return None
        return None

    def _values(self, model: str, request: DispatchRequest) -> dict[str, str]:
        prompt = request.prompt_file.read_text()
        return {
            "model": model,
            "effort": request.effort,
            "cwd": str(request.cwd),
            "workspace": str(request.workspace),
            "title": f"task-{request.task}-{request.role}",
            "prompt": prompt + _RETRY_NOTE if self._failed_before else prompt,
        }

    def _agent_env(self, request: DispatchRequest) -> dict[str, str]:
        path = request.workspace / "agent-env.json"
        if not path.exists():
            return {}
        raw: object = json.loads(path.read_text())
        if not isinstance(raw, dict):
            raise ValueError(f"{path} must be an object")
        return {str(key): str(value) for key, value in raw.items()}
