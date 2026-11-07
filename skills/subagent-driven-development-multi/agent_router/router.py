from __future__ import annotations

import json
import shlex
import shutil
import time
from collections.abc import Callable, Mapping
from pathlib import Path

from agent_router.command_builder import build_env, render_command
from agent_router.exhaustion_state import ExhaustionState
from agent_router.git_state import git_fingerprint, git_toplevel
from agent_router.ledger import Ledger
from agent_router.models import AgentConfig, DispatchRequest, DispatchResult, RouterConfig
from agent_router.outcomes import is_token_error, read_report_status
from agent_router.process_runner import ProcessRunner
from agent_router.prompts import build_prompt

EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_EXHAUSTED = 75

GIT_POLICY_VIOLATION = "git_policy_violation"
GUARD_ROOT_VAR = "AGENT_ROUTER_GUARD_ROOT"


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
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self._config = config
        self._which = which
        self._runner = runner
        self._state = state
        self._ledger = ledger
        self._guard_dir = guard_dir
        self._home = home
        self._environ = environ
        self._failed_before = False

    def dispatch(self, request: DispatchRequest) -> DispatchResult:
        for agent in self._candidates(request):
            result = self._try_agent(agent, request)
            if result is not None:
                return result
        if self._config.host_fallback.get(request.host) == "subagent":
            return DispatchResult(
                "EXHAUSTED", "none", "none", EXIT_EXHAUSTED, None,
                host_prompt=self._write_host_prompt(request),
            )
        return DispatchResult("BLOCKED", "none", "none", EXIT_BLOCKED, None)

    def _candidates(self, request: DispatchRequest) -> list[AgentConfig]:
        agents = (self._config.agents[name] for name in self._config.order if name != request.host)
        usable = (a for a in agents if a.enabled and not self._state.is_exhausted(a.name))
        return [agent for agent in usable if self._is_installed(agent, request)]

    def _is_installed(self, agent: AgentConfig, request: DispatchRequest) -> bool:
        if self._which(agent.command[0]) is not None:
            return True
        self._ledger.record(request, agent.name, agent.tiers[request.tier], 0, "not_installed")
        return False

    def _try_agent(self, agent: AgentConfig, request: DispatchRequest) -> DispatchResult | None:
        model = agent.tiers[request.tier]
        if agent.efforts and request.effort not in agent.efforts:
            self._ledger.record(request, agent.name, model, 0, "effort_unsupported")
            return None
        for attempt in range(1, self._config.limits.error_attempts + 1):
            log = request.workspace / f"task-{request.task}-{request.role}-{agent.name}-{attempt}.log"
            started_at = time.time()
            git_before = self._git_baseline(request)
            outcome = self._runner.run(
                render_command(agent, self._values(model, request), self._home),
                request.cwd,
                self._worker_env(agent, request),
                log,
                (request.workspace / "progress.md", request.report_file),
                self._config.limits.run_seconds,
                self._config.limits.stall_seconds,
            )
            if git_before is not None and git_before != git_fingerprint(request.cwd, self._environ):
                self._ledger.record(request, agent.name, model, attempt, GIT_POLICY_VIOLATION)
                return DispatchResult(
                    "BLOCKED", agent.name, model, EXIT_BLOCKED, log,
                    note=f"{GIT_POLICY_VIOLATION}: HEAD or the index changed during the run",
                )
            status = read_report_status(request.report_file, started_at)
            if outcome.returncode == 0 and status is not None:
                self._ledger.record(request, agent.name, model, attempt, "ok")
                return DispatchResult(status, agent.name, model, EXIT_OK, log)
            self._failed_before = True
            if is_token_error(outcome, log, agent.token_error_patterns):
                self._ledger.record(request, agent.name, model, attempt, "token_error")
                self._state.mark(agent.name, self._config.limits.token_cooldown_seconds)
                return None
            self._ledger.record(request, agent.name, model, attempt, f"{outcome.reason}_rc_{outcome.returncode}")
            if outcome.reason == "not_found":
                return None
        return None

    def _no_commit(self) -> bool:
        return self._config.git_policy == "no-commit"

    def _git_baseline(self, request: DispatchRequest) -> str | None:
        return git_fingerprint(request.cwd, self._environ) if self._no_commit() else None

    def _values(self, model: str, request: DispatchRequest) -> dict[str, str]:
        return {
            "model": model,
            "effort": request.effort,
            "cwd": str(request.cwd),
            "workspace": str(request.workspace),
            "title": f"task-{request.task}-{request.role}",
            "prompt": self._prompt(request, self._failed_before),
        }

    def _prompt(self, request: DispatchRequest, retry: bool) -> str:
        return build_prompt(request.prompt_file.read_text(), request, self._no_commit(), retry)

    def _write_host_prompt(self, request: DispatchRequest) -> Path:
        path = request.workspace / f"task-{request.task}-{request.role}-host-prompt.md"
        path.write_text(self._prompt(request, retry=True))
        return path

    def _worker_env(self, agent: AgentConfig, request: DispatchRequest) -> dict[str, str]:
        extra = self._agent_env(request)
        if self._guard_dir is not None:
            extra[GUARD_ROOT_VAR] = git_toplevel(request.cwd, self._environ) or ""
            if agent.guard_env_file_var:
                extra[agent.guard_env_file_var] = str(self._write_guard_env_file(request.workspace))
        return build_env(
            agent, self._environ, extra, self._guard_dir, self._config.host_session_env_prefixes
        )

    def _write_guard_env_file(self, workspace: Path) -> Path:
        # Some CLIs rebuild PATH for each tool call and source this file afterwards.
        path = workspace / "git-guard-env.sh"
        path.write_text(f'export PATH={shlex.quote(str(self._guard_dir))}:"$PATH"\n')
        return path

    def _agent_env(self, request: DispatchRequest) -> dict[str, str]:
        path = request.workspace / "agent-env.json"
        if not path.exists():
            return {}
        try:
            raw: object = json.loads(path.read_text())
        except ValueError as error:
            raise ValueError(f"{path}: invalid JSON: {error}") from error
        if not isinstance(raw, dict):
            raise ValueError(f"{path} must be an object")
        return {str(key): str(value) for key, value in raw.items()}
