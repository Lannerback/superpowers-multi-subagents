import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills/subagent-driven-development-multi/scripts/worktree-review-package"
)


class ReviewPackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(tempfile.mkdtemp())
        for args in (["init", "-q"], ["config", "user.name", "t"], ["config", "user.email", "t@t"]):
            subprocess.run(["git", *args], cwd=self.repo, check=True)
        (self.repo / "tracked.txt").write_text("old\n")
        (self.repo / "other.txt").write_text("old\n")
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=self.repo, check=True)
        (self.repo / "tracked.txt").write_text("new\n")
        (self.repo / "other.txt").write_text("unrelated\n")
        (self.repo / "added.txt").write_text("brand new\n")
        self.out = self.repo.parent / f"{self.repo.name}.diff"

    def test_includes_scoped_diff_and_new_files(self) -> None:
        subprocess.run(
            [str(SCRIPT), "-C", str(self.repo), str(self.out), "tracked.txt", "added.txt"], check=True
        )
        text = self.out.read_text()
        self.assertIn("+new", text)
        self.assertIn("=== new file: added.txt", text)
        self.assertIn("brand new", text)
        self.assertNotIn("unrelated", text)
