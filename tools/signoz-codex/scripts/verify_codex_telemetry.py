#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess  # nosec B404
import sys
from pathlib import Path

from docker_runtime import compose_args, compose_environment

SCRIPT_DIR = Path(__file__).resolve().parent
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
RESET = "\033[0m"


def compose_failure_message(process_error: subprocess.CalledProcessError) -> str:
    output = (process_error.stderr or process_error.stdout or "").strip()
    lowered = output.lower()
    if "is not running" in lowered or "no such service" in lowered:
        return (
            "SigNoz Codex stack is not running or ClickHouse is unavailable.\n"
            "Start the stack with ./scripts/signoz-codex start, then retry verify or run ./scripts/signoz-codex doctor."
        )
    if "connection refused" in lowered or "timeout" in lowered or "timed out" in lowered:
        return (
            "ClickHouse is not reachable yet.\n"
            "Wait for the stack to finish starting, then rerun ./scripts/signoz-codex verify "
            "or use ./scripts/signoz-codex health."
        )
    return (
        "Failed to query ClickHouse while verifying native Codex telemetry.\n"
        "Run ./scripts/signoz-codex health or ./scripts/signoz-codex doctor for stack diagnostics."
    )


def run_compose(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        compose_args(*args),
        check=True,
        text=True,
        capture_output=True,
        env=compose_environment(),
    )  # nosec B603


def query_clickhouse(sql: str) -> list[str]:
    result = run_compose("exec", "-T", "clickhouse", "clickhouse-client", f"--query={sql}")
    return [line for line in result.stdout.splitlines() if line.strip()]


def parse_tsv(lines: list[str]) -> list[list[str]]:
    return [line.split("\t") for line in lines]


def sql_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def sql_lines(*lines: str) -> str:
    return "\n".join(lines)


def print_heading(title: str) -> None:
    print("")
    print(title)


def print_kv(label: str, value: str) -> None:
    print(f"  {label}: {value}")


def print_rows(title: str, rows: list[list[str]], columns: list[str], empty_message: str = "no data") -> None:
    print_heading(title)
    if not rows:
        print(f"  {YELLOW}{empty_message}{RESET}")
        return
    for row in rows:
        parts = [f"{name}={value}" for name, value in zip(columns, row)]
        print(f"  - {'; '.join(parts)}")


def parse_count(lines: list[str]) -> int:
    return int(lines[0]) if lines else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify that native Codex telemetry is flowing into the local SigNoz stack."
    )
    parser.add_argument("--minutes", type=int, default=30, help="Look back this many minutes")
    parser.add_argument("--service", default="codex_cli_rs", help="Codex service.name to inspect")
    return parser.parse_args()


def main() -> int:
    # pylint: disable=too-many-locals,too-many-statements
    args = parse_args()
    service = sql_string(args.service)
    window_logs = f"toUnixTimestamp64Nano(now64(9) - INTERVAL {args.minutes} MINUTE)"
    window_metrics = f"toUnixTimestamp64Milli(now64(3) - INTERVAL {args.minutes} MINUTE)"

    logs_count = query_clickhouse(
        sql_lines(
            "SELECT count()",
            "FROM signoz_logs.distributed_logs_v2",
            f"WHERE resources_string['service.name'] = {service}",
            f"  AND timestamp >= {window_logs}",
        )
    )
    metrics_count = query_clickhouse(
        sql_lines(
            "SELECT count()",
            "FROM signoz_metrics.distributed_samples_v4 AS s",
            "ANY INNER JOIN signoz_metrics.time_series_v4 AS ts USING fingerprint",
            f"WHERE ts.resource_attrs['service.name'] = {service}",
            f"  AND s.unix_milli >= {window_metrics}",
        )
    )
    traces_count = query_clickhouse(
        sql_lines(
            "SELECT count()",
            "FROM signoz_traces.distributed_signoz_index_v3",
            f"WHERE serviceName = {service}",
            f"  AND timestamp >= now() - INTERVAL {args.minutes} MINUTE",
        )
    )

    log_total = parse_count(logs_count)
    metric_total = parse_count(metrics_count)
    trace_total = parse_count(traces_count)

    if log_total == 0 and metric_total == 0 and trace_total == 0:
        print(
            f"{RED}[ERROR]{RESET} No native Codex telemetry found for service {args.service!r} "
            f"in the last {args.minutes} minutes"
        )
        print("Make sure Codex was restarted after updating ~/.codex/config.toml, then generate some activity.")
        return 1

    print(f"{GREEN}[OK]{RESET} Native Codex telemetry detected for service {args.service!r}")

    print_heading("Signal Coverage")
    print_kv("logs", str(log_total))
    print_kv("metrics", str(metric_total))
    print_kv("traces", str(trace_total))
    if log_total == 0:
        print(f"  {YELLOW}logs are missing in this window; log-based sections may be empty{RESET}")
    if metric_total == 0:
        print(f"  {YELLOW}metrics are missing in this window; metric-based sections may be empty{RESET}")
    if trace_total == 0:
        print(f"  {YELLOW}traces are missing in this window; trace-based sections may be empty{RESET}")

    tool_rows = parse_tsv(
        query_clickhouse(
            sql_lines(
                "SELECT ts.attrs['tool'] AS tool, ts.attrs['success'] AS success, toString(sum(s.value)) AS calls",
                "FROM signoz_metrics.distributed_samples_v4 AS s",
                "ANY INNER JOIN signoz_metrics.time_series_v4 AS ts USING fingerprint",
                f"WHERE ts.resource_attrs['service.name'] = {service}",
                "  AND ts.metric_name = 'codex.tool.call.duration_ms.count'",
                f"  AND s.unix_milli >= {window_metrics}",
                "GROUP BY tool, success",
                "ORDER BY sum(s.value) DESC, tool ASC",
                "LIMIT 10",
            )
        )
    )
    print_rows("Tool Calls", tool_rows, ["tool", "success", "calls"], "no tool-call metrics in the selected window")

    token_rows = parse_tsv(
        query_clickhouse(
            sql_lines(
                "SELECT ts.attrs['token_type'] AS token_type, toString(round(sum(s.value), 2)) AS tokens",
                "FROM signoz_metrics.distributed_samples_v4 AS s",
                "ANY INNER JOIN signoz_metrics.time_series_v4 AS ts USING fingerprint",
                f"WHERE ts.resource_attrs['service.name'] = {service}",
                "  AND ts.metric_name = 'codex.turn.token_usage.sum'",
                f"  AND s.unix_milli >= {window_metrics}",
                "GROUP BY token_type",
                "ORDER BY sum(s.value) DESC, token_type ASC",
                "LIMIT 10",
            )
        )
    )
    print_rows("Token Usage", token_rows, ["token_type", "tokens"], "no token-usage metrics in the selected window")

    approval_rows = parse_tsv(
        query_clickhouse(
            sql_lines(
                "SELECT ts.attrs['approved'] AS approved, toString(sum(s.value)) AS requests",
                "FROM signoz_metrics.distributed_samples_v4 AS s",
                "ANY INNER JOIN signoz_metrics.time_series_v4 AS ts USING fingerprint",
                f"WHERE ts.resource_attrs['service.name'] = {service}",
                "  AND ts.metric_name = 'codex.approval.requested'",
                f"  AND s.unix_milli >= {window_metrics}",
                "GROUP BY approved",
                "ORDER BY sum(s.value) DESC, approved ASC",
                "LIMIT 10",
            )
        )
    )
    print_rows(
        "Approval Outcomes",
        approval_rows,
        ["approved", "requests"],
        "no approval prompts in the selected window",
    )

    ws_rows = parse_tsv(
        query_clickhouse(
            sql_lines(
                "SELECT ts.attrs['kind'] AS kind, toString(sum(s.value)) AS events",
                "FROM signoz_metrics.distributed_samples_v4 AS s",
                "ANY INNER JOIN signoz_metrics.time_series_v4 AS ts USING fingerprint",
                f"WHERE ts.resource_attrs['service.name'] = {service}",
                "  AND ts.metric_name = 'codex.websocket.event'",
                f"  AND s.unix_milli >= {window_metrics}",
                "GROUP BY kind",
                "ORDER BY sum(s.value) DESC, kind ASC",
                "LIMIT 10",
            )
        )
    )
    print_rows(
        "Top Websocket Event Kinds",
        ws_rows,
        ["kind", "events"],
        "no websocket event metrics in the selected window",
    )

    log_event_rows = parse_tsv(
        query_clickhouse(
            sql_lines(
                "SELECT attributes_string['event.name'] AS event_name, toString(count()) AS rows",
                "FROM signoz_logs.distributed_logs_v2",
                f"WHERE resources_string['service.name'] = {service}",
                f"  AND timestamp >= {window_logs}",
                "GROUP BY event_name",
                "ORDER BY count() DESC, event_name ASC",
                "LIMIT 10",
            )
        )
    )
    print_rows(
        "Top Log Event Names",
        log_event_rows,
        ["event_name", "rows"],
        "no native Codex logs in the selected window",
    )

    metric_project_rows = parse_tsv(
        query_clickhouse(
            sql_lines(
                "SELECT",
                "  ts.resource_attrs['project.name'] AS project_name,",
                "  ts.resource_attrs['project.path'] AS project_path,",
                "  if(",
                "    ts.resource_attrs['vcs.repository.name'] = '',",
                "    '-',",
                "    ts.resource_attrs['vcs.repository.name']",
                "  ) AS repo_name,",
                "  toString(countDistinct(ts.fingerprint)) AS series",
                "FROM signoz_metrics.distributed_samples_v4 AS s",
                "ANY INNER JOIN signoz_metrics.time_series_v4 AS ts USING fingerprint",
                f"WHERE ts.resource_attrs['service.name'] = {service}",
                f"  AND s.unix_milli >= {window_metrics}",
                "  AND ts.resource_attrs['project.name'] != ''",
                "GROUP BY project_name, project_path, repo_name",
                "ORDER BY countDistinct(ts.fingerprint) DESC, project_name ASC, project_path ASC",
                "LIMIT 20",
            )
        )
    )
    if metric_project_rows:
        print_rows(
            "Metric Project Dimensions",
            metric_project_rows,
            ["project_name", "project_path", "repo_name", "series"],
        )
    else:
        print_heading("Metric Project Dimensions")
        print(f"  {YELLOW}no project resource attributes found on native Codex metrics in the selected window{RESET}")
        print(
            f"  {YELLOW}if you want project-aware native metrics, launch plain codex from a shell that "
            f"sets project.name/project.path OTEL attrs{RESET}"
        )

    project_rows = parse_tsv(
        query_clickhouse(
            sql_lines(
                "SELECT",
                "  attributes_string['cwd'] AS cwd,",
                "  arrayStringConcat(arraySort(groupUniqArray(name)), ', ') AS span_names,",
                "  toString(count()) AS spans",
                "FROM signoz_traces.distributed_signoz_index_v3",
                f"WHERE serviceName = {service}",
                f"  AND timestamp >= now() - INTERVAL {args.minutes} MINUTE",
                "  AND mapContains(attributes_string, 'cwd')",
                "GROUP BY cwd",
                "ORDER BY count() DESC, cwd ASC",
                "LIMIT 20",
            )
        )
    )
    if project_rows:
        print_rows("Trace CWD Values", project_rows, ["cwd", "span_names", "spans"])
        if metric_project_rows:
            print(
                f"  {YELLOW}trace cwd is still useful for debugging, but project.name/project.path "
                f"are the preferred native metric dimensions{RESET}"
            )
        else:
            print(
                f"  {YELLOW}project context is partial: cwd is currently only visible on trace spans, "
                f"not native Codex logs/metrics{RESET}"
            )
    else:
        print_heading("Trace CWD Values")
        print(f"  {YELLOW}no project-identifying trace attributes found in the selected window{RESET}")
        print(f"  {YELLOW}native Codex logs and metrics currently do not expose a project dimension{RESET}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(f"{RED}[ERROR]{RESET} {compose_failure_message(exc)}\n")
        if exc.stderr:
            sys.stderr.write(exc.stderr)
        elif exc.stdout:
            sys.stderr.write(exc.stdout)
        raise SystemExit(exc.returncode) from exc
