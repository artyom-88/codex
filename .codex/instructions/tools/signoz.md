# SigNoz Tool Guidance

Use this note only when working on SigNoz-related tooling in this repo.

## Shared Basics

- Prefer a repo-provided helper entry point over raw `docker compose ... clickhouse-client` commands when the project already exposes one.
- Prefer helper-driven SQL access for inspection queries instead of hand-built ClickHouse commands.
- Keep reusable stack helpers under a project `scripts/` directory.

## Signoz Codex

Use this section for work under `tools/signoz-codex/`.

- For user-facing operational checks on this machine, use the `.zshrc` command through interactive zsh: `/bin/zsh -ic 'signoz-codex "$@"' signoz-codex status|verify|sql-read ...`.
- For `sql-read` with SQL arguments, use the argv-preserving `"$@"` form; do not embed SQL in the `-ic` script string because execpolicy matches the script token exactly.
- Use `./scripts/signoz-codex ...` when validating the public repo entry point or writing reusable docs/tests inside `tools/signoz-codex`.
- Keep tracked `tools/signoz-codex` scripts/docs minikube-agnostic. Put machine-specific runtime integration under git-ignored `tools/signoz-codex/local/`.
- Use `./scripts/signoz-codex sql-read` for read-only inspection queries.
- Use `./scripts/signoz-codex sql` only for intentional maintenance or write-capable queries.
- Prefer Python for new helper tooling in this subproject unless there is a clear reason not to.
