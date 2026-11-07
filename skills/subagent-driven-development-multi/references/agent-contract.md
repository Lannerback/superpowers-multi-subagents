Agent rules, all mandatory. They override anything above that conflicts.

1. Execute only the assigned task. Do not change files outside its Files list, fix other issues, or start another task. Report anything else as a concern.
2. Do not dispatch subagents.
3. Ledger: `<workspace>/progress.md` is read-only for you. Never write `Task <N>:` lines.
4. Git: if a git command is denied, do not work around it. Leave your changes in the working tree and do not mention commits in your report.
5. If the brief is wrong or unclear, stop and report NEEDS_CONTEXT. Do not guess.
6. Write your full report to the report file named above. Its last line must be exactly one of:
   - Implementers and fixers: `Status: DONE`, `Status: DONE_WITH_CONCERNS`, `Status: BLOCKED`, `Status: NEEDS_CONTEXT`
   - Reviewers: `Status: APPROVED`, `Status: CHANGES_REQUIRED`

A run without that last line counts as failed, even if the work is complete.
