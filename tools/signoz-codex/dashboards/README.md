# Dashboards

`codex-native-dashboard.json` is the main dashboard for native Codex OTEL metrics from `codex_cli_rs`.

It is currently service-level, not project-level. Native Codex logs and metrics do not currently expose a reusable project dimension. The only project-like signal observed so far is trace-level `attributes_string['cwd']` on some `run_sampling_request` spans, so the dashboard cannot reliably filter all native panels by project today.

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
