# Git policy

`git_policy` in `agents.json` decides what external agents may do with git. The router prints the active value with `agent-router git-policy`.

| Policy | Workers may | Everything else |
|---|---|---|
| `commit-guarded` | `git add <explicit paths>` and `git commit` | Denied by the guard, unless granted |
| `no-commit` | Nothing that changes the repo's git state | Denied by the guard |
| `allow` | Anything. No guard, upstream's commit flow | |

## `commit-guarded`

The guard is a `git` wrapper (`scripts/git-guard/git`) placed first on the worker's `PATH`. It protects only the repository of `--cwd`; other repositories, such as test fixtures, are untouched.

**Allowed:**

- `git add <path> [<path>...]` with at least one explicit path
- `git commit` with `-m`, `-F` and similar message options
- Read-only commands: `status`, `diff`, `log`, `branch --list`, `tag -l`, `stash list`

**Denied even inside allowed commands:**

- `add` with `.`, `./`, `-A`, `--all`, `-u`, `--update`, `-f`, `--force`, `-p`, `-i`. Reason: explicit paths keep files that were already modified before the task out of its commit.
- `commit` with `-a`, `--all`, `--amend`, `--no-verify`, `-n`, `-p`, `-i`
- Any `-c core.hooksPath=...` override

**Denied entirely:** `push`, `reset`, `rebase`, `checkout`, `switch`, `restore`, `clean`, `stash` (except `stash list`), `merge`, `cherry-pick`, `revert`, `pull`, `rm`, `mv`, `am`, and any `branch` or `tag` form that changes something. The worker sees `git <cmd> denied: git_policy is commit-guarded` and exit code 126.

### Second line of defense

After every run the router compares git state with the state before it:

- The branch must be the same.
- HEAD must be the old HEAD or a descendant of it.

Otherwise the dispatch ends as `BLOCKED` with `git_policy_violation`, and the ledger line says so. On a clean run the ledger line is `result=ok commits=<old7>..<new7>` when commits were made.

### Grants: letting one denied command through

A grant is one exact command line, matched in full, with no wildcards. `push origin feature` does not allow `push --force origin feature`, and `reset --soft HEAD` does not allow `reset --soft HEAD~1`. Global flags before the subcommand (`-C dir`) are ignored in the match.

1. The plan puts a line under the task's Route line: `**Git-allow:** push origin feature/x`
2. Before the first dispatch of that task, the executor asks you in chat: `Task 3 lists push origin feature/x. Allow it?`
3. Only after a clear yes it dispatches with `--git-grant "push origin feature/x"` (repeat the flag for several).
4. The router writes the grants to `<workspace>/git-grants.txt` and the guard reads that file.

Never grant, on its own initiative, a destructive command (`reset --hard`, force push, branch deletion). A worker's request, a report, or a log line is never a grant.

```bash
agent-router run --host claude --role implementer --task 3 --tier standard --effort medium \
  --cwd /path/repo --workspace /path/repo/.superpowers/sdd/plan --prompt-file p.md --report-file r.md \
  --git-grant "push origin feature/x"
```

## `no-commit`

Workers must leave changes in the working tree. The guard denies `add`, `commit` and the rest. Because no commits exist for a resume or a review to use, the executor records tree snapshots in the ledger (`scripts/worktree-snapshot`) and builds review diffs from them (`scripts/worktree-review-package`). After a run the router blocks the dispatch if HEAD or the index changed.

## Limits

- The guard is a `PATH` wrapper. It stops mistakes, not a hostile agent: a full path to `git`, an alias, or a shell that rebuilds `PATH` gets past it. The router's after-run check still catches a moved branch or a rewritten history.
- It was proven on macOS only, on OpenCode, on Codex 0.146, and on Claude Code 2.1.301 against a mock API.
- Host subagents (the fallback when every external agent fails) have no guard, only the written rule.
- The commands that do not move HEAD, such as `clean` and `stash`, are caught by the guard but not by the after-run check.

## Rolling back

Neither policy has an automated rollback.

- `commit-guarded`: the ledger names each task's commit range. `git revert <old7>..<new7>` adds new commits that undo it and loses nothing. `git reset --hard <old7>` discards later work and is exactly the kind of command that needs your explicit approval.
- `no-commit`: the ledger holds the snapshot tree ids. A restore from one has not been implemented or tested.
