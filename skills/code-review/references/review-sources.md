# Review Sources

Load this file when the review target, diff base, or remote host context is unclear.

## Source Selection Order

1. Use the exact target the user names.
2. Otherwise discover the repository's default branch and review the current branch against that merge base.
3. If there is no branch delta, review staged and unstaged changes.
4. If the user asks about a PR or MR, prefer host metadata in addition to the local diff.

## Local Git Commands

Use `git --no-pager` for review commands so output stays compact.

### Current Branch vs Default Branch

- `git --no-pager branch --show-current`
- `git --no-pager status --short`
- Discover the remote to use. Prefer the current branch upstream remote; otherwise prefer `origin`.
- Resolve the default branch ref from that remote, for example with `git --no-pager symbolic-ref refs/remotes/<remote>/HEAD`.
- `git --no-pager merge-base <remote>/<default-branch> HEAD`
- `git --no-pager diff --stat <merge-base>...HEAD`
- `git --no-pager diff <merge-base>...HEAD`

If the remote default branch ref is unavailable, prefer host metadata when `gh` or `glab` is available. Fall back to local `main` only when no authoritative default-branch source is available.

### Staged or Unstaged Changes

- `git --no-pager diff --stat`
- `git --no-pager diff`
- `git --no-pager diff --cached --stat`
- `git --no-pager diff --cached`

### Commit or Range Review

- `git --no-pager show --stat <commit>`
- `git --no-pager show <commit>`
- `git --no-pager diff --stat <base>..<head>`
- `git --no-pager diff <base>..<head>`

## Remote Review Context

Use remote context when the user asks about a PR or MR, comments matter, or the base branch is unclear. Do not block the review on remote access unless the user explicitly asks for hosted-review context.

### GitHub

- `gh auth status`
- `gh pr view --json number,title,baseRefName,headRefName,url`
- `gh pr view <number> --comments`
- `gh pr diff <number>`

### GitLab

- `glab auth status`
- `glab mr view <number> --comments`
- `glab mr diff <number>`

If the host CLI is unavailable, unauthenticated, or blocked by sandboxing, say so and continue with the local diff.

## Artifact Paths

Prefer repo-local `.codex/code-review/` for review artifacts. Create the directory when missing.

- Derive `<target-slug>` before writing files: lowercase the review target, replace `/`, `\\`, whitespace, and other path separators with `-`, remove remaining unsafe filename characters, and collapse repeated `-`. If there is no stable target name, use `head-<short-sha>`.
- Diff artifact: `.codex/code-review/diff-<target-slug>.patch`
- Review artifact: `.codex/code-review/review-<target-slug>.md`

Write the review artifact by default when the skill is explicitly invoked, unless the user asks for chat-only output.
Use descriptive names. Include the branch name, PR number, or ticket identifier when available. Overwrite the same review path on reruns unless the user asks to preserve history.
