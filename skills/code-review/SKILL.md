---
name: code-review
description: Review git changes in the current repository or a specified branch, pull request, merge request, commit, or diff range. Use when the user asks to review code, review changes, analyze a branch, inspect a PR or MR, assess regression risk, or identify correctness, API, data-flow, security, performance, or test-coverage issues.
---

# Code Review

## Overview

Perform a risk-first review of the most relevant git change set. Prefer concrete findings over summaries, use local repository evidence first, and pull PR or MR context only when it materially improves the review.

## Inputs

- Review target: current branch, explicit branch, PR, MR, commit, range, or working tree changes
- Base branch if the user specifies one
- Optional remote context from `gh` or `glab`

## Workflow

1. Resolve the review scope.
- Prefer the exact target named by the user.
- Otherwise discover the repository's default branch and review the current branch against its merge base with that branch.
- If there are no branch commits to review, fall back to staged or unstaged local changes.
- For GitHub or GitLab review requests, load remote context only when the CLI is available and authenticated.

2. Gather the smallest useful evidence set.
- Start with file lists, diff stats, and the scoped diff before reading full files.
- Inspect surrounding code only for changed or high-risk areas.
- Trace affected entry points, downstream calls, persistence, external integrations, and changed model or schema shapes.
- Create repo-local `.codex/code-review/` when needed and plan to export the final review there by default.

3. Analyze by impact.
- Prioritize correctness, behavioral regressions, security, data integrity, and compatibility.
- Check API contracts, model or DTO shape changes, migrations, config changes, and operational impact.
- Review test coverage for every material change and call out missing cases.
- Treat style or maintainability as secondary unless they create real risk.

4. Use structured reasoning when the diff is broad or cross-cutting.
- For multi-file or ambiguous changes, use sequential thinking to map affected flows before writing findings.
- Identify the user-visible entry point, layer transitions, changed components, and important data transformations.

5. Write the review.
- Put findings first, ordered by severity and user impact.
- Include specific file references and explain the concrete failure mode or risk.
- Suggest the missing test, guard, or safer design when it is clear.
- If there are no findings, say so directly and mention residual risk or verification gaps.

6. Export the review artifact.
- Unless the user explicitly asks for chat-only output, write the final review to repo-local `.codex/code-review/review-<target-slug>.md`.
- Derive `<target-slug>` from the review target by lowercasing it, replacing `/`, `\\`, whitespace, and other path separators with `-`, removing other unsafe filename characters, and collapsing repeated `-`.
- If there is no stable target name, fall back to `head-<short-sha>`.
- Mention the saved path in the response.
- Save extra artifacts such as diff patches only when the user asks for them or they materially help with a large review.

7. State verification boundaries.
- Say whether the review covered local diff only, full files, tests, and remote comments.
- If remote auth or network access blocked PR or MR context, state that and continue with the local review.

## Lazy References

- Load `references/review-sources.md` when choosing the right diff, base branch, host CLI flow, or artifact path.
- Load `references/review-output.md` when writing the saved review artifact, PR-ready markdown, or a consistent report shape.
