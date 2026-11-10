from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence

from superpowers_installers.base import RunResult


class SubprocessRunner:
    """Runs a command with no stdin, captured output and a timeout. Never uses a shell."""

    def run(self, argv: Sequence[str], timeout: float) -> RunResult:
        if shutil.which(argv[0]) is None:
            raise LookupError(f"{argv[0]} not found on PATH")
        try:
            done = subprocess.run(
                list(argv), stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise TimeoutError(f"timed out after {timeout:.0f}s") from error
        return RunResult(done.returncode, done.stdout, done.stderr)
