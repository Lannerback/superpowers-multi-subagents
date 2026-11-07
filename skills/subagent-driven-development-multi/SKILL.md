---
name: subagent-driven-development-multi
description: Use when executing an implementation plan on external agents such as opencode, codex, claude or cursor to save the current session's tokens, or when a plan names this skill
---

# Subagent-Driven Development on Multiple Agents

Announce: "I'm using subagent-driven-development-multi to execute this plan."

Use the superpowers `subagent-driven-development` skill and follow all of it: setup, ledger, resume rules, reviews, fix loop, final review. If your harness does not list it, read `SKILL.md` from `<upstream-path>/subagent-driven-development/`, using the path from Setup step 3. Only the rules below override it.

**Goal:** this session coordinates and external agents do the work. Host subagents are the last resort.

## Setup

`ROUTER` is `scripts/agent-router` in this skill's directory. `HOST` is the harness you are running in: `claude`, `codex`, `opencode`, `cursor`, or `other`.

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

- **Prompt file:** write it to `<workspace>/task-<N>-<role>-prompt.md`. Use the upstream template's prompt body and append [references/agent-contract.md](references/agent-contract.md). Where they conflict, the contract wins.
- **Report file:** `<workspace>/task-<N>-<role>-report.md`. The router reads the status from its last line.
- **Roles:** `implementer`, `reviewer`, `fixer-<R>`, `final-reviewer`.
- **Tier and effort:** take them from the task's `Route` line, replacing upstream's Model Selection. Without a Route line, use `standard` and `medium`. Reviewers use the task's values. Fix rounds 4-5 go one tier up. The final review uses `capable` and `high`.
- **`Route: orchestrator`:** run that task yourself.
- **Fix rounds:** external agents cannot be resumed. Every round is a fresh dispatch carrying the brief path, report path and findings, which upstream allows.
- Read only the router's output and, when needed, the report file. Do not read logs unless a dispatch failed.
- **Long runs:** a dispatch can last `limits.run_seconds` for each attempt on each agent, far beyond a normal shell timeout. Run it with your harness's background execution and wait for its completion notice. If your harness has none, start it with `nohup`, redirect its output to `<workspace>/task-<N>-<role>-router.out`, and check for that process's exit. Never rely on a foreground call.

## Router exits

| Exit | Output | Meaning | Do this |
|---|---|---|---|
| 0 | `Status: <X>` | An agent finished | Handle `<X>` as upstream handles that report status. `APPROVED` and `CHANGES_REQUIRED` are the reviewer's verdict |
| 75 | `Status: EXHAUSTED` | Every enabled external agent failed or ran out of tokens | Dispatch this one role through your harness's own subagent, per upstream's Model Selection, with the same prompt and report file. Append `Agent-run <UTC> task=<N> role=<role> runner=host model=<model> result=<status>` to the ledger |
| 1 | `Status: BLOCKED` | Exhausted, and this host's fallback is `block` | Stop and report to your human partner |

Retry the router on the next dispatch. Agents out of tokens are skipped until their cooldown ends.

## Ledger

The ledger stays upstream's `<workspace>/progress.md`. The router appends `Agent-run` lines: ignore them when applying upstream's resume rules ("last line" means last line starting `Task`). Only you write `Task <N>:` lines.

## Git policy `no-commit`

External agents run with a git guard on `PATH`, which denies mutating commands. Applies only when `git-policy` prints `no-commit`:

- Ignore upstream's commit instructions, for every role, and for yourself.
- Before each dispatch that changes code, record a snapshot: `BASE=$(scripts/worktree-snapshot -C <repo>)`. It touches neither the index nor history.
- Replace `review-package` with `scripts/worktree-review-package -C <repo> --base <BASE> <workspace>/task-<N>-review.diff <task paths>`, using the task's Files list. For a scoped re-review, use the snapshot taken before that fix round. For the final review, use the snapshot taken before Task 1 and pass no paths.
- Before Task 1, run `git status --short` in each repository and record it in the ledger as the baseline, so reviewers do not attribute those files to a task.
- Completion lines become `Task <N>: complete (<changed files>; <test evidence>; review clean)`.
- Do not stage, commit or push at the end. Report the changed files and let your human partner decide.
