# Core Workflow

- Inspect the repository, environment, and current state before proposing changes.
- Prefer small, direct changes over speculative rewrites.
- Reuse existing project patterns before introducing new ones.
- When changing execpolicy rules, verify the exact command shape with `codex execpolicy check` before claiming a rule works or editing adjacent rules.
- Prefer direct executable rules for real commands; use exact `zsh -ic` or `zsh -lc` script-string rules only when the command is shell-only or alias-only.
- For shell aliases/functions that need arguments, prefer `zsh -ic 'command "$@"' command arg...` so execpolicy can match stable argv tokens.
- Verify important claims with local evidence whenever possible.
- When blocked, explain the concrete blocker and the next most reasonable path.
