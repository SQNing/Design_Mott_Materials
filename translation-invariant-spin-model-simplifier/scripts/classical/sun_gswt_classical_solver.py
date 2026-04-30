#!/usr/bin/env python3
from copy import deepcopy
from fractions import Fraction

import numpy as np
from classical.sunny_sun_classical_driver import run_sunny_sun_classical
from common.cpn_classical_state import resolve_cpn_classical_state_payload
from common.cpn_magnetic_supercell import (
    lift_cpn_state_between_cells,
    magnetic_supercell_candidate_from_projector,
    reshape_cpn_model_to_magnetic_supercell,
)
from common.pseudospin_orbital_conventions import resolve_pseudospin_orbital_conventions

try:
    from scipy.optimize import Bounds, minimize
except ModuleNotFoundError:  # pragma: no cover - exercised indirectly in tests
    Bounds = None
    minimize = None


def _complex_from_serialized(value):
    if isinstance(value, dict):
        return complex(float(value.get("real", 0.0)), float(value.get("imag", 0.0)))
    return complex(value)


def _serialize_complex(value):
    return {"real": float(np.real(value)), "imag": float(np.imag(value))}


def _deserialize_vector(serialized):
    return np.array([_complex_from_serialized(value) for value in serialized], dtype=complex)


def _serialize_vector(vector):
    return [_serialize_complex(value) for value in vector]


def _serialize_matrix(matrix):
    return [[_serialize_complex(value) for value in row] for row in matrix]


def _deserialize_matrix(serialized):
    return np.array(
        [[_complex_from_serialized(value) for value in row] for row in serialized],
        dtype=complex,
    )


def _deserialize_tensor(serialized):
    local_dimension = len(serialized)
    tensor = np.zeros((local_dimension, local_dimension, local_dimension, local_dimension), dtype=complex)
    for a in range(local_dimension):
        for b in range(local_dimension):
            for c in range(local_dimension):
                for d in range(local_dimension):
                    tensor[a, b, c, d] = _complex_from_serialized(serialized[a][b][c][d])
    return tensor


def _unit_norm_ray(vector):
    vector = np.array(vector, dtype=complex)
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-14:
        raise ValueError("local ray must not be the zero vector")
    return vector / norm


def _normalized_ray(vector):
    vector = _unit_norm_ray(vector)
    for value in vector:
        if abs(value) > 1e-12:
            phase = value / abs(value)
            vector = vector / phase
            break
    return vector


def _state_array_from_serialized(state):
    raw_shape = state.get("shape", state.get("supercell_shape"))
    if raw_shape is None:
        raise ValueError("local-ray state must provide shape or supercell_shape")
    shape = tuple(int(value) for value in raw_shape)
    vectors = {}
    max_site = 0
    for item in state.get("local_rays", []):
        cell = tuple(int(value) for value in item["cell"])
        site = int(item.get("site", 0))
        vectors[(cell, site)] = _normalized_ray(_deserialize_vector(item["vector"]))
        max_site = max(max_site, site)
    first_vector = next(iter(vectors.values()))
    local_dimension = len(first_vector)
    site_count = max_site + 1 if vectors else 1
    array = np.zeros(shape + (site_count, local_dimension), dtype=complex)
    for index in np.ndindex(shape):
        for site in range(site_count):
            key = (index, site)
            if key not in vectors:
                raise ValueError(f"missing local ray for cell {list(index)} site {site}")
            array[index + (site,)] = vectors[key]
    return array


def _serialize_state_array(state_array):
    site_aware = _with_explicit_site_axis(state_array)
    shape = list(site_aware.shape[:3])
    site_count = int(site_aware.shape[3])
    rays = []
    for index in np.ndindex(tuple(shape)):
        for site in range(site_count):
            entry = {
                "cell": [int(value) for value in index],
                "vector": _serialize_vector(_normalized_ray(site_aware[index + (site,)])),
            }
            if site_count > 1:
                entry["site"] = int(site)
            rays.append(entry)
    return {"shape": shape, "local_rays": rays}


def _with_explicit_site_axis(state_array):
    if state_array.ndim == 4:
        return np.expand_dims(state_array, axis=3)
    return state_array


def _reject_magnetic_supercell_energy_state(state):
    if not isinstance(state, dict):
        return
    resolved_state = resolve_cpn_classical_state_payload(state)
    magnetic_supercell_matrix = resolved_state.get("magnetic_supercell_matrix")
    if magnetic_supercell_matrix is None:
        ordering = resolved_state.get("ordering")
        if isinstance(ordering, dict):
            magnetic_supercell_matrix = ordering.get("magnetic_supercell_matrix")
    if magnetic_supercell_matrix is not None:
        raise ValueError(
            "sun-gswt classical energy does not yet support states encoded in a magnetic-supercell convention; "
            "use the Sunny backend energy until this state lifting is implemented"
        )


def _q_from_index(q_index, shape):
    return [float(q_index[axis]) / float(shape[axis]) for axis in range(3)]


def _projector_matrix(vector):
    return np.outer(vector, np.conjugate(vector))


def _fractional_phase(q_vector, R):
    return 2.0 * np.pi * sum(float(q_vector[axis]) * float(R[axis]) for axis in range(3))


def _state_shape_from_model(model, supercell_shape):
    if supercell_shape is not None:
        return tuple(int(value) for value in supercell_shape)
    return (1, 1, 1)


def _mod_index(index, shape):
    return tuple(int(index[axis]) % int(shape[axis]) for axis in range(3))


def _state_array_from_model(model, supercell_shape, seed):
    shape = _state_shape_from_model(model, supercell_shape)
    rng = np.random.default_rng(seed)
    local_dimension = int(model["local_dimension"])
    site_count = max(1, int(len(model.get("positions", [])) or model.get("magnetic_site_count", 1)))
    state = np.zeros(shape + (site_count, local_dimension), dtype=complex)
    for index in np.ndindex(shape):
        for site in range(site_count):
            vector = rng.normal(size=local_dimension) + 1.0j * rng.normal(size=local_dimension)
            state[index + (site,)] = _unit_norm_ray(vector)
    return state


def _effective_local_matrix(model, state_array, cell_index, site):
    local_dimension = int(model["local_dimension"])
    matrix = np.zeros((local_dimension, local_dimension), dtype=complex)
    state_array = _with_explicit_site_axis(state_array)
    for bond in model.get("bond_tensors", []):
        tensor = _deserialize_tensor(bond["tensor"])
        R = tuple(int(value) for value in bond["R"])
        source = int(bond.get("source", 0))
        target = int(bond.get("target", 0))

        if source == int(site):
            right_index = _mod_index(tuple(cell_index[axis] + R[axis] for axis in range(3)), state_array.shape[:3])
            z_right = state_array[right_index + (target,)]
            matrix += np.einsum("abcd,c,d->ab", tensor, np.conjugate(z_right), z_right)

        if target == int(site):
            left_index = _mod_index(tuple(cell_index[axis] - R[axis] for axis in range(3)), state_array.shape[:3])
            z_left = state_array[left_index + (source,)]
            matrix += np.einsum("cdab,c,d->ab", tensor, np.conjugate(z_left), z_left)

    for onsite in model.get("onsite_terms", []):
        onsite_site = int(onsite.get("site", 0))
        if onsite_site == int(site):
            matrix += _deserialize_matrix(onsite["matrix"])

    return 0.5 * (matrix + matrix.conjugate().T)


def _sweep(model, state_array):
    max_change = 0.0
    site_aware = _with_explicit_site_axis(state_array)
    for cell_index in np.ndindex(site_aware.shape[:3]):
        for site in range(site_aware.shape[3]):
            local_matrix = _effective_local_matrix(model, site_aware, cell_index, site)
            eigenvalues, eigenvectors = np.linalg.eigh(local_matrix)
            new_vector = _normalized_ray(eigenvectors[:, int(np.argmin(eigenvalues))])
            max_change = max(max_change, float(np.linalg.norm(new_vector - site_aware[cell_index + (site,)])))
            site_aware[cell_index + (site,)] = new_vector
    return site_aware, float(max_change)


def _bond_energy(tensor, left_vector, right_vector):
    return complex(np.einsum("abcd,a,b,c,d", tensor, np.conjugate(left_vector), left_vector, np.conjugate(right_vector), right_vector))


def _active_axes(model):
    active = []
    for axis in range(3):
        if any(int(bond["R"][axis]) != 0 for bond in model.get("bond_tensors", [])):
            active.append(axis)
    return active or [0]


def _generator_param_count(local_dimension):
    return int(local_dimension * local_dimension - 1)


def _ray_from_params(params, local_dimension):
    vector = np.array(params[:local_dimension], dtype=float) + 1.0j * np.array(
        params[local_dimension : 2 * local_dimension],
        dtype=float,
    )
    return _unit_norm_ray(vector)


def _generator_from_params(params, local_dimension):
    matrix = np.zeros((local_dimension, local_dimension), dtype=complex)
    diagonal_count = max(0, local_dimension - 1)
    cursor = 0
    diagonal = [float(value) for value in params[cursor : cursor + diagonal_count]]
    cursor += diagonal_count
    if local_dimension > 0:
        diagonal.append(-sum(diagonal))
    for index, value in enumerate(diagonal):
        matrix[index, index] = float(value)
    for row in range(local_dimension):
        for col in range(row + 1, local_dimension):
            real_part = float(params[cursor])
            imag_part = float(params[cursor + 1])
            cursor += 2
            matrix[row, col] = real_part + 1.0j * imag_part
            matrix[col, row] = real_part - 1.0j * imag_part
    eigenvalues = np.linalg.eigvalsh(matrix)
    if eigenvalues.size == 0:
        return np.zeros_like(matrix)
    spectral_span = float(np.max(eigenvalues) - np.min(eigenvalues))
    if spectral_span <= 1e-12:
        return np.zeros_like(matrix)
    return matrix / spectral_span


def _single_q_unitary(generator, phase):
    if np.linalg.norm(generator) <= 1e-14:
        return np.eye(generator.shape[0], dtype=complex)
    eigenvalues, eigenvectors = np.linalg.eigh(generator)
    phases = np.exp(1.0j * float(phase) * eigenvalues)
    return eigenvectors @ np.diag(phases) @ eigenvectors.conjugate().T


def _single_q_ray(reference_ray, generator, q_vector, R):
    phase = _fractional_phase(q_vector, R)
    return _unit_norm_ray(_single_q_unitary(generator, phase) @ reference_ray)


def _single_q_energy(model, q_vector, reference_ray, generator):
    energy = 0.0 + 0.0j
    for bond in model.get("bond_tensors", []):
        tensor = _deserialize_tensor(bond["tensor"])
        right_vector = _single_q_ray(reference_ray, generator, q_vector, bond["R"])
        energy += _bond_energy(tensor, reference_ray, right_vector)
    onsite_terms = model.get("onsite_terms", [])
    if onsite_terms:
        shape = _supercell_shape_from_q(model, q_vector)
        onsite_energy = 0.0 + 0.0j
        for cell_index in np.ndindex(shape):
            vector = _single_q_ray(reference_ray, generator, q_vector, cell_index)
            for onsite in onsite_terms:
                site = int(onsite.get("site", 0))
                if site != 0:
                    raise ValueError("sun-gswt single-q solver currently supports only onsite terms on site 0")
                onsite_matrix = _deserialize_matrix(onsite["matrix"])
                onsite_energy += complex(np.vdot(vector, onsite_matrix @ vector))
        energy += onsite_energy / float(np.prod(shape))
    return float(np.real(energy))


def _single_q_state_array(reference_ray, generator, q_vector, shape):
    local_dimension = int(reference_ray.shape[0])
    state = np.zeros(tuple(shape) + (1, local_dimension), dtype=complex)
    for cell_index in np.ndindex(tuple(shape)):
        state[cell_index + (0,)] = _single_q_ray(reference_ray, generator, q_vector, cell_index)
    return state


def _supercell_shape_from_q(model, q_vector, *, max_denominator=16, max_total_cells=256):
    active_axes = set(_active_axes(model))
    shape = []
    for axis, value in enumerate(q_vector):
        if axis not in active_axes:
            shape.append(1)
            continue
        fraction = Fraction(float(value)).limit_denominator(int(max_denominator))
        shape.append(int(fraction.denominator) if fraction.numerator != 0 else 1)
    while int(np.prod(shape)) > int(max_total_cells):
        axis = int(np.argmax(shape))
        if shape[axis] <= 1:
            break
        shape[axis] = max(1, int(np.ceil(float(shape[axis]) / 2.0)))
    return tuple(max(1, int(value)) for value in shape)


def _serialize_single_q_generator(matrix):
    return _serialize_matrix(matrix)


def _single_q_active_axis_count(model):
    return len(_active_axes(model))


def _single_q_q_vector_from_reduced(model, reduced_q):
    q_vector = [0.0, 0.0, 0.0]
    for offset, axis in enumerate(_active_axes(model)):
        q_vector[axis] = float(reduced_q[offset])
    return q_vector


def _split_single_q_joint_vector(model, vector):
    q_count = _single_q_active_axis_count(model)
    reduced_q = np.array(vector[:q_count], dtype=float)
    q_vector = _single_q_q_vector_from_reduced(model, reduced_q)
    params = np.array(vector[q_count:], dtype=float)
    return q_vector, params


def _single_q_objective_from_params(model, q_vector, params):
    local_dimension = int(model["local_dimension"])
    try:
        reference_ray = _ray_from_params(params, local_dimension)
    except ValueError:
        return 1.0e6 + float(np.linalg.norm(params) ** 2)
    generator = _generator_from_params(params[2 * local_dimension :], local_dimension)
    return _single_q_energy(model, q_vector, reference_ray, generator)


def _random_single_q_params(local_dimension, rng):
    ray_real = rng.normal(size=local_dimension)
    ray_imag = rng.normal(size=local_dimension)
    generator_params = rng.normal(size=_generator_param_count(local_dimension))
    return np.concatenate([ray_real, ray_imag, generator_params]).astype(float)


def _unwrap_q_vector_for_storage(q_vector):
    return [float(value) % 1.0 for value in q_vector]


def _joint_single_q_objective(model, vector):
    q_vector, params = _split_single_q_joint_vector(model, vector)
    return _single_q_objective_from_params(model, q_vector, params)


def _single_q_bounds_for_model(model):
    if Bounds is None:
        return None
    local_dimension = int(model["local_dimension"])
    q_bound = 0.5
    ray_bound = 2.0
    generator_bound = np.pi
    q_count = _single_q_active_axis_count(model)
    lower = (
        [-q_bound] * q_count
        + [-ray_bound] * (2 * local_dimension)
        + [-generator_bound] * _generator_param_count(local_dimension)
    )
    upper = (
        [q_bound] * q_count
        + [ray_bound] * (2 * local_dimension)
        + [generator_bound] * _generator_param_count(local_dimension)
    )
    return Bounds(np.array(lower, dtype=float), np.array(upper, dtype=float))


def _random_single_q_joint_guess(model, rng):
    local_dimension = int(model["local_dimension"])
    q_vector = rng.uniform(low=-0.5, high=0.5, size=_single_q_active_axis_count(model))
    return np.concatenate([q_vector, _random_single_q_params(local_dimension, rng)]).astype(float)


def _optimize_single_q_joint_state(model, *, starts, seed, maxiter=200):
    local_dimension = int(model["local_dimension"])
    rng = np.random.default_rng(seed)
    bounds = _single_q_bounds_for_model(model)
    best = None

    for _ in range(int(starts)):
        guess = _random_single_q_joint_guess(model, rng)
        if minimize is None:
            value = float(_joint_single_q_objective(model, guess))
            vector = np.array(guess, dtype=float)
            status = {
                "success": True,
                "nit": 0,
                "nfev": 1,
                "method": "random-sampling-fallback",
                "optimality": None,
                "constr_violation": None,
            }
        else:
            result = minimize(
                lambda x: _joint_single_q_objective(model, x),
                guess,
                method="L-BFGS-B",
                bounds=bounds,
                options={
                    "maxiter": int(maxiter),
                    "ftol": 1e-12,
                    "gtol": 1e-8,
                    "maxls": 40,
                },
            )
            value = float(result.fun)
            vector = np.array(result.x, dtype=float)
            status = {
                "success": bool(result.success),
                "nit": int(getattr(result, "nit", 0)),
                "nfev": int(getattr(result, "nfev", 0)),
                "method": "L-BFGS-B",
                "optimality": None if getattr(result, "jac", None) is None else float(np.linalg.norm(np.ravel(result.jac), ord=np.inf)),
                "constr_violation": 0.0,
            }
        if best is None or value < best["value"]:
            best = {"value": value, "vector": vector, "status": status}

    vector = np.array(best["vector"], dtype=float)
    q_vector_raw, params = _split_single_q_joint_vector(model, vector)
    q_vector = _unwrap_q_vector_for_storage(q_vector_raw)
    reference_ray = _ray_from_params(params, local_dimension)
    generator = _generator_from_params(params[2 * local_dimension :], local_dimension)
    return {
        "energy": float(best["value"]),
        "q_vector": q_vector,
        "reference_ray": reference_ray,
        "generator": generator,
        "params": params,
        "optimizer": best["status"],
    }


def _projector_fourier_components(state_array):
    site_aware = _with_explicit_site_axis(state_array)
    shape = tuple(int(value) for value in site_aware.shape[:3])
    site_count = int(site_aware.shape[3])
    local_dimension = int(site_aware.shape[4])
    cell_count = int(np.prod(shape))
    components = []
    zero_q = (0.0, 0.0, 0.0)
    uniform_weight = 0.0
    dominant_ordering_q = None
    dominant_ordering_weight = -1.0

    for q_index in np.ndindex(shape):
        q = _q_from_index(q_index, shape)
        matrix = np.zeros((local_dimension, local_dimension), dtype=complex)
        for cell_index in np.ndindex(shape):
            phase = np.exp(
                -2.0j
                * np.pi
                * sum(float(q[axis]) * float(cell_index[axis]) for axis in range(3))
            )
            for site in range(site_count):
                matrix += phase * _projector_matrix(site_aware[cell_index + (site,)])
        matrix /= float(cell_count * site_count)
        weight = float(np.real(np.sum(np.abs(matrix) ** 2)))
        is_zero_q = all(abs(value) <= 1e-12 for value in q)
        if is_zero_q:
            uniform_weight = weight
        elif weight > dominant_ordering_weight + 1e-14:
            dominant_ordering_q = list(q)
            dominant_ordering_weight = weight
        components.append(
            {
                "q": list(q),
                "matrix": _serialize_matrix(matrix),
                "weight": weight,
                "is_zero_q": bool(is_zero_q),
            }
        )

    ordering_kind = "uniform"
    if dominant_ordering_weight > 1e-10:
        ordering_kind = "commensurate-supercell"

    return {
        "grid_shape": list(shape),
        "components": components,
        "uniform_q_weight": float(uniform_weight),
        "dominant_ordering_q": dominant_ordering_q,
        "dominant_ordering_weight": float(max(0.0, dominant_ordering_weight)),
        "ordering_kind": ordering_kind,
    }


def _stationarity_summary(model, state_array):
    site_aware = _with_explicit_site_axis(state_array)
    residuals = []
    for cell_index in np.ndindex(site_aware.shape[:3]):
        for site in range(site_aware.shape[3]):
            local_matrix = _effective_local_matrix(model, site_aware, cell_index, site)
            vector = site_aware[cell_index + (site,)]
            lagrange_multiplier = complex(np.vdot(vector, local_matrix @ vector))
            residual = local_matrix @ vector - lagrange_multiplier * vector
            residual_norm = float(np.linalg.norm(residual))
            residuals.append(
                {
                    "cell": [int(value) for value in cell_index],
                    "site": int(site),
                    "lagrange_multiplier": _serialize_complex(lagrange_multiplier),
                    "residual_norm": residual_norm,
                    "residual_vector": _serialize_vector(residual),
                }
            )

    norms = [item["residual_norm"] for item in residuals]
    return {
        "residual_definition": "r_i = M_i[Q] z_i - (z_i^dagger M_i[Q] z_i) z_i, measured in Euclidean norm",
        "max_residual_norm": float(max(norms) if norms else 0.0),
        "mean_residual_norm": float(sum(norms) / len(norms) if norms else 0.0),
        "sites": residuals,
    }


def _canonical_classical_state(state_array, conventions, diagnostics, *, ordering=None):
    serialized_state = _serialize_state_array(state_array)
    projector = diagnostics.get("projector_diagnostics", {}) if isinstance(diagnostics, dict) else {}
    state = {
        "schema_version": 1,
        "state_kind": "local_rays",
        "manifold": "CP^(N-1)",
        "basis_order": conventions["basis_order"],
        "pair_basis_order": conventions["pair_basis_order"],
        "supercell_shape": list(serialized_state["shape"]),
        "local_rays": serialized_state["local_rays"],
    }

    ordering_payload = {}
    if isinstance(ordering, dict):
        ordering_payload.update(ordering)
    if isinstance(projector, dict):
        if projector.get("ordering_kind") is not None:
            ordering_payload.setdefault("kind", projector.get("ordering_kind"))
        if projector.get("dominant_ordering_q") is not None:
            ordering_payload.setdefault("dominant_projector_q", projector.get("dominant_ordering_q"))
        if projector.get("dominant_ordering_weight") is not None:
            ordering_payload.setdefault("dominant_projector_weight", projector.get("dominant_ordering_weight"))
        if projector.get("uniform_q_weight") is not None:
            ordering_payload.setdefault("uniform_projector_q_weight", projector.get("uniform_q_weight"))
    if ordering_payload:
        ordering_payload.setdefault("supercell_shape", list(serialized_state["shape"]))
        state["ordering"] = ordering_payload
    return state


def diagnose_sun_gswt_classical_state(model, state):
    if model.get("classical_manifold") != "CP^(N-1)":
        raise ValueError("sun-gswt classical diagnostics expect a CP^(N-1) classical payload")
    conventions = resolve_pseudospin_orbital_conventions(model)
    state_array = _state_array_from_serialized(state) if isinstance(state, dict) else state
    return {
        "basis_order": conventions["basis_order"],
        "pair_basis_order": conventions["pair_basis_order"],
        "projector_diagnostics": _projector_fourier_components(state_array),
        "stationarity": _stationarity_summary(model, state_array),
    }


def evaluate_sun_gswt_classical_energy(model, state):
    if model.get("classical_manifold") != "CP^(N-1)":
        raise ValueError("sun-gswt classical energy expects a CP^(N-1) classical payload")
    resolve_pseudospin_orbital_conventions(model)
    _reject_magnetic_supercell_energy_state(state)
    state_array = _state_array_from_serialized(state) if isinstance(state, dict) else state
    site_aware = _with_explicit_site_axis(state_array)
    energy = 0.0 + 0.0j
    for cell_index in np.ndindex(site_aware.shape[:3]):
        for bond in model.get("bond_tensors", []):
            tensor = _deserialize_tensor(bond["tensor"])
            R = tuple(int(value) for value in bond["R"])
            source = int(bond.get("source", 0))
            target = int(bond.get("target", 0))
            right_index = _mod_index(tuple(cell_index[axis] + R[axis] for axis in range(3)), site_aware.shape[:3])
            energy += _bond_energy(
                tensor,
                site_aware[cell_index + (source,)],
                site_aware[right_index + (target,)],
            )
        for onsite in model.get("onsite_terms", []):
            onsite_matrix = _deserialize_matrix(onsite["matrix"])
            site = int(onsite.get("site", 0))
            vector = site_aware[cell_index + (site,)]
            energy += complex(np.vdot(vector, onsite_matrix @ vector))
    return float(np.real(energy) / float(np.prod(site_aware.shape[:3])))


def solve_sun_gswt_classical_ground_state(
    model,
    *,
    supercell_shape=None,
    starts=8,
    seed=0,
    max_sweeps=200,
    sweep_tolerance=1e-10,
):
    if model.get("classical_manifold") != "CP^(N-1)":
        raise ValueError("sun-gswt classical solver expects a CP^(N-1) classical payload")
    conventions = resolve_pseudospin_orbital_conventions(model)

    starts = max(1, int(starts))
    best_energy = None
    best_state = None
    best_change = None

    for start_index in range(starts):
        state_array = _state_array_from_model(model, supercell_shape, seed + start_index)
        last_change = None
        for _ in range(int(max_sweeps)):
            state_array, last_change = _sweep(model, state_array)
            if last_change <= sweep_tolerance:
                break
        energy = evaluate_sun_gswt_classical_energy(model, state_array)
        if best_energy is None or energy < best_energy:
            best_energy = energy
            best_state = np.array(state_array, copy=True)
            best_change = float(last_change if last_change is not None else 0.0)

    diagnostics = diagnose_sun_gswt_classical_state(model, best_state)
    classical_state = _canonical_classical_state(best_state, conventions, diagnostics)
    return {
        "method": "sun-gswt-classical-variational",
        "manifold": "CP^(N-1)",
        "basis_order": conventions["basis_order"],
        "pair_basis_order": conventions["pair_basis_order"],
        "manifold_scope": "full-CP^(N-1)",
        "reference_state_kind": "local_rays",
        "energy": float(best_energy),
        "supercell_shape": list(best_state.shape[:3]),
        "local_rays": list(classical_state["local_rays"]),
        "classical_state": classical_state,
        "projector_diagnostics": diagnostics["projector_diagnostics"],
        "stationarity": diagnostics["stationarity"],
        "convergence": {
            "last_sweep_change": float(best_change),
            "sweep_tolerance": float(sweep_tolerance),
        },
        "starts": int(starts),
        "seed": int(seed),
    }


def solve_sun_gswt_single_q_ground_state(
    model,
    *,
    starts=8,
    seed=0,
    maxiter=200,
):
    if model.get("classical_manifold") != "CP^(N-1)":
        raise ValueError("sun-gswt single-q solver expects a CP^(N-1) classical payload")
    conventions = resolve_pseudospin_orbital_conventions(model)

    starts = max(1, int(starts))
    refined = _optimize_single_q_joint_state(
        model,
        starts=starts,
        seed=seed,
        maxiter=maxiter,
    )
    shape = _supercell_shape_from_q(model, refined["q_vector"])
    state_array = _single_q_state_array(refined["reference_ray"], refined["generator"], refined["q_vector"], shape)
    diagnostics = diagnose_sun_gswt_classical_state(model, state_array)
    classical_state = _canonical_classical_state(
        state_array,
        conventions,
        diagnostics,
        ordering={
            "ansatz": "single-q-unitary-ray",
            "q_vector": list(refined["q_vector"]),
            "supercell_shape": list(shape),
        },
    )
    return {
        "method": "sun-gswt-classical-single-q",
        "ansatz": "single-q-unitary-ray",
        "manifold": "CP^(N-1)",
        "basis_order": conventions["basis_order"],
        "pair_basis_order": conventions["pair_basis_order"],
        "manifold_scope": "restricted-single-q-ansatz",
        "reference_state_kind": "local_rays",
        "energy": float(refined["energy"]),
        "q_vector": list(refined["q_vector"]),
        "reference_ray": _serialize_vector(refined["reference_ray"]),
        "generator_matrix": _serialize_single_q_generator(refined["generator"]),
        "supercell_shape": list(shape),
        "local_rays": list(classical_state["local_rays"]),
        "classical_state": classical_state,
        "projector_diagnostics": diagnostics["projector_diagnostics"],
        "stationarity": diagnostics["stationarity"],
        "ansatz_stationarity": {
            "best_objective": float(refined["energy"]),
            "optimizer_success": bool(refined["optimizer"].get("success", True)),
            "optimizer_method": str(refined["optimizer"].get("method", "unknown")),
            "optimization_mode": "direct-joint",
            "optimizer_nit": int(refined["optimizer"].get("nit", 0)),
            "optimizer_nfev": int(refined["optimizer"].get("nfev", 0)),
            "optimizer_optimality": refined["optimizer"].get("optimality"),
            "optimizer_constraint_violation": refined["optimizer"].get("constr_violation"),
            "objective_definition": "direct minimization of the single-q unitary-ray classical energy over q, z0, and a traceless Hermitian generator",
            "q_parameterization": "direct reduced-coordinate variables on active bond axes only, bounded to [-1/2, 1/2] before storage modulo reciprocal lattice vectors",
            "generator_normalization": "traceless Hermitian generator scaled to unit spectral span when nonzero",
            "active_q_axes": list(_active_axes(model)),
        },
        "starts": int(starts),
        "seed": int(seed),
    }


def _is_zero_q_vector(q_vector, *, tolerance=1e-10):
    return all(abs(float(value)) <= tolerance for value in q_vector)


def _ranked_nonzero_projector_components(projector_summary):
    projector_summary = projector_summary if isinstance(projector_summary, dict) else {}
    top_components = projector_summary.get("top_components")
    if isinstance(top_components, list) and top_components:
        components = top_components
    else:
        components = projector_summary.get("components", [])

    ranked = []
    for component in components:
        if not isinstance(component, dict):
            continue
        q_vector = list(component.get("q", []))
        if len(q_vector) != 3 or _is_zero_q_vector(q_vector):
            continue
        ranked.append(
            {
                "q": [float(value) for value in q_vector],
                "weight": float(component.get("weight", 0.0)),
            }
        )
    ranked.sort(key=lambda item: (-item["weight"], item["q"]))
    return ranked


def _candidate_matrix_key(matrix):
    return tuple(tuple(int(value) for value in row) for row in matrix)


def build_cpn_magnetic_supercell_refinement_candidates(
    model,
    classical_result,
    *,
    max_candidates=4,
    max_denominator=16,
):
    del model
    projector = classical_result.get("projector_diagnostics", {}) if isinstance(classical_result, dict) else {}
    components = _ranked_nonzero_projector_components(projector)
    candidate_entries = []
    seen_matrices = set()
    first_failure = None

    for component in components:
        candidate = magnetic_supercell_candidate_from_projector(
            {"top_components": [{"q": list(component["q"]), "weight": float(component["weight"])}]},
            max_denominator=max_denominator,
        )
        if candidate.get("status") != "ok":
            if first_failure is None:
                first_failure = candidate
            continue
        matrix_key = _candidate_matrix_key(candidate.get("matrix", []))
        if matrix_key in seen_matrices:
            continue
        seen_matrices.add(matrix_key)
        candidate_entries.append(
            {
                "candidate": candidate,
                "trigger_q": list(candidate.get("selected_q", [])),
                "projector_weight": float(component["weight"]),
            }
        )
        if len(candidate_entries) >= max(1, int(max_candidates)):
            break

    if not candidate_entries:
        failure = first_failure or {
            "status": "no_nonzero_component",
            "selected_q": None,
            "matrix": None,
            "determinant": 0,
        }
        return {
            "status": "no_candidate",
            "reason": failure.get("status", "missing-projector-candidate"),
            "candidate": failure,
            "candidates": [],
        }

    return {
        "status": "candidates",
        "candidates": candidate_entries,
    }


def build_cpn_magnetic_supercell_refinement_candidate(model, classical_result):
    branch = build_cpn_magnetic_supercell_refinement_candidates(
        model,
        classical_result,
        max_candidates=1,
    )
    if branch.get("status") != "candidates":
        return {
            "status": "no_candidate",
            "reason": branch.get("reason", branch.get("status")),
            "candidate": branch.get("candidate"),
        }
    candidate_entry = branch["candidates"][0]
    candidate = candidate_entry["candidate"]
    return {
        "status": "candidate",
        "candidate": candidate,
        "trigger_q": list(candidate.get("selected_q", [])),
        "chemical_site_count": int(len(model.get("positions", []))),
    }


def choose_refined_classical_branch(
    *,
    original_energy,
    original_site_count=1,
    refined_python_energy=None,
    refined_sunny_energy=None,
    refined_site_count=1,
    refined_state=None,
    refined_python_state=None,
    refined_sunny_state=None,
    energy_gain_tolerance=1e-6,
):
    original_site_count = max(1, int(original_site_count))
    refined_site_count = max(1, int(refined_site_count))
    original_energy_per_site = float(original_energy) / float(original_site_count)
    energy_candidates = []
    if refined_python_energy is not None:
        energy_candidates.append(("python", float(refined_python_energy) / float(refined_site_count)))
    if refined_sunny_energy is not None:
        energy_candidates.append(("sunny", float(refined_sunny_energy) / float(refined_site_count)))

    if not energy_candidates:
        return {
            "accepted": False,
            "reason": "no-refined-energy",
            "energy_before": float(original_energy),
            "energy_before_per_site": float(original_energy_per_site),
            "energy_after_python": None,
            "energy_after_python_per_site": None,
            "energy_after_sunny": None,
            "energy_after_sunny_per_site": None,
            "energy_gain": None,
            "energy_gain_per_site": None,
            "selected_backend": None,
            "acceptance_backend": None,
            "selected_energy_per_site": None,
            "selected_classical_state": None,
        }

    selected_backend, selected_energy_per_site = min(energy_candidates, key=lambda item: item[1])
    energy_gain_per_site = float(original_energy_per_site) - float(selected_energy_per_site)
    accepted = energy_gain_per_site > float(energy_gain_tolerance)
    if selected_backend == "sunny":
        selected_state = refined_sunny_state if refined_sunny_state is not None else refined_state
    else:
        selected_state = refined_python_state if refined_python_state is not None else refined_state
    return {
        "accepted": bool(accepted),
        "reason": "energy-improved" if accepted else "energy-gain-below-tolerance",
        "energy_before": float(original_energy),
        "energy_before_per_site": float(original_energy_per_site),
        "energy_after_python": None if refined_python_energy is None else float(refined_python_energy),
        "energy_after_python_per_site": (
            None if refined_python_energy is None else float(refined_python_energy) / float(refined_site_count)
        ),
        "energy_after_sunny": None if refined_sunny_energy is None else float(refined_sunny_energy),
        "energy_after_sunny_per_site": (
            None if refined_sunny_energy is None else float(refined_sunny_energy) / float(refined_site_count)
        ),
        "energy_gain": None if refined_python_energy is None and refined_sunny_energy is None else (
            float(original_energy) - (
                float(refined_python_energy)
                if selected_backend == "python"
                else float(refined_sunny_energy)
            )
        ),
        "energy_gain_per_site": float(energy_gain_per_site),
        "selected_backend": str(selected_backend),
        "acceptance_backend": str(selected_backend) if accepted else None,
        "selected_energy_per_site": float(selected_energy_per_site),
        "selected_classical_state": selected_state if accepted else None,
    }


def _run_sunny_cpn_refinement_verification(
    reshaped_model,
    *,
    lifted_state,
    starts,
    seed,
):
    payload = {
        "backend": "Sunny.jl",
        "payload_kind": "sunny_sun_classical",
        "model": reshaped_model,
        "supercell_shape": [int(value) for value in lifted_state.get("supercell_shape", [])],
        "initial_local_rays": list(lifted_state.get("local_rays", [])),
        "starts": int(starts),
        "seed": int(seed),
    }
    backend_result = run_sunny_sun_classical(payload)
    if backend_result.get("status") != "ok":
        return None
    resolved_state = resolve_cpn_classical_state_payload(
        backend_result,
        default_supercell_shape=lifted_state.get("supercell_shape"),
    )
    return {
        **backend_result,
        "supercell_shape": list(
            resolved_state.get("supercell_shape", backend_result.get("supercell_shape", lifted_state.get("supercell_shape", [])))
        ),
        "local_rays": list(resolved_state.get("local_rays", backend_result.get("local_rays", []))),
        "classical_state": resolved_state,
    }


def _run_single_cpn_magnetic_supercell_refinement_candidate(
    model,
    *,
    source_state,
    original_energy,
    original_site_count,
    candidate_entry,
    starts,
    seed,
    max_sweeps,
    sweep_tolerance,
    energy_gain_tolerance,
    verify_with_sunny=False,
):
    candidate = dict(candidate_entry.get("candidate", {}))
    reshaped_model = reshape_cpn_model_to_magnetic_supercell(model, candidate["matrix"])
    lifting_mapping = dict(reshaped_model["magnetic_supercell_mapping"])
    if source_state.get("supercell_shape") is not None:
        lifting_mapping["chemical_supercell_shape"] = [
            int(value) for value in source_state["supercell_shape"]
        ]
    lifted_state = lift_cpn_state_between_cells(
        source_state,
        lifting_mapping,
        direction="chemical_to_magnetic",
    )
    refined_python = solve_sun_gswt_classical_ground_state(
        reshaped_model,
        supercell_shape=lifted_state.get("supercell_shape"),
        starts=starts,
        seed=seed,
        max_sweeps=max_sweeps,
        sweep_tolerance=sweep_tolerance,
    )
    refined_site_count = max(
        1,
        int(len(reshaped_model.get("positions", [])) or reshaped_model.get("magnetic_site_count", 1)),
    )
    refined_sunny = (
        _run_sunny_cpn_refinement_verification(
            reshaped_model,
            lifted_state=lifted_state,
            starts=starts,
            seed=seed,
        )
        if verify_with_sunny
        else None
    )
    decision = choose_refined_classical_branch(
        original_energy=float(original_energy),
        original_site_count=int(original_site_count),
        refined_python_energy=refined_python.get("energy"),
        refined_sunny_energy=refined_sunny.get("energy") if isinstance(refined_sunny, dict) else None,
        refined_site_count=refined_site_count,
        refined_state=resolve_cpn_classical_state_payload(refined_python),
        refined_python_state=resolve_cpn_classical_state_payload(refined_python),
        refined_sunny_state=(
            resolve_cpn_classical_state_payload(
                refined_sunny,
                default_supercell_shape=lifted_state.get("supercell_shape"),
            )
            if isinstance(refined_sunny, dict)
            else None
        ),
        energy_gain_tolerance=energy_gain_tolerance,
    )
    lifted_energy = evaluate_sun_gswt_classical_energy(reshaped_model, lifted_state)
    summary = {
        "trigger_q": list(candidate.get("selected_q", [])),
        "projector_weight": candidate_entry.get("projector_weight"),
        "candidate_matrix": deepcopy(candidate.get("matrix")),
        "candidate_determinant": candidate.get("determinant"),
        "lifted_supercell_shape": list(lifted_state.get("supercell_shape", [])),
        "lifted_initial_energy": float(lifted_energy),
        "lifted_initial_energy_per_site": float(lifted_energy) / float(refined_site_count),
        "refined_site_count": int(refined_site_count),
        "accepted": bool(decision.get("accepted", False)),
        "reason": decision.get("reason"),
        "energy_after_python": decision.get("energy_after_python"),
        "energy_after_python_per_site": decision.get("energy_after_python_per_site"),
        "energy_after_sunny": decision.get("energy_after_sunny"),
        "energy_after_sunny_per_site": decision.get("energy_after_sunny_per_site"),
        "energy_gain_per_site": decision.get("energy_gain_per_site"),
        "acceptance_backend": decision.get("acceptance_backend"),
        "selected_backend": decision.get("selected_backend"),
    }
    return {
        "candidate": candidate,
        "reshaped_model": reshaped_model,
        "lifted_initial_state": lifted_state,
        "refined_python_result": refined_python,
        "refined_sunny_result": refined_sunny,
        "decision": decision,
        "summary": summary,
    }


def run_cpn_magnetic_supercell_refinement(
    model,
    *,
    classical_result,
    starts=8,
    seed=0,
    max_sweeps=200,
    sweep_tolerance=1e-10,
    energy_gain_tolerance=1e-6,
    max_candidate_components=4,
    max_denominator=16,
    verify_with_sunny=False,
):
    branch = build_cpn_magnetic_supercell_refinement_candidates(
        model,
        classical_result,
        max_candidates=max_candidate_components,
        max_denominator=max_denominator,
    )
    diagnostics = {
        "status": None,
        "trigger_q": None,
        "candidate_matrix": None,
        "candidates": [],
        "accepted": False,
        "max_candidate_components": int(max_candidate_components),
        "max_denominator": int(max_denominator),
        "original_site_count": int(len(model.get("positions", [])) or 1),
        "refined_site_count": None,
        "energy_before": classical_result.get("energy") if isinstance(classical_result, dict) else None,
        "energy_before_per_site": None,
        "energy_after_python": None,
        "energy_after_python_per_site": None,
        "energy_after_sunny": None,
        "energy_after_sunny_per_site": None,
        "energy_gain_per_site": None,
        "acceptance_backend": None,
        "selected_backend": None,
    }
    if diagnostics["energy_before"] is not None:
        diagnostics["energy_before_per_site"] = float(diagnostics["energy_before"]) / float(diagnostics["original_site_count"])
    if branch.get("status") != "candidates":
        diagnostics["status"] = branch.get("status")
        return {
            "status": branch.get("status"),
            "candidate": branch.get("candidate"),
            "decision": {
                "accepted": False,
                "reason": branch.get("reason", branch.get("status")),
                "selected_classical_state": None,
            },
            "magnetic_supercell_refinement": diagnostics,
        }

    source_state = resolve_cpn_classical_state_payload(classical_result)
    candidate_results = []
    for candidate_entry in branch.get("candidates", []):
        result = _run_single_cpn_magnetic_supercell_refinement_candidate(
            model,
            source_state=source_state,
            original_energy=float(classical_result.get("energy")),
            original_site_count=diagnostics["original_site_count"],
            candidate_entry=candidate_entry,
            starts=starts,
            seed=seed,
            max_sweeps=max_sweeps,
            sweep_tolerance=sweep_tolerance,
            energy_gain_tolerance=energy_gain_tolerance,
            verify_with_sunny=verify_with_sunny,
        )
        candidate_results.append(result)

    diagnostics["status"] = "candidate"
    diagnostics["candidates"] = [deepcopy(result["summary"]) for result in candidate_results]

    accepted_results = [result for result in candidate_results if result["decision"].get("accepted", False)]
    if accepted_results:
        selected_result = min(
            accepted_results,
            key=lambda result: float(result["decision"].get("selected_energy_per_site")),
        )
    else:
        selected_result = min(
            candidate_results,
            key=lambda result: float(result["decision"].get("selected_energy_per_site")),
        )

    candidate = selected_result["candidate"]
    decision = selected_result["decision"]
    reshaped_model = selected_result["reshaped_model"]
    lifted_state = selected_result["lifted_initial_state"]
    refined_python = selected_result["refined_python_result"]
    diagnostics.update(
        {
            "trigger_q": list(candidate.get("selected_q", [])),
            "candidate_matrix": deepcopy(candidate.get("matrix")),
            "accepted": bool(decision.get("accepted", False)),
            "refined_site_count": int(selected_result["summary"]["refined_site_count"]),
            "energy_after_python": refined_python.get("energy"),
            "energy_after_python_per_site": decision.get("energy_after_python_per_site"),
            "energy_after_sunny": decision.get("energy_after_sunny"),
            "energy_after_sunny_per_site": decision.get("energy_after_sunny_per_site"),
            "energy_gain_per_site": decision.get("energy_gain_per_site"),
            "acceptance_backend": decision.get("acceptance_backend"),
            "selected_backend": decision.get("selected_backend"),
        }
    )
    return {
        "status": "candidate",
        "candidate": candidate,
        "reshaped_model": reshaped_model,
        "lifted_initial_state": lifted_state,
        "refined_python_result": refined_python,
        "refined_sunny_result": selected_result.get("refined_sunny_result"),
        "decision": decision,
        "magnetic_supercell_refinement": diagnostics,
    }
