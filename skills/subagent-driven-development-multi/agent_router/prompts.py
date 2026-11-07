from __future__ import annotations

from agent_router.models import DispatchRequest

NO_COMMIT_RULE = (
    "Git rule: do not stage, commit, or run history-changing git commands. "
    "Leave your changes in the working tree."
)
RETRY_NOTE = (
    "A previous attempt failed. The working tree may contain its partial edits: "
    "inspect them before you start, and keep or replace them as the task requires."
)


def build_prompt(body: str, request: DispatchRequest, no_commit: bool, retry: bool) -> str:
    parts = [NO_COMMIT_RULE] if no_commit else []
    parts.append(body.rstrip())
    if retry:
        parts.append(RETRY_NOTE)
    parts.append(
        f"Report file: {request.report_file}\n"
        f"Ledger (read-only): {request.workspace / 'progress.md'}"
    )
    return "\n\n".join(parts)
