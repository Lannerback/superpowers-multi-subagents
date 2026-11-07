import tempfile
import unittest
from pathlib import Path

from agent_router.git_grants import normalize_grant, write_grants_file


class GitGrantsTest(unittest.TestCase):
    def test_whitespace_is_normalized(self) -> None:
        self.assertEqual(normalize_grant("  push   origin\tfeature "), "push origin feature")

    def test_newline_empty_and_leading_git_are_rejected(self) -> None:
        for bad in ("", "   ", "push\nreset", "git push"):
            with self.assertRaisesRegex(ValueError, "grant"):
                normalize_grant(bad)

    def test_file_has_one_line_per_grant(self) -> None:
        workspace = Path(tempfile.mkdtemp())
        path = write_grants_file(workspace, ("push origin x", "reset --soft HEAD"))
        self.assertEqual(path, workspace / "git-grants.txt")
        self.assertEqual(path.read_text(), "push origin x\nreset --soft HEAD\n")
