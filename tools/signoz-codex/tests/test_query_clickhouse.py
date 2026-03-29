from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "query_clickhouse.py"
SPEC = importlib.util.spec_from_file_location("query_clickhouse", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class QueryClickhouseTests(unittest.TestCase):
    def test_apply_output_format_preserves_existing_format(self) -> None:
        query = "SELECT 1 FORMAT Vertical"
        self.assertEqual(MODULE.apply_output_format(query, "TSV"), query)

    def test_apply_output_format_appends_format(self) -> None:
        self.assertEqual(MODULE.apply_output_format("SELECT 1;", "TSV"), "SELECT 1 FORMAT TSV")

    def test_load_query_from_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "query.sql"
            path.write_text("SELECT 42", encoding="utf-8")
            args = MODULE.parse_args(["--file", str(path)])
            self.assertEqual(MODULE.load_query(args), "SELECT 42")


if __name__ == "__main__":
    unittest.main()
