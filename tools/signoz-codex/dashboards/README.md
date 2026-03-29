# Dashboards

`codex-native-dashboard.json` is the main dashboard for native Codex OTEL metrics from `codex_cli_rs`.

Logs are still best explored in SigNoz's built-in Logs UI. Add columns for:
- `attributes_string['event.name']`
- `attributes_string['event.kind']`
- `attributes_string['tool_name']`
- `attributes_string['model']`
- `attributes_string['success']`
- `attributes_string['conversation.id']`

For repeatable validation outside the UI:
- run `./scripts/signoz_codex.py check-config` before restarting Codex
- run `./scripts/signoz_codex.py verify` after generating Codex activity
- run `./scripts/signoz_codex.py sql "SELECT ..."` when you need direct ClickHouse inspection
