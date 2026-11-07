from __future__ import annotations

from agent_router.models import DispatchRequest

NO_COMMIT_RULE = (
    "Git rule: do not stage, commit, or run history-changing git commands. "
    "Leave your changes in the working tree."
)
COMMIT_GUARDED_RULE = (
    "Git rule: you may `git add <explicit paths>` and `git commit`. Never add with `.`, `-A` or `-u`, "
    "never commit with `-a`, `--amend` or `--no-verify`, and do not switch branches or run any other "
    "history-changing git command unless your task names it under Git-allow."
)
RETRY_NOTE = (
    "A previous attempt failed. The working tree may contain its partial edits: "
    "inspect them before you start, and keep or replace them as the task requires."
)


GIT_RULES = {"no-commit": NO_COMMIT_RULE, "commit-guarded": COMMIT_GUARDED_RULE}


def build_prompt(body: str, request: DispatchRequest, git_policy: str, retry: bool) -> str:
    parts = [GIT_RULES[git_policy]] if git_policy in GIT_RULES else []
    parts.append(body.rstrip())
    if retry:
        parts.append(RETRY_NOTE)
    parts.append(
        f"Report file: {request.report_file}\n"
        f"Ledger (read-only): {request.workspace / 'progress.md'}"
    )
    return "\n\n".join(parts)
