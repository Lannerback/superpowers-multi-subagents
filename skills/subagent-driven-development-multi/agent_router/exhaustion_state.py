from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path


class ExhaustionState:
    def __init__(self, path: Path, clock: Callable[[], float]) -> None:
        self._path = path
        self._clock = clock

    def is_exhausted(self, agent: str) -> bool:
        return self._read().get(agent, 0.0) > self._clock()

    def mark(self, agent: str, seconds: int) -> None:
        data = self._read()
        data[agent] = self._clock() + seconds
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data))
        temporary.replace(self._path)

    def _read(self) -> dict[str, float]:
        if not self._path.exists():
            return {}
        try:
            raw: object = json.loads(self._path.read_text())
            if not isinstance(raw, dict):
                raise ValueError("expected an object")
            return {str(key): float(value) for key, value in raw.items()}
        except (TypeError, ValueError) as error:
            raise ValueError(f"invalid state file: {self._path}: {error}") from error
