#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path
from typing import Any

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
RESET = "\033[0m"

EXPECTED_ENDPOINT = "http://127.0.0.1:5317"
CONFIG_PATH = Path.home() / ".codex" / "config.toml"
EXAMPLE_PATH = Path(__file__).resolve().parents[1] / "examples" / "codex-otel.example.toml"


def ok(message: str, quiet: bool) -> None:
    if not quiet:
        print(f"{GREEN}✓{RESET} {message}")


def warn(message: str, quiet: bool) -> None:
    if not quiet:
        print(f"{YELLOW}!{RESET} {message}")


def error(message: str, quiet: bool) -> None:
    if not quiet:
        print(f"{RED}✗{RESET} {message}")


def extract_otlp_endpoint(raw: Any) -> str | None:
    if not isinstance(raw, dict):
        return None
    target = raw.get("otlp-grpc")
    if not isinstance(target, dict):
        return None
    endpoint = target.get("endpoint")
    return endpoint if isinstance(endpoint, str) else None


def check_exporter(name: str, value: Any, quiet: bool) -> tuple[int, int]:
    warnings = 0
    errors = 0
    endpoint = extract_otlp_endpoint(value)
    if endpoint == EXPECTED_ENDPOINT:
        ok(f"{name} endpoint is {EXPECTED_ENDPOINT}", quiet)
    elif endpoint is None:
        error(f"{name} is missing or not configured for otlp-grpc", quiet)
        errors += 1
    else:
        error(f"{name} endpoint is {endpoint!r} (expected {EXPECTED_ENDPOINT!r})", quiet)
        errors += 1
    return warnings, errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Codex OTEL configuration for the local SigNoz Codex stack.")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-check output and rely on exit code")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    quiet = args.quiet

    if not CONFIG_PATH.exists():
        error(f"Codex config not found at {CONFIG_PATH}", quiet)
        if not quiet:
            print("")
            print(f"Merge the OTEL snippet from {EXAMPLE_PATH}")
        return 1

    try:
        with CONFIG_PATH.open("rb") as handle:
            config = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        error(f"Failed to parse {CONFIG_PATH}: {exc}", quiet)
        return 1

    warnings = 0
    errors = 0

    otel = config.get("otel")
    if not isinstance(otel, dict):
        error("Missing [otel] configuration block", quiet)
        errors += 1
        otel = {}
    else:
        ok("Found [otel] configuration block", quiet)

    for field_name in ("exporter", "trace_exporter", "metrics_exporter"):
        field_warnings, field_errors = check_exporter(field_name, otel.get(field_name), quiet)
        warnings += field_warnings
        errors += field_errors

    log_user_prompt = otel.get("log_user_prompt")
    if log_user_prompt is False:
        warn("log_user_prompt is false, so codex.user_prompt events are exported with prompt='[REDACTED]'", quiet)
        warnings += 1
    elif log_user_prompt is True:
        ok("log_user_prompt is true, so raw prompt text is exported to logs", quiet)
    else:
        warn("log_user_prompt is unset", quiet)
        warnings += 1

    if errors:
        if not quiet:
            print("")
            print(f"{RED}[ERROR]{RESET} Codex telemetry configuration has {errors} error(s)")
            print("")
            print("Recommended OTEL snippet:")
            print("")
            print(EXAMPLE_PATH.read_text(encoding="utf-8").rstrip())
            print("")
            print("After updating ~/.codex/config.toml, restart Codex from the ~/.codex project root.")
        return 1

    if warnings and not quiet:
        print("")
        print(f"{YELLOW}[WARN]{RESET} Configuration has {warnings} warning(s)")
        print("Telemetry should still work, but review the notes above.")
        return 0

    if not quiet:
        print("")
        print(f"{GREEN}[OK]{RESET} Codex telemetry configuration looks good")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
