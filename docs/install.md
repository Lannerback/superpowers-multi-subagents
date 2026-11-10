# `install.py`

```bash
python3 install.py --host auto
```

`install.py` makes your two skills visible to an agent by creating one symlink per skill in that agent's skills folder. It copies nothing and installs nothing else (superpowers itself is installed separately, see the README).

## What it does, step by step

1. Finds the repo's `skills/` folder from its own location, so it works wherever you cloned the repo.
2. Works out the target skills folder for each requested agent (table below).
3. Skips an agent whose config folder does not exist, and says so.
4. Checks that superpowers is installed, the way the router finds it (see [upstream.md](upstream.md)). If it is not, it prints the install commands and exits with code 2 before changing anything.
5. Creates the target folder if needed.
6. For each folder under `skills/` that contains a `SKILL.md`, creates `<target>/<skill-name>` as a symlink to it. A link that already points at this repo's skill is left alone, so a second run does nothing.
7. Prints the path of every link it creates (or removes, with `--uninstall`).

It refuses to replace anything it did not create: if `<target>/<skill-name>` is a real folder, or a link to somewhere else, it stops with `FileExistsError` naming the path. Move that item away first.

## Options

| Option | Meaning |
|---|---|
| `--host auto` | Every agent whose config folder exists |
| `--host claude codex opencode cursor` | Only these agents, any combination. Each one whose config folder is missing is skipped with `skipped <host>: ~/<folder> not found` |
| `--force-host` | Install for the named agents even if their config folder is missing. Does not widen `auto` |
| `--target PATH` | Any other skills folder, for an agent not in the table. Can be combined with `--host` |
| `--skip-superpowers-check` | Install even when superpowers is not found. For setups the router cannot see, though the router would still need `SUPERPOWERS_SKILLS_DIR` to run |
| `--uninstall` | Remove the links this repo created in the selected targets. Other entries are never touched. Does not check for superpowers |

With none of `--host` or `--target` resolving to a folder, it exits with code 2 and says why.

## Where each agent's links go

| Agent | Detected by | Skills folder |
|---|---|---|
| `claude` | `~/.claude` | `~/.claude/skills` |
| `codex` | `~/.codex` | `~/.agents/skills` |
| `opencode` | `~/.config/opencode` | `~/.config/opencode/skills` |
| `cursor` | `~/.cursor` | `~/.agents/skills` (shared with Codex, linked once) |

## Examples

```bash
python3 install.py --host auto                      # everything that is set up
python3 install.py --host claude opencode           # just these two
python3 install.py --host codex --force-host        # Codex not run yet: create the folder anyway
python3 install.py --target ~/my-agent/skills       # any other agent
python3 install.py --host auto --uninstall          # remove the links again
```

## Installing from a marketplace instead

The repo is also a plugin for each agent, so no script is needed. Superpowers must already be installed in every case.

| Agent | Commands | Files that make it work |
|---|---|---|
| Claude Code | `claude plugin marketplace add Lannerback/superpowers-multi-subagents`, then `claude plugin install superpowers-multi-subagents@superpowers-multi-subagents` | `.claude-plugin/plugin.json` (declares the superpowers dependency) and `.claude-plugin/marketplace.json` |
| Codex | `codex plugin marketplace add Lannerback/superpowers-multi-subagents`, then `codex plugin add superpowers-multi-subagents@superpowers-multi-subagents` | `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json` |
| OpenCode | Add `"superpowers-multi-subagents@git+https://github.com/Lannerback/superpowers-multi-subagents.git"` to `plugins` (2.0.4 or later) or `plugin` (older) in `opencode.json` | `package.json`, `index.js` and `.opencode/plugins/superpowers-multi-subagents.js` |

How each route checks for superpowers:

- Claude Code: the `dependencies` entry in `plugin.json`, plus `allowCrossMarketplaceDependenciesOn` in `marketplace.json`, which lets Claude Code resolve it from the superpowers marketplace.
- Codex: no dependency field is known. The skills stop with `superpowers not found` when the router cannot find it.
- OpenCode: the plugin runs `agent-router upstream-path` when it loads. If superpowers is missing it logs a message and registers no skills.

## Things to know

- The links point into the clone. If you move or delete the clone, they break: run `--uninstall` first, move it, and install again.
- Use one route per agent. The symlinks from `install.py` and a plugin install both register the skills, so using both shows each skill twice.
- Both skills must be installed together. `writing-plans-multi-subagents` finds the router in its sibling skill.
- Windows symlinks have not been tested.
- Restart a running agent session after installing, so it re-reads its skills folder.
