#!/usr/bin/env python3

import numpy as np

from common.lattice_geometry import lattice_vector_rank

from classical.cpn_local_ray_energy import (
    canonical_classical_state,
    evaluate_cpn_local_ray_energy,
    projector_fourier_diagnostics,
    state_array_from_model,
    state_array_from_serialized,
    stationarity_summary,
    sweep_local_ray_state,
    tiled_state_array,
)


def _structural_dimension_from_model(model):
    rank = lattice_vector_rank(
        {
            "lattice_vectors": list(model.get("lattice_vectors", [])),
            "positions": list(model.get("positions", [])),
        }
    )
    return max(1, min(3, int(rank or 1)))


def _structural_supercell_shape(structural_dimension, linear_size):
    linear_size = max(1, int(linear_size))
    if int(structural_dimension) <= 1:
        return (linear_size, 1, 1)
    if int(structural_dimension) == 2:
        return (linear_size, linear_size, 1)
    return (linear_size, linear_size, linear_size)


def _structural_supercell_schedule(structural_dimension, max_linear_size, *, start_linear_size=1):
    start_linear_size = max(1, int(start_linear_size))
    if max_linear_size is None or int(max_linear_size) <= 0:
        linear_size = start_linear_size
        while True:
            yield _structural_supercell_shape(structural_dimension, linear_size)
            linear_size += 1
        return

    max_linear_size = max(start_linear_size, int(max_linear_size))
    for linear_size in range(start_linear_size, max_linear_size + 1):
        yield _structural_supercell_shape(structural_dimension, linear_size)


def _starting_linear_size(supercell_shape, structural_dimension):
    shape = [max(1, int(value)) for value in (supercell_shape or (1, 1, 1))]
    active_axes = 1 if int(structural_dimension) <= 1 else 2 if int(structural_dimension) == 2 else 3
    return max(shape[:active_axes])


def _refine_state(model, initial_state, *, max_sweeps, sweep_tolerance):
    state = np.array(initial_state, dtype=complex, copy=True)
    last_change = None
    for _ in range(int(max_sweeps)):
        state, change = sweep_local_ray_state(model, state)
        last_change = float(change)
        if change <= float(sweep_tolerance):
            break
    diagnostics = {
        "projector_diagnostics": projector_fourier_diagnostics(state),
        "stationarity": stationarity_summary(model, state),
    }
    return {
        "state": state,
        "energy": float(evaluate_cpn_local_ray_energy(model, state)),
        "last_change": float(last_change if last_change is not None else 0.0),
        "diagnostics": diagnostics,
    }


def _snapshot_result(
    model,
    state_array,
    diagnostics,
    history,
    *,
    energy,
    shape,
    starts,
    seed,
    structural_dimension,
    bounded_search,
    max_linear_size,
    repeats_required,
    energy_tolerance,
    stopped_reason,
):
    classical_state = canonical_classical_state(model, state_array, diagnostics)
    return {
        "method": "cpn-local-ray-minimize",
        "manifold": "CP^(N-1)",
        "energy": float(energy),
        "supercell_shape": [int(value) for value in shape],
        "local_rays": list(classical_state["local_rays"]),
        "classical_state": classical_state,
        "projector_diagnostics": diagnostics["projector_diagnostics"],
        "stationarity": diagnostics["stationarity"],
        "convergence": {
            "energy_converged": bool(stopped_reason == "converged"),
            "history": list(history),
            "energy_tolerance": float(energy_tolerance),
            "repeats_required": int(repeats_required),
            "structural_dimension": int(structural_dimension),
            "search_mode": "bounded" if bounded_search else "until-converged",
            "max_linear_size": int(max_linear_size) if bounded_search else None,
            "stopped_reason": str(stopped_reason),
        },
        "starts": int(starts),
        "seed": int(seed),
    }


def solve_cpn_local_ray_ground_state(
    model,
    *,
    starts=8,
    seed=0,
    initial_state=None,
    max_linear_size=1,
    convergence_repeats=1,
    max_sweeps=200,
    sweep_tolerance=1.0e-10,
    energy_tolerance=1.0e-6,
    progress_callback=None,
):
    if model.get("classical_manifold") != "CP^(N-1)":
        raise ValueError("cpn local-ray solver expects a CP^(N-1) classical payload")

    starts = max(1, int(starts))
    repeats_required = max(1, int(convergence_repeats))
    structural_dimension = _structural_dimension_from_model(model)
    seed_state_array = None
    start_linear_size = 1
    if isinstance(initial_state, dict) and initial_state.get("local_rays"):
        seed_state_array = state_array_from_serialized(initial_state)
        start_linear_size = _starting_linear_size(seed_state_array.shape[:3], structural_dimension)
    bounded_search = max_linear_size is not None and int(max_linear_size) > 0
    if bounded_search:
        max_linear_size = max(int(max_linear_size), int(start_linear_size))

    best_state = None
    previous = None
    stable_count = 0
    history = []

    for shape in _structural_supercell_schedule(
        structural_dimension,
        max_linear_size,
        start_linear_size=start_linear_size,
    ):
        candidates = []
        if best_state is None and seed_state_array is not None:
            candidates.append(
                {
                    "source": "glt-seed",
                    "state": (
                        np.array(seed_state_array, copy=True)
                        if tuple(int(value) for value in seed_state_array.shape[:3]) == tuple(int(value) for value in shape)
                        else tiled_state_array(seed_state_array, shape)
                    ),
                }
            )
        if best_state is not None:
            candidates.append({"source": "tiled-previous", "state": tiled_state_array(best_state, shape)})
        while len(candidates) < starts:
            offset = len(candidates)
            candidates.append(
                {
                    "source": "random",
                    "state": state_array_from_model(model, shape, int(seed) + offset),
                }
            )

        best_candidate = None
        for candidate in candidates[:starts]:
            refined = _refine_state(
                model,
                candidate["state"],
                max_sweeps=max_sweeps,
                sweep_tolerance=sweep_tolerance,
            )
            refined["source"] = str(candidate["source"])
            if best_candidate is None or refined["energy"] < best_candidate["energy"]:
                best_candidate = refined

        best_state = np.array(best_candidate["state"], copy=True)
        history.append(
            {
                "shape": [int(value) for value in shape],
                "energy": float(best_candidate["energy"]),
                "best_start_source": str(best_candidate["source"]),
                "max_local_change": float(best_candidate["last_change"]),
            }
        )

        if previous is not None:
            if abs(float(best_candidate["energy"]) - float(previous["energy"])) <= float(energy_tolerance):
                stable_count += 1
            else:
                stable_count = 0
        previous = {
            "shape": tuple(int(value) for value in shape),
            "energy": float(best_candidate["energy"]),
            "last_change": float(best_candidate["last_change"]),
            "diagnostics": best_candidate["diagnostics"],
            "source": str(best_candidate["source"]),
        }
        if progress_callback is not None:
            progress_callback(
                {
                    "status": "running",
                    "iteration": int(len(history)),
                    "stable_count": int(stable_count),
                    "repeats_required": int(repeats_required),
                    "result": _snapshot_result(
                        model,
                        best_state,
                        best_candidate["diagnostics"],
                        history,
                        energy=best_candidate["energy"],
                        shape=shape,
                        starts=starts,
                        seed=seed,
                        structural_dimension=structural_dimension,
                        bounded_search=bounded_search,
                        max_linear_size=max_linear_size,
                        repeats_required=repeats_required,
                        energy_tolerance=energy_tolerance,
                        stopped_reason="running",
                    ),
                }
            )
        if stable_count >= repeats_required:
            break

    final_diagnostics = previous["diagnostics"]
    converged = bool(stable_count >= repeats_required)
    final_result = _snapshot_result(
        model,
        best_state,
        final_diagnostics,
        history,
        energy=previous["energy"],
        shape=previous["shape"],
        starts=starts,
        seed=seed,
        structural_dimension=structural_dimension,
        bounded_search=bounded_search,
        max_linear_size=max_linear_size,
        repeats_required=repeats_required,
        energy_tolerance=energy_tolerance,
        stopped_reason="converged" if converged else "max_linear_size_reached",
    )
    if progress_callback is not None:
        progress_callback(
            {
                "status": "completed",
                "iteration": int(len(history)),
                "stable_count": int(stable_count),
                "repeats_required": int(repeats_required),
                "result": final_result,
            }
        )
    return final_result
