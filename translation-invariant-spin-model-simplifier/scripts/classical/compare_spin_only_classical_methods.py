#!/usr/bin/env python3
import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from classical.classical_solver_driver import run_classical_solver
    from common.downstream_stage_routing import resolve_downstream_stage_route
else:
    from .classical_solver_driver import run_classical_solver
    from common.downstream_stage_routing import resolve_downstream_stage_route


_DEFAULT_METHODS = ("auto", "luttinger-tisza", "generalized-lt", "variational")


def _json_safe(value):
    if isinstance(value, complex):
        if abs(value.imag) <= 1.0e-12:
            return float(value.real)
        return {"real": float(value.real), "imag": float(value.imag)}
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _clear_previous_solver_outputs(payload):
    for key in (
        "recommended_method",
        "classical_state",
        "classical_state_result",
        "lt_result",
        "generalized_lt_result",
        "variational_result",
        "rotating_frame_realization",
        "lswt",
    ):
        payload.pop(key, None)


def _route_summary(payload, stage_name):
    route = resolve_downstream_stage_route(payload, stage_name)
    return {
        "status": route.get("status"),
        "enabled": bool(route.get("enabled")),
        "reason": route.get("reason"),
        "recommended_backend": route.get("recommended_backend"),
    }


def _method_summary(result):
    classical = result.get("classical", {}) if isinstance(result, dict) else {}
    classical_state_result = result.get("classical_state_result", {}) if isinstance(result, dict) else {}
    auto_resolution = classical.get("auto_resolution", {}) if isinstance(classical, dict) else {}
    return {
        "requested_method": classical.get("requested_method"),
        "chosen_method": classical.get("chosen_method"),
        "recommended_method": result.get("recommended_method"),
        "resolved_method": auto_resolution.get("resolved_method"),
        "resolution_reason": auto_resolution.get("reason"),
        "evaluated_methods": list(auto_resolution.get("evaluated_methods", []))
        if isinstance(auto_resolution, dict)
        else [],
        "energy": classical_state_result.get("energy"),
        "ordering": classical_state_result.get("ordering"),
        "supercell_shape": classical_state_result.get("supercell_shape"),
        "standardized_method": classical_state_result.get("method"),
        "lswt_route": _route_summary(result, "lswt"),
    }


def compare_spin_only_classical_methods(payload, *, methods=None, starts=16, seed=0):
    selected_methods = list(methods or _DEFAULT_METHODS)
    results = {}

    for method in selected_methods:
        candidate = deepcopy(payload)
        classical = candidate.get("classical")
        if not isinstance(classical, dict):
            classical = {}
            candidate["classical"] = classical
        classical["method"] = str(method)
        _clear_previous_solver_outputs(candidate)
        solved = run_classical_solver(candidate, starts=starts, seed=seed)
        results[str(method)] = _method_summary(solved)

    best_energy_method = None
    best_energy = None
    for method_name, summary in results.items():
        energy = summary.get("energy")
        if energy is None:
            continue
        if best_energy is None or float(energy) < float(best_energy):
            best_energy = float(energy)
            best_energy_method = str(method_name)
            continue
        if (
            float(energy) == float(best_energy)
            and best_energy_method == "auto"
            and str(method_name) != "auto"
        ):
            best_energy_method = str(method_name)

    return {
        "methods": selected_methods,
        "results": results,
        "comparison": {
            "best_energy_method": best_energy_method,
            "best_energy": best_energy,
        },
    }


def _load_payload(path):
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.load(sys.stdin)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?")
    parser.add_argument("--output")
    parser.add_argument("--starts", type=int, default=16)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--methods", nargs="*", default=list(_DEFAULT_METHODS))
    args = parser.parse_args()

    comparison = compare_spin_only_classical_methods(
        _load_payload(args.input),
        methods=args.methods,
        starts=int(args.starts),
        seed=int(args.seed),
    )
    payload = _json_safe(comparison)
    if args.output:
        Path(args.output).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
