#!/usr/bin/env python3

from common.cpn_classical_state import resolve_cpn_classical_state_payload, resolve_cpn_local_state

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from classical.cpn_local_ray_solver import solve_cpn_local_ray_ground_state
    from classical.sun_gswt_classical_solver import diagnose_sun_gswt_classical_state
    from classical.sunny_sun_classical_driver import run_sunny_sun_classical
else:
    from .cpn_local_ray_solver import solve_cpn_local_ray_ground_state
    from .sun_gswt_classical_solver import diagnose_sun_gswt_classical_state
    from .sunny_sun_classical_driver import run_sunny_sun_classical


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


def _completion_payload(
    *,
    status,
    backend,
    search_mode,
    max_linear_size,
    repeats_required,
    stopped_reason,
    lower_bound_gap,
    max_residual_norm,
    reason=None,
):
    payload = {
        "status": str(status),
        "backend": backend,
        "search_mode": search_mode,
        "max_linear_size": max_linear_size,
        "repeats_required": repeats_required,
        "stopped_reason": stopped_reason,
        "lower_bound_gap": lower_bound_gap,
        "max_residual_norm": max_residual_norm,
    }
    if reason is not None:
        payload["reason"] = str(reason)
    return payload


def finalize_cpn_glt_result(
    model,
    glt_result,
    *,
    starts=1,
    seed=0,
    completion_backend="cpn-local-ray-minimize",
    max_linear_size=None,
    convergence_repeats=1,
    gap_tolerance=2.5e-1,
    stationarity_tolerance=1.0e-6,
):
    if not isinstance(glt_result, dict):
        raise ValueError("glt_result must be a dictionary")

    if str(glt_result.get("solver_role")) == "final":
        result = dict(glt_result)
        result["completion"] = _completion_payload(
            status="not_needed",
            backend=None,
            search_mode=None,
            max_linear_size=None,
            repeats_required=None,
            stopped_reason=None,
            lower_bound_gap=0.0,
            max_residual_norm=0.0,
        )
        return result

    candidate_state = _candidate_state(glt_result)
    if not isinstance(candidate_state, dict):
        result = dict(glt_result)
        result["completion"] = _completion_payload(
            status="failed",
            backend=None,
            search_mode=None,
            max_linear_size=None,
            repeats_required=None,
            stopped_reason="missing_candidate_state",
            lower_bound_gap=None,
            max_residual_norm=None,
            reason="missing_candidate_state",
        )
        return result

    resolved_state = resolve_cpn_local_state(candidate_state, default_supercell_shape=[1, 1, 1])
    if resolved_state is None:
        result = dict(glt_result)
        result["completion"] = _completion_payload(
            status="failed",
            backend=None,
            search_mode=None,
            max_linear_size=None,
            repeats_required=None,
            stopped_reason="unusable_candidate_state",
            lower_bound_gap=None,
            max_residual_norm=None,
            reason="unusable_candidate_state",
        )
        return result

    resolved_backend = str(completion_backend)
    linear_size = max(int(value) for value in resolved_state["shape"])
    resolved_max_linear_size = max(1, int(max_linear_size)) if max_linear_size is not None else int(linear_size)
    resolved_repeats = max(1, int(convergence_repeats))

    if resolved_backend == "cpn-local-ray-minimize":
        refined = solve_cpn_local_ray_ground_state(
            model,
            starts=max(1, int(starts)),
            seed=int(seed),
            initial_state=candidate_state,
            max_linear_size=int(resolved_max_linear_size),
            convergence_repeats=int(resolved_repeats),
        )
    elif resolved_backend == "sunny-cpn-minimize":
        sunny_payload = {
            "backend": "Sunny.jl",
            "payload_kind": "sunny_sun_classical",
            "model": model,
            "supercell_shape": [int(value) for value in resolved_state["shape"]],
            "initial_local_rays": list(resolved_state["local_rays"]),
            "starts": max(1, int(starts)),
            "seed": int(seed),
        }
        backend_result = run_sunny_sun_classical(sunny_payload)
        if backend_result.get("status") != "ok":
            error = backend_result.get("error", {}) if isinstance(backend_result.get("error"), dict) else {}
            result = dict(glt_result)
            result["completion"] = _completion_payload(
                status="failed",
                backend=resolved_backend,
                search_mode="single-shot",
                max_linear_size=int(linear_size),
                repeats_required=1,
                stopped_reason=error.get("code", "backend_failed"),
                lower_bound_gap=None,
                max_residual_norm=None,
                reason=error.get("message", "sunny backend failed"),
            )
            return result
        refined_state = resolve_cpn_classical_state_payload(
            backend_result,
            default_supercell_shape=resolved_state["shape"],
        )
        diagnostics = diagnose_sun_gswt_classical_state(model, refined_state)
        refined = {
            "energy": float(backend_result.get("energy", glt_result.get("energy", 0.0))),
            "classical_state": refined_state,
            "projector_diagnostics": diagnostics.get("projector_diagnostics"),
            "stationarity": diagnostics.get("stationarity", {}),
            "backend_stationarity": backend_result.get("backend_stationarity"),
            "convergence": {
                "energy_converged": True,
                "search_mode": "single-shot",
                "max_linear_size": int(linear_size),
                "repeats_required": 1,
                "stopped_reason": "backend-finished",
            },
        }
    else:
        raise ValueError(f"unsupported completion_backend: {completion_backend}")

    lower_bound = float(glt_result.get("energy", glt_result.get("lower_bound", refined.get("energy", 0.0))))
    refined_energy = float(refined.get("energy", lower_bound))
    stationarity = float(
        refined.get("stationarity", {}).get("max_residual_norm", float("inf"))
    )
    energy_gap = float(refined_energy - lower_bound)
    convergence = refined.get("convergence", {}) if isinstance(refined.get("convergence"), dict) else {}
    converged = bool(convergence.get("energy_converged", False))

    result = dict(glt_result)
    result["completion"] = _completion_payload(
        status="converged" if converged else "failed",
        backend=resolved_backend,
        search_mode=convergence.get("search_mode"),
        max_linear_size=convergence.get("max_linear_size"),
        repeats_required=convergence.get("repeats_required"),
        stopped_reason=convergence.get("stopped_reason"),
        lower_bound_gap=float(energy_gap),
        max_residual_norm=float(stationarity),
    )

    if converged and stationarity <= float(stationarity_tolerance) and energy_gap <= float(gap_tolerance):
        result["solver_role"] = "final"
        result["promotion_reason"] = "completed_cp_manifold_solution"
        result["classical_state"] = dict(refined.get("classical_state", candidate_state))
        result["energy"] = float(refined_energy)
        return result

    if energy_gap > float(gap_tolerance):
        result["completion"]["status"] = "gap_too_large"
    return result
