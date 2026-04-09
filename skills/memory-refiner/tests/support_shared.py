from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_script_module_from_dir(module_name: str, filename: str, scripts_dir: Path) -> ModuleType:
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    module_path = scripts_dir / filename
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
