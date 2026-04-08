#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess  # nosec B404
import sys
from pathlib import Path

from docker_runtime import compose_args, compose_environment

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
    if not output_format or has_trailing_top_level_format_clause(query):
        return query
    return f"{query.rstrip().rstrip(';')} FORMAT {output_format}"


def _next_char(text: str, index: int) -> str:
    return text[index + 1] if index + 1 < len(text) else ""


def _consume_line_comment(text: str, index: int) -> int:
    while index < len(text) and text[index] != "\n":
        index += 1
    return index


def _consume_block_comment(text: str, index: int) -> int:
    while index + 1 < len(text):
        if text[index] == "*" and text[index + 1] == "/":
            return index + 2
        index += 1
    return len(text)


def _consume_single_quoted_text(text: str, index: int) -> int:
    while index < len(text):
        char = text[index]
        next_char = _next_char(text, index)
        if char == "\\" and next_char:
            index += 2
            continue
        if char == "'" and next_char == "'":
            index += 2
            continue
        index += 1
        if char == "'":
            return index
    return index


def _consume_double_quoted_text(text: str, index: int) -> int:
    while index < len(text):
        char = text[index]
        next_char = _next_char(text, index)
        if char == "\\" and next_char:
            index += 2
            continue
        index += 1
        if char == '"':
            return index
    return index


def _consume_backtick_quoted_text(text: str, index: int) -> int:
    while index < len(text):
        char = text[index]
        index += 1
        if char == "`":
            return index
    return index


def _consume_quoted_text(text: str, index: int, quote: str) -> int:
    if quote == "'":
        return _consume_single_quoted_text(text, index)
    if quote == '"':
        return _consume_double_quoted_text(text, index)
    return _consume_backtick_quoted_text(text, index)


def _consume_word(text: str, index: int) -> tuple[int, str]:
    start = index
    index += 1
    while index < len(text):
        char = text[index]
        if char != "_" and not char.isalnum():
            break
        index += 1
    return index, text[start:index].upper()


def top_level_words(text: str) -> list[str]:
    words: list[str] = []
    depth = 0
    index = 0

    while index < len(text):
        char = text[index]
        next_char = _next_char(text, index)

        if char == "-" and next_char == "-":
            index = _consume_line_comment(text, index + 2)
            continue
        if char == "#":
            index = _consume_line_comment(text, index + 1)
            continue
        if char == "/" and next_char == "*":
            index = _consume_block_comment(text, index + 2)
            continue
        if char in {"'", '"', "`"}:
            index = _consume_quoted_text(text, index + 1, char)
            continue
        if char == "(":
            depth += 1
            index += 1
            continue
        if char == ")":
            depth = max(0, depth - 1)
            index += 1
            continue
        if depth == 0 and (char == "_" or char.isalpha()):
            index, word = _consume_word(text, index)
            words.append(word)
            continue
        index += 1

    return words


def has_trailing_top_level_format_clause(query: str) -> bool:
    words = top_level_words(query)
    return len(words) >= 2 and words[-2] == "FORMAT"


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
    return top_level_words(text)


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
