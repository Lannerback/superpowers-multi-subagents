# Upstream: what it is and how it works

**Upstream** is [obra/superpowers](https://github.com/obra/superpowers) (MIT, by Jesse Vincent): a skill library with `writing-plans` and `subagent-driven-development`. This repo does not copy those skills. Its two skills tell the agent to run the upstream one and then apply a short list of overrides.

| Upstream skill | This repo's skill | What the override changes |
|---|---|---|
| `writing-plans` | `writing-plans-multi-subagents` | Adds a `Route:` line to each task, applies the git policy to commit steps, adds `Git-allow:` |
| `subagent-driven-development` | `subagent-driven-development-multi` | Sends every dispatch through `agent-router run`, adds the `Agent-run` ledger lines, adds the git policies |

Because the overrides are small, an upstream update reaches you without touching this repo. The ledger, the review loop and the prompt templates all stay upstream's.

## Finding upstream

The router looks for the installed superpowers `skills` folder in this order:

1. The `SUPERPOWERS_SKILLS_DIR` environment variable, if set.
2. The newest version found under your home folder in:
   - `.claude/plugins/cache/*/superpowers/*/skills`
   - `.codex/plugins/cache/*/superpowers/*/skills`
   - `.cache/opencode/npm/*/*/node_modules/superpowers/skills`
   - `.cache/opencode/packages/superpowers@*/*/*/*/node_modules/superpowers/skills`

If none exists, the router stops with `superpowers not found: install it or set SUPERPOWERS_SKILLS_DIR`. Print the folder it chose:

```bash
skills/subagent-driven-development-multi/scripts/agent-router upstream-path
```

Cursor's own plugin folder is not searched. For Cursor, or any other agent, set `SUPERPOWERS_SKILLS_DIR`.

## Drift: knowing when upstream changed

`config/upstream-lock.json` stores the SHA-256 of each upstream file the overrides depend on (`WATCHED` in `agent_router/upstream.py`): the two `SKILL.md` files, the three prompt templates, the references, the `sdd-workspace` and `task-brief` scripts, and `code-reviewer.md`.

```bash
skills/subagent-driven-development-multi/scripts/agent-router upstream-check
```

For every watched file whose hash differs from the lock, or that is missing, it prints `upstream changed since last review: <file>`. It never fails and changes nothing. The executor skill runs it at the start of every plan: if a changed file makes one of the overrides wrong, the agent stops and tells you; otherwise it mentions the drift once and continues.

After you have read the changed files and confirmed the overrides still apply, record the new state:

```bash
skills/subagent-driven-development-multi/scripts/agent-router upstream-check --accept
```

`--accept` rewrites `upstream-lock.json` from the installed copy. It refuses if a watched file is missing. Commit the new lock, or the warning returns on the next run.

## What stays upstream's

- The workspace layout, `.superpowers/sdd/<plan>/`, created by upstream's `sdd-workspace`.
- The ledger, `progress.md`, and its `Task <N>:` lines. The router only appends `Agent-run` lines, which upstream's resume rule ignores.
- Task briefs and prompt bodies. The router appends `references/agent-contract.md` to a prompt, plus the report file, the ledger path and the git rule.
