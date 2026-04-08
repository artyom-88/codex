#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess  # nosec B404
import sys
from pathlib import Path

from docker_runtime import compose_args, compose_environment

FORMAT_PATTERN = re.compile(r"\bFORMAT\b", re.IGNORECASE)
READONLY_USER = "codex_readonly"
READ_ONLY_START_KEYWORDS = frozenset({"SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN", "EXISTS"})
WRITE_START_KEYWORDS = frozenset(
    {
        "INSERT",
        "CREATE",
        "DROP",
        "ALTER",
        "TRUNCATE",
        "DELETE",
        "UPDATE",
        "RENAME",
        "OPTIMIZE",
        "SYSTEM",
        "KILL",
        "GRANT",
        "REVOKE",
        "ATTACH",
        "DETACH",
        "UNDROP",
        "BACKUP",
        "RESTORE",
        "SET",
        "USE",
    }
)

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a ClickHouse query against the local SigNoz Codex stack."
    )
    parser.add_argument("query", nargs="?", help="SQL query to run")
    parser.add_argument("--file", help="Read the SQL query from a file, or '-' for stdin")
    parser.add_argument("--format", help="Append a ClickHouse FORMAT clause if the query does not already include one")
    parser.add_argument("--multiquery", action="store_true", help="Enable ClickHouse multiquery mode")
    parser.add_argument(
        "--readonly",
        action="store_true",
        help="Reject mutating SQL and run the query with the read-only ClickHouse user",
    )
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


def split_sql_statements(text: str) -> list[str]:
    # pylint: disable=too-many-branches,too-many-statements
    statements: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    in_backtick = False
    in_line_comment = False
    in_block_comment = False
    index = 0

    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""

        if in_line_comment:
            current.append(char)
            if char == "\n":
                in_line_comment = False
            index += 1
            continue

        if in_block_comment:
            current.append(char)
            if char == "*" and next_char == "/":
                current.append(next_char)
                in_block_comment = False
                index += 2
                continue
            index += 1
            continue

        if in_single:
            current.append(char)
            if char == "\\" and next_char:
                current.append(next_char)
                index += 2
                continue
            if char == "'" and next_char == "'":
                current.append(next_char)
                index += 2
                continue
            if char == "'":
                in_single = False
            index += 1
            continue

        if in_double:
            current.append(char)
            if char == "\\" and next_char:
                current.append(next_char)
                index += 2
                continue
            if char == '"':
                in_double = False
            index += 1
            continue

        if in_backtick:
            current.append(char)
            if char == "`":
                in_backtick = False
            index += 1
            continue

        if char == "-" and next_char == "-":
            current.append(char)
            current.append(next_char)
            in_line_comment = True
            index += 2
            continue

        if char == "#":
            current.append(char)
            in_line_comment = True
            index += 1
            continue

        if char == "/" and next_char == "*":
            current.append(char)
            current.append(next_char)
            in_block_comment = True
            index += 2
            continue

        if char == "'":
            current.append(char)
            in_single = True
            index += 1
            continue

        if char == '"':
            current.append(char)
            in_double = True
            index += 1
            continue

        if char == "`":
            current.append(char)
            in_backtick = True
            index += 1
            continue

        if char == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            index += 1
            continue

        current.append(char)
        index += 1

    statement = "".join(current).strip()
    if statement:
        statements.append(statement)
    return statements


def iter_top_level_keywords(text: str) -> list[str]:
    # pylint: disable=too-many-branches,too-many-statements
    keywords: list[str] = []
    in_single = False
    in_double = False
    in_backtick = False
    in_line_comment = False
    in_block_comment = False
    depth = 0
    index = 0

    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""

        if in_line_comment:
            if char == "\n":
                in_line_comment = False
            index += 1
            continue

        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                index += 2
                continue
            index += 1
            continue

        if in_single:
            if char == "\\" and next_char:
                index += 2
                continue
            if char == "'" and next_char == "'":
                index += 2
                continue
            if char == "'":
                in_single = False
            index += 1
            continue

        if in_double:
            if char == "\\" and next_char:
                index += 2
                continue
            if char == '"':
                in_double = False
            index += 1
            continue

        if in_backtick:
            if char == "`":
                in_backtick = False
            index += 1
            continue

        if char == "-" and next_char == "-":
            in_line_comment = True
            index += 2
            continue

        if char == "#":
            in_line_comment = True
            index += 1
            continue

        if char == "/" and next_char == "*":
            in_block_comment = True
            index += 2
            continue

        if char == "'":
            in_single = True
            index += 1
            continue

        if char == '"':
            in_double = True
            index += 1
            continue

        if char == "`":
            in_backtick = True
            index += 1
            continue

        if char == "(":
            depth += 1
            index += 1
            continue

        if char == ")":
            depth = max(0, depth - 1)
            index += 1
            continue

        if char == "_" or char.isalpha():
            start = index
            index += 1
            while index < len(text) and (text[index] == "_" or text[index].isalnum()):
                index += 1
            if depth == 0:
                keywords.append(text[start:index].upper())
            continue

        index += 1

    return keywords


def is_readonly_statement(statement: str) -> bool:
    keywords = iter_top_level_keywords(statement)
    if not keywords:
        return False

    first_keyword = keywords[0]
    if first_keyword in READ_ONLY_START_KEYWORDS:
        return True
    if first_keyword != "WITH":
        return False

    for keyword in keywords[1:]:
        if keyword in READ_ONLY_START_KEYWORDS:
            return True
        if keyword in WRITE_START_KEYWORDS:
            return False
    return False


def validate_readonly_query(query: str) -> None:
    for statement in split_sql_statements(query):
        if is_readonly_statement(statement):
            continue
        preview = " ".join(statement.split())
        raise SystemExit(f"sql-read only allows read queries; rejected statement: {preview[:120]}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    query = load_query(args)
    if args.readonly:
        validate_readonly_query(query)
    query = apply_output_format(query, args.format)

    command = compose_args("exec", "-T", "clickhouse", "clickhouse-client")
    if args.readonly:
        command.append(f"--user={READONLY_USER}")
    if args.multiquery:
        command.append("--multiquery")
    command.append(f"--query={query}")
    return subprocess.run(command, check=False, env=compose_environment()).returncode  # nosec


if __name__ == "__main__":
    raise SystemExit(main())
