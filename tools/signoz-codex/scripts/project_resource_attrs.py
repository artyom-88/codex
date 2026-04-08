#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess  # nosec B404
import tomllib
from collections import OrderedDict
from pathlib import Path

CONFIG_PATH = Path.home() / ".codex" / "config.toml"
GIT_BIN = shutil.which("git") or "git"
GIT_DISCOVERY_TIMEOUT_SECONDS = 2
MANAGED_KEYS = ("project.name", "project.path", "vcs.repository.name")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve and merge native Codex project resource attributes for OTEL_RESOURCE_ATTRIBUTES."
    )
    parser.add_argument("--cwd", default=os.getcwd(), help="Working directory to resolve")
    parser.add_argument("--config", default=str(CONFIG_PATH), help="Path to Codex config.toml")
    parser.add_argument(
        "--existing",
        default=os.environ.get("OTEL_RESOURCE_ATTRIBUTES", ""),
        help="Existing OTEL_RESOURCE_ATTRIBUTES value to merge into",
    )
    return parser.parse_args()


def parse_resource_attributes(raw: str) -> OrderedDict[str, str]:
    # pylint: disable=too-many-branches
    attrs: OrderedDict[str, str] = OrderedDict()
    if not raw:
        return attrs

    parts: list[str] = []
    buffer: list[str] = []
    escaped = False

    for char in raw:
        if escaped:
            buffer.append(char)
            escaped = False
            continue
        if char == "\\":
            buffer.append(char)
            escaped = True
            continue
        if char == ",":
            parts.append("".join(buffer))
            buffer = []
            continue
        buffer.append(char)

    if escaped:
        buffer.append("\\")
    parts.append("".join(buffer))

    for part in parts:
        if not part:
            continue
        key_chars: list[str] = []
        value_chars: list[str] = []
        current = key_chars
        escaped = False
        separator_seen = False

        for char in part:
            if escaped:
                current.append(char)
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == "=" and not separator_seen:
                current = value_chars
                separator_seen = True
                continue
            current.append(char)

        if escaped:
            current.append("\\")

        key = "".join(key_chars)
        value = "".join(value_chars) if separator_seen else ""
        if key:
            attrs[key] = value

    return attrs


def escape_resource_component(value: str) -> str:
    return value.replace("\\", "\\\\").replace(",", "\\,").replace("=", "\\=")


def serialize_resource_attributes(attrs: OrderedDict[str, str]) -> str:
    return ",".join(
        f"{escape_resource_component(key)}={escape_resource_component(value)}" for key, value in attrs.items()
    )


def git_repo_root(cwd: Path) -> Path | None:
    try:
        result = subprocess.run(
            [GIT_BIN, "-C", str(cwd), "rev-parse", "--show-toplevel"],
            check=True,
            text=True,
            capture_output=True,
            timeout=GIT_DISCOVERY_TIMEOUT_SECONDS,
        )  # nosec B603
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None

    output = result.stdout.strip()
    if not output:
        return None
    return Path(output).expanduser().resolve()


def load_codex_projects(config_path: Path) -> list[Path]:
    if not config_path.exists():
        return []

    try:
        with config_path.open("rb") as handle:
            config = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return []

    projects = config.get("projects")
    if not isinstance(projects, dict):
        return []

    resolved: list[Path] = []
    for key in projects.keys():
        if not isinstance(key, str):
            continue
        resolved.append(Path(key).expanduser().resolve())
    return resolved


def nearest_codex_project(cwd: Path, config_path: Path) -> Path | None:
    best_match: Path | None = None
    for candidate in load_codex_projects(config_path):
        try:
            cwd.relative_to(candidate)
        except ValueError:
            continue
        if best_match is None or len(candidate.parts) > len(best_match.parts):
            best_match = candidate
    return best_match


def build_managed_attributes(cwd: Path, config_path: Path) -> OrderedDict[str, str]:
    repo_root = git_repo_root(cwd)
    if repo_root is not None:
        repo_name = repo_root.name or str(repo_root)
        return OrderedDict(
            (
                ("project.name", repo_name),
                ("project.path", str(repo_root)),
                ("vcs.repository.name", repo_name),
            )
        )

    project_root = nearest_codex_project(cwd, config_path)
    if project_root is not None:
        project_name = project_root.name or str(project_root)
        return OrderedDict(
            (
                ("project.name", project_name),
                ("project.path", str(project_root)),
            )
        )

    return OrderedDict()


def merge_resource_attributes(existing: str, managed: OrderedDict[str, str]) -> str:
    attrs = parse_resource_attributes(existing)
    for key in MANAGED_KEYS:
        attrs.pop(key, None)
    attrs.update(managed)
    return serialize_resource_attributes(attrs)


def main() -> int:
    args = parse_args()
    cwd = Path(args.cwd).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve()
    managed = build_managed_attributes(cwd, config_path)
    print(merge_resource_attributes(args.existing, managed), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
