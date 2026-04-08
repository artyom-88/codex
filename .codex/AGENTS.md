# Repo-Local Codex Guidance

## Public Surface

- Keep `README.md` GitHub-facing and user-oriented.
- When editing public templates or example files, prefer descriptive comments over removing or disabling safe example settings.
- Use `.codex/instructions/workflow/sharing.md` for repo publishing rules and public/private boundary decisions.

## Tool Guidance

- `.codex/instructions/tools/signoz.md` contains SigNoz stack workflow guidance for `tools/signoz-codex/` plus shared SigNoz conventions. Load only when working on SigNoz-related tooling.
- `.codex/instructions/workflow/sharing.md` contains repo publishing workflow and public/private boundary guidance. Load only when changing tracked shareable content, allowlists, or GitHub-facing docs.

## Shareable Local Skills

- Keep shareability workflow repo-local. Do not move it into the global root `AGENTS.md`.

## Project Artifacts

- Treat `.codex/code-review/`, `.codex/plans/`, `.codex/diff/`, and `.codex/debug/` as generated repo artifacts, not instruction layers.
- Treat `.codex/reports/` as generated repo artifacts, not an instruction layer.
- Store generated threat models, security reviews, and similar one-off reports under `.codex/reports/`, not directly under `.codex/`.

## Skill Helpers

- When equivalent helper scripts exist both in `skills/` and under `plugins/cache/`, prefer the canonical `skills/` path.
- Avoid plugin-cache paths in commands unless the cached copy is the only available implementation.
