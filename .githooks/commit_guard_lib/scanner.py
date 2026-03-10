from __future__ import annotations

import re

from .git_tools import check_ignore, staged_blob_text
from .models import Issue

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("GitHub PAT", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("OpenAI-style key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Bearer token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{20,}\b")),
    (
        "Secret assignment",
        re.compile(
            r"""(?ix)
            \b(api[_ -]?key|token|secret|password)\b
            \s*[:=]\s*
            ["']?[A-Za-z0-9._/\-+=]{12,}["']?
            """
        ),
    ),
    (
        "Private key block",
        re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
)

PRIVATE_SURFACE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "Absolute local Codex path",
        re.compile(
            r"""(?ix)
            (?:/Users|/home)/[^/\s]+/\.codex/
            (?:
              auth\.json|
              config\.toml|
              history\.jsonl|
              models_cache\.json|
              version\.json|
              sessions/|
              shell_snapshots/|
              tmp/|
              log/|
              logs_\d+\.sqlite(?:-(?:shm|wal))?|
              state_\d+\.sqlite(?:-(?:shm|wal))?
            )
            """
        ),
    ),
    (
        "Session transcript path",
        re.compile(r"\bsessions/\d{4}/\d{2}/\d{2}/rollout-[^\s\"']+\.jsonl\b"),
    ),
    (
        "Shell snapshot path",
        re.compile(r"\bshell_snapshots/[0-9a-f-]+\.sh\b"),
    ),
)


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


def scan_content(path: str, text: str) -> list[Issue]:
    issues: list[Issue] = []
    for label, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            issues.append(Issue(path=path, reason=f"{label} detected in staged content"))
    for label, pattern in PRIVATE_SURFACE_PATTERNS:
        if pattern.search(text):
            issues.append(Issue(path=path, reason=f"{label} detected in staged content"))
    return issues


def deterministic_scan(paths: list[str]) -> list[Issue]:
    issues = validate_paths(paths)
    for path in paths:
        try:
            text = staged_blob_text(path)
        except RuntimeError as exc:
            issues.append(Issue(path=path, reason=str(exc)))
            continue
        issues.extend(scan_content(path, text))
    return issues
