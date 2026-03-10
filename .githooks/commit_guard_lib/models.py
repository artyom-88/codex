from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Issue:
    path: str
    reason: str
