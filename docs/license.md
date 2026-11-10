# License and credits

This project is MIT licensed, Copyright (c) 2026 Adriano D'Aguanno. See [LICENSE](../LICENSE).

It is an extension of [obra/superpowers](https://github.com/obra/superpowers), which is MIT licensed, Copyright (c) 2025 Jesse Vincent. This page explains what that means in practice. It is general information, not legal advice.

## What MIT lets you do

Use, copy, modify, merge, publish, distribute, sublicense and sell the software, for any purpose, with no fee and no permission needed. There is one condition: **the copyright notice and the license text must come with every copy or substantial portion of the software.**

The software comes without warranty. The authors are not liable for what it does.

## Where the notice lives, and why

| Place | Why it is there |
|---|---|
| `LICENSE` at the repo root | It is the notice MIT requires. The marketplace plugin root is the repo root, so every plugin copy, clone and fork includes it |
| `license` field in `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json` and `package.json` | Marketplaces and package tools show the license before anyone installs |
| "Credits and license" in the [README](../README.md#credits-and-license) | Tells users which project this builds on |
| Your own copyright line | When you fork or change this project, add `Copyright (c) <year> <you>` under the existing one. Never remove the existing line |

## What this project owes upstream

Nothing is copied from superpowers. The repo tracks none of its files, and `config/upstream-lock.json` holds hashes only. The skills call the installed copy at run time (see [upstream.md](upstream.md)).

Because no upstream text is copied, MIT's notice condition is not triggered for upstream's code. Credit is still given, because this project does not work without it.

If you ever copy upstream text into this repo:

1. Keep upstream's MIT notice with that file, or put it in a `THIRD_PARTY_NOTICES` file.
2. Check how much you copied. Compare against the installed upstream skills folder; long identical passages mean copying.

## Using, changing and sharing this project

- **Use it** on any project, including commercial ones. Nothing is owed.
- **Change it** freely. Keep `LICENSE` and the credits.
- **Share it**, as a fork, a marketplace plugin or a zip. Keep `LICENSE` in the shared copy.
- **Do not bundle superpowers** in a copy you share. Tell people to install it themselves, as this project does. Bundling it would make you redistribute upstream's files, which then need its notice.

## Names

MIT does not license names or logos. "superpowers" is the name of the upstream project. This project is not affiliated with or endorsed by superpowers or its author, and the README says so. Keep that line in forks.

## Not shipped here

- superpowers itself, installed separately for each agent.
- The agent CLIs (OpenCode, Codex, Claude Code, Cursor, aider). Each has its own terms.
