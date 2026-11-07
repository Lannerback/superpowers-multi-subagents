from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path

_CANDIDATE_GLOBS = (
    ".claude/plugins/cache/*/superpowers/*/skills",
    ".codex/plugins/cache/*/superpowers/*/skills",
)
_WATCHED = ("writing-plans/SKILL.md", "subagent-driven-development/SKILL.md")
_VERSION = re.compile(r"\d+(\.\d+)*")


def resolve_skills_dir(home: Path, environ: Mapping[str, str]) -> Path:
    override = environ.get("SUPERPOWERS_SKILLS_DIR")
    if override:
        return Path(override)
    candidates = [
        path
        for pattern in _CANDIDATE_GLOBS
        for path in home.glob(pattern)
        if (path / "subagent-driven-development" / "SKILL.md").exists()
    ]
    if not candidates:
        raise LookupError("superpowers not found: install it or set SUPERPOWERS_SKILLS_DIR")
    return max(candidates, key=_version_key)


def find_drift(skills_dir: Path, lock_path: Path) -> list[str]:
    raw: object = json.loads(lock_path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"{lock_path} must be an object")
    return [name for name in _WATCHED if raw.get(name) != _digest(skills_dir / name)]


def write_lock(skills_dir: Path, lock_path: Path) -> None:
    data = {name: _digest(skills_dir / name) for name in _WATCHED}
    lock_path.write_text(json.dumps(data, indent=2) + "\n")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _version_key(skills_dir: Path) -> tuple[int, ...]:
    name = skills_dir.parent.name
    return tuple(int(part) for part in name.split(".")) if _VERSION.fullmatch(name) else (0,)
