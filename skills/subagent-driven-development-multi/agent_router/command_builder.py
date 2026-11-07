from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from agent_router.models import AgentConfig

_PLACEHOLDER = re.compile(r"\{(model|effort|cwd|workspace|title|prompt)\}")


def render_command(agent: AgentConfig, values: Mapping[str, str], home: Path) -> list[str]:
    argv = [
        _PLACEHOLDER.sub(lambda match: values.get(match.group(1), ""), part)
        for part in agent.command
    ]
    if agent.add_dir_flag:
        for raw in agent.optional_dirs:
            path = home / raw[2:] if raw.startswith("~/") else Path(raw)
            if path.is_dir():
                argv += [agent.add_dir_flag, str(path)]
    return argv


def build_env(
    agent: AgentConfig,
    base: Mapping[str, str],
    extra: Mapping[str, str],
    guard_dir: Path | None,
) -> dict[str, str]:
    env = {
        key: value
        for key, value in base.items()
        if not any(key.startswith(prefix) for prefix in agent.unset_env_prefixes)
    }
    env.update(extra)
    if guard_dir is not None:
        env["PATH"] = f"{guard_dir}:{env.get('PATH', '')}"
    return env
