from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from agent_router.models import DispatchRequest


class Ledger:
    def __init__(self, path: Path, clock: Callable[[], float]) -> None:
        self._path = path
        self._clock = clock

    def record(
        self, request: DispatchRequest, runner: str, model: str, attempt: int, result: str
    ) -> None:
        # The "Agent-run" prefix keeps upstream's "Task <N>:" resume parsing unaffected.
        stamp = datetime.fromtimestamp(self._clock(), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = (
            f"Agent-run {stamp} task={request.task} role={request.role} runner={runner} "
            f"model={model} effort={request.effort} attempt={attempt} result={result}\n"
        )
        with self._path.open("a") as ledger:
            ledger.write(line)
