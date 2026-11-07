import os
import subprocess
import tempfile
import unittest
from pathlib import Path

GUARD = (
    Path(__file__).resolve().parents[1]
    / "skills/subagent-driven-development-multi/scripts/git-guard"
)


class GitGuardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp()
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.env = {**os.environ, "PATH": f"{GUARD}:{os.environ['PATH']}"}

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=self.repo, env=self.env, capture_output=True, text=True
        )

    def test_read_commands_pass(self) -> None:
        self.assertEqual(self._git("status", "--short").returncode, 0)
        self.assertEqual(self._git("-C", self.repo, "diff").returncode, 0)

    def test_mutations_are_denied(self) -> None:
        for sub in ("add", "commit", "push", "reset", "checkout", "switch", "restore",
                    "stash", "clean", "rebase", "merge", "cherry-pick", "revert", "branch", "tag"):
            result = self._git(sub, "x")
            self.assertEqual(result.returncode, 126, sub)
            self.assertIn("denied", result.stderr)

    def test_global_flags_do_not_bypass_the_guard(self) -> None:
        self.assertEqual(self._git("-C", self.repo, "commit", "-m", "x").returncode, 126)
        self.assertEqual(self._git("-c", "a.b=c", "push").returncode, 126)
