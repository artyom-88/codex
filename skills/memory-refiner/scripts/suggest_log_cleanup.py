#!/usr/bin/env python3
"""Suggest stale memory-refiner logs for manual cleanup."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from reflection_log import (
    DEFAULT_KEEP_DAYS,
    DEFAULT_KEEP_LATEST,
    build_cleanup_suggestions,
    load_active_runs,
    load_summary_entries,
    resolve_active_run_dir,
    resolve_log_dir,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", default="~/.codex", help="Path to Codex home")
    parser.add_argument("--cwd", default=str(Path.cwd()), help="Working directory for project-aware cleanup context")
    parser.add_argument("--keep-days", type=int, default=DEFAULT_KEEP_DAYS, help="Age threshold for stale logs")
    parser.add_argument(
        "--keep-latest",
        type=int,
        default=DEFAULT_KEEP_LATEST,
        help="Keep at least this many recent runs per project before suggesting cleanup",
    )
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    return parser.parse_args()


def render_markdown(candidates: list[dict[str, str]], invalid_logs: list[str]) -> str:
    lines = ["# Memory Refiner Log Cleanup Suggestions", ""]
    if invalid_logs:
        lines.append(f"- Ignored malformed logs: `{len(invalid_logs)}`")
    if not candidates:
        lines.append("- No cleanup candidates")
        return "\n".join(lines)
    lines.append(f"- Cleanup candidates: `{len(candidates)}`")
    lines.append("")
    for item in candidates:
        lines.append(f"- `{item['path']}`")
        lines.append(f"  reason: {item['reason']}")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    codex_home = Path(args.codex_home).expanduser().resolve()
    _cwd = Path(args.cwd).expanduser().resolve()
    entries, invalid_logs = load_summary_entries(resolve_log_dir(codex_home))
    active_entries, invalid_active = load_active_runs(resolve_active_run_dir(codex_home))
    candidates = build_cleanup_suggestions(
        entries,
        active_entries=active_entries,
        keep_days=args.keep_days,
        keep_latest=args.keep_latest,
    )
    invalid_logs.extend(invalid_active)
    if args.format == "json":
        print(json.dumps({"candidates": candidates, "invalid_logs": invalid_logs}, indent=2))
    else:
        print(render_markdown(candidates, invalid_logs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
