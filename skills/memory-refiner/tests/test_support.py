from __future__ import annotations

from pathlib import Path

from support_shared import load_script_module_from_dir

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"


def load_script_module(module_name: str, filename: str):
    return load_script_module_from_dir(module_name, filename, SCRIPTS_DIR)
