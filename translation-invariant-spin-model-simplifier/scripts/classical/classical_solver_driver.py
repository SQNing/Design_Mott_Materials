#!/usr/bin/env python3
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from classical.cpn_glt_reconstruction import minimal_commensurate_supercell, rationalize_q_vector
    from classical.generalized_lt_solver import find_generalized_lt_ground_state
    from classical.lt_constraint_recovery import recover_classical_state_from_lt, strong_constraint_residual
    from classical.lt_tensor_constraint_completion import complete_lt_constraints
    from classical.lt_solver import find_lt_ground_state
    from common.classical_solver_family_routing import resolve_classical_solver_method
    from common.classical_state_result import build_final_classical_state_result
    from common.rotating_frame_consistency import infer_single_q_from_supercell_site_phases
    from common.spin_only_onsite_adapter import spin_only_onsite_matrices_by_site
else:
    from .cpn_glt_reconstruction import minimal_commensurate_supercell, rationalize_q_vector
    from .generalized_lt_solver import find_generalized_lt_ground_state
    from .lt_constraint_recovery import recover_classical_state_from_lt, strong_constraint_residual
    from .lt_tensor_constraint_completion import complete_lt_constraints
    from .lt_solver import find_lt_ground_state
    from common.classical_solver_family_routing import resolve_classical_solver_method
    from common.classical_state_result import build_final_classical_state_result
    from common.rotating_frame_consistency import infer_single_q_from_supercell_site_phases
    from common.spin_only_onsite_adapter import spin_only_onsite_matrices_by_site

try:
    from scipy.optimize import Bounds, NonlinearConstraint, minimize
except ModuleNotFoundError:  # pragma: no cover - exercised indirectly in tests
    Bounds = None
    NonlinearConstraint = None
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
    for site, matrix in spin_only_onsite_matrices_by_site(model, site_count=len(spins)).items():
        energy += float(spins[site] @ matrix @ spins[site])
    return energy


def _n_spins(model):
    return max(max(bond["source"], bond["target"]) for bond in model["bonds"]) + 1


def _n_sublattices(model):
    lattice = model.get("lattice", {})
    if lattice.get("sublattices") is not None:
        return max(1, int(lattice["sublattices"]))
    return _n_spins(model)


def _spatial_dimension(model):
    lattice = model.get("lattice", {})
    if lattice.get("dimension") is not None:
        return max(1, min(3, int(lattice["dimension"])))

    active_axes = set()
    for bond in model.get("bonds", []):
        for axis, value in enumerate(bond.get("vector", [])[:3]):
            if abs(float(value)) > 1e-12:
                active_axes.add(axis)
    return max(1, min(3, len(active_axes) or 1))


def _normalize_mesh_shape(mesh_shape, default_shape):
    if mesh_shape is None:
        return tuple(int(value) for value in default_shape)
    values = tuple(int(value) for value in mesh_shape)
    if len(values) != 3:
        raise ValueError("mesh_shape must have length 3")
    if any(value <= 0 for value in values):
        raise ValueError("mesh_shape entries must be positive")
    return values


def _default_lt_mesh_shape(model):
    dimension = _spatial_dimension(model)
    if dimension == 1:
        return (33, 1, 1)
    if dimension == 2:
        return (33, 33, 1)
    return (17, 17, 17)


def _default_generalized_lt_mesh_shape(model):
    dimension = _spatial_dimension(model)
    if dimension == 1:
        return (17, 1, 1)
    if dimension == 2:
        return (17, 17, 1)
    return (9, 9, 9)


def _normalize_lambda_bounds(lambda_bounds):
    if lambda_bounds is None:
        return (-1.0, 1.0)
    values = tuple(float(value) for value in lambda_bounds)
    if len(values) != 2:
        raise ValueError("lambda_bounds must have length 2")
    if values[0] > values[1]:
        raise ValueError("lambda_bounds must satisfy lower <= upper")
    return values


def _resolve_lt_settings(classical_config, model):
    lt_config = classical_config.get("lt", {})
    if not isinstance(lt_config, dict):
        lt_config = {}
    mesh_shape = lt_config.get("mesh_shape", classical_config.get("lt_mesh_shape"))
    return {"mesh_shape": _normalize_mesh_shape(mesh_shape, _default_lt_mesh_shape(model))}


def _resolve_generalized_lt_settings(classical_config, model):
    generalized_config = classical_config.get("generalized_lt", {})
    if not isinstance(generalized_config, dict):
        generalized_config = {}

    mesh_shape = generalized_config.get("mesh_shape", classical_config.get("generalized_lt_mesh_shape"))
    lambda_bounds = generalized_config.get(
        "lambda_bounds", classical_config.get("generalized_lt_lambda_bounds")
    )
    lambda_points = generalized_config.get(
        "lambda_points", classical_config.get("generalized_lt_lambda_points", 21)
    )
    search_strategy = generalized_config.get(
        "search_strategy", classical_config.get("generalized_lt_search_strategy")
    )
    if search_strategy is None:
        search_strategy = "grid" if _n_sublattices(model) <= 2 else "coordinate"

    lambda_points = int(lambda_points)
    if lambda_points <= 0:
        raise ValueError("lambda_points must be positive")

    return {
        "mesh_shape": _normalize_mesh_shape(mesh_shape, _default_generalized_lt_mesh_shape(model)),
        "lambda_bounds": _normalize_lambda_bounds(lambda_bounds),
        "lambda_points": lambda_points,
        "search_strategy": str(search_strategy),
    }


def _resolve_auto_settings(classical_config):
    auto_config = classical_config.get("auto_resolve", {})
    if not isinstance(auto_config, dict):
        auto_config = {}
    lt_accept_residual = float(auto_config.get("lt_accept_residual", 1e-6))
    generalized_lt_min_improvement = float(auto_config.get("generalized_lt_min_improvement", 5e-2))
    return {
        "lt_accept_residual": max(0.0, lt_accept_residual),
        "generalized_lt_min_improvement": max(0.0, generalized_lt_min_improvement),
    }


def _append_evaluated_method(auto_resolution, method_name):
    if not isinstance(auto_resolution, dict):
        return
    methods = auto_resolution.setdefault("evaluated_methods", [])
    normalized = str(method_name)
    if normalized not in methods:
        methods.append(normalized)


def _resolve_variational_settings(classical_config, model):
    variational_config = classical_config.get("variational", {})
    if not isinstance(variational_config, dict):
        variational_config = {}

    structural_dimension = _spatial_dimension(model)
    default_linear_size = 2 if structural_dimension <= 2 else 2

    max_linear_size = int(
        variational_config.get(
            "max_linear_size",
            classical_config.get("variational_max_linear_size", default_linear_size),
        )
    )
    convergence_repeats = int(
        variational_config.get(
            "convergence_repeats",
            classical_config.get("variational_convergence_repeats", 1),
        )
    )
    max_sweeps = int(
        variational_config.get(
            "max_sweeps",
            classical_config.get("variational_max_sweeps", 200),
        )
    )
    sweep_tolerance = float(
        variational_config.get(
            "sweep_tolerance",
            classical_config.get("variational_sweep_tolerance", 1.0e-10),
        )
    )
    energy_tolerance = float(
        variational_config.get(
            "energy_tolerance",
            classical_config.get("variational_energy_tolerance", 1.0e-6),
        )
    )
    mode = str(
        variational_config.get(
            "mode",
            classical_config.get("variational_mode", "supercell-local-sweep"),
        )
    )
    maxiter = int(
        variational_config.get(
            "maxiter",
            classical_config.get("variational_maxiter", 200),
        )
    )
    constraint_tolerance = float(
        variational_config.get(
            "constraint_tolerance",
            classical_config.get("variational_constraint_tolerance", 1.0e-6),
        )
    )
    lt_seed_enabled = bool(
        variational_config.get(
            "lt_seed_enabled",
            classical_config.get("variational_lt_seed_enabled", True),
        )
    )
    spin_gradient_tolerance = float(
        variational_config.get(
            "spin_gradient_tolerance",
            classical_config.get("variational_spin_gradient_tolerance", 1.0e-6),
        )
    )
    q_gradient_tolerance = float(
        variational_config.get(
            "q_gradient_tolerance",
            classical_config.get("variational_q_gradient_tolerance", 1.0e-6),
        )
    )
    cg_beta_max = variational_config.get(
        "cg_beta_max",
        classical_config.get("variational_cg_beta_max", 5.0),
    )
    guided_q_vectors = variational_config.get(
        "guided_q_vectors",
        classical_config.get("variational_guided_q_vectors", []),
    )

    return {
        "max_linear_size": max(1, max_linear_size),
        "convergence_repeats": max(1, convergence_repeats),
        "max_sweeps": max(1, max_sweeps),
        "sweep_tolerance": max(0.0, sweep_tolerance),
        "energy_tolerance": max(0.0, energy_tolerance),
        "mode": str(mode),
        "maxiter": max(1, maxiter),
        "constraint_tolerance": max(0.0, constraint_tolerance),
        "lt_seed_enabled": bool(lt_seed_enabled),
        "spin_gradient_tolerance": max(0.0, spin_gradient_tolerance),
        "q_gradient_tolerance": max(0.0, q_gradient_tolerance),
        "cg_beta_max": cg_beta_max,
        "guided_q_vectors": list(guided_q_vectors or []),
    }


def _resolve_requested_method(classical_config, recommended_method):
    explicit_method = classical_config.get("method")
    chosen_method = classical_config.get("chosen_method")
    auto_selected = bool(classical_config.get("auto_selected", False))

    if explicit_method == "auto" or explicit_method is None and chosen_method is None:
        return {
            "requested_method": "auto",
            "initial_method": recommended_method,
            "auto_mode": True,
        }
    if auto_selected:
        return {
            "requested_method": explicit_method or chosen_method or recommended_method,
            "initial_method": explicit_method or chosen_method or recommended_method,
            "auto_mode": True,
        }
    requested_method = explicit_method or chosen_method or "variational"
    return {
        "requested_method": requested_method,
        "initial_method": requested_method,
        "auto_mode": False,
    }


def _deserialize_complex_vector(serialized):
    values = []
    for item in serialized:
        if isinstance(item, dict):
            values.append(complex(float(item.get("real", 0.0)), float(item.get("imag", 0.0))))
        else:
            values.append(complex(item))
    return values


def _infer_spin_length(payload):
    local_dimension = payload.get("normalized_model", {}).get("local_hilbert", {}).get("dimension")
    if local_dimension is None:
        local_dimension = payload.get("local_dim")
    if local_dimension is None:
        return 0.5
    local_dimension = max(2, int(local_dimension))
    return 0.5 * float(local_dimension - 1)


def _resolve_lattice_positions(model):
    positions = model.get("positions")
    if isinstance(positions, list) and positions:
        return [[float(value) for value in position[:3]] for position in positions]

    lattice = model.get("lattice", {})
    positions = lattice.get("positions")
    if isinstance(positions, list) and positions:
        return [[float(value) for value in position[:3]] for position in positions]

    magnetic_sites = lattice.get("magnetic_sites")
    if isinstance(magnetic_sites, list) and magnetic_sites:
        return [[float(value) for value in position[:3]] for position in magnetic_sites]

    return []


def _site_count(model):
    positions = _resolve_lattice_positions(model)
    return max(_n_spins(model), len(positions), int(model.get("lattice", {}).get("magnetic_site_count", 0) or 0), 1)


def _normalize_positions_for_site_count(model, site_count):
    positions = _resolve_lattice_positions(model)
    normalized = []
    for index in range(int(site_count)):
        if index < len(positions):
            position = list(positions[index])
            if len(position) < 3:
                position = position + [0.0] * (3 - len(position))
            normalized.append([float(value) for value in position[:3]])
        else:
            normalized.append([0.0, 0.0, 0.0])
    return normalized


def _normalize_spin_direction(vector):
    spin = np.array(vector, dtype=float)
    norm = float(np.linalg.norm(spin))
    if norm <= 1e-12:
        return [0.0, 0.0, 1.0], 0.0
    return [float(value) / norm for value in spin], norm


def _padded_q_vector(values):
    padded = [0.0, 0.0, 0.0]
    for axis, value in enumerate(list(values or [])[:3]):
        padded[axis] = float(value)
    return padded


def _structural_supercell_shape(structural_dimension, linear_size):
    linear_size = max(1, int(linear_size))
    if int(structural_dimension) <= 1:
        return (linear_size, 1, 1)
    if int(structural_dimension) == 2:
        return (linear_size, linear_size, 1)
    return (linear_size, linear_size, linear_size)


def _structural_supercell_schedule(structural_dimension, max_linear_size):
    for linear_size in range(1, max(1, int(max_linear_size)) + 1):
        yield _structural_supercell_shape(structural_dimension, linear_size)


def _shape_dominates(shape, reference):
    if reference is None:
        return True
    return all(int(shape[axis]) >= int(reference[axis]) for axis in range(3))


def _variational_supercell_schedule(structural_dimension, max_linear_size, lt_seed_shape=None):
    schedule = []
    seen = set()

    if isinstance(lt_seed_shape, (list, tuple)) and len(lt_seed_shape) == 3:
        normalized_seed = tuple(int(value) for value in lt_seed_shape)
        schedule.append(normalized_seed)
        seen.add(normalized_seed)
    else:
        normalized_seed = None

    for shape in _structural_supercell_schedule(structural_dimension, max_linear_size):
        normalized_shape = tuple(int(value) for value in shape)
        if not _shape_dominates(normalized_shape, normalized_seed):
            continue
        if normalized_shape in seen:
            continue
        schedule.append(normalized_shape)
        seen.add(normalized_shape)
    return schedule


def _random_spin(rng):
    u = rng.uniform(-1.0, 1.0)
    phi = rng.uniform(0.0, 2.0 * math.pi)
    xy = math.sqrt(max(0.0, 1.0 - u * u))
    return np.array([xy * math.cos(phi), xy * math.sin(phi), u], dtype=float)


def _random_supercell_spin_state(shape, site_count, rng):
    state = np.zeros(tuple(shape) + (int(site_count), 3), dtype=float)
    for index in np.ndindex(tuple(shape) + (int(site_count),)):
        state[index] = _random_spin(rng)
    return state


def _tiled_supercell_spin_state(previous_state, shape, rng, *, noise_scale=0.05):
    state = np.zeros(tuple(shape) + previous_state.shape[3:], dtype=float)
    previous_shape = previous_state.shape[:3]
    site_count = previous_state.shape[3]
    for cell in np.ndindex(tuple(shape)):
        source_cell = tuple(cell[axis] % previous_shape[axis] for axis in range(3))
        for site in range(site_count):
            state[cell + (site,)] = _normalized_direction(
                previous_state[source_cell + (site,)] + noise_scale * _random_spin(rng)
            )
    return state


def _cell_mod(index, shape):
    return tuple(int(index[axis]) % int(shape[axis]) for axis in range(3))


def _bond_vector_components(bond):
    vector = [0.0, 0.0, 0.0]
    raw = bond.get("vector", [])
    for axis in range(min(3, len(raw))):
        vector[axis] = float(raw[axis])
    return tuple(int(round(value)) for value in vector)


def _supercell_energy_per_cell(model, state, shape):
    energy = 0.0
    for cell in np.ndindex(tuple(shape)):
        for bond in model["bonds"]:
            matrix = np.array(bond["matrix"], dtype=float)
            source = int(bond["source"])
            target = int(bond["target"])
            target_cell = _cell_mod(
                tuple(cell[axis] + _bond_vector_components(bond)[axis] for axis in range(3)),
                shape,
            )
            energy += float(state[cell + (source,)] @ matrix @ state[target_cell + (target,)])
        for site, matrix in spin_only_onsite_matrices_by_site(model, site_count=state.shape[3]).items():
            energy += float(state[cell + (site,)] @ matrix @ state[cell + (site,)])
    return float(energy) / float(np.prod(shape))


def _effective_spin_field(model, state, shape, cell, site):
    field = np.zeros(3, dtype=float)
    for bond in model["bonds"]:
        matrix = np.array(bond["matrix"], dtype=float)
        source = int(bond["source"])
        target = int(bond["target"])
        delta = _bond_vector_components(bond)
        if source == int(site):
            target_cell = _cell_mod(tuple(cell[axis] + delta[axis] for axis in range(3)), shape)
            field += matrix @ state[target_cell + (target,)]
        if target == int(site):
            source_cell = _cell_mod(tuple(cell[axis] - delta[axis] for axis in range(3)), shape)
            field += matrix.T @ state[source_cell + (source,)]
    onsite_matrices = spin_only_onsite_matrices_by_site(model, site_count=state.shape[3])
    if int(site) in onsite_matrices:
        onsite_matrix = onsite_matrices[int(site)]
        field += (onsite_matrix + onsite_matrix.T) @ state[cell + (site,)]
    return field


def _spin_supercell_sweep(model, state, shape):
    max_change = 0.0
    site_count = state.shape[3]
    for cell in np.ndindex(tuple(shape)):
        for site in range(site_count):
            field = _effective_spin_field(model, state, shape, cell, site)
            norm = float(np.linalg.norm(field))
            if norm <= 1.0e-12:
                continue
            updated = -field / norm
            max_change = max(max_change, float(np.linalg.norm(updated - state[cell + (site,)])))
            state[cell + (site,)] = updated
    return state, float(max_change)


def _refine_spin_supercell_state(model, initial_state, shape, *, max_sweeps, sweep_tolerance):
    state = np.array(initial_state, dtype=float, copy=True)
    last_change = None
    for _ in range(int(max_sweeps)):
        state, change = _spin_supercell_sweep(model, state, shape)
        last_change = float(change)
        if change <= float(sweep_tolerance):
            break
    return state, float(last_change if last_change is not None else 0.0)


def _spin_structure_factor_peak(state, shape, site_count):
    cell_count = float(np.prod(shape))
    best = None
    for q_index in np.ndindex(tuple(shape)):
        q_vector = [
            float(q_index[axis]) / float(shape[axis]) if int(shape[axis]) > 0 else 0.0
            for axis in range(3)
        ]
        amplitude = np.zeros((int(site_count), 3), dtype=complex)
        for cell in np.ndindex(tuple(shape)):
            phase = complex(
                np.exp(
                    -2.0j
                    * math.pi
                    * sum(float(q_vector[axis]) * float(cell[axis]) for axis in range(3))
                )
            )
            for site in range(int(site_count)):
                amplitude[site] += state[cell + (site,)] * phase
        weight = float(np.sum(np.abs(amplitude) ** 2) / (cell_count * cell_count))
        if best is None or weight > best["weight"]:
            best = {"peak_q": [float(value) for value in q_vector], "weight": float(weight)}
    return best or {"peak_q": [0.0, 0.0, 0.0], "weight": 0.0}


def _wrapped_fractional_difference(left, right):
    raw = abs(float(left) - float(right))
    return min(raw, abs(1.0 - raw))


def _peak_is_stable(previous_peak, current_peak, previous_shape, current_shape):
    for axis in range(3):
        tolerance = max(1.0 / float(previous_shape[axis]), 1.0 / float(current_shape[axis]))
        if _wrapped_fractional_difference(previous_peak["peak_q"][axis], current_peak["peak_q"][axis]) > tolerance + 1e-12:
            return False
    return True


def _serialize_spin_supercell_state(state):
    entries = []
    site_count = state.shape[3]
    for cell in np.ndindex(state.shape[:3]):
        for site in range(site_count):
            entries.append(
                {
                    "cell": [int(value) for value in cell],
                    "site": int(site),
                    "direction": [float(value) for value in state[cell + (site,)].tolist()],
                }
            )
    return entries


def _phase_from_fractional_q(q_vector, coordinates):
    return 2.0 * math.pi * sum(float(q_vector[axis]) * float(coordinates[axis]) for axis in range(3))


def _lt_mode_vectors(result):
    if not isinstance(result, dict):
        return []
    serialized_modes = []
    if isinstance(result.get("eigenspace"), list) and result.get("eigenspace"):
        serialized_modes = result.get("eigenspace") or []
    elif isinstance(result.get("eigenvector"), list) and result.get("eigenvector"):
        serialized_modes = [result.get("eigenvector") or []]

    modes = []
    for serialized_mode in serialized_modes:
        mode = np.array(_deserialize_complex_vector(serialized_mode), dtype=complex)
        if mode.size:
            modes.append(mode)
    return modes


def _lt_seed_commensurate_shape(q_vector):
    rational_q = rationalize_q_vector(q_vector)
    if rational_q is None:
        return None
    return [int(value) for value in minimal_commensurate_supercell(rational_q)]


def _active_q_axes(model):
    active_axes = []
    for axis in range(3):
        for bond in model.get("bonds", []):
            vector = list(bond.get("vector", []))
            if axis < len(vector) and abs(float(vector[axis])) > 1.0e-12:
                active_axes.append(axis)
                break
    return active_axes or [0]


def _reduced_q_vector(q_vector, axes):
    return np.array([float(q_vector[axis]) for axis in axes], dtype=float)


def _expanded_q_vector(reduced_q, axes):
    q_vector = [0.0, 0.0, 0.0]
    for index, axis in enumerate(axes):
        q_vector[int(axis)] = float(reduced_q[index])
    return q_vector


def _resolve_variational_lt_seed(model, settings):
    info = {
        "status": "disabled" if not settings.get("lt_seed_enabled") else "unavailable",
        "source": None,
        "q_vector": None,
        "commensurate_shape": None,
        "lt_result": None,
    }
    if not settings.get("lt_seed_enabled"):
        return info
    if not model.get("bonds"):
        return info

    lt_result = model.get("lt_result")
    if not isinstance(lt_result, dict) or not lt_result.get("eigenvector"):
        classical_config = model.get("classical", {})
        if not isinstance(classical_config, dict):
            classical_config = {}
        lt_settings = _resolve_lt_settings(classical_config, model)
        lt_result = find_lt_ground_state(model, mesh_shape=lt_settings["mesh_shape"])
        model["lt_result"] = lt_result
        info["source"] = "on-demand-lt"
    else:
        info["source"] = "existing-lt"

    if isinstance(lt_result, dict) and not isinstance(lt_result.get("constraint_recovery"), dict):
        _recover_lt_classical_state(model, "luttinger-tisza")

    q_vector = _padded_q_vector((lt_result or {}).get("q", [0.0, 0.0, 0.0]))
    info["status"] = "ready"
    info["q_vector"] = q_vector
    info["commensurate_shape"] = _lt_seed_commensurate_shape(q_vector)
    info["lt_result"] = lt_result
    return info


def _lt_tensor_mode_and_source(lt_result):
    modes = _lt_mode_vectors(lt_result)
    constraint_recovery = lt_result.get("constraint_recovery", {}) if isinstance(lt_result, dict) else {}
    coefficients = []
    if isinstance(constraint_recovery, dict) and isinstance(constraint_recovery.get("combination_coefficients"), list):
        coefficients = _deserialize_complex_vector(constraint_recovery.get("combination_coefficients", []))

    if modes and coefficients and len(coefficients) == len(modes) and all(len(mode) == len(modes[0]) for mode in modes):
        tensor_mode = np.zeros(len(modes[0]), dtype=complex)
        for coefficient, mode in zip(coefficients, modes):
            tensor_mode += complex(coefficient) * np.array(mode, dtype=complex)
        source = "lt-single-q-cosine-ansatz" if len(modes) == 1 else "lt-shell-combination"
        return tensor_mode, source

    if modes and len(modes[0]) % 3 == 0:
        return np.array(modes[0], dtype=complex), "lt-single-q-cosine-ansatz"

    return None, None


def _seed_state_from_lt_result(model, lt_result, shape):
    if not isinstance(lt_result, dict):
        return None

    q_vector = _padded_q_vector(lt_result.get("q", [0.0, 0.0, 0.0]))
    tensor_mode, tensor_source = _lt_tensor_mode_and_source(lt_result)

    if tensor_mode is not None and len(tensor_mode) % 3 == 0:
        mode_site_count = max(1, len(tensor_mode) // 3)
        positions = _normalize_positions_for_site_count(model, mode_site_count)
        state = np.zeros(tuple(shape) + (int(mode_site_count), 3), dtype=float)
        for cell in np.ndindex(tuple(shape)):
            for site in range(mode_site_count):
                coordinates = [float(cell[axis]) + float(positions[site][axis]) for axis in range(3)]
                phase = np.exp(1.0j * _phase_from_fractional_q(q_vector, coordinates))
                block = tensor_mode[3 * site : 3 * (site + 1)]
                state[cell + (site,)] = _normalized_direction(np.real(block * phase))
        return {"state": state, "source": str(tensor_source)}

    amplitudes = _deserialize_complex_vector(lt_result.get("eigenvector", []))
    if not amplitudes:
        return None
    site_count = max(_site_count(model), len(amplitudes), 1)
    positions = _normalize_positions_for_site_count(model, site_count)
    while len(amplitudes) < site_count:
        amplitudes.append(0.0 + 0.0j)
    state = np.zeros(tuple(shape) + (int(site_count), 3), dtype=float)
    for cell in np.ndindex(tuple(shape)):
        for site in range(site_count):
            coordinates = [float(cell[axis]) + float(positions[site][axis]) for axis in range(3)]
            phase = np.exp(1.0j * _phase_from_fractional_q(q_vector, coordinates))
            complex_spin = complex(amplitudes[site]) * phase
            state[cell + (site,)] = _normalized_direction(
                [float(np.real(complex_spin)), float(np.imag(complex_spin)), 0.0]
            )
    return {"state": state, "source": "lt-complex-planar"}


def _lt_single_q_cosine_mode_payload(model, lt_result):
    if not isinstance(lt_result, dict):
        return None

    tensor_mode, source = _lt_tensor_mode_and_source(lt_result)
    if tensor_mode is None or len(tensor_mode) % 3 != 0:
        return None

    site_count = max(1, len(tensor_mode) // 3)
    amplitudes = np.zeros((int(site_count), 3), dtype=float)
    phases = np.zeros((int(site_count), 3), dtype=float)
    for site in range(int(site_count)):
        block = np.array(tensor_mode[3 * site : 3 * (site + 1)], dtype=complex)
        amplitudes[site, :] = np.abs(block)
        phases[site, :] = np.angle(block)

    return {
        "q_vector": _padded_q_vector(lt_result.get("q", [0.0, 0.0, 0.0])),
        "amplitudes": amplitudes,
        "phases": phases,
        "site_count": int(site_count),
        "source": str(source or "lt-single-q-cosine-ansatz"),
    }


def _lt_single_q_harmonic_mode_payload(model, lt_result):
    if not isinstance(lt_result, dict):
        return None

    tensor_mode, source = _lt_tensor_mode_and_source(lt_result)
    if tensor_mode is None or len(tensor_mode) % 3 != 0:
        return None

    site_count = max(1, len(tensor_mode) // 3)
    cosine_coefficients = np.zeros((int(site_count), 3), dtype=float)
    sine_coefficients = np.zeros((int(site_count), 3), dtype=float)
    for site in range(int(site_count)):
        block = np.array(tensor_mode[3 * site : 3 * (site + 1)], dtype=complex)
        cosine_coefficients[site, :] = np.real(block)
        sine_coefficients[site, :] = -np.imag(block)

    return {
        "q_vector": _padded_q_vector(lt_result.get("q", [0.0, 0.0, 0.0])),
        "cosine_coefficients": cosine_coefficients,
        "sine_coefficients": sine_coefficients,
        "site_count": int(site_count),
        "source": str(source or "lt-single-q-harmonic-ansatz"),
    }


def _wrap_angle(value):
    return float((float(value) + math.pi) % (2.0 * math.pi) - math.pi)


def _wrap_periodic_value(value, lower, upper):
    value = float(value)
    lower = float(lower)
    upper = float(upper)
    width = upper - lower
    if not np.isfinite(value) or not np.isfinite(lower) or not np.isfinite(upper) or width <= 0.0:
        return float(np.clip(value, lower, upper))
    wrapped = ((value - lower) % width) + lower
    if wrapped >= upper:
        wrapped -= width
    return float(wrapped)


def _wrap_reduced_q_vector(reduced_q, q_bounds):
    wrapped = np.array(reduced_q, dtype=float, copy=True)
    if q_bounds is None:
        return wrapped
    for axis_index, (lower, upper) in enumerate(q_bounds[: len(wrapped)]):
        wrapped[axis_index] = _wrap_periodic_value(wrapped[axis_index], lower, upper)
    return wrapped


def _single_q_harmonic_characteristic_energy_scale(model):
    scale = 0.0
    for bond in model.get("bonds", []):
        matrix = np.array(bond.get("matrix", np.zeros((3, 3))), dtype=float)
        if matrix.size:
            scale += float(np.linalg.norm(matrix, ord=2))
    for matrix in spin_only_onsite_matrices_by_site(model, site_count=_site_count(model)).values():
        onsite = np.array(matrix, dtype=float)
        if onsite.size:
            scale += float(np.linalg.norm(onsite, ord=2))
    return max(1.0, float(scale))


def _single_q_harmonic_effective_gradient_tolerances(model, settings):
    scale = _single_q_harmonic_characteristic_energy_scale(model)
    spin_tolerance = max(0.0, float(settings.get("spin_gradient_tolerance", 1.0e-6)) * scale)
    q_tolerance = max(0.0, float(settings.get("q_gradient_tolerance", 1.0e-6)) * scale)
    return float(scale), float(spin_tolerance), float(q_tolerance)


def _spin_state_from_single_q_cosine_ansatz(
    *,
    model,
    amplitudes,
    q_vector,
    phase_offsets,
    shape,
    fallback_state=None,
):
    site_count = int(amplitudes.shape[0])
    positions = _normalize_positions_for_site_count(model, site_count)
    state = np.zeros(tuple(shape) + (site_count, 3), dtype=float)
    for cell in np.ndindex(tuple(shape)):
        for site in range(site_count):
            coordinates = [float(cell[axis]) + float(positions[site][axis]) for axis in range(3)]
            base_phase = _phase_from_fractional_q(q_vector, coordinates)
            raw = np.array(amplitudes[site, :], dtype=float) * np.cos(base_phase + np.array(phase_offsets[site, :], dtype=float))
            norm = float(np.linalg.norm(raw))
            if norm <= 1.0e-12:
                if isinstance(fallback_state, np.ndarray) and fallback_state.shape[:4] == state.shape[:4]:
                    state[cell + (site,)] = np.array(fallback_state[cell + (site,)], dtype=float)
                else:
                    state[cell + (site,)] = np.array([0.0, 0.0, 1.0], dtype=float)
            else:
                state[cell + (site,)] = raw / norm
    return state


def _single_q_cosine_q_bounds(model):
    bounds = [(-0.5, 0.5) for _ in _active_q_axes(model)]
    return bounds


def _single_q_cosine_phase_bounds(site_count):
    return [(-math.pi, math.pi) for _ in range(int(site_count) * 3)]


def _single_q_cosine_amplitude_bounds(amplitudes):
    max_amplitude = float(np.max(np.abs(np.array(amplitudes, dtype=float)))) if np.size(amplitudes) else 1.0
    bound = max(2.0, 2.0 * max_amplitude)
    return [(-bound, bound) for _ in range(int(np.size(amplitudes)))]


def _single_q_harmonic_coefficient_bounds(cosine_coefficients, sine_coefficients):
    combined = np.concatenate(
        [
            np.array(cosine_coefficients, dtype=float).reshape(-1),
            np.array(sine_coefficients, dtype=float).reshape(-1),
        ]
    )
    max_coefficient = float(np.max(np.abs(combined))) if combined.size else 1.0
    bound = max(2.0, 2.0 * max_coefficient)
    return [(-bound, bound) for _ in range(int(combined.size))]


def _split_single_q_cosine_vector(model, vector, site_count, default_amplitudes=None):
    q_axes = _active_q_axes(model)
    q_count = len(q_axes)
    phase_count = int(site_count) * 3
    reduced_q = np.array(vector[:q_count], dtype=float)
    phases = np.array(vector[q_count : q_count + phase_count], dtype=float).reshape((int(site_count), 3))
    amplitude_start = q_count + phase_count
    if len(vector) >= amplitude_start + phase_count:
        amplitudes = np.array(vector[amplitude_start : amplitude_start + phase_count], dtype=float).reshape((int(site_count), 3))
    elif default_amplitudes is not None:
        amplitudes = np.array(default_amplitudes, dtype=float).reshape((int(site_count), 3))
    else:
        amplitudes = np.ones((int(site_count), 3), dtype=float)
    return _expanded_q_vector(reduced_q, q_axes), phases, amplitudes


def _split_single_q_harmonic_vector(model, vector, site_count=None):
    q_axes = _active_q_axes(model)
    q_count = len(q_axes)
    if site_count is None:
        inferred = len(vector) - q_count
        if inferred < 0 or inferred % 6 != 0:
            raise ValueError("single-q harmonic vector must contain q plus 6 parameters per site")
        site_count = inferred // 6
    site_count = int(site_count)
    coefficient_count = 3 * site_count
    reduced_q = np.array(vector[:q_count], dtype=float)
    coeff_start = q_count
    coeff_middle = coeff_start + coefficient_count
    coeff_end = coeff_middle + coefficient_count
    if len(vector) < coeff_end:
        raise ValueError("single-q harmonic vector is shorter than expected for the inferred site count")
    cosine_coefficients = np.array(vector[coeff_start:coeff_middle], dtype=float).reshape((site_count, 3))
    sine_coefficients = np.array(vector[coeff_middle:coeff_end], dtype=float).reshape((site_count, 3))
    return _expanded_q_vector(reduced_q, q_axes), cosine_coefficients, sine_coefficients


def _single_q_harmonic_raw_state_and_cache(model, vector, shape):
    q_vector, cosine_coefficients, sine_coefficients = _split_single_q_harmonic_vector(model, vector)
    site_count = int(cosine_coefficients.shape[0])
    positions = _normalize_positions_for_site_count(model, site_count)
    state = np.zeros(tuple(shape) + (site_count, 3), dtype=float)
    cache = {}

    for cell in np.ndindex(tuple(shape)):
        for site in range(site_count):
            coordinates = [float(cell[axis]) + float(positions[site][axis]) for axis in range(3)]
            phase = _phase_from_fractional_q(q_vector, coordinates)
            cos_phase = math.cos(phase)
            sin_phase = math.sin(phase)
            raw = (
                np.array(cosine_coefficients[site], dtype=float) * cos_phase
                + np.array(sine_coefficients[site], dtype=float) * sin_phase
            )
            state[cell + (site,)] = raw
            cache[cell + (site,)] = {
                "coordinates": coordinates,
                "phase": float(phase),
                "cos_phase": float(cos_phase),
                "sin_phase": float(sin_phase),
                "cosine_coefficients": np.array(cosine_coefficients[site], dtype=float),
                "sine_coefficients": np.array(sine_coefficients[site], dtype=float),
                "raw": raw,
            }
    return state, cache


def _single_q_harmonic_value_and_gradient(model, vector, shape):
    q_axes = _active_q_axes(model)
    q_count = len(q_axes)
    q_vector, cosine_coefficients, sine_coefficients = _split_single_q_harmonic_vector(model, vector)
    del q_vector
    site_count = int(cosine_coefficients.shape[0])
    state, cache = _single_q_harmonic_raw_state_and_cache(model, vector, shape)

    energy = _supercell_energy_per_cell(model, state, shape)
    gradient = np.zeros_like(np.array(vector, dtype=float))
    cell_count = float(np.prod(shape))
    cosine_base = q_count
    sine_base = q_count + 3 * site_count

    for cell in np.ndindex(tuple(shape)):
        for site in range(site_count):
            item = cache[cell + (site,)]
            field = _effective_spin_field(model, state, shape, cell, site)
            projected_field = field / cell_count

            d_raw_phase = (
                -np.array(item["cosine_coefficients"], dtype=float) * float(item["sin_phase"])
                + np.array(item["sine_coefficients"], dtype=float) * float(item["cos_phase"])
            )

            for reduced_axis, axis in enumerate(q_axes):
                dphase_dq = 2.0 * math.pi * float(item["coordinates"][axis])
                gradient[reduced_axis] += float(np.dot(projected_field, d_raw_phase * dphase_dq))

            for component in range(3):
                gradient[cosine_base + 3 * site + component] += float(
                    projected_field[component] * float(item["cos_phase"])
                )
                gradient[sine_base + 3 * site + component] += float(
                    projected_field[component] * float(item["sin_phase"])
                )

    return float(energy), gradient


def _single_q_harmonic_constraints_and_jacobian(model, vector, shape):
    q_axes = _active_q_axes(model)
    q_count = len(q_axes)
    q_vector, cosine_coefficients, sine_coefficients = _split_single_q_harmonic_vector(model, vector)
    del q_vector
    site_count = int(cosine_coefficients.shape[0])
    state, cache = _single_q_harmonic_raw_state_and_cache(model, vector, shape)
    variable_count = len(vector)
    cosine_base = q_count
    sine_base = q_count + 3 * site_count
    constraints = []
    jacobian = []

    for cell in np.ndindex(tuple(shape)):
        for site in range(site_count):
            item = cache[cell + (site,)]
            raw = np.array(item["raw"], dtype=float)
            row = np.zeros(variable_count, dtype=float)
            d_raw_phase = (
                -np.array(item["cosine_coefficients"], dtype=float) * float(item["sin_phase"])
                + np.array(item["sine_coefficients"], dtype=float) * float(item["cos_phase"])
            )

            for reduced_axis, axis in enumerate(q_axes):
                dphase_dq = 2.0 * math.pi * float(item["coordinates"][axis])
                row[reduced_axis] = 2.0 * float(np.dot(raw, d_raw_phase * dphase_dq))

            for component in range(3):
                row[cosine_base + 3 * site + component] = 2.0 * float(raw[component] * float(item["cos_phase"]))
                row[sine_base + 3 * site + component] = 2.0 * float(raw[component] * float(item["sin_phase"]))

            constraints.append(float(np.dot(raw, raw) - 1.0))
            jacobian.append(row)

    del state
    return np.array(constraints, dtype=float), np.array(jacobian, dtype=float)


def _single_q_cosine_objective(model, vector, amplitudes, shape, fallback_state):
    q_vector, phase_offsets, vector_amplitudes = _split_single_q_cosine_vector(
        model,
        vector,
        amplitudes.shape[0],
        default_amplitudes=amplitudes,
    )
    state = _spin_state_from_single_q_cosine_ansatz(
        model=model,
        amplitudes=vector_amplitudes,
        q_vector=q_vector,
        phase_offsets=phase_offsets,
        shape=shape,
        fallback_state=fallback_state,
    )
    return _supercell_energy_per_cell(model, state, shape)


def _single_q_cosine_raw_state_and_cache(model, vector, amplitudes, shape):
    q_vector, phase_offsets, vector_amplitudes = _split_single_q_cosine_vector(
        model,
        vector,
        amplitudes.shape[0],
        default_amplitudes=amplitudes,
    )
    site_count = int(amplitudes.shape[0])
    positions = _normalize_positions_for_site_count(model, site_count)
    state = np.zeros(tuple(shape) + (site_count, 3), dtype=float)
    cache = {}

    for cell in np.ndindex(tuple(shape)):
        for site in range(site_count):
            coordinates = [float(cell[axis]) + float(positions[site][axis]) for axis in range(3)]
            base_phase = _phase_from_fractional_q(q_vector, coordinates)
            angles = base_phase + np.array(phase_offsets[site, :], dtype=float)
            local_amplitudes = np.array(vector_amplitudes[site, :], dtype=float)
            cos_angles = np.cos(angles)
            raw = local_amplitudes * cos_angles
            state[cell + (site,)] = raw
            cache[cell + (site,)] = {
                "coordinates": coordinates,
                "angles": angles,
                "amplitudes": local_amplitudes,
                "cos_angles": cos_angles,
                "raw": raw,
            }
    return state, cache


def _single_q_cosine_value_and_gradient(model, vector, amplitudes, shape, fallback_state):
    del fallback_state
    q_axes = _active_q_axes(model)
    site_count = int(amplitudes.shape[0])
    state, cache = _single_q_cosine_raw_state_and_cache(model, vector, amplitudes, shape)

    energy = _supercell_energy_per_cell(model, state, shape)
    gradient = np.zeros_like(np.array(vector, dtype=float))
    cell_count = float(np.prod(shape))
    q_count = len(q_axes)
    phase_count = site_count * 3
    amplitude_base = q_count + phase_count
    has_amplitude_variables = len(vector) >= amplitude_base + phase_count

    for cell in np.ndindex(tuple(shape)):
        for site in range(site_count):
            item = cache[cell + (site,)]
            field = _effective_spin_field(model, state, shape, cell, site)
            projected_field = field / cell_count
            d_raw_phase = -np.array(item["amplitudes"], dtype=float) * np.sin(item["angles"])

            for reduced_axis, axis in enumerate(q_axes):
                d_raw_q = d_raw_phase * (2.0 * math.pi * float(item["coordinates"][axis]))
                gradient[reduced_axis] += float(np.dot(projected_field, d_raw_q))

            phase_base = q_count + 3 * site
            for component in range(3):
                gradient[phase_base + component] += float(projected_field[component] * d_raw_phase[component])
                if has_amplitude_variables:
                    gradient[amplitude_base + 3 * site + component] += float(
                        projected_field[component] * item["cos_angles"][component]
                    )

    return float(energy), gradient


def _single_q_cosine_constraints_and_jacobian(model, vector, amplitudes, shape):
    q_axes = _active_q_axes(model)
    site_count = int(amplitudes.shape[0])
    state, cache = _single_q_cosine_raw_state_and_cache(model, vector, amplitudes, shape)
    q_count = len(q_axes)
    phase_count = site_count * 3
    amplitude_base = q_count + phase_count
    has_amplitude_variables = len(vector) >= amplitude_base + phase_count
    variable_count = len(vector)
    constraints = []
    jacobian = []

    for cell in np.ndindex(tuple(shape)):
        for site in range(site_count):
            item = cache[cell + (site,)]
            raw = np.array(item["raw"], dtype=float)
            d_raw_phase = -np.array(item["amplitudes"], dtype=float) * np.sin(item["angles"])
            row = np.zeros(variable_count, dtype=float)

            for reduced_axis, axis in enumerate(q_axes):
                d_raw_q = d_raw_phase * (2.0 * math.pi * float(item["coordinates"][axis]))
                row[reduced_axis] = 2.0 * float(np.dot(raw, d_raw_q))

            phase_base = q_count + 3 * site
            for component in range(3):
                row[phase_base + component] = 2.0 * float(raw[component] * d_raw_phase[component])
                if has_amplitude_variables:
                    row[amplitude_base + 3 * site + component] = 2.0 * float(
                        raw[component] * item["cos_angles"][component]
                    )

            constraints.append(float(np.dot(raw, raw) - 1.0))
            jacobian.append(row)

    del state
    return np.array(constraints, dtype=float), np.array(jacobian, dtype=float)


def _single_q_cosine_raw_norm_diagnostics(model, vector, amplitudes, shape):
    state, _cache = _single_q_cosine_raw_state_and_cache(model, vector, amplitudes, shape)
    norms = []
    entries = []
    for cell in np.ndindex(tuple(shape)):
        for site in range(int(amplitudes.shape[0])):
            raw = np.array(state[cell + (site,)], dtype=float)
            norm = float(np.linalg.norm(raw))
            norms.append(norm)
            entries.append({"cell": [int(value) for value in cell], "site": int(site), "norm": norm})
    norms = np.array(norms, dtype=float)
    sorted_entries = sorted(entries, key=lambda item: item["norm"])
    return {
        "min": float(np.min(norms)) if norms.size else 0.0,
        "max": float(np.max(norms)) if norms.size else 0.0,
        "mean": float(np.mean(norms)) if norms.size else 0.0,
        "median": float(np.median(norms)) if norms.size else 0.0,
        "std": float(np.std(norms)) if norms.size else 0.0,
        "max_abs_norm_minus_1": float(np.max(np.abs(norms - 1.0))) if norms.size else 0.0,
        "count_lt_1e-8": int(np.sum(norms < 1.0e-8)),
        "count_lt_1e-6": int(np.sum(norms < 1.0e-6)),
        "count_lt_1e-4": int(np.sum(norms < 1.0e-4)),
        "count_lt_1e-2": int(np.sum(norms < 1.0e-2)),
        "min_entries": sorted_entries[:8],
    }


def _single_q_harmonic_raw_norm_diagnostics(model, vector, shape):
    state, _cache = _single_q_harmonic_raw_state_and_cache(model, vector, shape)
    q_vector, cosine_coefficients, _sine_coefficients = _split_single_q_harmonic_vector(model, vector)
    del q_vector
    norms = []
    entries = []
    for cell in np.ndindex(tuple(shape)):
        for site in range(int(cosine_coefficients.shape[0])):
            raw = np.array(state[cell + (site,)], dtype=float)
            norm = float(np.linalg.norm(raw))
            norms.append(norm)
            entries.append({"cell": [int(value) for value in cell], "site": int(site), "norm": norm})
    norms = np.array(norms, dtype=float)
    sorted_entries = sorted(entries, key=lambda item: item["norm"])
    return {
        "min": float(np.min(norms)) if norms.size else 0.0,
        "max": float(np.max(norms)) if norms.size else 0.0,
        "mean": float(np.mean(norms)) if norms.size else 0.0,
        "median": float(np.median(norms)) if norms.size else 0.0,
        "std": float(np.std(norms)) if norms.size else 0.0,
        "max_abs_norm_minus_1": float(np.max(np.abs(norms - 1.0))) if norms.size else 0.0,
        "count_lt_1e-8": int(np.sum(norms < 1.0e-8)),
        "count_lt_1e-6": int(np.sum(norms < 1.0e-6)),
        "count_lt_1e-4": int(np.sum(norms < 1.0e-4)),
        "count_lt_1e-2": int(np.sum(norms < 1.0e-2)),
        "min_entries": sorted_entries[:8],
    }


def _single_q_harmonic_retract_pair(pair):
    pair = np.array(pair, dtype=float).reshape((3, 2))
    first = np.array(pair[:, 0], dtype=float)
    second = np.array(pair[:, 1], dtype=float)

    if float(np.linalg.norm(first)) <= 1.0e-12:
        if float(np.linalg.norm(second)) > 1.0e-12:
            first = np.array(second, dtype=float)
        else:
            first = np.array([1.0, 0.0, 0.0], dtype=float)
    first = first / max(float(np.linalg.norm(first)), 1.0e-12)

    second = second - float(np.dot(second, first)) * first
    if float(np.linalg.norm(second)) <= 1.0e-12:
        second = _perpendicular_axis(first)
    else:
        second = second / max(float(np.linalg.norm(second)), 1.0e-12)

    return np.column_stack([first, second]).astype(float)


def _single_q_harmonic_project_pair_tangent(pair, gradient):
    pair = _single_q_harmonic_retract_pair(pair)
    gradient = np.array(gradient, dtype=float).reshape((3, 2))
    symmetric_component = 0.5 * (pair.T @ gradient + gradient.T @ pair)
    return (gradient - pair @ symmetric_component).astype(float)


def _single_q_harmonic_retract_vector(model, vector, *, site_count=None, q_bounds=None):
    q_vector, cosine_coefficients, sine_coefficients = _split_single_q_harmonic_vector(
        model,
        vector,
        site_count=site_count,
    )
    q_axes = _active_q_axes(model)
    reduced_q = _reduced_q_vector(q_vector, q_axes)
    reduced_q = _wrap_reduced_q_vector(reduced_q, q_bounds)

    retracted_cosine = np.zeros_like(cosine_coefficients)
    retracted_sine = np.zeros_like(sine_coefficients)
    for site in range(int(cosine_coefficients.shape[0])):
        pair = _single_q_harmonic_retract_pair(
            np.column_stack([cosine_coefficients[site], sine_coefficients[site]])
        )
        retracted_cosine[site] = pair[:, 0]
        retracted_sine[site] = pair[:, 1]

    return _single_q_harmonic_vector(model, reduced_q, retracted_cosine, retracted_sine)


def _single_q_harmonic_projected_gradient(model, vector, shape, *, site_count=None):
    q_axes = _active_q_axes(model)
    q_count = len(q_axes)
    q_vector, cosine_coefficients, sine_coefficients = _split_single_q_harmonic_vector(
        model,
        vector,
        site_count=site_count,
    )
    del q_vector
    value, gradient = _single_q_harmonic_value_and_gradient(model, vector, shape)
    projected_gradient = np.array(gradient, dtype=float, copy=True)
    cosine_base = q_count
    sine_base = q_count + 3 * int(cosine_coefficients.shape[0])

    for site in range(int(cosine_coefficients.shape[0])):
        pair = np.column_stack([cosine_coefficients[site], sine_coefficients[site]])
        pair_gradient = np.column_stack(
            [
                projected_gradient[cosine_base + 3 * site : cosine_base + 3 * (site + 1)],
                projected_gradient[sine_base + 3 * site : sine_base + 3 * (site + 1)],
            ]
        )
        projected_pair_gradient = _single_q_harmonic_project_pair_tangent(pair, pair_gradient)
        projected_gradient[cosine_base + 3 * site : cosine_base + 3 * (site + 1)] = projected_pair_gradient[:, 0]
        projected_gradient[sine_base + 3 * site : sine_base + 3 * (site + 1)] = projected_pair_gradient[:, 1]

    spin_gradient_norm = float(np.linalg.norm(projected_gradient[q_count:]))
    q_gradient_norm = float(np.linalg.norm(projected_gradient[:q_count]))
    return float(value), np.array(gradient, dtype=float), projected_gradient, spin_gradient_norm, q_gradient_norm


def _single_q_harmonic_transport_vector(model, current_vector, tangent_vector, *, site_count=None):
    q_axes = _active_q_axes(model)
    q_count = len(q_axes)
    q_vector, cosine_coefficients, sine_coefficients = _split_single_q_harmonic_vector(
        model,
        current_vector,
        site_count=site_count,
    )
    del q_vector
    transported = np.array(tangent_vector, dtype=float, copy=True)
    cosine_base = q_count
    sine_base = q_count + 3 * int(cosine_coefficients.shape[0])

    for site in range(int(cosine_coefficients.shape[0])):
        pair = np.column_stack([cosine_coefficients[site], sine_coefficients[site]])
        pair_tangent = np.column_stack(
            [
                transported[cosine_base + 3 * site : cosine_base + 3 * (site + 1)],
                transported[sine_base + 3 * site : sine_base + 3 * (site + 1)],
            ]
        )
        projected_pair_tangent = _single_q_harmonic_project_pair_tangent(pair, pair_tangent)
        transported[cosine_base + 3 * site : cosine_base + 3 * (site + 1)] = projected_pair_tangent[:, 0]
        transported[sine_base + 3 * site : sine_base + 3 * (site + 1)] = projected_pair_tangent[:, 1]

    return transported


def _single_q_harmonic_polak_ribiere_beta(current_gradient, previous_gradient):
    current_gradient = np.array(current_gradient, dtype=float)
    previous_gradient = np.array(previous_gradient, dtype=float)
    denominator = float(np.dot(previous_gradient, previous_gradient))
    if not np.isfinite(denominator) or denominator <= 1.0e-18:
        return 0.0
    numerator = float(np.dot(current_gradient, current_gradient - previous_gradient))
    beta = numerator / denominator
    if not np.isfinite(beta):
        return 0.0
    return max(0.0, float(beta))


def _single_q_harmonic_backtracking_step(
    model,
    vector,
    direction,
    shape,
    *,
    site_count,
    q_bounds,
    initial_value,
    directional_derivative,
    initial_step,
    armijo=1.0e-4,
    shrink=0.5,
    max_trials=20,
):
    step = float(initial_step)
    if not np.isfinite(directional_derivative) or directional_derivative >= 0.0:
        return np.array(vector, dtype=float, copy=True), float(initial_value), 0.0, False, 0

    evaluations = 0
    for _trial in range(int(max_trials)):
        trial_vector = np.array(vector, dtype=float, copy=True) + step * np.array(direction, dtype=float)
        trial_vector = _single_q_harmonic_retract_vector(
            model,
            trial_vector,
            site_count=site_count,
            q_bounds=q_bounds,
        )
        trial_value, _trial_gradient = _single_q_harmonic_value_and_gradient(model, trial_vector, shape)
        evaluations += 1
        if float(trial_value) <= float(initial_value) + float(armijo) * step * float(directional_derivative):
            return trial_vector, float(trial_value), float(step), True, evaluations
        step *= float(shrink)

    return np.array(vector, dtype=float, copy=True), float(initial_value), 0.0, False, evaluations


def _single_q_harmonic_next_step_guess(step, *, growth=2.0, max_step=10.0):
    step = float(step)
    growth = float(growth)
    max_step = float(max_step)
    if not np.isfinite(step) or step <= 0.0:
        return 1.0
    if not np.isfinite(growth) or growth <= 1.0:
        growth = 2.0
    if not np.isfinite(max_step) or max_step <= 0.0:
        max_step = 10.0
    return float(min(max_step, max(step * growth, 1.0e-6)))


def _single_q_harmonic_jitter_vector(model, vector, *, site_count=None, q_bounds=None, rng=None, magnitude=1.0e-8):
    magnitude = float(magnitude)
    if not np.isfinite(magnitude) or magnitude <= 0.0:
        return _single_q_harmonic_retract_vector(
            model,
            vector,
            site_count=site_count,
            q_bounds=q_bounds,
        )
    if rng is None:
        rng = np.random.default_rng()
    jittered = np.array(vector, dtype=float, copy=True)
    q_count = len(_active_q_axes(model))
    if jittered.size > q_count:
        jittered[q_count:] += rng.normal(scale=magnitude, size=jittered.size - q_count)
    return _single_q_harmonic_retract_vector(
        model,
        jittered,
        site_count=site_count,
        q_bounds=q_bounds,
    )


def _single_q_cosine_candidate_is_better(candidate, incumbent, constraint_tolerance):
    if incumbent is None:
        return True
    candidate_violation = float(candidate["optimizer"].get("constr_violation", float("inf")))
    incumbent_violation = float(incumbent["optimizer"].get("constr_violation", float("inf")))
    candidate_feasible = candidate_violation <= float(constraint_tolerance)
    incumbent_feasible = incumbent_violation <= float(constraint_tolerance)
    if candidate_feasible != incumbent_feasible:
        return candidate_feasible
    if candidate_feasible and incumbent_feasible:
        return float(candidate["value"]) < float(incumbent["value"])
    if abs(candidate_violation - incumbent_violation) > float(constraint_tolerance):
        return candidate_violation < incumbent_violation
    return float(candidate["value"]) < float(incumbent["value"])


def _single_q_cosine_uniform_feasible_guess(model, amplitudes):
    q_axes = _active_q_axes(model)
    site_count = int(amplitudes.shape[0])
    phases = np.zeros((site_count, 3), dtype=float)
    free_amplitudes = np.zeros((site_count, 3), dtype=float)
    for site in range(site_count):
        free_amplitudes[site, 0] = 1.0
    return np.concatenate([np.zeros(len(q_axes), dtype=float), phases.reshape(-1), free_amplitudes.reshape(-1)]).astype(float)


def _single_q_cosine_planar_feasible_guess(model, amplitudes, reduced_q, rng=None):
    q_axes = _active_q_axes(model)
    site_count = int(amplitudes.shape[0])
    phases = np.zeros((site_count, 3), dtype=float)
    free_amplitudes = np.zeros((site_count, 3), dtype=float)
    for site in range(site_count):
        origin_phase = 0.0 if rng is None else float(rng.uniform(-math.pi, math.pi))
        phases[site, 0] = origin_phase
        phases[site, 1] = _wrap_angle(origin_phase + math.pi / 2.0)
        phases[site, 2] = 0.0
        free_amplitudes[site, 0] = 1.0
        free_amplitudes[site, 1] = 1.0
        free_amplitudes[site, 2] = 0.0
    return np.concatenate([np.array(reduced_q, dtype=float).reshape(len(q_axes)), phases.reshape(-1), free_amplitudes.reshape(-1)]).astype(float)


def _single_q_harmonic_vector(model, reduced_q, cosine_coefficients, sine_coefficients):
    q_axes = _active_q_axes(model)
    return np.concatenate(
        [
            np.array(reduced_q, dtype=float).reshape(len(q_axes)),
            np.array(cosine_coefficients, dtype=float).reshape(-1),
            np.array(sine_coefficients, dtype=float).reshape(-1),
        ]
    ).astype(float)


def _single_q_harmonic_uniform_feasible_guess(model, site_count):
    q_axes = _active_q_axes(model)
    cosine_coefficients = np.zeros((int(site_count), 3), dtype=float)
    sine_coefficients = np.zeros((int(site_count), 3), dtype=float)
    for site in range(int(site_count)):
        cosine_coefficients[site, 0] = 1.0
    return _single_q_harmonic_vector(model, np.zeros(len(q_axes), dtype=float), cosine_coefficients, sine_coefficients)


def _single_q_harmonic_planar_feasible_guess(model, site_count, reduced_q, rng=None):
    cosine_coefficients = np.zeros((int(site_count), 3), dtype=float)
    sine_coefficients = np.zeros((int(site_count), 3), dtype=float)
    for site in range(int(site_count)):
        angle = 0.0 if rng is None else float(rng.uniform(-math.pi, math.pi))
        cosine_coefficients[site, 0] = math.cos(angle)
        sine_coefficients[site, 0] = -math.sin(angle)
        cosine_coefficients[site, 1] = math.sin(angle)
        sine_coefficients[site, 1] = math.cos(angle)
    return _single_q_harmonic_vector(model, reduced_q, cosine_coefficients, sine_coefficients)


def _single_q_harmonic_lt_aligned_feasible_guess(model, cosine_coefficients, sine_coefficients, reduced_q):
    cosine_coefficients = np.array(cosine_coefficients, dtype=float)
    sine_coefficients = np.array(sine_coefficients, dtype=float)
    site_count = int(cosine_coefficients.shape[0])
    feasible_cosine = np.zeros_like(cosine_coefficients)
    feasible_sine = np.zeros_like(sine_coefficients)

    for site in range(site_count):
        cosine_vector = np.array(cosine_coefficients[site], dtype=float)
        sine_vector = np.array(sine_coefficients[site], dtype=float)

        if float(np.linalg.norm(cosine_vector)) <= 1.0e-8 and float(np.linalg.norm(sine_vector)) <= 1.0e-8:
            primary = np.array([1.0, 0.0, 0.0], dtype=float)
            secondary = np.array([0.0, 1.0, 0.0], dtype=float)
        else:
            if float(np.linalg.norm(cosine_vector)) > 1.0e-8:
                primary = cosine_vector / float(np.linalg.norm(cosine_vector))
            else:
                primary = sine_vector / max(float(np.linalg.norm(sine_vector)), 1.0e-12)

            secondary = sine_vector - float(np.dot(sine_vector, primary)) * primary
            if float(np.linalg.norm(secondary)) <= 1.0e-8:
                secondary = cosine_vector - float(np.dot(cosine_vector, primary)) * primary
            if float(np.linalg.norm(secondary)) <= 1.0e-8:
                secondary = _perpendicular_axis(primary)
            secondary = secondary / max(float(np.linalg.norm(secondary)), 1.0e-12)

        feasible_cosine[site] = primary
        feasible_sine[site] = secondary

    return _single_q_harmonic_vector(model, reduced_q, feasible_cosine, feasible_sine)


def _single_q_harmonic_lt_randomized_feasible_guess(
    model,
    cosine_coefficients,
    sine_coefficients,
    reduced_q,
    *,
    rng,
    q_bounds=None,
):
    base_vector = _single_q_harmonic_lt_aligned_feasible_guess(
        model,
        cosine_coefficients,
        sine_coefficients,
        reduced_q,
    )
    _q_vector, base_cosine, base_sine = _split_single_q_harmonic_vector(
        model,
        base_vector,
        site_count=int(np.array(cosine_coefficients, dtype=float).shape[0]),
    )

    randomized_q = np.array(reduced_q, dtype=float, copy=True)
    if q_bounds is not None and len(randomized_q):
        randomized_q += rng.normal(scale=0.1, size=len(randomized_q))
        randomized_q = _wrap_reduced_q_vector(randomized_q, q_bounds)

    randomized_cosine = np.zeros_like(base_cosine)
    randomized_sine = np.zeros_like(base_sine)
    for site in range(int(base_cosine.shape[0])):
        angle = float(rng.uniform(-math.pi, math.pi))
        cosine_theta = math.cos(angle)
        sine_theta = math.sin(angle)
        randomized_cosine[site] = cosine_theta * base_cosine[site] + sine_theta * base_sine[site]
        randomized_sine[site] = -sine_theta * base_cosine[site] + cosine_theta * base_sine[site]

    return _single_q_harmonic_vector(model, randomized_q, randomized_cosine, randomized_sine)


def _single_q_harmonic_clamp_beta(beta, beta_max):
    beta = float(beta)
    if beta_max is None:
        return beta, False
    beta_max = float(beta_max)
    if not np.isfinite(beta_max) or beta_max < 0.0:
        return beta, False
    if float(beta) > float(beta_max):
        return float(beta_max), True
    return float(beta), False


def _single_q_harmonic_guided_reduced_q_vectors(model, settings, q_bounds):
    q_axes = _active_q_axes(model)
    guided_vectors = []
    for item in list(settings.get("guided_q_vectors", []) or []):
        full_q = _padded_q_vector(item)
        reduced_q = np.array(_reduced_q_vector(full_q, q_axes), dtype=float, copy=True)
        reduced_q = _wrap_reduced_q_vector(reduced_q, q_bounds)
        guided_vectors.append(reduced_q)
    return guided_vectors


def _single_q_harmonic_guided_feasible_guesses(model, cosine_coefficients, sine_coefficients, guided_reduced_q_vectors):
    guided = []
    site_count = int(np.array(cosine_coefficients, dtype=float).shape[0])
    for guided_index, reduced_q in enumerate(guided_reduced_q_vectors):
        guided.append(
            (
                f"guided-lt-aligned-q-{guided_index}",
                _single_q_harmonic_lt_aligned_feasible_guess(
                    model,
                    cosine_coefficients,
                    sine_coefficients,
                    reduced_q,
                ),
            )
        )
        guided.append(
            (
                f"guided-planar-q-{guided_index}",
                _single_q_harmonic_planar_feasible_guess(
                    model,
                    site_count,
                    reduced_q,
                ),
            )
        )
    return guided


def _lt_single_q_cosine_variational(model, *, starts, seed, settings):
    lt_seed = _resolve_variational_lt_seed(model, settings)
    if lt_seed.get("status") != "ready" or not isinstance(lt_seed.get("lt_result"), dict):
        raise ValueError("lt-single-q-cosine variational mode requires an available LT seed")

    lt_payload = _lt_single_q_cosine_mode_payload(model, lt_seed["lt_result"])
    if lt_payload is None:
        raise ValueError("lt-single-q-cosine variational mode requires a 3-component LT eigenspace mode")

    shape = [max(1, int(value)) for value in (lt_seed.get("commensurate_shape") or [1, 1, 1])]
    structural_shape = list(
        _structural_supercell_shape(
            _spatial_dimension(model),
            settings.get("max_linear_size", 1),
        )
    )
    shape = [max(int(shape[axis]), int(structural_shape[axis])) for axis in range(3)]
    fallback_seed = _seed_state_from_lt_result(model, lt_seed["lt_result"], shape)
    fallback_state = None
    if isinstance(fallback_seed, dict) and isinstance(fallback_seed.get("state"), np.ndarray):
        fallback_state = np.array(fallback_seed["state"], dtype=float, copy=True)

    q_axes = _active_q_axes(model)
    initial_q = _reduced_q_vector(lt_payload["q_vector"], q_axes)
    initial_phase_offsets = np.array(lt_payload["phases"], dtype=float)
    initial_amplitudes = np.array(lt_payload["amplitudes"], dtype=float)
    initial_vector = np.concatenate([initial_q, initial_phase_offsets.reshape(-1), initial_amplitudes.reshape(-1)]).astype(float)
    phase_count = int(lt_payload["site_count"]) * 3
    bounds = (
        _single_q_cosine_q_bounds(model)
        + _single_q_cosine_phase_bounds(lt_payload["site_count"])
        + _single_q_cosine_amplitude_bounds(initial_amplitudes)
    )
    deterministic_guesses = [initial_vector]
    planar_lt_guess = _single_q_cosine_planar_feasible_guess(model, initial_amplitudes, initial_q)
    deterministic_guesses.append(planar_lt_guess)
    uniform_feasible_guess = _single_q_cosine_uniform_feasible_guess(model, lt_payload["amplitudes"])
    if uniform_feasible_guess is not None:
        deterministic_guesses.append(uniform_feasible_guess)
    rng = np.random.default_rng(seed)
    best = None
    constraint_tolerance = float(settings.get("constraint_tolerance", 1.0e-6))

    for start_index in range(max(1, int(starts))):
        if start_index < len(deterministic_guesses):
            guess = np.array(deterministic_guesses[start_index], dtype=float, copy=True)
        else:
            q_count = len(q_axes)
            random_q = np.array(initial_q, dtype=float, copy=True)
            if q_count:
                random_q += rng.normal(scale=0.1, size=q_count)
                for axis_index, (lower, upper) in enumerate(bounds[:q_count]):
                    random_q[axis_index] = float(np.clip(random_q[axis_index], lower, upper))
            guess = _single_q_cosine_planar_feasible_guess(model, initial_amplitudes, random_q, rng=rng)
            phase_end = q_count + phase_count
            if guess.size > phase_end:
                guess[phase_end:] += rng.normal(scale=0.25, size=guess.size - phase_end)
            for index, (lower, upper) in enumerate(bounds):
                guess[index] = float(np.clip(guess[index], lower, upper))
            if phase_end > q_count:
                guess[q_count:phase_end] = np.array([_wrap_angle(value) for value in guess[q_count:phase_end]], dtype=float)

        if minimize is None or NonlinearConstraint is None or Bounds is None:
            value, _gradient = _single_q_cosine_value_and_gradient(
                model,
                guess,
                lt_payload["amplitudes"],
                shape,
                fallback_state,
            )
            value = float(value)
            vector = np.array(guess, dtype=float)
            optimizer = {
                "success": True,
                "nit": 0,
                "nfev": 1,
                "method": "raw-random-sampling-fallback",
                "optimality": None,
                "constr_violation": float(
                    np.max(
                        np.abs(
                            _single_q_cosine_constraints_and_jacobian(
                                model,
                                guess,
                                lt_payload["amplitudes"],
                                shape,
                            )[0]
                        )
                    )
                ),
            }
        else:
            constraint = NonlinearConstraint(
                lambda x: _single_q_cosine_constraints_and_jacobian(
                    model,
                    x,
                    lt_payload["amplitudes"],
                    shape,
                )[0],
                np.zeros(int(np.prod(shape)) * int(lt_payload["site_count"]), dtype=float),
                np.zeros(int(np.prod(shape)) * int(lt_payload["site_count"]), dtype=float),
                jac=lambda x: _single_q_cosine_constraints_and_jacobian(
                    model,
                    x,
                    lt_payload["amplitudes"],
                    shape,
                )[1],
            )
            lower_bounds = np.array([lower for lower, _upper in bounds], dtype=float)
            upper_bounds = np.array([upper for _lower, upper in bounds], dtype=float)
            try:
                result = minimize(
                    lambda x: _single_q_cosine_value_and_gradient(
                        model,
                        x,
                        lt_payload["amplitudes"],
                        shape,
                        fallback_state,
                    ),
                    guess,
                    method="trust-constr",
                    jac=True,
                    bounds=Bounds(lower_bounds, upper_bounds),
                    constraints=[constraint],
                    options={
                        "maxiter": int(settings.get("maxiter", 200)),
                        "gtol": 1e-8,
                        "xtol": 1e-10,
                        "barrier_tol": 1e-10,
                        "verbose": 0,
                    },
                )
                value = float(result.fun)
                vector = np.array(result.x, dtype=float)
                optimizer = {
                    "success": bool(result.success),
                    "nit": int(getattr(result, "nit", 0)),
                    "nfev": int(getattr(result, "nfev", 0)),
                    "method": "trust-constr",
                    "optimality": None if getattr(result, "optimality", None) is None else float(result.optimality),
                    "constr_violation": float(getattr(result, "constr_violation", 0.0)),
                }
            except (FloatingPointError, ValueError, np.linalg.LinAlgError) as error:
                value, _gradient = _single_q_cosine_value_and_gradient(
                    model,
                    guess,
                    lt_payload["amplitudes"],
                    shape,
                    fallback_state,
                )
                constraints, _jacobian = _single_q_cosine_constraints_and_jacobian(
                    model,
                    guess,
                    lt_payload["amplitudes"],
                    shape,
                )
                vector = np.array(guess, dtype=float)
                optimizer = {
                    "success": False,
                    "nit": 0,
                    "nfev": 1,
                    "method": "trust-constr-error",
                    "optimality": None,
                    "constr_violation": float(np.max(np.abs(constraints))) if constraints.size else 0.0,
                    "error": str(error),
                }
        candidate = {"value": value, "vector": vector, "optimizer": optimizer}
        if _single_q_cosine_candidate_is_better(candidate, best, constraint_tolerance):
            best = candidate

    final_q_vector, final_phase_offsets, final_amplitudes = _split_single_q_cosine_vector(
        model,
        best["vector"],
        lt_payload["site_count"],
        default_amplitudes=lt_payload["amplitudes"],
    )
    final_state, _final_cache = _single_q_cosine_raw_state_and_cache(
        model,
        best["vector"],
        final_amplitudes,
        shape,
    )
    raw_norm_diagnostics = _single_q_cosine_raw_norm_diagnostics(
        model,
        best["vector"],
        lt_payload["amplitudes"],
        shape,
    )
    constraint_violation = float(best["optimizer"].get("constr_violation", float("inf")))
    constraints_satisfied = constraint_violation <= constraint_tolerance
    optimizer_success = bool(best["optimizer"].get("success", True)) and constraints_satisfied
    if optimizer_success:
        stopped_reason = "optimizer_converged"
    elif constraints_satisfied:
        stopped_reason = "optimizer_feasible_not_converged"
    else:
        stopped_reason = "optimizer_infeasible"
    positions = _normalize_positions_for_site_count(model, lt_payload["site_count"])
    structure_factor = _spin_structure_factor_peak(final_state, shape, lt_payload["site_count"])
    phase_fit = _spin_supercell_phase_fit(final_state, positions)
    phase_fit["phase_sample_summary"] = dict(phase_fit.get("phase_sample_summary", {}))
    phase_fit["phase_sample_summary"]["phase_sample_inferred_q_vector"] = [float(value) % 1.0 for value in final_q_vector]
    phase_fit["status"] = "single-q-ansatz"

    ordering = {
        "kind": "commensurate",
        "q_vector": [float(value) % 1.0 for value in final_q_vector],
        "supercell_shape": [int(value) for value in shape],
        "ansatz": "lt-single-q-cosine",
    }
    return {
        "method": "variational-single-q-cosine-spin",
        "ansatz": "lt-single-q-cosine",
        "energy": float(best["value"]),
        "supercell_shape": [int(value) for value in shape],
        "magnetic_supercell_shape": [int(value) for value in shape],
        "state": _serialize_spin_supercell_state(final_state),
        "ordering": ordering,
        "phase_fit": phase_fit,
        "rotating_frame_realization": None,
        "convergence": {
            "energy_converged": bool(optimizer_success),
            "structure_factor_converged": True,
            "history": [
                {
                    "shape": [int(value) for value in shape],
                    "energy": float(best["value"]),
                    "last_sweep_change": 0.0,
                    "structure_factor": dict(structure_factor),
                }
            ],
            "energy_tolerance": float(settings["energy_tolerance"]),
            "repeats_required": 1,
            "stopped_reason": stopped_reason,
            "search_limit_hit": False,
        },
        "search_settings": dict(settings),
        "initialization": {
            "lt_seed_status": "applied",
            "lt_seed_source": str(lt_payload["source"]),
            "lt_seed_q_vector": list(lt_seed.get("q_vector") or [0.0, 0.0, 0.0]),
            "lt_seed_commensurate_shape": [int(value) for value in shape],
            "lt_seed_start_shape": [int(value) for value in shape],
            "uniform_feasible_seed_available": bool(uniform_feasible_guess is not None),
        },
        "diagnostics_summary": {
            "single_q_fit_status": "single-q-ansatz",
            "single_q_q_vector": [float(value) % 1.0 for value in final_q_vector],
            "optimized_supercell_shape": [int(value) for value in shape],
            "magnetic_supercell_shape": [int(value) for value in shape],
            "stopped_reason": stopped_reason,
            "search_limit_hit": False,
            "lt_seed_status": "applied",
            "lt_seed_q_vector": list(lt_seed.get("q_vector") or [0.0, 0.0, 0.0]),
        },
        "ansatz_stationarity": {
            "best_objective": float(best["value"]),
            "optimizer_success": bool(optimizer_success),
            "optimizer_method": str(best["optimizer"].get("method", "unknown")),
            "optimization_mode": "direct-q-and-component-phases",
            "gradient_mode": "analytic",
            "optimizer_nit": int(best["optimizer"].get("nit", 0)),
            "optimizer_nfev": int(best["optimizer"].get("nfev", 0)),
            "optimizer_optimality": best["optimizer"].get("optimality"),
            "optimizer_constraint_violation": best["optimizer"].get("constr_violation"),
            "constraint_tolerance": float(constraint_tolerance),
            "amplitude_mode": "optimized",
            "optimized_amplitudes": [[float(value) for value in row] for row in final_amplitudes.tolist()],
            "initial_amplitudes": [[float(value) for value in row] for row in initial_amplitudes.tolist()],
            "raw_norm_diagnostics": raw_norm_diagnostics,
            "objective_definition": "direct constrained minimization of single-q cosine spin ansatz energy over q, per-site Cartesian phase offsets, and amplitudes with explicit |u(R,a)|^2 = 1 constraints",
            "active_q_axes": list(q_axes),
        },
        "starts": int(starts),
        "seed": int(seed),
        "multi_q_extension": {
            "status": "reserved",
            "trigger": "single-q-cosine-ansatz",
        },
    }


def _lt_single_q_harmonic_variational(model, *, starts, seed, settings):
    lt_seed = _resolve_variational_lt_seed(model, settings)
    if lt_seed.get("status") != "ready" or not isinstance(lt_seed.get("lt_result"), dict):
        raise ValueError("lt-single-q-harmonic variational mode requires an available LT seed")

    lt_payload = _lt_single_q_harmonic_mode_payload(model, lt_seed["lt_result"])
    if lt_payload is None:
        raise ValueError("lt-single-q-harmonic variational mode requires a 3-component LT eigenspace mode")

    shape = [max(1, int(value)) for value in (lt_seed.get("commensurate_shape") or [1, 1, 1])]
    structural_shape = list(
        _structural_supercell_shape(
            _spatial_dimension(model),
            settings.get("max_linear_size", 1),
        )
    )
    shape = [max(int(shape[axis]), int(structural_shape[axis])) for axis in range(3)]

    q_axes = _active_q_axes(model)
    initial_q = _reduced_q_vector(lt_payload["q_vector"], q_axes)
    initial_cosine = np.array(lt_payload["cosine_coefficients"], dtype=float)
    initial_sine = np.array(lt_payload["sine_coefficients"], dtype=float)
    q_bounds = _single_q_cosine_q_bounds(model)
    initial_vector = _single_q_harmonic_retract_vector(
        model,
        _single_q_harmonic_vector(model, initial_q, initial_cosine, initial_sine),
        site_count=lt_payload["site_count"],
        q_bounds=q_bounds,
    )
    guided_reduced_q_vectors = _single_q_harmonic_guided_reduced_q_vectors(
        model,
        settings,
        q_bounds,
    )

    deterministic_guesses = [
        ("lt-harmonic-seed", initial_vector),
        (
            "lt-aligned-feasible",
            _single_q_harmonic_lt_aligned_feasible_guess(model, initial_cosine, initial_sine, initial_q),
        ),
        (
            "planar-feasible",
            _single_q_harmonic_planar_feasible_guess(model, lt_payload["site_count"], initial_q),
        ),
        (
            "uniform-feasible",
            _single_q_harmonic_uniform_feasible_guess(model, lt_payload["site_count"]),
        ),
    ]
    deterministic_guesses.extend(
        _single_q_harmonic_guided_feasible_guesses(
            model,
            initial_cosine,
            initial_sine,
            guided_reduced_q_vectors,
        )
    )
    rng = np.random.default_rng(seed)
    best = None
    best_start_index = None
    best_start_source = None
    candidate_start_summaries = []
    gradient_tolerance_scale, spin_gradient_tolerance, q_gradient_tolerance = _single_q_harmonic_effective_gradient_tolerances(
        model,
        settings,
    )
    cg_beta_max = settings.get("cg_beta_max", 5.0)
    jitter_magnitude = float(settings.get("jitter", 1.0e-8))
    lt_randomized_guess_count = max(
        0,
        min(4, max(1, int(starts)) - len(deterministic_guesses)),
    )

    for start_index in range(max(1, int(starts))):
        if start_index < len(deterministic_guesses):
            start_source, start_guess = deterministic_guesses[start_index]
            guess = np.array(start_guess, dtype=float, copy=True)
        elif start_index < len(deterministic_guesses) + lt_randomized_guess_count:
            randomized_index = start_index - len(deterministic_guesses)
            start_source = f"lt-randomized-planar-{randomized_index}"
            guess = _single_q_harmonic_lt_randomized_feasible_guess(
                model,
                initial_cosine,
                initial_sine,
                initial_q,
                rng=rng,
                q_bounds=q_bounds,
            )
        else:
            start_source = f"random-planar-{start_index - len(deterministic_guesses) - lt_randomized_guess_count}"
            q_count = len(q_axes)
            random_q = np.array(initial_q, dtype=float, copy=True)
            if q_count:
                random_q += rng.normal(scale=0.1, size=q_count)
                random_q = _wrap_reduced_q_vector(random_q, q_bounds)
            guess = _single_q_harmonic_planar_feasible_guess(
                model,
                lt_payload["site_count"],
                random_q,
                rng=rng,
            )
            if guess.size > q_count:
                guess[q_count:] += rng.normal(scale=0.25, size=guess.size - q_count)

        current_vector = _single_q_harmonic_retract_vector(
            model,
            guess,
            site_count=lt_payload["site_count"],
            q_bounds=q_bounds,
        )
        current_vector = _single_q_harmonic_jitter_vector(
            model,
            current_vector,
            site_count=lt_payload["site_count"],
            q_bounds=q_bounds,
            rng=rng,
            magnitude=jitter_magnitude,
        )
        nfev = 0
        (
            initial_value,
            _initial_gradient,
            projected_gradient,
            spin_gradient_norm,
            q_gradient_norm,
        ) = _single_q_harmonic_projected_gradient(
            model,
            current_vector,
            shape,
            site_count=lt_payload["site_count"],
        )
        nfev += 1
        current_value = float(initial_value)
        accepted_iterations = 0
        optimizer_nit = 0
        optimizer_success = False
        optimizer_stopped_reason = "minimize-line-search-failed"
        previous_projected_gradient = None
        previous_direction = None
        restart_count = 0
        line_search_restart_count = 0
        final_beta = 0.0
        beta_clamped_count = 0
        step_guess = 1.0
        max_line_search_restarts = max(4, min(16, int(settings.get("maxiter", 200))))

        for iteration in range(int(settings.get("maxiter", 200))):
            optimizer_nit = int(iteration)
            if spin_gradient_norm <= spin_gradient_tolerance and q_gradient_norm <= q_gradient_tolerance:
                optimizer_success = True
                optimizer_stopped_reason = "minimize-converged"
                break

            direction = -np.array(projected_gradient, dtype=float)
            final_beta = 0.0
            if previous_projected_gradient is not None and previous_direction is not None:
                transported_previous_gradient = _single_q_harmonic_transport_vector(
                    model,
                    current_vector,
                    previous_projected_gradient,
                    site_count=lt_payload["site_count"],
                )
                transported_previous_direction = _single_q_harmonic_transport_vector(
                    model,
                    current_vector,
                    previous_direction,
                    site_count=lt_payload["site_count"],
                )
                final_beta = _single_q_harmonic_polak_ribiere_beta(
                    projected_gradient,
                    transported_previous_gradient,
                )
                final_beta, beta_was_clamped = _single_q_harmonic_clamp_beta(
                    final_beta,
                    cg_beta_max,
                )
                if beta_was_clamped:
                    beta_clamped_count += 1
                candidate_direction = -np.array(projected_gradient, dtype=float) + final_beta * transported_previous_direction
                directional_derivative = float(np.dot(projected_gradient, candidate_direction))
                if np.isfinite(directional_derivative) and directional_derivative < -1.0e-18:
                    direction = candidate_direction
                else:
                    restart_count += 1
                    final_beta = 0.0
                    direction = -np.array(projected_gradient, dtype=float)
                    step_guess = max(1.0e-6, 0.5 * float(step_guess))

            directional_derivative = float(np.dot(projected_gradient, direction))
            if not np.isfinite(directional_derivative) or directional_derivative >= -1.0e-18:
                restart_count += 1
                final_beta = 0.0
                direction = -np.array(projected_gradient, dtype=float)
                directional_derivative = float(np.dot(projected_gradient, direction))
                step_guess = max(1.0e-6, 0.5 * float(step_guess))

            (
                trial_vector,
                trial_value,
                accepted_step,
                accepted,
                evaluations,
            ) = _single_q_harmonic_backtracking_step(
                model,
                current_vector,
                direction,
                shape,
                site_count=lt_payload["site_count"],
                q_bounds=q_bounds,
                initial_value=current_value,
                directional_derivative=directional_derivative,
                initial_step=step_guess,
            )
            nfev += int(evaluations)
            if not accepted:
                restart_count += 1
                line_search_restart_count += 1
                previous_projected_gradient = None
                previous_direction = None
                final_beta = 0.0
                step_guess = max(1.0e-6, 0.5 * float(step_guess))
                if line_search_restart_count > max_line_search_restarts:
                    optimizer_stopped_reason = "minimize-line-search-failed"
                    break
                optimizer_stopped_reason = "minimize-line-search-restarted"
                continue
            accepted_iterations += 1
            previous_projected_gradient = np.array(projected_gradient, dtype=float, copy=True)
            previous_direction = np.array(direction, dtype=float, copy=True)
            current_vector = np.array(trial_vector, dtype=float, copy=True)
            current_value = float(trial_value)
            step_guess = _single_q_harmonic_next_step_guess(accepted_step)

            (
                current_value,
                _ambient_gradient,
                projected_gradient,
                spin_gradient_norm,
                q_gradient_norm,
            ) = _single_q_harmonic_projected_gradient(
                model,
                current_vector,
                shape,
                site_count=lt_payload["site_count"],
            )
            nfev += 1
        else:
            optimizer_nit = int(settings.get("maxiter", 200))
            optimizer_stopped_reason = "minimize-maxiter-reached"

        vector = np.array(current_vector, dtype=float)
        value = float(current_value)
        optimizer = {
            "success": bool(optimizer_success),
            "nit": int(optimizer_nit),
            "nfev": int(nfev),
            "method": "minimize-spiral-manifold-cg",
            "optimality": float(max(spin_gradient_norm, q_gradient_norm)),
            "constr_violation": 0.0,
            "spin_gradient_norm": float(spin_gradient_norm),
            "q_gradient_norm": float(q_gradient_norm),
            "gradient_tolerance_scale": float(gradient_tolerance_scale),
            "effective_spin_gradient_tolerance": float(spin_gradient_tolerance),
            "effective_q_gradient_tolerance": float(q_gradient_tolerance),
            "accepted_iterations": int(accepted_iterations),
            "restart_count": int(restart_count),
            "line_search_restart_count": int(line_search_restart_count),
            "final_beta": float(final_beta),
            "beta_clamped_count": int(beta_clamped_count),
            "stopped_reason": str(optimizer_stopped_reason),
            "initial_objective": float(initial_value),
        }
        candidate = {"value": float(value), "vector": vector, "optimizer": optimizer}
        candidate_start_summaries.append(
            {
                "start_index": int(start_index),
                "start_source": str(start_source),
                "initial_objective": float(initial_value),
                "initial_constraint_violation": 0.0,
                "final_objective": float(value),
                "final_constraint_violation": 0.0,
                "optimizer_success": bool(optimizer.get("success", False)),
                "optimizer_nit": int(optimizer.get("nit", 0)),
                "optimizer_nfev": int(optimizer.get("nfev", 0)),
            }
        )
        if _single_q_cosine_candidate_is_better(candidate, best, 1.0e-12):
            best = candidate
            best_start_index = int(start_index)
            best_start_source = str(start_source)

    final_q_vector, final_cosine, final_sine = _split_single_q_harmonic_vector(
        model,
        best["vector"],
        site_count=lt_payload["site_count"],
    )
    final_state, _final_cache = _single_q_harmonic_raw_state_and_cache(model, best["vector"], shape)
    raw_norm_diagnostics = _single_q_harmonic_raw_norm_diagnostics(model, best["vector"], shape)
    constraint_violation = float(best["optimizer"].get("constr_violation", 0.0))
    constraints_satisfied = True
    optimizer_success = bool(best["optimizer"].get("success", False))
    if optimizer_success:
        stopped_reason = "minimize-converged"
    else:
        stopped_reason = str(best["optimizer"].get("stopped_reason", "minimize-not-converged"))

    positions = _normalize_positions_for_site_count(model, lt_payload["site_count"])
    structure_factor = _spin_structure_factor_peak(final_state, shape, lt_payload["site_count"])
    phase_fit = _spin_supercell_phase_fit(final_state, positions)
    phase_fit["phase_sample_summary"] = dict(phase_fit.get("phase_sample_summary", {}))
    phase_fit["phase_sample_summary"]["phase_sample_inferred_q_vector"] = [float(value) % 1.0 for value in final_q_vector]
    phase_fit["status"] = "single-q-ansatz"

    ordering = {
        "kind": "commensurate",
        "q_vector": [float(value) % 1.0 for value in final_q_vector],
        "supercell_shape": [int(value) for value in shape],
        "ansatz": "lt-single-q-harmonic",
    }
    return {
        "method": "variational-single-q-harmonic-spin",
        "ansatz": "lt-single-q-harmonic",
        "energy": float(best["value"]),
        "supercell_shape": [int(value) for value in shape],
        "magnetic_supercell_shape": [int(value) for value in shape],
        "state": _serialize_spin_supercell_state(final_state),
        "ordering": ordering,
        "phase_fit": phase_fit,
        "rotating_frame_realization": None,
        "convergence": {
            "energy_converged": bool(optimizer_success),
            "structure_factor_converged": True,
            "history": [
                {
                    "shape": [int(value) for value in shape],
                    "energy": float(best["value"]),
                    "last_sweep_change": 0.0,
                    "structure_factor": dict(structure_factor),
                }
            ],
            "energy_tolerance": float(settings["energy_tolerance"]),
            "repeats_required": 1,
            "stopped_reason": stopped_reason,
            "search_limit_hit": False,
        },
        "search_settings": dict(settings),
        "initialization": {
            "lt_seed_status": "applied",
            "lt_seed_source": str(lt_payload["source"]),
            "lt_seed_q_vector": list(lt_seed.get("q_vector") or [0.0, 0.0, 0.0]),
            "lt_seed_commensurate_shape": [int(value) for value in shape],
            "lt_seed_start_shape": [int(value) for value in shape],
            "uniform_feasible_seed_available": True,
        },
        "diagnostics_summary": {
            "single_q_fit_status": "single-q-ansatz",
            "single_q_q_vector": [float(value) % 1.0 for value in final_q_vector],
            "optimized_supercell_shape": [int(value) for value in shape],
            "magnetic_supercell_shape": [int(value) for value in shape],
            "stopped_reason": stopped_reason,
            "search_limit_hit": False,
            "lt_seed_status": "applied",
            "lt_seed_q_vector": list(lt_seed.get("q_vector") or [0.0, 0.0, 0.0]),
        },
        "ansatz_stationarity": {
            "best_objective": float(best["value"]),
            "optimizer_success": bool(optimizer_success),
            "optimizer_method": str(best["optimizer"].get("method", "unknown")),
            "optimization_mode": "lt-seeded-minimize-spiral-manifold-cg-and-q-relaxation",
            "gradient_mode": "analytic",
            "optimizer_nit": int(best["optimizer"].get("nit", 0)),
            "optimizer_nfev": int(best["optimizer"].get("nfev", 0)),
            "optimizer_optimality": best["optimizer"].get("optimality"),
            "optimizer_constraint_violation": best["optimizer"].get("constr_violation"),
            "constraint_tolerance": 0.0,
            "initial_objective": float(best["optimizer"].get("initial_objective", best["value"])),
            "spin_gradient_norm": float(best["optimizer"].get("spin_gradient_norm", 0.0)),
            "q_gradient_norm": float(best["optimizer"].get("q_gradient_norm", 0.0)),
            "gradient_tolerance_scale": float(best["optimizer"].get("gradient_tolerance_scale", 1.0)),
            "effective_spin_gradient_tolerance": float(best["optimizer"].get("effective_spin_gradient_tolerance", 0.0)),
            "effective_q_gradient_tolerance": float(best["optimizer"].get("effective_q_gradient_tolerance", 0.0)),
            "accepted_iterations": int(best["optimizer"].get("accepted_iterations", 0)),
            "restart_count": int(best["optimizer"].get("restart_count", 0)),
            "line_search_restart_count": int(best["optimizer"].get("line_search_restart_count", 0)),
            "final_beta": float(best["optimizer"].get("final_beta", 0.0)),
            "beta_clamped_count": int(best["optimizer"].get("beta_clamped_count", 0)),
            "coefficient_mode": "optimized",
            "optimized_cosine_coefficients": [[float(value) for value in row] for row in final_cosine.tolist()],
            "optimized_sine_coefficients": [[float(value) for value in row] for row in final_sine.tolist()],
            "initial_cosine_coefficients": [[float(value) for value in row] for row in initial_cosine.tolist()],
            "initial_sine_coefficients": [[float(value) for value in row] for row in initial_sine.tolist()],
            "raw_norm_diagnostics": raw_norm_diagnostics,
            "objective_definition": "direct LT-seeded Sunny-like manifold minimization of single-q harmonic spin ansatz energy over q and per-site orthonormal cosine/sine spin pairs",
            "active_q_axes": list(q_axes),
            "best_start_index": best_start_index,
            "best_start_source": best_start_source,
            "candidate_start_summaries": candidate_start_summaries,
        },
        "starts": int(starts),
        "seed": int(seed),
        "multi_q_extension": {
            "status": "reserved",
            "trigger": "single-q-harmonic-ansatz",
        },
    }


def _perpendicular_axis(vector):
    candidate = np.array(vector, dtype=float)
    basis = np.array([1.0, 0.0, 0.0], dtype=float)
    if abs(float(np.dot(candidate, basis))) > 0.9:
        basis = np.array([0.0, 1.0, 0.0], dtype=float)
    perpendicular = np.cross(candidate, basis)
    norm = float(np.linalg.norm(perpendicular))
    if norm <= 1.0e-12:
        return np.array([0.0, 0.0, 1.0], dtype=float)
    return perpendicular / norm


def _infer_rotation_axis(vectors):
    normalized_vectors = [np.array(vector, dtype=float) for vector in vectors]
    reference = None
    for vector in normalized_vectors:
        norm = float(np.linalg.norm(vector))
        if norm > 1.0e-12:
            reference = vector / norm
            break
    if reference is None:
        return np.array([0.0, 0.0, 1.0], dtype=float), "degenerate"

    max_cross = max(float(np.linalg.norm(np.cross(reference, vector))) for vector in normalized_vectors)
    if max_cross <= 1.0e-6:
        return _perpendicular_axis(reference), "collinear"

    matrix = np.array(normalized_vectors, dtype=float)
    _u, _s, vh = np.linalg.svd(matrix, full_matrices=False)
    axis = np.array(vh[-1], dtype=float)
    norm = float(np.linalg.norm(axis))
    if norm <= 1.0e-12:
        return _perpendicular_axis(reference), "fallback"
    return axis / norm, "planar"


def _spin_supercell_phase_fit(state, positions):
    shape = state.shape[:3]
    site_count = state.shape[3]
    vectors = [state[cell + (site,)] for cell in np.ndindex(shape) for site in range(site_count)]
    axis, axis_kind = _infer_rotation_axis(vectors)

    reference_vector = np.array(state[(0, 0, 0, 0)], dtype=float)
    reference_perpendicular = reference_vector - float(np.dot(reference_vector, axis)) * axis
    if float(np.linalg.norm(reference_perpendicular)) <= 1.0e-8:
        for vector in vectors:
            candidate = np.array(vector, dtype=float)
            perpendicular = candidate - float(np.dot(candidate, axis)) * axis
            if float(np.linalg.norm(perpendicular)) > 1.0e-8:
                reference_perpendicular = perpendicular
                break
    if float(np.linalg.norm(reference_perpendicular)) <= 1.0e-8:
        reference_perpendicular = _perpendicular_axis(axis)

    basis_x = reference_perpendicular / max(float(np.linalg.norm(reference_perpendicular)), 1.0e-12)
    basis_y = np.cross(axis, basis_x)
    basis_y = basis_y / max(float(np.linalg.norm(basis_y)), 1.0e-12)

    site_phase_offsets = {}
    supercell_site_phases = []
    parallel_components = []
    perpendicular_norms = []
    for cell in np.ndindex(shape):
        for site in range(site_count):
            vector = np.array(state[cell + (site,)], dtype=float)
            parallel = float(np.dot(vector, axis))
            perpendicular = vector - parallel * axis
            perpendicular_norm = float(np.linalg.norm(perpendicular))
            if perpendicular_norm <= 1.0e-8:
                phase = 0.0
            else:
                phase = float(math.atan2(float(np.dot(perpendicular, basis_y)), float(np.dot(perpendicular, basis_x))))
            parallel_components.append(parallel)
            perpendicular_norms.append(perpendicular_norm)
            if cell == (0, 0, 0):
                basis_phase = 2.0 * math.pi * sum(
                    float(positions[site][axis_index]) * 0.0 for axis_index in range(3)
                )
                site_phase_offsets[str(site)] = float(phase - basis_phase)
            supercell_site_phases.append(
                {
                    "cell": [int(value) for value in cell],
                    "site": int(site),
                    "phase": float(phase),
                }
            )

    realization = {
        "status": "explicit",
        "kind": "single_q_site_phase_rotation",
        "source_order_kind": "single_q_spiral",
        "wavevector_units": "reciprocal_lattice_units",
        "phase_rule": "Q_dot_r_plus_phi_s",
        "rotation_axis": [float(value) for value in axis.tolist()],
        "site_phase_offsets": {key: float(value) for key, value in site_phase_offsets.items()},
        "supercell_shape": [int(value) for value in shape],
        "supercell_site_phases": supercell_site_phases,
        "phase_coordinate_semantics": "fractional_direct_positions_with_two_pi_factor",
    }
    summary = infer_single_q_from_supercell_site_phases(
        {
            "positions": positions,
            "site_count": site_count,
        },
        realization,
    )
    return {
        "status": str(summary.get("phase_sample_status", "unavailable")),
        "rotation_axis": [float(value) for value in axis.tolist()],
        "rotation_axis_kind": str(axis_kind),
        "parallel_component_range": [
            float(min(parallel_components) if parallel_components else 0.0),
            float(max(parallel_components) if parallel_components else 0.0),
        ],
        "perpendicular_norm_range": [
            float(min(perpendicular_norms) if perpendicular_norms else 0.0),
            float(max(perpendicular_norms) if perpendicular_norms else 0.0),
        ],
        "phase_sample_summary": summary,
        "realization": realization,
    }


def _build_minimal_single_q_realization(positions, fit):
    summary = fit.get("phase_sample_summary", {})
    q_vector = summary.get("phase_sample_inferred_q_vector")
    if not isinstance(q_vector, list):
        return None, None
    q_vector = [float(value) % 1.0 for value in q_vector]
    rational_q = rationalize_q_vector(q_vector)
    supercell_shape = minimal_commensurate_supercell(rational_q) if rational_q is not None else [1, 1, 1]
    site_offsets = summary.get("phase_sample_effective_site_phase_offsets", {})
    supercell_site_phases = []
    site_count = len(positions)
    for cell in np.ndindex(tuple(supercell_shape)):
        for site in range(site_count):
            phase = 2.0 * math.pi * sum(
                float(q_vector[axis]) * (float(cell[axis]) + float(positions[site][axis]))
                for axis in range(3)
            ) + float(site_offsets.get(str(site), 0.0))
            supercell_site_phases.append(
                {
                    "cell": [int(value) for value in cell],
                    "site": int(site),
                    "phase": float(phase),
                }
            )
    realization = dict(fit["realization"])
    realization["wavevector"] = [float(value) for value in q_vector]
    realization["site_phase_offsets"] = {str(key): float(value) for key, value in site_offsets.items()}
    realization["supercell_shape"] = [int(value) for value in supercell_shape]
    realization["supercell_site_phases"] = supercell_site_phases
    return realization, [int(value) for value in supercell_shape]


def _supercell_variational(model, *, starts, seed, settings):
    rng = np.random.default_rng(seed)
    site_count = _site_count(model)
    positions = _normalize_positions_for_site_count(model, site_count)
    structural_dimension = _spatial_dimension(model)
    lt_seed = _resolve_variational_lt_seed(model, settings)
    lt_seed_applied = False
    lt_seed_source = lt_seed.get("source")

    best_state = None
    previous = None
    stable_count = 0
    history = []
    stopped_reason = "max_linear_size_reached"

    for shape in _variational_supercell_schedule(
        structural_dimension,
        settings["max_linear_size"],
        lt_seed_shape=lt_seed.get("commensurate_shape"),
    ):
        candidates = []
        if lt_seed.get("status") == "ready":
            seed_candidate = _seed_state_from_lt_result(model, lt_seed.get("lt_result"), shape)
            if isinstance(seed_candidate, dict) and isinstance(seed_candidate.get("state"), np.ndarray):
                candidates.append(seed_candidate["state"])
                lt_seed_applied = True
                lt_seed_source = str(seed_candidate.get("source") or lt_seed_source)
        if best_state is not None:
            candidates.append(_tiled_supercell_spin_state(best_state, shape, rng))
        while len(candidates) < max(1, int(starts)):
            candidates.append(_random_supercell_spin_state(shape, site_count, rng))

        current_best = None
        for candidate in candidates[: max(1, int(starts))]:
            refined, last_change = _refine_spin_supercell_state(
                model,
                candidate,
                shape,
                max_sweeps=settings["max_sweeps"],
                sweep_tolerance=settings["sweep_tolerance"],
            )
            candidate_result = {
                "state": refined,
                "energy": _supercell_energy_per_cell(model, refined, shape),
                "last_change": float(last_change),
                "structure_factor": _spin_structure_factor_peak(refined, shape, site_count),
            }
            if current_best is None or candidate_result["energy"] < current_best["energy"]:
                current_best = candidate_result

        best_state = np.array(current_best["state"], dtype=float, copy=True)
        history.append(
            {
                "shape": [int(value) for value in shape],
                "energy": float(current_best["energy"]),
                "last_sweep_change": float(current_best["last_change"]),
                "structure_factor": dict(current_best["structure_factor"]),
            }
        )

        if previous is not None:
            energy_converged = abs(float(current_best["energy"]) - float(previous["energy"])) <= float(
                settings["energy_tolerance"]
            )
            peak_converged = _peak_is_stable(previous["structure_factor"], current_best["structure_factor"], previous["shape"], shape)
            if energy_converged and peak_converged:
                stable_count += 1
            else:
                stable_count = 0
        previous = {
            "energy": float(current_best["energy"]),
            "shape": tuple(int(value) for value in shape),
            "last_change": float(current_best["last_change"]),
            "structure_factor": dict(current_best["structure_factor"]),
        }
        if stable_count >= int(settings["convergence_repeats"]):
            stopped_reason = "stable_repeats_reached"
            break

    fit = _spin_supercell_phase_fit(best_state, positions)
    realization = None
    magnetic_shape = list(previous["shape"])
    if fit["status"] == "single-q-compatible":
        realization, minimal_shape = _build_minimal_single_q_realization(positions, fit)
        if minimal_shape is not None:
            magnetic_shape = minimal_shape

    final_energy_converged = len(history) == 1 or abs(float(history[-1]["energy"]) - float(history[-2]["energy"])) <= float(
        settings["energy_tolerance"]
    )
    final_structure_factor_converged = len(history) == 1 or _peak_is_stable(
        history[-2]["structure_factor"],
        history[-1]["structure_factor"],
        history[-2]["shape"],
        history[-1]["shape"],
    )
    if (
        stopped_reason != "stable_repeats_reached"
        and len(history) > 1
        and final_energy_converged
        and final_structure_factor_converged
    ):
        stopped_reason = "stable_repeats_reached"

    lt_seed_status = str(lt_seed.get("status", "unavailable"))
    if lt_seed_status == "ready":
        lt_seed_status = "applied" if lt_seed_applied else "unavailable"

    return {
        "method": "variational-supercell-spin",
        "energy": float(previous["energy"]),
        "supercell_shape": [int(value) for value in previous["shape"]],
        "magnetic_supercell_shape": [int(value) for value in magnetic_shape],
        "state": _serialize_spin_supercell_state(best_state),
        "phase_fit": fit,
        "rotating_frame_realization": realization,
        "convergence": {
            "energy_converged": bool(final_energy_converged),
            "structure_factor_converged": bool(final_structure_factor_converged),
            "history": history,
            "energy_tolerance": float(settings["energy_tolerance"]),
            "repeats_required": int(settings["convergence_repeats"]),
            "stopped_reason": str(stopped_reason),
            "search_limit_hit": bool(stopped_reason == "max_linear_size_reached"),
        },
        "search_settings": dict(settings),
        "initialization": {
            "lt_seed_status": str(lt_seed_status),
            "lt_seed_source": lt_seed_source,
            "lt_seed_q_vector": list(lt_seed.get("q_vector") or [0.0, 0.0, 0.0]),
            "lt_seed_commensurate_shape": (
                [int(value) for value in lt_seed.get("commensurate_shape", [])]
                if isinstance(lt_seed.get("commensurate_shape"), list)
                else None
            ),
            "lt_seed_start_shape": [int(value) for value in history[0]["shape"]],
        },
        "diagnostics_summary": {
            "single_q_fit_status": fit.get("status"),
            "single_q_q_vector": (
                [
                    float(value) % 1.0
                    for value in (
                        (fit.get("phase_sample_summary", {}) or {}).get("phase_sample_inferred_q_vector")
                        or [0.0, 0.0, 0.0]
                    )
                ]
                if isinstance(fit.get("phase_sample_summary"), dict)
                else [0.0, 0.0, 0.0]
            ),
            "optimized_supercell_shape": [int(value) for value in previous["shape"]],
            "magnetic_supercell_shape": [int(value) for value in magnetic_shape],
            "stopped_reason": str(stopped_reason),
            "search_limit_hit": bool(stopped_reason == "max_linear_size_reached"),
            "lt_seed_status": str(lt_seed_status),
            "lt_seed_q_vector": list(lt_seed.get("q_vector") or [0.0, 0.0, 0.0]),
        },
        "starts": int(starts),
        "seed": int(seed),
        "multi_q_extension": {
            "status": "reserved",
            "trigger": "phase_fit_not_single_q_compatible",
        },
    }


def _build_variational_classical_state(payload):
    variational_result = payload.get("variational_result", {})
    if not isinstance(variational_result, dict):
        return None

    spin_entries = list(variational_result.get("state", []))
    if spin_entries:
        cell0_entries = [
            entry
            for entry in spin_entries
            if entry.get("cell") == [0, 0, 0]
        ]
        if not cell0_entries:
            return None

        spin_length = _infer_spin_length(payload)
        site_frames = []
        site_norms = []
        for entry in sorted(cell0_entries, key=lambda item: int(item.get("site", 0))):
            direction, norm = _normalize_spin_direction(entry.get("direction", [0.0, 0.0, 1.0]))
            site_frames.append(
                {
                    "site": int(entry.get("site", 0)),
                    "spin_length": float(spin_length),
                    "direction": direction,
                }
            )
            site_norms.append(float(norm))

        fit = variational_result.get("phase_fit", {})
        summary = fit.get("phase_sample_summary", {}) if isinstance(fit, dict) else {}
        explicit_ordering = variational_result.get("ordering", {})
        inferred_q_vector = summary.get("phase_sample_inferred_q_vector", [0.0, 0.0, 0.0])
        if not isinstance(inferred_q_vector, list):
            inferred_q_vector = [0.0, 0.0, 0.0]
        q_vector = [float(value) % 1.0 for value in inferred_q_vector]
        magnetic_shape = variational_result.get("magnetic_supercell_shape", variational_result.get("supercell_shape", [1, 1, 1]))
        if isinstance(explicit_ordering, dict):
            explicit_q_vector = explicit_ordering.get("q_vector")
            if isinstance(explicit_q_vector, list) and len(explicit_q_vector) == 3:
                q_vector = [float(value) % 1.0 for value in explicit_q_vector]
            explicit_shape = explicit_ordering.get("supercell_shape")
            if isinstance(explicit_shape, list) and len(explicit_shape) == 3:
                magnetic_shape = [int(value) for value in explicit_shape]
        ordering = {
            "kind": "commensurate",
            "q_vector": [float(value) for value in q_vector],
            "supercell_shape": [int(value) for value in magnetic_shape],
        }
        if isinstance(explicit_ordering, dict):
            for key, value in explicit_ordering.items():
                if key in {"q_vector", "supercell_shape"}:
                    continue
                ordering[key] = value
        return {
            "site_frames": site_frames,
            "supercell_shape": [int(value) for value in magnetic_shape],
            "ordering": ordering,
            "constraint_recovery": {
                "source": "variational-supercell",
                "reconstruction": "single-q-fit-from-supercell",
                "strong_constraint_residual": strong_constraint_residual(
                    [np.array(entry["direction"], dtype=float) for entry in site_frames]
                ),
                "site_norms": site_norms,
                "ordering_reconstruction": fit,
                "supercell_search": variational_result.get("convergence", {}),
            },
        }

    spins = variational_result.get("spins", [])
    if not spins:
        return None

    spin_length = _infer_spin_length(payload)
    spin_vectors = [np.array(spin, dtype=float) for spin in spins]
    site_frames = []
    site_norms = []
    for index, spin in enumerate(spin_vectors):
        direction, norm = _normalize_spin_direction(spin)
        site_frames.append({"site": int(index), "spin_length": float(spin_length), "direction": direction})
        site_norms.append(float(norm))
    return {
        "site_frames": site_frames,
        "supercell_shape": [1, 1, 1],
        "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0], "supercell_shape": [1, 1, 1]},
        "constraint_recovery": {
            "source": "variational",
            "reconstruction": "direct",
            "strong_constraint_residual": strong_constraint_residual(spin_vectors),
            "site_norms": site_norms,
        },
    }


def _recover_lt_classical_state(payload, chosen_method):
    spin_length = _infer_spin_length(payload)
    source_result = payload.get("lt_result", {})
    amplitudes = _deserialize_complex_vector(source_result.get("eigenvector", []))
    q_vector = source_result.get("q", [0.0, 0.0, 0.0])
    target_result = source_result
    source_name = "lt"

    if chosen_method == "generalized-lt":
        target_result = payload.get("generalized_lt_result", {})
        q_vector = target_result.get("q", q_vector)
        completion = target_result.get("constraint_recovery")
        if isinstance(completion, dict) and completion.get("site_frames"):
            site_frames = []
            for frame in completion.get("site_frames", []):
                site_frames.append(
                    {
                        "site": int(frame["site"]),
                        "spin_length": float(spin_length),
                        "direction": list(frame["direction"]),
                    }
                )
            return {
                "site_frames": site_frames,
                "ordering": {"kind": "commensurate", "q_vector": q_vector},
                "constraint_recovery": completion,
            }
        eigenspace = target_result.get("eigenspace", [])
        if eigenspace:
            amplitudes = _deserialize_complex_vector(eigenspace[0])
        source_name = "generalized-lt"

    completion = target_result.get("constraint_recovery")
    if not isinstance(completion, dict) and isinstance(target_result, dict):
        has_tensor_shell = bool(target_result.get("minimum_shell")) or bool(target_result.get("eigenspace"))
        if has_tensor_shell or amplitudes:
            completion = complete_lt_constraints(target_result, payload)
            target_result["constraint_recovery"] = completion

    if isinstance(completion, dict) and completion.get("site_frames"):
        site_frames = []
        for frame in completion.get("site_frames", []):
            site_frames.append(
                {
                    "site": int(frame["site"]),
                    "spin_length": float(spin_length),
                    "direction": list(frame["direction"]),
                }
            )
        ordering = {"kind": "commensurate", "q_vector": q_vector}
        shell_q_vectors = completion.get("shell_q_vectors")
        if isinstance(shell_q_vectors, list) and len(shell_q_vectors) > 1:
            ordering["kind"] = "shell-completed"
            ordering["shell_q_vectors"] = shell_q_vectors
        return {
            "site_frames": site_frames,
            "ordering": ordering,
            "constraint_recovery": completion,
        }

    if not amplitudes:
        return None

    classical_state = recover_classical_state_from_lt(
        payload,
        q=q_vector,
        amplitudes=amplitudes,
        spin_length=spin_length,
        source=source_name,
    )
    target_result["constraint_recovery"] = classical_state["constraint_recovery"]
    return classical_state


def _constraint_residual(result):
    if not isinstance(result, dict):
        return None
    constraint_recovery = result.get("constraint_recovery", {})
    residual = constraint_recovery.get("max_site_norm_residual")
    if residual is not None:
        return float(residual)
    residual = constraint_recovery.get("strong_constraint_residual")
    if residual is None:
        return None
    return float(residual)


def _constraint_status(result):
    if not isinstance(result, dict):
        return None
    constraint_recovery = result.get("constraint_recovery", {})
    status = constraint_recovery.get("status")
    if status is None:
        return None
    return str(status)


def _constraint_completion_succeeds(result, tolerance):
    status = _constraint_status(result)
    if status in {"exact_relaxed_hit", "completed_from_shell"}:
        return True
    residual = _constraint_residual(result)
    if residual is None:
        return False
    return residual <= float(tolerance)


def _generalized_lt_bound_improvement(payload):
    lt_result = payload.get("lt_result", {})
    generalized_lt_result = payload.get("generalized_lt_result", {})
    lt_bound = lt_result.get("lowest_eigenvalue")
    generalized_bound = generalized_lt_result.get("tightened_lower_bound")
    if lt_bound is None or generalized_bound is None:
        return None
    return float(generalized_bound) - float(lt_bound)


def _selected_solver_result(payload, chosen_method):
    if chosen_method == "variational":
        return payload.get("variational_result", {})
    if chosen_method == "luttinger-tisza":
        return payload.get("lt_result", {})
    if chosen_method == "generalized-lt":
        return payload.get("generalized_lt_result", {})
    return {}


def _selected_solver_energy(payload, chosen_method):
    solver_result = _selected_solver_result(payload, chosen_method)
    if chosen_method == "variational":
        energy = solver_result.get("energy")
    elif chosen_method == "luttinger-tisza":
        energy = solver_result.get("lowest_eigenvalue")
    elif chosen_method == "generalized-lt":
        energy = solver_result.get("tightened_lower_bound")
    else:
        energy = None
    if energy is None:
        return None
    return float(energy)


def _classical_state_supercell_shape(classical_state):
    ordering = classical_state.get("ordering", {}) if isinstance(classical_state, dict) else {}
    supercell_shape = ordering.get("supercell_shape")
    if supercell_shape is None:
        return [1, 1, 1]
    return [int(value) for value in supercell_shape]


def _build_spin_only_classical_state_result(payload, chosen_method, classical_state):
    method_metadata = resolve_classical_solver_method(chosen_method)
    if method_metadata["solver_family"] != "spin_only_explicit":
        raise ValueError(f"unsupported classical solver method: {chosen_method}")
    if not isinstance(classical_state, dict) or not classical_state:
        return None

    diagnostics = {}
    constraint_recovery = classical_state.get("constraint_recovery")
    if isinstance(constraint_recovery, dict):
        diagnostics["constraint_recovery"] = constraint_recovery

    result = build_final_classical_state_result(classical_state, diagnostics=diagnostics)
    result["solver_family"] = method_metadata["solver_family"]
    result["method"] = method_metadata["standardized_method"]
    result["ordering"] = classical_state.get("ordering")
    result["supercell_shape"] = _classical_state_supercell_shape(classical_state)

    energy = _selected_solver_energy(payload, chosen_method)
    if energy is not None:
        result["energy"] = energy
    return result


def _choose_auto_method(recommended_method, lt_residual, generalized_lt_residual, model, auto_settings):
    if recommended_method == "variational":
        return "variational", "recommended-variational"

    if lt_residual is not None and lt_residual <= auto_settings["lt_accept_residual"]:
        return "luttinger-tisza", "lt-residual-within-tolerance"

    if _n_sublattices(model) > 1 and generalized_lt_residual is not None and lt_residual is not None:
        if generalized_lt_residual + auto_settings["generalized_lt_min_improvement"] < lt_residual:
            return "generalized-lt", "generalized-lt-improved-residual"
        return "variational", "generalized-lt-did-not-improve-residual"

    if _n_sublattices(model) > 1 and generalized_lt_residual is not None and lt_residual is None:
        return "generalized-lt", "generalized-lt-available-without-lt-residual"

    if _n_sublattices(model) <= 1:
        return "variational", "single-sublattice-lt-residual-too-large"

    return "variational", "missing-residual-diagnostics"


def _resolve_lt_like_method(initial_method, payload, auto_settings):
    lt_complete = _constraint_completion_succeeds(payload.get("lt_result"), auto_settings["lt_accept_residual"])
    generalized_lt_complete = _constraint_completion_succeeds(
        payload.get("generalized_lt_result"),
        auto_settings["lt_accept_residual"],
    )
    improvement = _generalized_lt_bound_improvement(payload)

    if initial_method == "luttinger-tisza":
        if lt_complete:
            return "luttinger-tisza", "lt-completion-succeeded"
        if generalized_lt_complete and improvement is not None and improvement >= auto_settings["generalized_lt_min_improvement"]:
            return "generalized-lt", "generalized-lt-improved-bound-and-completed"
        return "variational", "lt-needs-variational-polish"

    if initial_method == "generalized-lt":
        if lt_complete:
            return "luttinger-tisza", "lt-already-exact"
        if generalized_lt_complete and (
            improvement is None or improvement >= auto_settings["generalized_lt_min_improvement"]
        ):
            return "generalized-lt", "generalized-lt-improved-bound-and-completed"
        return "variational", "no-exact-lt-or-glt-completion"

    return initial_method, "non-lt-like-method"


def _normalized_direction(direction):
    if direction is None:
        direction = [0.0, 0.0, 1.0]
    vector = np.array(direction, dtype=float)
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        raise ValueError("field direction must have non-zero norm")
    return vector / norm


def magnetization_per_spin(spins, field_direction=None):
    direction = _normalized_direction(field_direction)
    return float(np.mean(spins, axis=0) @ direction)


def infer_high_temperature_energy_per_spin(model):
    n_spins = _n_spins(model)
    energy_total = 0.0
    for bond in model["bonds"]:
        if int(bond["source"]) != int(bond["target"]):
            continue
        matrix = np.array(bond["matrix"], dtype=float)
        energy_total += float(np.trace(matrix) / 3.0)
    return energy_total / float(n_spins)


def resolve_temperature_schedule(temperatures, scan_order="as_given"):
    indexed = [(index, float(temperature)) for index, temperature in enumerate(temperatures)]
    if scan_order == "as_given":
        return indexed
    if scan_order == "ascending":
        return sorted(indexed, key=lambda item: item[1])
    if scan_order == "descending":
        return sorted(indexed, key=lambda item: item[1], reverse=True)
    raise ValueError(f"unsupported scan_order: {scan_order}")


def integrated_autocorrelation_time(samples):
    values = np.array(samples, dtype=float)
    sample_count = len(values)
    if sample_count < 2:
        return 0.0
    centered = values - float(np.mean(values))
    variance = float(np.mean(centered**2))
    if variance <= 1e-15:
        return 0.0

    tau = 0.5
    max_lag = sample_count - 1
    for lag in range(1, max_lag + 1):
        covariance = float(np.mean(centered[:-lag] * centered[lag:]))
        rho = covariance / variance
        if rho <= 0.0:
            break
        tau += rho
    return float(tau)


def _mean_stderr(samples):
    values = np.array(samples, dtype=float)
    sample_count = len(values)
    if sample_count == 0:
        raise ValueError("at least one sample is required")
    if sample_count == 1:
        return 0.0, 0.0

    variance = float(np.mean((values - float(np.mean(values))) ** 2))
    if variance <= 1e-15:
        return 0.0, integrated_autocorrelation_time(values)

    tau = integrated_autocorrelation_time(values)
    correlation_factor = max(1.0, 2.0 * tau)
    stderr = math.sqrt(variance * correlation_factor / float(sample_count))
    return float(stderr), float(tau)


def _variance_stderr(samples):
    values = np.array(samples, dtype=float)
    if len(values) < 2:
        return 0.0
    centered_squares = (values - float(np.mean(values))) ** 2
    stderr, _tau = _mean_stderr(centered_squares)
    return float(stderr)


def recommend_method(model):
    if model.get("bonds"):
        return "luttinger-tisza"
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
    classical_config = model.get("classical", {})
    if not isinstance(classical_config, dict):
        classical_config = {}
    settings = _resolve_variational_settings(classical_config, model)
    if settings.get("mode") == "lt-single-q-harmonic":
        return _lt_single_q_harmonic_variational(model, starts=starts, seed=seed, settings=settings)
    if settings.get("mode") == "lt-single-q-cosine":
        return _lt_single_q_cosine_variational(model, starts=starts, seed=seed, settings=settings)
    return _supercell_variational(model, starts=starts, seed=seed, settings=settings)


def random_spin(rng):
    u = rng.uniform(-1.0, 1.0)
    phi = rng.uniform(0.0, 2.0 * math.pi)
    xy = math.sqrt(max(0.0, 1.0 - u * u))
    return np.array([xy * math.cos(phi), xy * math.sin(phi), u])


def metropolis_step(model, spins, temperature, rng, current_energy=None):
    trial = spins.copy()
    index = int(rng.integers(0, len(spins)))
    old_energy = classical_energy(model, spins) if current_energy is None else current_energy
    trial[index] = random_spin(rng)
    new_energy = classical_energy(model, trial)
    if new_energy <= old_energy:
        return trial, new_energy
    if temperature <= 0.0:
        return spins, old_energy
    accept_prob = math.exp(-(new_energy - old_energy) / temperature)
    if rng.uniform() < accept_prob:
        return trial, new_energy
    return spins, old_energy


def metropolis_sweep(model, spins, temperature, rng):
    energy = classical_energy(model, spins)
    for _ in range(len(spins)):
        spins, energy = metropolis_step(model, spins, temperature, rng, current_energy=energy)
    return spins, energy


def summarize_thermodynamics(
    temperatures,
    energy_samples,
    magnetization_samples,
    *,
    n_spins=1,
    high_temperature_entropy=0.0,
    energy_infinite_temperature=0.0,
    scan_order="as_given",
    reuse_configuration=True,
    sweeps=None,
    burn_in=None,
    measurement_interval=1,
):
    if len(temperatures) != len(energy_samples) or len(temperatures) != len(magnetization_samples):
        raise ValueError("temperature grid and sample collections must have the same length")

    summaries = []
    for index, temperature in enumerate(temperatures):
        temperature = float(temperature)
        if temperature <= 0.0:
            raise ValueError("temperatures must be strictly positive")

        local_energies = np.array(energy_samples[index], dtype=float)
        local_magnetizations = np.array(magnetization_samples[index], dtype=float)
        if local_energies.size == 0 or local_magnetizations.size == 0:
            raise ValueError("each temperature requires at least one post-burn-in measurement")

        mean_energy = float(np.mean(local_energies))
        mean_magnetization = float(np.mean(local_magnetizations))
        energy_variance = float(max(0.0, np.mean(local_energies**2) - mean_energy**2))
        magnetization_variance = float(max(0.0, np.mean(local_magnetizations**2) - mean_magnetization**2))
        beta = 1.0 / temperature
        energy_stderr, energy_tau = _mean_stderr(local_energies)
        magnetization_stderr, magnetization_tau = _mean_stderr(local_magnetizations)
        specific_heat_stderr = float(beta * beta * n_spins * _variance_stderr(local_energies))
        susceptibility_stderr = float(beta * n_spins * _variance_stderr(local_magnetizations))
        summaries.append(
            {
                "index": index,
                "temperature": temperature,
                "beta": beta,
                "energy": mean_energy,
                "magnetization": mean_magnetization,
                "energy_variance": energy_variance,
                "magnetization_variance": magnetization_variance,
                "energy_stderr": energy_stderr,
                "magnetization_stderr": magnetization_stderr,
                "energy_tau": energy_tau,
                "magnetization_tau": magnetization_tau,
                "specific_heat": float(beta * beta * n_spins * energy_variance),
                "susceptibility": float(beta * n_spins * magnetization_variance),
                "specific_heat_stderr": specific_heat_stderr,
                "susceptibility_stderr": susceptibility_stderr,
            }
        )

    sorted_summaries = sorted(summaries, key=lambda item: item["beta"])
    previous_beta = 0.0
    previous_energy = float(energy_infinite_temperature)
    previous_energy_stderr = 0.0
    cumulative_beta_f = -float(high_temperature_entropy)
    cumulative_beta_f_variance = 0.0
    for summary in sorted_summaries:
        delta_beta = summary["beta"] - previous_beta
        cumulative_beta_f += 0.5 * (previous_energy + summary["energy"]) * delta_beta
        cumulative_beta_f_variance += (0.5 * delta_beta) ** 2 * (
            previous_energy_stderr**2 + summary["energy_stderr"] ** 2
        )
        summary["free_energy"] = float(cumulative_beta_f / summary["beta"])
        summary["free_energy_stderr"] = float(math.sqrt(cumulative_beta_f_variance) / summary["beta"])
        summary["entropy"] = float((summary["energy"] - summary["free_energy"]) / summary["temperature"])
        summary["entropy_stderr"] = float(
            math.sqrt(summary["energy_stderr"] ** 2 + summary["free_energy_stderr"] ** 2) / summary["temperature"]
        )
        previous_beta = summary["beta"]
        previous_energy = summary["energy"]
        previous_energy_stderr = summary["energy_stderr"]

    sorted_summaries.sort(key=lambda item: item["index"])
    grid = [
        {
            "temperature": summary["temperature"],
            "beta": summary["beta"],
            "energy": summary["energy"],
            "magnetization": summary["magnetization"],
            "specific_heat": summary["specific_heat"],
            "susceptibility": summary["susceptibility"],
            "free_energy": summary["free_energy"],
            "entropy": summary["entropy"],
            "energy_stderr": summary["energy_stderr"],
            "magnetization_stderr": summary["magnetization_stderr"],
            "specific_heat_stderr": summary["specific_heat_stderr"],
            "susceptibility_stderr": summary["susceptibility_stderr"],
            "free_energy_stderr": summary["free_energy_stderr"],
            "entropy_stderr": summary["entropy_stderr"],
            "energy_autocorrelation_time": summary["energy_tau"],
            "magnetization_autocorrelation_time": summary["magnetization_tau"],
        }
        for summary in sorted_summaries
    ]

    return {
        "grid": grid,
        "observables": {
            "energy": [summary["energy"] for summary in sorted_summaries],
            "free_energy": [summary["free_energy"] for summary in sorted_summaries],
            "specific_heat": [summary["specific_heat"] for summary in sorted_summaries],
            "magnetization": [summary["magnetization"] for summary in sorted_summaries],
            "susceptibility": [summary["susceptibility"] for summary in sorted_summaries],
            "entropy": [summary["entropy"] for summary in sorted_summaries],
        },
        "uncertainties": {
            "energy": [summary["energy_stderr"] for summary in sorted_summaries],
            "free_energy": [summary["free_energy_stderr"] for summary in sorted_summaries],
            "specific_heat": [summary["specific_heat_stderr"] for summary in sorted_summaries],
            "magnetization": [summary["magnetization_stderr"] for summary in sorted_summaries],
            "susceptibility": [summary["susceptibility_stderr"] for summary in sorted_summaries],
            "entropy": [summary["entropy_stderr"] for summary in sorted_summaries],
        },
        "autocorrelation": {
            "energy": [summary["energy_tau"] for summary in sorted_summaries],
            "magnetization": [summary["magnetization_tau"] for summary in sorted_summaries],
        },
        "reference": {
            "high_temperature_entropy": float(high_temperature_entropy),
            "energy_infinite_temperature": float(energy_infinite_temperature),
            "normalization": "per_spin",
        },
        "sampling": {
            "scan_order": scan_order,
            "reuse_configuration": bool(reuse_configuration),
            "sweeps": sweeps,
            "burn_in": burn_in,
            "measurement_interval": int(measurement_interval),
        },
    }


def estimate_thermodynamics(
    model,
    temperatures,
    sweeps=100,
    burn_in=50,
    seed=0,
    measurement_interval=1,
    field_direction=None,
    high_temperature_entropy=0.0,
    energy_infinite_temperature=None,
    scan_order="as_given",
    reuse_configuration=True,
):
    rng = np.random.default_rng(seed)
    n_spins = _n_spins(model)
    spins = np.array([random_spin(rng) for _ in range(n_spins)])
    if measurement_interval <= 0:
        raise ValueError("measurement_interval must be positive")
    if energy_infinite_temperature is None:
        energy_infinite_temperature = infer_high_temperature_energy_per_spin(model)

    energy_samples = [None] * len(temperatures)
    magnetization_samples = [None] * len(temperatures)

    for index, temperature in resolve_temperature_schedule(temperatures, scan_order=scan_order):
        if not reuse_configuration:
            spins = np.array([random_spin(rng) for _ in range(n_spins)])
        local_energies = []
        local_mags = []
        for sweep in range(sweeps + burn_in):
            spins, energy = metropolis_sweep(model, spins, temperature, rng)
            if sweep >= burn_in and (sweep - burn_in) % measurement_interval == 0:
                local_energies.append(float(energy) / float(n_spins))
                local_mags.append(magnetization_per_spin(spins, field_direction=field_direction))

        energy_samples[index] = local_energies
        magnetization_samples[index] = local_mags

    return summarize_thermodynamics(
        temperatures,
        energy_samples,
        magnetization_samples,
        n_spins=n_spins,
        high_temperature_entropy=high_temperature_entropy,
        energy_infinite_temperature=energy_infinite_temperature,
        scan_order=scan_order,
        reuse_configuration=reuse_configuration,
        sweeps=sweeps,
        burn_in=burn_in,
        measurement_interval=measurement_interval,
    )


def run_classical_solver(payload, starts=16, seed=0):
    recommended_method = payload.setdefault("recommended_method", recommend_method(payload))
    classical_config = payload.setdefault("classical", {})
    method_resolution = _resolve_requested_method(classical_config, recommended_method)
    requested_method = method_resolution["requested_method"]
    initial_method = method_resolution["initial_method"]
    auto_mode = method_resolution["auto_mode"]
    auto_settings = _resolve_auto_settings(classical_config)

    resolve_classical_solver_method(initial_method)

    classical_config["requested_method"] = requested_method
    classical_config["auto_resolution"] = {
        "enabled": bool(auto_mode),
        "recommended_method": recommended_method,
        "initial_method": initial_method,
        "resolved_method": None,
        "lt_residual": None,
        "generalized_lt_residual": None,
        "reason": None,
        "lt_accept_residual": auto_settings["lt_accept_residual"],
        "generalized_lt_min_improvement": auto_settings["generalized_lt_min_improvement"],
        "evaluated_methods": [],
    }

    if not auto_mode:
        classical_config["chosen_method"] = initial_method

    if initial_method in {"luttinger-tisza", "generalized-lt"}:
        lt_settings = _resolve_lt_settings(classical_config, payload)
        payload["lt_result"] = find_lt_ground_state(payload, mesh_shape=lt_settings["mesh_shape"])
        _append_evaluated_method(classical_config["auto_resolution"], "luttinger-tisza")

    if initial_method == "generalized-lt":
        generalized_settings = _resolve_generalized_lt_settings(classical_config, payload)
        payload["generalized_lt_result"] = find_generalized_lt_ground_state(
            payload,
            mesh_shape=generalized_settings["mesh_shape"],
            lambda_bounds=generalized_settings["lambda_bounds"],
            lambda_points=generalized_settings["lambda_points"],
            search_strategy=generalized_settings["search_strategy"],
        )
        _append_evaluated_method(classical_config["auto_resolution"], "generalized-lt")

    lt_classical_state = None
    generalized_lt_classical_state = None
    variational_classical_state = None

    if "lt_result" in payload:
        lt_classical_state = _recover_lt_classical_state(payload, "luttinger-tisza")
        classical_config["auto_resolution"]["lt_residual"] = _constraint_residual(payload.get("lt_result"))

    if initial_method == "generalized-lt":
        generalized_lt_classical_state = _recover_lt_classical_state(payload, "generalized-lt")
        classical_config["auto_resolution"]["generalized_lt_residual"] = _constraint_residual(
            payload.get("generalized_lt_result")
        )

    chosen_method = initial_method
    classical_state = None
    resolution_reason = "explicit-user-choice"

    if auto_mode:
        lt_residual = classical_config["auto_resolution"]["lt_residual"]
        generalized_lt_residual = classical_config["auto_resolution"]["generalized_lt_residual"]

        if initial_method == "luttinger-tisza" and lt_residual is not None and lt_residual > auto_settings["lt_accept_residual"]:
            generalized_settings = _resolve_generalized_lt_settings(classical_config, payload)
            payload["generalized_lt_result"] = find_generalized_lt_ground_state(
                payload,
                mesh_shape=generalized_settings["mesh_shape"],
                lambda_bounds=generalized_settings["lambda_bounds"],
                lambda_points=generalized_settings["lambda_points"],
                search_strategy=generalized_settings["search_strategy"],
            )
            _append_evaluated_method(classical_config["auto_resolution"], "generalized-lt")
            generalized_lt_classical_state = _recover_lt_classical_state(payload, "generalized-lt")
            generalized_lt_residual = _constraint_residual(payload.get("generalized_lt_result"))
            classical_config["auto_resolution"]["generalized_lt_residual"] = generalized_lt_residual

        if initial_method in {"luttinger-tisza", "generalized-lt"}:
            chosen_method, resolution_reason = _resolve_lt_like_method(initial_method, payload, auto_settings)
        else:
            chosen_method, resolution_reason = _choose_auto_method(
                recommended_method,
                lt_residual=classical_config["auto_resolution"]["lt_residual"],
                generalized_lt_residual=classical_config["auto_resolution"]["generalized_lt_residual"],
                model=payload,
                auto_settings=auto_settings,
            )
    elif initial_method in {"luttinger-tisza", "generalized-lt"}:
        chosen_method, resolution_reason = _resolve_lt_like_method(initial_method, payload, auto_settings)

    if chosen_method == "variational":
        payload["variational_result"] = solve_variational(payload, starts=starts, seed=seed)
        _append_evaluated_method(classical_config["auto_resolution"], "variational")
        variational_classical_state = _build_variational_classical_state(payload)
    else:
        payload.pop("variational_result", None)

    if chosen_method == "luttinger-tisza":
        classical_state = lt_classical_state
    elif chosen_method == "generalized-lt":
        classical_state = generalized_lt_classical_state
    elif chosen_method == "variational":
        classical_state = variational_classical_state

    classical_config["chosen_method"] = chosen_method
    classical_config["auto_resolution"]["resolved_method"] = chosen_method
    classical_config["auto_resolution"]["reason"] = resolution_reason

    if classical_state is not None:
        payload["classical_state"] = classical_state
        classical_config["classical_state"] = classical_state
        rotating_frame_realization = payload.get("variational_result", {}).get("rotating_frame_realization")
        if chosen_method == "variational" and isinstance(rotating_frame_realization, dict):
            payload["rotating_frame_realization"] = rotating_frame_realization
            classical_config["rotating_frame_realization"] = rotating_frame_realization
        payload["classical_state_result"] = _build_spin_only_classical_state_result(
            payload,
            chosen_method,
            classical_state,
        )

    thermodynamics = payload.get("thermodynamics")
    if isinstance(thermodynamics, dict) and thermodynamics.get("temperatures"):
        payload["thermodynamics_result"] = estimate_thermodynamics(
            payload,
            thermodynamics["temperatures"],
            sweeps=int(thermodynamics.get("sweeps", 100)),
            burn_in=int(thermodynamics.get("burn_in", 50)),
            seed=int(thermodynamics.get("seed", seed)),
            measurement_interval=int(thermodynamics.get("measurement_interval", 1)),
            field_direction=thermodynamics.get("field_direction"),
            high_temperature_entropy=float(thermodynamics.get("high_temperature_entropy", 0.0)),
            energy_infinite_temperature=thermodynamics.get("energy_infinite_temperature"),
            scan_order=str(thermodynamics.get("scan_order", "as_given")),
            reuse_configuration=bool(thermodynamics.get("reuse_configuration", True)),
        )
    return payload


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
    payload = run_classical_solver(payload, starts=args.starts, seed=args.seed)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
