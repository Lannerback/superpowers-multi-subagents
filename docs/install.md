# `install.py`

```bash
python3 install.py --host auto
```

`install.py` makes your two skills visible to an agent by creating one symlink per skill in that agent's skills folder. It copies nothing and installs nothing else (superpowers itself is installed separately, see the README).

## What it does, step by step

1. Finds the repo's `skills/` folder from its own location, so it works wherever you cloned the repo.
2. Works out the target skills folder for each requested agent (table below).
3. Skips an agent whose config folder does not exist, and says so.
4. Creates the target folder if needed.
5. For each folder under `skills/` that contains a `SKILL.md`, creates `<target>/<skill-name>` as a symlink to it. A link that already points at this repo's skill is left alone, so a second run does nothing.
6. Prints the path of every link it creates (or removes, with `--uninstall`).

It refuses to replace anything it did not create: if `<target>/<skill-name>` is a real folder, or a link to somewhere else, it stops with `FileExistsError` naming the path. Move that item away first.

## Options

| Option | Meaning |
|---|---|
| `--host auto` | Every agent whose config folder exists |
| `--host claude codex opencode cursor` | Only these agents, any combination. Each one whose config folder is missing is skipped with `skipped <host>: ~/<folder> not found` |
| `--force-host` | Install for the named agents even if their config folder is missing. Does not widen `auto` |
| `--target PATH` | Any other skills folder, for an agent not in the table. Can be combined with `--host` |
| `--uninstall` | Remove the links this repo created in the selected targets. Other entries are never touched |

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

## Things to know

- The links point into the clone. If you move or delete the clone, they break: run `--uninstall` first, move it, and install again.
- Both skills must be installed together. `writing-plans-multi-subagents` finds the router in its sibling skill.
- Windows symlinks have not been tested.
- Restart a running agent session after installing, so it re-reads its skills folder.
