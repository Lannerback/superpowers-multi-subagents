import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from agent_router.command_builder import build_env, render_command
from agent_router.config import load_config
from agent_router.exhaustion_state import ExhaustionState
from agent_router.ledger import Ledger
from agent_router.models import AgentConfig, DispatchRequest
from agent_router.outcomes import is_token_error, read_report_status
from agent_router.process_runner import ProcessRunner, RunOutcome

SHIPPED = (
    Path(__file__).resolve().parents[1]
    / "skills/subagent-driven-development-multi/config/agents.json"
)
EXITED_1 = RunOutcome(1, "exited")


def agent(**overrides: object) -> AgentConfig:
    values: dict[str, object] = dict(
        name="a", enabled=True, command=("tool", "{model}#{effort}", "{prompt}"),
        allowed_models=None, efforts=("low",), tiers={}, add_dir_flag=None,
        optional_dirs=(), unset_env_prefixes=(), token_error_patterns=(), guard_env_file_var=None,
    )
    values.update(overrides)
    return AgentConfig(**values)  # type: ignore[arg-type]


def _alive_after(pid_file: Path) -> bool:
    deadline = time.monotonic_ns() + 3_000_000_000
    while not pid_file.exists() and time.monotonic_ns() < deadline:
        time.sleep(0.05)
    if not pid_file.exists():
        return False
    try:
        os.kill(int(pid_file.read_text()), 0)
    except ProcessLookupError:
        return False
    return True


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
            {"CLAUDECODE": "1", "PATH": "/bin"}, {"X": "1"}, Path("/guard"), (),
        )
        self.assertNotIn("CLAUDECODE", env)
        self.assertEqual(env["PATH"], "/guard:/bin")
        self.assertEqual(env["X"], "1")

    def test_env_drops_host_session_prefixes_for_every_agent(self) -> None:
        env = build_env(agent(), {"HOST_TOKEN": "s", "KEEP": "1"}, {}, None, ("HOST_",))
        self.assertEqual(env, {"KEEP": "1"})


class ShippedEnvTest(unittest.TestCase):
    BASE = {
        "PATH": "/bin",
        "CLAUDECODE": "1",
        "CLAUDE_CODE_ENTRYPOINT": "sdk",
        "CLAUDE_CODE_MESSAGING_TOKEN": "secret",
        "CLAUDE_CODE_MESSAGING_SOCKET": "/s",
        "CLAUDE_CODE_SESSION_ID": "id",
        "CLAUDE_CODE_OAUTH_TOKEN": "login",
        "CLAUDE_CONFIG_DIR": "/config",
        "ANTHROPIC_API_KEY": "provider",
        "OPENAI_API_KEY": "provider",
    }
    HOST_VARS = (
        "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_MESSAGING_TOKEN",
        "CLAUDE_CODE_MESSAGING_SOCKET", "CLAUDE_CODE_SESSION_ID",
    )

    def setUp(self) -> None:
        self.config = load_config(SHIPPED)

    def _env(self, name: str) -> dict[str, str]:
        return build_env(
            self.config.agents[name], self.BASE, {}, None, self.config.host_session_env_prefixes
        )

    def test_claude_keeps_its_own_login(self) -> None:
        env = self._env("claude")
        self.assertEqual(env["CLAUDE_CODE_OAUTH_TOKEN"], "login")
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], "/config")

    def test_every_worker_loses_host_session_variables(self) -> None:
        for name in ("claude", "codex", "opencode"):
            env = self._env(name)
            for variable in self.HOST_VARS:
                self.assertNotIn(variable, env, f"{name}: {variable}")

    def test_provider_keys_stay(self) -> None:
        for name in ("claude", "codex", "opencode"):
            env = self._env(name)
            self.assertEqual(env["ANTHROPIC_API_KEY"], "provider", name)
            self.assertEqual(env["OPENAI_API_KEY"], "provider", name)


class ShippedCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(SHIPPED)

    def test_codex_tool_calls_do_not_use_a_login_shell(self) -> None:
        # A login shell runs path_helper on macOS, which puts /usr/bin ahead of the guard.
        command = self.config.agents["codex"].command
        self.assertEqual(command[command.index("allow_login_shell=false") - 1], "-c")

    def test_codex_still_runs_outside_git_repositories(self) -> None:
        self.assertIn("--skip-git-repo-check", self.config.agents["codex"].command)

    def test_claude_streams_so_silent_runs_do_not_look_stalled(self) -> None:
        command = self.config.agents["claude"].command
        self.assertEqual(command[command.index("--output-format") + 1], "stream-json")
        self.assertIn("--verbose", command)

    def test_claude_reapplies_the_guard_through_its_env_file(self) -> None:
        self.assertEqual(self.config.agents["claude"].guard_env_file_var, "CLAUDE_ENV_FILE")

    def test_stall_limit_outlasts_a_long_silent_build(self) -> None:
        self.assertGreaterEqual(self.config.limits.stall_seconds, 1200)


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

    def test_report_file_growth_counts_as_progress(self) -> None:
        report = self.dir / "report"
        code = (
            "import time\n"
            f"for i in range(8):\n open({str(report)!r}, 'a').write('x'); time.sleep(0.4)"
        )
        outcome = self.runner.run(
            [sys.executable, "-c", code], self.dir, dict(os.environ), self.dir / "log", (report,), 30, 2,
        )
        self.assertEqual(outcome.reason, "exited")

    def test_terminate_tolerates_a_vanished_or_zombie_group(self) -> None:
        for error in (ProcessLookupError, PermissionError):
            process = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
            with mock.patch("os.killpg", side_effect=error):
                self.runner._terminate(process)
            self.assertIsNotNone(process.returncode, error)

    def test_real_zombie_does_not_crash_terminate(self) -> None:
        process = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
        time.sleep(0.5)
        self.runner._terminate(process)
        self.assertEqual(process.returncode, 0)

    def test_exception_during_supervision_terminates_the_worker(self) -> None:
        marker = self.dir / "pid"
        code = (
            "import os, time\n"
            f"open({str(marker)!r}, 'w').write(str(os.getpid()))\n"
            "time.sleep(30)"
        )
        with mock.patch("time.monotonic", side_effect=[0.0, 0.0, KeyboardInterrupt]):
            with self.assertRaises(KeyboardInterrupt):
                self.runner.run(
                    [sys.executable, "-c", code], self.dir, dict(os.environ), self.dir / "log", (), 30, 30,
                )
        self.assertFalse(_alive_after(marker))


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
        self.assertFalse(is_token_error(EXITED_1, log, ("quota",)))
        log.write_text("HTTP 429 Too Many\n")
        self.assertTrue(is_token_error(EXITED_1, log, ("http 429",)))

    def test_token_error_needs_a_non_zero_exit(self) -> None:
        log = self.dir / "log"
        log.write_text("quota\n")
        self.assertFalse(is_token_error(RunOutcome(0, "exited"), log, ("quota",)))
        self.assertFalse(is_token_error(RunOutcome(-15, "stalled"), log, ("quota",)))
        self.assertFalse(is_token_error(RunOutcome(-15, "timeout"), log, ("quota",)))
        self.assertTrue(is_token_error(EXITED_1, log, ("quota",)))


class ShippedTokenPatternsTest(unittest.TestCase):
    """Strings below come from real CLI output or from the CLI binaries."""

    TOKEN_ERRORS = {
        "claude": (
            "Failed to authenticate: OAuth session expired and could not be refreshed",
            "Not logged in · Please run /login",
            "Invalid API key · Fix external API key",
            "API Error: 429 rate limited",
            "API Error: Request rejected (429) · This request would exceed your rate limit",
            '"api_error_status":429,"result":"x"',
            '{"type":"error","error":{"type":"rate_limit_error"}}',
            "There's an issue with the selected model (x). It may not exist",
            "You've hit your session limit",
        ),
        "codex": (
            "ERROR: exceeded retry limit, last status: 429 Too Many Requests",
            "ERROR: unexpected status 401 Unauthorized: Unauthorized, url: http://x/v1/responses",
            "ERROR: You've hit your usage limit. Upgrade to Pro",
            'code: usage_limit_reached',
            'ERROR: {"detail":"The bogus model is not supported when using Codex with a ChatGPT account."}',
            "The model requires a newer version of Codex",
            "Your access token could not be refreshed because your refresh token has expired",
        ),
        "opencode": (
            "Error: Model unavailable: bogus/bogus",
            "ProviderModelNotFoundError",
            "ProviderAuthError: API key is missing",
            "HTTP 429 Too Many Requests",
            "rate_limit_error",
            "usage_limit_reached",
        ),
    }
    NOT_TOKEN_ERRORS = (
        "failed to refresh OAuth tokens for server trello: unauthorized_client",
        "all authentication tests pass",
        "FAILED tests/test_login.py - 401 Unauthorized",
        "Added rate limit middleware",
        "quota table migrated",
        "ran 429 tests",
    )

    def setUp(self) -> None:
        self.config = load_config(SHIPPED)
        self.dir = Path(tempfile.mkdtemp())

    def _matches(self, name: str, line: str) -> bool:
        log = self.dir / "log"
        log.write_text(f"some output\n{line}\n")
        return is_token_error(EXITED_1, log, self.config.agents[name].token_error_patterns)

    def test_real_token_failures_are_recognised(self) -> None:
        for name, lines in self.TOKEN_ERRORS.items():
            for line in lines:
                self.assertTrue(self._matches(name, line), f"{name}: {line}")

    def test_ordinary_failures_are_not_token_errors(self) -> None:
        for name in self.TOKEN_ERRORS:
            for line in self.NOT_TOKEN_ERRORS:
                self.assertFalse(self._matches(name, line), f"{name}: {line}")

    def test_patterns_are_valid_regexes(self) -> None:
        for agent_config in self.config.agents.values():
            for pattern in agent_config.token_error_patterns:
                re.compile(pattern)


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
