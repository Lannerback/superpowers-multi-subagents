#!/usr/bin/env python3
"""Symlink this repo's skills into each agent's skills folder."""
from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development-multi"))

from agent_router.upstream import resolve_skills_dir  # noqa: E402

HOST_TARGETS = {
    "claude": ".claude/skills",
    "codex": ".agents/skills",
    "opencode": ".config/opencode/skills",
    "cursor": ".agents/skills",
}


HOST_CONFIG_DIRS = {
    "claude": ".claude",
    "codex": ".codex",
    "opencode": ".config/opencode",
    "cursor": ".cursor",
}
AUTO = "auto"
SUPERPOWERS_HELP = """superpowers is required and was not found. Install it first (upstream: https://github.com/obra/superpowers):
  Claude Code: claude plugin marketplace add obra/superpowers-marketplace
               claude plugin install superpowers@superpowers-marketplace
  Codex:       codex plugin marketplace add obra/superpowers
               codex plugin add superpowers@superpowers-dev
  OpenCode:    add "superpowers@git+https://github.com/obra/superpowers.git" to the plugins list in opencode.json
  Others:      install it as upstream describes, then set SUPERPOWERS_SKILLS_DIR to its skills folder
Then run this script again. To install anyway, use --skip-superpowers-check."""


def resolve_hosts(requested: list[str], home: Path, force: bool) -> tuple[list[str], list[str]]:
    """Split requested hosts into installed ones and skipped ones, by their config folder."""
    names = list(HOST_CONFIG_DIRS) if AUTO in requested else requested
    present = [name for name in names if (home / HOST_CONFIG_DIRS[name]).is_dir()]
    if AUTO in requested:
        return present, []
    selected = names if force else present
    return selected, [name for name in names if name not in selected]


def find_superpowers(home: Path, environ: Mapping[str, str]) -> Path | None:
    """The installed superpowers skills folder, found the way the router finds it, or None."""
    try:
        return resolve_skills_dir(home, environ)
    except LookupError:
        return None


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
    parser.add_argument("--host", nargs="*", default=[], choices=[AUTO, *sorted(HOST_TARGETS)])
    parser.add_argument(
        "--force-host", action="store_true",
        help="create the skills folder even when the agent's config folder does not exist",
    )
    parser.add_argument("--target", help="skills folder for any other agent")
    parser.add_argument(
        "--skip-superpowers-check", action="store_true",
        help="install even when superpowers is not found",
    )
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    hosts, skipped = resolve_hosts(args.host, Path.home(), args.force_host)
    for host in skipped:
        print(f"skipped {host}: ~/{HOST_CONFIG_DIRS[host]} not found (use --force-host to install anyway)")
    targets = list(dict.fromkeys(Path.home() / HOST_TARGETS[host] for host in hosts))
    if args.target:
        targets.append(Path(args.target).expanduser())
    if not targets:
        parser.error("nothing to install: no agent config folder found. Use --host with --force-host, or --target")
    if not (args.uninstall or args.skip_superpowers_check) and find_superpowers(Path.home(), os.environ) is None:
        print(SUPERPOWERS_HELP, file=sys.stderr)
        return 2
    skills_root = ROOT / "skills"
    action = uninstall if args.uninstall else install
    for target in targets:
        for path in action(skills_root, target):
            print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
