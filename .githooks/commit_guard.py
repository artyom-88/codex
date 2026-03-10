#!/usr/bin/env python3
"""Thin entrypoint for the tracked pre-commit exposure guard."""

from commit_guard_lib.main import main


if __name__ == "__main__":
    raise SystemExit(main())
