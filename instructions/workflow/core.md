# Core Workflow

- Inspect the repository, environment, and current state before proposing changes.
- Prefer small, direct changes over speculative rewrites.
- Reuse existing project patterns before introducing new ones.
- When changing execpolicy rules, verify the exact command shape with `codex execpolicy check` before claiming a rule works or editing adjacent rules.
- Verify important claims with local evidence whenever possible.
- When blocked, explain the concrete blocker and the next most reasonable path.

## Command Form

- Prefer direct executable rules and direct command forms for real commands.
- Use exact `zsh -ic` or `zsh -lc` script-string forms only when the command is shell-only or alias-only.
- For shell aliases/functions that need arguments, prefer `zsh -ic 'command "$@"' command arg...` so execpolicy can match stable argv tokens.
- Do not present shell-wrapper forms as if they were the intended command shape for ordinary executables.

## Commit Scope

- When the user asks to `commit`, default to committing only the task-relevant files. Broaden the scope only when the user explicitly says `all`, `everything`, or names additional files.
