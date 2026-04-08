# Shareable Codex Home

This repository contains a public, reusable subset of a local Codex home directory.
It is meant to be copied from, adapted, and used as reference material for Codex setup,
repo guidance, sharable skills, and supporting tooling.

## What is included

- `AGENTS.md` and `.codex/AGENTS.md` for global and repo-local guidance examples
- `config.example.toml` as a safe baseline config template
- `instructions/` and `.codex/instructions/` for reusable workflow and tool guidance
- `rules/global.rules` for shared rule examples
- selected local skills such as `skills/code-review/` and `skills/memory-refiner/`
- `tools/signoz-codex/` for SigNoz-oriented Codex telemetry tooling
- `.githooks/` and `.github/` for guardrails and CI automation

## How to use it

- Start from `config.example.toml` and copy only the defaults you want into your private live `config.toml`
- Reuse guidance from `AGENTS.md`, `instructions/`, or `.codex/AGENTS.md` as templates for your own Codex setup
- Explore `tools/signoz-codex/` if you want OTEL or SigNoz support for Codex activity
- Copy skills selectively rather than treating this repo as an all-or-nothing Codex home

## Privacy boundary

This repo intentionally excludes live auth, runtime history, sessions, caches, databases,
memories, shell snapshots, and other machine-specific state.

`config.example.toml` is public-safe by design. Keep personal paths, usernames, auth state,
and `[projects."..."]` trust entries in your private live `config.toml`, not in the example.

## For contributors

Keep GitHub-facing docs user-oriented. Repo-maintainer publishing workflow, allowlist rules,
and example-file conventions live in `.codex/AGENTS.md` and `.codex/instructions/workflow/sharing.md`.
