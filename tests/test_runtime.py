import os
import sys
import tempfile
import unittest
from pathlib import Path

from agent_router.command_builder import build_env, render_command
from agent_router.exhaustion_state import ExhaustionState
from agent_router.ledger import Ledger
from agent_router.models import AgentConfig, DispatchRequest
from agent_router.outcomes import is_token_error, read_report_status
from agent_router.process_runner import ProcessRunner


def agent(**overrides: object) -> AgentConfig:
    values: dict[str, object] = dict(
        name="a", enabled=True, command=("tool", "{model}#{effort}", "{prompt}"),
        allowed_models=None, efforts=("low",), tiers={}, add_dir_flag=None,
        optional_dirs=(), unset_env_prefixes=(),
    )
    values.update(overrides)
    return AgentConfig(**values)  # type: ignore[arg-type]


class RenderTest(unittest.TestCase):
    def test_substitutes_without_expanding_prompt_contents(self) -> None:
        argv = render_command(agent(), {"model": "m", "effort": "low", "prompt": "use {model}"}, Path("/h"))
        self.assertEqual(argv, ["tool", "m#low", "use {model}"])

    def test_optional_dirs_added_only_if_present(self) -> None:
        home = Path(tempfile.mkdtemp())
        (home / "cache").mkdir()
        a = agent(add_dir_flag="--add-dir", optional_dirs=("~/cache", "~/absent"))
        argv = render_command(a, {"model": "m", "effort": "low", "prompt": "p"}, home)
        self.assertEqual(argv[-2:], ["--add-dir", str(home / "cache")])
        self.assertNotIn(str(home / "absent"), argv)

    def test_env_drops_prefixes_and_prepends_guard(self) -> None:
        env = build_env(
            agent(unset_env_prefixes=("CLAUDE",)),
            {"CLAUDECODE": "1", "PATH": "/bin"}, {"X": "1"}, Path("/guard"),
        )
        self.assertNotIn("CLAUDECODE", env)
        self.assertEqual(env["PATH"], "/guard:/bin")
        self.assertEqual(env["X"], "1")


class ProcessRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())
        self.runner = ProcessRunner(poll_seconds=0.05)

    def _run(self, code: str, run: int = 30, stall: int = 30) -> tuple[str, int]:
        outcome = self.runner.run(
            [sys.executable, "-c", code], self.dir, dict(os.environ),
            self.dir / "log", (), run, stall,
        )
        return outcome.reason, outcome.returncode

    def test_captures_exit_code_and_output(self) -> None:
        self.assertEqual(self._run("print('hi'); raise SystemExit(3)"), ("exited", 3))
        self.assertIn("hi", (self.dir / "log").read_text())

    def test_kills_stalled_process(self) -> None:
        self.assertEqual(self._run("import time; time.sleep(30)", stall=1)[0], "stalled")

    def test_kills_process_over_time_limit(self) -> None:
        code = "import time\nwhile True:\n print('x', flush=True); time.sleep(0.1)"
        self.assertEqual(self._run(code, run=1)[0], "timeout")

    def test_missing_binary_is_reported(self) -> None:
        outcome = self.runner.run(
            ["definitely-not-a-binary"], self.dir, dict(os.environ), self.dir / "log", (), 5, 5,
        )
        self.assertEqual(outcome.reason, "not_found")


class OutcomesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())

    def test_reads_last_line_status(self) -> None:
        report = self.dir / "r.md"
        report.write_text("notes\nStatus: DONE_WITH_CONCERNS\n\n")
        self.assertEqual(read_report_status(report, 0.0), "DONE_WITH_CONCERNS")

    def test_status_must_be_last_line(self) -> None:
        report = self.dir / "r.md"
        report.write_text("Status: DONE\nmore text\n")
        self.assertIsNone(read_report_status(report, 0.0))

    def test_stale_report_is_ignored(self) -> None:
        report = self.dir / "r.md"
        report.write_text("Status: DONE\n")
        os.utime(report, (1000, 1000))
        self.assertIsNone(read_report_status(report, 2000.0))

    def test_token_error_only_checks_log_tail(self) -> None:
        log = self.dir / "log"
        log.write_text("quota\n" + "x" * 20000 + "\nfine\n")
        self.assertFalse(is_token_error(log, ("quota",)))
        log.write_text("HTTP 429 Too Many\n")
        self.assertTrue(is_token_error(log, ("http 429",)))


class StateAndLedgerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())

    def test_exhaustion_expires_and_persists(self) -> None:
        now = [100.0]
        path = self.dir / "state.json"
        ExhaustionState(path, lambda: now[0]).mark("opencode", 50)
        state = ExhaustionState(path, lambda: now[0])
        self.assertTrue(state.is_exhausted("opencode"))
        self.assertFalse(state.is_exhausted("codex"))
        now[0] = 151.0
        self.assertFalse(state.is_exhausted("opencode"))

    def test_ledger_appends_agent_run_lines_only(self) -> None:
        path = self.dir / "progress.md"
        path.write_text("# SDD ledger — plan: x\n")
        request = DispatchRequest(
            host="claude", role="implementer", task="3", tier="cheap", effort="low",
            cwd=self.dir, workspace=self.dir, prompt_file=self.dir / "p", report_file=self.dir / "r",
        )
        Ledger(path, lambda: 0.0).record(request, "codex", "gpt", 2, "ok")
        lines = path.read_text().splitlines()
        self.assertEqual(lines[0], "# SDD ledger — plan: x")
        self.assertTrue(lines[1].startswith("Agent-run 1970-01-01T00:00:00Z task=3 role=implementer"))
        self.assertIn("runner=codex model=gpt effort=low attempt=2 result=ok", lines[1])
