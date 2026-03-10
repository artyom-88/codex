from __future__ import annotations

from .git_tools import check_ignore, staged_blob_text
from .models import Issue
from .pattern_config import PatternConfig


def validate_paths(paths: list[str]) -> list[Issue]:
    issues: list[Issue] = []
    for path in paths:
        completed = check_ignore(path)
        if completed.returncode == 0:
            issues.append(
                Issue(
                    path=path,
                    reason="staged path is ignored by .gitignore and outside the shareable allowlist",
                )
            )
        elif completed.returncode != 1:
            stderr = completed.stderr.strip() or f"git check-ignore exited {completed.returncode}"
            issues.append(Issue(path=path, reason=f"unable to evaluate .gitignore rules: {stderr}"))
    return issues


def scan_content(path: str, text: str, patterns: PatternConfig) -> list[Issue]:
    issues: list[Issue] = []
    for pattern in patterns.secret_patterns:
        if pattern.compiled.search(text):
            issues.append(Issue(path=path, reason=f"{pattern.label} detected in staged content"))
    for pattern in patterns.private_surface_patterns:
        if pattern.compiled.search(text):
            issues.append(Issue(path=path, reason=f"{pattern.label} detected in staged content"))
    return issues


def deterministic_scan(paths: list[str], patterns: PatternConfig) -> list[Issue]:
    issues = validate_paths(paths)
    for path in paths:
        try:
            text = staged_blob_text(path)
        except RuntimeError as exc:
            issues.append(Issue(path=path, reason=str(exc)))
            continue
        issues.extend(scan_content(path, text, patterns))
    return issues
