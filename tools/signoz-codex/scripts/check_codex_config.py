#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from docker_runtime import expected_otlp_endpoint
from toml_compat import TOMLDecodeError, tomllib

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
RESET = "\033[0m"

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


def normalize_otlp_endpoint(endpoint: str) -> str:
    candidate = endpoint.strip()
    parsed = urlparse(candidate)
    if not parsed.scheme or not parsed.netloc:
        return candidate

    try:
        port = parsed.port
    except ValueError:
        return candidate

    hostname = parsed.hostname or ""
    normalized_host = hostname.lower()
    if normalized_host in {"127.0.0.1", "::1", "localhost"}:
        normalized_host = "localhost"

    userinfo = ""
    if parsed.username:
        userinfo = parsed.username
        if parsed.password:
            userinfo = f"{userinfo}:{parsed.password}"
        userinfo = f"{userinfo}@"

    netloc = normalized_host
    if ":" in netloc and not netloc.startswith("["):
        netloc = f"[{netloc}]"
    if port is not None:
        netloc = f"{netloc}:{port}"
    netloc = f"{userinfo}{netloc}"

    path = parsed.path.rstrip("/")
    if path == "/":
        path = ""

    return parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=netloc,
        path=path,
        params="",
        query="",
        fragment="",
    ).geturl()


def check_exporter(name: str, value: Any, quiet: bool, expected: str) -> tuple[int, int]:
    warnings = 0
    errors = 0
    endpoint = extract_otlp_endpoint(value)
    normalized_endpoint = normalize_otlp_endpoint(endpoint) if endpoint is not None else None
    normalized_expected = normalize_otlp_endpoint(expected)
    if normalized_endpoint == normalized_expected:
        ok(f"{name} endpoint is {expected}", quiet)
    elif endpoint is None:
        error(f"{name} is missing or not configured for otlp-grpc", quiet)
        errors += 1
    else:
        error(f"{name} endpoint is {endpoint!r} (expected {expected!r})", quiet)
        errors += 1
    return warnings, errors


def check_log_user_prompt(value: Any, quiet: bool) -> int:
    warnings = 0
    if value is False:
        ok("log_user_prompt is false, so prompt text is redacted in exported codex.user_prompt events", quiet)
    elif value is True:
        ok("log_user_prompt is true, so raw prompt text is exported to logs", quiet)
    else:
        warn("log_user_prompt is unset", quiet)
        warnings += 1
    return warnings


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
    except TOMLDecodeError as exc:
        error(f"Failed to parse {CONFIG_PATH}: {exc}", quiet)
        return 1

    warnings = 0
    errors = 0
    endpoint = expected_otlp_endpoint()

    otel = config.get("otel")
    if not isinstance(otel, dict):
        error("Missing [otel] configuration block", quiet)
        errors += 1
        otel = {}
    else:
        ok("Found [otel] configuration block", quiet)

    for field_name in ("exporter", "trace_exporter", "metrics_exporter"):
        field_warnings, field_errors = check_exporter(field_name, otel.get(field_name), quiet, endpoint)
        warnings += field_warnings
        errors += field_errors

    warnings += check_log_user_prompt(otel.get("log_user_prompt"), quiet)

    if errors:
        if not quiet:
            print("")
            print(f"{RED}[ERROR]{RESET} Codex telemetry configuration has {errors} error(s)")
            print("")
            print("Recommended OTEL snippet:")
            print("")
            print("[otel]")
            print("log_user_prompt = false")
            print(f"exporter = {{ otlp-grpc = {{ endpoint = {endpoint!r} }} }}")
            print(f"trace_exporter = {{ otlp-grpc = {{ endpoint = {endpoint!r} }} }}")
            print(f"metrics_exporter = {{ otlp-grpc = {{ endpoint = {endpoint!r} }} }}")
            print("")
            print("After updating ~/.codex/config.toml, restart Codex so the new OTEL settings are loaded.")
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
