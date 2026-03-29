#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
COMPOSE_FILE = PROJECT_ROOT / "docker-compose.yaml"
PROJECT_NAME = "signoz-codex"

FORMAT_PATTERN = re.compile(r"\bFORMAT\b", re.IGNORECASE)


def compose_args(*args: str) -> list[str]:
    return ["docker", "compose", "-f", str(COMPOSE_FILE), "-p", PROJECT_NAME, *args]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a ClickHouse query against the local SigNoz Codex stack."
    )
    parser.add_argument("query", nargs="?", help="SQL query to run")
    parser.add_argument("--file", help="Read the SQL query from a file, or '-' for stdin")
    parser.add_argument("--format", help="Append a ClickHouse FORMAT clause if the query does not already include one")
    parser.add_argument("--multiquery", action="store_true", help="Enable ClickHouse multiquery mode")
    return parser.parse_args(argv)


def load_query(args: argparse.Namespace) -> str:
    if args.query and args.file:
        raise SystemExit("Pass either a query argument or --file, not both")

    if args.file:
        if args.file == "-":
            text = sys.stdin.read()
        else:
            text = Path(args.file).read_text(encoding="utf-8")
    elif args.query:
        text = args.query
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        raise SystemExit("Provide a query, use --file, or pipe SQL on stdin")

    query = text.strip()
    if not query:
        raise SystemExit("SQL query is empty")
    return query


def apply_output_format(query: str, output_format: str | None) -> str:
    if not output_format or FORMAT_PATTERN.search(query):
        return query
    return f"{query.rstrip().rstrip(';')} FORMAT {output_format}"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    query = apply_output_format(load_query(args), args.format)

    command = compose_args("exec", "-T", "clickhouse", "clickhouse-client")
    if args.multiquery:
        command.append("--multiquery")
    command.append(f"--query={query}")
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
