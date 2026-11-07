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


class CommitGuardedGuardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp()
        self.other = tempfile.mkdtemp()
        for repo in (self.repo, self.other):
            subprocess.run(["git", "init", "-q", repo], check=True)
        self.grants = Path(tempfile.mkdtemp()) / "git-grants.txt"
        self.env = {
            **os.environ,
            "PATH": f"{GUARD}:{os.environ['PATH']}",
            "AGENT_ROUTER_GUARD_ROOT": toplevel(self.repo),
            "AGENT_ROUTER_GIT_POLICY": "commit-guarded",
            "AGENT_ROUTER_GIT_GRANTS_FILE": str(self.grants),
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
        }
        (Path(self.repo) / "a.txt").write_text("a\n")

    def _git(self, *args: str, cwd: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=cwd or self.repo, env=self.env, capture_output=True, text=True
        )

    def _commit_one(self) -> None:
        self.assertEqual(self._git("add", "a.txt").returncode, 0)
        self.assertEqual(self._git("commit", "-q", "-m", "first").returncode, 0)

    def test_add_explicit_path_and_commit_pass(self) -> None:
        self._commit_one()
        self.assertEqual(self._git("log", "--oneline").stdout.count("first"), 1)

    def test_blanket_add_is_denied(self) -> None:
        for form in ((".",), ("-A",), ("--all",), ("-u",), ("--update",), ("./",), ("-f", "a.txt"),
                     ("--force", "a.txt"), ("-p",), ()):
            result = self._git("add", *form)
            self.assertEqual(result.returncode, 126, form)
            self.assertIn("commit-guarded", result.stderr)

    def test_dangerous_commit_flags_are_denied(self) -> None:
        self._commit_one()
        for form in (("--amend", "-m", "x"), ("--no-verify", "-m", "x"), ("-n", "-m", "x"),
                     ("-a", "-m", "x"), ("--all", "-m", "x"), ("-am", "x"), ("-p",)):
            self.assertEqual(self._git("commit", *form).returncode, 126, form)

    def test_message_text_that_looks_like_a_flag_is_not_a_flag(self) -> None:
        (Path(self.repo) / "a.txt").write_text("changed\n")
        self._git("add", "a.txt")
        self.assertEqual(self._git("commit", "-q", "-m", "-a --amend").returncode, 0)

    def test_hooks_path_override_is_denied(self) -> None:
        self._git("add", "a.txt")
        result = self._git("-c", "core.hooksPath=/dev/null", "commit", "-m", "x")
        self.assertEqual(result.returncode, 126)

    def test_other_history_commands_are_denied(self) -> None:
        for form in (("push",), ("reset", "--hard"), ("rebase", "x"), ("checkout", "x"),
                     ("switch", "x"), ("restore", "a.txt"), ("clean", "-fd"), ("stash",),
                     ("merge", "x"), ("cherry-pick", "x"), ("revert", "x"), ("pull",),
                     ("rm", "a.txt"), ("mv", "a", "b"), ("branch", "-D", "x"), ("tag", "-d", "x"),
                     ("am",)):
            self.assertEqual(self._git(*form).returncode, 126, form)

    def test_read_only_commands_pass(self) -> None:
        for form in (("status", "--short"), ("diff",), ("branch", "--list"), ("stash", "list")):
            self.assertEqual(self._git(*form).returncode, 0, form)

    def test_exact_grant_allows_one_command(self) -> None:
        self.grants.write_text("reset --soft HEAD\n")
        self._commit_one()
        self.assertEqual(self._git("reset", "--soft", "HEAD").returncode, 0)
        self.assertEqual(self._git("reset", "--hard", "HEAD").returncode, 126)

    def test_grant_ignores_global_flags_but_not_arguments(self) -> None:
        self.grants.write_text("reset --soft HEAD\n")
        self._commit_one()
        self.assertEqual(self._git("-C", self.repo, "reset", "--soft", "HEAD").returncode, 0)
        self.assertEqual(self._git("reset", "--soft", "HEAD~0").returncode, 126)

    def test_grant_is_exact_not_a_prefix(self) -> None:
        self.grants.write_text("push\n")
        self.assertEqual(self._git("push", "--force").returncode, 126)

    def test_other_repositories_are_not_guarded(self) -> None:
        self.assertNotEqual(self._git("reset", "-q", cwd=self.other).returncode, 126)

    def test_no_commit_policy_ignores_grants(self) -> None:
        self.env["AGENT_ROUTER_GIT_POLICY"] = "no-commit"
        self.grants.write_text("add a.txt\n")
        self.assertEqual(self._git("add", "a.txt").returncode, 126)

    def test_system_bash_runs_commit_guarded(self) -> None:
        result = subprocess.run(
            ["/bin/bash", str(GUARD / "git"), "add", "."], cwd=self.repo, env=self.env,
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 126, result.stderr)
