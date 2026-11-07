---
name: subagent-driven-development-multi
description: Use when executing an implementation plan on external agents such as opencode, codex, claude or cursor to save the current session's tokens, or when a plan names this skill
---

# Subagent-Driven Development on Multiple Agents

Announce: "I'm using subagent-driven-development-multi to execute this plan."

Use the superpowers `subagent-driven-development` skill and follow all of it: setup, ledger, resume rules, reviews, fix loop, final review. If your harness does not list it, read `SKILL.md` from `<upstream-path>/subagent-driven-development/`, using the path from Setup step 3. Only the rules below override it.

**Goal:** this session coordinates and external agents do the work. Host subagents are the last resort.

## Setup

`SKILL_DIR` is this skill's directory, as an absolute path. `ROUTER` is `$SKILL_DIR/scripts/agent-router`. `HOST` is the harness you are running in: `claude`, `codex`, `opencode`, `cursor`, or `other`.

1. Run `"$ROUTER" doctor --host "$HOST"`. Report any `FAIL`. Continue if at least one agent is ok.
2. Run `"$ROUTER" upstream-check`. If it prints a changed file, read that file. If an override below no longer applies, stop and tell your human partner. Otherwise mention the drift once and continue.
3. Run `"$ROUTER" upstream-path`. Upstream's scripts are in `<that path>/subagent-driven-development/scripts/`. Run them as upstream describes.
4. Run `"$ROUTER" git-policy` and keep the value.

## Dispatch

Replace every subagent dispatch, for implementers, reviewers, fixers and the final reviewer, with:

```bash
"$ROUTER" run --host "$HOST" --role <role> --task <N> --tier <tier> --effort <effort> \
  --cwd <repo> --workspace <workspace> --prompt-file <file> --report-file <file>
```

- **Prompt file:** write it to `<workspace>/task-<N>-<role>-prompt.md`. Use the upstream template's prompt body and append [references/agent-contract.md](references/agent-contract.md). Where they conflict, the contract wins. The router adds the report file, the ledger path and, under `no-commit`, the git rule. Do not add them yourself.
- **Report file:** `<workspace>/task-<N>-<role>-report.md`, as an absolute path. The router reads the status from its last line. A template's `[REPORT_FILE]` is the implementer's report, as input for reviewers.
- **Fixers append:** pass the implementer's report, `<workspace>/task-<N>-implementer-report.md`, as `--report-file`, and tell the fixer in its prompt to append to that same file. The final fix wave has no implementer report, so it uses its own `task-final-fixer-1-report.md`.
- **Roles:** `implementer`, `reviewer`, `fixer-<R>`, `re-reviewer-<R>`, `final-reviewer`. A re-review gets its own role, so it cannot overwrite the report holding the findings.
- **Final review:** use `--task final` for the final reviewer, its fixer and its re-reviewer.
- **Tier and effort:** take them from the task's `Route` line, replacing upstream's Model Selection. Without a Route line, use `standard` and `medium`. Reviewers use the task's values, at least `standard`. Fix rounds 4-5 go one tier up. The final review uses `capable` and `high`.
- **`Route: orchestrator`:** run that task yourself.
- **Fix rounds:** external agents cannot be resumed. Every round is a fresh dispatch carrying the brief path, report path and findings, which upstream allows.
- **Reading:** always read every reviewer, re-reviewer and final-reviewer report, whatever its verdict: `Status: APPROVED` can still carry Minor and ⚠️ items, which upstream requires you to handle. For other roles, read the router's output and, when needed, the report file. Do not read logs unless a dispatch failed.
- **Reviewer `NEEDS_CONTEXT`:** give it the missing context and dispatch the same role again.
- **Long runs:** a dispatch can last `limits.run_seconds` for each attempt on each agent, far beyond a normal shell timeout. Run it with your harness's background execution and wait for its completion notice. If your harness has none, start it with `nohup`, redirect its output to `<workspace>/task-<N>-<role>-router.out`, and check for that process's exit. Never rely on a foreground call.

## Router exits

| Exit | Output | Meaning | Do this |
|---|---|---|---|
| 0 | `Status: <X>` | An agent finished | Handle `<X>` as upstream handles that report status. `APPROVED` and `CHANGES_REQUIRED` are the reviewer's verdict, mapped in the contract |
| 75 | `Status: EXHAUSTED`, `host_prompt=<file>` | Every enabled external agent failed or ran out of tokens | Dispatch this one role through your harness's own subagent, per upstream's Model Selection, using that file as its prompt. It holds your prompt plus the report file, the `no-commit` rule and the partial-edits note. A host subagent has no git guard, so never drop them. Append `Agent-run <UTC> task=<N> role=<role> runner=host model=<model> result=<status>` to the ledger |
| 1 | `Status: BLOCKED`, `runner=none` | Exhausted, and this host's fallback is `block` | Stop and report to your human partner |
| 1 | `Status: BLOCKED`, `git_policy_violation` | Under `no-commit`, the agent changed HEAD or the index. The ledger has the line | Stop and report to your human partner. Do not retry or undo it |
| 2 | `Status: ERROR` and a message | Bad call or bad config. No agent ran | Fix what the message names and run it again. Do not fall back to host subagents. If superpowers is not found, set `SUPERPOWERS_SKILLS_DIR` or tell your human partner |
| Other | none | The router was killed, and took its worker down | Treat the dispatch as failed. The working tree may hold partial edits, so say so in the next prompt |

Retry the router on the next dispatch. Agents out of tokens are skipped until their cooldown ends.

## Ledger

The ledger stays upstream's `<workspace>/progress.md`. The router appends `Agent-run` lines and you append `Snapshot:` lines: ignore both when applying upstream's resume rules ("last line" means last line starting `Task`). Only you write `Task <N>:` lines.

## Git policy `no-commit`

External agents run with a best-effort git guard, which denies mutating commands in the repository of `--cwd`. The router also blocks a dispatch that changes HEAD or the index. Applies only when `git-policy` prints `no-commit`:

- Ignore upstream's commit instructions, for every role, and for yourself.
- **Snapshots:** there are no commits for a resume to find, so the ledger holds the bases. Before each dispatch that changes code, run `"$SKILL_DIR/scripts/worktree-snapshot" -C <repo>`, which touches neither the index nor history, and append `Snapshot: task=<N> phase=<start|fix-R> tree=<id>`. Use `phase=start` before the implementer and `phase=fix-R` before round R's fixer. The final fix wave uses `task=final`.
- Replace `review-package` with `"$SKILL_DIR/scripts/worktree-review-package" -C <repo> --base <tree> <workspace>/task-<N>-review.diff <task paths>`, using the task's Files list. Read `<tree>` from the ledger, never from memory: the task's `phase=start` line for its review, and the round's `phase=fix-R` line for a scoped re-review. For the final review, use Task 1's `phase=start` line and pass no paths.
- Before Task 1, run `git status --short` in each repository and record it in the ledger as the baseline, so reviewers do not attribute those files to a task.
- Fix-round lines end with `snapshots <a7>..<b7>` instead of `commits <a7>..<b7>`: the first 7 characters of the round's `phase=fix-R` tree, and of a snapshot you take after the fix.
- Completion lines become `Task <N>: complete (<changed files>; <test evidence>; review clean)`.
- Do not stage, commit or push at the end. Report the changed files and let your human partner decide.
- Do not delete the workspace until your human partner has decided. Upstream deletes it because git history is the record, and here there is no such history.
