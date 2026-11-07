import json
import os
import tempfile
import unittest
from pathlib import Path

from agent_router.exhaustion_state import ExhaustionState
from agent_router.ledger import Ledger
from agent_router.models import AgentConfig, DispatchRequest, Limits, RouterConfig
from agent_router.process_runner import ProcessRunner
from agent_router.router import EXIT_BLOCKED, EXIT_EXHAUSTED, EXIT_OK, AgentRouter

OK = 'printf "Status: DONE\\n" > "$REPORT"'
FAIL = "exit 1"
TOKEN = 'echo "HTTP 429 quota" ; exit 1'


class RouterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())
        self.ws = self.dir / "ws"
        self.ws.mkdir()
        (self.ws / "progress.md").write_text("# SDD ledger — plan: p\n")
        self.report = self.ws / "report.md"
        self.prompt = self.ws / "prompt.md"
        self.prompt.write_text("do the task")
        (self.ws / "agent-env.json").write_text(json.dumps({"REPORT": str(self.report)}))
        self.agents: dict[str, AgentConfig] = {}

    def _agent(self, name: str, body: str, enabled: bool = True) -> None:
        script = self.dir / name
        calls = self.dir / f"{name}.calls"
        prompts = self.dir / f"{name}.prompt"
        script.write_text(
            f'#!/usr/bin/env bash\necho call >> "{calls}"\nprintf "%s" "$1" > "{prompts}"\n{body}\n'
        )
        script.chmod(0o755)
        self.agents[name] = AgentConfig(
            name=name, enabled=enabled, command=(str(script), "{prompt}"), allowed_models=None,
            efforts=("low",), tiers={"cheap": f"{name}-m"}, add_dir_flag=None, optional_dirs=(),
            unset_env_prefixes=(),
        )

    def _calls(self, name: str) -> int:
        path = self.dir / f"{name}.calls"
        return len(path.read_text().splitlines()) if path.exists() else 0

    def _dispatch(self, host: str = "claude", fallback: str = "subagent", policy: str = "allow"):
        config = RouterConfig(
            order=tuple(self.agents), agents=self.agents,
            limits=Limits(30, 30, 3, 1000),
            host_fallback={"claude": fallback}, git_policy=policy,
            token_error_patterns=("quota",),
        )
        router = AgentRouter(
            config, ProcessRunner(poll_seconds=0.02),
            ExhaustionState(self.ws / "router-state.json", lambda: 100.0),
            Ledger(self.ws / "progress.md", lambda: 0.0),
            guard_dir=None, home=self.dir, environ=dict(os.environ),
        )
        return router.dispatch(DispatchRequest(
            host=host, role="implementer", task="1", tier="cheap", effort="low",
            cwd=self.dir, workspace=self.ws, prompt_file=self.prompt, report_file=self.report,
        ))

    def _ledger(self) -> str:
        return (self.ws / "progress.md").read_text()

    def test_first_agent_success(self) -> None:
        self._agent("a", OK)
        self._agent("b", OK)
        result = self._dispatch()
        self.assertEqual((result.status, result.runner, result.exit_code), ("DONE", "a", EXIT_OK))
        self.assertEqual(self._calls("b"), 0)
        self.assertIn("runner=a model=a-m effort=low attempt=1 result=ok", self._ledger())

    def test_host_agent_is_never_dispatched(self) -> None:
        self._agent("claude", OK)
        self._agent("b", OK)
        self.assertEqual(self._dispatch(host="claude").runner, "b")
        self.assertEqual(self._calls("claude"), 0)

    def test_disabled_agent_is_skipped(self) -> None:
        self._agent("a", OK, enabled=False)
        self._agent("b", OK)
        self.assertEqual(self._dispatch().runner, "b")

    def test_errors_retry_then_move_on(self) -> None:
        self._agent("a", FAIL)
        self._agent("b", OK)
        self.assertEqual(self._dispatch().runner, "b")
        self.assertEqual(self._calls("a"), 3)

    def test_token_error_moves_on_at_once_and_is_remembered(self) -> None:
        self._agent("a", TOKEN)
        self._agent("b", OK)
        self.assertEqual(self._dispatch().runner, "b")
        self.assertEqual(self._calls("a"), 1)
        self.assertEqual(self._dispatch().runner, "b")
        self.assertEqual(self._calls("a"), 1)
        self.assertIn("result=token_error", self._ledger())

    def test_exit_zero_without_report_is_an_error(self) -> None:
        self._agent("a", "exit 0")
        self._agent("b", OK)
        self.assertEqual(self._dispatch().runner, "b")
        self.assertEqual(self._calls("a"), 3)

    def test_retry_warns_about_partial_work(self) -> None:
        self._agent("a", FAIL)
        self._agent("b", OK)
        self._dispatch()
        self.assertIn("partial edits", (self.dir / "b.prompt").read_text())

    def test_exhausted_falls_back_to_host_subagent(self) -> None:
        self._agent("a", TOKEN)
        result = self._dispatch()
        self.assertEqual((result.status, result.exit_code), ("EXHAUSTED", EXIT_EXHAUSTED))

    def test_exhausted_blocks_when_configured(self) -> None:
        self._agent("a", TOKEN)
        result = self._dispatch(fallback="block")
        self.assertEqual((result.status, result.exit_code), ("BLOCKED", EXIT_BLOCKED))

    def test_unknown_host_blocks_by_default(self) -> None:
        self._agent("a", TOKEN)
        self.assertEqual(self._dispatch(host="other").exit_code, EXIT_BLOCKED)

    def test_agent_blocked_status_is_a_successful_dispatch(self) -> None:
        self._agent("a", 'printf "Status: BLOCKED\\n" > "$REPORT"')
        self._agent("b", OK)
        result = self._dispatch()
        self.assertEqual((result.status, result.runner, result.exit_code), ("BLOCKED", "a", EXIT_OK))

    def test_unsupported_effort_skips_agent(self) -> None:
        self._agent("a", OK)
        self.agents["a"] = AgentConfig(**{**self.agents["a"].__dict__, "efforts": ("max",)})
        self._agent("b", OK)
        self.assertEqual(self._dispatch().runner, "b")
        self.assertIn("runner=a model=a-m effort=low attempt=0 result=effort_unsupported", self._ledger())
