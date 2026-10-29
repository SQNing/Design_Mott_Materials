"""Small, explicit contracts shared by the workflow and subprocess workers."""
import hashlib
import json
import math
import re
import sys
import os
from pathlib import Path
from importlib import metadata

SCRIPTS = Path(__file__).resolve().parents[1]
TASK_ALIASES = {"harmonic_spectrum": "spin_wave_spectrum",
                "thermodynamics": "classical_monte_carlo"}
DEFAULT_BUDGET = {"max_solver_runs": 16, "max_wall_time_seconds": 1800,
                  "max_memory_mb": 4096}


def json_safe(value):
    if isinstance(value, complex):
        return {"kind": "complex", "re": value.real, "im": value.imag}
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if hasattr(value, "tolist"):
        return json_safe(value.tolist())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def digest(value):
    data = json.dumps(json_safe(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode()
    return hashlib.sha256(data).hexdigest()


def restore_complex(value):
    if isinstance(value, dict):
        if value.get("kind") == "complex":
            return complex(value.get("re", value.get("real", 0.)),
                           value.get("im", value.get("imag", 0.)))
        return {k: restore_complex(v) for k, v in value.items()}
    if isinstance(value, list):
        return [restore_complex(v) for v in value]
    return value


def validate_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", value):
        raise ValueError("action_id must be a short filename-safe identifier")
    return value


def task_name(name):
    return TASK_ALIASES.get(name, name)


def budget_for(request):
    result = {**DEFAULT_BUDGET, **request.get("budget", {})}
    for key in DEFAULT_BUDGET:
        value = result[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError("budget must be positive and finite: " + key)
    if int(result["max_solver_runs"]) != result["max_solver_runs"]:
        raise ValueError("max_solver_runs must be an integer")
    result["max_solver_runs"] = int(result["max_solver_runs"])
    return result


def runtime_identity():
    versions = {}
    for package in ("numpy", "scipy"):
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = None
    return {"python": sys.version.split()[0], "executable": sys.executable,
            "packages": versions,
            "backend_environment": {k: os.environ[k] for k in ("DESIGN_MOTT_JULIA_CMD",
                "DESIGN_MOTT_JULIA_BIN", "DESIGN_MOTT_JULIA_DEPOT") if k in os.environ}}


def code_identity():
    hashes = {}
    for directory in ("research", "common", "input", "simplify", "classical",
                      "lswt", "three_dimensional", "cli"):
        for p in sorted(p for p in (SCRIPTS / directory).iterdir() if p.suffix in {".py", ".jl", ".sh"}):
            hashes[str(p.relative_to(SCRIPTS))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return {"source_hash": digest(hashes), "runtime": runtime_identity()}

