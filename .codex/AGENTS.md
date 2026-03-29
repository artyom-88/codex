# Repo-Local Codex Guidance

## Shareable Local Skills

- When adding a new local skill intended to be shareable, update `.gitignore`, `skills/INDEX.md`, and `README.md` together.
- Add an explicit `!/skills/<skill-name>/` allowlist rule before staging shareable skill files.
- Keep this publishing workflow repo-local. Do not move it into the global root `AGENTS.md`.

## Project Artifacts

- Treat `.codex/code-review/`, `.codex/plans/`, `.codex/diff/`, and `.codex/debug/` as generated repo artifacts, not instruction layers.
- Treat `.codex/reports/` as generated repo artifacts, not an instruction layer.
- Store generated threat models, security reviews, and similar one-off reports under `.codex/reports/`, not directly under `.codex/`.
