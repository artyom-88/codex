from __future__ import annotations

import json
import os
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
        self.assertEqual(env["SIGNOZ_CODEX_CLICKHOUSE_CONFIG"], "/srv/signoz-codex/common/clickhouse/config.xml")

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
            stack_host="10.0.0.50",
            otlp_endpoint="http://10.0.0.50:5317",
        )

        lines = MODULE.runtime_summary_lines(runtime)

        self.assertIn("Bind address: 127.0.0.1", lines)
        self.assertIn("Remote assets root: /srv/signoz-codex", lines)
        self.assertIn("Remote asset sync: not configured", lines)


if __name__ == "__main__":
    unittest.main()
