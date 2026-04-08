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
            mock.patch.object(MODULE, "compose_args", return_value=["docker", "compose"]),
            mock.patch.object(MODULE, "compose_environment", return_value={}),
            mock.patch.object(MODULE.subprocess, "run", return_value=SimpleNamespace(returncode=0)),
            mock.patch.object(MODULE, "_check_http_health", return_value=True),
            mock.patch.object(MODULE, "_check_port", side_effect=[True, True]),
        ):
            self.assertEqual(MODULE.health_check(runtime), 0)

    def test_health_check_returns_nonzero_when_any_probe_fails(self) -> None:
        runtime = SimpleNamespace()
        with (
            contextlib.redirect_stdout(io.StringIO()),
            mock.patch.object(MODULE, "stack_host", return_value="localhost"),
            mock.patch.object(MODULE, "compose_args", return_value=["docker", "compose"]),
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


if __name__ == "__main__":
    unittest.main()
