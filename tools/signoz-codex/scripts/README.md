# Scripts

Use `./scripts/signoz-codex` as the stable entry point from the project root.

## Entry points

- `signoz-codex`: thin wrapper that execs `signoz_codex.py`
- `signoz_codex.py`: main command dispatcher for stack lifecycle, health checks, and SQL access
- `query_clickhouse.py`: low-level ClickHouse query runner used by `sql` and `sql-read`
- `check_codex_config.py`: validates `~/.codex/config.toml` for the local OTEL setup
- `verify_codex_telemetry.py`: checks recent native Codex telemetry in SigNoz

## SQL modes

- `sql-read`: preferred for ad hoc inspection queries. It accepts inline SQL, `--file`, or stdin, rejects mutating statements, and connects with the read-only ClickHouse user.
- `sql`: use only when you intentionally need write-capable or maintenance-oriented queries.

Examples:

```sh
./scripts/signoz-codex sql-read "SELECT count() FROM signoz_logs.distributed_logs_v2"
./scripts/signoz-codex sql-read --format Vertical "SELECT * FROM signoz_metrics.time_series_v4 LIMIT 3"
cat ./query.sql | ./scripts/signoz-codex sql-read
./scripts/signoz-codex sql "OPTIMIZE TABLE signoz_logs.distributed_logs_v2 FINAL"
```

## Approval model

The private rules in `~/.codex/rules/default.rules` are meant to allow direct `sql-read` and prompt for direct `sql` calls. Those rules target the real script paths, not a shell alias, so Codex can match them without relying on `zsh -ic`.
