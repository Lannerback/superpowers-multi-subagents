Agent rules, all mandatory. They override anything above that conflicts.

1. Execute only the assigned task. Do not change files outside its Files list, fix other issues, or start another task. Report anything else as a concern.
2. Do not dispatch subagents.
3. Ledger: the ledger named at the end of this prompt is read-only for you. Never write `Task <N>:` lines.
4. Git: follow the Git rule at the top of this prompt, which overrides any commit step in the template. If a git command is denied, do not work around it: stop, leave your changes as they are, and name the denied command in your report.
5. If the brief is wrong or unclear, stop and report NEEDS_CONTEXT. Do not guess.
6. Write your full report to the `Report file:` named at the end of this prompt, even if a template says your final message is the report. Any other report named above is input: never overwrite it. Fixers append to their report file, and everyone else replaces it. Its last line must be exactly one of:
   - Implementers and fixers: `Status: DONE`, `Status: DONE_WITH_CONCERNS`, `Status: BLOCKED`, `Status: NEEDS_CONTEXT`
   - Reviewers: `Status: APPROVED`, `Status: CHANGES_REQUIRED`, `Status: NEEDS_CONTEXT`
7. Reviewers keep the template's output format and map its verdict to that last line. Minor and ⚠️ items stay in the report and do not change the status.
   - Task review: `APPROVED` only if spec compliance is ✅, task quality is Approved, and there is no Critical or Important finding. Otherwise `CHANGES_REQUIRED`.
   - Re-review: `APPROVED` only if every finding is ADDRESSED and the fix diff has no new Critical or Important breakage. Otherwise `CHANGES_REQUIRED`.
   - Final review: `APPROVED` only if the answer to "Ready to merge?" is Yes. No and With fixes are `CHANGES_REQUIRED`.

A run without that last line counts as failed, even if the work is complete.
