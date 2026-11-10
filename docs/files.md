# What every file is for

```
.
├── README.md                          install, config, risks
├── LICENSE                            MIT license
├── install.py                         symlinks the skills into each agent, checks superpowers
├── package.json, index.js             OpenCode plugin entry
├── .opencode/plugins/                 the OpenCode plugin
├── .claude-plugin/                    Claude Code plugin and marketplace manifests
├── .codex-plugin/, .agents/plugins/   Codex plugin and marketplace manifests
├── docs/                              this folder
├── skills/
│   ├── writing-plans-multi-subagents/
│   │   └── SKILL.md                   plan skill: adds tier, effort and git rules to upstream's writing-plans
│   └── subagent-driven-development-multi/
│       ├── SKILL.md                   executor skill: sends every dispatch through the router
│       ├── references/agent-contract.md
│       ├── config/agents.json
│       ├── config/upstream-lock.json
│       ├── scripts/                   agent-router, git-guard/git, worktree-snapshot, worktree-review-package
│       └── agent_router/              the Python router
└── tests/                             unit and end-to-end tests
```

Not in git: `.superpowers/` (per-plan workspaces and ledgers), `.plans/`, caches. See `.gitignore`.

## Skills

| File | Purpose |
|---|---|
| `skills/writing-plans-multi-subagents/SKILL.md` | Tells the agent to run upstream `writing-plans`, then add a `Route:` line (tier, effort, repo) to every task, apply the git policy to the plan's commit steps, and optional `Git-allow:` lines |
| `skills/subagent-driven-development-multi/SKILL.md` | Tells the agent to run upstream `subagent-driven-development` but replace every subagent dispatch with `agent-router run`. Holds the exit-code table, the ledger rules, and the `commit-guarded` and `no-commit` procedures |
| `references/agent-contract.md` | Rules appended to every prompt sent to an external agent: stay in the task, no subagents, never write `Task <N>:` ledger lines, follow the git rule, write the report file ending in an exact `Status:` line |

## Config

| File | Purpose |
|---|---|
| `config/agents.json` | Shipped router config. A copy at `~/.config/superpowers-multi-subagents/agents.json` replaces it. Properties are explained in the README's Config section |
| `config/upstream-lock.json` | SHA-256 of each upstream superpowers file this repo's overrides were written against. See [upstream.md](upstream.md) |

## Scripts

| File | Purpose |
|---|---|
| `scripts/agent-router` | Launcher: puts the skill folder on `sys.path` and calls `agent_router.cli.main` |
| `scripts/git-guard/git` | A `git` wrapper put first on the worker's `PATH`. Denies history-changing commands in the protected repo. See [git-policy.md](git-policy.md) |
| `scripts/worktree-snapshot` | Prints a tree id of the working tree, untracked files included, using a temporary index. Used by `no-commit` so a resume has a base to diff from |
| `scripts/worktree-review-package` | Writes the stat and diff from a base tree to the working tree into one file for a reviewer. Used by `no-commit` instead of upstream's `review-package` |

## The router, `skills/subagent-driven-development-multi/agent_router/`

| Module | Purpose |
|---|---|
| `__init__.py` | Marks the package |
| `cli.py` | Command line. Subcommands: `run`, `doctor`, `git-policy`, `upstream-path`, `upstream-check`. Turns errors into `Status: ERROR` and exit code 2 |
| `router.py` | `AgentRouter.dispatch`: walks the agents in `order`, skips disabled, exhausted and uninstalled ones, runs each, checks the git policy afterwards, records the ledger, and falls back to the host subagent (exit 75) when all fail |
| `config.py` | Loads and validates `agents.json`. User copy wins over the shipped one |
| `models.py` | Frozen dataclasses: `AgentConfig`, `Limits`, `RouterConfig`, `DispatchRequest`, `DispatchResult`, and the constants for efforts, tiers and policies |
| `command_builder.py` | Fills `{model}`, `{effort}`, `{cwd}`, `{workspace}`, `{title}`, `{prompt}` into an agent's command, appends existing `optional_dirs`, and builds the worker's environment (strips launcher variables, puts the guard first on `PATH`) |
| `process_runner.py` | Starts the worker, writes its log, enforces `run_seconds` and `stall_seconds`, and turns SIGTERM, SIGHUP and Ctrl-C into a clean shutdown. Outcome reasons: `exited`, `stalled`, `timeout`, `not_found` |
| `outcomes.py` | Reads the worker's result from the last line of the report file (never the log) and decides whether a failed run was a token or login error by matching `token_error_patterns` against the end of the log |
| `exhaustion_state.py` | Remembers, in `<workspace>/router-state.json`, which agents ran out of tokens and until when |
| `ledger.py` | Appends `Agent-run` lines to the plan's `progress.md` |
| `git_state.py` | Reads git state: top level, a fingerprint of HEAD and the index (`no-commit`), and branch plus HEAD with an ancestry check (`commit-guarded`) |
| `git_grants.py` | Validates grants and writes them to `<workspace>/git-grants.txt` for the guard |
| `prompts.py` | Builds the worker's prompt: git rule, your prompt body, retry note, report file and ledger paths |
| `doctor.py` | Checks that each enabled agent's command is on `PATH`, and with `--smoke` sends it a one-line prompt |
| `upstream.py` | Finds the installed superpowers skills folder, and compares watched upstream files with the lock |

## Install and packaging

| File | Purpose |
|---|---|
| `install.py` | See [install.md](install.md) |
| `.claude-plugin/plugin.json` | Claude Code plugin manifest. Declares superpowers as a dependency |
| `.claude-plugin/marketplace.json` | Claude Code marketplace listing this plugin, and allows the superpowers dependency to come from its marketplace |
| `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json` | Codex plugin manifest and marketplace listing |
| `package.json`, `index.js` | OpenCode package metadata and the directory-form entry for OpenCode 2.x |
| `.opencode/plugins/superpowers-multi-subagents.js` | The OpenCode plugin: registers the skills, only when superpowers is found |
| `LICENSE`, [license.md](license.md) | The MIT license and what it means for this project |

## Tests, `tests/`

One `unittest` file per area: `test_config`, `test_router`, `test_runtime` (process runner, outcomes, environment), `test_cli` (end-to-end, including the real git guard), `test_git_guard`, `test_git_grants`, `test_doctor`, `test_upstream`, `test_review_package`, `test_install`, `test_skills` (checks the skill texts), `test_packaging` (manifests, license, README structure, OpenCode plugin). Run them with the command in the README's Development section.
