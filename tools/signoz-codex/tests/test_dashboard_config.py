from __future__ import annotations

import json
import unittest
from pathlib import Path


DASHBOARD_PATH = Path(__file__).resolve().parents[1] / "dashboards" / "codex-native-dashboard.json"


class DashboardConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dashboard_text = DASHBOARD_PATH.read_text(encoding="utf-8")
        self.dashboard = json.loads(self.dashboard_text)

    def test_layout_and_widget_ids_match(self) -> None:
        widget_ids = [widget["id"] for widget in self.dashboard["widgets"]]
        layout_ids = [item["i"] for item in self.dashboard["layout"]]

        self.assertEqual(len(widget_ids), len(set(widget_ids)), "dashboard widget ids must be unique")
        self.assertEqual(set(layout_ids), set(widget_ids), "layout items and widgets must match exactly")

    def test_project_progress_metrics_are_referenced(self) -> None:
        expected_fragments = [
            "codex.conversation.turn.count",
            "codex.thread.started",
            "codex.turn.e2e_duration_ms",
            "codex.turn.ttft.duration_ms",
            "codex.turn.ttfm.duration_ms",
            "codex.api_request",
            "codex.mcp.call",
            "Approval request ratio %",
            "approval-request-ratio-total",
            "Tool success rate %",
            "tool-success-rate-total",
            "tool-failures-by-tool",
            "A / B * 100",
            "project.name",
        ]

        for fragment in expected_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.dashboard_text)

    def test_non_row_widgets_have_clear_descriptions(self) -> None:
        for widget in self.dashboard["widgets"]:
            if widget.get("panelTypes") == "row":
                continue
            with self.subTest(widget_id=widget["id"]):
                description = widget.get("description", "")
                self.assertGreaterEqual(len(description.split()), 18)

        tool_call_description = self._description_for("tool-calls-total")
        self.assertIn("host environment", tool_call_description)
        self.assertIn("does not mean launching Codex itself", tool_call_description)

    def _description_for(self, widget_id: str) -> str:
        for widget in self.dashboard["widgets"]:
            if widget["id"] == widget_id:
                return widget.get("description", "")
        raise AssertionError(f"dashboard widget {widget_id!r} was not found")


if __name__ == "__main__":
    unittest.main()
