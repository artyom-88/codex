from __future__ import annotations

import json
import os
import secrets
import hashlib
import shutil
import subprocess  # nosec B404
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
COMPOSE_FILE = PROJECT_ROOT / "docker-compose.yaml"
PROJECT_NAME = "signoz-codex"
DEFAULT_BIND_ADDR = "127.0.0.1"
DOCKER_BIN = shutil.which("docker") or "docker"
CLICKHOUSE_WRITE_USER = "default"
CLICKHOUSE_READONLY_USER = "codex_readonly"
CLICKHOUSE_WRITE_PASSWORD_ENV = "SIGNOZ_CODEX_CLICKHOUSE_WRITE_PASSWORD"
CLICKHOUSE_READONLY_PASSWORD_ENV = "SIGNOZ_CODEX_CLICKHOUSE_READONLY_PASSWORD"
CLICKHOUSE_WRITE_DSN_ENV = "SIGNOZ_CODEX_CLICKHOUSE_WRITE_DSN"
GENERATED_DIR = PROJECT_ROOT / "local" / "generated"
CREDENTIALS_ENV_PATH = GENERATED_DIR / "clickhouse.env"
CLICKHOUSE_USERS_TEMPLATE_PATH = PROJECT_ROOT / "common" / "clickhouse" / "users.template.xml"
CLICKHOUSE_USERS_RENDERED_PATH = GENERATED_DIR / "clickhouse-users.xml"
SIGNOZ_PROMETHEUS_TEMPLATE_PATH = PROJECT_ROOT / "common" / "signoz" / "prometheus.template.yml"
SIGNOZ_PROMETHEUS_RENDERED_PATH = GENERATED_DIR / "signoz-prometheus.yml"


def load_local_runtime_env() -> None:
    path = PROJECT_ROOT / "local" / "runtime.env"
    if path.exists():
        _load_env_file(path)


def _load_env_file(path: Path) -> None:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, os.path.expandvars(value))


load_local_runtime_env()


def remote_bind_mounts(remote_assets_root: Path) -> dict[str, Path]:
    return {
        "SIGNOZ_CODEX_CLICKHOUSE_USER_SCRIPTS": remote_assets_root / "common" / "clickhouse" / "user_scripts",
        "SIGNOZ_CODEX_CLICKHOUSE_CONFIG": remote_assets_root / "common" / "clickhouse" / "config.xml",
        "SIGNOZ_CODEX_CLICKHOUSE_USERS": remote_assets_root / "local" / "generated" / "clickhouse-users.xml",
        "SIGNOZ_CODEX_CLICKHOUSE_CUSTOM_FUNCTION": remote_assets_root / "common" / "clickhouse" / "custom-function.xml",
        "SIGNOZ_CODEX_CLICKHOUSE_HISTOGRAM_SHA256": (
            remote_assets_root / "common" / "clickhouse" / "histogram-quantile.sha256"
        ),
        "SIGNOZ_CODEX_CLICKHOUSE_CLUSTER": remote_assets_root / "common" / "clickhouse" / "cluster.xml",
        "SIGNOZ_CODEX_SIGNOZ_PROMETHEUS": remote_assets_root / "local" / "generated" / "signoz-prometheus.yml",
        "SIGNOZ_CODEX_SIGNOZ_COMMON": remote_assets_root / "common" / "signoz",
        "SIGNOZ_CODEX_OTEL_COLLECTOR_CONFIG": remote_assets_root / "otel-collector-config.yaml",
    }


@dataclass(frozen=True)
# RuntimeConfig intentionally keeps the resolved runtime values together so callers can pass one object around.
# pylint: disable-next=too-many-instance-attributes
class RuntimeConfig:
    docker_context: str
    docker_context_source: str
    docker_endpoint: str
    engine_mode: str
    remote_assets_root: Path
    remote_asset_sync_cmd: str
    bind_addr: str
    stack_host: str
    otlp_endpoint: str

    @property
    def uses_remote_docker_host(self) -> bool:
        return self.engine_mode == "remote"

    @property
    def requires_remote_asset_sync(self) -> bool:
        return self.uses_remote_docker_host and bool(self.remote_asset_sync_cmd)


@dataclass(frozen=True)
class ClickHouseCredentials:
    write_user: str
    write_password: str
    readonly_user: str
    readonly_password: str


def _run_docker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [DOCKER_BIN, *args],
        check=False,
        text=True,
        capture_output=True,
    )  # nosec B603


def current_docker_context() -> str:
    try:
        result = _run_docker("context", "show")
    except FileNotFoundError:
        return "default"
    if result.returncode != 0:
        return "default"
    return result.stdout.strip() or "default"


def resolve_docker_context() -> tuple[str, str]:
    explicit_context = os.environ.get("DOCKER_CONTEXT", "").strip()
    if explicit_context:
        return explicit_context, "env:DOCKER_CONTEXT"
    return current_docker_context(), "docker context show"


def docker_context_inspect(context_name: str | None = None) -> dict[str, object]:
    context = context_name or resolve_docker_context()[0]
    try:
        result = _run_docker("context", "inspect", context)
    except FileNotFoundError:
        return {}
    if result.returncode != 0:
        return {}
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    if not data:
        return {}
    first = data[0]
    return first if isinstance(first, dict) else {}


def docker_endpoint(context_name: str | None = None) -> str:
    return str(docker_context_inspect(context_name).get("Endpoints", {}).get("docker", {}).get("Host", ""))


def endpoint_host(endpoint: str) -> str:
    if endpoint.startswith("ssh://") or endpoint.startswith("tcp://"):
        parsed = urlparse(endpoint)
        return parsed.hostname or ""
    return ""


def looks_like_remote_endpoint(endpoint: str) -> bool:
    return endpoint.startswith("tcp://") or endpoint.startswith("ssh://")


def bind_addr_is_loopback(bind_addr: str) -> bool:
    return bind_addr.strip().lower() in {"127.0.0.1", "localhost", "::1", "[::1]"}


def clickhouse_credentials() -> ClickHouseCredentials:
    ensure_runtime_assets_rendered()
    return ClickHouseCredentials(
        write_user=CLICKHOUSE_WRITE_USER,
        write_password=os.environ[CLICKHOUSE_WRITE_PASSWORD_ENV],
        readonly_user=CLICKHOUSE_READONLY_USER,
        readonly_password=os.environ[CLICKHOUSE_READONLY_PASSWORD_ENV],
    )


def _generated_password() -> str:
    return secrets.token_hex(24)


def _quote_env_value(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _write_file_if_changed(path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    # Write with restrictive permissions and atomically replace to avoid exposing secrets
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_path, path)
        os.chmod(path, 0o600)
    finally:
        # If something went wrong before replace, ensure temp file doesn't linger
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def ensure_clickhouse_secret_env() -> None:
    if CREDENTIALS_ENV_PATH.exists():
        _load_env_file(CREDENTIALS_ENV_PATH)

    if CLICKHOUSE_WRITE_PASSWORD_ENV not in os.environ:
        os.environ[CLICKHOUSE_WRITE_PASSWORD_ENV] = _generated_password()
    if CLICKHOUSE_READONLY_PASSWORD_ENV not in os.environ:
        os.environ[CLICKHOUSE_READONLY_PASSWORD_ENV] = _generated_password()

    os.environ.setdefault(
        CLICKHOUSE_WRITE_DSN_ENV,
        (
            f"tcp://{CLICKHOUSE_WRITE_USER}:{os.environ[CLICKHOUSE_WRITE_PASSWORD_ENV]}"
            "@clickhouse:9000"
        ),
    )

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    env_lines = [
        "# Generated by tools/signoz-codex/scripts/docker_runtime.py",
        f"export {CLICKHOUSE_WRITE_PASSWORD_ENV}={_quote_env_value(os.environ[CLICKHOUSE_WRITE_PASSWORD_ENV])}",
        f"export {CLICKHOUSE_READONLY_PASSWORD_ENV}={_quote_env_value(os.environ[CLICKHOUSE_READONLY_PASSWORD_ENV])}",
        f"export {CLICKHOUSE_WRITE_DSN_ENV}={_quote_env_value(os.environ[CLICKHOUSE_WRITE_DSN_ENV])}",
        "",
    ]
    _write_file_if_changed(CREDENTIALS_ENV_PATH, "\n".join(env_lines))


def ensure_runtime_assets_rendered() -> None:
    ensure_clickhouse_secret_env()
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    users_template = CLICKHOUSE_USERS_TEMPLATE_PATH.read_text(encoding="utf-8")
    users_rendered = (
        users_template
        .replace("__SIGNOZ_CODEX_CLICKHOUSE_READONLY_PASSWORD_SHA256_HEX__", _sha256_hex(os.environ[CLICKHOUSE_READONLY_PASSWORD_ENV]))
        .replace("__SIGNOZ_CODEX_CLICKHOUSE_WRITE_PASSWORD_SHA256_HEX__", _sha256_hex(os.environ[CLICKHOUSE_WRITE_PASSWORD_ENV]))
    )
    _write_file_if_changed(CLICKHOUSE_USERS_RENDERED_PATH, users_rendered)

    signoz_prometheus_template = SIGNOZ_PROMETHEUS_TEMPLATE_PATH.read_text(encoding="utf-8")
    signoz_prometheus_rendered = signoz_prometheus_template.replace(
        "__SIGNOZ_CODEX_CLICKHOUSE_WRITE_DSN__", os.environ[CLICKHOUSE_WRITE_DSN_ENV]
    )
    _write_file_if_changed(SIGNOZ_PROMETHEUS_RENDERED_PATH, signoz_prometheus_rendered)


def resolve_runtime() -> RuntimeConfig:
    context_name, context_source = resolve_docker_context()
    endpoint = docker_endpoint(context_name)

    requested_engine_mode = os.environ.get("SIGNOZ_CODEX_ENGINE_MODE", "auto").strip().lower() or "auto"
    if requested_engine_mode not in {"auto", "local", "remote"}:
        raise SystemExit("SIGNOZ_CODEX_ENGINE_MODE must be one of: auto, local, remote")

    if requested_engine_mode == "local":
        engine_mode = "local"
    elif requested_engine_mode == "remote":
        engine_mode = "remote"
    elif looks_like_remote_endpoint(endpoint):
        engine_mode = "remote"
    else:
        engine_mode = "local"

    bind_addr = os.environ.get("SIGNOZ_CODEX_BIND_ADDR", "").strip() or DEFAULT_BIND_ADDR
    stack_host_override = os.environ.get("SIGNOZ_CODEX_STACK_HOST", "").strip()
    if stack_host_override:
        resolved_stack_host = stack_host_override
    elif engine_mode == "local" or bind_addr_is_loopback(bind_addr):
        resolved_stack_host = "localhost"
    else:
        resolved_stack_host = endpoint_host(endpoint) or "localhost"

    otlp_endpoint = os.environ.get("SIGNOZ_CODEX_OTLP_ENDPOINT", "").strip() or f"http://{resolved_stack_host}:5317"
    remote_asset_sync_cmd = os.environ.get("SIGNOZ_CODEX_REMOTE_ASSET_SYNC_CMD", "").strip()
    remote_assets_root = Path(os.environ.get("SIGNOZ_CODEX_REMOTE_ASSETS_ROOT", "/srv/signoz-codex"))

    return RuntimeConfig(
        docker_context=context_name,
        docker_context_source=context_source,
        docker_endpoint=endpoint,
        engine_mode=engine_mode,
        remote_assets_root=remote_assets_root,
        remote_asset_sync_cmd=remote_asset_sync_cmd,
        bind_addr=bind_addr,
        stack_host=resolved_stack_host,
        otlp_endpoint=otlp_endpoint,
    )


def expected_otlp_endpoint(runtime: RuntimeConfig | None = None) -> str:
    return (runtime or resolve_runtime()).otlp_endpoint


def stack_host(runtime: RuntimeConfig | None = None) -> str:
    return (runtime or resolve_runtime()).stack_host


def docker_args(*args: str, runtime: RuntimeConfig | None = None) -> list[str]:
    active_runtime = runtime or resolve_runtime()
    return [DOCKER_BIN, "--context", active_runtime.docker_context, *args]


def compose_args(*args: str, runtime: RuntimeConfig | None = None) -> list[str]:
    return [*docker_args("compose", runtime=runtime), "-f", str(COMPOSE_FILE), "-p", PROJECT_NAME, *args]


def compose_environment(runtime: RuntimeConfig | None = None) -> dict[str, str]:
    active_runtime = runtime or resolve_runtime()
    ensure_clickhouse_secret_env()
    env = os.environ.copy()
    env["SIGNOZ_CODEX_BIND_ADDR"] = active_runtime.bind_addr
    env.setdefault("SIGNOZ_CODEX_CLICKHOUSE_USERS", str(CLICKHOUSE_USERS_RENDERED_PATH))
    env.setdefault("SIGNOZ_CODEX_SIGNOZ_PROMETHEUS", str(SIGNOZ_PROMETHEUS_RENDERED_PATH))
    if not active_runtime.requires_remote_asset_sync:
        return env
    env.update({name: str(path) for name, path in remote_bind_mounts(active_runtime.remote_assets_root).items()})
    return env


def runtime_summary_lines(runtime: RuntimeConfig | None = None) -> list[str]:
    active_runtime = runtime or resolve_runtime()
    lines = [
        f"Docker context: {active_runtime.docker_context}",
        f"Context source: {active_runtime.docker_context_source}",
        f"Engine mode: {active_runtime.engine_mode}",
        f"Bind address: {active_runtime.bind_addr}",
        f"Advertised stack host: {active_runtime.stack_host}",
        f"Expected OTLP endpoint: {active_runtime.otlp_endpoint}",
    ]
    if active_runtime.docker_endpoint:
        lines.append(f"Docker endpoint: {active_runtime.docker_endpoint}")
    if active_runtime.uses_remote_docker_host:
        lines.append(f"Remote assets root: {active_runtime.remote_assets_root}")
        lines.append(
            "Remote asset sync: configured"
            if active_runtime.remote_asset_sync_cmd
            else "Remote asset sync: not configured"
        )
        if bind_addr_is_loopback(active_runtime.bind_addr) and active_runtime.stack_host == "localhost":
            lines.append("Remote access: published ports stay on the remote host loopback interface")
            lines.append(
                "Remote access hint: use an SSH tunnel for localhost, or set "
                "SIGNOZ_CODEX_BIND_ADDR=0.0.0.0 and SIGNOZ_CODEX_STACK_HOST=<remote-host>"
            )
    return lines
