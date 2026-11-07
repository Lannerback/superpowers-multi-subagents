import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from install import HOST_TARGETS, install, uninstall  # noqa: E402


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
