---
name: writing-plans-multi-subagents
description: Use when the user wants an implementation plan whose tasks will run on external agents such as opencode, codex, claude or cursor, or asks for a multi-agent or multi-subagent plan
---

# Writing Plans for Multiple Agents

Announce: "I'm using writing-plans-multi-subagents to create the plan."

Use the superpowers `writing-plans` skill and follow all of it. If your harness does not list it, run `"$ROUTER" upstream-path` and read `<that path>/writing-plans/SKILL.md`. Only these overrides apply.

`SKILL_DIR` is this skill's directory, as an absolute path. `ROUTER` is `$SKILL_DIR/../subagent-driven-development-multi/scripts/agent-router`. The two skills install together: if that file is missing, stop and tell your human partner to install both skills together (`python3 install.py --host auto` in the repo).

## Overrides

**Header.** Replace the "REQUIRED SUB-SKILL" line with:

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development-multi to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Route line.** Directly under each task heading, add:

`**Route:** tier=<cheap|standard|capable> effort=<low|medium|high|xhigh|max> repo=<absolute repository path>`

- `cheap`: the plan text contains the complete change, 1-2 files.
- `standard`: multi-file work or integration.
- `capable`: design judgment or broad codebase understanding.
- `effort`: scale to how much reasoning the task needs. Most tasks are `medium`.
- A task the orchestrator must run itself, such as one writing to a real external system, uses `Route: orchestrator`.

**Git policy.** Run `"$ROUTER" git-policy`.

- `no-commit`: replace every commit step with "Summarize changed files and verification evidence", and add this Global Constraint: "Git: no agent stages, commits, pushes, resets, checks out, or stashes. Review uses working-tree diffs."
- `commit-guarded`: keep upstream's commit steps, but write each as `git add <the task's exact files>` then `git commit`, never `git add .`. Add this Global Constraint: "Git: agents may add explicit paths and commit. Reset, rebase, push, amend, checkout, switch, restore, clean, stash, merge, cherry-pick, revert, pull, rm, mv, and branch or tag changes are denied unless the task's Git-allow line names the exact command."
- If a task truly needs one denied command, such as `push origin <branch>`, add under its Route line `**Git-allow:** <git arguments, exactly as they will be typed, without the leading git>`, one line per command. Say in the handoff that the executor will ask the user before granting each. Never write Git-allow for a destructive command such as `reset --hard`, force push or branch deletion unless the user asked for it in this conversation.
- `allow`: follow upstream unchanged.

**Leave out of the plan:** agent names, model IDs, fallback order, retry rules, and runner scripts. They live in the executor's config, so plans stay valid when the config changes.

**Per-plan environment.** If agents need environment variables, such as an emulator host, add a setup step that writes them as a JSON object to `<workspace>/agent-env.json`. Never put secrets there.

**Handoff.** Recommend `subagent-driven-development-multi`. Offer the upstream methods as alternatives.
