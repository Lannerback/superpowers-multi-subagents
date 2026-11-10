from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from agent_router.upstream import host_skills_dirs

Outcome = Literal["present", "installed", "failed", "not-detected", "manual"]


@dataclass(frozen=True)
class RunResult:
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def run(self, argv: Sequence[str], timeout: float) -> RunResult:
        """Run one command. Raises LookupError if the program is missing, TimeoutError on timeout."""
        ...


@dataclass(frozen=True)
class HostInstaller:
    """One agent: where its superpowers copy lives and the commands that install it.

    Empty commands mean there is no scriptable install; the user follows the printed help.
    """

    host: str
    commands: tuple[tuple[str, ...], ...] = ()

    def is_installed(self, home: Path) -> bool:
        return bool(host_skills_dirs(self.host, home))


@dataclass(frozen=True)
class HostResult:
    host: str
    outcome: Outcome
    detail: str = ""

    @property
    def failed(self) -> bool:
        return self.outcome in ("failed", "not-detected")
