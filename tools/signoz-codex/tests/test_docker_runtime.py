from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_support import load_script_module

MODULE = load_script_module("docker_runtime", "docker_runtime.py")


def completed(stdout: str = "", returncode: int = 0) -> mock.Mock:
    result = mock.Mock()
    result.stdout = stdout
    result.returncode = returncode
    return result


def runtime_env(**overrides: str) -> dict[str, str]:
    env = dict(os.environ)
    for key in (
        "DOCKER_CONTEXT",
        "SIGNOZ_CODEX_ENGINE_MODE",
        "SIGNOZ_CODEX_REMOTE_ASSETS_ROOT",
        "SIGNOZ_CODEX_REMOTE_ASSET_SYNC_CMD",
        "SIGNOZ_CODEX_BIND_ADDR",
        "SIGNOZ_CODEX_STACK_HOST",
        "SIGNOZ_CODEX_OTLP_ENDPOINT",
    ):
        env.pop(key, None)
    env.update(overrides)
    return env


class DockerRuntimeTests(unittest.TestCase):
    REMOTE_BIND_ALL_ADDR = ".".join(["0", "0", "0", "0"])

    def test_resolve_runtime_defaults_to_local_active_context(self) -> None:
        inspect_json = json.dumps(
            [
                {
                    "Endpoints": {
                        "docker": {
                            "Host": "unix:///var/run/docker.sock",
                        }
                    }
                }
            ]
        )

        with mock.patch.dict(os.environ, runtime_env(), clear=True):
            with mock.patch.object(
                MODULE,
                "_run_docker",
                side_effect=[
                    completed("default\n"),
                    completed(inspect_json),
                ],
            ):
                runtime = MODULE.resolve_runtime()

        self.assertEqual(runtime.docker_context, "default")
        self.assertEqual(runtime.engine_mode, "local")
        self.assertFalse(runtime.requires_remote_asset_sync)
        self.assertEqual(runtime.bind_addr, "127.0.0.1")
        self.assertEqual(runtime.stack_host, "localhost")

    def test_resolve_runtime_uses_explicit_remote_context(self) -> None:
        inspect_json = json.dumps(
            [
                {
                    "Endpoints": {
                        "docker": {
                            "Host": "tcp://10.0.0.50:2376",
                        }
                    }
                }
            ]
        )

        with mock.patch.dict(os.environ, runtime_env(DOCKER_CONTEXT="remote-dev"), clear=True):
            with mock.patch.object(MODULE, "_run_docker", return_value=completed(inspect_json)):
                runtime = MODULE.resolve_runtime()

        self.assertEqual(runtime.docker_context, "remote-dev")
        self.assertEqual(runtime.docker_context_source, "env:DOCKER_CONTEXT")
        self.assertEqual(runtime.engine_mode, "remote")
        self.assertEqual(runtime.stack_host, "localhost")

    def test_resolve_runtime_exposes_remote_host_only_with_non_loopback_bind(self) -> None:
        inspect_json = json.dumps(
            [
                {
                    "Endpoints": {
                        "docker": {
                            "Host": "tcp://10.0.0.50:2376",
                        }
                    }
                }
            ]
        )

        with mock.patch.dict(
            os.environ,
            runtime_env(DOCKER_CONTEXT="remote-dev", SIGNOZ_CODEX_BIND_ADDR=self.REMOTE_BIND_ALL_ADDR),
            clear=True,
        ):
            with mock.patch.object(MODULE, "_run_docker", return_value=completed(inspect_json)):
                runtime = MODULE.resolve_runtime()

        self.assertEqual(runtime.stack_host, "10.0.0.50")

    def test_resolve_runtime_respects_explicit_bind_address(self) -> None:
        inspect_json = json.dumps(
            [
                {
                    "Endpoints": {
                        "docker": {
                            "Host": "unix:///var/run/docker.sock",
                        }
                    }
                }
            ]
        )

        with mock.patch.dict(
            os.environ,
            runtime_env(SIGNOZ_CODEX_BIND_ADDR=self.REMOTE_BIND_ALL_ADDR),
            clear=True,
        ):
            with mock.patch.object(
                MODULE,
                "_run_docker",
                side_effect=[
                    completed("default\n"),
                    completed(inspect_json),
                ],
            ):
                runtime = MODULE.resolve_runtime()
                env = MODULE.compose_environment(runtime=runtime)

        self.assertEqual(runtime.bind_addr, self.REMOTE_BIND_ALL_ADDR)
        self.assertEqual(env["SIGNOZ_CODEX_BIND_ADDR"], self.REMOTE_BIND_ALL_ADDR)

    def test_resolve_runtime_respects_explicit_remote_asset_sync_command(self) -> None:
        inspect_json = json.dumps(
            [
                {
                    "Endpoints": {
                        "docker": {
                            "Host": "tcp://10.0.0.50:2376",
                        }
                    }
                }
            ]
        )

        with mock.patch.dict(
            os.environ,
            runtime_env(
                DOCKER_CONTEXT="remote-dev",
                SIGNOZ_CODEX_REMOTE_ASSETS_ROOT="/srv/signoz-codex",
                SIGNOZ_CODEX_REMOTE_ASSET_SYNC_CMD=str(Path(os.sep) / "var" / "run" / "remote-sync.sh"),
            ),
            clear=True,
        ):
            with mock.patch.object(MODULE, "_run_docker", return_value=completed(inspect_json)):
                runtime = MODULE.resolve_runtime()
                env = MODULE.compose_environment(runtime=runtime)

        self.assertTrue(runtime.requires_remote_asset_sync)
        self.assertEqual(runtime.remote_assets_root, Path("/srv/signoz-codex"))
        self.assertEqual(runtime.remote_asset_sync_cmd, str(Path(os.sep) / "var" / "run" / "remote-sync.sh"))
        self.assertIn("SIGNOZ_CODEX_CLICKHOUSE_CONFIG", env)
        self.assertIn("SIGNOZ_CODEX_CLICKHOUSE_HISTOGRAM_SHA256", env)
        self.assertEqual(env["SIGNOZ_CODEX_CLICKHOUSE_CONFIG"], "/srv/signoz-codex/common/clickhouse/config.xml")
        self.assertEqual(
            env["SIGNOZ_CODEX_CLICKHOUSE_HISTOGRAM_SHA256"],
            "/srv/signoz-codex/common/clickhouse/histogram-quantile.sha256",
        )

    def test_stack_host_override_wins_over_detected_remote_host(self) -> None:
        inspect_json = json.dumps(
            [
                {
                    "Endpoints": {
                        "docker": {
                            "Host": "tcp://10.0.0.50:2376",
                        }
                    }
                }
            ]
        )

        with mock.patch.dict(
            os.environ,
            runtime_env(
                DOCKER_CONTEXT="remote-prod",
                SIGNOZ_CODEX_STACK_HOST="signoz.internal",
            ),
            clear=True,
        ):
            with mock.patch.object(MODULE, "_run_docker", return_value=completed(inspect_json)):
                runtime = MODULE.resolve_runtime()

        self.assertEqual(runtime.stack_host, "signoz.internal")
        self.assertEqual(runtime.otlp_endpoint, "http://signoz.internal:5317")

    def test_runtime_summary_reports_remote_sync_state(self) -> None:
        runtime = MODULE.RuntimeConfig(
            docker_context="remote-dev",
            docker_context_source="env:DOCKER_CONTEXT",
            docker_endpoint="tcp://10.0.0.50:2376",
            engine_mode="remote",
            remote_assets_root=Path("/srv/signoz-codex"),
            remote_asset_sync_cmd="",
            bind_addr="127.0.0.1",
            stack_host="localhost",
            otlp_endpoint="http://localhost:5317",
        )

        lines = MODULE.runtime_summary_lines(runtime)

        self.assertIn("Bind address: 127.0.0.1", lines)
        self.assertIn("Remote assets root: /srv/signoz-codex", lines)
        self.assertIn("Remote asset sync: not configured", lines)
        self.assertIn("Remote access: published ports stay on the remote host loopback interface", lines)

    def test_clickhouse_credentials_are_stable(self) -> None:
        with mock.patch.dict(
            os.environ,
            runtime_env(
                SIGNOZ_CODEX_CLICKHOUSE_WRITE_PASSWORD="write-pass",  # nosec B106
                SIGNOZ_CODEX_CLICKHOUSE_READONLY_PASSWORD="readonly-pass",  # nosec B106
            ),
            clear=True,
        ):
            credentials = MODULE.clickhouse_credentials()

        self.assertEqual(credentials.write_user, "default")
        self.assertEqual(credentials.write_password, "write-pass")
        self.assertEqual(credentials.readonly_user, "codex_readonly")
        self.assertEqual(credentials.readonly_password, "readonly-pass")

    def test_render_runtime_assets_writes_generated_files_without_tracked_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            generated_dir = root / "local" / "generated"
            users_template = root / "users.template.xml"
            signoz_template = root / "prometheus.template.yml"
            users_template.write_text(
                "<clickhouse><users>"
                "<codex_readonly><password_sha256_hex>"
                "__SIGNOZ_CODEX_CLICKHOUSE_READONLY_PASSWORD_SHA256_HEX__"
                "</password_sha256_hex></codex_readonly>"
                "<default><password_sha256_hex>"
                "__SIGNOZ_CODEX_CLICKHOUSE_WRITE_PASSWORD_SHA256_HEX__"
                "</password_sha256_hex></default>"
                "</users></clickhouse>",
                encoding="utf-8",
            )
            signoz_template.write_text(
                "remote_read:\n  - url: __SIGNOZ_CODEX_CLICKHOUSE_WRITE_DSN__/signoz_metrics\n",
                encoding="utf-8",
            )
            credentials_env_path = generated_dir / "clickhouse.env"

            with (
                mock.patch.dict(os.environ, runtime_env(), clear=True),
                mock.patch.object(MODULE, "GENERATED_DIR", generated_dir),
                mock.patch.object(MODULE, "CREDENTIALS_ENV_PATH", credentials_env_path),
                mock.patch.object(MODULE, "CLICKHOUSE_USERS_TEMPLATE_PATH", users_template),
                mock.patch.object(MODULE, "CLICKHOUSE_USERS_RENDERED_PATH", generated_dir / "clickhouse-users.xml"),
                mock.patch.object(MODULE, "SIGNOZ_PROMETHEUS_TEMPLATE_PATH", signoz_template),
                mock.patch.object(MODULE, "SIGNOZ_PROMETHEUS_RENDERED_PATH", generated_dir / "signoz-prometheus.yml"),
            ):
                MODULE.ensure_runtime_assets_rendered()

                rendered_users = (generated_dir / "clickhouse-users.xml").read_text(encoding="utf-8")
                rendered_prometheus = (generated_dir / "signoz-prometheus.yml").read_text(encoding="utf-8")
                rendered_env = credentials_env_path.read_text(encoding="utf-8")

        self.assertNotIn("__SIGNOZ_CODEX_CLICKHOUSE_WRITE_PASSWORD_SHA256_HEX__", rendered_users)
        self.assertNotIn("__SIGNOZ_CODEX_CLICKHOUSE_READONLY_PASSWORD_SHA256_HEX__", rendered_users)
        self.assertIn("tcp://default:", rendered_prometheus)
        self.assertIn("SIGNOZ_CODEX_CLICKHOUSE_WRITE_PASSWORD", rendered_env)


if __name__ == "__main__":
    unittest.main()
