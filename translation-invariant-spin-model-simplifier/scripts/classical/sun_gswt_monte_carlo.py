#!/usr/bin/env python3
import math

import numpy as np

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from classical.sun_gswt_classical_solver import (
        _normalized_ray,
        _serialize_vector,
        _state_array_from_model,
        evaluate_sun_gswt_classical_energy,
    )
else:
    from .sun_gswt_classical_solver import (
        _normalized_ray,
        _serialize_vector,
        _state_array_from_model,
        evaluate_sun_gswt_classical_energy,
    )


def _propose_local_ray(current_ray, rng, proposal_scale):
    trial = current_ray + proposal_scale * (rng.normal(size=len(current_ray)) + 1.0j * rng.normal(size=len(current_ray)))
    return _normalized_ray(trial)


def _serialize_state_array(state_array):
    shape = list(state_array.shape[:3])
    rays = []
    for index in np.ndindex(tuple(shape)):
        rays.append({"cell": [int(value) for value in index], "vector": _serialize_vector(state_array[index])})
    return {"shape": shape, "local_rays": rays}


def run_sun_gswt_monte_carlo(
    model,
    *,
    temperatures,
    supercell_shape=(1, 1, 1),
    sweeps=100,
    burn_in=50,
    seed=0,
    proposal_scale=0.2,
):
    if model.get("classical_manifold") != "CP^(N-1)":
        raise ValueError("sun-gswt Monte Carlo expects a CP^(N-1) classical payload")

    rng = np.random.default_rng(seed)
    state_array = _state_array_from_model(model, supercell_shape, seed)
    total_proposals = 0
    total_accepts = 0
    grid = []

    for temperature in temperatures:
        temperature = float(temperature)
        if temperature <= 0.0:
            raise ValueError("Monte Carlo temperatures must be positive")

        local_energies = []
        current_energy = evaluate_sun_gswt_classical_energy(model, state_array)
        for sweep in range(int(sweeps) + int(burn_in)):
            for index in np.ndindex(state_array.shape[:3]):
                total_proposals += 1
                old_ray = np.array(state_array[index], copy=True)
                trial_ray = _propose_local_ray(old_ray, rng, proposal_scale)
                state_array[index] = trial_ray
                trial_energy = evaluate_sun_gswt_classical_energy(model, state_array)
                delta = float(trial_energy - current_energy)
                accept = delta <= 0.0 or rng.uniform() < math.exp(-delta / temperature)
                if accept:
                    current_energy = trial_energy
                    total_accepts += 1
                else:
                    state_array[index] = old_ray

            if sweep >= int(burn_in):
                local_energies.append(float(current_energy))

        grid.append(
            {
                "temperature": float(temperature),
                "energy": float(np.mean(local_energies)) if local_energies else float(current_energy),
                "samples": len(local_energies),
            }
        )

    return {
        "method": "sun-gswt-monte-carlo",
        "manifold": "CP^(N-1)",
        "grid": grid,
        "sampling": {
            "acceptance_rate": float(total_accepts) / float(total_proposals) if total_proposals else 0.0,
            "proposal_scale": float(proposal_scale),
            "sweeps": int(sweeps),
            "burn_in": int(burn_in),
            "seed": int(seed),
        },
        "final_state": _serialize_state_array(state_array),
    }
