from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Mapping
from pathlib import Path


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


def _git(cwd: Path, environ: Mapping[str, str], *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, env=dict(environ), capture_output=True, text=True,
            errors="replace", check=False,
        )
    except OSError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None
