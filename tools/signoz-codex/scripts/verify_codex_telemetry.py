#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
COMPOSE_FILE = PROJECT_ROOT / "docker-compose.yaml"
PROJECT_NAME = "signoz-codex"

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
RESET = "\033[0m"


def compose_args(*args: str) -> list[str]:
    return ["docker", "compose", "-f", str(COMPOSE_FILE), "-p", PROJECT_NAME, *args]


def run_compose(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(compose_args(*args), check=True, text=True, capture_output=True)


def query_clickhouse(sql: str) -> list[str]:
    result = run_compose("exec", "-T", "clickhouse", "clickhouse-client", f"--query={sql}")
    return [line for line in result.stdout.splitlines() if line.strip()]


def parse_tsv(lines: list[str]) -> list[list[str]]:
    return [line.split("\t") for line in lines]


def print_heading(title: str) -> None:
    print("")
    print(title)


def print_kv(label: str, value: str) -> None:
    print(f"  {label}: {value}")


def print_rows(title: str, rows: list[list[str]], columns: list[str]) -> None:
    print_heading(title)
    if not rows:
        print(f"  {YELLOW}no data{RESET}")
        return
    for row in rows:
        parts = [f"{name}={value}" for name, value in zip(columns, row)]
        print(f"  - {'; '.join(parts)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify that native Codex telemetry is flowing into the local SigNoz stack.")
    parser.add_argument("--minutes", type=int, default=30, help="Look back this many minutes")
    parser.add_argument("--service", default="codex_cli_rs", help="Codex service.name to inspect")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    window_logs = f"toUnixTimestamp64Nano(now64(9) - INTERVAL {args.minutes} MINUTE)"
    window_metrics = f"toUnixTimestamp64Milli(now64(3) - INTERVAL {args.minutes} MINUTE)"

    logs_count = query_clickhouse(
        f"""
        SELECT count()
        FROM signoz_logs.distributed_logs_v2
        WHERE resources_string['service.name'] = '{args.service}'
          AND timestamp >= {window_logs}
        """
    )
    traces_count = query_clickhouse(
        f"""
        SELECT count()
        FROM signoz_traces.distributed_signoz_index_v3
        WHERE serviceName = '{args.service}'
          AND timestamp >= now() - INTERVAL {args.minutes} MINUTE
        """
    )

    log_total = int(logs_count[0]) if logs_count else 0
    trace_total = int(traces_count[0]) if traces_count else 0

    if log_total == 0 and trace_total == 0:
        print(f"{RED}[ERROR]{RESET} No native Codex telemetry found for service {args.service!r} in the last {args.minutes} minutes")
        print("Make sure Codex was restarted after updating ~/.codex/config.toml and then generate some activity.")
        return 1

    print(f"{GREEN}[OK]{RESET} Native Codex telemetry detected for service {args.service!r}")
    print_kv("logs", str(log_total))
    print_kv("traces", str(trace_total))

    tool_rows = parse_tsv(
        query_clickhouse(
            f"""
            SELECT ts.attrs['tool'] AS tool, toString(sum(s.value)) AS calls
            FROM signoz_metrics.distributed_samples_v4 AS s
            ANY INNER JOIN signoz_metrics.time_series_v4 AS ts USING fingerprint
            WHERE ts.resource_attrs['service.name'] = '{args.service}'
              AND ts.metric_name = 'codex.tool.call'
              AND s.unix_milli >= {window_metrics}
            GROUP BY tool
            ORDER BY sum(s.value) DESC, tool ASC
            LIMIT 10
            """
        )
    )
    print_rows("Tool Calls", tool_rows, ["tool", "calls"])

    token_rows = parse_tsv(
        query_clickhouse(
            f"""
            SELECT ts.attrs['token_type'] AS token_type, toString(round(sum(s.value), 2)) AS tokens
            FROM signoz_metrics.distributed_samples_v4 AS s
            ANY INNER JOIN signoz_metrics.time_series_v4 AS ts USING fingerprint
            WHERE ts.resource_attrs['service.name'] = '{args.service}'
              AND ts.metric_name = 'codex.turn.token_usage.sum'
              AND s.unix_milli >= {window_metrics}
            GROUP BY token_type
            ORDER BY sum(s.value) DESC, token_type ASC
            LIMIT 10
            """
        )
    )
    print_rows("Token Usage", token_rows, ["token_type", "tokens"])

    approval_rows = parse_tsv(
        query_clickhouse(
            f"""
            SELECT ts.attrs['approved'] AS approved, toString(sum(s.value)) AS requests
            FROM signoz_metrics.distributed_samples_v4 AS s
            ANY INNER JOIN signoz_metrics.time_series_v4 AS ts USING fingerprint
            WHERE ts.resource_attrs['service.name'] = '{args.service}'
              AND ts.metric_name = 'codex.approval.requested'
              AND s.unix_milli >= {window_metrics}
            GROUP BY approved
            ORDER BY sum(s.value) DESC, approved ASC
            LIMIT 10
            """
        )
    )
    print_rows("Approval Outcomes", approval_rows, ["approved", "requests"])

    ws_rows = parse_tsv(
        query_clickhouse(
            f"""
            SELECT ts.attrs['kind'] AS kind, toString(sum(s.value)) AS events
            FROM signoz_metrics.distributed_samples_v4 AS s
            ANY INNER JOIN signoz_metrics.time_series_v4 AS ts USING fingerprint
            WHERE ts.resource_attrs['service.name'] = '{args.service}'
              AND ts.metric_name = 'codex.websocket.event'
              AND s.unix_milli >= {window_metrics}
            GROUP BY kind
            ORDER BY sum(s.value) DESC, kind ASC
            LIMIT 10
            """
        )
    )
    print_rows("Top Websocket Event Kinds", ws_rows, ["kind", "events"])

    log_event_rows = parse_tsv(
        query_clickhouse(
            f"""
            SELECT attributes_string['event.name'] AS event_name, toString(count()) AS rows
            FROM signoz_logs.distributed_logs_v2
            WHERE resources_string['service.name'] = '{args.service}'
              AND timestamp >= {window_logs}
            GROUP BY event_name
            ORDER BY count() DESC, event_name ASC
            LIMIT 10
            """
        )
    )
    print_rows("Top Log Event Names", log_event_rows, ["event_name", "rows"])

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(exc.stderr or str(exc))
        raise SystemExit(exc.returncode)
