# Dashboards

`codex-native-dashboard.json` is the main dashboard for native Codex OTEL metrics from `codex_cli_rs`.

The dashboard defaults to an all-projects overview. Project-aware panels group by `project.name` so you can see which repositories consumed turns, tokens, tool calls, approvals, and latency without switching to a separate board.

It is service-level by default. To make native Codex metrics project-aware, launch plain `codex` from a shell that exports `project.name`, `project.path`, and `vcs.repository.name` through `OTEL_RESOURCE_ATTRIBUTES`.

The intended local flow is:
- Git repo available: use repo root/name
- No Git repo: fall back to the nearest matching Codex `[projects]` path

`project.name` is resource-level context inherited when Codex starts. If you move one long-running Codex session across repositories, metric project attribution can remain tied to the session's original resource attributes. Trace-level `attributes_string['cwd']` on some `run_sampling_request` spans is useful for debugging actual working directories, but it is not the primary metric dimension.

If that shell hook is not installed, project-aware dashboard panels can show empty project names. Use the Project Context Health panel to spot missing project attribution.

Tool success metrics measure whether Codex's host actions completed successfully, not whether the overall task was solved. For example, `exec_command success=false` usually means the command returned a non-zero exit status, was denied, was aborted, or failed to execute; `apply_patch success=false` usually means the patch did not apply. These failures can still be useful when Codex is probing the environment or testing an assumption.

Logs are still best explored in SigNoz's built-in Logs UI. Add columns for:
- `attributes_string['event.name']`
- `attributes_string['event.kind']`
- `attributes_string['tool_name']`
- `attributes_string['model']`
- `attributes_string['success']`
- `attributes_string['conversation.id']`

Avoid displaying raw `codex.user_prompt` prompt text, `user.email`, or `user.account_id` in dashboards. Prefer aggregate counts, token totals, duration signals, and project/repository names.

For repeatable validation outside the UI:
- run `./scripts/signoz_codex.py check-config` before restarting Codex
- run `./scripts/signoz_codex.py verify` after generating Codex activity
- run `./scripts/signoz_codex.py sql "SELECT ..."` when you need direct ClickHouse inspection
