#!/usr/bin/env python3

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from classical.cpn_generalized_lt_solver import solve_cpn_generalized_lt_ground_state
else:
    from ..cpn_generalized_lt_solver import solve_cpn_generalized_lt_ground_state


def normalize_heuristic_seed(result):
    relaxed = result.get("relaxed_lt", {}) if isinstance(result.get("relaxed_lt"), dict) else {}
    weight_search = relaxed.get("weight_search", {}) if isinstance(relaxed.get("weight_search"), dict) else {}
    p_weights = weight_search.get("best_p_weights")
    if not p_weights:
        p_weights = [1.0] * max(1, int(result.get("magnetic_site_count", 1)))
    lower_bound = relaxed.get("lower_bound", result.get("energy"))
    q_vectors = relaxed.get("lowest_shell_q_vectors", [])
    return {
        "q_vector": list(result.get("q_vector", [0.0, 0.0, 0.0])),
        "energy_upper_bound": float(result.get("energy", 0.0)),
        "lower_bound": float(lower_bound if lower_bound is not None else result.get("energy", 0.0)),
        "p_weights": [float(value) for value in p_weights],
        "mode_kind": relaxed.get("mode_kind"),
        "lowest_shell_q_vectors": [list(vector) for vector in q_vectors],
        "projector_exact_solution": bool(
            result.get("projector_exactness", {}).get("is_exact_projector_solution", False)
        ),
        "raw_result": dict(result),
    }


def build_heuristic_seed(model, heuristic_result=None, *, starts=1, seed=0):
    if heuristic_result is None:
        heuristic_result = solve_cpn_generalized_lt_ground_state(
            model,
            requested_method="cpn-generalized-lt",
            starts=int(starts),
            seed=int(seed),
        )
    return normalize_heuristic_seed(heuristic_result)
