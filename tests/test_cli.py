import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1] / "skills" / "subagent-driven-development-multi"
ROUTER = SKILL_ROOT / "scripts" / "agent-router"
REAL_GIT = shutil.which("git")


class CliCase(unittest.TestCase):
    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp()).resolve()
        self.repo = self.home / "repo"
        self.repo.mkdir()
        for args in (["init", "-q"], ["config", "user.name", "t"], ["config", "user.email", "t@t"]):
            subprocess.run(["git", *args], cwd=self.repo, check=True)
        self.ws = self.home / "ws"
        self.ws.mkdir()
        self.prompt = self.ws / "prompt.md"
        self.prompt.write_text("do the task")
        self.report = self.ws / "report.md"
        (self.ws / "agent-env.json").write_text(json.dumps({"REPORT": str(self.report)}))
        self.config_path = self.home / ".config/superpowers-multi-subagents/agents.json"
        self.config_path.parent.mkdir(parents=True)
        self.env = {
            key: value for key, value in os.environ.items() if not key.startswith("SUPERPOWERS")
        }
        self.env["HOME"] = str(self.home)

    def _config(self, body: str, policy: str = "no-commit", stall: int = 30) -> None:
        worker = self.home / "worker"
        worker.write_text(f'#!/usr/bin/env bash\nprintf "%s" "$1" > "{self.home}/seen-prompt"\n{body}\n')
        worker.chmod(0o755)
        self.config_path.write_text(json.dumps({
            "order": ["fake"],
            "host_fallback": {"host": "subagent"},
            "git_policy": policy,
            "limits": {"run_seconds": 60, "stall_seconds": stall, "error_attempts": 1,
                       "token_cooldown_seconds": 10},
            "host_session_env_prefixes": [],
            "agents": {
                "host": {"enabled": False},
                "fake": {
                    "enabled": True, "command": [str(worker), "{prompt}"], "models": "all",
                    "tiers": {"cheap": "m", "standard": "m", "capable": "m"},
                },
            },
        }))

    def _args(self, **overrides: str) -> list[str]:
        values = {
            "--host": "other", "--role": "implementer", "--task": "1", "--tier": "cheap",
            "--effort": "low", "--cwd": str(self.repo), "--workspace": str(self.ws),
            "--prompt-file": str(self.prompt), "--report-file": str(self.report),
        }
        values.update({f"--{key.replace('_', '-')}": value for key, value in overrides.items()})
        return ["run", *[part for pair in values.items() for part in pair]]

    def _router(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(ROUTER), *args], cwd=self.home, env=self.env, capture_output=True, text=True, timeout=60
        )

    def _ledger(self) -> str:
        path = self.ws / "progress.md"
        return path.read_text() if path.exists() else ""


class GuardWiringTest(CliCase):
    def test_worker_is_denied_in_the_cwd_repo(self) -> None:
        self._config('touch new.txt\ngit add new.txt\necho "add_rc=$?" > "$REPORT"\necho "Status: DONE" >> "$REPORT"')
        result = self._router(*self._args())
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("add_rc=126", self.report.read_text())
        status = subprocess.run(
            ["git", "status", "--short"], cwd=self.repo, capture_output=True, text=True, check=True
        ).stdout
        self.assertIn("?? new.txt", status)

    def test_worker_can_use_git_in_other_repositories(self) -> None:
        other = self.home / "other"
        other.mkdir()
        subprocess.run(["git", "init", "-q", str(other)], check=True)
        self._config(f'cd "{other}"\ntouch f\ngit add f\necho "add_rc=$?" > "$REPORT"\necho "Status: DONE" >> "$REPORT"')
        self.assertEqual(self._router(*self._args()).returncode, 0)
        self.assertIn("add_rc=0", self.report.read_text())

    def test_allow_policy_has_no_guard(self) -> None:
        self._config('touch f\ngit add f\necho "add_rc=$?" > "$REPORT"\necho "Status: DONE" >> "$REPORT"', policy="allow")
        self.assertEqual(self._router(*self._args()).returncode, 0)
        self.assertIn("add_rc=0", self.report.read_text())

    def test_commit_that_bypasses_the_guard_blocks_the_dispatch(self) -> None:
        self._config(
            f'touch f\n"{REAL_GIT}" add f\n"{REAL_GIT}" commit -qm sneaky\necho "Status: DONE" > "$REPORT"'
        )
        result = self._router(*self._args())
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("Status: BLOCKED", result.stdout)
        self.assertIn("git_policy_violation", result.stdout)
        self.assertIn("runner=fake", result.stdout)
        self.assertIn("result=git_policy_violation", self._ledger())

    def test_staging_that_bypasses_the_guard_blocks_the_dispatch(self) -> None:
        self._config(f'touch f\n"{REAL_GIT}" add f\necho "Status: DONE" > "$REPORT"')
        self.assertEqual(self._router(*self._args()).returncode, 1)
        self.assertIn("result=git_policy_violation", self._ledger())

    def test_git_status_and_edits_are_not_a_violation(self) -> None:
        self._config('touch f\ngit status >/dev/null\necho "Status: DONE" > "$REPORT"')
        self.assertEqual(self._router(*self._args()).returncode, 0)
        self.assertIn("result=ok", self._ledger())

    def test_prompt_reaches_the_worker_with_rule_and_paths(self) -> None:
        self._config('echo "Status: DONE" > "$REPORT"')
        self.assertEqual(self._router(*self._args()).returncode, 0)
        seen = (self.home / "seen-prompt").read_text()
        self.assertTrue(seen.startswith("Git rule: do not stage, commit"))
        self.assertIn(f"Report file: {self.report}", seen)
        self.assertIn(str(self.ws / "progress.md"), seen)


class ExhaustedOutputTest(CliCase):
    def test_exhausted_names_a_host_prompt_with_rule_and_note(self) -> None:
        self._config("exit 1")
        result = self._router(*self._args(host="host"))
        self.assertEqual(result.returncode, 75, result.stdout)
        self.assertIn("Status: EXHAUSTED", result.stdout)
        path = Path(result.stdout.split("host_prompt=")[1].split()[0])
        text = path.read_text()
        self.assertIn("Git rule: do not stage, commit", text)
        self.assertIn("partial edits", text)
        self.assertIn(f"Report file: {self.report}", text)


class SignalTest(CliCase):
    def _orphan_check(self, signum: int, expected_rc: int) -> None:
        pid_file = self.home / "worker.pid"
        self._config(f'echo $$ > "{pid_file}"\nexec sleep 30')
        process = subprocess.Popen(
            [str(ROUTER), *self._args()], cwd=self.home, env=self.env, stdout=subprocess.DEVNULL
        )
        deadline = time.monotonic() + 20
        while not (pid_file.exists() and pid_file.read_text().strip()):
            self.assertLess(time.monotonic(), deadline, "worker never started")
            time.sleep(0.05)
        worker_pid = int(pid_file.read_text())
        process.send_signal(signum)
        self.assertEqual(process.wait(timeout=20), expected_rc)
        with self.assertRaises(ProcessLookupError):
            os.kill(worker_pid, 0)

    def test_sigterm_takes_the_worker_down(self) -> None:
        self._orphan_check(signal.SIGTERM, 128 + signal.SIGTERM)

    def test_sighup_takes_the_worker_down(self) -> None:
        self._orphan_check(signal.SIGHUP, 128 + signal.SIGHUP)


    def test_sigint_takes_the_worker_down(self) -> None:
        self._orphan_check(signal.SIGINT, 128 + signal.SIGINT)

    def test_nohup_keeps_the_run_alive_through_sighup(self) -> None:
        started = self.home / "started"
        self._config(f'touch "{started}"\nsleep 2\necho "Status: DONE" > "$REPORT"')
        process = subprocess.Popen(
            [str(ROUTER), *self._args()], cwd=self.home, env=self.env, stdout=subprocess.DEVNULL,
            preexec_fn=lambda: signal.signal(signal.SIGHUP, signal.SIG_IGN),
        )
        deadline = time.monotonic() + 20
        while not started.exists():
            self.assertLess(time.monotonic(), deadline, "worker never started")
            time.sleep(0.05)
        process.send_signal(signal.SIGHUP)
        self.assertEqual(process.wait(timeout=30), 0)
        self.assertIn("result=ok", self._ledger())


class ErrorBoundaryTest(CliCase):
    def _assert_error(self, result: subprocess.CompletedProcess[str], needle: str) -> None:
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("Status: ERROR", result.stdout)
        self.assertIn(needle, result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_missing_cwd_is_an_error_not_exhaustion(self) -> None:
        self._config('echo "Status: DONE" > "$REPORT"')
        result = self._router(*self._args(cwd=str(self.home / "typo")))
        self._assert_error(result, "typo")
        self.assertEqual(self._ledger(), "")

    def test_missing_prompt_file(self) -> None:
        self._config('echo "Status: DONE" > "$REPORT"')
        self._assert_error(self._router(*self._args(prompt_file=str(self.ws / "none.md"))), "none.md")

    def test_missing_workspace(self) -> None:
        self._config('echo "Status: DONE" > "$REPORT"')
        missing = str(self.home / "no-ws")
        self._assert_error(self._router(*self._args(workspace=missing)), "no-ws")

    def test_report_file_in_missing_folder(self) -> None:
        self._config('echo "Status: DONE" > "$REPORT"')
        self._assert_error(self._router(*self._args(report_file=str(self.home / "nope/r.md"))), "nope")

    def test_malformed_config_names_its_path(self) -> None:
        self.config_path.write_text("{not json")
        self._assert_error(self._router("git-policy"), str(self.config_path))

    def test_invalid_config_names_its_path(self) -> None:
        self.config_path.write_text(json.dumps({"order": "x"}))
        self._assert_error(self._router("git-policy"), str(self.config_path))

    def test_invalid_regex_in_config_is_an_error(self) -> None:
        self._config("exit 0")
        data = json.loads(self.config_path.read_text())
        data["agents"]["fake"]["token_error_patterns"] = ["("]
        self.config_path.write_text(json.dumps(data))
        self._assert_error(self._router("git-policy"), "regex")

    def test_malformed_agent_env_names_its_path(self) -> None:
        self._config('echo "Status: DONE" > "$REPORT"')
        path = self.ws / "agent-env.json"
        path.write_text("{not json")
        self._assert_error(self._router(*self._args()), str(path))

    def test_corrupt_router_state_names_its_path(self) -> None:
        self._config('echo "Status: DONE" > "$REPORT"')
        path = self.ws / "router-state.json"
        path.write_text("{not json")
        self._assert_error(self._router(*self._args()), str(path))

    def test_bad_argument_is_an_error(self) -> None:
        self._config("exit 0")
        self._assert_error(self._router(*self._args(tier="huge")), "huge")

    def test_unknown_host_is_rejected(self) -> None:
        self._config('echo "Status: DONE" > "$REPORT"')
        self._assert_error(self._router(*self._args(host="Claude")), "Claude")
        self._assert_error(self._router("doctor", "--host", "typo"), "typo")

    def test_configured_agent_and_other_are_accepted_hosts(self) -> None:
        self._config('echo "Status: DONE" > "$REPORT"')
        self.assertEqual(self._router(*self._args(host="other")).returncode, 0)
        self.assertEqual(self._router(*self._args(host="fake")).returncode, 1)

    def test_upstream_commands_report_missing_superpowers(self) -> None:
        self._config("exit 0")
        self._assert_error(self._router("upstream-path"), "SUPERPOWERS_SKILLS_DIR")
        self._assert_error(self._router("upstream-check"), "SUPERPOWERS_SKILLS_DIR")


class UpstreamCheckTest(CliCase):
    def test_missing_watched_file_is_reported_as_drift(self) -> None:
        self._config("exit 0")
        skills = self.home / "skills"
        (skills / "subagent-driven-development").mkdir(parents=True)
        (skills / "subagent-driven-development" / "SKILL.md").write_text("x")
        self.env["SUPERPOWERS_SKILLS_DIR"] = str(skills)
        result = self._router("upstream-check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("upstream changed since last review: writing-plans/SKILL.md", result.stdout)

    def test_accept_refuses_an_incomplete_upstream(self) -> None:
        self._config("exit 0")
        skills = self.home / "skills"
        skills.mkdir()
        self.env["SUPERPOWERS_SKILLS_DIR"] = str(skills)
        result = self._router("upstream-check", "--accept")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("writing-plans/SKILL.md", result.stdout)
