import re
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1] / "skills"


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
