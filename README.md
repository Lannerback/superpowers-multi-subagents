# superpowers-multi-subagents

Two skills that extend [superpowers](https://github.com/obra/superpowers) so plan tasks run on external agents, and the session you launch from saves its tokens for last.

| Skill | Purpose |
|---|---|
| `writing-plans-multi-subagents` | Runs superpowers `writing-plans`, and adds a tier and effort to each task |
| `subagent-driven-development-multi` | Runs superpowers `subagent-driven-development`, and sends every dispatch through the agent router |

Both defer to upstream, so superpowers updates keep reaching you. Upstream's ledger, review loop and prompts stay in charge.

## How it works

1. The session you launch from coordinates. It never implements, unless a task says so.
2. For each dispatch, the router walks `order` in the config, skipping disabled agents and the agent you are running in.
3. If an agent's CLI quits with an error that matches its `token_error_patterns`, such as a login or quota failure, the router moves to the next agent at once and skips that agent until its cooldown ends. Other failures get three attempts.
4. A run succeeds only if the agent exits 0 and the report file ends with a `Status:` line.
5. If every agent fails, the session uses its own subagents, or stops if `host_fallback` says so. Bad input, such as a wrong `--cwd`, prints `Status: ERROR` and exits 2. It never falls back.
6. Every attempt is an `Agent-run` line in the plan's ledger, `.superpowers/sdd/<plan>/progress.md`.

## Requirements

- Python 3.10+, git, bash. macOS or Linux.
- Superpowers installed for each agent you launch from. See below.
- The CLI of each agent you enable, signed in.

## Install

**1. Install superpowers.** Upstream installs separately per agent:

| Agent | Command |
|---|---|
| Claude Code | `claude plugin marketplace add obra/superpowers-marketplace`, then `claude plugin install superpowers@superpowers-marketplace` |
| Codex | `codex plugin marketplace add obra/superpowers`, then `codex plugin add superpowers@superpowers-dev` |
| OpenCode | Add `"plugins": ["superpowers@git+https://github.com/obra/superpowers.git"]` to `~/.config/opencode/opencode.json`. The router finds it in `~/.cache/opencode` after OpenCode has loaded the plugin. If not, set `SUPERPOWERS_SKILLS_DIR` to its `skills` folder |
| Cursor | In Agent chat: `/add-plugin superpowers`. The router does not look in Cursor's own plugin folder, so if Claude, Codex or OpenCode has no copy, also set `SUPERPOWERS_SKILLS_DIR` to a `skills` folder |
| Others | See upstream's README, then set `SUPERPOWERS_SKILLS_DIR` to its `skills` folder |

Claude's official marketplace can lag: it was at 7.0.0 when upstream was at 7.0.2.

**2. Install these skills**, as symlinks, so `git pull` updates them:

```bash
git clone https://github.com/Lannerback/superpowers-multi-subagents.git
cd superpowers-multi-subagents
./install.py --host claude codex opencode cursor
```

Hosts: `claude`, `codex` and `cursor` (both use `~/.agents/skills`), `opencode`. For any other agent that loads `SKILL.md` folders:

```bash
./install.py --target ~/path/to/its/skills
```

**3. Configure agents.** Copy the shipped config and edit it. Your copy overrides the shipped one and stays out of git:

```bash
mkdir -p ~/.config/superpowers-multi-subagents
cp skills/subagent-driven-development-multi/config/agents.json ~/.config/superpowers-multi-subagents/agents.json
```

**4. Check it:**

```bash
skills/subagent-driven-development-multi/scripts/agent-router doctor --host claude --smoke
```

`--smoke` sends a one-line prompt to each enabled agent, which costs a few tokens.

## Agent support

This table states what was actually run, on macOS only. No complete plan has yet run through implementer, review, fix and final review on any agent, and the host-subagent fallback has not run in a real session. Only effort `low` ran on real CLIs.

| Agent | As launcher | As worker |
|---|---|---|
| Claude Code | **Discovery not checked.** The CLI was logged out, so no session could confirm it sees the skills. `doctor` and `--host claude` routing ran from another session | **No real model run.** Logged out, it is recorded as `token_error` on the first attempt, with no retries. CLI 2.1.301 was also run against a local mock API, which proved the git guard denies `git clean` |
| Codex | Skill discovery question, and `doctor --smoke` | `doctor --smoke`, and one real dispatch that wrote a file. Git guard proven on CLI 0.146 with a local mock API and `codex sandbox` |
| OpenCode | Skill discovery question, and `doctor --smoke` | `doctor --smoke`, and real dispatches that wrote files. Git guard denials seen on real runs |
| Cursor | **Discovery not checked.** The CLI asked for authentication. Installed through `~/.agents/skills`. `--host cursor` routing ran. `host_fallback` is unset, so exhaustion blocks | **Never run.** Disabled by default |
| Others | Not run. It should work if it loads `SKILL.md` and can run shell commands | Not run. Add a command template |

## Config

`skills/subagent-driven-development-multi/config/agents.json`:

| Key | Meaning |
|---|---|
| `order` | Dispatch order. The launching agent is removed automatically. Every enabled agent must be listed |
| `host_fallback` | `subagent` uses the launcher's own subagents when all fail. Unlisted hosts block |
| `git_policy` | `no-commit` gives external agents a best-effort git guard, tells them not to commit, and blocks a dispatch that changes HEAD or the index. `allow` uses upstream's commit flow |
| `limits` | Run time, stall time, attempts per agent, token cooldown. A run counts as stalled when its log, the ledger and the report file all stop growing |
| `host_session_env_prefixes` | Variables of the launching session, removed for every worker |
| `agents.<name>.enabled` | Whether the agent can be used |
| `agents.<name>.command` | Command template. Placeholders: `{model}`, `{effort}`, `{cwd}`, `{workspace}`, `{title}`, `{prompt}` |
| `agents.<name>.models` | Allowed models, or `"all"` |
| `agents.<name>.efforts` | Supported efforts. An unsupported effort skips the agent |
| `agents.<name>.tiers` | Model for `cheap`, `standard`, `capable` |
| `agents.<name>.add_dir_flag`, `optional_dirs` | Extra writable folders, added if they exist |
| `agents.<name>.unset_env_prefixes` | Further variables removed for this agent, such as Claude's nesting markers |
| `agents.<name>.token_error_patterns` | Regexes for this CLI's own login, model and quota messages. Checked only when it exits non-zero, against the end of its log |
| `agents.<name>.guard_env_file_var` | For a CLI that sources a file before each tool call: the variable naming that file, so it can reapply the git guard |

To add an agent, add an entry with a command template and list its name in `order`. No code change is needed. An enabled agent needs a `command` and all three tiers, and one missing from `order` is rejected at load. Without `token_error_patterns`, its token failures get the normal three attempts and no cooldown.

Per-plan environment variables go in `<workspace>/agent-env.json`, as a JSON object. Do not put secrets there.

## Keeping up with superpowers

Update superpowers the normal way for each agent. On the next run, the executor warns if upstream's skills changed since the last review. After checking that the overrides still apply:

```bash
skills/subagent-driven-development-multi/scripts/agent-router upstream-check --accept
```

## Risks

- **Permissions.** Workers run unattended with write access: `opencode --auto`, `codex -s workspace-write` with network on, `claude --permission-mode acceptEdits` with Bash allowed. Run them only on code you are willing to have changed.
- **The git guard is best-effort.** It is a `git` wrapper on `PATH`, so it stops mistakes, not hostile agents: a full path, an alias, or a shell that rebuilds `PATH` gets past it. It was proven only on macOS, on OpenCode, on Codex 0.146 with `allow_login_shell=false`, and on Claude Code 2.1.301 against a mock API. Other versions and Linux are unproven. The router's check catches a changed HEAD or index after the run, but not `git clean` or a stash of unstaged work. Host subagents have no guard, only the written rule.
- **Workers can read your environment.** The launching session's variables are removed, using `host_session_env_prefixes`. Everything else stays, including provider API keys such as `ANTHROPIC_API_KEY`, because an agent may need its own. Every enabled worker can read them.
- **Your code goes to each enabled provider.** Check this is allowed for your project.
- **Token errors are detected by matching text**, and can change with CLI versions. Misdetection wastes attempts or skips a healthy agent.
- **A failed run can leave partial edits.** The next agent, including a host subagent, is told to inspect them.
- **Stopping the router.** SIGTERM, SIGHUP and Ctrl-C take the worker down. SIGKILL cannot, so a worker can outlive it.

## Development

```bash
PYTHONPATH=skills/subagent-driven-development-multi python3 -m unittest discover -s tests -v
ruff check skills install.py
uvx mypy --strict skills/subagent-driven-development-multi/agent_router install.py
```
