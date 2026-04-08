#!/usr/bin/env python3
"""Suggest stale memory-refiner logs and optionally delete them."""

from __future__ import annotations

import argparse
import json
import shutil
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
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Delete the suggested stale log directories and active-run files inside the memory-refiner log roots",
    )
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    return parser.parse_args()


def render_markdown(
    candidates: list[dict[str, str]],
    invalid_logs: list[str],
    *,
    deleted_paths: list[str] | None = None,
    skipped_paths: list[dict[str, str]] | None = None,
) -> str:
    deleted = deleted_paths or []
    skipped = skipped_paths or []
    lines = ["# Memory Refiner Log Cleanup Suggestions", ""]
    if invalid_logs:
        lines.append(f"- Ignored malformed logs: `{len(invalid_logs)}`")
    if deleted:
        lines.append(f"- Deleted paths: `{len(deleted)}`")
    if skipped:
        lines.append(f"- Skipped paths: `{len(skipped)}`")
    if not candidates:
        lines.append("- No cleanup candidates")
        if skipped:
            lines.append("")
            for item in skipped:
                lines.append(f"- skipped `{item['path']}`")
                lines.append(f"  reason: {item['reason']}")
        return "\n".join(lines)
    lines.append(f"- Cleanup candidates: `{len(candidates)}`")
    lines.append("")
    for item in candidates:
        lines.append(f"- `{item['path']}`")
        lines.append(f"  reason: {item['reason']}")
    if skipped:
        lines.append("")
        for item in skipped:
            lines.append(f"- skipped `{item['path']}`")
            lines.append(f"  reason: {item['reason']}")
    return "\n".join(lines)


def is_within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def delete_cleanup_candidates(
    candidates: list[dict[str, str]],
    *,
    log_dir: Path,
    active_dir: Path,
) -> tuple[list[str], list[dict[str, str]]]:
    deleted: list[str] = []
    skipped: list[dict[str, str]] = []
    allowed_roots = (log_dir, active_dir)

    for item in candidates:
        candidate_path = Path(item["path"]).expanduser()
        if not any(is_within_root(candidate_path, root) for root in allowed_roots):
            skipped.append(
                {
                    "path": item["path"],
                    "reason": "outside the memory-refiner log roots",
                }
            )
            continue
        if not candidate_path.exists():
            skipped.append(
                {
                    "path": item["path"],
                    "reason": "path no longer exists",
                }
            )
            continue
        if candidate_path.is_dir() and not candidate_path.is_symlink():
            shutil.rmtree(candidate_path)
        else:
            candidate_path.unlink()
        deleted.append(item["path"])
    return deleted, skipped


def main() -> int:
    args = parse_args()
    codex_home = Path(args.codex_home).expanduser().resolve()
    _cwd = Path(args.cwd).expanduser().resolve()
    log_dir = resolve_log_dir(codex_home)
    active_dir = resolve_active_run_dir(codex_home)
    entries, invalid_logs = load_summary_entries(log_dir)
    active_entries, invalid_active = load_active_runs(active_dir)
    candidates = build_cleanup_suggestions(
        entries,
        active_entries=active_entries,
        keep_days=args.keep_days,
        keep_latest=args.keep_latest,
    )
    invalid_logs.extend(invalid_active)
    deleted_paths: list[str] = []
    skipped_paths: list[dict[str, str]] = []
    if args.apply:
        deleted_paths, skipped_paths = delete_cleanup_candidates(
            candidates,
            log_dir=log_dir,
            active_dir=active_dir,
        )
    if args.format == "json":
        print(
            json.dumps(
                {
                    "apply": args.apply,
                    "candidates": candidates,
                    "deleted_paths": deleted_paths,
                    "skipped_paths": skipped_paths,
                    "invalid_logs": invalid_logs,
                },
                indent=2,
            )
        )
    else:
        print(
            render_markdown(
                candidates,
                invalid_logs,
                deleted_paths=deleted_paths,
                skipped_paths=skipped_paths,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
