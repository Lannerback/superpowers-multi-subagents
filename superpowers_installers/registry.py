from __future__ import annotations

from superpowers_installers.base import HostInstaller

# Only Claude Code and Codex have a scriptable install. The others print the manual step.
INSTALLERS: dict[str, HostInstaller] = {
    "claude": HostInstaller(
        "claude",
        (
            ("claude", "plugin", "marketplace", "add", "obra/superpowers-marketplace"),
            ("claude", "plugin", "install", "superpowers@superpowers-marketplace"),
        ),
    ),
    "codex": HostInstaller(
        "codex",
        (
            ("codex", "plugin", "marketplace", "add", "obra/superpowers"),
            ("codex", "plugin", "add", "superpowers@superpowers-dev"),
        ),
    ),
    "opencode": HostInstaller("opencode"),
    "cursor": HostInstaller("cursor"),
}
