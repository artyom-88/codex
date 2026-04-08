#!/usr/bin/env python3
"""Shared helpers for memory-refiner lifecycle logging."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jsonl_utils import load_jsonl_objects
from project_context import resolve_project_root

SCHEMA_VERSION = 2
DEFAULT_KEEP_DAYS = 30
DEFAULT_KEEP_LATEST = 20
SUMMARY_LIMIT = 280
STATUS_VALUES = frozenset({"proposed", "approved", "applied", "rejected", "deferred", "unknown"})


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_text(value: str, limit: int = SUMMARY_LIMIT) -> str:
    normalized = re.sub(r"\s+", " ", value.strip())
    return normalized if len(normalized) <= limit else normalized[: limit - 3] + "..."


def short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def path_hash(path: Path) -> str:
    return short_hash(str(path.expanduser()))


def resolve_log_dir(codex_home: Path) -> Path:
    return codex_home / "log" / "memory-refiner"


def resolve_active_run_dir(codex_home: Path) -> Path:
    return codex_home / "cache" / "memory-refiner" / "active"


def sanitize_path_value(raw: str, project_root: Path | None, codex_home: Path) -> str:
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        return normalize_text(raw)

    if project_root is not None:
        try:
            return str(candidate.relative_to(project_root))
        except ValueError:
            pass

    try:
        relative = candidate.relative_to(codex_home)
        return f"~/.codex/{relative}"
    except ValueError:
        return f"path-hash:{path_hash(candidate)}"


def sanitize_value(value: Any, project_root: Path | None, codex_home: Path) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        expanded = Path(value).expanduser()
        if expanded.is_absolute():
            return sanitize_path_value(value, project_root, codex_home)
        return normalize_text(value)
    if isinstance(value, list):
        return [sanitize_value(item, project_root, codex_home) for item in value[:50]]
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in list(value.items())[:50]:
            sanitized[str(key)] = sanitize_value(item, project_root, codex_home)
        return sanitized
    return normalize_text(str(value))


def derive_project_context(cwd: Path) -> dict[str, str | None]:
    project_root = resolve_project_root(cwd)
    project_name = project_root.name if project_root is not None else cwd.name
    repo_name = project_root.name if project_root is not None else None
    project_key_source = path_hash(project_root) if project_root is not None else path_hash(cwd)
    return {
        "project_name": project_name,
        "repo_name": repo_name,
        "project_root_hash": path_hash(project_root) if project_root is not None else None,
        "cwd_hash": path_hash(cwd),
        "project_key": f"{slugify(project_name)}-{project_key_source}",
    }


def sanitize_payload_for_run(payload: dict[str, Any], *, cwd: Path, codex_home: Path) -> dict[str, Any]:
    project_root = resolve_project_root(cwd)
    sanitized = sanitize_value(payload, project_root, codex_home)
    return sanitized if isinstance(sanitized, dict) else {"value": sanitized}


def normalize_status(value: Any) -> str:
    if not isinstance(value, str):
        return "unknown"
    lowered = value.strip().lower()
    return lowered if lowered in STATUS_VALUES else "unknown"


def recommendation_id(record: dict[str, Any]) -> str:
    basis = "\0".join(
        (
            str(record.get("scope", "")),
            str(record.get("target", "")),
            str(record.get("change_type", "")),
            str(record.get("summary", "")),
        )
    )
    return f"rec-{short_hash(basis)}"


def build_recommendation_record(
    raw: dict[str, Any], project_root: Path | None, codex_home: Path
) -> dict[str, Any]:
    target = raw.get("target") or raw.get("target_file") or ""
    record = {
        "scope": normalize_text(str(raw.get("scope", ""))),
        "target": sanitize_path_value(str(target), project_root, codex_home) if target else "",
        "priority": normalize_text(str(raw.get("priority", ""))),
        "change_type": normalize_text(str(raw.get("change_type", ""))),
        "summary": normalize_text(
            str(raw.get("summary") or raw.get("proposed_change") or raw.get("rationale") or "")
        ),
        "rationale": normalize_text(str(raw.get("rationale", ""))),
        "status": normalize_status(raw.get("status")),
    }
    record["recommendation_id"] = recommendation_id(record)
    return record


def create_run_id(cwd: Path, user_request_summary: str, now: datetime | None = None) -> str:
    current_time = now or utc_now()
    return short_hash(f"{format_timestamp(current_time)}::{cwd}::{user_request_summary}")


def run_dir_name(timestamp: datetime, project_name: str, run_id: str) -> str:
    compact = format_timestamp(timestamp).replace(":", "").replace("-", "")
    return f"{compact}-{slugify(project_name)}-{run_id}"


def build_start_record(
    *,
    cwd: Path,
    codex_home: Path,
    user_request_summary: str,
    now: datetime | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    current_time = now or utc_now()
    project_root = resolve_project_root(cwd)
    context = derive_project_context(cwd)
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": create_run_id(cwd, user_request_summary, current_time),
        "timestamp": format_timestamp(current_time),
        "event_type": "start",
        "project_name": context["project_name"],
        "repo_name": context["repo_name"],
        "project_root_hash": context["project_root_hash"],
        "cwd_hash": context["cwd_hash"],
        "project_key": context["project_key"],
        "user_request_summary": normalize_text(user_request_summary),
        "notes": sanitize_value(notes or [], project_root, codex_home),
    }


def create_run_dir(log_dir: Path, start_record: dict[str, Any]) -> Path:
    timestamp = parse_timestamp(start_record["timestamp"])
    if timestamp is None:
        raise ValueError("start record is missing a valid timestamp")
    path = log_dir / run_dir_name(timestamp, str(start_record["project_name"]), str(start_record["run_id"]))
    path.mkdir(parents=True, exist_ok=True)
    return path


def events_path(run_dir: Path) -> Path:
    return run_dir / "events.jsonl"


def summary_path(run_dir: Path) -> Path:
    return run_dir / "summary.json"


def append_event(run_dir: Path, event: dict[str, Any]) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = events_path(run_dir)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    return path


def load_events(run_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    path = events_path(run_dir)
    return load_jsonl_objects(path, keep_invalid_paths=True)


def project_key_filename(project_key: str) -> str:
    return f"{project_key}.json"


def read_active_run(project_key: str, active_dir: Path) -> dict[str, Any] | None:
    path = active_dir / project_key_filename(project_key)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def write_active_run(active_dir: Path, payload: dict[str, Any]) -> Path:
    active_dir.mkdir(parents=True, exist_ok=True)
    path = active_dir / project_key_filename(str(payload["project_key"]))
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def clear_active_run(project_key: str, active_dir: Path) -> None:
    path = active_dir / project_key_filename(project_key)
    if path.exists():
        path.unlink()


def build_active_run_record(start_record: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": start_record["run_id"],
        "project_key": start_record["project_key"],
        "project_name": start_record["project_name"],
        "timestamp": start_record["timestamp"],
        "run_dir": str(run_dir),
    }


def build_event_record(
    *,
    stage: str,
    payload: dict[str, Any],
    run_id: str,
    now: datetime | None = None,
    event_type: str = "stage",
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "timestamp": format_timestamp(now or utc_now()),
        "event_type": event_type,
        "stage": stage,
        "payload": payload,
    }


def _recommendation_signature(log: dict[str, Any]) -> tuple[str, tuple[tuple[str, str], ...]]:
    recommendations = log.get("recommendations", [])
    if not isinstance(recommendations, list):
        recommendations = []
    entries = []
    for item in recommendations:
        if not isinstance(item, dict):
            continue
        entries.append((str(item.get("recommendation_id", "")), normalize_status(item.get("status"))))
    return (str(log.get("user_request_summary", "")), tuple(sorted(entries)))


def load_summary_entries(log_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    entries: list[dict[str, Any]] = []
    invalid: list[str] = []
    if not log_dir.exists():
        return entries, invalid

    for run_dir in sorted(path for path in log_dir.iterdir() if path.is_dir()):
        path = summary_path(run_dir)
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            invalid.append(str(path))
            continue
        if not isinstance(payload, dict):
            invalid.append(str(path))
            continue
        payload["_log_path"] = str(path)
        payload["_run_dir"] = str(run_dir)
        payload["_timestamp"] = parse_timestamp(payload.get("timestamp"))
        entries.append(payload)
    return entries, invalid


def load_active_runs(active_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    entries: list[dict[str, Any]] = []
    invalid: list[str] = []
    if not active_dir.exists():
        return entries, invalid

    for path in sorted(active_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            invalid.append(str(path))
            continue
        if not isinstance(payload, dict):
            invalid.append(str(path))
            continue
        payload["_path"] = str(path)
        payload["_timestamp"] = parse_timestamp(payload.get("timestamp"))
        entries.append(payload)
    return entries, invalid


def detect_stale_active_runs(
    active_entries: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    stale_after: timedelta = timedelta(hours=8),
) -> list[dict[str, Any]]:
    current_time = now or utc_now()
    stale: list[dict[str, Any]] = []
    for entry in active_entries:
        timestamp = entry.get("_timestamp")
        if timestamp is None:
            stale.append(entry)
            continue
        if current_time - timestamp > stale_after:
            stale.append(entry)
    return stale


def summarize_recommendation_activity(
    entries: list[dict[str, Any]],
    limit: int,
) -> dict[str, list[dict[str, Any]]]:
    repeated_counter: Counter[str] = Counter()
    applied_counter: Counter[str] = Counter()
    rejected_counter: Counter[str] = Counter()
    metadata: dict[str, dict[str, str]] = {}

    for entry in entries:
        recommendations = entry.get("recommendations", [])
        if not isinstance(recommendations, list):
            continue
        for recommendation in recommendations:
            if not isinstance(recommendation, dict):
                continue
            recommendation_id_value = str(recommendation.get("recommendation_id", ""))
            if not recommendation_id_value:
                continue
            repeated_counter[recommendation_id_value] += 1
            metadata.setdefault(
                recommendation_id_value,
                {
                    "target": str(recommendation.get("target", "")),
                    "scope": str(recommendation.get("scope", "")),
                    "summary": str(recommendation.get("summary", "")),
                },
            )
            status = normalize_status(recommendation.get("status"))
            if status == "applied":
                applied_counter[recommendation_id_value] += 1
            if status == "rejected":
                rejected_counter[recommendation_id_value] += 1

    return {
        "repeated_recommendations": render_top_recommendations(repeated_counter, metadata, limit),
        "repeated_applied_recommendations": render_top_recommendations(applied_counter, metadata, limit),
        "repeated_rejected_recommendations": render_top_recommendations(rejected_counter, metadata, limit),
    }


def render_top_recommendations(
    counter: Counter[str],
    metadata: dict[str, dict[str, str]],
    limit: int,
) -> list[dict[str, Any]]:
    rendered: list[dict[str, Any]] = []
    for recommendation_id_value, count in counter.most_common(limit):
        info = metadata.get(recommendation_id_value, {})
        rendered.append(
            {
                "recommendation_id": recommendation_id_value,
                "count": count,
                "target": info.get("target", ""),
                "scope": info.get("scope", ""),
                "summary": info.get("summary", ""),
            }
        )
    return rendered


def list_projects(entries: list[dict[str, Any]]) -> list[str]:
    return sorted({str(entry.get("project_name") or "unknown") for entry in entries})


def filter_entries_for_project(
    entries: list[dict[str, Any]],
    project_name: str | None,
) -> list[dict[str, Any]]:
    if project_name is None:
        return entries
    return [entry for entry in entries if entry.get("project_name") == project_name]


def summarize_recent_logs(
    entries: list[dict[str, Any]],
    *,
    project_name: str | None = None,
    limit: int = 5,
    active_entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    project_entries = filter_entries_for_project(entries, project_name)
    active = filter_entries_for_project(active_entries or [], project_name)
    stale_active = detect_stale_active_runs(active)
    summary = {
        "total_logs": len(entries),
        "project_name": project_name,
        "project_logs": len(project_entries),
        "projects": list_projects(entries),
        "active_runs": len(active),
        "stale_active_runs": len(stale_active),
    }
    summary.update(summarize_recommendation_activity(project_entries, limit))
    return summary


def build_reflection_signals(
    recommendations: list[dict[str, Any]],
    prior_logs: list[dict[str, Any]],
    project_name: str,
) -> dict[str, Any]:
    prior_summary = summarize_recent_logs(prior_logs, project_name=project_name, limit=10)
    seen_ids = {str(item.get("recommendation_id", "")) for item in recommendations if isinstance(item, dict)}

    def relevant(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [item for item in items if item.get("recommendation_id") in seen_ids]

    return {
        "prior_log_count": len(prior_logs),
        "prior_project_log_count": prior_summary["project_logs"],
        "repeated_recommendations": relevant(prior_summary["repeated_recommendations"]),
        "repeated_applied_recommendations": relevant(prior_summary["repeated_applied_recommendations"]),
        "repeated_rejected_recommendations": relevant(prior_summary["repeated_rejected_recommendations"]),
    }


def build_summary_record(
    *,
    prepared_payload: dict[str, Any],
    prior_logs: list[dict[str, Any]] | None = None,
    active_run: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = now or utc_now()
    previous_logs = prior_logs or []
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": active_run["run_id"],
        "timestamp": format_timestamp(current_time),
        "project_name": prepared_payload["project_name"],
        "repo_name": prepared_payload["repo_name"],
        "project_root_hash": prepared_payload["project_root_hash"],
        "cwd_hash": prepared_payload["cwd_hash"],
        "project_key": prepared_payload["project_key"],
        "user_request_summary": prepared_payload["user_request_summary"],
        "history_summary": prepared_payload["history_summary"],
        "memory_surface_summary": prepared_payload["memory_surface_summary"],
        "recommendations": prepared_payload["recommendations"],
        "notes": prepared_payload["notes"],
        "reflection_signals": build_reflection_signals(
            prepared_payload["recommendations"],
            previous_logs,
            str(prepared_payload["project_name"]),
        ),
        "final_status": prepared_payload["final_status"],
    }


def prepare_summary_payload(
    payload: dict[str, Any],
    *,
    cwd: Path,
    codex_home: Path,
) -> dict[str, Any]:
    project_root = resolve_project_root(cwd)
    context = derive_project_context(cwd)
    recommendations = [
        build_recommendation_record(item, project_root, codex_home)
        for item in payload.get("recommendations", [])
        if isinstance(item, dict)
    ]
    return {
        "project_name": context["project_name"],
        "repo_name": context["repo_name"],
        "project_root_hash": context["project_root_hash"],
        "cwd_hash": context["cwd_hash"],
        "project_key": context["project_key"],
        "user_request_summary": normalize_text(str(payload.get("user_request_summary", ""))),
        "history_summary": sanitize_value(payload.get("history_summary", {}), project_root, codex_home),
        "memory_surface_summary": sanitize_value(payload.get("memory_surface_summary", {}), project_root, codex_home),
        "recommendations": recommendations,
        "notes": sanitize_value(payload.get("notes", []), project_root, codex_home),
        "final_status": normalize_text(str(payload.get("final_status", "completed"))),
    }


def write_summary_file(run_dir: Path, record: dict[str, Any]) -> Path:
    path = summary_path(run_dir)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_run_by_active_entry(active_entry: dict[str, Any]) -> tuple[Path | None, list[dict[str, Any]], list[str]]:
    run_dir_raw = active_entry.get("run_dir")
    if not isinstance(run_dir_raw, str):
        return None, [], []
    run_dir = Path(run_dir_raw)
    if not run_dir.exists():
        return run_dir, [], []
    events, invalid = load_events(run_dir)
    return run_dir, events, invalid


def mark_superseded_run(
    active_entry: dict[str, Any],
    *,
    now: datetime | None = None,
) -> bool:
    run_dir, events, _invalid = load_run_by_active_entry(active_entry)
    if run_dir is None or not run_dir.exists():
        return False
    summary_exists = summary_path(run_dir).exists()
    if summary_exists:
        return False
    event = {
        "schema_version": SCHEMA_VERSION,
        "run_id": active_entry.get("run_id"),
        "timestamp": format_timestamp(now or utc_now()),
        "event_type": "interrupted",
        "stage": "interrupted",
        "payload": {
            "reason": "superseded by a newer memory-refiner run for the same project",
            "previous_event_count": len(events),
        },
    }
    append_event(run_dir, event)
    return True


def append_age_based_suggestions(
    suggestions: dict[str, dict[str, Any]],
    entries: list[dict[str, Any]],
    *,
    current_time: datetime,
    keep_days: int,
    keep_latest: int,
) -> None:
    by_project: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        project_name = str(entry.get("project_name") or "unknown")
        by_project[project_name].append(entry)

    for group in by_project.values():
        group.sort(key=lambda item: item.get("_timestamp") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        for stale_entry in group[keep_latest:]:
            path = str(stale_entry.get("_run_dir") or stale_entry.get("_log_path"))
            suggestions[path] = {
                "path": path,
                "reason": f"older than the most recent {keep_latest} finalized runs for this project",
            }
        for entry in group:
            timestamp = entry.get("_timestamp")
            if timestamp is None or current_time - timestamp <= timedelta(days=keep_days):
                continue
            path = str(entry.get("_run_dir") or entry.get("_log_path"))
            suggestions[path] = {
                "path": path,
                "reason": f"older than {keep_days} days",
            }


def append_superseded_suggestions(
    suggestions: dict[str, dict[str, Any]],
    entries: list[dict[str, Any]],
) -> None:
    signatures: defaultdict[
        tuple[str, str, tuple[tuple[str, str], ...]],
        list[dict[str, Any]],
    ] = defaultdict(list)
    for entry in entries:
        project_identity = str(entry.get("project_key") or entry.get("project_name") or "unknown")
        request_summary, recommendation_outcomes = _recommendation_signature(entry)
        signatures[(project_identity, request_summary, recommendation_outcomes)].append(entry)

    for group in signatures.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda item: item.get("_timestamp") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        for older_entry in group[1:]:
            path = str(older_entry.get("_run_dir") or older_entry.get("_log_path"))
            suggestions[path] = {
                "path": path,
                "reason": (
                    "superseded by a newer finalized run with the same request summary "
                    "and recommendation outcomes"
                ),
            }


def append_stale_active_suggestions(
    suggestions: dict[str, dict[str, Any]],
    active_entries: list[dict[str, Any]],
    *,
    current_time: datetime,
) -> None:
    for active_entry in detect_stale_active_runs(active_entries, now=current_time):
        path = str(active_entry.get("_path"))
        suggestions[path] = {
            "path": path,
            "reason": "stale active-run metadata; the run was likely interrupted before finalize",
        }


def build_cleanup_suggestions(
    entries: list[dict[str, Any]],
    *,
    active_entries: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
    keep_days: int = DEFAULT_KEEP_DAYS,
    keep_latest: int = DEFAULT_KEEP_LATEST,
) -> list[dict[str, Any]]:
    current_time = now or utc_now()
    suggestions: dict[str, dict[str, Any]] = {}
    append_age_based_suggestions(
        suggestions,
        entries,
        current_time=current_time,
        keep_days=keep_days,
        keep_latest=keep_latest,
    )
    append_superseded_suggestions(suggestions, entries)
    append_stale_active_suggestions(suggestions, active_entries or [], current_time=current_time)
    return sorted(suggestions.values(), key=lambda item: item["path"])
