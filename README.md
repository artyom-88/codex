# Shareable Codex Home

This repository is a curated, shareable subset of a local Codex home directory.

Everything is private by default. A file is eligible for publishing only if it is:

- reusable across clients or projects
- free of secrets, tokens, auth state, and local machine state
- anonymized enough to share

## Current public set

- `AGENTS.md`
- `.pylintrc`
- `config.example.toml`
- everything under `.github/`
- everything under `.githooks/`
- everything under `instructions/`
- `rules/global.rules`
- everything under `skills/memory-refiner/`

System skills under `skills/.system/` stay private.

## Publish workflow

1. Review the file contents and confirm they are client-agnostic and safe to share.
2. Add the folder or exact path to `.gitignore` if it is not already allowlisted.
3. Stage only the intended paths with `git add <path>`.
4. Review the staged diff with `git diff --cached`.
5. Commit and push only after the staged diff contains no secrets, local state, or project-specific details.

## Shared config template

`config.example.toml` is a sanitized template for sharable Codex defaults.

- Codex loads the live user config from `config.toml`, not from `config.example.toml`.
- Keep machine-specific settings in the private `config.toml`, especially absolute paths, usernames, and `[projects."..."]` trust entries.
- Mirror only safe, generic defaults into `config.example.toml`.

## Pre-commit guard

This repo uses a native Git pre-commit hook from `.githooks/`.

- Install it with `git config core.hooksPath .githooks`
- The hook requires `python3` 3.11 or newer on the machine running it
- The hook prints short phase progress messages to stderr while it runs
- The hook blocks commits unless both checks pass:
- a deterministic scanner over staged paths and staged content
- a non-interactive Codex review of the staged diff
- Commits fail closed if Codex is unavailable, errors, or returns a blocking result
- Regex-based deterministic checks are configured in `.githooks/commit_guard_patterns.toml`
- The hook fails closed if that pattern config is missing, malformed, or contains invalid regexes
- Tune Codex review for large commits with env vars:
- `COMMIT_GUARD_CODEX_TIMEOUT_SECONDS`
- `COMMIT_GUARD_MAX_REVIEW_DIFF_CHARS`
- `COMMIT_GUARD_MAX_REVIEW_DIFF_STAT_CHARS`
- `COMMIT_GUARD_MAX_REVIEW_PATHS`

## GitHub automation

- `.github/workflows/shareable-checks.yml` runs regular CI
- The same workflow also runs `bandit` against tracked Python files for a basic security scan
- `.github/dependabot.yml` keeps GitHub Actions dependencies up to date
- CI runs `pylint` over tracked Python files

## Keep private

Do not publish auth, the live `config.toml`, history, caches, databases, sessions, memories, temp files, shell snapshots, editor metadata, or other runtime state. New files remain ignored until they are explicitly allowlisted.
