# SigNoz Codex Stack

Local SigNoz + OpenTelemetry stack for inspecting native Codex telemetry.

## What This Project Covers

- Native Codex OTEL data sent to a local SigNoz collector
- A helper stack with ClickHouse, SigNoz, and the OTEL collector
- A primary native dashboard for Codex OTEL metrics

Use a single entry point for operations:
- `./scripts/signoz_codex.py <command>`

Native Codex telemetry is best explored through the native dashboard plus SigNoz's built-in Services, Traces, and Logs views. Import `dashboards/codex-native-dashboard.json` first.

## Quick Start

1. Validate your Codex OTEL config:
   `./scripts/signoz_codex.py check-config`
2. Start the stack:
   `./scripts/signoz_codex.py start`
3. Open SigNoz:
   `http://localhost:8105`
4. Import the primary dashboard from:
   `dashboards/codex-native-dashboard.json`
5. Merge the example OTEL settings from:
   `examples/codex-otel.example.toml`
   into `~/.codex/config.toml`
6. Start a fresh Codex session and generate activity.
7. Verify native telemetry:
   `./scripts/signoz_codex.py verify`

## Ports

- SigNoz UI: `8105`
- OTLP gRPC: `5317`
- OTLP HTTP: `5318`

These ports intentionally differ from the existing Claude-focused stack so both projects can coexist on one machine.

## Helper Commands

- `./scripts/signoz_codex.py start`
- `./scripts/signoz_codex.py start --force`
- `./scripts/signoz_codex.py stop`
- `./scripts/signoz_codex.py restart`
- `./scripts/signoz_codex.py status`
- `./scripts/signoz_codex.py logs`
- `./scripts/signoz_codex.py logs otel-collector`
- `./scripts/signoz_codex.py check-config`
- `./scripts/signoz_codex.py health`
- `./scripts/signoz_codex.py verify`
- `./scripts/signoz_codex.py doctor`
- `./scripts/signoz_codex.py config`
- `./scripts/signoz_codex.py sql "SELECT count() FROM signoz_logs.distributed_logs_v2"`

## ClickHouse Queries

Use the single entry point instead of the full `docker compose ... clickhouse-client` command:

- `./scripts/signoz_codex.py sql "SELECT count() FROM signoz_logs.distributed_logs_v2"`
- `./scripts/signoz_codex.py sql --format Vertical "SELECT attributes_string['event.name'], count() FROM signoz_logs.distributed_logs_v2 GROUP BY 1 ORDER BY count() DESC LIMIT 10"`
- `./scripts/signoz_codex.py sql --file ./query.sql`
- `cat ./query.sql | ./scripts/signoz_codex.py sql`

If you are using your shell alias, the same commands become:

- `signoz-codex sql "SELECT count() FROM signoz_logs.distributed_logs_v2"`
- `signoz-codex sql --format Vertical "SELECT * FROM signoz_metrics.time_series_v4 LIMIT 3"`

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

## Validation

- `python3 -m py_compile ./scripts/signoz_codex.py ./scripts/check_codex_config.py ./scripts/verify_codex_telemetry.py ./scripts/query_clickhouse.py`
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'`

## Notes

- Cost analytics are intentionally out of scope for this project version.
- The example OTEL snippet is based on the current local Codex parser behavior and verified against `codex features list`.
- Start with `dashboards/codex-native-dashboard.json` for native Codex telemetry.
- If a native Codex metric you care about is missing from the dashboard, inspect it first in SigNoz Services or via `./scripts/signoz_codex.py sql` and then extend the dashboard query set.
- `./scripts/signoz_codex.py check-config` validates `~/.codex/config.toml` before you start or verify the stack.
- `./scripts/signoz_codex.py verify` checks recent native `codex_cli_rs` logs, traces, tool calls, token totals, approval outcomes, websocket events, and top log event names.
- `./scripts/signoz_codex.py doctor` runs config validation, stack health checks, and telemetry verification in one pass.
