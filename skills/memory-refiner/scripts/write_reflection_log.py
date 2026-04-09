#!/usr/bin/env python3
"""Lifecycle logger for memory-refiner runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from reflection_log import (
    SCHEMA_VERSION,
    append_event,
    build_active_run_record,
    build_cleanup_suggestions,
    build_event_record,
    build_start_record,
    build_summary_record,
    clear_active_run,
    create_run_dir,
    derive_project_context,
    format_timestamp,
    load_active_runs,
    load_summary_entries,
    mark_superseded_run,
    prepare_summary_payload,
    read_active_run,
    resolve_active_run_dir,
    resolve_log_dir,
    sanitize_payload_for_run,
    utc_now,
    write_active_run,
    write_summary_file,
)


GLOBAL_OPTIONS = {"--codex-home", "--cwd", "--format"}


def normalize_global_option_order(argv: list[str]) -> list[str]:
    if not argv:
        return argv

    command_tokens: list[str] = []
    global_tokens: list[str] = []
    trailing: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in {"start", "event", "finalize"}:
            command_tokens.append(token)
            index += 1
            break
        global_tokens.append(token)
        index += 1

    while index < len(argv):
        token = argv[index]
        if token in GLOBAL_OPTIONS and index + 1 < len(argv):
            global_tokens.extend([token, argv[index + 1]])
            index += 2
            continue
        trailing.append(token)
        index += 1

    return global_tokens + command_tokens + trailing


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", default="~/.codex", help="Path to Codex home")
    parser.add_argument("--cwd", default=str(Path.cwd()), help="Working directory for the run")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")

    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("--user-request-summary", required=True, help="Short summary of the user request")
    start_parser.add_argument("--note", action="append", default=[], help="Optional run-start note")

    event_parser = subparsers.add_parser("event")
    event_parser.add_argument("--stage", required=True, help="Lifecycle stage name")
    event_parser.add_argument("--event-type", default="stage", help="Structured event type")
    event_parser.add_argument("--summary", help="Short event summary")
    event_parser.add_argument("--input", default="-", help="JSON payload file, or '-' for stdin")

    finalize_parser = subparsers.add_parser("finalize")
    finalize_parser.add_argument("--input", default="-", help="JSON payload file, or '-' for stdin")
    finalize_parser.add_argument("--final-status", default="completed", help="Final run status label")

    return parser.parse_args(normalize_global_option_order(sys.argv[1:]))


def load_payload(source: str) -> dict[str, object]:
    if source == "-":
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
    else:
        raw = Path(source).read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Failed to parse reflection payload JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("Reflection payload must be a JSON object")
    return payload


def resolve_active_run(cwd: Path, codex_home: Path) -> dict[str, object]:
    context = derive_project_context(cwd)
    active = read_active_run(str(context["project_key"]), resolve_active_run_dir(codex_home))
    if active is None:
        raise SystemExit(
            "No active memory-refiner run found for this project. Start a run first with "
            "`python3 scripts/write_reflection_log.py --cwd \"$PWD\" start ...`."
        )
    return active


def render_markdown_start(run_dir: Path, active_path: Path, start_record: dict[str, object]) -> str:
    lines = ["# Memory Refiner Run Started", ""]
    lines.append(f"- Run dir: `{run_dir}`")
    lines.append(f"- Active record: `{active_path}`")
    lines.append(f"- Run id: `{start_record['run_id']}`")
    lines.append(f"- Project: `{start_record['project_name']}`")
    return "\n".join(lines)


def render_markdown_event(run_dir: Path, event: dict[str, object]) -> str:
    lines = ["# Memory Refiner Event Logged", ""]
    lines.append(f"- Run dir: `{run_dir}`")
    lines.append(f"- Run id: `{event['run_id']}`")
    lines.append(f"- Event type: `{event['event_type']}`")
    lines.append(f"- Stage: `{event['stage']}`")
    return "\n".join(lines)


def render_markdown_finalize(summary_file: Path, summary_record: dict[str, object], cleanup_count: int) -> str:
    lines = ["# Memory Refiner Run Finalized", ""]
    lines.append(f"- Summary file: `{summary_file}`")
    lines.append(f"- Run id: `{summary_record['run_id']}`")
    lines.append(f"- Final status: `{summary_record['final_status']}`")
    lines.append(f"- Recommendations: `{len(summary_record.get('recommendations', []))}`")
    lines.append(f"- Cleanup suggestions: `{cleanup_count}`")
    return "\n".join(lines)


def print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, indent=2))


def append_finalize_note(summary_record: dict[str, object], note: str) -> None:
    notes = list(summary_record.get("notes", []))
    notes.append(note)
    summary_record["notes"] = notes


def build_finalize_event(run_id: str, final_status: str) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "timestamp": format_timestamp(utc_now()),
        "event_type": "finalize",
        "stage": "finalize",
        "payload": {"final_status": final_status},
    }


def command_start(args: argparse.Namespace, codex_home: Path, cwd: Path) -> int:
    start_record = build_start_record(
        cwd=cwd,
        codex_home=codex_home,
        user_request_summary=args.user_request_summary,
        notes=args.note,
    )
    log_dir = resolve_log_dir(codex_home)
    active_dir = resolve_active_run_dir(codex_home)
    previous_active = read_active_run(str(start_record["project_key"]), active_dir)
    if previous_active is not None:
        mark_superseded_run(previous_active)
        clear_active_run(str(start_record["project_key"]), active_dir)

    run_dir = create_run_dir(log_dir, start_record)
    append_event(run_dir, start_record)
    active_record = build_active_run_record(start_record, run_dir)
    active_path = write_active_run(active_dir, active_record)

    if args.format == "json":
        print_json(
            {
                "run_dir": str(run_dir),
                "active_record": str(active_path),
                "run_id": start_record["run_id"],
            }
        )
    else:
        print(render_markdown_start(run_dir, active_path, start_record))
    return 0


def command_event(args: argparse.Namespace, codex_home: Path, cwd: Path) -> int:
    active = resolve_active_run(cwd, codex_home)
    payload = load_payload(args.input)
    if args.summary:
        payload.setdefault("summary", args.summary)
    run_dir = Path(str(active["run_dir"]))
    sanitized_payload = sanitize_payload_for_run(payload, cwd=cwd, codex_home=codex_home)
    event = build_event_record(
        stage=args.stage,
        payload=sanitized_payload,
        run_id=str(active["run_id"]),
        event_type=args.event_type,
    )
    append_event(run_dir, event)
    if args.format == "json":
        print_json({"run_dir": str(run_dir), "run_id": event["run_id"], "stage": event["stage"]})
    else:
        print(render_markdown_event(run_dir, event))
    return 0


def load_finalize_context(
    codex_home: Path,
    cwd: Path,
) -> dict[str, object]:
    active = resolve_active_run(cwd, codex_home)
    log_dir = resolve_log_dir(codex_home)
    active_dir = resolve_active_run_dir(codex_home)
    prior_logs, invalid_logs = load_summary_entries(log_dir)
    active_entries, invalid_active = load_active_runs(active_dir)
    return {
        "active": active,
        "active_dir": active_dir,
        "prior_logs": prior_logs,
        "invalid_logs": invalid_logs,
        "active_entries": active_entries,
        "invalid_active": invalid_active,
    }


def build_finalize_artifacts(
    payload: dict[str, object],
    *,
    codex_home: Path,
    cwd: Path,
    context: dict[str, object],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    prior_logs = list(context["prior_logs"])
    active_entries = list(context["active_entries"])
    invalid_logs = list(context["invalid_logs"])
    invalid_active = list(context["invalid_active"])
    active = dict(context["active"])

    prepared_payload = prepare_summary_payload(payload, cwd=cwd, codex_home=codex_home)
    summary_record = build_summary_record(
        prepared_payload=prepared_payload,
        prior_logs=prior_logs,
        active_run=active,
    )
    if invalid_logs:
        append_finalize_note(
            summary_record,
            f"ignored {len(invalid_logs)} malformed prior summary file(s)",
        )
    cleanup_suggestions = build_cleanup_suggestions(
        prior_logs,
        active_entries=active_entries,
    )
    if invalid_active:
        append_finalize_note(
            summary_record,
            f"ignored {len(invalid_active)} malformed active-run record(s)",
        )
    summary_record["cleanup_suggestions"] = cleanup_suggestions
    return summary_record, cleanup_suggestions


def command_finalize(args: argparse.Namespace, codex_home: Path, cwd: Path) -> int:
    context = load_finalize_context(codex_home, cwd)
    payload = load_payload(args.input)
    payload["final_status"] = args.final_status
    active = dict(context["active"])
    run_dir = Path(str(active["run_dir"]))
    final_event = build_finalize_event(str(active["run_id"]), args.final_status)
    append_event(run_dir, final_event)
    summary_record, cleanup_suggestions = build_finalize_artifacts(
        payload,
        codex_home=codex_home,
        cwd=cwd,
        context=context,
    )

    summary_file = write_summary_file(run_dir, summary_record)
    clear_active_run(str(active["project_key"]), Path(str(context["active_dir"])))

    if args.format == "json":
        print_json(
            {
                "summary_file": str(summary_file),
                "run_id": summary_record["run_id"],
                "recommendations": len(summary_record.get("recommendations", [])),
                "cleanup_suggestions": len(cleanup_suggestions),
            }
        )
    else:
        print(render_markdown_finalize(summary_file, summary_record, len(cleanup_suggestions)))
    return 0


def main() -> int:
    args = parse_args()
    codex_home = Path(args.codex_home).expanduser().resolve()
    cwd = Path(args.cwd).expanduser().resolve()
    if args.command == "start":
        return command_start(args, codex_home, cwd)
    if args.command == "event":
        return command_event(args, codex_home, cwd)
    if args.command == "finalize":
        return command_finalize(args, codex_home, cwd)
    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
