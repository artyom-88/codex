# Repo-Local Codex Guidance

## Tool Guidance

- `.codex/instructions/tools/signoz.md` contains SigNoz stack workflow guidance for `tools/signoz-codex/` plus shared SigNoz conventions. Load only when working on SigNoz-related tooling.

## Shareable Local Skills

- When adding a new local skill intended to be shareable, update `.gitignore`, `skills/INDEX.md`, and `README.md` together.
- Add an explicit `!/skills/<skill-name>/` allowlist rule before staging shareable skill files.
- Keep this publishing workflow repo-local. Do not move it into the global root `AGENTS.md`.

## Project Artifacts

- Treat `.codex/code-review/`, `.codex/plans/`, `.codex/diff/`, and `.codex/debug/` as generated repo artifacts, not instruction layers.
- Treat `.codex/reports/` as generated repo artifacts, not an instruction layer.
- Store generated threat models, security reviews, and similar one-off reports under `.codex/reports/`, not directly under `.codex/`.

## Skill Helpers

- When equivalent helper scripts exist both in `skills/` and under `plugins/cache/`, prefer the canonical `skills/` path.
- Avoid plugin-cache paths in commands unless the cached copy is the only available implementation.

## Skill Helpers

- When equivalent helper scripts exist both in `skills/` and under `plugins/cache/`, prefer the canonical `skills/` path.
- Avoid plugin-cache paths in commands unless the cached copy is the only available implementation.
