from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from test_support import load_script_module

MODULE = load_script_module("reflection_log", "reflection_log.py")


class ReflectionLogTests(unittest.TestCase):
    def test_build_summary_record_redacts_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home = root / "codex-home"
            project_root = root / "project"
            cwd = project_root / "nested"
            cwd.mkdir(parents=True)
            (project_root / "AGENTS.md").write_text("# project\n", encoding="utf-8")

            active_run = {
                "run_id": "run123",
                "project_key": "project-abc",
            }
            payload = {
                "user_request_summary": "Refine memory guidance for this repository",
                "history_summary": {"path": str(project_root / "private" / "notes.md")},
                "memory_surface_summary": {"root": str(project_root)},
                "recommendations": [
                    {
                        "scope": "global",
                        "target": str(project_root / "instructions" / "workflow" / "core.md"),
                        "priority": "medium",
                        "change_type": "modify",
                        "summary": "Clarify command form guidance",
                        "status": "approved",
                    },
                    {
                        "scope": "project-local",
                        "target": str(root / "outside" / "secret.txt"),
                        "priority": "low",
                        "change_type": "add",
                        "summary": "Keep this private",
                        "status": "rejected",
                    },
                ],
            }

            prepared_payload = MODULE.prepare_summary_payload(
                payload,
                cwd=cwd,
                codex_home=codex_home,
            )
            record = MODULE.build_summary_record(
                prepared_payload=prepared_payload,
                prior_logs=[],
                active_run=active_run,
                now=datetime(2026, 4, 8, 15, 0, tzinfo=timezone.utc),
            )

            serialized = json.dumps(record)
            self.assertEqual(record["project_name"], "project")
            self.assertEqual(record["recommendations"][0]["target"], "instructions/workflow/core.md")
            self.assertTrue(record["recommendations"][1]["target"].startswith("path-hash:"))
            self.assertNotIn(str(project_root), serialized)
            self.assertNotIn(str(root / "outside"), serialized)

    def test_paths_use_log_and_cache_roots(self) -> None:
        codex_home = Path("/Users/example/.codex")
        self.assertEqual(
            MODULE.resolve_log_dir(codex_home),
            codex_home / "log" / "memory-refiner",
        )
        self.assertEqual(
            MODULE.resolve_active_run_dir(codex_home),
            codex_home / "cache" / "memory-refiner" / "active",
        )

    def test_start_run_creates_project_key_and_dir_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir) / "project"
            cwd = project_root / "nested"
            cwd.mkdir(parents=True)
            (project_root / "AGENTS.md").write_text("# project\n", encoding="utf-8")

            start_record = MODULE.build_start_record(
                cwd=cwd,
                codex_home=Path(temp_dir) / "codex-home",
                user_request_summary="Refine skill behavior",
                now=datetime(2026, 4, 8, 15, 0, tzinfo=timezone.utc),
            )

            self.assertEqual(start_record["project_name"], "project")
            self.assertTrue(str(start_record["project_key"]).startswith("project-"))
            self.assertEqual(
                MODULE.run_dir_name(
                    datetime(2026, 4, 8, 15, 0, tzinfo=timezone.utc),
                    "Prompt Evaluator",
                    "abc123",
                ),
                "20260408T150000Z-prompt-evaluator-abc123",
            )

    def test_append_and_load_events_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "run"
            event = {
                "schema_version": MODULE.SCHEMA_VERSION,
                "run_id": "run1",
                "timestamp": "2026-04-08T15:00:00Z",
                "event_type": "stage",
                "stage": "evidence",
                "payload": {"summary": "ok"},
            }
            MODULE.append_event(run_dir, event)
            events, invalid = MODULE.load_events(run_dir)
            self.assertEqual(invalid, [])
            self.assertEqual(events, [event])

    def test_summarize_recent_logs_reports_repeated_outcomes(self) -> None:
        entries = [
            {
                "project_key": "repo-a-key",
                "project_name": "repo-a",
                "recommendations": [
                    {
                        "recommendation_id": "rec-1",
                        "target": "AGENTS.md",
                        "scope": "global",
                        "summary": "a",
                        "status": "applied",
                    },
                    {
                        "recommendation_id": "rec-2",
                        "target": "rules/global.rules",
                        "scope": "global",
                        "summary": "b",
                        "status": "rejected",
                    },
                ],
            },
            {
                "project_key": "repo-a-key",
                "project_name": "repo-a",
                "recommendations": [
                    {
                        "recommendation_id": "rec-1",
                        "target": "AGENTS.md",
                        "scope": "global",
                        "summary": "a",
                        "status": "applied",
                    },
                ],
            },
            {
                "project_key": "repo-b-key",
                "project_name": "repo-b",
                "recommendations": [
                    {
                        "recommendation_id": "rec-foreign",
                        "target": "README.md",
                        "scope": "project-local",
                        "summary": "ignore me",
                        "status": "rejected",
                    },
                ],
            },
        ]
        active_entries = [
            {
                "_timestamp": MODULE.utc_now(),
                "project_key": "repo-a-key",
                "project_name": "repo-a",
            },
            {
                "_timestamp": MODULE.parse_timestamp("2026-04-08T01:00:00Z"),
                "project_key": "repo-b-key",
                "project_name": "repo-b",
            },
        ]

        summary = MODULE.summarize_recent_logs(
            entries,
            project_key="repo-a-key",
            project_name="repo-a",
            limit=5,
            active_entries=active_entries,
        )
        self.assertEqual(summary["project_logs"], 2)
        self.assertEqual(summary["active_runs"], 1)
        self.assertEqual(summary["stale_active_runs"], 0)
        self.assertEqual(len(summary["repeated_recommendations"]), 2)
        self.assertEqual(summary["repeated_recommendations"][0]["recommendation_id"], "rec-1")
        self.assertEqual(
            summary["repeated_applied_recommendations"][0]["recommendation_id"],
            "rec-1",
        )
        self.assertEqual(
            summary["repeated_rejected_recommendations"][0]["recommendation_id"],
            "rec-2",
        )

    def test_build_reflection_signals_ignores_other_projects(self) -> None:
        recommendations = [
            {
                "recommendation_id": "rec-1",
                "target": "AGENTS.md",
                "scope": "global",
                "summary": "a",
                "status": "applied",
            }
        ]
        prior_logs = [
            {
                "project_key": "repo-a-key",
                "project_name": "repo-a",
                "recommendations": [
                    {
                        "recommendation_id": "rec-1",
                        "target": "AGENTS.md",
                        "scope": "global",
                        "summary": "a",
                        "status": "applied",
                    }
                ],
            },
            {
                "project_key": "repo-b-key",
                "project_name": "repo-b",
                "recommendations": [
                    {
                        "recommendation_id": "rec-1",
                        "target": "README.md",
                        "scope": "project-local",
                        "summary": "foreign",
                        "status": "rejected",
                    }
                ],
            },
        ]

        signals = MODULE.build_reflection_signals(recommendations, prior_logs, "repo-a-key", "repo-a")

        self.assertEqual(signals["prior_log_count"], 2)
        self.assertEqual(signals["prior_project_log_count"], 1)
        self.assertEqual(len(signals["repeated_recommendations"]), 1)
        self.assertEqual(signals["repeated_recommendations"][0]["recommendation_id"], "rec-1")
        self.assertEqual(len(signals["repeated_applied_recommendations"]), 1)
        self.assertEqual(signals["repeated_rejected_recommendations"], [])

    def test_summaries_use_project_key_when_repo_names_collide(self) -> None:
        entries = [
            {
                "project_key": "shared-aaa",
                "project_name": "shared",
                "recommendations": [
                    {
                        "recommendation_id": "rec-a",
                        "target": "AGENTS.md",
                        "scope": "global",
                        "summary": "keep",
                        "status": "applied",
                    }
                ],
            },
            {
                "project_key": "shared-bbb",
                "project_name": "shared",
                "recommendations": [
                    {
                        "recommendation_id": "rec-b",
                        "target": "README.md",
                        "scope": "project-local",
                        "summary": "ignore",
                        "status": "rejected",
                    }
                ],
            },
        ]
        active_entries = [
            {
                "_timestamp": MODULE.parse_timestamp("2026-04-08T15:00:00Z"),
                "project_key": "shared-aaa",
                "project_name": "shared",
            },
            {
                "_timestamp": MODULE.parse_timestamp("2026-04-08T01:00:00Z"),
                "project_key": "shared-bbb",
                "project_name": "shared",
            },
        ]

        summary = MODULE.summarize_recent_logs(
            entries,
            project_key="shared-aaa",
            project_name="shared",
            limit=5,
            active_entries=active_entries,
        )

        self.assertEqual(summary["project_logs"], 1)
        self.assertEqual(summary["active_runs"], 1)
        self.assertEqual(summary["repeated_recommendations"][0]["recommendation_id"], "rec-a")
        self.assertEqual(summary["repeated_rejected_recommendations"], [])

    def test_build_reflection_signals_ignore_same_named_other_repo(self) -> None:
        recommendations = [
            {
                "recommendation_id": "rec-a",
                "target": "AGENTS.md",
                "scope": "global",
                "summary": "keep",
                "status": "applied",
            }
        ]
        prior_logs = [
            {
                "project_key": "shared-aaa",
                "project_name": "shared",
                "recommendations": recommendations,
            },
            {
                "project_key": "shared-bbb",
                "project_name": "shared",
                "recommendations": [
                    {
                        "recommendation_id": "rec-a",
                        "target": "README.md",
                        "scope": "project-local",
                        "summary": "foreign",
                        "status": "rejected",
                    }
                ],
            },
        ]

        signals = MODULE.build_reflection_signals(recommendations, prior_logs, "shared-aaa", "shared")

        self.assertEqual(signals["prior_project_log_count"], 1)
        self.assertEqual(len(signals["repeated_recommendations"]), 1)
        self.assertEqual(len(signals["repeated_applied_recommendations"]), 1)
        self.assertEqual(signals["repeated_rejected_recommendations"], [])

    def test_cleanup_suggestions_flag_age_superseded_and_stale_active(self) -> None:
        now = datetime(2026, 4, 8, 15, 0, tzinfo=timezone.utc)
        old_timestamp = (now - timedelta(days=45)).isoformat().replace("+00:00", "Z")
        recent_timestamp = (now - timedelta(days=1)).isoformat().replace("+00:00", "Z")
        stale_entry = {
            "_run_dir": "old-run",
            "_timestamp": MODULE.parse_timestamp(old_timestamp),
            "timestamp": old_timestamp,
            "project_key": "repo-a-key",
            "project_name": "repo-a",
            "user_request_summary": "same request",
            "recommendations": [{"recommendation_id": "rec-1", "status": "applied"}],
        }
        fresh_entry = {
            "_run_dir": "new-run",
            "_timestamp": MODULE.parse_timestamp(recent_timestamp),
            "timestamp": recent_timestamp,
            "project_key": "repo-a-key",
            "project_name": "repo-a",
            "user_request_summary": "same request",
            "recommendations": [{"recommendation_id": "rec-1", "status": "applied"}],
        }
        stale_active = {
            "_path": "active/project.json",
            "_timestamp": MODULE.parse_timestamp((now - timedelta(hours=12)).isoformat().replace("+00:00", "Z")),
        }

        suggestions = MODULE.build_cleanup_suggestions(
            [stale_entry, fresh_entry],
            active_entries=[stale_active],
            now=now,
            keep_days=30,
            keep_latest=5,
        )
        reasons = {item["path"]: item["reason"] for item in suggestions}
        self.assertIn("old-run", reasons)
        self.assertIn("superseded", reasons["old-run"])
        self.assertIn("active/project.json", reasons)
        self.assertIn("stale active-run metadata", reasons["active/project.json"])

    def test_cleanup_suggestions_do_not_cross_project_supersede(self) -> None:
        now = datetime(2026, 4, 8, 15, 0, tzinfo=timezone.utc)
        entries = [
            {
                "_run_dir": "repo-a-run",
                "_timestamp": MODULE.parse_timestamp("2026-04-07T15:00:00Z"),
                "project_name": "repo-a",
                "project_key": "repo-a-key",
                "user_request_summary": "same request",
                "recommendations": [{"recommendation_id": "rec-1", "status": "applied"}],
            },
            {
                "_run_dir": "repo-b-run",
                "_timestamp": MODULE.parse_timestamp("2026-04-08T15:00:00Z"),
                "project_name": "repo-b",
                "project_key": "repo-b-key",
                "user_request_summary": "same request",
                "recommendations": [{"recommendation_id": "rec-1", "status": "applied"}],
            },
        ]

        suggestions = MODULE.build_cleanup_suggestions(
            entries,
            now=now,
            keep_days=30,
            keep_latest=5,
        )

        paths = {item["path"] for item in suggestions}
        self.assertNotIn("repo-a-run", paths)
        self.assertNotIn("repo-b-run", paths)

    def test_cleanup_keep_latest_ignores_same_named_other_repo(self) -> None:
        now = datetime(2026, 4, 8, 15, 0, tzinfo=timezone.utc)
        entries = [
            {
                "_run_dir": "shared-a-run",
                "_timestamp": MODULE.parse_timestamp("2026-04-07T15:00:00Z"),
                "project_name": "shared",
                "project_key": "shared-aaa",
                "user_request_summary": "request-a",
                "recommendations": [{"recommendation_id": "rec-1", "status": "applied"}],
            },
            {
                "_run_dir": "shared-b-run",
                "_timestamp": MODULE.parse_timestamp("2026-04-08T15:00:00Z"),
                "project_name": "shared",
                "project_key": "shared-bbb",
                "user_request_summary": "request-b",
                "recommendations": [{"recommendation_id": "rec-2", "status": "applied"}],
            },
        ]

        suggestions = MODULE.build_cleanup_suggestions(
            entries,
            now=now,
            keep_days=30,
            keep_latest=1,
        )

        paths = {item["path"] for item in suggestions}
        self.assertNotIn("shared-a-run", paths)
        self.assertNotIn("shared-b-run", paths)

    def test_mark_superseded_run_appends_interrupted_event(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "run"
            run_dir.mkdir(parents=True)
            MODULE.append_event(
                run_dir,
                {
                    "schema_version": MODULE.SCHEMA_VERSION,
                    "run_id": "run1",
                    "timestamp": "2026-04-08T15:00:00Z",
                    "event_type": "start",
                    "project_key": "proj-1",
                    "project_name": "repo-a",
                    "stage": "start",
                    "payload": {},
                },
            )
            active_entry = {"run_id": "run1", "run_dir": str(run_dir)}
            changed = MODULE.mark_superseded_run(
                active_entry,
                now=datetime(2026, 4, 8, 16, 0, tzinfo=timezone.utc),
            )
            events, invalid = MODULE.load_events(run_dir)
            self.assertTrue(changed)
            self.assertEqual(invalid, [])
            self.assertEqual(events[-1]["event_type"], "interrupted")


if __name__ == "__main__":
    unittest.main()
