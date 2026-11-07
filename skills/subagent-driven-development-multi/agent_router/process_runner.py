from __future__ import annotations

import os
import signal
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

_KILL_GRACE_SECONDS = 5


@dataclass(frozen=True)
class RunOutcome:
    returncode: int
    reason: str


class ProcessRunner:
    def __init__(self, poll_seconds: float = 2.0) -> None:
        self._poll_seconds = poll_seconds

    def run(
        self,
        argv: Sequence[str],
        cwd: Path,
        env: Mapping[str, str],
        log_path: Path,
        watch: Sequence[Path],
        run_seconds: int,
        stall_seconds: int,
    ) -> RunOutcome:
        with log_path.open("wb") as log:
            try:
                # stdin is closed because codex and opencode block on an open pipe.
                process = subprocess.Popen(
                    list(argv), cwd=cwd, env=dict(env), stdin=subprocess.DEVNULL,
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                )
            except FileNotFoundError:
                log.write(f"command not found: {argv[0]}\n".encode())
                return RunOutcome(127, "not_found")
            return self._supervise(process, log_path, watch, run_seconds, stall_seconds)

    def _supervise(
        self,
        process: subprocess.Popen[bytes],
        log_path: Path,
        watch: Sequence[Path],
        run_seconds: int,
        stall_seconds: int,
    ) -> RunOutcome:
        started = last_change = time.monotonic()
        last_size = -1
        while process.poll() is None:
            time.sleep(self._poll_seconds)
            now = time.monotonic()
            size = sum(path.stat().st_size for path in (log_path, *watch) if path.exists())
            if size != last_size:
                last_size, last_change = size, now
            if now - started >= run_seconds:
                self._terminate(process)
                return RunOutcome(process.returncode, "timeout")
            if now - last_change >= stall_seconds:
                self._terminate(process)
                return RunOutcome(process.returncode, "stalled")
        return RunOutcome(process.returncode, "exited")

    def _terminate(self, process: subprocess.Popen[bytes]) -> None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=_KILL_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
