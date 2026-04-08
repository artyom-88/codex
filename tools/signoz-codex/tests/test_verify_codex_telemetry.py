from __future__ import annotations

import contextlib
import io
import unittest

from test_support import load_script_module

MODULE = load_script_module("verify_codex_telemetry", "verify_codex_telemetry.py")


class VerifyCodexTelemetryTests(unittest.TestCase):
    def test_sql_string_escapes_literals(self) -> None:
        self.assertEqual(MODULE.sql_string("codex_cli_rs"), "'codex_cli_rs'")
        self.assertEqual(MODULE.sql_string("codex'cli\\rs"), "'codex\\'cli\\\\rs'")

    def test_print_rows_uses_section_specific_empty_message(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            MODULE.print_rows("Tool Calls", [], ["tool", "calls"], "no tool-call metrics in the selected window")

        output = buffer.getvalue()
        self.assertIn("Tool Calls", output)
        self.assertIn("no tool-call metrics in the selected window", output)
        self.assertNotIn("no data", output)

    def test_parse_count_handles_empty_result(self) -> None:
        self.assertEqual(MODULE.parse_count([]), 0)
        self.assertEqual(MODULE.parse_count(["42"]), 42)

    def test_compose_failure_message_handles_stopped_stack(self) -> None:
        error = MODULE.subprocess.CalledProcessError(
            returncode=1,
            cmd=["docker", "compose", "exec"],
            stderr='service "clickhouse" is not running\n',
        )

        message = MODULE.compose_failure_message(error)
        self.assertIn("stack is not running", message)
        self.assertIn("./scripts/signoz-codex start", message)

    def test_compose_failure_message_handles_connectivity_errors(self) -> None:
        error = MODULE.subprocess.CalledProcessError(
            returncode=1,
            cmd=["docker", "compose", "exec"],
            stderr="connection refused\n",
        )

        message = MODULE.compose_failure_message(error)
        self.assertIn("not reachable yet", message)
        self.assertIn("./scripts/signoz-codex health", message)


if __name__ == "__main__":
    unittest.main()
