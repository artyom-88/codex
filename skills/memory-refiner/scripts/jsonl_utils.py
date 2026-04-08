#!/usr/bin/env python3
"""Shared JSONL readers for memory-refiner scripts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_jsonl_objects(
    path: Path,
    *,
    keep_invalid_paths: bool = False,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.exists():
        return [], []

    entries: list[dict[str, Any]] = []
    invalid: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                if keep_invalid_paths:
                    invalid.append(f"{path}:{lineno}")
                continue
            if isinstance(payload, dict):
                entries.append(payload)
            elif keep_invalid_paths:
                invalid.append(f"{path}:{lineno}")
    return entries, invalid
