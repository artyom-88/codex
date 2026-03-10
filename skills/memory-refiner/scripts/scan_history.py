#!/usr/bin/env python3
"""Summarize repeated patterns from Codex history.jsonl without flooding context."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PREFERENCE_MARKERS = (
    "prefer ",
    "always ",
    "never ",
    "do not ",
    "don't ",
    "use ",
    "keep ",
    "avoid ",
)

CORRECTION_MARKERS = (
    "fix ",
    "actually",
    "instead",
    "missing",
    "should ",
    "don't ",
    "do not ",
    "why ",
)

TOOL_TOKENS = (
    "pnpm",
    "npm",
    "yarn",
    "bun",
    "git",
    "docker",
    "gradle",
    "maven",
    "pytest",
    "vitest",
    "vite",
    "kubectl",
    "python",
    "java",
    "react",
    "drupal",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", default="~/.codex/history.jsonl", help="Path to Codex history.jsonl")
    parser.add_argument("--top", type=int, default=15, help="Maximum items per section")
    parser.add_argument("--min-frequency", type=int, default=2, help="Minimum frequency to report")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    return parser.parse_args()


def normalize_text(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.strip().lower())
    return normalized[:240]


def display_text(value: str, limit: int = 140) -> str:
    return value if len(value) <= limit else value[: limit - 3] + "..."


def parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        raw = float(value)
        if raw > 1_000_000_000_000:
            raw /= 1000
        return datetime.fromtimestamp(raw, tz=timezone.utc)
    if isinstance(value, str):
        try:
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def load_entries(path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and isinstance(payload.get("text"), str):
                entries.append(payload)
    return entries


def top_examples(counter: Counter[str], top: int, min_frequency: int) -> list[dict[str, Any]]:
    items = []
    for text, count in counter.most_common(top):
        if count < min_frequency:
            continue
        items.append({"text": text, "count": count})
    return items


def build_summary(entries: list[dict[str, Any]], top: int, min_frequency: int) -> dict[str, Any]:
    texts = [entry["text"] for entry in entries]
    normalized = [normalize_text(text) for text in texts if text.strip()]
    repeated_counter = Counter(
        text for text in normalized if 12 <= len(text) <= 240
    )
    preference_counter = Counter(
        text for text in normalized if any(marker in text for marker in PREFERENCE_MARKERS)
    )
    correction_counter = Counter(
        text for text in normalized if any(marker in text for marker in CORRECTION_MARKERS)
    )

    tool_counter: Counter[str] = Counter()
    for text in normalized:
        for token in TOOL_TOKENS:
            if re.search(rf"\b{re.escape(token)}\b", text):
                tool_counter[token] += 1

    session_ids = {
        entry.get("session_id")
        for entry in entries
        if isinstance(entry.get("session_id"), str) and entry.get("session_id")
    }
    timestamps = [
        parsed
        for parsed in (parse_timestamp(entry.get("ts")) for entry in entries)
        if parsed is not None
    ]

    return {
        "stats": {
            "entries": len(entries),
            "sessions": len(session_ids),
            "date_range": {
                "start": min(timestamps).isoformat() if timestamps else None,
                "end": max(timestamps).isoformat() if timestamps else None,
            },
        },
        "repeated_requests": top_examples(repeated_counter, top, min_frequency),
        "preference_signals": top_examples(preference_counter, top, min_frequency),
        "correction_signals": top_examples(correction_counter, top, min_frequency),
        "tool_mentions": [
            {"tool": tool, "count": count}
            for tool, count in tool_counter.most_common(top)
            if count >= min_frequency
        ],
    }


def render_markdown(summary: dict[str, Any], history_path: Path) -> str:
    stats = summary["stats"]
    lines = ["# Codex History Scan", "", f"- History file: `{history_path}`"]
    lines.append(f"- Entries: `{stats['entries']}`")
    lines.append(f"- Sessions: `{stats['sessions']}`")

    date_range = stats["date_range"]
    if date_range["start"] and date_range["end"]:
        lines.append(f"- Date range: `{date_range['start']}` -> `{date_range['end']}`")

    def add_section(title: str, items: list[dict[str, Any]], key: str = "text") -> None:
        lines.extend(["", f"## {title}"])
        if not items:
            lines.append("- None above the reporting threshold")
            return
        for item in items:
            value = display_text(item[key])
            lines.append(f"- {item['count']}x: {value}")

    add_section("Repeated Requests", summary["repeated_requests"])
    add_section("Preference Signals", summary["preference_signals"])
    add_section("Correction Signals", summary["correction_signals"])

    lines.extend(["", "## Tool Mentions"])
    if not summary["tool_mentions"]:
        lines.append("- None above the reporting threshold")
    else:
        for item in summary["tool_mentions"]:
            lines.append(f"- {item['count']}x: {item['tool']}")

    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    history_path = Path(args.history).expanduser()
    if not history_path.exists():
        raise SystemExit(f"History file not found: {history_path}")

    entries = load_entries(history_path)
    summary = build_summary(entries, args.top, args.min_frequency)

    if args.format == "json":
        print(json.dumps(summary, indent=2))
    else:
        print(render_markdown(summary, history_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
