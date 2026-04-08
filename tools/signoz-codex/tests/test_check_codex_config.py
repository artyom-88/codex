from __future__ import annotations

import contextlib
import io
import unittest

from test_support import load_script_module

MODULE = load_script_module("check_codex_config", "check_codex_config.py")


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
