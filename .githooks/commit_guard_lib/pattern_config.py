from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import tomllib

from .settings import HOOKS_DIR

PATTERN_CONFIG_PATH = HOOKS_DIR / "commit_guard_patterns.toml"


@dataclass(frozen=True)
class CompiledPattern:
    label: str
    regex: str
    compiled: re.Pattern[str]


@dataclass(frozen=True)
class PatternConfig:
    secret_patterns: tuple[CompiledPattern, ...]
    private_surface_patterns: tuple[CompiledPattern, ...]


def _load_file(path: Path) -> dict[str, object]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except FileNotFoundError as exc:
        raise RuntimeError(f"pattern config file not found: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise RuntimeError(f"invalid pattern config TOML: {exc}") from exc


def _compile_patterns(raw: object, key: str) -> tuple[CompiledPattern, ...]:
    if not isinstance(raw, list):
        raise RuntimeError(f"{key} must be an array of tables")

    compiled_patterns: list[CompiledPattern] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise RuntimeError(f"{key}[{index}] must be a table")

        label = item.get("label")
        regex = item.get("regex")
        if not isinstance(label, str) or not label.strip():
            raise RuntimeError(f"{key}[{index}].label must be a non-empty string")
        if not isinstance(regex, str) or not regex.strip():
            raise RuntimeError(f"{key}[{index}].regex must be a non-empty string")

        try:
            compiled = re.compile(regex)
        except re.error as exc:
            raise RuntimeError(f"{key}[{index}] has invalid regex {label!r}: {exc}") from exc

        compiled_patterns.append(CompiledPattern(label=label, regex=regex, compiled=compiled))
    return tuple(compiled_patterns)


def load_pattern_config(path: Path = PATTERN_CONFIG_PATH) -> PatternConfig:
    payload = _load_file(path)
    return PatternConfig(
        secret_patterns=_compile_patterns(payload.get("secret_patterns"), "secret_patterns"),
        private_surface_patterns=_compile_patterns(payload.get("private_surface_patterns"), "private_surface_patterns"),
    )
