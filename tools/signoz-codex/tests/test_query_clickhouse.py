from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test_support import load_script_module

MODULE = load_script_module("query_clickhouse", "query_clickhouse.py")


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

    def test_split_sql_statements_ignores_semicolons_in_strings(self) -> None:
        statements = MODULE.split_sql_statements("SELECT ';' AS semi; SELECT 2")
        self.assertEqual(statements, ["SELECT ';' AS semi", "SELECT 2"])

    def test_validate_readonly_query_accepts_select_and_show(self) -> None:
        MODULE.validate_readonly_query("SELECT 1; SHOW TABLES")

    def test_validate_readonly_query_accepts_cte_select(self) -> None:
        MODULE.validate_readonly_query("WITH numbers AS (SELECT 1) SELECT * FROM numbers")

    def test_validate_readonly_query_rejects_insert(self) -> None:
        with self.assertRaises(SystemExit) as error:
            MODULE.validate_readonly_query("INSERT INTO t SELECT 1")
        self.assertIn("sql-read only allows read queries", str(error.exception))

    def test_validate_readonly_query_rejects_write_in_multiquery(self) -> None:
        with self.assertRaises(SystemExit) as error:
            MODULE.validate_readonly_query("SELECT 1; DROP TABLE t")
        self.assertIn("DROP TABLE t", str(error.exception))


if __name__ == "__main__":
    unittest.main()
