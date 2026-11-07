from __future__ import annotations

import json
from pathlib import Path

from agent_router.models import (
    EFFORTS,
    GIT_POLICIES,
    HOST_FALLBACKS,
    TIERS,
    AgentConfig,
    Limits,
    RouterConfig,
)

USER_CONFIG = ".config/superpowers-multi-subagents/agents.json"
ALL_MODELS = "all"


def resolve_config_path(skill_root: Path, home: Path) -> Path:
    override = home / USER_CONFIG
    return override if override.exists() else skill_root / "config" / "agents.json"


def load_config(path: Path) -> RouterConfig:
    if not path.exists():
        raise LookupError(f"config not found: {path}")
    raw: object = json.loads(path.read_text())
    root = _mapping(raw, "config")
    agents_raw = _mapping(root.get("agents"), "agents")
    agents = {name: _agent(name, value) for name, value in agents_raw.items()}
    order = _strings(root.get("order"), "order")
    for name in order:
        if name not in agents:
            raise ValueError(f"order names unknown agent: {name}")
    git_policy = _string(root.get("git_policy"), "git_policy")
    if git_policy not in GIT_POLICIES:
        raise ValueError(f"git_policy must be one of {GIT_POLICIES}")
    host_fallback = {
        host: _string(value, f"host_fallback.{host}")
        for host, value in _mapping(root.get("host_fallback"), "host_fallback").items()
    }
    for host, value in host_fallback.items():
        if value not in HOST_FALLBACKS:
            raise ValueError(f"host_fallback.{host} must be one of {HOST_FALLBACKS}")
    return RouterConfig(
        order=order,
        agents=agents,
        limits=_limits(root.get("limits")),
        host_fallback=host_fallback,
        git_policy=git_policy,
        token_error_patterns=_strings(root.get("token_error_patterns"), "token_error_patterns"),
    )


def _agent(name: str, value: object) -> AgentConfig:
    raw = _mapping(value, f"agents.{name}")
    enabled = raw.get("enabled")
    if not isinstance(enabled, bool):
        raise ValueError(f"agents.{name}.enabled must be a boolean")
    models_raw = raw.get("models", ALL_MODELS)
    allowed = None if models_raw == ALL_MODELS else _strings(models_raw, f"agents.{name}.models")
    tiers = {
        tier: _string(model, f"agents.{name}.tiers.{tier}")
        for tier, model in _mapping(raw.get("tiers", {}), f"agents.{name}.tiers").items()
    }
    add_dir_flag = raw.get("add_dir_flag")
    agent = AgentConfig(
        name=name,
        enabled=enabled,
        command=_strings(raw.get("command", []), f"agents.{name}.command"),
        allowed_models=allowed,
        efforts=_strings(raw.get("efforts", []), f"agents.{name}.efforts"),
        tiers=tiers,
        add_dir_flag=add_dir_flag if isinstance(add_dir_flag, str) else None,
        optional_dirs=_strings(raw.get("optional_dirs", []), f"agents.{name}.optional_dirs"),
        unset_env_prefixes=_strings(
            raw.get("unset_env_prefixes", []), f"agents.{name}.unset_env_prefixes"
        ),
    )
    if enabled:
        _validate_enabled(agent)
    return agent


def _validate_enabled(agent: AgentConfig) -> None:
    if not agent.command:
        raise ValueError(f"agent {agent.name} is enabled but has no command")
    missing = [tier for tier in TIERS if tier not in agent.tiers]
    if missing:
        raise ValueError(f"agent {agent.name} is missing tiers: {missing}")
    if agent.allowed_models is not None:
        bad = [m for m in agent.tiers.values() if m not in agent.allowed_models]
        if bad:
            raise ValueError(f"agent {agent.name} tiers use models not allowed: {bad}")
    unknown = [e for e in agent.efforts if e not in EFFORTS]
    if unknown:
        raise ValueError(f"agent {agent.name} has unknown efforts: {unknown}")


def _limits(value: object) -> Limits:
    raw = _mapping(value, "limits")
    return Limits(
        run_seconds=_integer(raw.get("run_seconds"), "limits.run_seconds"),
        stall_seconds=_integer(raw.get("stall_seconds"), "limits.stall_seconds"),
        error_attempts=_integer(raw.get("error_attempts"), "limits.error_attempts"),
        token_cooldown_seconds=_integer(
            raw.get("token_cooldown_seconds"), "limits.token_cooldown_seconds"
        ),
    )


def _mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return {str(key): item for key, item in value.items()}


def _strings(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be a list of strings")
    return tuple(str(item) for item in value)


def _string(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    return value


def _integer(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    return value
