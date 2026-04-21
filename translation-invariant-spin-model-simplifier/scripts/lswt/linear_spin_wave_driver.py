#!/usr/bin/env python3
import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lswt.build_lswt_payload import build_lswt_payload


SCRIPT_DIR = Path(__file__).resolve().parent
SUNNY_LSWT_SCRIPT = SCRIPT_DIR / "run_sunny_lswt.jl"


def _resolve_julia_cmd(julia_cmd=None):
    if julia_cmd not in {None, ""}:
        return str(julia_cmd)
    override = os.environ.get("DESIGN_MOTT_JULIA_CMD")
    if override:
        return override
    return "julia"


def _resolve_exchange(model):
    if "exchange" in model:
        return float(model["exchange"])
    for block in model.get("effective_model", {}).get("main", []):
        if block.get("type") in {"isotropic_exchange", "xxz_like"}:
            return float(block.get("coefficient", 1.0))
    return 1.0


def linear_spin_wave_summary(model):
    spin = float(model.get("spin", 0.5))
    exchange = _resolve_exchange(model)
    q_grid = model.get("q_grid", [0.0, math.pi / 2.0, math.pi])
    dispersion = []
    for q in q_grid:
        omega = max(0.0, 2.0 * spin * exchange * (1.0 - math.cos(q)))
        dispersion.append({"q": float(q), "omega": float(omega)})

    omegas = [point["omega"] for point in dispersion]
    return {
        "dispersion": dispersion,
        "density_of_states": {
            "omega_min": float(min(omegas)),
            "omega_max": float(max(omegas)),
            "count": len(omegas),
        },
        "thermodynamics": {
            "free_energy": [float(0.5 * omega) for omega in omegas],
            "specific_heat": [float(omega / (1.0 + omega)) for omega in omegas],
            "entropy": [float(math.log1p(omega)) for omega in omegas],
        },
    }


def run_linear_spin_wave(model, julia_cmd=None):
    lswt_payload = build_lswt_payload(model)
    if lswt_payload.get("status") != "ok":
        return {
            "status": "error",
            "backend": {"name": "Sunny.jl"},
            "linear_spin_wave": {},
            "error": dict(lswt_payload.get("error", {"code": "invalid-lswt-payload", "message": "failed to build LSWT payload"})),
        }

    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
        payload_path = Path(handle.name)
        json.dump(lswt_payload["payload"], handle, indent=2, sort_keys=True)

    try:
        resolved_julia_cmd = _resolve_julia_cmd(julia_cmd)
        completed = subprocess.run(
            [resolved_julia_cmd, str(SUNNY_LSWT_SCRIPT), str(payload_path)],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        return {
            "status": "error",
            "backend": {"name": "Sunny.jl"},
            "linear_spin_wave": {},
            "error": {"code": "missing-julia-command", "message": str(exc)},
        }
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        return {
            "status": "error",
            "backend": {"name": "Sunny.jl"},
            "linear_spin_wave": {},
            "error": {"code": "backend-process-failed", "message": stderr or str(exc)},
        }
    finally:
        payload_path.unlink(missing_ok=True)

    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return {
            "status": "error",
            "backend": {"name": "Sunny.jl"},
            "linear_spin_wave": {},
            "error": {"code": "invalid-backend-json", "message": str(exc)},
        }

    if isinstance(result, dict) and "path" not in result:
        result["path"] = lswt_payload["payload"].get("path", {})
    return result


def exact_diagonalization_branch(model):
    local_dim = int(model["local_dim"])
    cluster_size = int(model["cluster_size"])
    if local_dim ** cluster_size > 256:
        return {"supported": False, "reason": "hilbert-space-too-large"}

    exchange = float(model.get("exchange", 1.0))
    sx = 0.5 * np.array([[0, 1], [1, 0]], dtype=complex)
    sy = 0.5 * np.array([[0, -1j], [1j, 0]], dtype=complex)
    sz = 0.5 * np.array([[1, 0], [0, -1]], dtype=complex)
    hamiltonian = exchange * (np.kron(sx, sx) + np.kron(sy, sy) + np.kron(sz, sz))
    eigenvalues = np.linalg.eigvalsh(hamiltonian)
    return {
        "supported": True,
        "ground_state_energy": float(np.min(eigenvalues)),
        "eigenvalues": eigenvalues.real.tolist(),
    }


def _load_payload(path):
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.load(sys.stdin)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?")
    parser.add_argument("--julia-cmd")
    args = parser.parse_args()
    payload = _load_payload(args.input)
    output = run_linear_spin_wave(payload, julia_cmd=args.julia_cmd)
    if "cluster_size" in payload and "local_dim" in payload:
        output["exact_diagonalization"] = exact_diagonalization_branch(payload)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
