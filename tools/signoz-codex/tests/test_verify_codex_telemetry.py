from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "verify_codex_telemetry.py"
SPEC = importlib.util.spec_from_file_location("verify_codex_telemetry", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


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


if __name__ == "__main__":
    unittest.main()
