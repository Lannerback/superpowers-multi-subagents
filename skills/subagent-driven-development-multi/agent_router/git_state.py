from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitPosition:
    branch: str | None
    head: str | None


def git_toplevel(cwd: Path, environ: Mapping[str, str]) -> str | None:
    return _git(cwd, environ, "rev-parse", "--show-toplevel")


def git_fingerprint(cwd: Path, environ: Mapping[str, str]) -> str | None:
    """Identify HEAD and the index's content. None outside a repository.

    Hashes `ls-files --stage`, not the index file: `git status` rewrites that file's stat data.
    """
    if git_toplevel(cwd, environ) is None:
        return None
    parts = (
        _git(cwd, environ, "symbolic-ref", "-q", "HEAD"),
        _git(cwd, environ, "rev-parse", "-q", "--verify", "HEAD"),
        _git(cwd, environ, "ls-files", "--stage", "-z"),
    )
    return hashlib.sha256(repr(parts).encode()).hexdigest()


def git_position(cwd: Path, environ: Mapping[str, str]) -> GitPosition | None:
    """Current branch and HEAD commit. None outside a repository."""
    if git_toplevel(cwd, environ) is None:
        return None
    return GitPosition(
        _git(cwd, environ, "symbolic-ref", "-q", "HEAD"),
        _git(cwd, environ, "rev-parse", "-q", "--verify", "HEAD"),
    )


def advanced_cleanly(cwd: Path, environ: Mapping[str, str], before: GitPosition) -> bool:
    """Same branch, and HEAD is the old HEAD or a descendant of it."""
    now = git_position(cwd, environ)
    if now is None or now.branch != before.branch:
        return False
    if before.head is None or now.head == before.head:
        return True
    return now.head is not None and _git(
        cwd, environ, "merge-base", "--is-ancestor", before.head, now.head
    ) is not None


def commit_range(before: GitPosition, now: GitPosition | None) -> str | None:
    if now is None or before.head is None or now.head is None or before.head == now.head:
        return None
    return f"{before.head[:7]}..{now.head[:7]}"


def _git(cwd: Path, environ: Mapping[str, str], *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, env=dict(environ), capture_output=True, text=True,
            errors="replace", check=False,
        )
    except OSError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None
