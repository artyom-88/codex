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
- Prefer the minimum number of extra files needed to do the work well.
- When a repo needs a local `AGENTS.md`, keep it limited to repo-specific overrides, discovery metadata, and local workflow notes. Do not repeat global defaults.

## Scope Precedence

- Prefer the narrowest applicable instruction scope: project-local `.codex/` over repo-local `AGENTS.md` over global `~/.codex`.
- If guidance is duplicated across scopes, remove the broader duplicate instead of maintaining both copies.

## Instruction Layout

- `instructions/workflow/` contains universal workflow guidance.
- `instructions/tasks/` contains task-mode guidance such as review, debugging, or planning.
- Add more subfolders only when there is a clear need for more specialized guidance.
