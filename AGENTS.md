# Global Codex Instructions

Apply these defaults across all projects.

## Core

- Ground yourself in the actual environment before making claims or proposing changes.
- Prefer existing project conventions, tools, and workflows over generic defaults.
- Ask only when the answer cannot be discovered locally or when product intent or tradeoffs matter.
- Be concise by default. Add detail only when the task or risk level requires it.
- Keep facts, assumptions, and recommendations clearly separated.
- Avoid destructive actions unless the user explicitly asks for them.
- Promote new global guidance only when it is supported by repeated evidence across sessions or repositories; do not turn one-off incidents into permanent memory.

## Loading Policy

- Keep this root file small.
- Load extra instruction files only when they are clearly relevant to the task.
- Do not bulk-load instruction folders.
- Treat file references in this root file as a lazy-load index, not a default read list.
- Prefer the minimum number of extra files needed to do the work well.
- When a repo needs a local `AGENTS.md`, keep it limited to repo-specific overrides, discovery metadata, and local workflow notes. Do not repeat global defaults.

## Scope Precedence

- Prefer the narrowest applicable instruction scope: project-local `.codex/` over repo-local `AGENTS.md` over global `~/.codex`.
- If guidance is duplicated across scopes, remove the broader duplicate instead of maintaining both copies.

## Instruction Layout

- The entries below are an index of available guidance. Do not load them by default; load only the specific file or files that are relevant to the current task.
- `instructions/workflow/core.md` contains general execution guidance for inspecting context, making focused changes, and verifying with evidence. Load only when general workflow guidance is needed.
- `instructions/workflow/communication.md` contains progress-update and response-structure guidance. Load only when the task involves substantive interactive work.
- `instructions/workflow/safety.md` contains guidance for destructive actions, user-owned changes, and remote-affecting steps. Load only when the task has operational risk.
- `instructions/workflow/skills.md` contains skill provenance and maintenance guidance. Load only when skill work is relevant.
- `instructions/tasks/debugging.md` contains debugging guidance for reproducing failures and isolating root causes. Load only for debugging work.
- `instructions/tasks/planning.md` contains planning guidance for turning goals into implementation-ready steps. Load only when planning is the primary task.
- `instructions/tasks/review.md` contains review guidance focused on findings, regressions, and verification gaps. Load only for review requests.
- Add more subfolders only when there is a clear need for more specialized guidance.
