from __future__ import annotations

import os
import signal
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import FrameType

_KILL_GRACE_SECONDS = 5
_TERMINATION_SIGNALS = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)


@dataclass(frozen=True)
class RunOutcome:
    returncode: int
    reason: str


def raise_on_termination_signals() -> None:
    """Turn termination signals into SystemExit, so the runner's cleanup runs."""
    for signum in _TERMINATION_SIGNALS:
        # An inherited ignore is deliberate: the skill starts long runs under nohup.
        if signal.getsignal(signum) != signal.SIG_IGN:
            signal.signal(signum, _exit_on_signal)


def _exit_on_signal(signum: int, _frame: FrameType | None) -> None:
    # Ignore repeats, so a second signal cannot interrupt the worker's cleanup.
    for repeat in _TERMINATION_SIGNALS:
        signal.signal(repeat, signal.SIG_IGN)
    raise SystemExit(128 + signum)


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
            except (FileNotFoundError, PermissionError) as error:
                log.write(f"command not runnable: {argv[0]}: {error}\n".encode())
                return RunOutcome(127, "not_found")
            try:
                return self._supervise(process, log_path, watch, run_seconds, stall_seconds)
            finally:
                if process.poll() is None:
                    self._terminate(process)

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
        self._signal_group(process, signal.SIGTERM)
        try:
            process.wait(timeout=_KILL_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            self._signal_group(process, signal.SIGKILL)
            process.wait()

    def _signal_group(self, process: subprocess.Popen[bytes], signum: signal.Signals) -> None:
        # A worker that just exited has no group left. macOS reports a zombie as PermissionError.
        try:
            os.killpg(process.pid, signum)
        except (ProcessLookupError, PermissionError):
            pass
