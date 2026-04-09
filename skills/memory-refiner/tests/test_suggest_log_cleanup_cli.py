from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

from test_support import load_script_module

MODULE = load_script_module("suggest_log_cleanup_cli", "suggest_log_cleanup.py")


class SuggestLogCleanupCliTests(unittest.TestCase):
    def run_cli(self, args: list[str]) -> tuple[int, str]:
        original_argv = sys.argv
        stdout = io.StringIO()
        try:
            sys.argv = ["suggest_log_cleanup.py", *args]
            with redirect_stdout(stdout):
                exit_code = MODULE.main()
        finally:
            sys.argv = original_argv
        return exit_code, stdout.getvalue()

    def test_delete_cleanup_candidates_skips_paths_outside_log_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            log_dir = root / "log"
            active_dir = root / "active"
            outside = root / "outside.txt"
            log_dir.mkdir()
            active_dir.mkdir()
            outside.write_text("keep me\n", encoding="utf-8")

            deleted, skipped = MODULE.delete_cleanup_candidates(
                [{"path": str(outside), "reason": "external"}],
                log_dir=log_dir,
                active_dir=active_dir,
            )

            self.assertEqual(deleted, [])
            self.assertEqual(skipped[0]["path"], str(outside))
            self.assertTrue(outside.exists())

    def test_apply_removes_stale_run_dirs_and_active_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home = root / "codex-home"
            log_dir = codex_home / "log" / "memory-refiner"
            active_dir = codex_home / "cache" / "memory-refiner" / "active"
            run_dir = log_dir / "20260201T120000Z-project-run123"
            run_dir.mkdir(parents=True)
            active_dir.mkdir(parents=True)

            old_timestamp = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat().replace("+00:00", "Z")
            stale_timestamp = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat().replace("+00:00", "Z")

            (run_dir / "summary.json").write_text(
                json.dumps(
                    {
                        "timestamp": old_timestamp,
                        "project_name": "project",
                        "project_key": "project-key",
                        "user_request_summary": "same request",
                        "recommendations": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            active_record = active_dir / "project-key.json"
            active_record.write_text(
                json.dumps(
                    {
                        "run_id": "run123",
                        "project_key": "project-key",
                        "project_name": "project",
                        "timestamp": stale_timestamp,
                        "run_dir": str(run_dir),
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            exit_code, output = self.run_cli(
                [
                    "--codex-home",
                    str(codex_home),
                    "--format",
                    "json",
                    "--apply",
                ]
            )

            self.assertEqual(exit_code, 0)
            payload = json.loads(output)
            self.assertTrue(payload["apply"])
            deleted_paths = {str(Path(path).resolve()) for path in payload["deleted_paths"]}
            self.assertIn(str(run_dir.resolve()), deleted_paths)
            self.assertIn(str(active_record.resolve()), deleted_paths)
            self.assertEqual(payload["skipped_paths"], [])
            self.assertFalse(run_dir.exists())
            self.assertFalse(active_record.exists())


if __name__ == "__main__":
    unittest.main()
