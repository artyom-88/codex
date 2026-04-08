from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from test_support import load_script_module

MODULE = load_script_module("query_clickhouse", "query_clickhouse.py")


class CredentialsStub:
    write_user = "default"
    readonly_user = "codex_readonly"

    @property
    def write_password(self) -> str:
        return "writer1"

    @property
    def readonly_password(self) -> str:
        return "reader1"


class QueryClickhouseTests(unittest.TestCase):
    def test_apply_output_format_preserves_existing_format(self) -> None:
        query = "SELECT 1 FORMAT Vertical"
        self.assertEqual(MODULE.apply_output_format(query, "TSV"), query)

    def test_apply_output_format_ignores_format_in_string_literal(self) -> None:
        query = "SELECT 'FORMAT' AS label"
        self.assertEqual(MODULE.apply_output_format(query, "TSV"), "SELECT 'FORMAT' AS label FORMAT TSV")

    def test_apply_output_format_ignores_format_in_comment(self) -> None:
        query = "SELECT 1 /* FORMAT TSV */"
        self.assertEqual(
            MODULE.apply_output_format(query, "JSONEachRow"),
            "SELECT 1 /* FORMAT TSV */ FORMAT JSONEachRow",
        )

    def test_has_trailing_top_level_format_clause_requires_terminal_clause(self) -> None:
        self.assertTrue(MODULE.has_trailing_top_level_format_clause("SELECT 1 FORMAT Vertical"))
        self.assertFalse(MODULE.has_trailing_top_level_format_clause("SELECT format FROM metrics"))
        self.assertFalse(MODULE.has_trailing_top_level_format_clause("SELECT 'FORMAT' AS label"))

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

    def test_main_uses_readonly_clickhouse_client_args(self) -> None:
        with (
            mock.patch.object(MODULE, "clickhouse_client_args", return_value=["docker", "compose"]) as client_args,
            mock.patch.object(MODULE, "compose_environment", return_value={}),
            mock.patch.object(MODULE.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run,
        ):
            self.assertEqual(MODULE.main(["--readonly", "SELECT 1"]), 0)

        client_args.assert_called_once_with(readonly=True)
        self.assertEqual(run.call_args.args[0], ["docker", "compose", "--query=SELECT 1"])

    def test_main_uses_write_clickhouse_client_args_for_sql(self) -> None:
        with (
            mock.patch.object(MODULE, "clickhouse_client_args", return_value=["docker", "compose"]) as client_args,
            mock.patch.object(MODULE, "compose_environment", return_value={}),
            mock.patch.object(MODULE.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run,
        ):
            self.assertEqual(MODULE.main(["SELECT 1"]), 0)

        client_args.assert_called_once_with(readonly=False)
        self.assertEqual(run.call_args.args[0], ["docker", "compose", "--query=SELECT 1"])


if __name__ == "__main__":
    unittest.main()
