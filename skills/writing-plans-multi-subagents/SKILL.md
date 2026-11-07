---
name: writing-plans-multi-subagents
description: Use when the user wants an implementation plan whose tasks will run on external agents such as opencode, codex, claude or cursor, or asks for a multi-agent or multi-subagent plan
---

# Writing Plans for Multiple Agents

Announce: "I'm using writing-plans-multi-subagents to create the plan."

Use the superpowers `writing-plans` skill and follow all of it. If your harness does not list it, run `../subagent-driven-development-multi/scripts/agent-router upstream-path` from this skill's directory and read `<that path>/writing-plans/SKILL.md`. Only these overrides apply.

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

**Git policy.** Run `../subagent-driven-development-multi/scripts/agent-router git-policy` from this skill's directory. If it prints `no-commit`, replace every commit step with "Summarize changed files and verification evidence", and add this Global Constraint: "Git: no agent stages, commits, pushes, resets, checks out, or stashes. Review uses working-tree diffs."

**Leave out of the plan:** agent names, model IDs, fallback order, retry rules, and runner scripts. They live in the executor's config, so plans stay valid when the config changes.

**Per-plan environment.** If agents need environment variables, such as an emulator host, add a setup step that writes them as a JSON object to `<workspace>/agent-env.json`. Never put secrets there.

**Handoff.** Recommend `subagent-driven-development-multi`. Offer the upstream methods as alternatives.
