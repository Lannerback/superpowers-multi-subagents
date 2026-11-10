import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_FILE = ROOT / ".opencode/plugins/superpowers-multi-subagents.js"
OWNER = "Adriano D'Aguanno"
OUR_SKILLS = {"writing-plans-multi-subagents", "subagent-driven-development-multi"}


def load(relative: str) -> dict[str, object]:
    return json.loads((ROOT / relative).read_text())


class ManifestTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifests = {
            path: load(path)
            for path in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json", "package.json")
        }

    def test_name_and_version_agree_everywhere(self) -> None:
        self.assertEqual({m["name"] for m in self.manifests.values()}, {"superpowers-multi-subagents"})
        self.assertEqual(len({m["version"] for m in self.manifests.values()}), 1)

    def test_each_manifest_declares_mit(self) -> None:
        for path, manifest in self.manifests.items():
            self.assertEqual(manifest["license"], "MIT", path)

    def test_descriptions_say_superpowers_is_required(self) -> None:
        for path, manifest in self.manifests.items():
            self.assertIn("superpowers", str(manifest["description"]), path)
            self.assertIn("required", str(manifest["description"]), path)

    def test_claude_depends_on_superpowers_and_allows_its_marketplace(self) -> None:
        plugin = load(".claude-plugin/plugin.json")
        marketplace = load(".claude-plugin/marketplace.json")
        dependencies = plugin["dependencies"]
        self.assertIsInstance(dependencies, list)
        names = {d["name"]: d["marketplace"] for d in dependencies}
        self.assertIn("superpowers", names)
        self.assertIn(names["superpowers"], marketplace["allowCrossMarketplaceDependenciesOn"])

    def test_marketplace_entries_point_at_the_plugin_root(self) -> None:
        claude = load(".claude-plugin/marketplace.json")["plugins"]
        codex = load(".agents/plugins/marketplace.json")["plugins"]
        self.assertEqual((claude[0]["name"], claude[0]["source"]), ("superpowers-multi-subagents", "./"))
        self.assertEqual(codex[0]["source"]["path"], "./")

    def test_codex_skills_path_exists(self) -> None:
        self.assertTrue((ROOT / str(load(".codex-plugin/plugin.json")["skills"])).is_dir())

    def test_owner_name_is_used(self) -> None:
        for path in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
            self.assertEqual(load(path)["author"]["name"], OWNER)


class LicenseTest(unittest.TestCase):
    def test_license_is_mit_with_the_owner(self) -> None:
        text = (ROOT / "LICENSE").read_text()
        self.assertTrue(text.startswith("MIT License"))
        self.assertIn(f"Copyright (c) 2026 {OWNER}", text)

    def test_no_upstream_skill_is_copied_into_the_repo(self) -> None:
        self.assertEqual({p.name for p in (ROOT / "skills").iterdir() if p.is_dir()}, OUR_SKILLS)

    def test_license_doc_names_upstream_and_its_license(self) -> None:
        text = (ROOT / "docs/license.md").read_text()
        self.assertIn("Jesse Vincent", text)
        self.assertIn("MIT", text)


class ReadmeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.readme = (ROOT / "README.md").read_text()

    def test_install_is_the_first_section(self) -> None:
        self.assertEqual(re.findall(r"^## (.+)$", self.readme, re.M)[0], "Install")

    def test_install_block_comes_before_every_other_section(self) -> None:
        first_other = self.readme.index("## What it adds")
        top = self.readme[:first_other]
        for needle in (
            "Requires superpowers, already installed",
            "./install.py --host auto",
            "docs/install.md",
            "docs/README.md",
        ):
            self.assertIn(needle, top)

    def test_credits_and_not_affiliated_line(self) -> None:
        self.assertIn("## Credits and license", self.readme)
        self.assertIn("not affiliated with or endorsed by superpowers", self.readme)
        self.assertIn("(LICENSE)", self.readme)

    def test_docs_readme_has_architecture_and_links_every_doc(self) -> None:
        docs = ROOT / "docs"
        text = (docs / "README.md").read_text()
        self.assertIn("## Architecture overview", text)
        for other in docs.glob("*.md"):
            if other.name != "README.md":
                self.assertIn(f"]({other.name})", text, other.name)


NODE_PROBE = """
import plugin, {readSkills, superpowersInstalled} from %r;
const config = {};
await (await plugin.server()).config(config);
const added = [];
await plugin.setup({skill: {transform: async (edit) => edit({add: (s) => added.push(s.id)})}});
console.log(JSON.stringify({installed: superpowersInstalled(), skills: readSkills().length, config, added}));
"""


@unittest.skipUnless(shutil.which("node") and shutil.which("python3"), "node and python3 needed")
class OpenCodePluginTest(unittest.TestCase):
    def _probe(self, environ: dict[str, str]) -> dict[str, object]:
        done = subprocess.run(
            ["node", "--input-type=module", "-e", NODE_PROBE % str(PLUGIN_FILE)],
            capture_output=True, text=True, env=environ, check=True,
        )
        return json.loads(done.stdout.strip().splitlines()[-1])

    def _environ(self, **extra: str) -> dict[str, str]:
        base = {k: v for k, v in os.environ.items() if k != "SUPERPOWERS_SKILLS_DIR"}
        return {**base, **extra}

    def test_registers_both_skills_when_superpowers_is_found(self) -> None:
        result = self._probe(self._environ(SUPERPOWERS_SKILLS_DIR=tempfile.mkdtemp()))
        self.assertTrue(result["installed"])
        self.assertEqual(sorted(result["added"]), sorted(OUR_SKILLS))
        self.assertEqual(len(result["config"]["skills"]["paths"]), 1)

    def test_registers_nothing_when_superpowers_is_missing(self) -> None:
        result = self._probe(self._environ(HOME=tempfile.mkdtemp()))
        self.assertFalse(result["installed"])
        self.assertEqual(result["added"], [])
        self.assertEqual(result["config"], {})


if __name__ == "__main__":
    unittest.main()
