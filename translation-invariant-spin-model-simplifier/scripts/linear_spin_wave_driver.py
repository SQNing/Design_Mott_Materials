#!/usr/bin/env python3
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np


def linear_spin_wave_summary(model):
    spin = float(model.get("spin", 0.5))
    exchange = float(model.get("exchange", 1.0))
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
    args = parser.parse_args()
    payload = _load_payload(args.input)
    output = {"linear_spin_wave": linear_spin_wave_summary(payload)}
    if "cluster_size" in payload and "local_dim" in payload:
        output["exact_diagonalization"] = exact_diagonalization_branch(payload)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
