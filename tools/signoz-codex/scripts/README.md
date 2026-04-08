# Scripts

Use `./scripts/signoz-codex` as the stable entry point from the project root.

## Entry points

- `signoz-codex`: thin wrapper that execs `signoz_codex.py`
- `signoz_codex.py`: main command dispatcher for stack lifecycle, health checks, and SQL access
- `query_clickhouse.py`: low-level ClickHouse query runner used by `sql` and `sql-read`
- `check_codex_config.py`: validates `~/.codex/config.toml` for the selected stack host and OTLP endpoint
- `verify_codex_telemetry.py`: checks recent native Codex telemetry in SigNoz
- `project_resource_attrs.py`: resolves Git-or-Codex-project metadata and merges it into `OTEL_RESOURCE_ATTRIBUTES` for shell hooks
- `project_resource_attrs_hook.zsh`: lightweight `zsh` hook that calls `project_resource_attrs.py` on startup and directory changes

The scripts use the active Docker context by default. Local contexts run directly from the repo checkout. Remote contexts are supported too, but stack startup needs a remote asset-sync command because the compose file bind-mounts project config files. With the default loopback bind, remote contexts keep advertising `localhost` so you can pair them with an SSH tunnel; if you want direct remote-host access, set both `SIGNOZ_CODEX_BIND_ADDR=0.0.0.0` and `SIGNOZ_CODEX_STACK_HOST=<remote-host>`.

On first use, the helper renders secret-bearing runtime files into `local/generated/`. That directory stays git-ignored. If you do not provide ClickHouse passwords yourself, the helper also creates `local/generated/clickhouse.env` with generated credentials and reuses them for future runs.

## SQL modes

- `sql-read`: preferred for ad hoc inspection queries. It accepts inline SQL, `--file`, or stdin, rejects mutating statements, and authenticates with the read-only ClickHouse user.
- `sql`: use only when you intentionally need write-capable or maintenance-oriented queries. It authenticates with the writable ClickHouse account used by the helper stack.

Examples:

```sh
./scripts/signoz-codex sql-read "SELECT count() FROM signoz_logs.distributed_logs_v2"
./scripts/signoz-codex sql-read --format Vertical "SELECT * FROM signoz_metrics.time_series_v4 LIMIT 3"
cat ./query.sql | ./scripts/signoz-codex sql-read
./scripts/signoz-codex sql "OPTIMIZE TABLE signoz_logs.distributed_logs_v2 FINAL"
```

## Runtime overrides

Optional runtime env vars:

- `DOCKER_CONTEXT` to select a non-default Docker context
- `SIGNOZ_CODEX_ENGINE_MODE=auto|local|remote`
- `SIGNOZ_CODEX_CLICKHOUSE_WRITE_PASSWORD` to pin the writable ClickHouse password instead of using a generated local one
- `SIGNOZ_CODEX_CLICKHOUSE_READONLY_PASSWORD` to pin the read-only ClickHouse password instead of using a generated local one
- `SIGNOZ_CODEX_REMOTE_ASSETS_ROOT` to choose the target asset directory on the remote engine host
- `SIGNOZ_CODEX_REMOTE_ASSET_SYNC_CMD` to run a local sync command before remote compose startup
- `SIGNOZ_CODEX_STACK_HOST` to override the advertised UI and OTLP host
- `SIGNOZ_CODEX_BIND_ADDR` to override the Docker bind address for published UI/OTLP ports
- `SIGNOZ_CODEX_OTLP_ENDPOINT` to override the expected Codex OTLP endpoint directly

`SIGNOZ_CODEX_BIND_ADDR` defaults to `127.0.0.1` so local telemetry endpoints are not reachable from other hosts. Use `0.0.0.0` only when you intentionally need remote/shared-host access.

Recommended activation flow:

1. Copy `examples/runtime.env.example` to `local/runtime.env`
2. Uncomment only the variables you need
3. Run `./scripts/signoz-codex ...`

Example:

```sh
mkdir -p ./local
cp ./examples/runtime.env.example ./local/runtime.env
```

The example env file is documentation plus a reusable template. The `signoz-codex` Python entrypoint auto-loads `local/runtime.env` if it exists, and `local/` is git-ignored. Rendered secret-bearing files land under `local/generated/`.

## Native project metadata

The recommended native setup is a small `zsh` hook that calls `project_resource_attrs.py` on shell startup and directory changes. The hook keeps plain `codex` usage intact while making these resource attributes available to native metrics, traces, and logs:

- `project.name`
- `project.path`
- `vcs.repository.name` when the current directory is inside a Git repo

Why it belongs in `~/.zshrc`:

- the hook runs once when the shell starts and again whenever `PWD` changes
- that keeps `OTEL_RESOURCE_ATTRIBUTES` aligned with the repo you are actually working in
- without it, `codex` still works, but project-aware dimensions in SigNoz may be missing or stale

Suggested minimal `~/.zshrc` line after replacing `/path/to/signoz-codex` with your actual checkout path:

```zsh
[[ -f "/path/to/signoz-codex/scripts/project_resource_attrs_hook.zsh" ]] && source "/path/to/signoz-codex/scripts/project_resource_attrs_hook.zsh"
```
