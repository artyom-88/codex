# Review Output

Load this file when writing the saved review artifact, PR-ready markdown, or a consistent review structure.

## Default Structure

Keep findings primary. Summaries are secondary.

```md
Code Review

## Findings
1. Severity: short title
   - Why it matters
   - Evidence: file reference
   - Missing test or safer fix

## Open Questions
- Question or assumption that materially affects the review

## Verification
- What was reviewed
- What was not verified

## Change Summary
- Optional short recap only after findings
```

## No-Finding Case

If no issues are found, say so directly and keep the rest short:

```md
Code Review

## Findings
No findings.

## Residual Risk
- Any area that was not fully verified

## Verification
- Diff reviewed
- Tests not run
```

## PR or MR Notes

When the user wants a comment or description-ready note, compress it:

```md
## Review Summary
- Main risk area
- Required fix or follow-up
- Coverage gap
```

## Saved Reports

When the skill is explicitly invoked, export the final review by default to repo-local `.codex/code-review/review-<target-slug>.md`.
Also export the exact reviewed diff by default to repo-local `.codex/diff/diff-<target-slug>.patch` as a unified patch.
Compute `<target-slug>` with the slugging rule from `references/review-sources.md`, and fall back to `head-<short-sha>` when needed.
Skip the file only when the user explicitly asks for chat-only output.
Mention both saved paths in the response so the user can find them immediately.
