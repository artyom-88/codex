from __future__ import annotations

import shutil
import subprocess  # nosec B404: this module intentionally shells out to fixed local tooling

from .settings import REPO_ROOT


def _git_bin() -> str:
    git_bin = shutil.which("git")
    if git_bin is None:
        raise RuntimeError("git is not installed or not on PATH")
    return git_bin


def run_command(
    args: list[str],
    *,
    input_text: str | None = None,
    timeout: int = 30,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(  # nosec B603: callers pass fixed local CLI commands
        args,
        cwd=REPO_ROOT,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if check and completed.returncode != 0:
        stderr = completed.stderr.strip() or "command failed"
        raise RuntimeError(f"{' '.join(args)}: {stderr}")
    return completed


def staged_paths() -> list[str]:
    completed = run_command(
        [_git_bin(), "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"],
        timeout=10,
    )
    return [path for path in completed.stdout.split("\0") if path]


def check_ignore(path: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603: fixed git command over repo-controlled paths
        [_git_bin(), "check-ignore", "-q", "--no-index", "--", path],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def staged_blob_text(path: str) -> str:
    completed = run_command([_git_bin(), "show", f":{path}"], timeout=20)
    return completed.stdout


def _truncate_text(text: str, max_chars: int, label: str) -> str:
    if len(text) <= max_chars:
        return text

    truncated = len(text) - max_chars
    return text[:max_chars] + f"\n\n[{label}; omitted {truncated} trailing characters]\n"


def staged_diff(paths: list[str], max_chars: int) -> str:
    args = [_git_bin(), "diff", "--cached", "--no-ext-diff", "--text", "--unified=3", "--"]
    args.extend(paths)
    completed = run_command(args, timeout=30)
    return _truncate_text(completed.stdout, max_chars, "diff truncated by commit_guard.py")


def staged_diff_stat(paths: list[str], max_chars: int) -> str:
    args = [_git_bin(), "diff", "--cached", "--stat", "--"]
    args.extend(paths)
    completed = run_command(args, timeout=20)
    return _truncate_text(completed.stdout, max_chars, "diff stat truncated by commit_guard.py")
