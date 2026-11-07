from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

EFFORTS = ("low", "medium", "high", "xhigh", "max")
TIERS = ("cheap", "standard", "capable")
GIT_POLICIES = ("no-commit", "allow")
HOST_FALLBACKS = ("subagent", "block")


@dataclass(frozen=True)
class AgentConfig:
    name: str
    enabled: bool
    command: tuple[str, ...]
    allowed_models: tuple[str, ...] | None
    efforts: tuple[str, ...]
    tiers: Mapping[str, str]
    add_dir_flag: str | None
    optional_dirs: tuple[str, ...]
    unset_env_prefixes: tuple[str, ...]


@dataclass(frozen=True)
class Limits:
    run_seconds: int
    stall_seconds: int
    error_attempts: int
    token_cooldown_seconds: int


@dataclass(frozen=True)
class RouterConfig:
    order: tuple[str, ...]
    agents: Mapping[str, AgentConfig]
    limits: Limits
    host_fallback: Mapping[str, str]
    git_policy: str
    token_error_patterns: tuple[str, ...]


@dataclass(frozen=True)
class DispatchRequest:
    host: str
    role: str
    task: str
    tier: str
    effort: str
    cwd: Path
    workspace: Path
    prompt_file: Path
    report_file: Path


@dataclass(frozen=True)
class DispatchResult:
    status: str
    runner: str
    model: str
    exit_code: int
    log: Path | None
