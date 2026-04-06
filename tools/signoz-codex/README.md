# SigNoz Codex Stack

Reusable SigNoz + OpenTelemetry stack for inspecting native Codex telemetry.

## What This Project Covers

- Native Codex OTEL data sent to a SigNoz collector managed by this project
- A helper stack with ClickHouse, SigNoz, and the OTEL collector
- A primary native dashboard for Codex OTEL metrics

Use a single entry point for operations:
- `./scripts/signoz-codex <command>`

Script-level details live in:
- `scripts/README.md`

Native Codex telemetry is best explored through the native dashboard plus SigNoz's built-in Services, Traces, and Logs views. Import `dashboards/codex-native-dashboard.json` first.

## Quick Start

1. Make sure Docker and `docker compose` work for your active Docker context.
2. Validate your Codex OTEL config:
   `./scripts/signoz-codex check-config`
3. Start the stack:
   `./scripts/signoz-codex start`
4. Print the current stack endpoints:
   `./scripts/signoz-codex status`
5. Open the reported SigNoz UI endpoint. For local Docker and the minikube localhost-forwarding profile, that is usually `http://localhost:8105`.
6. Import the primary dashboard from:
   `dashboards/codex-native-dashboard.json`
7. Merge the example OTEL settings from:
   `examples/codex-otel.example.toml`
   into `~/.codex/config.toml`
8. Start a fresh Codex session and generate activity.
9. Verify native telemetry:
   `./scripts/signoz-codex verify`

If the selected Docker context is a minikube-backed remote engine, rerunning `./scripts/signoz-codex start` is safe and refreshes the synced guest-side bind-mounted assets before reporting status.

## Ports

- SigNoz UI: `8105`
- OTLP gRPC: `5317`
- OTLP HTTP: `5318`

These ports intentionally differ from the existing Claude-focused stack so both projects can coexist on one machine.

## Docker Runtime Model

The helper uses the active Docker context by default.

- Local Docker context: bind mounts stay local and the advertised stack host defaults to `localhost`
- Remote Docker context: the helper inspects the selected context and reports the reachable stack host based on runtime settings
- Minikube remote context: supported through a dedicated minikube asset-sync adapter, while user-facing endpoints can still stay on `localhost` if your minikube tooling forwards them there

Optional runtime overrides live in:
- `examples/runtime.env.example`

The main controls are:

- `DOCKER_CONTEXT` to choose a non-default Docker context
- `SIGNOZ_CODEX_ENGINE_MODE=auto|local|remote|minikube`
- `SIGNOZ_CODEX_REMOTE_ASSET_STRATEGY=auto|none|minikube-sync`
- `SIGNOZ_CODEX_STACK_HOST` to override the advertised UI/OTLP host
- `SIGNOZ_CODEX_OTLP_ENDPOINT` to override the expected Codex OTLP endpoint directly

Generic remote Docker engines are supported for inspection commands, but starting the stack requires either a local engine or a supported remote asset strategy. Today the supported remote asset strategy is minikube sync.

## Minikube Integration

Minikube can still be your central local Docker infrastructure. The helper will auto-detect common minikube-style contexts such as `minikube` or `minikube-*` and use the minikube asset-sync adapter automatically.

If your minikube profile name is not inferable from the Docker context name, set:

- `MINIKUBE_PROFILE=<profile>`

If you also keep localhost port forwarding outside this repo, the user-facing endpoints can stay on:

- `http://localhost:8105`
- `localhost:5317`
- `http://localhost:5318`

## Helper Commands

- `./scripts/signoz-codex start`
- `./scripts/signoz-codex start --force`
- `./scripts/signoz-codex stop`
- `./scripts/signoz-codex restart`
- `./scripts/signoz-codex status`
- `./scripts/signoz-codex logs`
- `./scripts/signoz-codex logs otel-collector`
- `./scripts/signoz-codex check-config`
- `./scripts/signoz-codex health`
- `./scripts/signoz-codex verify`
- `./scripts/signoz-codex doctor`
- `./scripts/signoz-codex config`
- `./scripts/signoz-codex sql-read "SELECT count() FROM signoz_logs.distributed_logs_v2"`
- `./scripts/signoz-codex sql "OPTIMIZE TABLE signoz_logs.distributed_logs_v2 FINAL"`

## ClickHouse Queries

Use the single entry point instead of the full `docker compose ... clickhouse-client` command:

- `./scripts/signoz-codex sql-read "SELECT count() FROM signoz_logs.distributed_logs_v2"`
- `./scripts/signoz-codex sql-read --format Vertical "SELECT attributes_string['event.name'], count() FROM signoz_logs.distributed_logs_v2 GROUP BY 1 ORDER BY count() DESC LIMIT 10"`
- `./scripts/signoz-codex sql-read --file ./query.sql`
- `cat ./query.sql | ./scripts/signoz-codex sql-read`

Use `sql` only when you intentionally need a non-read-only session for DDL, maintenance, or writes. `sql-read` rejects mutating statements before execution and connects with a dedicated read-only ClickHouse user.

If you are using your shell alias, the same commands become:

- `signoz-codex sql-read "SELECT count() FROM signoz_logs.distributed_logs_v2"`
- `signoz-codex sql-read --format Vertical "SELECT * FROM signoz_metrics.time_series_v4 LIMIT 3"`

## Logs Configuration

Native Codex logs are already enabled. The main decision is whether prompt text should be redacted:

- `log_user_prompt = false`: `codex.user_prompt` events are still exported, but the `prompt` attribute is stored as `[REDACTED]`
- `log_user_prompt = true`: raw prompt text is exported to SigNoz logs

The collector also enriches Codex logs with a synthesized `body` when the original body is empty. Typical examples are:

- `codex.tool_result tool=exec_command success=true`
- `codex.websocket_event kind=response.function_call_arguments.delta`
- `codex.user_prompt prompt_length=33`

The Logs UI is most useful if you add these fields as columns:

- `attributes_string['event.name']`
- `attributes_string['event.kind']`
- `attributes_string['tool_name']`
- `attributes_string['model']`
- `attributes_string['success']`
- `attributes_string['conversation.id']`

Recommended Logs filter:

- `service.name = codex_cli_rs`

Useful live event names seen in this stack include:

- `codex.websocket_event`
- `codex.tool_decision`
- `codex.tool_result`
- `codex.sse_event`
- `codex.user_prompt`

## Project Context

Native Codex metrics can expose a project dimension if Codex inherits project-aware `OTEL_RESOURCE_ATTRIBUTES` from the shell.

The intended native shape is:

- `project.name`
- `project.path`
- `vcs.repository.name` when a Git repo is available

The recommended local setup uses a `zsh` hook that resolves project identity from the current directory:

- use the nearest Git repo root and basename when `git rev-parse --show-toplevel` succeeds
- otherwise fall back to the nearest matching path in `~/.codex/config.toml` under `[projects]`
- keep launching plain `codex`; no Codex wrapper is required

Add a line like this to `~/.zshrc` after replacing `/path/to/signoz-codex` with the clone or install location of this project:

```zsh
[[ -f "/path/to/signoz-codex/scripts/project_resource_attrs_hook.zsh" ]] && source "/path/to/signoz-codex/scripts/project_resource_attrs_hook.zsh"
```

After updating `~/.zshrc`, start a fresh interactive `zsh` before launching `codex`.

Use `./scripts/signoz-codex verify` to print any observed `cwd` values from recent traces.

If the shell hook is active, `verify` also prints any project resource attributes detected on native Codex metrics.

If you want to inspect them directly:

- `./scripts/signoz-codex sql-read --format TSV "SELECT ts.resource_attrs['project.name'] AS project_name, ts.resource_attrs['project.path'] AS project_path, countDistinct(ts.fingerprint) AS series FROM signoz_metrics.distributed_samples_v4 AS s ANY INNER JOIN signoz_metrics.time_series_v4 AS ts USING fingerprint WHERE ts.resource_attrs['service.name']='codex_cli_rs' AND s.unix_milli >= toUnixTimestamp64Milli(now64(3) - INTERVAL 30 MINUTE) GROUP BY project_name, project_path ORDER BY series DESC, project_name ASC"`
- `./scripts/signoz-codex sql-read --format TSV "SELECT attributes_string['cwd'] AS cwd, count() AS spans FROM signoz_traces.distributed_signoz_index_v3 WHERE serviceName='codex_cli_rs' AND mapContains(attributes_string, 'cwd') GROUP BY cwd ORDER BY spans DESC"`

If project resource attributes are missing, trace-level `attributes_string['cwd']` remains the fallback project-like signal for debugging.

## Validation

- `python3 -m py_compile ./scripts/signoz_codex.py ./scripts/check_codex_config.py ./scripts/verify_codex_telemetry.py ./scripts/query_clickhouse.py ./scripts/project_resource_attrs.py`
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'`

## Notes

- Cost analytics are intentionally out of scope for this project version.
- The example OTEL snippet is based on the current local Codex parser behavior and verified against `codex features list`.
- Start with `dashboards/codex-native-dashboard.json` for native Codex telemetry.
- If a native Codex metric you care about is missing from the dashboard, inspect it first in SigNoz Services or via `./scripts/signoz-codex sql-read` and then extend the dashboard query set.
- `./scripts/signoz-codex check-config` validates `~/.codex/config.toml` before you start or verify the stack.
- `./scripts/signoz-codex verify` checks recent native `codex_cli_rs` logs, traces, tool calls, token totals, approval outcomes, websocket events, top log event names, and any trace-level `cwd` values.
- `./scripts/signoz-codex doctor` runs config validation, stack health checks, and telemetry verification in one pass.
