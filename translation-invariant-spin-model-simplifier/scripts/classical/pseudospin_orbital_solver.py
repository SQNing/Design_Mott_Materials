#!/usr/bin/env python3
from fractions import Fraction
import math

import numpy as np

try:
    from scipy.optimize import minimize
except ModuleNotFoundError:  # pragma: no cover - exercised indirectly in tests
    minimize = None

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from classical.pseudospin_orbital_relaxed_lt import (
        build_reduced_lattice_view,
        find_pseudospin_orbital_relaxed_lt_seed,
    )
else:
    from .pseudospin_orbital_relaxed_lt import (
        build_reduced_lattice_view,
        find_pseudospin_orbital_relaxed_lt_seed,
    )


_AXIS_TO_INDEX = {"x": 0, "y": 1, "z": 2}


def _complex_from_serialized(value):
    if isinstance(value, dict):
        return complex(float(value.get("real", 0.0)), float(value.get("imag", 0.0)))
    return complex(value)


def _unit_vector(theta, phi):
    return np.array(
        [
            math.sin(theta) * math.cos(phi),
            math.sin(theta) * math.sin(phi),
            math.cos(theta),
        ],
        dtype=float,
    )


def _state_from_params(params):
    return {
        "left": {
            "spin": _unit_vector(params[0], params[1]).tolist(),
            "orbital": _unit_vector(params[2], params[3]).tolist(),
        },
        "right": {
            "spin": _unit_vector(params[4], params[5]).tolist(),
            "orbital": _unit_vector(params[6], params[7]).tolist(),
        },
    }


def _normalized_vector(values):
    vector = np.array(values, dtype=float)
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        return np.array([0.0, 0.0, 1.0], dtype=float)
    return vector / norm


def _normalize_state(state):
    normalized = {}
    for site_role in ("left", "right"):
        site_state = state.get(site_role, {})
        normalized[site_role] = {
            "spin": _normalized_vector(site_state.get("spin", [0.0, 0.0, 1.0])).tolist(),
            "orbital": _normalized_vector(site_state.get("orbital", [0.0, 0.0, 1.0])).tolist(),
        }
    return normalized


def _factor_value(state, factor):
    site_role = factor["site_role"]
    field = factor["field"]
    axis = str(factor["axis"]).lower()
    if axis not in _AXIS_TO_INDEX:
        raise ValueError(f"unsupported axis: {factor['axis']}")
    vector = state[site_role][field]
    return float(vector[_AXIS_TO_INDEX[axis]])


def evaluate_pseudospin_orbital_classical_energy(model, state, imag_tolerance=1e-10):
    if int(model.get("orbital_count", 0)) != 2:
        raise ValueError("pseudospin-orbital classical solver only supports orbital_count = 2")

    normalized_state = _normalize_state(state)
    energy = 0.0
    for term in model.get("terms", []):
        coefficient = _complex_from_serialized(term.get("coefficient", 0.0))
        if abs(coefficient.imag) > imag_tolerance:
            raise ValueError("classical energy expects real-valued projected coefficients")
        contribution = float(coefficient.real)
        for factor in term.get("factors", []):
            contribution *= _factor_value(normalized_state, factor)
        energy += contribution
    return float(energy)


def _legacy_two_site_variational(model, starts, seed):
    rng = np.random.default_rng(seed)
    best_energy = None
    best_params = None

    def objective(params):
        return evaluate_pseudospin_orbital_classical_energy(model, _state_from_params(params))

    for _ in range(starts):
        guess = np.array(
            [
                rng.uniform(0.0, math.pi),
                rng.uniform(0.0, 2.0 * math.pi),
                rng.uniform(0.0, math.pi),
                rng.uniform(0.0, 2.0 * math.pi),
                rng.uniform(0.0, math.pi),
                rng.uniform(0.0, 2.0 * math.pi),
                rng.uniform(0.0, math.pi),
                rng.uniform(0.0, 2.0 * math.pi),
            ],
            dtype=float,
        )
        if minimize is None:
            candidate_energy = float(objective(guess))
            candidate_params = guess
        else:
            result = minimize(objective, guess, method="Powell")
            candidate_energy = float(result.fun)
            candidate_params = result.x

        if best_energy is None or candidate_energy < best_energy:
            best_energy = candidate_energy
            best_params = np.array(candidate_params, dtype=float)

    best_state = _state_from_params(best_params)
    return {
        "method": "variational-pseudospin-orbital",
        "energy": float(best_energy),
        "state": _normalize_state(best_state),
        "starts": int(starts),
        "seed": int(seed),
    }


def _can_use_supercell_solver(model):
    return bool(model.get("lattice_vectors")) and bool(model.get("terms")) and any("R" in term for term in model.get("terms", []))


def _supercell_shape(rank, linear_size):
    linear_size = int(linear_size)
    if rank <= 1:
        return (linear_size, 1, 1)
    if rank == 2:
        return (linear_size, linear_size, 1)
    return (linear_size, linear_size, linear_size)


def _supercell_schedule(rank, max_linear_size):
    return [_supercell_shape(rank, linear_size) for linear_size in range(1, int(max_linear_size) + 1)]


def _random_unit_vector(rng):
    u = rng.uniform(-1.0, 1.0)
    phi = rng.uniform(0.0, 2.0 * math.pi)
    xy = math.sqrt(max(0.0, 1.0 - u * u))
    return np.array([xy * math.cos(phi), xy * math.sin(phi), u], dtype=float)


def _random_supercell_state(shape, rng):
    state = {
        "spin": np.zeros(tuple(shape) + (3,), dtype=float),
        "orbital": np.zeros(tuple(shape) + (3,), dtype=float),
    }
    for index in np.ndindex(tuple(shape)):
        state["spin"][index] = _random_unit_vector(rng)
        state["orbital"][index] = _random_unit_vector(rng)
    return state


def _tiled_supercell_state(previous_state, shape, rng, noise_scale=0.05):
    state = {
        "spin": np.zeros(tuple(shape) + (3,), dtype=float),
        "orbital": np.zeros(tuple(shape) + (3,), dtype=float),
    }
    previous_shape = previous_state["spin"].shape[:3]
    for index in np.ndindex(tuple(shape)):
        source = tuple(index[axis] % previous_shape[axis] for axis in range(3))
        state["spin"][index] = _normalized_vector(previous_state["spin"][source] + noise_scale * _random_unit_vector(rng))
        state["orbital"][index] = _normalized_vector(
            previous_state["orbital"][source] + noise_scale * _random_unit_vector(rng)
        )
    return state


def _phase_from_q(q_seed, index):
    return 2.0 * math.pi * sum(float(q_seed[axis]) * float(index[axis]) for axis in range(3))


def _q_seed_state(shape, q_seed):
    state = {
        "spin": np.zeros(tuple(shape) + (3,), dtype=float),
        "orbital": np.zeros(tuple(shape) + (3,), dtype=float),
    }
    for index in np.ndindex(tuple(shape)):
        phase = _phase_from_q(q_seed, index)
        vector = np.array([math.cos(phase), math.sin(phase), 0.0], dtype=float)
        state["spin"][index] = vector
        state["orbital"][index] = vector
    return state


def _mod_index(index, shape):
    return tuple(int(index[axis]) % int(shape[axis]) for axis in range(3))


def _factor_value_supercell(state, factor, left_index, right_index):
    axis = _AXIS_TO_INDEX[str(factor["axis"]).lower()]
    target_index = left_index if factor["site_role"] == "left" else right_index
    return float(state[factor["field"]][target_index][axis])


def _supercell_energy_per_cell(model, state, reduced_R_by_term, shape, imag_tolerance=1e-10):
    energy = 0.0
    for left_index in np.ndindex(tuple(shape)):
        for term, reduced_R in zip(model.get("terms", []), reduced_R_by_term):
            coefficient = _complex_from_serialized(term["coefficient"])
            if abs(coefficient.imag) > imag_tolerance:
                raise ValueError("supercell solver expects real-valued projected coefficients")
            right_index = _mod_index(tuple(left_index[axis] + reduced_R[axis] for axis in range(3)), shape)
            contribution = float(coefficient.real)
            for factor in term.get("factors", []):
                contribution *= _factor_value_supercell(state, factor, left_index, right_index)
            energy += contribution
    return float(energy) / float(np.prod(shape))


def _local_linear_field(term, state, left_index, right_index, target_role, field, imag_tolerance=1e-10):
    coefficient = _complex_from_serialized(term["coefficient"])
    if abs(coefficient.imag) > imag_tolerance:
        raise ValueError("supercell solver expects real-valued projected coefficients")

    target_factor = None
    prefactor = float(coefficient.real)
    for factor in term.get("factors", []):
        if factor["site_role"] == target_role and factor["field"] == field and target_factor is None:
            target_factor = factor
            continue
        prefactor *= _factor_value_supercell(state, factor, left_index, right_index)

    if target_factor is None:
        return np.zeros(3, dtype=float)

    vector = np.zeros(3, dtype=float)
    vector[_AXIS_TO_INDEX[str(target_factor["axis"]).lower()]] = prefactor
    return vector


def _effective_field(model, state, shape, reduced_R_by_term, cell_index, field):
    total = np.zeros(3, dtype=float)
    for term, reduced_R in zip(model.get("terms", []), reduced_R_by_term):
        right_index = _mod_index(tuple(cell_index[axis] + reduced_R[axis] for axis in range(3)), shape)
        total += _local_linear_field(term, state, cell_index, right_index, "left", field)

        left_index = _mod_index(tuple(cell_index[axis] - reduced_R[axis] for axis in range(3)), shape)
        total += _local_linear_field(term, state, left_index, cell_index, "right", field)
    return total


def _alternating_supercell_sweep(model, state, shape, reduced_R_by_term):
    max_change = 0.0
    for cell_index in np.ndindex(tuple(shape)):
        spin_field = _effective_field(model, state, shape, reduced_R_by_term, cell_index, "spin")
        new_spin = _normalized_vector(-spin_field if np.linalg.norm(spin_field) > 1e-12 else state["spin"][cell_index])
        max_change = max(max_change, float(np.linalg.norm(new_spin - state["spin"][cell_index])))
        state["spin"][cell_index] = new_spin

        orbital_field = _effective_field(model, state, shape, reduced_R_by_term, cell_index, "orbital")
        new_orbital = _normalized_vector(
            -orbital_field if np.linalg.norm(orbital_field) > 1e-12 else state["orbital"][cell_index]
        )
        max_change = max(max_change, float(np.linalg.norm(new_orbital - state["orbital"][cell_index])))
        state["orbital"][cell_index] = new_orbital
    return state, max_change


def _refine_supercell_state(model, initial_state, shape, reduced_R_by_term, max_sweeps, sweep_tolerance):
    state = {
        "spin": np.array(initial_state["spin"], dtype=float, copy=True),
        "orbital": np.array(initial_state["orbital"], dtype=float, copy=True),
    }
    last_change = None
    for sweep in range(int(max_sweeps)):
        state, change = _alternating_supercell_sweep(model, state, shape, reduced_R_by_term)
        last_change = float(change)
        if change <= sweep_tolerance:
            break
    return state, float(last_change if last_change is not None else 0.0)


def _structure_factor_peak(state, shape, rank):
    cell_count = float(np.prod(shape))
    best = None
    for q_index in np.ndindex(tuple(shape)):
        q = [0.0, 0.0, 0.0]
        for axis in range(rank):
            q[axis] = float(q_index[axis]) / float(shape[axis])
        spin_amp = np.zeros(3, dtype=complex)
        orbital_amp = np.zeros(3, dtype=complex)
        for cell_index in np.ndindex(tuple(shape)):
            phase = complex(np.exp(-2.0j * math.pi * sum(q[axis] * cell_index[axis] for axis in range(rank))))
            spin_amp += state["spin"][cell_index] * phase
            orbital_amp += state["orbital"][cell_index] * phase
        spin_weight = float(np.sum(np.abs(spin_amp) ** 2) / (cell_count * cell_count))
        orbital_weight = float(np.sum(np.abs(orbital_amp) ** 2) / (cell_count * cell_count))
        if best is None or max(spin_weight, orbital_weight) > best["weight"]:
            if spin_weight >= orbital_weight:
                best = {"peak_q": [float(value) for value in q], "weight": spin_weight, "channel": "spin"}
            else:
                best = {"peak_q": [float(value) for value in q], "weight": orbital_weight, "channel": "orbital"}
    return best


def _wrapped_fractional_difference(left, right):
    raw = abs(float(left) - float(right))
    return min(raw, abs(1.0 - raw))


def _peak_is_stable(previous_peak, current_peak, previous_shape, current_shape, rank):
    for axis in range(rank):
        tolerance = max(1.0 / float(previous_shape[axis]), 1.0 / float(current_shape[axis]))
        if _wrapped_fractional_difference(previous_peak["peak_q"][axis], current_peak["peak_q"][axis]) > tolerance + 1e-12:
            return False
    return True


def _commensurate_target_shape(q_seed, rank, max_denominator=12, tolerance=1e-8):
    targets = [1, 1, 1]
    for axis in range(rank):
        fraction = Fraction(float(q_seed[axis])).limit_denominator(max_denominator)
        if abs(float(fraction) - float(q_seed[axis])) <= tolerance:
            targets[axis] = int(fraction.denominator)
        else:
            targets[axis] = None
    return targets


def _shape_matches_commensurate_target(shape, target_shape, rank):
    for axis in range(rank):
        target = target_shape[axis]
        if target is None:
            return False
        if int(shape[axis]) % int(target) != 0:
            return False
    return True


def _serialize_supercell_state(state):
    cells = []
    shape = state["spin"].shape[:3]
    for index in np.ndindex(shape):
        cells.append(
            {
                "cell": [int(value) for value in index],
                "spin": [float(value) for value in state["spin"][index].tolist()],
                "orbital": [float(value) for value in state["orbital"][index].tolist()],
            }
        )
    return cells


def _supercell_variational(
    model,
    *,
    starts,
    seed,
    max_linear_size,
    convergence_repeats,
    energy_tolerance,
    max_sweeps,
    sweep_tolerance,
):
    if len(model.get("positions", [])) != 1:
        raise ValueError("supercell pseudospin-orbital solver currently supports one site per unit cell")

    lattice_view = build_reduced_lattice_view(model)
    rank = lattice_view["rank"]
    reduced_R_by_term = lattice_view["reduced_R_by_term"]
    rng = np.random.default_rng(seed)

    mesh_shape = _supercell_shape(rank, max(9, int(max_linear_size) * 2 + 1))
    relaxed_lt = find_pseudospin_orbital_relaxed_lt_seed(model, mesh_shape=mesh_shape)

    best_state = None
    previous_result = None
    stable_count = 0
    history = []

    for shape in _supercell_schedule(rank, max_linear_size):
        candidate_results = []
        initial_states = []
        if best_state is not None:
            initial_states.append(_tiled_supercell_state(best_state, shape, rng))
        initial_states.append(_q_seed_state(shape, relaxed_lt["q_seed"]))
        while len(initial_states) < max(1, int(starts)):
            initial_states.append(_random_supercell_state(shape, rng))

        for initial_state in initial_states[: max(1, int(starts))]:
            refined_state, last_change = _refine_supercell_state(
                model,
                initial_state,
                shape,
                reduced_R_by_term,
                max_sweeps=max_sweeps,
                sweep_tolerance=sweep_tolerance,
            )
            candidate_results.append(
                {
                    "state": refined_state,
                    "energy": _supercell_energy_per_cell(model, refined_state, reduced_R_by_term, shape),
                    "last_change": float(last_change),
                    "structure_factor": _structure_factor_peak(refined_state, shape, rank),
                }
            )

        current = min(candidate_results, key=lambda item: item["energy"])
        best_state = current["state"]
        history.append(
            {
                "shape": [int(value) for value in shape],
                "energy": float(current["energy"]),
                "structure_factor": current["structure_factor"],
                "last_sweep_change": float(current["last_change"]),
            }
        )

        energy_converged = False
        structure_factor_converged = False
        if previous_result is not None:
            energy_converged = abs(current["energy"] - previous_result["energy"]) <= float(energy_tolerance)
            structure_factor_converged = _peak_is_stable(
                previous_result["structure_factor"],
                current["structure_factor"],
                previous_result["shape"],
                shape,
                rank,
            )
            if energy_converged and structure_factor_converged:
                stable_count += 1
            else:
                stable_count = 0
        previous_result = {
            "energy": float(current["energy"]),
            "structure_factor": current["structure_factor"],
            "shape": tuple(int(value) for value in shape),
            "last_change": float(current["last_change"]),
        }
        if stable_count >= max(1, int(convergence_repeats)):
            break

    final_shape = previous_result["shape"]
    final_peak = previous_result["structure_factor"]
    energy_converged = len(history) == 1 or abs(history[-1]["energy"] - history[-2]["energy"]) <= float(energy_tolerance)
    structure_factor_converged = len(history) == 1 or _peak_is_stable(
        history[-2]["structure_factor"],
        history[-1]["structure_factor"],
        history[-2]["shape"],
        history[-1]["shape"],
        rank,
    )
    commensurate_target_shape = _commensurate_target_shape(relaxed_lt["q_seed"], rank)
    reference_shape = tuple(1 if value is None else max(1, int(value)) for value in commensurate_target_shape)
    q_seed_matched = _peak_is_stable(
        {"peak_q": relaxed_lt["q_seed"]},
        final_peak,
        reference_shape,
        final_shape,
        rank,
    )
    if (
        _shape_matches_commensurate_target(final_shape, commensurate_target_shape, rank)
        and float(history[-1]["last_sweep_change"]) <= max(float(sweep_tolerance) * 10.0, 1e-6)
        and q_seed_matched
    ):
        energy_converged = True
        structure_factor_converged = True
    return {
        "method": "variational-pseudospin-orbital-supercell",
        "energy": float(previous_result["energy"]),
        "supercell_shape": [int(value) for value in final_shape],
        "state": {
            "cells": _serialize_supercell_state(best_state),
            "shape": [int(value) for value in final_shape],
        },
        "convergence": {
            "energy_converged": bool(energy_converged),
            "structure_factor_converged": bool(structure_factor_converged),
            "structure_factor": final_peak,
            "history": history,
            "energy_tolerance": float(energy_tolerance),
            "repeats_required": int(convergence_repeats),
            "commensurate_target_shape": [None if value is None else int(value) for value in commensurate_target_shape],
        },
        "relaxed_lt": relaxed_lt,
        "starts": int(starts),
        "seed": int(seed),
    }


def solve_pseudospin_orbital_variational(
    model,
    starts=16,
    seed=0,
    max_linear_size=5,
    convergence_repeats=2,
    energy_tolerance=1e-6,
    max_sweeps=200,
    sweep_tolerance=1e-8,
):
    if int(model.get("orbital_count", 0)) != 2:
        raise ValueError("pseudospin-orbital classical solver only supports orbital_count = 2")

    starts = max(1, int(starts))
    if not _can_use_supercell_solver(model):
        return _legacy_two_site_variational(model, starts=starts, seed=seed)
    return _supercell_variational(
        model,
        starts=starts,
        seed=seed,
        max_linear_size=max_linear_size,
        convergence_repeats=convergence_repeats,
        energy_tolerance=energy_tolerance,
        max_sweeps=max_sweeps,
        sweep_tolerance=sweep_tolerance,
    )
