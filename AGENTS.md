# Global Codex Instructions

Use this file for global routing and defaults, not detailed task guidance.

## Core

- Promote new global guidance only when it is supported by repeated evidence across sessions or repositories; do not turn one-off incidents into permanent memory.

## Security Default

- Prefer secure-by-default choices when requirements are ambiguous.
- Escalate scrutiny for secrets, credentials, authentication, permissions, external network access, and destructive operations.
- Do not normalize insecure shortcuts in shared guidance; if a faster path weakens security, call out the tradeoff explicitly.

## Loading Policy

- Keep this root file small.
- Load extra instruction files only when they are relevant to the task.
- Do not bulk-load instruction folders.
- Treat file references in this root file as a lazy-load index, not as instructions to load by default.
- Prefer the minimum number of extra files needed to do the work well.
- When a repo needs a local `AGENTS.md`, keep it limited to repo-specific overrides, discovery metadata, and local workflow notes. Do not repeat global defaults.

## Project Artifacts

- Prefer storing repo-specific Codex artifacts under the repo-local `.codex/` directory instead of `/tmp`.
- Use stable subfolders when helpful: `.codex/code-review/` for PR or review snapshots, `.codex/debug/` for repro notes and logs, `.codex/diff/` for saved patches or comparisons, `.codex/plans/` for deferred plans, and `.codex/rules/` for project approval rules.
- Name artifacts descriptively and include the branch name or PR/MR number when relevant.
- Under `.codex/tools/`, keep operational helpers in topic-specific subfolders rather than the tools root, for example `.codex/tools/minikube/`.
- When a tool subfolder contains operational scripts, launch agents, or recovery commands, add a short `README.md` in that subfolder explaining the setup and any external files involved.

## Scope Precedence

- Prefer the narrowest applicable instruction scope: project-local `.codex/` over repo-local `AGENTS.md` over global `~/.codex`.
- If guidance is duplicated across scopes, remove the broader duplicate instead of maintaining both copies.
- For `.codex/rules/*.rules`, matching rules are merged across scopes and the most restrictive decision wins; local rules do not override a broader `prompt` or `forbidden` rule.

## Instruction Layout

- The entries below are an index of available guidance. Do not load them by default.
- `instructions/workflow/core.md` contains general execution guidance for inspecting context, making focused changes, and verifying with evidence. Load only when general workflow guidance is needed.
- `instructions/workflow/communication.md` contains progress-update and response-structure guidance. Load only when the task involves substantive interactive work.
- `instructions/workflow/github.md` contains GitHub branch and pull request workflow defaults. Load only when GitHub workflow work is relevant.
- `instructions/workflow/safety.md` contains guidance for destructive actions, user-owned changes, and remote-affecting steps. Load only when the task has operational risk.
- `instructions/workflow/skills.md` contains skill provenance and maintenance guidance. Load only when skill work is relevant.
- `instructions/tasks/debugging.md` contains debugging guidance for reproducing failures and isolating root causes. Load only for debugging work.
- `instructions/tasks/planning.md` contains planning guidance for turning goals into implementation-ready steps. Load only when planning is the primary task.
- `instructions/tasks/review.md` contains review guidance focused on findings, regressions, and verification gaps. Load only for review requests.
- Add more subfolders only when there is a clear need for more specialized guidance.
