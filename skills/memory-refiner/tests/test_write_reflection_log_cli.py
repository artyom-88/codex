from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from contextlib import redirect_stdout
from pathlib import Path

from test_support import load_script_module

WRITE_MODULE = load_script_module("write_reflection_log_cli", "write_reflection_log.py")
REFLECTION_MODULE = load_script_module("reflection_log_cli_e2e", "reflection_log.py")


class WriteReflectionLogCliTests(unittest.TestCase):
    @contextmanager
    def create_project(self):
        temp_dir = tempfile.TemporaryDirectory()
        try:
            root = Path(temp_dir.name)
            codex_home = root / "codex-home"
            project_root = root / "project"
            project_root.mkdir(parents=True)
            (project_root / "AGENTS.md").write_text("# project\n", encoding="utf-8")
            yield temp_dir, codex_home, project_root
        finally:
            temp_dir.cleanup()

    def run_cli(
        self,
        args: list[str],
        *,
        stdin_text: str = "",
    ) -> tuple[int, str]:
        original_argv = sys.argv
        original_stdin = sys.stdin
        stdout = io.StringIO()
        try:
            sys.argv = ["write_reflection_log.py", *args]
            sys.stdin = io.StringIO(stdin_text)
            with redirect_stdout(stdout):
                exit_code = WRITE_MODULE.main()
        finally:
            sys.argv = original_argv
            sys.stdin = original_stdin
        return exit_code, stdout.getvalue()

    def start_run(
        self,
        *,
        codex_home: Path,
        project_root: Path,
        summary: str,
        format_position: str = "before",
    ) -> dict[str, str]:
        args = [
            "--codex-home",
            str(codex_home),
            "--cwd",
            str(project_root),
        ]
        if format_position == "before":
            args.extend(["--format", "json", "start"])
        else:
            args.extend(["start", "--format", "json"])
        args.extend(["--user-request-summary", summary])
        exit_code, output = self.run_cli(args)
        self.assertEqual(exit_code, 0)
        return json.loads(output)

    def finalize_run(
        self,
        *,
        codex_home: Path,
        project_root: Path,
        payload: str,
    ) -> dict[str, str]:
        exit_code, output = self.run_cli(
            [
                "--codex-home",
                str(codex_home),
                "--cwd",
                str(project_root),
                "--format",
                "json",
                "finalize",
                "--input",
                "-",
            ],
            stdin_text=payload,
        )
        self.assertEqual(exit_code, 0)
        return json.loads(output)

    def test_start_accepts_format_after_subcommand(self) -> None:
        with self.create_project() as (_temp_dir, codex_home, project_root):
            payload = self.start_run(
                codex_home=codex_home,
                project_root=project_root,
                summary="smoke start",
                format_position="after",
            )
            run_dir = Path(payload["run_dir"])
            active_record_path = Path(payload["active_record"])
            self.assertTrue(run_dir.exists())
            self.assertTrue((run_dir / "events.jsonl").exists())
            self.assertTrue(active_record_path.exists())
            active_record = json.loads(active_record_path.read_text(encoding="utf-8"))
            self.assertEqual(active_record["run_id"], payload["run_id"])
            self.assertEqual(active_record["run_dir"], str(run_dir))
            self.assertEqual(active_record["project_name"], "project")

    def test_cli_lifecycle_persists_files_for_custom_codex_home(self) -> None:
        with self.create_project() as (_temp_dir, codex_home, project_root):
            start_payload = self.start_run(
                codex_home=codex_home,
                project_root=project_root,
                summary="full lifecycle",
            )
            run_dir = Path(start_payload["run_dir"])
            active_record = Path(start_payload["active_record"])
            self.assertTrue(run_dir.exists())
            self.assertTrue((run_dir / "events.jsonl").exists())
            self.assertTrue(active_record.exists())

            event_code, event_output = self.run_cli(
                [
                    "--codex-home",
                    str(codex_home),
                    "--cwd",
                    str(project_root),
                    "event",
                    "--format",
                    "json",
                    "--stage",
                    "evidence",
                    "--input",
                    "-",
                ],
                stdin_text='{"summary":"event payload"}',
            )
            self.assertEqual(event_code, 0)
            event_payload = json.loads(event_output)
            self.assertEqual(event_payload["stage"], "evidence")

            finalize_payload = self.finalize_run(
                codex_home=codex_home,
                project_root=project_root,
                payload=(
                    '{"user_request_summary":"full lifecycle",'
                    '"history_summary":{"entries":1},'
                    '"memory_surface_summary":{"files":["AGENTS.md"]},'
                    '"recommendations":[]}'
                ),
            )
            summary_file = Path(finalize_payload["summary_file"])
            self.assertTrue(summary_file.exists())
            self.assertFalse(active_record.exists())

            summary = json.loads(summary_file.read_text(encoding="utf-8"))
            self.assertEqual(summary["final_status"], "completed")
            self.assertEqual(summary["recommendations"], [])

    def test_second_start_supersedes_previous_run(self) -> None:
        with self.create_project() as (_temp_dir, codex_home, project_root):
            first_payload = self.start_run(
                codex_home=codex_home,
                project_root=project_root,
                summary="supersede one",
            )
            first_run_dir = Path(first_payload["run_dir"])

            second_payload = self.start_run(
                codex_home=codex_home,
                project_root=project_root,
                summary="supersede two",
            )
            second_run_dir = Path(second_payload["run_dir"])

            first_events, invalid = REFLECTION_MODULE.load_events(first_run_dir)
            self.assertEqual(invalid, [])
            self.assertEqual(first_events[0]["event_type"], "start")
            self.assertEqual(first_events[-1]["event_type"], "interrupted")
            self.assertTrue(second_run_dir.exists())

            active_record = json.loads(Path(second_payload["active_record"]).read_text(encoding="utf-8"))
            self.assertEqual(active_record["run_id"], second_payload["run_id"])
            self.assertEqual(active_record["run_dir"], str(second_run_dir))


if __name__ == "__main__":
    unittest.main()
