import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from install import HOST_TARGETS, find_superpowers, install, resolve_hosts, uninstall  # noqa: E402


class InstallTest(unittest.TestCase):
    def setUp(self) -> None:
        base = Path(tempfile.mkdtemp())
        self.skills = base / "skills"
        (self.skills / "one").mkdir(parents=True)
        (self.skills / "one/SKILL.md").write_text("x")
        self.target = base / "target"

    def test_creates_symlinks_and_is_idempotent(self) -> None:
        install(self.skills, self.target)
        install(self.skills, self.target)
        self.assertEqual((self.target / "one").resolve(), (self.skills / "one").resolve())

    def test_refuses_to_replace_a_real_directory(self) -> None:
        (self.target / "one").mkdir(parents=True)
        with self.assertRaisesRegex(FileExistsError, "one"):
            install(self.skills, self.target)

    def test_refuses_a_symlink_pointing_elsewhere(self) -> None:
        self.target.mkdir()
        (self.target / "one").symlink_to(self.target)
        with self.assertRaises(FileExistsError):
            install(self.skills, self.target)

    def test_uninstall_removes_only_own_links(self) -> None:
        install(self.skills, self.target)
        (self.target / "other").mkdir()
        uninstall(self.skills, self.target)
        self.assertFalse((self.target / "one").exists())
        self.assertTrue((self.target / "other").exists())

    def test_cursor_shares_the_codex_folder(self) -> None:
        self.assertEqual(HOST_TARGETS["cursor"], HOST_TARGETS["codex"])

    def test_ignores_folders_without_skill_file(self) -> None:
        (self.skills / "notes").mkdir()
        install(self.skills, self.target)
        self.assertFalse((self.target / "notes").exists())


class ResolveHostsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp())
        (self.home / ".claude").mkdir()
        (self.home / ".config/opencode").mkdir(parents=True)

    def test_named_host_without_config_folder_is_skipped(self) -> None:
        selected, skipped = resolve_hosts(["claude", "codex"], self.home, force=False)
        self.assertEqual(selected, ["claude"])
        self.assertEqual(skipped, ["codex"])

    def test_auto_picks_only_hosts_with_a_config_folder(self) -> None:
        selected, skipped = resolve_hosts(["auto"], self.home, force=False)
        self.assertEqual(selected, ["claude", "opencode"])
        self.assertEqual(skipped, [])

    def test_force_keeps_a_host_without_config_folder(self) -> None:
        selected, skipped = resolve_hosts(["codex"], self.home, force=True)
        self.assertEqual((selected, skipped), (["codex"], []))

    def test_force_does_not_widen_auto(self) -> None:
        selected, _ = resolve_hosts(["auto"], self.home, force=True)
        self.assertEqual(selected, ["claude", "opencode"])


class SuperpowersCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp())
        self.target = self.home / "skills-target"

    def _run(self, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
        base = {k: v for k, v in os.environ.items() if k != "SUPERPOWERS_SKILLS_DIR"}
        return subprocess.run(
            [sys.executable, str(ROOT / "install.py"), "--target", str(self.target), *args],
            capture_output=True, text=True, env={**base, "HOME": str(self.home), **env},
        )

    def test_not_found_without_superpowers(self) -> None:
        self.assertIsNone(find_superpowers(self.home, {}))

    def test_found_through_the_environment_override(self) -> None:
        self.assertEqual(find_superpowers(self.home, {"SUPERPOWERS_SKILLS_DIR": "/x"}), Path("/x"))

    def test_install_stops_with_instructions_when_missing(self) -> None:
        done = self._run()
        self.assertEqual(done.returncode, 2)
        self.assertIn("obra/superpowers", done.stderr)
        self.assertFalse(self.target.exists())

    def test_install_proceeds_when_superpowers_is_found(self) -> None:
        done = self._run(SUPERPOWERS_SKILLS_DIR=str(self.home))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue((self.target / "writing-plans-multi-subagents").is_symlink())

    def test_skip_flag_bypasses_the_check(self) -> None:
        self.assertEqual(self._run("--skip-superpowers-check").returncode, 0)

    def test_uninstall_needs_no_superpowers(self) -> None:
        self._run("--skip-superpowers-check")
        self.assertEqual(self._run("--uninstall").returncode, 0)
        self.assertFalse((self.target / "writing-plans-multi-subagents").exists())


FAKE_CLI = """#!/bin/sh
echo "$0 $*" >> "$HOME/calls.log"
[ "$FAKE_MODE" = fail ] && { echo "network down" >&2; exit 1; }
if [ "$2" = install ] || [ "$2" = add ] && [ "$3" != marketplace ] && [ "$FAKE_MODE" != silent ]; then
  mkdir -p "$HOME/$FAKE_CACHE/m/superpowers/7.0.2/skills/subagent-driven-development"
  : > "$HOME/$FAKE_CACHE/m/superpowers/7.0.2/skills/subagent-driven-development/SKILL.md"
fi
exit 0
"""


class InstallSuperpowersFlagTest(unittest.TestCase):
    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp())
        self.bin = Path(tempfile.mkdtemp())
        self.target = self.home / "skills-target"
        for name in ("claude", "codex"):
            script = self.bin / name
            script.write_text(FAKE_CLI)
            script.chmod(0o755)
        (self.home / ".claude").mkdir()

    def _run(self, *args: str, mode: str = "ok", **env: str) -> subprocess.CompletedProcess[str]:
        base = {k: v for k, v in os.environ.items() if k != "SUPERPOWERS_SKILLS_DIR"}
        environ = {
            **base, "HOME": str(self.home), "PATH": f"{self.bin}:{base['PATH']}",
            "FAKE_MODE": mode, "FAKE_CACHE": ".claude/plugins/cache", **env,
        }
        return subprocess.run(
            [sys.executable, str(ROOT / "install.py"), "--host", "claude", "--target", str(self.target), *args],
            capture_output=True, text=True, env=environ,
        )

    def _calls(self) -> str:
        log = self.home / "calls.log"
        return log.read_text() if log.exists() else ""

    def _linked(self) -> bool:
        return (self.target / "writing-plans-multi-subagents").is_symlink()

    def test_without_the_flag_nothing_runs_and_nothing_is_linked(self) -> None:
        done = self._run()
        self.assertEqual(done.returncode, 2)
        self.assertEqual(self._calls(), "")
        self.assertFalse(self._linked())
        self.assertIn("--install-superpowers", done.stderr)

    def test_flag_installs_then_links(self) -> None:
        done = self._run("--install-superpowers")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(self._linked())
        self.assertIn("host=claude run: claude plugin marketplace add obra/superpowers-marketplace", done.stdout)
        self.assertIn("host=claude result=installed", done.stdout)
        self.assertNotIn(" -y", self._calls())

    def test_second_run_is_a_noop(self) -> None:
        self._run("--install-superpowers")
        (self.home / "calls.log").unlink()
        done = self._run("--install-superpowers")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self._calls(), "")
        self.assertIn("host=claude result=present", done.stdout)

    def test_success_exit_but_no_copy_found_stops_without_linking(self) -> None:
        done = self._run("--install-superpowers", mode="silent")
        self.assertEqual(done.returncode, 2)
        self.assertIn("result=not-detected", done.stdout)
        self.assertFalse(self._linked())

    def test_failing_command_stops_without_linking(self) -> None:
        done = self._run("--install-superpowers", mode="fail")
        self.assertEqual(done.returncode, 2)
        self.assertIn("result=failed", done.stdout)
        self.assertIn("network down", done.stdout)
        self.assertFalse(self._linked())

    def test_manual_host_prints_help_and_exits_2(self) -> None:
        done = subprocess.run(
            [sys.executable, str(ROOT / "install.py"), "--host", "opencode", "--force-host",
             "--install-superpowers", "--target", str(self.target)],
            capture_output=True, text=True,
            env={**os.environ, "HOME": str(self.home), "PATH": f"{self.bin}:{os.environ['PATH']}",
                 "SUPERPOWERS_SKILLS_DIR": ""},
        )
        self.assertEqual(done.returncode, 2)
        self.assertIn("host=opencode result=manual", done.stdout)
        self.assertIn("opencode.json", done.stderr)
        self.assertEqual(self._calls(), "")

    def test_flag_conflicts_with_skip_check(self) -> None:
        done = self._run("--install-superpowers", "--skip-superpowers-check")
        self.assertEqual(done.returncode, 2)
        self.assertIn("not allowed with", done.stderr)

    def test_uninstall_ignores_the_flag_and_touches_no_superpowers(self) -> None:
        self._run("--install-superpowers")
        cache = self.home / ".claude/plugins/cache"
        (self.home / "calls.log").unlink()
        done = self._run("--install-superpowers", "--uninstall")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("ignored with --uninstall", done.stdout)
        self.assertFalse(self._linked())
        self.assertTrue(cache.exists())
        self.assertEqual(self._calls(), "")
