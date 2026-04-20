#!/usr/bin/env python3

from common.cpn_classical_state import resolve_cpn_local_state

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from classical.cpn_local_ray_solver import solve_cpn_local_ray_ground_state
else:
    from .cpn_local_ray_solver import solve_cpn_local_ray_ground_state


def _candidate_state(glt_result):
    if not isinstance(glt_result, dict):
        return None
    if isinstance(glt_result.get("classical_state"), dict):
        return glt_result.get("classical_state")
    seed_candidate = glt_result.get("seed_candidate", {})
    if isinstance(seed_candidate, dict) and isinstance(seed_candidate.get("classical_state"), dict):
        return seed_candidate.get("classical_state")
    reconstruction = glt_result.get("reconstruction", {})
    if isinstance(reconstruction, dict) and isinstance(reconstruction.get("completion_candidate"), dict):
        return reconstruction.get("completion_candidate")
    if isinstance(reconstruction, dict) and isinstance(reconstruction.get("classical_state"), dict):
        return reconstruction.get("classical_state")
    return None


def finalize_cpn_glt_result(
    model,
    glt_result,
    *,
    starts=1,
    seed=0,
    gap_tolerance=2.5e-1,
    stationarity_tolerance=1.0e-6,
):
    if not isinstance(glt_result, dict):
        raise ValueError("glt_result must be a dictionary")

    if str(glt_result.get("solver_role")) == "final":
        result = dict(glt_result)
        result["completion"] = {
            "status": "not_needed",
            "lower_bound_gap": 0.0,
            "max_residual_norm": 0.0,
        }
        return result

    candidate_state = _candidate_state(glt_result)
    if not isinstance(candidate_state, dict):
        result = dict(glt_result)
        result["completion"] = {"status": "failed", "reason": "missing_candidate_state"}
        return result

    resolved_state = resolve_cpn_local_state(candidate_state, default_supercell_shape=[1, 1, 1])
    if resolved_state is None:
        result = dict(glt_result)
        result["completion"] = {"status": "failed", "reason": "unusable_candidate_state"}
        return result

    linear_size = max(int(value) for value in resolved_state["shape"])
    refined = solve_cpn_local_ray_ground_state(
        model,
        starts=max(1, int(starts)),
        seed=int(seed),
        initial_state=candidate_state,
        max_linear_size=max(1, int(linear_size)),
        convergence_repeats=1,
    )
    lower_bound = float(glt_result.get("energy", glt_result.get("lower_bound", refined.get("energy", 0.0))))
    refined_energy = float(refined.get("energy", lower_bound))
    stationarity = float(
        refined.get("stationarity", {}).get("max_residual_norm", float("inf"))
    )
    energy_gap = float(refined_energy - lower_bound)
    converged = bool(refined.get("convergence", {}).get("energy_converged", False))

    result = dict(glt_result)
    result["completion"] = {
        "status": "converged" if converged else "failed",
        "lower_bound_gap": float(energy_gap),
        "max_residual_norm": float(stationarity),
    }

    if converged and stationarity <= float(stationarity_tolerance) and energy_gap <= float(gap_tolerance):
        result["solver_role"] = "final"
        result["promotion_reason"] = "completed_cp_manifold_solution"
        result["classical_state"] = dict(refined.get("classical_state", candidate_state))
        result["energy"] = float(refined_energy)
        return result

    if energy_gap > float(gap_tolerance):
        result["completion"]["status"] = "gap_too_large"
    return result
