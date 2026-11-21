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
OBSERVABLES_SCHEMA_VERSION = "observables/v1"


def validate_observables_block(block, backend=None):
    """Minimal observables/v1 shape check; raises ValueError on violation."""
    if not isinstance(block, dict):
        raise ValueError("observables block must be an object")
    if block.get("schema_version") != OBSERVABLES_SCHEMA_VERSION:
        raise ValueError("observables schema_version must be " + OBSERVABLES_SCHEMA_VERSION)
    provenance = block.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("observables block requires provenance")
    for key in ("backend", "cluster", "sector", "convergence", "state"):
        if key not in provenance:
            raise ValueError("observables provenance missing " + key)
    if backend is not None and provenance["backend"] != backend:
        raise ValueError("observables provenance backend mismatch")
    if not isinstance(block.get("static"), dict) or "energy" not in block["static"]:
        raise ValueError("observables block requires static.energy")
    if "dynamic" not in block:
        raise ValueError("observables block requires a dynamic field (may be deferred)")
    return block


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
    # sys.executable can be a relative path in the launching process and an
    # absolute one in the worker; identity must not depend on that spelling.
    # abspath (not realpath) keeps a virtualenv's bin/python symlink intact:
    # resolving it would select the base interpreter and drop site-packages.
    executable = os.path.abspath(sys.executable) if sys.executable else sys.executable
    return {"python": sys.version.split()[0], "executable": executable,
            "packages": versions,
            "backend_environment": {k: os.environ[k] for k in ("SPINFORGE_JULIA_CMD",
                "SPINFORGE_JULIA_BIN", "SPINFORGE_JULIA_DEPOT",
                "DESIGN_MOTT_JULIA_BIN", "DESIGN_MOTT_JULIA_DEPOT") if k in os.environ}}


CODE_GROUPS = ("research", "common", "input", "simplify", "classical",
               "lswt", "three_dimensional", "cli", "quantum")

# Each task only depends on a subset of the source tree. Hashing per task scope
# keeps validation caches and reference chains valid when an unrelated backend
# changes. Groups are names of immediate subdirectories of scripts/.
TASK_CODE_GROUPS = {
    "classical_ground_state": ("common", "classical", "three_dimensional", "research"),
    "spin_wave_spectrum": ("common", "lswt", "three_dimensional", "research"),
    "classical_monte_carlo": ("common", "three_dimensional", "research"),
    "classical_finite_size": ("common", "three_dimensional", "research"),
    "quantum_low_energy": ("common", "three_dimensional", "quantum", "research"),
    "quantum_thermodynamics": ("common", "three_dimensional", "quantum", "research"),
    "fourier_exchange_spectrum": ("common", "three_dimensional", "research"),
    "dipolar_ewald": ("common", "three_dimensional", "research"),
    # Comparison tasks touch every registered solver backend plus the full
    # research layer; keep them on the widest scope.
    "reduction_validation": CODE_GROUPS,
    "mechanism_test": CODE_GROUPS,
}


def task_code_groups(task):
    return tuple(TASK_CODE_GROUPS.get(task, CODE_GROUPS))


def _group_hashes(selected):
    hashes = {}
    for directory in selected:
        root = SCRIPTS / directory
        if not root.is_dir():
            continue
        per_group = {}
        for p in sorted(p for p in root.iterdir() if p.suffix in {".py", ".jl", ".sh"}):
            per_group[str(p.relative_to(SCRIPTS))] = hashlib.sha256(p.read_bytes()).hexdigest()
        hashes[directory] = digest(per_group)
    return hashes


def code_identity(groups=None):
    """Identity of the selected code groups plus the runtime.

    With ``groups=None`` every known group is hashed (legacy full identity).
    A scoped identity stays valid when unrelated backend code changes, so
    validation caches and reference chains survive edits to other solvers.
    """
    selected = tuple(groups) if groups is not None else CODE_GROUPS
    unknown = sorted(set(selected) - set(CODE_GROUPS))
    if unknown:
        raise ValueError("unknown code group: " + ",".join(unknown))
    group_hashes = _group_hashes(selected)
    identity = {"groups": sorted(selected), "group_hashes": group_hashes,
                "source_hash": digest(group_hashes), "runtime": runtime_identity()}
    if groups is None:
        # Legacy shape: no explicit scope means "the full tree".
        identity.pop("groups")
    return identity


def same_code_identity(recorded):
    """A recorded identity is reusable iff its scoped code is unchanged."""
    if not isinstance(recorded, dict) or "source_hash" not in recorded:
        return False
    groups = recorded.get("groups")
    if groups is None or "group_hashes" not in recorded:
        # Legacy full-tree record: compare against the full identity.
        return recorded == code_identity()
    fresh = code_identity(groups=groups)
    if recorded.get("runtime") != fresh.get("runtime"):
        return False
    return all(recorded["group_hashes"].get(group) == fresh["group_hashes"].get(group)
               for group in groups)

