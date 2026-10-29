#!/usr/bin/env python3
"""Additive model-driven 3D workflow. Read JSON input; write JSON to stdout."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.hamiltonian_symmetry_gate import SymmetryGateRequest, run_hamiltonian_symmetry_gate
from common.canonical_hamiltonian import compile_canonical_hamiltonian
from common.model_analysis import run_model_analysis
from three_dimensional.spin_system import PeriodicSpinSystem, minimize_fixed_length
from three_dimensional.spin_waves import spin_wave_spectrum
from three_dimensional.ewald import dipolar_ewald
from three_dimensional.monte_carlo import classical_monte_carlo, classical_finite_size
from three_dimensional.quantum import quantum_low_energy
from three_dimensional.spin_payload import global_spin_payload


def _run_workflow(model, request):
    """Validate the full Hamiltonian before selecting a compatible calculation."""
    if request.get("task") == "dipolar_ewald":
        if "terms" in model or "schema_version" in model:
            raise ValueError("dipolar_ewald takes explicit geometry and moments, not a truncated canonical Hamiltonian")
        calculation = dipolar_ewald(model, request)
        return {"status": calculation["status"], "task": "dipolar_ewald", "calculation": calculation}
    if model.get("schema_version") == "lattice-term-contract/v1":
        model = compile_canonical_hamiltonian(model)
    gate = run_hamiltonian_symmetry_gate(
        model, SymmetryGateRequest(repair=request.get("symmetry_repair", False)))
    if gate["status"] != "ok":
        return gate
    for term in gate["solver_model"].get("terms", []):
        cluster = term.get("cluster", [])
        if (term.get("operator_family") in {"bilinear_exchange_tensor", "bilinear_exchange_matrix"}
                and len(cluster) == 2 and cluster[0] == cluster[1]):
            raise ValueError("solver-capability-mismatch: onsite self bond %s requires an onsite solver"
                             % term.get("term_ref"))
    task = request.get("task")
    if task == "fourier_exchange_spectrum":
        calculation = run_model_analysis(gate, request)
        calculation["eigenvector_coordinate_frame"] = "input spin-component basis at each site"
    elif task == "classical_finite_size":
        calculation = classical_finite_size(global_spin_payload(gate), request)
    elif task in {"classical_ground_state", "spin_wave_spectrum", "classical_monte_carlo", "quantum_low_energy"}:
        payload = global_spin_payload(gate)
        system = PeriodicSpinSystem(payload, request["supercell_shape"])
        solver = {"classical_ground_state": minimize_fixed_length,
                  "spin_wave_spectrum": spin_wave_spectrum,
                  "classical_monte_carlo": classical_monte_carlo,
                  "quantum_low_energy": quantum_low_energy}[task]
        calculation = solver(system, request)
        calculation["spin_coordinate_frame"] = "global Cartesian (crystallographic axes)"
        calculation["bridge_metadata"] = payload["bridge_metadata"]
    else:
        calculation = {"status": "unsupported", "task": task,
                       "blocker": "unsupported-three-dimensional-task"}
    return {
        "status": calculation["status"], "task": task,
        "solver_model_hash": gate["symmetry_validation_stamp"]["hamiltonian_hash"],
        "symmetry_validation": gate["symmetry_validation"],
        "hamiltonian_provenance": gate["hamiltonian_provenance"],
        "warnings": list(gate.get("warnings") or []),
        **({"symmetry_repair_report": gate["symmetry_repair_report"]} if "symmetry_repair_report" in gate else {}),
        "calculation": calculation,
    }


def run_three_dimensional_workflow(model, request):
    """Return model/request and capability failures without fabricating results."""
    try:
        return _run_workflow(model, request)
    except (KeyError, ValueError) as error:
        message = str(error)
        unsupported = "solver-capability-mismatch" in message or "unsupported-classical-space" in message
        return {"status": "unsupported" if unsupported else "invalid_request",
                "task": request.get("task"), "blocker": message}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", help="JSON with model and request; default stdin")
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8")) if args.input else json.load(sys.stdin)
    result = run_three_dimensional_workflow(data["model"], data["request"])
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
