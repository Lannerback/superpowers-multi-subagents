from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

_STATUS = re.compile(
    r"^\**Status:\**\s*(DONE_WITH_CONCERNS|DONE|BLOCKED|NEEDS_CONTEXT|APPROVED|CHANGES_REQUIRED)\**\s*$"
)
_LOG_TAIL_BYTES = 8192


def read_report_status(report: Path, started_at: float) -> str | None:
    """Read status from the report, not the log: logs can echo the prompt's status list."""
    if not report.exists() or report.stat().st_mtime < started_at - 1:
        return None
    lines = [line.strip() for line in report.read_text(errors="replace").splitlines() if line.strip()]
    if not lines:
        return None
    match = _STATUS.match(lines[-1])
    return match.group(1) if match else None


def is_token_error(log: Path, patterns: Sequence[str]) -> bool:
    if not log.exists():
        return False
    data = log.read_bytes()[-_LOG_TAIL_BYTES:].decode(errors="replace")
    return any(re.search(pattern, data, re.IGNORECASE) for pattern in patterns)
