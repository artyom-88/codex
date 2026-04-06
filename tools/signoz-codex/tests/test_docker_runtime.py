from __future__ import annotations

import importlib.util
import json
import os
import sys
import unittest
from unittest import mock
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "docker_runtime.py"
SPEC = importlib.util.spec_from_file_location("docker_runtime", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def completed(stdout: str = "", returncode: int = 0) -> mock.Mock:
    result = mock.Mock()
    result.stdout = stdout
    result.returncode = returncode
    return result


class DockerRuntimeTests(unittest.TestCase):
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

        with mock.patch.dict(os.environ, {}, clear=False):
            with mock.patch.object(
                MODULE,
                "_run_docker",
                side_effect=[
                    completed("default\n"),
                    completed("default\n"),
                    completed(inspect_json),
                ],
            ):
                runtime = MODULE.resolve_runtime()

        self.assertEqual(runtime.docker_context, "default")
        self.assertEqual(runtime.engine_mode, "local")
        self.assertEqual(runtime.remote_asset_strategy, "none")
        self.assertEqual(runtime.stack_host, "localhost")

    def test_resolve_runtime_falls_back_to_reachable_minikube_context(self) -> None:
        inspect_json = json.dumps(
            [
                {
                    "Endpoints": {
                        "docker": {
                            "Host": "tcp://192.168.64.4:2376",
                        }
                    }
                }
            ]
        )

        with mock.patch.dict(os.environ, {}, clear=False):
            with mock.patch.object(
                MODULE,
                "_run_docker",
                side_effect=[
                    completed("default\n"),
                    completed("default\nminikube-vfkit\n"),
                    completed("", 0),
                    completed(inspect_json),
                ],
            ):
                runtime = MODULE.resolve_runtime()

        self.assertEqual(runtime.docker_context, "minikube-vfkit")
        self.assertEqual(runtime.docker_context_source, "fallback:reachable minikube context")
        self.assertEqual(runtime.remote_asset_strategy, "minikube-sync")
        self.assertEqual(runtime.stack_host, "localhost")

    def test_resolve_runtime_auto_detects_minikube_remote_context(self) -> None:
        inspect_json = json.dumps(
            [
                {
                    "Endpoints": {
                        "docker": {
                            "Host": "tcp://192.168.64.4:2376",
                        }
                    }
                }
            ]
        )

        with mock.patch.dict(os.environ, {"DOCKER_CONTEXT": "minikube-vfkit"}, clear=False):
            with mock.patch.object(MODULE, "_run_docker", return_value=completed(inspect_json)):
                runtime = MODULE.resolve_runtime()

        self.assertEqual(runtime.docker_context, "minikube-vfkit")
        self.assertEqual(runtime.engine_mode, "remote")
        self.assertEqual(runtime.remote_asset_strategy, "minikube-sync")
        self.assertEqual(runtime.minikube_profile, "vfkit")
        self.assertEqual(runtime.stack_host, "localhost")

    def test_resolve_runtime_uses_endpoint_host_for_generic_remote_context(self) -> None:
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

        with mock.patch.dict(os.environ, {}, clear=False):
            with mock.patch.object(
                MODULE,
                "_run_docker",
                side_effect=[
                    completed("remote-prod\n"),
                    completed(inspect_json),
                ],
            ):
                runtime = MODULE.resolve_runtime()

        self.assertEqual(runtime.docker_context, "remote-prod")
        self.assertEqual(runtime.engine_mode, "remote")
        self.assertEqual(runtime.remote_asset_strategy, "none")
        self.assertEqual(runtime.stack_host, "10.0.0.50")

    def test_compose_environment_only_rewrites_bind_mounts_for_minikube_sync(self) -> None:
        inspect_json = json.dumps(
            [
                {
                    "Endpoints": {
                        "docker": {
                            "Host": "tcp://192.168.64.4:2376",
                        }
                    }
                }
            ]
        )

        with mock.patch.dict(os.environ, {"DOCKER_CONTEXT": "minikube-vfkit"}, clear=False):
            with mock.patch.object(MODULE, "_run_docker", return_value=completed(inspect_json)):
                runtime = MODULE.resolve_runtime()
                env = MODULE.compose_environment(runtime=runtime)

        self.assertIn("SIGNOZ_CODEX_CLICKHOUSE_CONFIG", env)
        self.assertTrue(env["SIGNOZ_CODEX_CLICKHOUSE_CONFIG"].endswith("/common/clickhouse/config.xml"))

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
            {
                "DOCKER_CONTEXT": "remote-prod",
                "SIGNOZ_CODEX_STACK_HOST": "signoz.internal",
            },
            clear=False,
        ):
            with mock.patch.object(MODULE, "_run_docker", return_value=completed(inspect_json)):
                runtime = MODULE.resolve_runtime()

        self.assertEqual(runtime.stack_host, "signoz.internal")
        self.assertEqual(runtime.otlp_endpoint, "http://signoz.internal:5317")


if __name__ == "__main__":
    unittest.main()
