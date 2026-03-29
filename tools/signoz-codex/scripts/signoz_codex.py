#!/usr/bin/env python3
from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
COMPOSE_FILE = PROJECT_ROOT / "docker-compose.yaml"
PROJECT_NAME = "signoz-codex"
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


def compose_args(*args: str) -> list[str]:
    return ["docker", "compose", "-f", str(COMPOSE_FILE), "-p", PROJECT_NAME, *args]


def run_compose(*args: str, capture_output: bool = False, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        compose_args(*args),
        check=check,
        text=True,
        capture_output=capture_output,
    )


def run_local_script(script_path: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script_path), *args],
        check=check,
        text=True,
        capture_output=True,
    )


def emit_script_result(result: subprocess.CompletedProcess[str]) -> None:
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)


def check_docker() -> None:
    try:
        subprocess.run(["docker", "ps"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError as exc:
        raise SystemExit("Docker is not installed or not in PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit("Docker daemon is not running or not accessible") from exc


def running_services() -> set[str]:
    result = run_compose("ps", "--services", "--filter", "status=running", capture_output=True)
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def are_all_running() -> bool:
    active = running_services()
    return all(service in active for service in REQUIRED_SERVICES)


def show_status() -> int:
    log_info("SigNoz Codex stack status")
    print()
    run_compose("ps", check=False)
    print()
    if are_all_running():
        log_info("All required services are running")
    else:
        log_warn("Not all required services are running yet")
    log_info("SigNoz UI: http://localhost:8105")
    log_info("OTLP gRPC: localhost:5317")
    log_info("OTLP HTTP: http://localhost:5318")
    log_info(f"Primary dashboard: {PROJECT_ROOT / 'dashboards' / 'codex-native-dashboard.json'}")
    log_info("Query helper: ./scripts/signoz_codex.py sql \"SELECT 1\"")
    config_result = run_local_script(CONFIG_CHECK_SCRIPT, "--quiet")
    if config_result.returncode != 0:
        print("")
        log_warn("Codex telemetry config check failed")
        log_warn("Run ./scripts/check_codex_config.py for details")
    return 0


def start_services(force: bool) -> int:
    if not force:
        config_result = run_local_script(CONFIG_CHECK_SCRIPT)
        if config_result.stdout:
            print(config_result.stdout, end="")
        if config_result.stderr:
            print(config_result.stderr, end="", file=sys.stderr)
        if config_result.returncode != 0:
            return config_result.returncode

    if are_all_running():
        log_info("All services already running")
        return show_status()

    log_info("Starting SigNoz Codex stack")
    run_compose("up", "-d")
    log_info("Waiting for core services")
    waited = 0
    while waited < 90:
        if are_all_running():
            break
        print('.', end='', flush=True)
        time.sleep(2)
        waited += 2
    print()
    return show_status()


def stop_services() -> int:
    log_info("Stopping SigNoz Codex stack")
    run_compose("stop")
    return 0


def restart_services() -> int:
    log_info("Restarting SigNoz Codex stack")
    run_compose("restart")
    return show_status()


def show_logs(service: str | None) -> int:
    args = ["logs", "-f"]
    if service:
        args.append(service)
    return subprocess.run(compose_args(*args), check=False).returncode


def cleanup() -> int:
    log_warn("This stops and removes containers but keeps volumes")
    reply = input("Continue? (y/N): ").strip()
    if reply.lower() == 'y':
        run_compose("down")
    else:
        log_info("Cancelled")
    return 0


def purge() -> int:
    log_error("This removes containers and persistent volumes")
    reply = input("Type DELETE to confirm: ").strip()
    if reply == 'DELETE':
        run_compose("down", "-v")
    else:
        log_info("Cancelled")
    return 0


def _check_http_health() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8105/api/v1/health", timeout=5) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError):
        return False


def _check_port(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def health_check() -> int:
    log_info("Checking SigNoz Codex stack health")
    print()

    clickhouse_ok = subprocess.run(
        compose_args("exec", "-T", "clickhouse", "clickhouse-client", "--query=SELECT 1"),
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0
    print(f"  {(GREEN + '✓' + RESET) if clickhouse_ok else (RED + '✗' + RESET)} ClickHouse")
    print(f"  {(GREEN + '✓' + RESET) if _check_http_health() else (YELLOW + '!' + RESET)} SigNoz UI")
    print(f"  {(GREEN + '✓' + RESET) if _check_port(5317) else (YELLOW + '!' + RESET)} OTLP gRPC on :5317")
    print(f"  {(GREEN + '✓' + RESET) if _check_port(5318) else (YELLOW + '!' + RESET)} OTLP HTTP on :5318")
    return 0


def check_codex_config() -> int:
    result = run_local_script(CONFIG_CHECK_SCRIPT)
    emit_script_result(result)
    return result.returncode


def verify_telemetry(minutes: int) -> int:
    config_result = run_local_script(CONFIG_CHECK_SCRIPT)
    emit_script_result(config_result)
    if config_result.returncode != 0:
        return config_result.returncode

    print("")
    verify_result = run_local_script(VERIFY_SCRIPT, "--minutes", str(minutes))
    emit_script_result(verify_result)
    return verify_result.returncode


def run_clickhouse_query(extra_args: list[str]) -> int:
    result = run_local_script(QUERY_SCRIPT, *extra_args)
    emit_script_result(result)
    return result.returncode


def config_check() -> int:
    run_compose("config", "-q")
    log_info("Compose configuration is valid")
    return 0


def doctor(minutes: int) -> int:
    log_info("Running Codex telemetry diagnostics")
    print("")

    config_rc = check_codex_config()
    if config_rc != 0:
        return config_rc

    print("")
    health_rc = health_check()
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
    verify_parser.add_argument("--minutes", type=int, default=30, help="Look back this many minutes for native Codex telemetry")
    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument("--minutes", type=int, default=30, help="Look back this many minutes for native Codex telemetry")

    sql_parser = subparsers.add_parser("sql")
    sql_parser.add_argument("query", nargs='?')
    sql_parser.add_argument("--file")
    sql_parser.add_argument("--format")
    sql_parser.add_argument("--multiquery", action="store_true")

    subparsers.add_parser("cleanup")
    subparsers.add_parser("purge")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or 'start'

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
        'cleanup',
        'purge',
    }
    if command in docker_commands:
        check_docker()

    if command == 'start':
        return start_services(args.force)
    if command == 'stop':
        return stop_services()
    if command == 'restart':
        return restart_services()
    if command == 'status':
        return show_status()
    if command == 'logs':
        return show_logs(args.service)
    if command == 'check-config':
        return check_codex_config()
    if command == 'health':
        return health_check()
    if command == 'config':
        return config_check()
    if command == 'verify':
        return verify_telemetry(args.minutes)
    if command == 'doctor':
        return doctor(args.minutes)
    if command == 'sql':
        extra: list[str] = []
        if args.file:
            extra.extend(["--file", args.file])
        if args.format:
            extra.extend(["--format", args.format])
        if args.multiquery:
            extra.append("--multiquery")
        if args.query:
            extra.append(args.query)
        return run_clickhouse_query(extra)
    if command == 'cleanup':
        return cleanup()
    if command == 'purge':
        return purge()

    parser.error(f'Unknown command: {command}')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
