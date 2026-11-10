# `install.py`

```bash
python3 install.py --host auto
```

`install.py` makes your two skills visible to an agent by creating one symlink per skill in that agent's skills folder. It copies nothing. It installs superpowers only when you pass `--install-superpowers`; otherwise superpowers is installed separately, see the README.

## What it does, step by step

1. Finds the repo's `skills/` folder from its own location, so it works wherever you cloned the repo.
2. Works out the target skills folder for each requested agent (table below).
3. Skips an agent whose config folder does not exist, and says so.
4. Checks that superpowers is installed, the way the router finds it (see [upstream.md](upstream.md)). If it is not, it prints the install commands and exits with code 2 before changing anything. With `--install-superpowers` it first installs it, see [below](#installing-superpowers-with---install-superpowers).
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
| `--install-superpowers` | Install superpowers for the selected agents that lack it (Claude Code and Codex only), then link the skills. Cannot be combined with `--skip-superpowers-check`. Ignored, with a note, by `--uninstall` |
| `--skip-superpowers-check` | Install even when superpowers is not found. For setups the router cannot see, though the router would still need `SUPERPOWERS_SKILLS_DIR` to run |
| `--uninstall` | Remove the links this repo created in the selected targets. Other entries are never touched. Does not check for superpowers |

With none of `--host` or `--target` resolving to a folder, it exits with code 2 and says why.

## Installing superpowers with `--install-superpowers`

The default is to stop. The flag is opt-in because installing superpowers writes third-party code and hooks into your global agent config, which is more than linking two skills; upstream's install has no version pin documented, so "latest" can move past what the overrides were reviewed against; and only two of the four agents can be installed from a script.

```bash
./install.py --host auto --install-superpowers
```

For each selected agent the script does check, install, re-check:

1. If the agent's own plugin cache already holds superpowers, it does nothing (`result=present`). Another agent's copy does not count.
2. Otherwise it prints the exact command, then runs it with no stdin, a 5 minute timeout and no `-y` or `--accept-command`.
3. It looks for the copy again. An install that exits 0 but leaves nothing the router can see is reported as `not-detected`.

| Agent | Scriptable | What it runs |
|---|---|---|
| Claude Code | yes | `claude plugin marketplace add obra/superpowers-marketplace`, then `claude plugin install superpowers@superpowers-marketplace` |
| Codex | yes | `codex plugin marketplace add obra/superpowers`, then `codex plugin add superpowers@superpowers-dev` |
| OpenCode | no | Nothing. Prints: add `superpowers@git+https://github.com/obra/superpowers.git` to the plugins list in `opencode.json` |
| Cursor | no | Nothing. Prints: run `/add-plugin superpowers` in Agent chat |

Each line of the run is one structured line, such as `host=claude result=installed`. The results are `present`, `installed`, `failed`, `not-detected` and `manual`.

- `failed` and `not-detected` stop the script with exit code 2 and no skills are linked.
- `manual` is only informational. If superpowers is found afterwards the script goes on; if not, it prints the manual steps and exits 2.
- Re-running is safe: marketplaces that were already added are accepted by both CLIs, and agents that have superpowers are skipped.
- After a successful install the script compares upstream's files with `config/upstream-lock.json` and prints `upstream changed since last review: <file>` for each difference. This is a warning, never a failure. See [upstream.md](upstream.md).
- `--uninstall` never removes superpowers.

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
| Claude Code | `claude plugin marketplace add obra/superpowers-marketplace` first, then `claude plugin marketplace add Lannerback/superpowers-multi-subagents`, then `claude plugin install superpowers-multi-subagents@superpowers-multi-subagents` | `.claude-plugin/plugin.json` (declares the superpowers dependency) and `.claude-plugin/marketplace.json` |
| Codex | `codex plugin marketplace add Lannerback/superpowers-multi-subagents`, then `codex plugin add superpowers-multi-subagents@superpowers-multi-subagents` | `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json` |
| OpenCode | Add `"superpowers-multi-subagents@git+https://github.com/Lannerback/superpowers-multi-subagents.git"` to `plugins` (2.0.4 or later) or `plugin` (older) in `opencode.json` | `package.json`, `index.js` and `.opencode/plugins/superpowers-multi-subagents.js` |

How each route checks for superpowers:

- Claude Code: the `dependencies` entry in `plugin.json`, plus `allowCrossMarketplaceDependenciesOn` in `marketplace.json`. Claude installs superpowers as a dependency only when the superpowers marketplace is already added. Checked on a clean home folder: without it the plugin installs but fails to load with a message naming the fix; with it, superpowers is installed along with the plugin.
- Codex: no dependency field is known. The skills stop with `superpowers not found` when the router cannot find it.
- OpenCode: the plugin runs `agent-router upstream-path` when it loads. If superpowers is missing it logs a message and registers no skills.

## Things to know

- The links point into the clone. If you move or delete the clone, they break: run `--uninstall` first, move it, and install again.
- Use one route per agent. The symlinks from `install.py` and a plugin install both register the skills, so using both shows each skill twice.
- Both skills must be installed together. `writing-plans-multi-subagents` finds the router in its sibling skill.
- Windows symlinks have not been tested.
- Restart a running agent session after installing, so it re-reads its skills folder.
