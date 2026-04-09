#!/usr/bin/env python3
from fractions import Fraction

import numpy as np
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
    shape = tuple(int(value) for value in state["shape"])
    vectors = {}
    for item in state.get("local_rays", []):
        vectors[tuple(int(value) for value in item["cell"])] = _normalized_ray(_deserialize_vector(item["vector"]))
    local_dimension = len(next(iter(vectors.values())))
    array = np.zeros(shape + (local_dimension,), dtype=complex)
    for index in np.ndindex(shape):
        array[index] = vectors[index]
    return array


def _serialize_state_array(state_array):
    shape = list(state_array.shape[:3])
    rays = []
    for index in np.ndindex(tuple(shape)):
        rays.append({"cell": [int(value) for value in index], "vector": _serialize_vector(_normalized_ray(state_array[index]))})
    return {"shape": shape, "local_rays": rays}


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
    state = np.zeros(shape + (local_dimension,), dtype=complex)
    for index in np.ndindex(shape):
        vector = rng.normal(size=local_dimension) + 1.0j * rng.normal(size=local_dimension)
        state[index] = _unit_norm_ray(vector)
    return state


def _effective_local_matrix(model, state_array, cell_index):
    local_dimension = int(model["local_dimension"])
    matrix = np.zeros((local_dimension, local_dimension), dtype=complex)
    for bond in model.get("bond_tensors", []):
        tensor = _deserialize_tensor(bond["tensor"])
        R = tuple(int(value) for value in bond["R"])

        right_index = _mod_index(tuple(cell_index[axis] + R[axis] for axis in range(3)), state_array.shape[:3])
        z_right = state_array[right_index]
        matrix += np.einsum("abcd,c,d->ab", tensor, np.conjugate(z_right), z_right)

        left_index = _mod_index(tuple(cell_index[axis] - R[axis] for axis in range(3)), state_array.shape[:3])
        z_left = state_array[left_index]
        matrix += np.einsum("cdab,c,d->ab", tensor, np.conjugate(z_left), z_left)

    return 0.5 * (matrix + matrix.conjugate().T)


def _sweep(model, state_array):
    max_change = 0.0
    for cell_index in np.ndindex(state_array.shape[:3]):
        local_matrix = _effective_local_matrix(model, state_array, cell_index)
        eigenvalues, eigenvectors = np.linalg.eigh(local_matrix)
        new_vector = _normalized_ray(eigenvectors[:, int(np.argmin(eigenvalues))])
        max_change = max(max_change, float(np.linalg.norm(new_vector - state_array[cell_index])))
        state_array[cell_index] = new_vector
    return state_array, float(max_change)


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
    return float(np.real(energy))


def _single_q_state_array(reference_ray, generator, q_vector, shape):
    local_dimension = int(reference_ray.shape[0])
    state = np.zeros(tuple(shape) + (local_dimension,), dtype=complex)
    for cell_index in np.ndindex(tuple(shape)):
        state[cell_index] = _single_q_ray(reference_ray, generator, q_vector, cell_index)
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
    shape = tuple(int(value) for value in state_array.shape[:3])
    local_dimension = int(state_array.shape[3])
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
            matrix += phase * _projector_matrix(state_array[cell_index])
        matrix /= float(cell_count)
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
    residuals = []
    for cell_index in np.ndindex(state_array.shape[:3]):
        local_matrix = _effective_local_matrix(model, state_array, cell_index)
        vector = state_array[cell_index]
        lagrange_multiplier = complex(np.vdot(vector, local_matrix @ vector))
        residual = local_matrix @ vector - lagrange_multiplier * vector
        residual_norm = float(np.linalg.norm(residual))
        residuals.append(
            {
                "cell": [int(value) for value in cell_index],
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
    state_array = _state_array_from_serialized(state) if isinstance(state, dict) else state
    energy = 0.0 + 0.0j
    for cell_index in np.ndindex(state_array.shape[:3]):
        for bond in model.get("bond_tensors", []):
            tensor = _deserialize_tensor(bond["tensor"])
            R = tuple(int(value) for value in bond["R"])
            right_index = _mod_index(tuple(cell_index[axis] + R[axis] for axis in range(3)), state_array.shape[:3])
            energy += _bond_energy(tensor, state_array[cell_index], state_array[right_index])
    return float(np.real(energy) / float(np.prod(state_array.shape[:3])))


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
