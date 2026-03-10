from __future__ import annotations

from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = HOOKS_DIR.parent
SCHEMA_PATH = HOOKS_DIR / "commit_guard_output.schema.json"

CODEX_TIMEOUT_SECONDS = 120
MAX_DIFF_CHARS = 120_000
