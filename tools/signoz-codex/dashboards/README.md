# Dashboards

`codex-native-dashboard.json` is the main dashboard for native Codex OTEL metrics from `codex_cli_rs`.

It is service-level by default. To make native Codex metrics project-aware, launch plain `codex` from a shell that exports `project.name`, `project.path`, and `vcs.repository.name` through `OTEL_RESOURCE_ATTRIBUTES`.

The intended local flow is:
- Git repo available: use repo root/name
- No Git repo: fall back to the nearest matching Codex `[projects]` path

If that shell hook is not installed, the only project-like fallback remains trace-level `attributes_string['cwd']` on some `run_sampling_request` spans.

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
