"""Compatibility shim: make `backend.energy_consumption` importable while
the source files live in `backend/energy-consumption/` (hyphen in name).

This dynamically loads any .py files from the sibling `energy-consumption`
directory as submodules of this package (e.g. `predict`, `train_model`).
"""
from pathlib import Path
import importlib.util
import sys


_THIS_PKG = __package__  # 'backend.energy_consumption'
_PKG_DIR = Path(__file__).resolve().parent
_ALT_DIR = _PKG_DIR.parent / "energy-consumption"

if _ALT_DIR.exists():
    for _py in sorted(_ALT_DIR.glob("*.py")):
        _name = _py.stem
        try:
            _spec = importlib.util.spec_from_file_location(f"{_THIS_PKG}.{_name}", str(_py))
            _mod = importlib.util.module_from_spec(_spec)
            # register module before executing to allow intra-module imports
            sys.modules[_spec.name] = _mod
            _spec.loader.exec_module(_mod)
            # expose as attribute on this package
            globals()[_name] = _mod
        except Exception:
            # if loading fails, skip so tests can still import other modules
            continue
else:
    # nothing to shim; package may be installed differently
    pass
