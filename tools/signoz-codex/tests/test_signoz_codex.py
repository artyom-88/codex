from __future__ import annotations

import contextlib
import io
import unittest
from types import SimpleNamespace
from unittest import mock

from test_support import load_script_module

MODULE = load_script_module("signoz_codex", "signoz_codex.py")


class SignozCodexTests(unittest.TestCase):
    def test_health_check_returns_zero_when_all_probes_pass(self) -> None:
        runtime = SimpleNamespace()
        with (
            contextlib.redirect_stdout(io.StringIO()),
            mock.patch.object(MODULE, "stack_host", return_value="localhost"),
            mock.patch.object(MODULE, "clickhouse_client_args", return_value=["docker", "compose"]) as client_args,
            mock.patch.object(MODULE, "compose_environment", return_value={}),
            mock.patch.object(MODULE.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run,
            mock.patch.object(MODULE, "_check_http_health", return_value=True),
            mock.patch.object(MODULE, "_check_port", side_effect=[True, True]),
        ):
            self.assertEqual(MODULE.health_check(runtime), 0)
        client_args.assert_called_once_with("--query=SELECT 1", runtime=runtime)
        self.assertEqual(run.call_args.args[0], ["docker", "compose"])

    def test_health_check_returns_nonzero_when_any_probe_fails(self) -> None:
        runtime = SimpleNamespace()
        with (
            contextlib.redirect_stdout(io.StringIO()),
            mock.patch.object(MODULE, "stack_host", return_value="localhost"),
            mock.patch.object(MODULE, "clickhouse_client_args", return_value=["docker", "compose"]),
            mock.patch.object(MODULE, "compose_environment", return_value={}),
            mock.patch.object(MODULE.subprocess, "run", return_value=SimpleNamespace(returncode=0)),
            mock.patch.object(MODULE, "_check_http_health", return_value=False),
            mock.patch.object(MODULE, "_check_port", side_effect=[True, True]),
        ):
            self.assertEqual(MODULE.health_check(runtime), 1)

    def test_doctor_returns_health_failure_without_running_verify(self) -> None:
        runtime = SimpleNamespace()
        with (
            contextlib.redirect_stdout(io.StringIO()),
            mock.patch.object(MODULE, "check_codex_config", return_value=0),
            mock.patch.object(MODULE, "health_check", return_value=1),
            mock.patch.object(MODULE, "verify_telemetry") as verify_telemetry,
        ):
            self.assertEqual(MODULE.doctor(runtime, minutes=30), 1)
        verify_telemetry.assert_not_called()

    def test_start_services_returns_nonzero_when_services_remain_unhealthy(self) -> None:
        runtime = SimpleNamespace()
        with (
            contextlib.redirect_stdout(io.StringIO()),
            mock.patch.object(
                MODULE,
                "run_local_script",
                return_value=SimpleNamespace(returncode=0, stdout="", stderr=""),
            ),
            mock.patch.object(MODULE, "ensure_runtime_assets", return_value=False),
            mock.patch.object(MODULE, "are_all_running", return_value=False),
            mock.patch.object(MODULE, "run_compose"),
            mock.patch.object(MODULE, "show_status", return_value=0),
            mock.patch.object(MODULE.time, "sleep"),
        ):
            self.assertEqual(MODULE.start_services(runtime, force=False), 1)

    def test_start_services_returns_status_code_when_services_become_healthy(self) -> None:
        runtime = SimpleNamespace()
        with (
            contextlib.redirect_stdout(io.StringIO()),
            mock.patch.object(
                MODULE,
                "run_local_script",
                return_value=SimpleNamespace(returncode=0, stdout="", stderr=""),
            ),
            mock.patch.object(MODULE, "ensure_runtime_assets", return_value=False),
            mock.patch.object(MODULE, "are_all_running", side_effect=[False, False, True, True]),
            mock.patch.object(MODULE, "run_compose"),
            mock.patch.object(MODULE, "show_status", return_value=0),
            mock.patch.object(MODULE.time, "sleep"),
        ):
            self.assertEqual(MODULE.start_services(runtime, force=False), 0)

    def test_start_services_force_recreates_when_remote_assets_refresh(self) -> None:
        runtime = SimpleNamespace()
        with (
            contextlib.redirect_stdout(io.StringIO()),
            mock.patch.object(
                MODULE,
                "run_local_script",
                return_value=SimpleNamespace(returncode=0, stdout="", stderr=""),
            ),
            mock.patch.object(MODULE, "ensure_runtime_assets", return_value=True) as ensure_runtime_assets,
            mock.patch.object(MODULE, "are_all_running", side_effect=[False, True, True]),
            mock.patch.object(MODULE, "run_compose") as run_compose,
            mock.patch.object(MODULE, "show_status", return_value=0),
            mock.patch.object(MODULE.time, "sleep"),
        ):
            self.assertEqual(MODULE.start_services(runtime, force=False), 0)

        ensure_runtime_assets.assert_called_once_with(runtime, required=False)
        run_compose.assert_called_once_with(runtime, "up", "-d", "--force-recreate")


if __name__ == "__main__":
    unittest.main()
