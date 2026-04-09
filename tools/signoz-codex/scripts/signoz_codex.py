#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess  # nosec B404
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from docker_runtime import (
    PROJECT_ROOT,
    RuntimeConfig,
    bind_addr_is_loopback,
    clickhouse_client_args,
    compose_args,
    compose_environment,
    docker_args,
    ensure_runtime_assets_rendered,
    resolve_runtime,
    runtime_summary_lines,
    stack_host,
)

SCRIPT_DIR = Path(__file__).resolve().parent
DOCKER_BIN = shutil.which("docker") or "docker"
REQUIRED_SERVICES = ("clickhouse", "zookeeper-1", "signoz", "otel-collector")
CONFIG_CHECK_SCRIPT = SCRIPT_DIR / "check_codex_config.py"
VERIFY_SCRIPT = SCRIPT_DIR / "verify_codex_telemetry.py"
QUERY_SCRIPT = SCRIPT_DIR / "query_clickhouse.py"

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
RESET = "\033[0m"


def log_info(message: str) -> None:
    print(f"{GREEN}[INFO]{RESET} {message}")


def log_warn(message: str) -> None:
    print(f"{YELLOW}[WARN]{RESET} {message}")


def log_error(message: str) -> None:
    print(f"{RED}[ERROR]{RESET} {message}", file=sys.stderr)


def remote_loopback_access_warning(runtime: RuntimeConfig) -> str | None:
    if (
        getattr(runtime, "uses_remote_docker_host", False)
        and bind_addr_is_loopback(getattr(runtime, "bind_addr", ""))
        and stack_host(runtime) == "localhost"
    ):
        return (
            "Remote Docker ports are still bound to the remote host loopback interface. "
            "Use an SSH tunnel for localhost access, or set SIGNOZ_CODEX_BIND_ADDR=0.0.0.0 "
            "and SIGNOZ_CODEX_STACK_HOST=<remote-host> for direct access."
        )
    return None


def run_compose(
    runtime: RuntimeConfig,
    *args: str,
    capture_output: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        compose_args(*args, runtime=runtime),
        check=check,
        text=True,
        capture_output=capture_output,
        env=compose_environment(runtime=runtime),
    )  # nosec B603


def run_local_script(script_path: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script_path), *args],
        check=check,
        text=True,
        capture_output=True,
    )  # nosec B603


def emit_script_result(result: subprocess.CompletedProcess[str]) -> None:
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)


def check_docker(runtime: RuntimeConfig) -> None:
    try:
        subprocess.run(
            [DOCKER_BIN, "--version"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )  # nosec B603
    except FileNotFoundError as exc:
        raise SystemExit("Docker is not installed or not in PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit("Docker CLI is installed but not working correctly") from exc

    context_result = subprocess.run(
        [DOCKER_BIN, "context", "inspect", runtime.docker_context],
        check=False,
        text=True,
        capture_output=True,
    )  # nosec B603
    if context_result.returncode != 0:
        raise SystemExit(f"Docker context {runtime.docker_context!r} is not available")

    docker_result = subprocess.run(
        docker_args("ps", runtime=runtime),
        check=False,
        text=True,
        capture_output=True,
    )  # nosec B603
    if docker_result.returncode != 0:
        raise SystemExit(f"Docker context {runtime.docker_context!r} is not reachable")

    compose_result = subprocess.run(
        compose_args("version", runtime=runtime),
        check=False,
        text=True,
        capture_output=True,
        env=compose_environment(runtime=runtime),
    )  # nosec B603
    if compose_result.returncode != 0:
        raise SystemExit("docker compose is not available for the selected Docker context")


def unsupported_remote_assets_message(runtime: RuntimeConfig) -> str:
    lines = [
        (
            f"The active Docker context {runtime.docker_context!r} uses a remote engine "
            f"({runtime.docker_endpoint or 'unknown endpoint'})."
        ),
        (
            "This stack relies on bind-mounted config files, so remote engines need an explicit "
            "asset-sync command before compose startup."
        ),
        (
            "Set SIGNOZ_CODEX_REMOTE_ASSET_SYNC_CMD to a local command that copies this project's "
            "runtime assets to the remote host."
        ),
    ]
    if runtime.stack_host != "localhost":
        lines.append(f"Configured stack host: {runtime.stack_host}")
    lines.append(
        "The remote sync command should write files into SIGNOZ_CODEX_REMOTE_ASSETS_ROOT so the compose "
        "bind mounts resolve on the remote engine."
    )
    return "\n".join(lines)


def ensure_runtime_assets(runtime: RuntimeConfig, *, required: bool) -> bool:
    if not runtime.uses_remote_docker_host:
        return False
    if not runtime.requires_remote_asset_sync:
        if required:
            raise SystemExit(unsupported_remote_assets_message(runtime))
        return False

    log_info(f"Syncing remote runtime assets into {runtime.remote_assets_root}")
    result = subprocess.run(
        ["/bin/sh", "-lc", runtime.remote_asset_sync_cmd],
        check=False,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
        cwd=PROJECT_ROOT,
    )  # nosec B603
    if result.returncode != 0:
        output = result.stderr.strip() or result.stdout.strip() or "remote asset sync command failed"
        raise SystemExit(output)
    return True


def running_services(runtime: RuntimeConfig) -> set[str]:
    result = run_compose(runtime, "ps", "--services", "--filter", "status=running", capture_output=True)
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def are_all_running(runtime: RuntimeConfig) -> bool:
    active = running_services(runtime)
    return all(service in active for service in REQUIRED_SERVICES)


def show_status(runtime: RuntimeConfig) -> int:
    host = stack_host(runtime)
    log_info("SigNoz Codex stack status")
    print()
    run_compose(runtime, "ps", check=False)
    print()
    if are_all_running(runtime):
        log_info("All required services are running")
    else:
        log_warn("Not all required services are running yet")
    for line in runtime_summary_lines(runtime):
        log_info(line)
    access_warning = remote_loopback_access_warning(runtime)
    if access_warning:
        log_warn(access_warning)
    log_info(f"SigNoz UI: http://{host}:8105")
    log_info(f"OTLP gRPC: {host}:5317")
    log_info(f"OTLP HTTP: http://{host}:5318")
    log_info(f"Primary dashboard: {PROJECT_ROOT / 'dashboards' / 'codex-native-dashboard.json'}")
    log_info("Query helper: ./scripts/signoz-codex sql-read \"SELECT 1\"")
    config_result = run_local_script(CONFIG_CHECK_SCRIPT, "--quiet")
    if config_result.returncode != 0:
        print("")
        log_warn("Codex telemetry config check failed")
        log_warn("Run ./scripts/check_codex_config.py for details")
    return 0


def start_services(runtime: RuntimeConfig, force: bool) -> int:
    if not force:
        config_result = run_local_script(CONFIG_CHECK_SCRIPT)
        if config_result.stdout:
            print(config_result.stdout, end="")
        if config_result.stderr:
            print(config_result.stderr, end="", file=sys.stderr)
        if config_result.returncode != 0:
            return config_result.returncode

    assets_refreshed = ensure_runtime_assets(runtime, required=False)

    if are_all_running(runtime):
        log_info("All services already running")
        if assets_refreshed:
            log_info("Remote runtime assets were refreshed before returning status")
            log_warn("Run ./scripts/signoz-codex restart if config changes require service reload")
        return show_status(runtime)

    if not assets_refreshed:
        ensure_runtime_assets(runtime, required=True)

    log_info("Starting SigNoz Codex stack")
    up_args = ["up", "-d"]
    if assets_refreshed:
        up_args.append("--force-recreate")
    run_compose(runtime, *up_args)
    log_info("Waiting for core services")
    waited = 0
    while waited < 90:
        if are_all_running(runtime):
            break
        print('.', end='', flush=True)
        time.sleep(2)
        waited += 2
    print()
    status_rc = show_status(runtime)
    if not are_all_running(runtime):
        return 1
    return status_rc


def stop_services(runtime: RuntimeConfig) -> int:
    log_info("Stopping SigNoz Codex stack")
    run_compose(runtime, "stop")
    return 0


def restart_services(runtime: RuntimeConfig) -> int:
    ensure_runtime_assets(runtime, required=False)
    log_info("Restarting SigNoz Codex stack")
    run_compose(runtime, "restart")
    return show_status(runtime)


def show_logs(runtime: RuntimeConfig, service: str | None) -> int:
    args = ["logs", "-f"]
    if service:
        args.append(service)
    return subprocess.run(
        compose_args(*args, runtime=runtime),
        check=False,
        env=compose_environment(runtime=runtime),
    ).returncode  # nosec B603


def cleanup(runtime: RuntimeConfig) -> int:
    log_warn("This stops and removes containers but keeps volumes")
    reply = input("Continue? (y/N): ").strip()
    if reply.lower() == 'y':
        run_compose(runtime, "down")
    else:
        log_info("Cancelled")
    return 0


def purge(runtime: RuntimeConfig) -> int:
    log_error("This removes containers and persistent volumes")
    reply = input("Type DELETE to confirm: ").strip()
    if reply == 'DELETE':
        run_compose(runtime, "down", "-v")
    else:
        log_info("Cancelled")
    return 0


def _check_http_health(runtime: RuntimeConfig) -> bool:
    health_url = f"http://{stack_host(runtime)}:8105/api/v1/health"
    if urlparse(health_url).scheme not in {"http", "https"}:
        return False
    try:
        with urllib.request.urlopen(health_url, timeout=5) as response:  # nosec B310
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError):
        return False


def _check_port(runtime: RuntimeConfig, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex((stack_host(runtime), port)) == 0


def health_check(runtime: RuntimeConfig) -> int:
    host = stack_host(runtime)
    log_info("Checking SigNoz Codex stack health")
    print()
    access_warning = remote_loopback_access_warning(runtime)
    if access_warning:
        log_warn(access_warning)
        print("")

    clickhouse_ok = subprocess.run(
        clickhouse_client_args("--query=SELECT 1", runtime=runtime),
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=compose_environment(runtime=runtime),
    ).returncode == 0  # nosec B603
    http_ok = _check_http_health(runtime)
    grpc_ok = _check_port(runtime, 5317)
    http_ingest_ok = _check_port(runtime, 5318)

    print(f"  {(GREEN + '✓' + RESET) if clickhouse_ok else (RED + '✗' + RESET)} ClickHouse")
    print(
        f"  {(GREEN + '✓' + RESET) if http_ok else (YELLOW + '!' + RESET)} "
        f"SigNoz UI on {host}:8105"
    )
    print(
        f"  {(GREEN + '✓' + RESET) if grpc_ok else (YELLOW + '!' + RESET)} "
        f"OTLP gRPC on {host}:5317"
    )
    print(
        f"  {(GREEN + '✓' + RESET) if http_ingest_ok else (YELLOW + '!' + RESET)} "
        f"OTLP HTTP on {host}:5318"
    )
    return 0 if all((clickhouse_ok, http_ok, grpc_ok, http_ingest_ok)) else 1


def check_codex_config() -> int:
    result = run_local_script(CONFIG_CHECK_SCRIPT)
    emit_script_result(result)
    return result.returncode


def verify_telemetry(minutes: int) -> int:
    runtime = resolve_runtime()
    config_result = run_local_script(CONFIG_CHECK_SCRIPT)
    emit_script_result(config_result)
    if config_result.returncode != 0:
        return config_result.returncode

    if not are_all_running(runtime):
        log_error("SigNoz Codex stack is not fully running")
        log_error("Run ./scripts/signoz-codex start, then retry verify or use ./scripts/signoz-codex doctor")
        return 1

    print("")
    verify_result = run_local_script(VERIFY_SCRIPT, "--minutes", str(minutes))
    emit_script_result(verify_result)
    if verify_result.returncode != 0:
        log_warn("Verification failed")
        log_warn(
            "Use ./scripts/signoz-codex health for service readiness or "
            "./scripts/signoz-codex doctor for a full check"
        )
    return verify_result.returncode


def run_clickhouse_query(extra_args: list[str]) -> int:
    result = run_local_script(QUERY_SCRIPT, *extra_args)
    emit_script_result(result)
    return result.returncode


def build_sql_args(args: argparse.Namespace, readonly: bool = False) -> list[str]:
    extra: list[str] = []
    if readonly:
        extra.append("--readonly")
    if args.file:
        extra.extend(["--file", args.file])
    if args.format:
        extra.extend(["--format", args.format])
    if args.multiquery:
        extra.append("--multiquery")
    if args.query:
        extra.append(args.query)
    return extra


def config_check(runtime: RuntimeConfig) -> int:
    ensure_runtime_assets(runtime, required=runtime.uses_remote_docker_host)
    run_compose(runtime, "config", "-q")
    log_info("Compose configuration is valid")
    return 0


def doctor(runtime: RuntimeConfig, minutes: int) -> int:
    log_info("Running Codex telemetry diagnostics")
    print("")

    config_rc = check_codex_config()
    if config_rc != 0:
        return config_rc

    print("")
    health_rc = health_check(runtime)
    if health_rc != 0:
        return health_rc

    print("")
    return verify_telemetry(minutes)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SigNoz Codex stack helper")
    subparsers = parser.add_subparsers(dest="command")

    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("--force", action="store_true", help="Start without checking the Codex OTEL config")
    subparsers.add_parser("stop")
    subparsers.add_parser("restart")
    subparsers.add_parser("status")

    logs_parser = subparsers.add_parser("logs")
    logs_parser.add_argument("service", nargs='?')

    subparsers.add_parser("check-config")
    subparsers.add_parser("health")
    subparsers.add_parser("config")
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument(
        "--minutes",
        type=int,
        default=30,
        help="Look back this many minutes for native Codex telemetry",
    )
    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument(
        "--minutes",
        type=int,
        default=30,
        help="Look back this many minutes for native Codex telemetry",
    )

    sql_parser = subparsers.add_parser("sql")
    sql_parser.add_argument("query", nargs='?')
    sql_parser.add_argument("--file")
    sql_parser.add_argument("--format")
    sql_parser.add_argument("--multiquery", action="store_true")

    sql_read_parser = subparsers.add_parser("sql-read")
    sql_read_parser.add_argument("query", nargs='?')
    sql_read_parser.add_argument("--file")
    sql_read_parser.add_argument("--format")
    sql_read_parser.add_argument("--multiquery", action="store_true")

    subparsers.add_parser("cleanup")
    subparsers.add_parser("purge")
    return parser


def main(argv: list[str] | None = None) -> int:
    # pylint: disable=too-many-branches
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or 'start'
    runtime = resolve_runtime()

    docker_commands = {
        'start',
        'stop',
        'restart',
        'status',
        'logs',
        'health',
        'config',
        'verify',
        'doctor',
        'sql',
        'sql-read',
        'cleanup',
        'purge',
    }
    if command in docker_commands:
        ensure_runtime_assets_rendered()
        check_docker(runtime)

    if command == 'start':
        return start_services(runtime, args.force)
    if command == 'stop':
        return stop_services(runtime)
    if command == 'restart':
        return restart_services(runtime)
    if command == 'status':
        return show_status(runtime)
    if command == 'logs':
        return show_logs(runtime, args.service)
    if command == 'check-config':
        return check_codex_config()
    if command == 'health':
        return health_check(runtime)
    if command == 'config':
        return config_check(runtime)
    if command == 'verify':
        return verify_telemetry(args.minutes)
    if command == 'doctor':
        return doctor(runtime, args.minutes)
    if command == 'sql':
        return run_clickhouse_query(build_sql_args(args))
    if command == 'sql-read':
        return run_clickhouse_query(build_sql_args(args, readonly=True))
    if command == 'cleanup':
        return cleanup(runtime)
    if command == 'purge':
        return purge(runtime)

    parser.error(f'Unknown command: {command}')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
