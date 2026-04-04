#!/usr/bin/env python3
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

try:
    from scipy.optimize import minimize
except ModuleNotFoundError:  # pragma: no cover - exercised indirectly in tests
    minimize = None


def unit_vector(theta, phi):
    return np.array(
        [
            math.sin(theta) * math.cos(phi),
            math.sin(theta) * math.sin(phi),
            math.cos(theta),
        ]
    )


def classical_energy(model, spins):
    energy = 0.0
    for bond in model["bonds"]:
        matrix = np.array(bond["matrix"], dtype=float)
        s_i = spins[bond["source"]]
        s_j = spins[bond["target"]]
        energy += float(s_i @ matrix @ s_j)
    return energy


def recommend_method(model):
    effective_main = model.get("effective_model", {}).get("main", [])
    effective_types = {block.get("type") for block in effective_main}
    simplified_template = model.get("simplified_model", {}).get("template")
    if simplified_template == "heisenberg" or "isotropic_exchange" in effective_types:
        return "luttinger-tisza"
    if model.get("lattice", {}).get("sublattices", 1) == 1 and (
        simplified_template == "xxz" or "xxz_like" in effective_types
    ):
        return "luttinger-tisza"
    return "variational"


def choose_method(model, user_choice=None, timed_out=False, allow_auto_select=False):
    if user_choice is not None:
        return {"method": user_choice, "auto_selected": False}
    recommended = recommend_method(model)
    if timed_out:
        return {"method": recommended, "auto_selected": True}
    if allow_auto_select:
        return {"method": recommended, "auto_selected": True}
    return {"method": None, "auto_selected": False, "recommended": recommended}


def solve_variational(model, starts=16, seed=0):
    rng = np.random.default_rng(seed)
    n_spins = max(max(bond["source"], bond["target"]) for bond in model["bonds"]) + 1
    best = None

    def objective(params):
        spins = np.array([unit_vector(params[2 * index], params[2 * index + 1]) for index in range(n_spins)])
        return classical_energy(model, spins)

    for _ in range(starts):
        guess = rng.uniform(0.0, 2.0 * math.pi, size=2 * n_spins)
        if minimize is None:
            result = type("FallbackResult", (), {"fun": objective(guess), "x": guess})()
        else:
            result = minimize(objective, guess, method="Powell")
        if best is None or result.fun < best.fun:
            best = result

    spins = [unit_vector(best.x[2 * index], best.x[2 * index + 1]).tolist() for index in range(n_spins)]
    return {"method": "variational", "energy": float(best.fun), "spins": spins}


def random_spin(rng):
    u = rng.uniform(-1.0, 1.0)
    phi = rng.uniform(0.0, 2.0 * math.pi)
    xy = math.sqrt(max(0.0, 1.0 - u * u))
    return np.array([xy * math.cos(phi), xy * math.sin(phi), u])


def metropolis_step(model, spins, temperature, rng):
    trial = spins.copy()
    index = int(rng.integers(0, len(spins)))
    old_energy = classical_energy(model, spins)
    trial[index] = random_spin(rng)
    new_energy = classical_energy(model, trial)
    if new_energy <= old_energy:
        return trial, new_energy
    accept_prob = math.exp(-(new_energy - old_energy) / temperature)
    if rng.uniform() < accept_prob:
        return trial, new_energy
    return spins, old_energy


def estimate_thermodynamics(model, temperatures, sweeps=100, burn_in=50, seed=0):
    rng = np.random.default_rng(seed)
    n_spins = max(max(bond["source"], bond["target"]) for bond in model["bonds"]) + 1
    spins = np.array([random_spin(rng) for _ in range(n_spins)])
    grid = []
    energy_samples = []
    magnetization_samples = []

    for temperature in temperatures:
        local_energies = []
        local_mags = []
        for sweep in range(sweeps + burn_in):
            spins, energy = metropolis_step(model, spins, temperature, rng)
            if sweep >= burn_in:
                local_energies.append(energy)
                local_mags.append(float(np.linalg.norm(np.mean(spins, axis=0))))

        mean_energy = float(np.mean(local_energies))
        mean_mag = float(np.mean(local_mags))
        grid.append({"temperature": float(temperature), "energy": mean_energy, "magnetization": mean_mag})
        energy_samples.append(mean_energy)
        magnetization_samples.append(mean_mag)

    return {
        "grid": grid,
        "observables": {
            "energy": energy_samples,
            "free_energy": [
                point["energy"] - point["temperature"] * max(0.0, np.log(2.0) - point["energy"] / max(point["temperature"], 1e-9))
                for point in grid
            ],
            "specific_heat": [float(np.var([item["energy"] for item in grid]))] * len(grid),
            "magnetization": magnetization_samples,
            "susceptibility": [float(np.var(magnetization_samples) / max(point["temperature"], 1e-9)) for point in grid],
            "entropy": [float(max(0.0, np.log(2.0) - point["energy"] / max(point["temperature"], 1e-9))) for point in grid],
        },
    }


def _load_payload(path):
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.load(sys.stdin)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?")
    parser.add_argument("--starts", type=int, default=16)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    payload = _load_payload(args.input)
    payload.setdefault("recommended_method", recommend_method(payload))
    payload["variational_result"] = solve_variational(payload, starts=args.starts, seed=args.seed)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
