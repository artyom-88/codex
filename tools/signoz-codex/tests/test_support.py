from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
_SHARED_HELPER = (
    Path(__file__).resolve().parents[3]
    / "skills"
    / "memory-refiner"
    / "tests"
    / "support_shared.py"
)
_SPEC = importlib.util.spec_from_file_location("repo_test_support_shared", _SHARED_HELPER)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Unable to load shared test support from {_SHARED_HELPER}")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def load_script_module(module_name: str, filename: str):
    return _MODULE.load_script_module_from_dir(module_name, filename, SCRIPTS_DIR)
