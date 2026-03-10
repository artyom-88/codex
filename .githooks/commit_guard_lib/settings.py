from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = HOOKS_DIR.parent
SCHEMA_PATH = HOOKS_DIR / "commit_guard_output.schema.json"


@dataclass(frozen=True)
class GuardSettings:
    codex_timeout_seconds: int
    max_review_diff_chars: int
    max_review_diff_stat_chars: int
    max_review_paths: int


def _read_positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default

    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a positive integer, got {raw!r}") from exc

    if value <= 0:
        raise RuntimeError(f"{name} must be a positive integer, got {raw!r}")
    return value


def load_guard_settings() -> GuardSettings:
    return GuardSettings(
        codex_timeout_seconds=_read_positive_int("COMMIT_GUARD_CODEX_TIMEOUT_SECONDS", 180),
        max_review_diff_chars=_read_positive_int("COMMIT_GUARD_MAX_REVIEW_DIFF_CHARS", 30_000),
        max_review_diff_stat_chars=_read_positive_int("COMMIT_GUARD_MAX_REVIEW_DIFF_STAT_CHARS", 4_000),
        max_review_paths=_read_positive_int("COMMIT_GUARD_MAX_REVIEW_PATHS", 50),
    )
