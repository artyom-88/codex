from __future__ import annotations

import subprocess

from .settings import MAX_DIFF_CHARS, REPO_ROOT


def run_command(
    args: list[str],
    *,
    input_text: str | None = None,
    timeout: int = 30,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        cwd=REPO_ROOT,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if check and completed.returncode != 0:
        stderr = completed.stderr.strip() or "command failed"
        raise RuntimeError(f"{' '.join(args)}: {stderr}")
    return completed


def staged_paths() -> list[str]:
    completed = run_command(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"],
        timeout=10,
    )
    return [path for path in completed.stdout.split("\0") if path]


def check_ignore(path: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", "--", path],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def staged_blob_text(path: str) -> str:
    completed = run_command(["git", "show", f":{path}"], timeout=20)
    return completed.stdout


def staged_diff(paths: list[str]) -> str:
    args = ["git", "diff", "--cached", "--no-ext-diff", "--text", "--unified=3", "--"]
    args.extend(paths)
    completed = run_command(args, timeout=30)
    diff = completed.stdout
    if len(diff) > MAX_DIFF_CHARS:
        truncated = len(diff) - MAX_DIFF_CHARS
        diff = (
            diff[:MAX_DIFF_CHARS]
            + f"\n\n[diff truncated by commit_guard.py; omitted {truncated} trailing characters]\n"
        )
    return diff
