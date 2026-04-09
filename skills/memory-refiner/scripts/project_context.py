#!/usr/bin/env python3
"""Shared project-context helpers for memory-refiner scripts."""

from __future__ import annotations

import shutil
import subprocess  # nosec B404: fixed local git lookup for project root detection
from pathlib import Path

PROJECT_MARKERS = (
    ".codex",
    "AGENTS.md",
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
)


def resolve_project_root(cwd: Path) -> Path | None:
    git_bin = shutil.which("git")
    if git_bin is None:
        result = None
    else:
        try:
            result = subprocess.run(
                [git_bin, "rev-parse", "--show-toplevel"],
                cwd=cwd,
                check=True,
                capture_output=True,
                text=True,
            )  # nosec B603: fixed git command for local repo root detection
        except (subprocess.CalledProcessError, FileNotFoundError):
            result = None

    if result is not None:
        candidate = Path(result.stdout.strip())
        if candidate.exists():
            return candidate

    for candidate in (cwd, *cwd.parents):
        if any((candidate / marker).exists() for marker in PROJECT_MARKERS):
            return candidate
    return None
