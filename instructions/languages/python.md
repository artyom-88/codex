# Python Guidance

Load this file when editing tracked `.py` files, Python CI workflows, or Python lint/security failures.

- Keep Python changes small and analyzer-friendly; prefer refactoring repeated command or credential setup into a helper before adding suppressions.
- In tests, avoid placeholder values and keyword assignments that look like real secrets to static analyzers; prefer helper builders, properties, or computed attribute names when the value is only a fixture.
- Scope `# nosec` and linter disables narrowly with the exact rule id, and only after a direct refactor would be worse.
- When the same Python command construction appears in more than one place, extract a shared helper instead of duplicating argv fragments in scripts and tests.
- After Python edits, rerun the smallest relevant checks first, then the repo-required gates:
  - targeted `unittest`
  - targeted `pylint`
  - targeted `bandit` when security heuristics are involved
- Do not duplicate repo-specific tool settings here; keep those in CI config and lint config.
