from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path

_CANDIDATE_GLOBS = (
    ".claude/plugins/cache/*/superpowers/*/skills",
    ".codex/plugins/cache/*/superpowers/*/skills",
    ".cache/opencode/npm/*/*/node_modules/superpowers/skills",
    ".cache/opencode/packages/superpowers@*/*/*/*/node_modules/superpowers/skills",
)
_SDD = "subagent-driven-development"
WATCHED = (
    "writing-plans/SKILL.md",
    f"{_SDD}/SKILL.md",
    f"{_SDD}/implementer-prompt.md",
    f"{_SDD}/task-reviewer-prompt.md",
    f"{_SDD}/re-review-prompt.md",
    f"{_SDD}/references/resuming.md",
    f"{_SDD}/references/fix-loop.md",
    f"{_SDD}/references/final-review.md",
    f"{_SDD}/references/handling-reports.md",
    f"{_SDD}/scripts/sdd-workspace",
    f"{_SDD}/scripts/task-brief",
    "requesting-code-review/code-reviewer.md",
)
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
    locked = _read_lock(lock_path)
    return [
        name for name in WATCHED
        if not (skills_dir / name).is_file() or locked.get(name) != _digest(skills_dir / name)
    ]


def write_lock(skills_dir: Path, lock_path: Path) -> None:
    missing = [name for name in WATCHED if not (skills_dir / name).is_file()]
    if missing:
        raise LookupError(f"cannot accept {skills_dir}: missing {', '.join(missing)}")
    data = {name: _digest(skills_dir / name) for name in WATCHED}
    lock_path.write_text(json.dumps(data, indent=2) + "\n")


def _read_lock(lock_path: Path) -> dict[str, object]:
    if not lock_path.exists():
        return {}
    try:
        raw: object = json.loads(lock_path.read_text())
    except ValueError as error:
        raise ValueError(f"{lock_path}: invalid JSON: {error}") from error
    if not isinstance(raw, dict):
        raise ValueError(f"{lock_path} must be an object")
    return {str(key): value for key, value in raw.items()}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _version_key(skills_dir: Path) -> tuple[int, ...]:
    name = skills_dir.parent.name
    return _parse_version(name) or _parse_version(_package_version(skills_dir.parent)) or (0,)


def _parse_version(text: str) -> tuple[int, ...] | None:
    return tuple(int(part) for part in text.split(".")) if _VERSION.fullmatch(text) else None


def _package_version(package_dir: Path) -> str:
    """OpenCode's cache folders carry no version in their names. Empty means unknown, sorted last."""
    try:
        raw: object = json.loads((package_dir / "package.json").read_text())
    except (OSError, ValueError):
        return ""
    version = raw.get("version") if isinstance(raw, dict) else None
    return version if isinstance(version, str) else ""
