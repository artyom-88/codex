#!/usr/bin/env python3
"""List Codex instruction and configuration surfaces for the active repo context."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from project_context import resolve_project_root

LOCAL_CODEX_SUFFIXES = {".md", ".toml", ".rules", ".yaml", ".yml"}
PROJECT_ARTIFACT_DIRS = {"code-review", "debug", "diff", "plans", "reports"}
LOCAL_CODEX_IGNORED_PREFIXES = {
    (".tmp",),
    ("plugins", "cache"),
}
LOCAL_CODEX_IGNORED_PARTS = {"__pycache__", ".venv", "node_modules"}
LOCAL_CODEX_IGNORED_SUFFIXES = {".pyc"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", default="~/.codex", help="Path to Codex home")
    parser.add_argument("--cwd", default=str(Path.cwd()), help="Current working directory")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    return parser.parse_args()

def count_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        return sum(1 for _ in handle)


def to_display_path(path: Path, base: Path | None = None) -> str:
    if base is not None:
        try:
            return str(path.relative_to(base))
        except ValueError:
            pass
    return str(path)


def file_record(path: Path, scope: str, category: str, display_base: Path | None = None) -> dict[str, Any]:
    stat = path.stat()
    return {
        "scope": scope,
        "category": category,
        "path": str(path),
        "display_path": to_display_path(path, display_base),
        "bytes": stat.st_size,
        "lines": count_lines(path),
    }


def should_skip_local_codex(rel_path: Path) -> bool:
    parts = rel_path.parts
    if any(part in LOCAL_CODEX_IGNORED_PARTS for part in parts):
        return True
    if rel_path.suffix in LOCAL_CODEX_IGNORED_SUFFIXES:
        return True
    return any(parts[: len(prefix)] == prefix for prefix in LOCAL_CODEX_IGNORED_PREFIXES)


def collect_global_surfaces(codex_home: Path) -> list[dict[str, Any]]:
    surfaces: list[dict[str, Any]] = []
    agents = codex_home / "AGENTS.md"
    if agents.exists():
        surfaces.append(file_record(agents, "global", "instruction-root", codex_home))

    config = codex_home / "config.toml"
    if config.exists():
        surfaces.append(file_record(config, "global", "config", codex_home))

    instructions = codex_home / "instructions"
    if instructions.exists():
        for path in sorted(instructions.rglob("*.md")):
            surfaces.append(file_record(path, "global", "instruction-lazy", codex_home))

    rules = codex_home / "rules"
    if rules.exists():
        for path in sorted(rules.glob("*.rules")):
            surfaces.append(file_record(path, "global", "rules", codex_home))

    skills = codex_home / "skills"
    if skills.exists():
        for path in sorted(skills.rglob("SKILL.md")):
            category = "skill-system" if ".system" in path.parts else "skill-user"
            surfaces.append(file_record(path, "global", category, codex_home))
        for path in sorted(skills.rglob("openai.yaml")):
            category = "skill-system-metadata" if ".system" in path.parts else "skill-user-metadata"
            surfaces.append(file_record(path, "global", category, codex_home))

    return surfaces


def collect_project_surfaces(
    project_root: Path | None, codex_home: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if project_root is None:
        return [], []

    surfaces: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    agents = project_root / "AGENTS.md"
    if agents.exists() and not (project_root == codex_home and agents == codex_home / "AGENTS.md"):
        surfaces.append(file_record(agents, "repo-local", "instruction-root", project_root))

    local_codex = project_root / ".codex"
    if local_codex.exists():
        if local_codex.resolve() == codex_home:
            return surfaces, artifacts
        project_agents = local_codex / "AGENTS.md"
        if project_agents.exists():
            surfaces.append(file_record(project_agents, "project-local", "instruction-root", project_root))
        for path in sorted(local_codex.rglob("*")):
            if not path.is_file():
                continue
            rel_path = path.relative_to(local_codex)
            if should_skip_local_codex(rel_path):
                continue
            if rel_path.parts and rel_path.parts[0] in PROJECT_ARTIFACT_DIRS:
                artifacts.append(file_record(path, "project-local", "project-artifact", project_root))
                continue
            if path.suffix not in LOCAL_CODEX_SUFFIXES:
                continue
            if path == project_agents:
                continue
            surfaces.append(file_record(path, "project-local", "local-codex", project_root))

    return surfaces, artifacts


def render_markdown(payload: dict[str, Any]) -> str:
    lines = ["# Codex Memory Surfaces", ""]
    lines.append(f"- Codex home: `{payload['codex_home']}`")
    lines.append(f"- CWD: `{payload['cwd']}`")
    lines.append(f"- Project root: `{payload['project_root'] or 'not found'}`")

    def add_group(title: str, items: list[dict[str, Any]]) -> None:
        lines.extend(["", f"## {title}"])
        if not items:
            lines.append("- None")
            return
        for item in items:
            lines.append(
                f"- `{item['category']}` {item['display_path']} ({item['lines']} lines, {item['bytes']} bytes)"
            )

    add_group("Global Surfaces", payload["global_surfaces"])
    add_group("Project Surfaces", payload["project_surfaces"])
    add_group("Project Artifacts", payload["project_artifacts"])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    codex_home = Path(args.codex_home).expanduser().resolve()
    cwd = Path(args.cwd).expanduser().resolve()
    project_root = resolve_project_root(cwd)

    project_surfaces, project_artifacts = collect_project_surfaces(project_root, codex_home)

    payload = {
        "codex_home": str(codex_home),
        "cwd": str(cwd),
        "project_root": str(project_root) if project_root else None,
        "global_surfaces": collect_global_surfaces(codex_home),
        "project_surfaces": project_surfaces,
        "project_artifacts": project_artifacts,
    }

    if args.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(render_markdown(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
