import sys
import tempfile
import unittest
from collections.abc import Callable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from superpowers_installers.base import HostInstaller, RunResult  # noqa: E402
from superpowers_installers.registry import INSTALLERS  # noqa: E402
from superpowers_installers.runner import SubprocessRunner  # noqa: E402
from superpowers_installers.service import install_missing  # noqa: E402

SDD = "subagent-driven-development/SKILL.md"


def plant(home: Path, relative: str) -> None:
    marker = home / relative / SDD
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("x")


class FakeRunner:
    """Records commands. `on_run` may plant files or raise; otherwise returns `result`."""

    def __init__(self, result: RunResult = RunResult(0, "", ""),
                 on_run: Callable[[Sequence[str]], None] | None = None) -> None:
        self.result = result
        self.on_run = on_run
        self.calls: list[tuple[str, ...]] = []

    def run(self, argv: Sequence[str], timeout: float) -> RunResult:
        self.calls.append(tuple(argv))
        if self.on_run:
            self.on_run(argv)
        return self.result


class InstallMissingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp())
        self.log: list[str] = []

    def _install(self, hosts: list[str], runner: FakeRunner) -> list[tuple[str, str]]:
        results = install_missing(hosts, self.home, INSTALLERS, runner, self.log.append)
        return [(r.host, r.outcome) for r in results]

    def _plant_on_install(self, argv: Sequence[str]) -> None:
        if argv[:3] == ("claude", "plugin", "install"):
            plant(self.home, ".claude/plugins/cache/m/superpowers/7.0.2/skills")

    def test_already_installed_runs_nothing(self) -> None:
        plant(self.home, ".claude/plugins/cache/m/superpowers/7.0.2/skills")
        runner = FakeRunner()
        self.assertEqual(self._install(["claude"], runner), [("claude", "present")])
        self.assertEqual(runner.calls, [])

    def test_installed_in_another_host_does_not_count(self) -> None:
        plant(self.home, ".codex/plugins/cache/m/superpowers/7.0.2/skills")
        runner = FakeRunner(on_run=self._plant_on_install)
        self.assertEqual(self._install(["claude"], runner), [("claude", "installed")])

    def test_runs_the_two_exact_commands_in_order_without_accept_flags(self) -> None:
        runner = FakeRunner(on_run=self._plant_on_install)
        self._install(["claude"], runner)
        self.assertEqual(runner.calls, [
            ("claude", "plugin", "marketplace", "add", "obra/superpowers-marketplace"),
            ("claude", "plugin", "install", "superpowers@superpowers-marketplace"),
        ])
        for call in runner.calls:
            self.assertNotIn("-y", call)
            self.assertFalse(any(part.startswith("--accept") for part in call))

    def test_codex_commands(self) -> None:
        runner = FakeRunner()
        self._install(["codex"], runner)
        self.assertEqual(runner.calls, [
            ("codex", "plugin", "marketplace", "add", "obra/superpowers"),
            ("codex", "plugin", "add", "superpowers@superpowers-dev"),
        ])

    def test_exact_command_is_logged_before_it_runs(self) -> None:
        self._install(["claude"], FakeRunner(on_run=self._plant_on_install))
        self.assertIn("host=claude run: claude plugin marketplace add obra/superpowers-marketplace", self.log)

    def test_first_command_failing_stops_the_second(self) -> None:
        runner = FakeRunner(RunResult(1, "", "boom\nnetwork down"))
        results = install_missing(["claude"], self.home, INSTALLERS, runner, self.log.append)
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(results[0].outcome, "failed")
        self.assertIn("exit 1", results[0].detail)
        self.assertIn("network down", results[0].detail)
        self.assertTrue(results[0].failed)

    def test_missing_cli_and_timeout_are_failures(self) -> None:
        for error in (LookupError("claude not found on PATH"), TimeoutError("timed out after 300s")):
            def raise_it(_: Sequence[str], error: Exception = error) -> None:
                raise error
            results = install_missing(["claude"], self.home, INSTALLERS, FakeRunner(on_run=raise_it), self.log.append)
            self.assertEqual(results[0].outcome, "failed")
            self.assertIn(str(error), results[0].detail)

    def test_success_without_a_detectable_copy_is_not_detected(self) -> None:
        results = install_missing(["claude"], self.home, INSTALLERS, FakeRunner(), self.log.append)
        self.assertEqual(results[0].outcome, "not-detected")
        self.assertTrue(results[0].failed)

    def test_manual_hosts_run_nothing_and_do_not_fail(self) -> None:
        runner = FakeRunner()
        results = install_missing(["opencode", "cursor"], self.home, INSTALLERS, runner, self.log.append)
        self.assertEqual([r.outcome for r in results], ["manual", "manual"])
        self.assertFalse(any(r.failed for r in results))
        self.assertEqual(runner.calls, [])

    def test_duplicate_hosts_run_once(self) -> None:
        runner = FakeRunner(on_run=self._plant_on_install)
        self.assertEqual(self._install(["claude", "claude"], runner), [("claude", "installed")])

    def test_each_result_is_logged_as_one_structured_line(self) -> None:
        self._install(["opencode"], FakeRunner())
        self.assertIn("host=opencode result=manual detail=no scriptable install", self.log)


class RegistryTest(unittest.TestCase):
    def test_every_host_install_py_knows_has_an_installer(self) -> None:
        from install import HOST_TARGETS
        self.assertEqual(set(INSTALLERS), set(HOST_TARGETS))

    def test_only_claude_and_codex_are_scriptable(self) -> None:
        self.assertEqual({h for h, i in INSTALLERS.items() if i.commands}, {"claude", "codex"})

    def test_installers_are_immutable(self) -> None:
        with self.assertRaises(AttributeError):
            INSTALLERS["claude"].host = "x"  # type: ignore[misc]
        self.assertIsInstance(INSTALLERS["claude"], HostInstaller)


class SubprocessRunnerTest(unittest.TestCase):
    def test_runs_a_command_and_captures_output(self) -> None:
        done = SubprocessRunner().run([sys.executable, "-c", "print('hi')"], 30)
        self.assertEqual((done.returncode, done.stdout.strip()), (0, "hi"))

    def test_nonzero_exit_is_returned_not_raised(self) -> None:
        self.assertEqual(SubprocessRunner().run([sys.executable, "-c", "raise SystemExit(3)"], 30).returncode, 3)

    def test_missing_program_raises_lookup_error(self) -> None:
        with self.assertRaises(LookupError):
            SubprocessRunner().run(["definitely-not-a-real-program-xyz"], 5)

    def test_timeout_raises_timeout_error(self) -> None:
        with self.assertRaises(TimeoutError):
            SubprocessRunner().run([sys.executable, "-c", "import time; time.sleep(5)"], 0.3)

    def test_stdin_is_closed(self) -> None:
        done = SubprocessRunner().run([sys.executable, "-c", "import sys; print(repr(sys.stdin.read()))"], 30)
        self.assertEqual(done.stdout.strip(), "''")


if __name__ == "__main__":
    unittest.main()
