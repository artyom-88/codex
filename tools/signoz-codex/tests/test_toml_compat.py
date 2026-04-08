from __future__ import annotations

import types
import unittest

from test_support import load_script_module

MODULE = load_script_module("toml_compat", "toml_compat.py")


class TomlCompatTests(unittest.TestCase):
    def test_load_toml_module_prefers_tomllib(self) -> None:
        sentinel = types.SimpleNamespace(TOMLDecodeError=ValueError)

        def fake_import(name: str) -> object:
            if name == "tomllib":
                return sentinel
            raise AssertionError(f"unexpected import: {name}")

        self.assertIs(MODULE.load_toml_module(fake_import), sentinel)

    def test_load_toml_module_falls_back_to_tomli(self) -> None:
        sentinel = types.SimpleNamespace(TOMLDecodeError=ValueError)

        def fake_import(name: str) -> object:
            if name == "tomllib":
                raise ModuleNotFoundError(name)
            if name == "tomli":
                return sentinel
            raise AssertionError(f"unexpected import: {name}")

        self.assertIs(MODULE.load_toml_module(fake_import), sentinel)

    def test_load_toml_module_raises_helpful_error_without_parser(self) -> None:
        def fake_import(name: str) -> object:
            raise ModuleNotFoundError(name)

        with self.assertRaises(RuntimeError) as error:
            MODULE.load_toml_module(fake_import)

        self.assertIn("No TOML parser is available", str(error.exception))
        self.assertIn("tomli", str(error.exception))


if __name__ == "__main__":
    unittest.main()
