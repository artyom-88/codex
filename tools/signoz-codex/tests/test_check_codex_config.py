from __future__ import annotations

import contextlib
import io
import unittest

from test_support import load_script_module

MODULE = load_script_module("check_codex_config", "check_codex_config.py")


class CheckCodexConfigTests(unittest.TestCase):
    def test_normalize_otlp_endpoint_treats_loopback_hosts_as_equivalent(self) -> None:
        self.assertEqual(
            MODULE.normalize_otlp_endpoint("http://127.0.0.1:5317/"),
            MODULE.normalize_otlp_endpoint("http://localhost:5317"),
        )

    def test_check_exporter_accepts_equivalent_loopback_endpoint(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            warnings, errors = MODULE.check_exporter(
                "exporter",
                {"otlp-grpc": {"endpoint": "http://127.0.0.1:5317/"}},
                quiet=False,
                expected="http://localhost:5317",
            )

        self.assertEqual((warnings, errors), (0, 0))
        self.assertIn("exporter endpoint is http://localhost:5317", buffer.getvalue())

    def test_check_exporter_rejects_different_endpoint(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            warnings, errors = MODULE.check_exporter(
                "exporter",
                {"otlp-grpc": {"endpoint": "http://localhost:4317"}},
                quiet=False,
                expected="http://localhost:5317",
            )

        self.assertEqual((warnings, errors), (0, 1))
        self.assertIn("expected 'http://localhost:5317'", buffer.getvalue())

    def test_check_log_user_prompt_false_is_informational(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            warnings = MODULE.check_log_user_prompt(False, quiet=False)

        self.assertEqual(warnings, 0)
        self.assertIn("log_user_prompt is false", buffer.getvalue())
        self.assertNotIn("!", buffer.getvalue())

    def test_check_log_user_prompt_unset_warns(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            warnings = MODULE.check_log_user_prompt(None, quiet=False)

        self.assertEqual(warnings, 1)
        self.assertIn("log_user_prompt is unset", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
