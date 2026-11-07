#!/usr/bin/env python3
"""Symlink this repo's skills into each agent's skills folder."""
from __future__ import annotations

import argparse
from pathlib import Path

HOST_TARGETS = {
    "claude": ".claude/skills",
    "codex": ".agents/skills",
    "opencode": ".config/opencode/skills",
    "cursor": ".agents/skills",
}


def install(skills_root: Path, target: Path) -> list[str]:
    target.mkdir(parents=True, exist_ok=True)
    linked = []
    for skill in _skills(skills_root):
        link = target / skill.name
        if link.is_symlink() and link.resolve() == skill.resolve():
            continue
        if link.exists() or link.is_symlink():
            raise FileExistsError(f"{link} already exists and is not this repo's skill")
        link.symlink_to(skill.resolve())
        linked.append(str(link))
    return linked


def uninstall(skills_root: Path, target: Path) -> list[str]:
    removed = []
    for skill in _skills(skills_root):
        link = target / skill.name
        if link.is_symlink() and link.resolve() == skill.resolve():
            link.unlink()
            removed.append(str(link))
    return removed


def _skills(skills_root: Path) -> list[Path]:
    return sorted(path for path in skills_root.iterdir() if (path / "SKILL.md").exists())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", nargs="*", default=[], choices=sorted(HOST_TARGETS))
    parser.add_argument("--target", help="skills folder for any other agent")
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    targets = [Path.home() / HOST_TARGETS[host] for host in args.host]
    if args.target:
        targets.append(Path(args.target).expanduser())
    if not targets:
        parser.error("pass --host or --target")
    skills_root = Path(__file__).resolve().parent / "skills"
    action = uninstall if args.uninstall else install
    for target in targets:
        for path in action(skills_root, target):
            print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
