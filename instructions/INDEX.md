# Instructions Index

This file tracks the available instruction sets for Codex, organized by category. These should be lazy-loaded by referencing them only when their specific context is required.

## Workflow

These live under `instructions/workflow/` and are for general execution and communication logic.

- [communication.md](workflow/communication.md): Progress-update and response-structure guidance. (Load only when the task involves substantive interactive work.)
- [core.md](workflow/core.md): General execution guidance for inspecting context, making focused changes, and verifying with evidence. (Load only when general workflow guidance is needed.)
- [github.md](workflow/github.md): GitHub branch and pull request workflow defaults. (Load only when GitHub workflow work is relevant.)
- [safety.md](workflow/safety.md): Guidance for destructive actions, user-owned changes, and remote-affecting steps. (Load only when the task has operational risk.)
- [skills.md](workflow/skills.md): Skill provenance and maintenance guidance. (Load only when skill work is relevant.)

## Languages

These live under `instructions/languages/` and are for language-specific guidance.

- [python.md](languages/python.md): Python coding guidance for analyzer-friendly patterns, test fixtures, and targeted verification. (Load only when Python files or Python CI/tooling are involved.)

## Tasks

These live under `instructions/tasks/` and are for specific task-oriented guidance.

- [debugging.md](tasks/debugging.md): Debugging guidance for reproducing failures and isolating root causes. (Load only for debugging work.)
- [planning.md](tasks/planning.md): Planning guidance for turning goals into implementation-ready steps. (Load only when planning is the primary task.)
- [review.md](tasks/review.md): Review guidance focused on findings, regressions, and verification gaps. (Load only for review requests.)
