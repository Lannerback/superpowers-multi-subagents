# Docs

Back to the [main README](../README.md) for install and config.

## Architecture overview

This project adds two skills on top of [superpowers](https://github.com/obra/superpowers) so each task of a plan can run on an external agent instead of your own session. Superpowers keeps doing the planning and the review; this project only changes who runs each task.

```
 you
  │  ask for a plan
  ▼
 writing-plans-multi-subagents ──► runs upstream writing-plans, then adds
  │                                 a Route (tier, effort, repo) to each task
  │  plan file
  ▼
 subagent-driven-development-multi ──► runs upstream subagent-driven-development,
  │                                    but sends every dispatch to the router
  ▼
 agent-router run
  │   reads config/agents.json (your copy in ~/.config/... wins)
  │   picks the first agent that is enabled, installed and not out of tokens
  │   puts the git guard first on the worker's PATH
  ▼
 opencode / codex / claude / cursor / aider      (the worker, one process per task)
  │   writes its report file, ends it with a Status: line
  ▼
 agent-router: checks the report and the git state, appends an Agent-run line
 to upstream's ledger (.superpowers/sdd/<plan>/progress.md)
  │
  ├─ ok ───────────────► upstream's review loop continues
  └─ all agents failed ─► exit 75: your session's own subagents take the task
```

The pieces:

- **Two skills**, in `skills/`. They are instructions for the agent, not code. Each tells it to run the matching upstream skill and apply a short list of overrides.
- **The router**, in `skills/subagent-driven-development-multi/agent_router/`. Plain Python with no dependencies. It builds the worker's command, runs it, enforces time limits, reads the result from the report file, and records every attempt.
- **Config**, `config/agents.json`: which agents exist, their order, models, efforts and git policy.
- **The git guard**, a `git` wrapper that blocks history-changing commands in the worker. See [git-policy.md](git-policy.md).
- **Upstream**, found at run time in the plugin folders of your agents and never copied. The ledger, the review loop and the prompt templates are upstream's. See [upstream.md](upstream.md).
- **Install**, `install.py` for symlinks, plus plugin and marketplace manifests for Claude Code, Codex and OpenCode. See [install.md](install.md).

## Files in this folder

| File | Read it to learn |
|---|---|
| [files.md](files.md) | What every file in the repo is for, including each Python module |
| [upstream.md](upstream.md) | What upstream superpowers is, how it is found, and how drift is detected |
| [install.md](install.md) | What `install.py` does, every option, and the marketplace routes |
| [git-policy.md](git-policy.md) | The three git policies, the guard, grants and rollback |
| [license.md](license.md) | The MIT license, the credits to upstream, and what you may do with this project |

Config properties, with examples, are in the [README's Config section](../README.md#config).
