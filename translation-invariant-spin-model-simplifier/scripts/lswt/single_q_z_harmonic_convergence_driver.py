#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.classical_contract_resolution import get_classical_state_result, get_standardized_classical_state
from lswt.single_q_z_harmonic_convergence import analyze_single_q_z_harmonic_convergence


def _load_pipeline_output_directory(path):
    path = Path(path)
    classical_model_path = path / "classical_model.json"
    solver_result_path = path / "solver_result.json"
    if not classical_model_path.exists():
        raise ValueError(f"missing pipeline artifact: {classical_model_path}")
    if not solver_result_path.exists():
        raise ValueError(f"missing pipeline artifact: {solver_result_path}")

    payload = json.loads(classical_model_path.read_text(encoding="utf-8"))
    solver_result = json.loads(solver_result_path.read_text(encoding="utf-8"))
    payload["classical_state"] = solver_result
    classical_state_result = get_classical_state_result(solver_result)
    if isinstance(classical_state_result, dict):
        payload["classical_state_result"] = classical_state_result
        compatibility_state = get_standardized_classical_state(solver_result)
        if isinstance(compatibility_state, dict):
            if any(
                solver_result.get(key) is not None
                for key in ("reference_ray", "generator_matrix", "site_ansatz", "ansatz_stationarity")
            ):
                payload["classical_state"] = {
                    **solver_result,
                    "classical_state": compatibility_state,
                }
            else:
                payload["classical_state"] = compatibility_state

    gswt_payload_path = path / "gswt_payload.json"
    if gswt_payload_path.exists():
        gswt_payload = json.loads(gswt_payload_path.read_text(encoding="utf-8"))
        for key in (
            "phase_grid_size",
            "z_harmonic_cutoff",
            "sideband_cutoff",
            "z_harmonic_reference_mode",
        ):
            if key in gswt_payload:
                payload[key] = gswt_payload[key]
    return payload


def _load_json_payload(payload):
    if isinstance(payload, dict):
        return payload
    if payload is None:
        return json.load(sys.stdin)
    path = Path(payload)
    if path.is_dir():
        return _load_pipeline_output_directory(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_scan_values(payload, plural_key, singular_key):
    if payload.get(plural_key) is not None:
        return payload.get(plural_key)
    singular_value = payload.get(singular_key)
    if singular_value is None:
        return None
    return [singular_value]


def run_single_q_z_harmonic_convergence_driver(
    payload,
    *,
    phase_grid_sizes=None,
    z_harmonic_cutoffs=None,
    sideband_cutoffs=None,
    z_harmonic_reference_mode=None,
):
    payload = _load_json_payload(payload)
    return analyze_single_q_z_harmonic_convergence(
        payload,
        classical_state=payload.get("classical_state"),
        phase_grid_sizes=(
            phase_grid_sizes
            if phase_grid_sizes is not None
            else _resolve_scan_values(payload, "phase_grid_sizes", "phase_grid_size")
        ),
        z_harmonic_cutoffs=(
            z_harmonic_cutoffs
            if z_harmonic_cutoffs is not None
            else _resolve_scan_values(payload, "z_harmonic_cutoffs", "z_harmonic_cutoff")
        ),
        sideband_cutoffs=(
            sideband_cutoffs
            if sideband_cutoffs is not None
            else _resolve_scan_values(payload, "sideband_cutoffs", "sideband_cutoff")
        ),
        z_harmonic_reference_mode=(
            z_harmonic_reference_mode
            if z_harmonic_reference_mode is not None
            else payload.get("z_harmonic_reference_mode", "input")
        ),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?")
    parser.add_argument("--phase-grid-sizes", type=int, nargs="+")
    parser.add_argument("--z-harmonic-cutoffs", type=int, nargs="+")
    parser.add_argument("--sideband-cutoffs", type=int, nargs="+")
    parser.add_argument(
        "--z-harmonic-reference-mode",
        choices=["input", "refined-retained-local"],
    )
    args = parser.parse_args()
    result = run_single_q_z_harmonic_convergence_driver(
        args.input,
        phase_grid_sizes=list(args.phase_grid_sizes) if args.phase_grid_sizes is not None else None,
        z_harmonic_cutoffs=list(args.z_harmonic_cutoffs) if args.z_harmonic_cutoffs is not None else None,
        sideband_cutoffs=list(args.sideband_cutoffs) if args.sideband_cutoffs is not None else None,
        z_harmonic_reference_mode=(
            str(args.z_harmonic_reference_mode) if args.z_harmonic_reference_mode is not None else None
        ),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
