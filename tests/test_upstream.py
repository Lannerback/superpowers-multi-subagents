import tempfile
import unittest
from pathlib import Path

from agent_router.upstream import find_drift, resolve_skills_dir, write_lock


def plant(home: Path, relative: str) -> Path:
    skills = home / relative
    for name in ("writing-plans", "subagent-driven-development"):
        (skills / name).mkdir(parents=True)
        (skills / name / "SKILL.md").write_text(name)
    return skills


class ResolveTest(unittest.TestCase):
    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp())

    def test_highest_version_across_hosts_wins(self) -> None:
        plant(self.home, ".claude/plugins/cache/m/superpowers/7.0.2/skills")
        expected = plant(self.home, ".codex/plugins/cache/m/superpowers/7.0.10/skills")
        self.assertEqual(resolve_skills_dir(self.home, {}), expected)

    def test_env_override_wins(self) -> None:
        plant(self.home, ".claude/plugins/cache/m/superpowers/7.0.2/skills")
        override = plant(self.home, "custom/skills")
        env = {"SUPERPOWERS_SKILLS_DIR": str(override)}
        self.assertEqual(resolve_skills_dir(self.home, env), override)

    def test_missing_raises_lookup_error(self) -> None:
        with self.assertRaises(LookupError):
            resolve_skills_dir(self.home, {})


class DriftTest(unittest.TestCase):
    def test_reports_changed_upstream_file(self) -> None:
        home = Path(tempfile.mkdtemp())
        skills = plant(home, "s")
        lock = home / "lock.json"
        write_lock(skills, lock)
        self.assertEqual(find_drift(skills, lock), [])
        (skills / "writing-plans/SKILL.md").write_text("changed")
        self.assertEqual(find_drift(skills, lock), ["writing-plans/SKILL.md"])
