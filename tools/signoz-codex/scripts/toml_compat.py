from __future__ import annotations

import importlib
from types import ModuleType
from typing import Callable


ImportModule = Callable[[str], ModuleType]


def load_toml_module(import_module: ImportModule | None = None) -> ModuleType:
    loader = import_module or importlib.import_module
    try:
        return loader("tomllib")
    except ModuleNotFoundError:
        try:
            return loader("tomli")
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "No TOML parser is available. Install Python 3.11+ or add the 'tomli' package for Python 3.10."
            ) from exc


tomllib = load_toml_module()
TOMLDecodeError = tomllib.TOMLDecodeError
