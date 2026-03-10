from __future__ import annotations

import sys

from .codex_review import run_codex_review
from .git_tools import staged_diff, staged_paths
from .models import Issue
from .scanner import deterministic_scan


def print_status(message: str) -> None:
    print(f"pre-commit guard: {message}", file=sys.stderr, flush=True)


def print_issues(header: str, issues: list[Issue]) -> None:
    print(header, file=sys.stderr)
    for issue in issues:
        print(f"- {issue.path}: {issue.reason}", file=sys.stderr)


def main() -> int:
    print_status("collecting staged files")
    try:
        paths = staged_paths()
    except RuntimeError as exc:
        print(f"pre-commit guard failed: {exc}", file=sys.stderr)
        return 1

    if not paths:
        print_status("no staged files; skipping")
        return 0

    print_status(f"running deterministic checks for {len(paths)} staged path(s)")
    deterministic_issues = deterministic_scan(paths)
    if deterministic_issues:
        print_issues("Commit blocked by deterministic exposure checks:", deterministic_issues)
        return 1

    print_status("deterministic checks passed")
    print_status("building staged diff for Codex review")
    diff_text = staged_diff(paths)

    print_status("running Codex exposure review")
    codex_issues = run_codex_review(paths, diff_text)
    if codex_issues:
        print_issues("Commit blocked by Codex exposure review:", codex_issues)
        return 1

    print_status("Codex review passed")
    print_status("commit guard passed")
    return 0
