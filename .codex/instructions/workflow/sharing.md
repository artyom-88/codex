# Shareable Repo Workflow

Use this note when changing the tracked public surface of this repository.

## Public docs

- Keep `README.md` GitHub-facing and user-oriented.
- Move repo-maintainer process details, allowlist rules, and publish workflow notes into repo-local guidance instead of the public README.

## Public examples

- Keep public example files functional and copyable by default.
- Do not disable otherwise useful example settings just to mark them optional.
- Explain optional or environment-specific blocks with short descriptions instead.
- Keep private-only values out of examples, but keep safe defaults in place when they improve usability.

## Allowlists and tracked surface

- This repo is deny-by-default in `.gitignore`; new paths stay private until explicitly allowlisted.
- When making a repo-local instruction folder shareable, update `.gitignore` so the intended subtree is unignored.
- When adding a new shareable local skill, update `.gitignore`, `skills/INDEX.md`, and `README.md` together.
- Add an explicit `!/skills/<skill-name>/` allowlist rule before staging a new shareable skill.

## Publish checks

- Publish only content that is reusable across clients or projects.
- Exclude secrets, auth state, local runtime state, machine-specific paths, and other user-private data.
- Stage explicit paths, review the staged diff, and confirm the public surface is intentional before committing.

## Private by default

- Keep the live `config.toml`, auth, history, caches, databases, sessions, memories, temp files, shell snapshots, and editor metadata out of Git.
- Keep `[projects."..."]` trust entries private unless there is a compelling sanitized example use case.
