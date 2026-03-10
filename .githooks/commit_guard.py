#!/usr/bin/env python3
"""Thin entrypoint for the tracked pre-commit exposure guard."""

from __future__ import annotations

import sys

MIN_PYTHON = (3, 11)


def _ensure_supported_python() -> None:
    if sys.version_info >= MIN_PYTHON:
        return

    version = ".".join(str(part) for part in MIN_PYTHON)
    print(
        f"pre-commit guard requires Python {version}+; found {sys.version.split()[0]}",
        file=sys.stderr,
    )
    raise SystemExit(1)


if __name__ == "__main__":
    _ensure_supported_python()
    from commit_guard_lib.main import main

    raise SystemExit(main())
