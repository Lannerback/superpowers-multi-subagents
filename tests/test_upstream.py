import json
import tempfile
import unittest
from pathlib import Path

from agent_router.upstream import WATCHED, find_drift, host_skills_dirs, resolve_skills_dir, write_lock

UPSTREAM = Path(__file__).resolve().parents[1] / "skills/subagent-driven-development-multi"


def plant(home: Path, relative: str) -> Path:
    skills = home / relative
    for name in WATCHED:
        (skills / name).parent.mkdir(parents=True, exist_ok=True)
        (skills / name).write_text(name)
    return skills


class HostSkillsDirsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp())

    def test_each_host_sees_only_its_own_cache(self) -> None:
        claude = plant(self.home, ".claude/plugins/cache/m/superpowers/7.0.2/skills")
        codex = plant(self.home, ".codex/plugins/cache/m/superpowers/7.0.2/skills")
        self.assertEqual(host_skills_dirs("claude", self.home), [claude])
        self.assertEqual(host_skills_dirs("codex", self.home), [codex])
        self.assertEqual(host_skills_dirs("opencode", self.home), [])

    def test_newest_version_comes_first(self) -> None:
        plant(self.home, ".claude/plugins/cache/m/superpowers/7.0.2/skills")
        newest = plant(self.home, ".claude/plugins/cache/m/superpowers/7.0.10/skills")
        self.assertEqual(host_skills_dirs("claude", self.home)[0], newest)

    def test_unknown_host_has_no_dirs(self) -> None:
        self.assertEqual(host_skills_dirs("cursor", self.home), [])


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


    def test_opencode_cache_layouts_are_found(self) -> None:
        for relative in (
            ".cache/opencode/npm/git-superpowers-abc/123/node_modules/superpowers/skills",
            ".cache/opencode/packages/superpowers@git+https:/github.com/obra/superpowers.git#v7/"
            "node_modules/superpowers/skills",
        ):
            home = Path(tempfile.mkdtemp())
            expected = plant(home, relative)
            self.assertEqual(resolve_skills_dir(home, {}), expected)

    def test_opencode_version_comes_from_package_json(self) -> None:
        old = plant(self.home, ".claude/plugins/cache/m/superpowers/6.0.0/skills")
        new = plant(self.home, ".cache/opencode/npm/x/1/node_modules/superpowers/skills")
        (new.parent / "package.json").write_text('{"version": "7.0.2"}')
        self.assertEqual(resolve_skills_dir(self.home, {}), new)
        (new.parent / "package.json").write_text('{"version": "5.0.0"}')
        self.assertEqual(resolve_skills_dir(self.home, {}), old)

    def test_unreadable_package_json_sorts_last(self) -> None:
        old = plant(self.home, ".claude/plugins/cache/m/superpowers/6.0.0/skills")
        new = plant(self.home, ".cache/opencode/npm/x/1/node_modules/superpowers/skills")
        (new.parent / "package.json").write_text("{broken")
        self.assertEqual(resolve_skills_dir(self.home, {}), old)


class DriftTest(unittest.TestCase):
    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp())
        self.skills = plant(self.home, "s")
        self.lock = self.home / "lock.json"
        write_lock(self.skills, self.lock)

    def test_reports_changed_upstream_file(self) -> None:
        self.assertEqual(find_drift(self.skills, self.lock), [])
        (self.skills / "writing-plans/SKILL.md").write_text("changed")
        self.assertEqual(find_drift(self.skills, self.lock), ["writing-plans/SKILL.md"])

    def test_watches_every_file_the_wrapper_depends_on(self) -> None:
        sdd = "subagent-driven-development"
        for name in (
            "writing-plans/SKILL.md", f"{sdd}/SKILL.md", f"{sdd}/implementer-prompt.md",
            f"{sdd}/task-reviewer-prompt.md", f"{sdd}/re-review-prompt.md",
            f"{sdd}/references/resuming.md", f"{sdd}/references/fix-loop.md",
            f"{sdd}/references/final-review.md", f"{sdd}/references/handling-reports.md",
            f"{sdd}/scripts/sdd-workspace", f"{sdd}/scripts/task-brief",
            "requesting-code-review/code-reviewer.md",
        ):
            (self.skills / name).write_text("changed")
            self.assertEqual(find_drift(self.skills, self.lock), [name], name)
            (self.skills / name).write_text(name)

    def test_missing_watched_file_is_drift(self) -> None:
        (self.skills / "subagent-driven-development/references/resuming.md").unlink()
        self.assertEqual(
            find_drift(self.skills, self.lock), ["subagent-driven-development/references/resuming.md"]
        )

    def test_missing_lock_reports_every_file(self) -> None:
        self.assertEqual(find_drift(self.skills, self.home / "none.json"), list(WATCHED))

    def test_malformed_lock_names_its_path(self) -> None:
        self.lock.write_text("{broken")
        with self.assertRaisesRegex(ValueError, str(self.lock)):
            find_drift(self.skills, self.lock)

    def test_write_lock_refuses_missing_files(self) -> None:
        (self.skills / "writing-plans/SKILL.md").unlink()
        with self.assertRaisesRegex(LookupError, "writing-plans/SKILL.md"):
            write_lock(self.skills, self.lock)

    def test_shipped_lock_covers_the_watch_list(self) -> None:
        shipped = json.loads((UPSTREAM / "config/upstream-lock.json").read_text())
        self.assertEqual(sorted(shipped), sorted(WATCHED))
