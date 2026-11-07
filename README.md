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
3. A token or quota error moves to the next agent at once, and that agent is skipped until its cooldown ends. Other errors get three attempts.
4. A run succeeds only if the agent exits 0 and the report file ends with a `Status:` line.
5. If every agent fails, the session uses its own subagents, or stops if `host_fallback` says so.
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
| OpenCode | Add `"plugins": ["superpowers@git+https://github.com/obra/superpowers.git"]` to `~/.config/opencode/opencode.json` |
| Cursor | In Agent chat: `/add-plugin superpowers`. Optional if Claude or Codex has superpowers, because the skills then read those files directly |
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

| Agent | As launcher | As worker |
|---|---|---|
| Claude Code | Tested | Tested |
| Codex | Tested | Tested |
| OpenCode | Tested | Tested |
| Cursor | **Not fully tested.** Installed through `~/.agents/skills`. `host_fallback` is unset, so exhaustion blocks | **Untested.** Disabled by default |
| Others | Works if it loads `SKILL.md` and can run shell commands | Add a command template |

## Config

`skills/subagent-driven-development-multi/config/agents.json`:

| Key | Meaning |
|---|---|
| `order` | Dispatch order. The launching agent is removed automatically |
| `host_fallback` | `subagent` uses the launcher's own subagents when all fail. Unlisted hosts block |
| `git_policy` | `no-commit` puts a git guard on external agents' `PATH`. `allow` uses upstream's commit flow |
| `limits` | Run time, stall time, attempts per agent, token cooldown |
| `token_error_patterns` | Regexes checked against the end of a failed run's log |
| `agents.<name>.enabled` | Whether the agent can be used |
| `agents.<name>.command` | Command template. Placeholders: `{model}`, `{effort}`, `{cwd}`, `{workspace}`, `{title}`, `{prompt}` |
| `agents.<name>.models` | Allowed models, or `"all"` |
| `agents.<name>.efforts` | Supported efforts. An unsupported effort skips the agent |
| `agents.<name>.tiers` | Model for `cheap`, `standard`, `capable` |
| `agents.<name>.add_dir_flag`, `optional_dirs` | Extra writable folders, added if they exist |
| `agents.<name>.unset_env_prefixes` | Environment variables removed for this agent |

To add an agent, add an entry with a command template. No code change is needed. An enabled agent needs a `command` and all three tiers.

Per-plan environment variables go in `<workspace>/agent-env.json`, as a JSON object. Do not put secrets there.

## Keeping up with superpowers

Update superpowers the normal way for each agent. On the next run, the executor warns if upstream's skills changed since the last review. After checking that the overrides still apply:

```bash
skills/subagent-driven-development-multi/scripts/agent-router upstream-check --accept
```

## Risks

- **Permissions.** Workers run unattended with write access: `opencode --auto`, `codex -s workspace-write` with network on, `claude --permission-mode acceptEdits` with Bash allowed. Run them only on code you are willing to have changed.
- **The git guard stops mistakes, not hostile agents.** An agent can still call git by its full path.
- **Your code goes to each enabled provider.** Check this is allowed for your project.
- **Token errors are detected by matching text**, and can change with CLI versions. Misdetection wastes attempts or skips a healthy agent.
- **A failed run can leave partial edits.** The next agent is told to inspect them.

## Development

```bash
PYTHONPATH=skills/subagent-driven-development-multi python3 -m unittest discover -s tests -v
ruff check skills install.py
uvx mypy --strict skills/subagent-driven-development-multi/agent_router install.py
```
