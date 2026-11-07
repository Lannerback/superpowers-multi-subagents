import re
import unittest
from pathlib import Path

from agent_router.cli import EXIT_ERROR
from agent_router.router import EXIT_BLOCKED, EXIT_EXHAUSTED, EXIT_OK

SKILLS = Path(__file__).resolve().parents[1] / "skills"
EXECUTOR = SKILLS / "subagent-driven-development-multi"


class SkillFilesTest(unittest.TestCase):
    def test_frontmatter_name_matches_folder(self) -> None:
        for name in ("writing-plans-multi-subagents", "subagent-driven-development-multi"):
            text = (SKILLS / name / "SKILL.md").read_text()
            match = re.match(r"---\nname: (\S+)\ndescription: Use when .+\n---\n", text)
            self.assertIsNotNone(match, name)
            self.assertEqual(match.group(1), name)

    def test_no_machine_specific_paths_in_tracked_skills(self) -> None:
        for path in SKILLS.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                self.assertNotIn("/Users/", path.read_text(errors="ignore"), str(path))

    def test_executor_names_each_router_exit(self) -> None:
        text = (SKILLS / "subagent-driven-development-multi/SKILL.md").read_text()
        for needle in ("EXHAUSTED", "75", "agent-contract.md", "worktree-review-package", "Agent-run"):
            self.assertIn(needle, text)

    def test_executor_has_a_row_for_each_exit_code(self) -> None:
        text = (EXECUTOR / "SKILL.md").read_text()
        for code in (EXIT_OK, EXIT_BLOCKED, EXIT_EXHAUSTED, EXIT_ERROR):
            self.assertIn(f"\n| {code} | `Status:", text)
        self.assertIn("\n| Other |", text)

    def test_error_exit_forbids_falling_back(self) -> None:
        row = next(
            line for line in (EXECUTOR / "SKILL.md").read_text().splitlines()
            if line.startswith(f"| {EXIT_ERROR} |")
        )
        self.assertIn("Status: ERROR", row)
        self.assertIn("Do not fall back", row)

    def test_exhausted_row_carries_host_prompt_and_blocked_row_names_the_violation(self) -> None:
        text = (EXECUTOR / "SKILL.md").read_text()
        self.assertIn("host_prompt=", text)
        self.assertIn("partial-edits note", text)
        self.assertIn("git_policy_violation", text)

    def test_snapshots_live_in_the_ledger(self) -> None:
        text = (EXECUTOR / "SKILL.md").read_text()
        self.assertIn("Snapshot: task=<N> phase=<start|fix-R> tree=<id>", text)
        self.assertIn("snapshots <a7>..<b7>", text)
        self.assertIn("Do not delete the workspace until your human partner has decided", text)

    def test_roles_and_reports(self) -> None:
        text = (EXECUTOR / "SKILL.md").read_text()
        self.assertIn("`re-reviewer-<R>`", text)
        self.assertIn("--task final", text)
        self.assertIn("always read every reviewer", text)
        self.assertIn("at least `standard`", text)
        self.assertIn("task-<N>-implementer-report.md", text)

    def test_script_paths_are_absolute(self) -> None:
        text = (EXECUTOR / "SKILL.md").read_text()
        self.assertNotIn("(scripts/", text)
        self.assertNotIn("`scripts/worktree", text)
        self.assertIn('"$SKILL_DIR/scripts/worktree-snapshot"', text)
        self.assertIn('"$SKILL_DIR/scripts/worktree-review-package"', text)

    def test_contract_maps_verdicts_and_names_the_report_file(self) -> None:
        text = (EXECUTOR / "references/agent-contract.md").read_text()
        self.assertNotIn("<workspace>", text)
        self.assertIn("`Report file:` named at the end", text)
        reviewers = next(line for line in text.splitlines() if "- Reviewers:" in line)
        self.assertIn("Status: NEEDS_CONTEXT", reviewers)
        for needle in ("Task review:", "Re-review:", "Final review:", "ADDRESSED", "Ready to merge"):
            self.assertIn(needle, text)
