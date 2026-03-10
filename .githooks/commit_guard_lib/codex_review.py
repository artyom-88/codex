from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from .git_tools import run_command
from .models import Issue
from .settings import GuardSettings, REPO_ROOT, SCHEMA_PATH


def _summarize_paths(paths: list[str], max_paths: int) -> str:
    visible = paths[:max_paths]
    lines = [f"- {path}" for path in visible]
    omitted = len(paths) - len(visible)
    if omitted > 0:
        lines.append(f"- ... {omitted} more staged path(s) omitted from this list")
    return "\n".join(lines)


def build_prompt(paths: list[str], diff_stat_text: str, diff_text: str, settings: GuardSettings) -> str:
    path_lines = _summarize_paths(paths, settings.max_review_paths)
    return f"""You are the final safety gate for a shareable Codex home repository.

Review the staged diff and decide whether this commit is safe to publish.

Repository policy:
- Allowed staged paths are only those not ignored by the current .gitignore.
- This repo is meant to publish only reusable, anonymized, non-secret content.
- Block anything that contains credentials, auth/config/history/runtime-state data, local machine paths, copied transcripts, or content that is not clearly safe to share.
- If unsure, block.

Important review rule:
- Do not block the hook implementation or its policy/config files merely because they contain regex patterns, denylist constants, schema text, or documented examples of forbidden content.
- Only block if the diff appears to contain actual sensitive values, actual local/private state, or content that is otherwise unsafe to publish.

Return JSON matching the provided schema.

Staged path summary:
- Total staged paths: {len(paths)}
- Review path list limit: {settings.max_review_paths}
{path_lines}

Staged diff stat:
```text
{diff_stat_text}
```

Staged diff excerpt:
```diff
{diff_text}
```
"""


def parse_result(payload: dict[str, object]) -> list[Issue]:
    if payload.get("decision") == "allow":
        return []

    issues: list[Issue] = []
    for item in payload.get("blocking_issues", []):
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "(unknown)")
        reason = str(item.get("reason") or payload.get("summary") or "codex blocked the commit")
        issues.append(Issue(path=path, reason=reason))

    if not issues:
        issues.append(Issue(path="(hook)", reason=str(payload.get("summary") or "codex blocked the commit")))
    return issues


def run_codex_review(
    paths: list[str],
    diff_stat_text: str,
    diff_text: str,
    settings: GuardSettings,
) -> list[Issue]:
    codex_bin = shutil.which("codex")
    if codex_bin is None:
        return [Issue(path="(hook)", reason="codex CLI is not installed or not on PATH")]

    prompt = build_prompt(paths, diff_stat_text, diff_text, settings)
    with tempfile.TemporaryDirectory(prefix="commit-guard-") as temp_dir:
        output_path = Path(temp_dir) / "codex-output.json"
        args = [
            codex_bin,
            "-a",
            "never",
            "exec",
            "--ephemeral",
            "-s",
            "read-only",
            "--color",
            "never",
            "-C",
            str(REPO_ROOT),
            "--output-schema",
            str(SCHEMA_PATH),
            "-o",
            str(output_path),
            "-",
        ]

        try:
            completed = run_command(
                args,
                input_text=prompt,
                timeout=settings.codex_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return [Issue(path="(hook)", reason="codex review timed out")]
        except RuntimeError as exc:
            return [Issue(path="(hook)", reason=str(exc))]

        if completed.returncode != 0:
            stderr = completed.stderr.strip() or completed.stdout.strip() or "codex review failed"
            return [Issue(path="(hook)", reason=f"codex review failed: {stderr}")]

        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return [Issue(path="(hook)", reason="codex did not produce an output file")]
        except json.JSONDecodeError as exc:
            return [Issue(path="(hook)", reason=f"codex returned invalid JSON: {exc}")]

    return parse_result(payload)
