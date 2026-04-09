#!/usr/bin/env python3
"""Summarize recent memory-refiner reflection logs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from reflection_log import (
    derive_project_context,
    load_active_runs,
    load_summary_entries,
    resolve_active_run_dir,
    resolve_log_dir,
    summarize_recent_logs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", default="~/.codex", help="Path to Codex home")
    parser.add_argument("--cwd", default=str(Path.cwd()), help="Working directory for project-aware summaries")
    parser.add_argument("--limit", type=int, default=5, help="Maximum repeated items per section")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    return parser.parse_args()


def render_markdown(summary: dict[str, object], invalid_logs: list[str]) -> str:
    lines = ["# Memory Refiner Reflection Summary", ""]
    lines.append(f"- Total logs: `{summary['total_logs']}`")
    lines.append(f"- Current project: `{summary.get('project_name') or 'unknown'}`")
    lines.append(f"- Project logs: `{summary['project_logs']}`")
    lines.append(f"- Distinct projects: `{len(summary.get('projects', []))}`")
    lines.append(f"- Active runs: `{summary.get('active_runs', 0)}`")
    lines.append(f"- Stale active runs: `{summary.get('stale_active_runs', 0)}`")
    if invalid_logs:
        lines.append(f"- Ignored malformed logs: `{len(invalid_logs)}`")
    if summary["total_logs"] == 0:
        lines.append(
            "- No reflection logs exist yet. The logging workflow may not have been "
            "executed, or the log root may be empty."
        )

    sections = (
        ("Repeated Recommendations", list(summary.get("repeated_recommendations", []))),
        ("Repeated Applied Recommendations", list(summary.get("repeated_applied_recommendations", []))),
        ("Repeated Rejected Recommendations", list(summary.get("repeated_rejected_recommendations", []))),
    )
    for title, items in sections:
        lines.extend(["", f"## {title}"])
        if not items:
            lines.append("- None")
            continue
        for item in items:
            target = item["target"] or "unknown target"
            lines.append(f"- {item['count']}x `{item['recommendation_id']}` on `{target}`")
            if item.get("summary"):
                lines.append(f"  summary: {item['summary']}")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    codex_home = Path(args.codex_home).expanduser().resolve()
    cwd = Path(args.cwd).expanduser().resolve()
    log_dir = resolve_log_dir(codex_home)
    entries, invalid_logs = load_summary_entries(log_dir)
    active_entries, invalid_active = load_active_runs(resolve_active_run_dir(codex_home))
    project_context = derive_project_context(cwd)
    summary = summarize_recent_logs(
        entries,
        project_key=str(project_context["project_key"]),
        project_name=str(project_context["project_name"]),
        limit=args.limit,
        active_entries=active_entries,
    )
    invalid_logs.extend(invalid_active)

    if args.format == "json":
        print(json.dumps({"summary": summary, "invalid_logs": invalid_logs}, indent=2))
    else:
        print(render_markdown(summary, invalid_logs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
