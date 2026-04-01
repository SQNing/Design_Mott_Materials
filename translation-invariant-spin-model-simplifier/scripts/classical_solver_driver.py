#!/usr/bin/env python3
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from lattice_geometry import build_isotropic_heisenberg_bonds_from_parameters


def unit_vector(theta, phi):
    return np.array(
        [
            math.sin(theta) * math.cos(phi),
            math.sin(theta) * math.sin(phi),
            math.cos(theta),
        ]
    )


def build_classical_state(spins, method, converged=True):
    site_frames = []
    for index, spin in enumerate(spins):
        vector = np.array(spin, dtype=float)
        site_frames.append(
            {
                "site": index,
                "spin_length": float(np.linalg.norm(vector)),
                "direction": vector.tolist(),
            }
        )
    return {
        "site_frames": site_frames,
        "ordering": {
            "kind": "commensurate",
            "q_vector": [0.0, 0.0, 0.0],
        },
        "provenance": {
            "method": method,
            "converged": bool(converged),
        },
    }


def _site_count_from_model(model):
    bonds = resolve_model_bonds(model)
    if bonds:
        return max(max(bond["source"], bond["target"]) for bond in bonds) + 1
    return int(model.get("lattice", {}).get("sublattices", 1))


def classical_energy(model, spins):
    bonds = resolve_model_bonds(model)
    energy = 0.0
    for bond in bonds:
        matrix = np.array(bond["matrix"], dtype=float)
        s_i = spins[bond["source"]]
        s_j = spins[bond["target"]]
        energy += float(s_i @ matrix @ s_j)
    return energy


def resolve_model_bonds(model):
    explicit_bonds = model.get("bonds", [])
    if explicit_bonds:
        return explicit_bonds
    simplified_model = model.get("simplified_model", {})
    simplified_bonds = simplified_model.get("bonds", [])
    if simplified_bonds:
        return simplified_bonds
    if simplified_model.get("template") == "heisenberg":
        exchange_mapping = model.get("exchange_mapping", {})
        bonds, _shell_map = build_isotropic_heisenberg_bonds_from_parameters(
            model.get("lattice", {}),
            model.get("parameters", {}),
            shell_map_override=exchange_mapping.get("shell_map", {}),
        )
        if bonds:
            return bonds
    return []


def _is_isotropic_exchange(matrix, tolerance=1e-9):
    diagonal = [float(matrix[index][index]) for index in range(3)]
    average = sum(diagonal) / 3.0
    for row in range(3):
        for col in range(3):
            value = float(matrix[row][col])
            if row == col:
                if abs(value - average) > tolerance:
                    return False, average
            elif abs(value) > tolerance:
                return False, average
    return True, average


def _active_spatial_dimension(model):
    lattice = model.get("lattice", {})
    positions = lattice.get("positions") or []
    active = [False, False, False]
    if positions:
        for axis in range(3):
            values = [float(position[axis]) if axis < len(position) else 0.0 for position in positions]
            if max(values) - min(values) > 1e-9:
                active[axis] = True
    for bond in resolve_model_bonds(model):
        vector = bond.get("vector", [])
        for axis in range(min(3, len(vector))):
            if abs(float(vector[axis])) > 1e-9:
                active[axis] = True
    kind = str(lattice.get("kind", "")).lower()
    if any(token in kind for token in {"square", "rect", "triang", "honeycomb", "kagome", "2d"}):
        return max(2, sum(1 for axis in active if axis))
    if any(token in kind for token in {"cubic", "orthorhombic", "tetragonal", "3d"}):
        return max(3, sum(1 for axis in active if axis))
    explicit = lattice.get("dimension")
    if isinstance(explicit, int):
        return max(explicit, sum(1 for axis in active if axis), 1)
    return max(sum(1 for axis in active if axis), 1)


def _commensurability_kind(q_vector, tolerance=1e-6, max_denominator=6):
    for value in q_vector:
        if abs(value) <= tolerance:
            continue
        matched = False
        for denominator in range(1, max_denominator + 1):
            rounded = round(value * denominator) / float(denominator)
            if abs(rounded - value) <= tolerance:
                matched = True
                break
        if not matched:
            return "incommensurate"
    return "commensurate"


def _magnetic_periods_from_q(q_vector, dimension, max_denominator=24, tolerance=1e-6):
    periods = [1, 1, 1]
    for axis in range(min(3, int(dimension))):
        value = float(q_vector[axis]) if axis < len(q_vector) else 0.0
        if abs(value) <= tolerance:
            periods[axis] = 1
            continue
        matched = None
        for denominator in range(1, max_denominator + 1):
            rounded = round(value * denominator) / float(denominator)
            if abs(rounded - value) <= tolerance:
                matched = denominator
                break
        periods[axis] = matched or 1
    return periods


def _enumerate_supercell_periods(dimension, max_magnetic_period):
    max_magnetic_period = max(1, int(max_magnetic_period))
    dimension = max(1, min(3, int(dimension)))
    periods = []
    seen = set()
    for bound in range(1, max_magnetic_period + 1):
        ranges = [range(1, bound + 1) if axis < dimension else range(1, 2) for axis in range(3)]
        for p0 in ranges[0]:
            for p1 in ranges[1]:
                for p2 in ranges[2]:
                    candidate = (p0, p1, p2)
                    if max(candidate[:dimension]) != bound:
                        continue
                    if candidate in seen:
                        continue
                    seen.add(candidate)
                    periods.append(candidate)
    periods.sort(key=lambda item: (np.prod(item[:dimension]), max(item[:dimension]), item))
    return periods


def _site_index(cell, basis_index, periods, basis_size):
    px, py, pz = (int(value) for value in periods)
    cx, cy, cz = (int(value) for value in cell)
    return (((cz * py) + cy) * px + cx) * basis_size + int(basis_index)


def expand_model_to_supercell(model, magnetic_periods):
    bonds = resolve_model_bonds(model)
    if not bonds:
        raise ValueError("variational solver requires at least one bond")

    periods = tuple(int(value) for value in magnetic_periods)
    basis_size = _site_count_from_model(model)
    expanded_bonds = []

    for cx in range(periods[0]):
        for cy in range(periods[1]):
            for cz in range(periods[2]):
                cell = (cx, cy, cz)
                for bond in bonds:
                    vector = [int(round(component)) for component in bond.get("vector", [0, 0, 0])]
                    while len(vector) < 3:
                        vector.append(0)
                    target_cell = tuple((cell[axis] + vector[axis]) % periods[axis] for axis in range(3))
                    expanded_bonds.append(
                        {
                            "source": _site_index(cell, bond["source"], periods, basis_size),
                            "target": _site_index(target_cell, bond["target"], periods, basis_size),
                            "matrix": bond["matrix"],
                            "vector": vector,
                        }
                    )

    expanded_model = dict(model)
    expanded_lattice = dict(model.get("lattice", {}))
    expanded_lattice["magnetic_periods"] = list(periods)
    expanded_lattice["sublattices"] = basis_size * int(np.prod(periods))
    expanded_model["lattice"] = expanded_lattice
    expanded_model["bonds"] = expanded_bonds
    expanded_model["magnetic_periods"] = list(periods)
    expanded_model["magnetic_basis_size"] = basis_size
    return expanded_model


def solve_luttinger_tisza(model, grid_size=33):
    bonds = resolve_model_bonds(model)
    if not bonds:
        raise ValueError("luttinger-tisza requires at least one bond")

    dimension = _active_spatial_dimension(model)
    values = np.linspace(0.0, 0.5, int(grid_size))
    bond_terms = []
    for bond in bonds:
        isotropic, coupling = _is_isotropic_exchange(bond["matrix"])
        if not isotropic:
            raise ValueError("luttinger-tisza currently supports isotropic bilinear exchange only")
        vector = [float(component) for component in bond.get("vector", [0.0, 0.0, 0.0])]
        while len(vector) < 3:
            vector.append(0.0)
        bond_terms.append((coupling, vector))

    best_energy = None
    best_q = [0.0, 0.0, 0.0]
    for q_components in np.ndindex(*(len(values),) * dimension):
        q_vector = [0.0, 0.0, 0.0]
        for axis in range(dimension):
            q_vector[axis] = float(values[q_components[axis]])
        energy = 0.0
        for coupling, vector in bond_terms:
            phase = 2.0 * math.pi * sum(q_vector[axis] * vector[axis] for axis in range(3))
            energy += coupling * math.cos(phase)
        if best_energy is None or energy < best_energy - 1e-12:
            best_energy = energy
            best_q = q_vector

    magnetic_periods = _magnetic_periods_from_q(best_q, dimension)
    magnetic_cell_size = int(np.prod(magnetic_periods[:dimension])) if dimension > 0 else 1
    classical_state = build_classical_state([[0.0, 0.0, 1.0]], method="luttinger-tisza", converged=True)
    classical_state["ordering"] = {"kind": _commensurability_kind(best_q), "q_vector": best_q}
    classical_state["provenance"]["grid_size"] = int(grid_size)
    return {
        "method": "luttinger-tisza",
        "energy": float(best_energy),
        "energy_per_unit_cell": float(best_energy),
        "magnetic_supercell_energy": float(best_energy * magnetic_cell_size),
        "magnetic_periods": magnetic_periods,
        "q_vector": best_q,
        "spins": [[0.0, 0.0, 1.0]],
        "classical_state": classical_state,
    }


def recommend_method(model):
    if model.get("lattice", {}).get("sublattices", 1) == 1 and model.get("simplified_model", {}).get(
        "template"
    ) in {"heisenberg", "xxz"}:
        return "luttinger-tisza"
    return "variational"


def choose_method(model, user_choice=None, timed_out=False):
    if user_choice is not None:
        return {"method": user_choice, "auto_selected": False}
    recommended = recommend_method(model)
    if timed_out:
        return {"method": recommended, "auto_selected": True}
    return {"method": None, "auto_selected": False, "recommended": recommended}


def solve_variational(model, starts=16, seed=0):
    bonds = resolve_model_bonds(model)
    if not bonds:
        raise ValueError("variational solver requires at least one bond")
    rng = np.random.default_rng(seed)
    n_spins = _site_count_from_model(model)
    best = None

    def objective(params):
        spins = np.array([unit_vector(params[2 * index], params[2 * index + 1]) for index in range(n_spins)])
        return classical_energy(model, spins)

    for _ in range(starts):
        guess = rng.uniform(0.0, 2.0 * math.pi, size=2 * n_spins)
        result = minimize(objective, guess, method="Powell")
        if best is None or result.fun < best.fun:
            best = result

    spins = [unit_vector(best.x[2 * index], best.x[2 * index + 1]).tolist() for index in range(n_spins)]
    return {
        "method": "variational",
        "energy": float(best.fun),
        "spins": spins,
        "classical_state": build_classical_state(spins, method="variational", converged=bool(best.success)),
    }


def solve_variational_until_converged(
    model,
    starts=16,
    seed=0,
    max_magnetic_period=6,
    energy_tolerance=1e-4,
):
    dimension = _active_spatial_dimension(model)
    periods_to_scan = _enumerate_supercell_periods(dimension, max_magnetic_period)
    convergence_history = []
    best_result = None
    stable_steps = 0

    for scan_index, periods in enumerate(periods_to_scan):
        expanded_model = expand_model_to_supercell(model, periods)
        trial = solve_variational(expanded_model, starts=starts, seed=seed + scan_index)
        n_spins = len(trial["spins"])
        energy_per_spin = float(trial["energy"]) / float(n_spins)
        entry = {
            "magnetic_periods": list(periods),
            "energy": float(trial["energy"]),
            "energy_per_spin": energy_per_spin,
            "spin_count": n_spins,
        }
        convergence_history.append(entry)

        if best_result is None or energy_per_spin < best_result["energy_per_spin"] - 1e-12:
            best_result = {
                **trial,
                "energy_per_spin": energy_per_spin,
                "magnetic_periods": list(periods),
            }

        if len(convergence_history) >= 2:
            delta = abs(convergence_history[-1]["energy_per_spin"] - convergence_history[-2]["energy_per_spin"])
            stable_steps = stable_steps + 1 if delta < energy_tolerance else 0
        if stable_steps >= 2:
            break

    if best_result is None:
        raise ValueError("variational supercell scan produced no trial states")

    best_result["convergence_history"] = convergence_history
    best_result["scanned_magnetic_periods"] = list(convergence_history[-1]["magnetic_periods"])
    best_result["converged_supercell_scan"] = stable_steps >= 2
    best_result["energy_tolerance"] = float(energy_tolerance)
    best_result["max_magnetic_period"] = int(max_magnetic_period)
    best_result["classical_state"]["ordering"]["kind"] = "commensurate"
    best_result["classical_state"]["ordering"]["magnetic_periods"] = list(best_result["magnetic_periods"])
    best_result["classical_state"]["provenance"]["supercell_scan"] = True
    best_result["classical_state"]["provenance"]["converged_supercell_scan"] = bool(best_result["converged_supercell_scan"])
    return best_result


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
    bonds = resolve_model_bonds(model)
    if not bonds:
        raise ValueError("thermodynamics estimation requires at least one bond")
    rng = np.random.default_rng(seed)
    n_spins = max(max(bond["source"], bond["target"]) for bond in bonds) + 1
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
    parser.add_argument("--method", choices=["auto", "variational", "luttinger-tisza"], default="auto")
    parser.add_argument("--lt-grid-size", type=int, default=33)
    parser.add_argument("--max-magnetic-period", type=int, default=6)
    parser.add_argument("--energy-tolerance", type=float, default=1e-4)
    args = parser.parse_args()

    payload = _load_payload(args.input)
    payload.setdefault("recommended_method", recommend_method(payload))
    chosen_method = args.method
    if chosen_method == "auto":
        chosen_method = payload["recommended_method"]
    payload["chosen_method"] = chosen_method
    if chosen_method == "luttinger-tisza":
        payload["luttinger_tisza_result"] = solve_luttinger_tisza(payload, grid_size=args.lt_grid_size)
    else:
        payload["variational_result"] = solve_variational_until_converged(
            payload,
            starts=args.starts,
            seed=args.seed,
            max_magnetic_period=args.max_magnetic_period,
            energy_tolerance=args.energy_tolerance,
        )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
