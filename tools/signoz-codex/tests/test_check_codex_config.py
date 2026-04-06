from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_codex_config.py"
SPEC = importlib.util.spec_from_file_location("check_codex_config", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CheckCodexConfigTests(unittest.TestCase):
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
