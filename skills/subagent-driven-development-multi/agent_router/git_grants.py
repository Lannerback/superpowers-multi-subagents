from __future__ import annotations

from pathlib import Path

GRANTS_FILE_NAME = "git-grants.txt"


def normalize_grant(grant: str) -> str:
    """One exact git command line, without the leading `git` and without extra whitespace."""
    if "\n" in grant or "\r" in grant:
        raise ValueError("git grant must be a single line")
    words = grant.split()
    if not words:
        raise ValueError("git grant is empty")
    if words[0] == "git":
        raise ValueError("git grant must not start with 'git': write the arguments only")
    return " ".join(words)


def write_grants_file(workspace: Path, grants: tuple[str, ...]) -> Path:
    path = workspace / GRANTS_FILE_NAME
    path.write_text("".join(f"{normalize_grant(grant)}\n" for grant in grants))
    return path
