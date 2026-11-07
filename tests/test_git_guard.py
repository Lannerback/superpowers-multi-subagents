import os
import subprocess
import tempfile
import unittest
from pathlib import Path

GUARD = (
    Path(__file__).resolve().parents[1]
    / "skills/subagent-driven-development-multi/scripts/git-guard"
)
MUTATIONS = (
    "add", "am", "branch", "checkout", "cherry-pick", "clean", "commit", "merge", "mv", "pull",
    "push", "rebase", "reset", "restore", "revert", "rm", "stash", "switch", "tag",
)


def toplevel(repo: str) -> str:
    return subprocess.run(
        ["git", "-C", repo, "rev-parse", "--show-toplevel"], check=True, capture_output=True, text=True
    ).stdout.strip()


class GitGuardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp()
        self.other = tempfile.mkdtemp()
        for repo in (self.repo, self.other):
            subprocess.run(["git", "init", "-q", repo], check=True)
        self.env = {
            **os.environ,
            "PATH": f"{GUARD}:{os.environ['PATH']}",
            "AGENT_ROUTER_GUARD_ROOT": toplevel(self.repo),
        }

    def _git(self, *args: str, cwd: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=cwd or self.repo, env=self.env, capture_output=True, text=True
        )

    def test_read_commands_pass(self) -> None:
        self.assertEqual(self._git("status", "--short").returncode, 0)
        self.assertEqual(self._git("-C", self.repo, "diff").returncode, 0)

    def test_mutations_are_denied_in_the_protected_repo(self) -> None:
        for sub in MUTATIONS:
            result = self._git(sub, "x")
            self.assertEqual(result.returncode, 126, sub)
            self.assertIn("denied", result.stderr)

    def test_mutations_are_denied_from_a_subdirectory(self) -> None:
        subdir = Path(self.repo) / "deep"
        subdir.mkdir()
        self.assertEqual(self._git("add", ".", cwd=str(subdir)).returncode, 126)

    def test_global_flags_do_not_bypass_the_guard(self) -> None:
        self.assertEqual(self._git("-C", self.repo, "commit", "-m", "x").returncode, 126)
        self.assertEqual(self._git("-c", "a.b=c", "push").returncode, 126)

    def test_other_repositories_are_not_guarded(self) -> None:
        (Path(self.other) / "file.txt").write_text("x\n")
        self.assertEqual(self._git("add", "file.txt", cwd=self.other).returncode, 0)
        self.assertEqual(self._git("-C", self.other, "rm", "--cached", "file.txt").returncode, 0)

    def test_dash_c_into_another_repository_is_not_guarded(self) -> None:
        (Path(self.other) / "file.txt").write_text("x\n")
        self.assertEqual(self._git("-C", self.other, "add", "file.txt").returncode, 0)

    def test_dash_c_into_the_protected_repository_is_guarded(self) -> None:
        self.assertEqual(self._git("-C", self.repo, "add", ".", cwd=self.other).returncode, 126)

    def test_outside_any_repository_git_answers_for_itself(self) -> None:
        result = self._git("add", ".", cwd=tempfile.mkdtemp())
        self.assertNotEqual(result.returncode, 126)

    def test_read_only_forms_pass_in_the_protected_repo(self) -> None:
        for form in (("branch",), ("branch", "--show-current"), ("branch", "--list"),
                     ("tag",), ("tag", "-l"), ("tag", "--list"), ("stash", "list")):
            result = self._git(*form)
            self.assertEqual(result.returncode, 0, f"{form}: {result.stderr}")

    def test_mutating_forms_of_read_only_commands_stay_denied(self) -> None:
        for form in (("branch", "-D", "x"), ("branch", "new"), ("tag", "-d", "x"), ("tag", "new"),
                     ("stash", "pop"), ("stash", "drop"), ("stash", "push")):
            self.assertEqual(self._git(*form).returncode, 126, form)

    def test_without_a_root_the_guard_fails_closed(self) -> None:
        del self.env["AGENT_ROUTER_GUARD_ROOT"]
        self.assertEqual(self._git("add", ".", cwd=self.other).returncode, 126)
        self.assertEqual(self._git("branch", "--show-current").returncode, 0)

    def test_system_bash_runs_the_guard(self) -> None:
        # macOS ships bash 3.2, where empty array slices can trip `set -u`.
        result = subprocess.run(
            ["/bin/bash", str(GUARD / "git"), "add", "."], cwd=self.repo, env=self.env,
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 126, result.stderr)
