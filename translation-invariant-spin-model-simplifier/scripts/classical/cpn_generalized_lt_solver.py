#!/usr/bin/env python3
import math

import numpy as np

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from classical.lt_brillouin_zone import generate_q_mesh
    from classical.cpn_glt_reconstruction import (
        reconstruct_commensurate_relaxed_shell,
        reconstruct_commensurate_single_q_texture,
    )
    from classical.cpn_glt_finalization import finalize_cpn_glt_result
    from classical.sun_gswt_classical_solver import diagnose_sun_gswt_classical_state
    from common.pseudospin_orbital_conventions import resolve_pseudospin_orbital_conventions
else:
    from .lt_brillouin_zone import generate_q_mesh
    from .cpn_glt_reconstruction import (
        reconstruct_commensurate_relaxed_shell,
        reconstruct_commensurate_single_q_texture,
    )
    from .cpn_glt_finalization import finalize_cpn_glt_result
    from .sun_gswt_classical_solver import diagnose_sun_gswt_classical_state
    from common.pseudospin_orbital_conventions import resolve_pseudospin_orbital_conventions


def _complex_from_serialized(value):
    if isinstance(value, dict):
        return complex(float(value.get("real", 0.0)), float(value.get("imag", 0.0)))
    return complex(value)


def _serialize_complex(value):
    return {"real": float(np.real(value)), "imag": float(np.imag(value))}


def _serialize_vector(vector):
    return [_serialize_complex(value) for value in vector]


def _deserialize_tensor(serialized):
    local_dimension = len(serialized)
    tensor = np.zeros((local_dimension, local_dimension, local_dimension, local_dimension), dtype=complex)
    for a in range(local_dimension):
        for b in range(local_dimension):
            for c in range(local_dimension):
                for d in range(local_dimension):
                    tensor[a, b, c, d] = _complex_from_serialized(serialized[a][b][c][d])
    return tensor


def _jacobi_real_symmetric_eigh(matrix, *, tolerance=1.0e-12, max_iterations=None):
    symmetric = np.array(matrix, dtype=float, copy=True)
    dimension = int(symmetric.shape[0])
    if dimension == 0:
        return np.zeros((0,), dtype=float), np.zeros((0, 0), dtype=float)

    vectors = np.eye(dimension, dtype=float)
    scale = max(1.0, float(np.linalg.norm(symmetric, ord=np.inf)))
    threshold = float(tolerance) * scale
    iteration_limit = int(max_iterations or max(32, 8 * dimension * dimension))

    for _ in range(iteration_limit):
        upper = np.triu(np.abs(symmetric), k=1)
        pivot = int(np.argmax(upper))
        p, q = divmod(pivot, dimension)
        if p >= q or upper[p, q] <= threshold:
            break

        app = float(symmetric[p, p])
        aqq = float(symmetric[q, q])
        apq = float(symmetric[p, q])
        if abs(apq) <= threshold:
            symmetric[p, q] = 0.0
            symmetric[q, p] = 0.0
            continue

        tau = (aqq - app) / (2.0 * apq)
        if abs(tau) <= 1.0e-30:
            tangent = 1.0
        else:
            tangent = math.copysign(1.0, tau) / (abs(tau) + math.sqrt(1.0 + tau * tau))
        cosine = 1.0 / math.sqrt(1.0 + tangent * tangent)
        sine = tangent * cosine

        for index in range(dimension):
            if index in {p, q}:
                continue
            aip = float(symmetric[index, p])
            aiq = float(symmetric[index, q])
            symmetric[index, p] = symmetric[p, index] = cosine * aip - sine * aiq
            symmetric[index, q] = symmetric[q, index] = sine * aip + cosine * aiq

        symmetric[p, p] = cosine * cosine * app - 2.0 * sine * cosine * apq + sine * sine * aqq
        symmetric[q, q] = sine * sine * app + 2.0 * sine * cosine * apq + cosine * cosine * aqq
        symmetric[p, q] = 0.0
        symmetric[q, p] = 0.0

        vector_p = vectors[:, p].copy()
        vector_q = vectors[:, q].copy()
        vectors[:, p] = cosine * vector_p - sine * vector_q
        vectors[:, q] = sine * vector_p + cosine * vector_q

    eigenvalues = np.diag(symmetric)
    order = np.argsort(eigenvalues)
    return np.array(eigenvalues[order], dtype=float), np.array(vectors[:, order], dtype=float)


def _stable_hermitian_eigh(matrix):
    array = np.array(matrix, copy=True)
    hermitian = 0.5 * (array + array.conjugate().T)
    real_symmetric = np.array(np.real(np.real_if_close(hermitian, tol=1000.0)), dtype=float)
    return _jacobi_real_symmetric_eigh(real_symmetric)


def _active_axes(model):
    active = []
    for axis in range(3):
        if any(int(bond["R"][axis]) != 0 for bond in model.get("bond_tensors", [])):
            active.append(axis)
    return active or [0]


def _magnetic_site_count(model):
    explicit = model.get("magnetic_site_count")
    if explicit is not None:
        return max(1, int(explicit))
    magnetic_sites = model.get("magnetic_sites", [])
    if magnetic_sites:
        return max(1, len(magnetic_sites))
    max_index = 0
    for bond in model.get("bond_tensors", []):
        max_index = max(max_index, int(bond.get("source", 0)), int(bond.get("target", 0)))
    return max_index + 1


def _default_mesh_shape(model, mesh_shape):
    if mesh_shape is not None:
        resolved = [max(1, int(value)) for value in mesh_shape]
        if len(resolved) != 3:
            raise ValueError("mesh_shape must have length 3")
        return tuple(resolved)

    active = set(_active_axes(model))
    resolved = []
    for axis in range(3):
        resolved.append(17 if axis in active else 1)
    return tuple(resolved)


def _fractional_phase(q_vector, R):
    return 2.0 * np.pi * sum(float(q_vector[axis]) * float(R[axis]) for axis in range(3))


def _normalize_fractional_component(component, *, tolerance=1.0e-12):
    value = float(component) % 1.0
    if abs(value) <= tolerance or abs(value - 1.0) <= tolerance:
        return 0.0
    return float(value)


def _normalized_q_vector(q_vector, *, tolerance=1.0e-12):
    return [_normalize_fractional_component(component, tolerance=tolerance) for component in q_vector]


def _is_zero_q_vector(q_vector, *, tolerance=1.0e-12):
    normalized = _normalized_q_vector(q_vector, tolerance=tolerance)
    return all(abs(float(component)) <= tolerance for component in normalized)


def _canonicalize_q_vector_under_inversion(q_vector, *, tolerance=1.0e-12, digits=12):
    positive = _normalized_q_vector(q_vector, tolerance=tolerance)
    negative = _normalized_q_vector([-float(component) for component in positive], tolerance=tolerance)
    rounded_positive = tuple(round(float(value), int(digits)) for value in positive)
    rounded_negative = tuple(round(float(value), int(digits)) for value in negative)
    chosen = rounded_positive if rounded_positive <= rounded_negative else rounded_negative
    return [float(value) for value in chosen]


def _q_sector_key(q_vector, *, tolerance=1.0e-12, digits=12):
    canonical = _canonicalize_q_vector_under_inversion(
        q_vector,
        tolerance=tolerance,
        digits=digits,
    )
    return tuple(round(float(value), int(digits)) for value in canonical)


def _orthonormal_hermitian_basis(local_dimension):
    basis = [np.eye(local_dimension, dtype=complex) / math.sqrt(float(local_dimension))]

    for row in range(local_dimension):
        for col in range(row + 1, local_dimension):
            symmetric = np.zeros((local_dimension, local_dimension), dtype=complex)
            symmetric[row, col] = 1.0 / math.sqrt(2.0)
            symmetric[col, row] = 1.0 / math.sqrt(2.0)
            basis.append(symmetric)

            antisymmetric = np.zeros((local_dimension, local_dimension), dtype=complex)
            antisymmetric[row, col] = -1.0j / math.sqrt(2.0)
            antisymmetric[col, row] = 1.0j / math.sqrt(2.0)
            basis.append(antisymmetric)

    for count in range(1, local_dimension):
        diagonal = np.zeros((local_dimension, local_dimension), dtype=complex)
        normalization = math.sqrt(float(count * (count + 1)))
        for index in range(count):
            diagonal[index, index] = 1.0 / normalization
        diagonal[count, count] = -float(count) / normalization
        basis.append(diagonal)

    return np.array(basis, dtype=complex)


def _realify_matrix(matrix):
    return np.real_if_close(matrix, tol=1000.0)


def _coupling_matrix_in_hermitian_basis(tensor, basis):
    projected = np.einsum("abcd,mab,ncd->mn", tensor, basis, basis, optimize=True)
    imag_residual = float(np.max(np.abs(np.imag(projected)))) if projected.size else 0.0
    return np.array(np.real(_realify_matrix(projected)), dtype=float), imag_residual


def _lt_blocks(model):
    local_dimension = int(model["local_dimension"])
    basis = _orthonormal_hermitian_basis(local_dimension)
    blocks = []
    imag_residuals = []
    for bond in model.get("bond_tensors", []):
        coupling, imag_residual = _coupling_matrix_in_hermitian_basis(
            _deserialize_tensor(bond["tensor"]),
            basis,
        )
        imag_residuals.append(float(imag_residual))
        blocks.append(
            {
                "source": int(bond.get("source", 0)),
                "target": int(bond.get("target", 0)),
                "R": [int(value) for value in bond["R"]],
                "full": coupling,
                "traceless": np.array(coupling[1:, 1:], dtype=float),
            }
        )
    return {
        "basis": basis,
        "blocks": blocks,
        "magnetic_site_count": int(_magnetic_site_count(model)),
        "magnetic_sites": list(model.get("magnetic_sites", [])),
        "basis_projection_imag_max": float(max(imag_residuals) if imag_residuals else 0.0),
    }


def _traceless_dim(local_dimension):
    return max(0, int(local_dimension) * int(local_dimension) - 1)


def _traceless_slice(site_index, traceless_dim):
    start = int(site_index) * int(traceless_dim)
    return slice(start, start + int(traceless_dim))


def _full_slice(site_index, full_dim):
    start = int(site_index) * int(full_dim)
    return slice(start, start + int(full_dim))


def _kernel_at_q(blocks, q_vector, *, p_weights=None, magnetic_site_count=1):
    if not blocks:
        return np.zeros((0, 0), dtype=float)
    traceless_dim = int(blocks[0]["traceless"].shape[0])
    site_count = max(1, int(magnetic_site_count))
    weights = np.array(p_weights if p_weights is not None else [1.0] * site_count, dtype=float)
    kernel = np.zeros((site_count * traceless_dim, site_count * traceless_dim), dtype=complex)
    for block in blocks:
        source = int(block.get("source", 0))
        target = int(block.get("target", 0))
        phase = _fractional_phase(q_vector, block["R"])
        reduced = float(weights[source]) * float(weights[target]) * np.array(block["traceless"], dtype=float)
        kernel[_traceless_slice(source, traceless_dim), _traceless_slice(target, traceless_dim)] += (
            np.exp(1.0j * phase) * reduced
        )
    kernel = 0.5 * (kernel + kernel.conjugate().T)
    return np.array(np.real(_realify_matrix(kernel)), dtype=float)


def _physicalize_site_mode_vector(mode_vector, p_weights, traceless_dim):
    vector = np.array(mode_vector, dtype=float, copy=True)
    weights = np.array(p_weights, dtype=float)
    for site_index, weight in enumerate(weights):
        vector[_traceless_slice(site_index, traceless_dim)] *= float(weight)
    return vector


def _physicalize_shell_basis(shell_basis, p_weights, traceless_dim):
    basis = np.array(shell_basis, dtype=float, copy=True)
    if basis.ndim == 1:
        basis = basis[:, np.newaxis]
    weights = np.array(p_weights, dtype=float)
    for site_index, weight in enumerate(weights):
        basis[_traceless_slice(site_index, traceless_dim), :] *= float(weight)
    return basis


def _uniform_field_vector(blocks, local_dimension, *, p_weights=None, magnetic_site_count=1):
    x0 = 1.0 / math.sqrt(float(local_dimension))
    if not blocks:
        return np.zeros((max(0, local_dimension * local_dimension - 1),), dtype=float), 0.0

    full_dim = int(blocks[0]["full"].shape[0])
    traceless_dim = int(full_dim - 1)
    site_count = max(1, int(magnetic_site_count))
    weights = np.array(p_weights if p_weights is not None else [1.0] * site_count, dtype=float)
    full_matrix = np.zeros((site_count * full_dim, site_count * full_dim), dtype=float)
    for block in blocks:
        source = int(block.get("source", 0))
        target = int(block.get("target", 0))
        full = np.array(block["full"], dtype=float)
        scaled = np.zeros_like(full)
        scaled[0, 0] = full[0, 0]
        scaled[0, 1:] = float(weights[target]) * full[0, 1:]
        scaled[1:, 0] = float(weights[source]) * full[1:, 0]
        scaled[1:, 1:] = float(weights[source]) * float(weights[target]) * full[1:, 1:]
        full_matrix[_full_slice(source, full_dim), _full_slice(target, full_dim)] += scaled

    symmetric = 0.5 * (full_matrix + full_matrix.T)
    fixed = np.zeros((site_count * full_dim,), dtype=float)
    for site_index in range(site_count):
        fixed[_full_slice(site_index, full_dim).start] = x0

    constant = float(fixed @ symmetric @ fixed)
    field_full = symmetric @ fixed
    field = np.zeros((site_count * traceless_dim,), dtype=float)
    for site_index in range(site_count):
        field[_traceless_slice(site_index, traceless_dim)] = field_full[_full_slice(site_index, full_dim).start + 1 : _full_slice(site_index, full_dim).stop]
    return field, float(constant)


def _trust_region_on_sphere(kernel, field, radius_sq, *, tolerance=1.0e-12):
    dimension = int(kernel.shape[0])
    radius = math.sqrt(max(0.0, float(radius_sq)))
    if dimension == 0 or radius <= tolerance:
        vector = np.zeros((dimension,), dtype=float)
        energy = float(vector @ kernel @ vector + 2.0 * np.dot(field, vector))
        return vector, energy, {"mode": "trivial", "lagrange_multiplier": None}

    eigenvalues, eigenvectors = _stable_hermitian_eigh(kernel)
    rotated_field = eigenvectors.conjugate().T @ np.array(field, dtype=float)

    if float(np.linalg.norm(rotated_field)) <= tolerance:
        vector = np.array(np.real_if_close(eigenvectors[:, 0], tol=1000.0), dtype=float) * radius
        energy = float(vector @ kernel @ vector)
        return vector, energy, {"mode": "lowest-eigenvector", "lagrange_multiplier": float(eigenvalues[0])}

    def secular(lambda_value):
        denominator = eigenvalues - float(lambda_value)
        return float(np.sum((rotated_field / denominator) ** 2) - radius_sq)

    upper = float(eigenvalues[0] - 1.0e-12)
    lower = float(eigenvalues[0] - max(1.0, np.max(np.abs(eigenvalues)) + np.linalg.norm(field) / max(radius, tolerance)))
    while secular(lower) > 0.0:
        lower -= max(1.0, abs(lower))

    for _ in range(200):
        midpoint = 0.5 * (lower + upper)
        value = secular(midpoint)
        if abs(value) <= tolerance:
            lower = midpoint
            upper = midpoint
            break
        if value > 0.0:
            upper = midpoint
        else:
            lower = midpoint

    lagrange_multiplier = 0.5 * (lower + upper)
    denominator = eigenvalues - lagrange_multiplier
    rotated_vector = -rotated_field / denominator
    vector = np.array(np.real_if_close(eigenvectors @ rotated_vector, tol=1000.0), dtype=float)
    norm = float(np.linalg.norm(vector))
    if norm > tolerance:
        vector *= radius / norm
    energy = float(vector @ kernel @ vector + 2.0 * np.dot(field, vector))
    return vector, energy, {"mode": "trust-region-bisection", "lagrange_multiplier": float(lagrange_multiplier)}


def _normalized_ray(vector):
    vector = np.array(vector, dtype=complex)
    norm = float(np.linalg.norm(vector))
    if norm <= 1.0e-14:
        raise ValueError("local ray must not be zero")
    vector = vector / norm
    for value in vector:
        if abs(value) > 1.0e-12:
            vector = vector / (value / abs(value))
            break
    return vector


def _projector_exactness(projector, *, tolerance):
    hermitian_part = 0.5 * (projector + projector.conjugate().T)
    eigenvalues, eigenvectors = np.linalg.eigh(hermitian_part)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = np.array(eigenvalues[order], dtype=float)
    eigenvectors = np.array(eigenvectors[:, order], dtype=complex)

    dominant = float(eigenvalues[0]) if eigenvalues.size else 0.0
    negativity = float(sum(max(0.0, -value) for value in eigenvalues))
    purity = float(np.real(np.trace(hermitian_part @ hermitian_part)))
    trace_value = complex(np.trace(projector))
    residual = {
        "trace": trace_value,
        "trace_residual": float(abs(trace_value - 1.0)),
        "hermiticity_residual": float(np.linalg.norm(projector - projector.conjugate().T)),
        "negativity_residual": float(negativity),
        "purity_residual": float(abs(purity - 1.0)),
        "rank_one_residual": float(
            math.sqrt((1.0 - dominant) ** 2 + sum(value * value for value in eigenvalues[1:]))
        ),
        "eigenvalues": [float(value) for value in eigenvalues],
        "dominant_eigenvalue": float(dominant),
        "is_exact_projector_solution": False,
    }
    residual["is_exact_projector_solution"] = bool(
        residual["trace_residual"] <= tolerance
        and residual["hermiticity_residual"] <= tolerance
        and residual["negativity_residual"] <= tolerance
        and residual["purity_residual"] <= tolerance
        and residual["rank_one_residual"] <= tolerance
    )
    return residual, eigenvectors[:, 0] if eigenvectors.size else np.zeros((projector.shape[0],), dtype=complex)


def _aggregate_projector_exactness(exactness_by_site):
    if not exactness_by_site:
        return {
            "trace_residual": 0.0,
            "hermiticity_residual": 0.0,
            "negativity_residual": 0.0,
            "purity_residual": 0.0,
            "rank_one_residual": 0.0,
            "is_exact_projector_solution": False,
            "sites": [],
        }

    aggregate = {
        "trace_residual": max(float(item["trace_residual"]) for item in exactness_by_site),
        "hermiticity_residual": max(float(item["hermiticity_residual"]) for item in exactness_by_site),
        "negativity_residual": max(float(item["negativity_residual"]) for item in exactness_by_site),
        "purity_residual": max(float(item["purity_residual"]) for item in exactness_by_site),
        "rank_one_residual": max(float(item["rank_one_residual"]) for item in exactness_by_site),
        "dominant_eigenvalue": min(float(item["dominant_eigenvalue"]) for item in exactness_by_site),
        "eigenvalues": [list(item["eigenvalues"]) for item in exactness_by_site],
        "is_exact_projector_solution": all(bool(item["is_exact_projector_solution"]) for item in exactness_by_site),
        "sites": [],
    }
    for site_index, item in enumerate(exactness_by_site):
        aggregate["sites"].append(
            {
                "site": int(site_index),
                "trace": _serialize_complex(item["trace"]),
                "trace_residual": float(item["trace_residual"]),
                "hermiticity_residual": float(item["hermiticity_residual"]),
                "negativity_residual": float(item["negativity_residual"]),
                "purity_residual": float(item["purity_residual"]),
                "rank_one_residual": float(item["rank_one_residual"]),
                "dominant_eigenvalue": float(item["dominant_eigenvalue"]),
                "eigenvalues": list(item["eigenvalues"]),
                "is_exact_projector_solution": bool(item["is_exact_projector_solution"]),
            }
        )
    if len(exactness_by_site) == 1:
        aggregate["trace"] = _serialize_complex(exactness_by_site[0]["trace"])
    return aggregate


def _weights_from_log_coordinates(log_coordinates):
    coordinates = np.array(log_coordinates, dtype=float)
    if coordinates.size == 0:
        full = np.array([0.0], dtype=float)
    else:
        full = np.concatenate([coordinates, np.array([-float(np.sum(coordinates))], dtype=float)])
    p_weights = np.exp(full)
    alpha_weights = np.exp(-2.0 * full)
    return p_weights, alpha_weights, full


def _evaluate_weighted_candidate(blocks_payload, *, q_mesh, local_dimension, p_weights):
    site_count = int(blocks_payload["magnetic_site_count"])
    blocks = blocks_payload["blocks"]
    alpha_weights = [float(value) ** -2 for value in p_weights]
    radius_sq = max(0.0, (1.0 - 1.0 / float(local_dimension)) * float(sum(alpha_weights)))
    field, constant_term = _uniform_field_vector(
        blocks,
        local_dimension,
        p_weights=p_weights,
        magnetic_site_count=site_count,
    )
    uniform_kernel = _kernel_at_q(
        blocks,
        [0.0, 0.0, 0.0],
        p_weights=p_weights,
        magnetic_site_count=site_count,
    )
    uniform_vector, uniform_relative_energy, uniform_optimizer = _trust_region_on_sphere(
        uniform_kernel,
        field,
        radius_sq,
    )
    uniform_energy = float(constant_term + uniform_relative_energy)

    best_q_energy = None
    best_q_vector = None
    best_q_mode = None
    best_q_kernel = None
    best_q_basis = None
    best_q_shell_dimension = 0
    q_sector_candidates = []
    zero_q = [0.0, 0.0, 0.0]
    for q_vector in q_mesh:
        normalized_q = _normalized_q_vector(q_vector)
        if _is_zero_q_vector(normalized_q):
            continue
        kernel = _kernel_at_q(
            blocks,
            normalized_q,
            p_weights=p_weights,
            magnetic_site_count=site_count,
        )
        if kernel.size == 0:
            eigenvalue = 0.0
            eigenvector = np.zeros((0,), dtype=float)
            eigenspace = np.zeros((0, 0), dtype=float)
        else:
            eigenvalues, eigenvectors = _stable_hermitian_eigh(kernel)
            degenerate = np.isclose(eigenvalues, eigenvalues[0], atol=1.0e-9)
            eigenvalue = float(eigenvalues[0])
            eigenvector = np.array(np.real_if_close(eigenvectors[:, 0], tol=1000.0), dtype=float)
            eigenspace = np.array(np.real_if_close(eigenvectors[:, degenerate], tol=1000.0), dtype=float)
        energy = float(constant_term + radius_sq * eigenvalue)
        q_sector_candidates.append(
            {
                "q_vector": list(normalized_q),
                "energy": float(energy),
                "mode_vector": np.array(eigenvector, dtype=float),
                "kernel": kernel,
                "shell_basis": np.array(eigenspace, dtype=float),
                "shell_dimension": int(eigenspace.shape[1]) if eigenspace.ndim == 2 else 0,
            }
        )
        if best_q_energy is None or energy < best_q_energy:
            best_q_energy = energy
            best_q_vector = [float(value) for value in normalized_q]
            best_q_mode = eigenvector
            best_q_kernel = kernel
            best_q_basis = eigenspace
            best_q_shell_dimension = int(eigenspace.shape[1]) if eigenspace.ndim == 2 else 0

    lowest_shell_sectors = []
    if best_q_energy is not None:
        energy_tolerance = 1.0e-10 + 1.0e-9 * max(1.0, abs(float(best_q_energy)))
        sector_by_key = {}
        for candidate in q_sector_candidates:
            if abs(float(candidate["energy"]) - float(best_q_energy)) > energy_tolerance:
                continue
            key = _q_sector_key(candidate["q_vector"])
            if key in sector_by_key:
                continue
            sector_by_key[key] = {
                "q_vector": list(_canonicalize_q_vector_under_inversion(candidate["q_vector"])),
                "shell_basis": _physicalize_shell_basis(
                    candidate["shell_basis"],
                    p_weights,
                    _traceless_dim(local_dimension),
                ),
            }
        lowest_shell_sectors = list(sector_by_key.values())
        if lowest_shell_sectors:
            best_q_vector = list(lowest_shell_sectors[0]["q_vector"])
            for candidate in q_sector_candidates:
                if _q_sector_key(candidate["q_vector"]) == _q_sector_key(best_q_vector):
                    best_q_mode = candidate["mode_vector"]
                    best_q_kernel = candidate["kernel"]
                    best_q_basis = candidate["shell_basis"]
                    best_q_shell_dimension = int(candidate["shell_dimension"])
                    break

    winning_q = list(best_q_vector or zero_q)
    winning_energy = float(best_q_energy if best_q_energy is not None else uniform_energy)
    winning_mode_kind = "nonzero-q-relaxed-mode"
    winning_scaled_vector = np.array(best_q_mode if best_q_mode is not None else np.zeros_like(field), dtype=float)
    winning_kernel = best_q_kernel
    winning_basis = np.array(best_q_basis, dtype=float) if best_q_basis is not None else np.zeros((field.size, 0), dtype=float)
    winning_shell_dimension = int(
        sum(
            np.array(sector.get("shell_basis", np.zeros((0, 0), dtype=float)), dtype=float).shape[1]
            for sector in lowest_shell_sectors
        )
        if lowest_shell_sectors
        else best_q_shell_dimension
    )
    optimizer_metadata = {
        "mode": "lowest-eigenmode-on-q-mesh",
        "lagrange_multiplier": None,
    }
    if best_q_energy is None or uniform_energy <= winning_energy + 1.0e-12:
        winning_q = list(zero_q)
        winning_energy = float(uniform_energy)
        winning_mode_kind = "uniform-trust-region"
        winning_scaled_vector = np.array(uniform_vector, dtype=float)
        winning_kernel = uniform_kernel
        winning_basis = np.array(uniform_vector, dtype=float)[:, np.newaxis]
        winning_shell_dimension = 1 if uniform_vector.size else 0
        optimizer_metadata = dict(uniform_optimizer)
        lowest_shell_sectors = []

    return {
        "energy": float(winning_energy),
        "q_vector": list(winning_q),
        "mode_kind": str(winning_mode_kind),
        "scaled_vector": np.array(winning_scaled_vector, dtype=float),
        "kernel": winning_kernel,
        "constant_term": float(constant_term),
        "radius_sq": float(radius_sq),
        "uniform_lower_bound": float(uniform_energy),
        "q_zero_affine_lower_bound": float(uniform_energy),
        "best_q_mesh_lower_bound": float(best_q_energy if best_q_energy is not None else uniform_energy),
        "uniform_optimizer": optimizer_metadata,
        "q_zero_affine_optimizer": dict(optimizer_metadata),
        "p_weights": [float(value) for value in p_weights],
        "alpha_weights": [float(value) for value in alpha_weights],
        "lowest_shell_basis": winning_basis,
        "lowest_shell_dimension": int(winning_shell_dimension),
        "lowest_shell_sectors": list(lowest_shell_sectors),
        "lowest_shell_sector_count": int(len(lowest_shell_sectors)),
    }


def _search_weights(blocks_payload, *, q_mesh, local_dimension, magnetic_site_count, weight_bound=1.0, weight_points=9):
    site_count = max(1, int(magnetic_site_count))
    if site_count <= 1:
        candidate = _evaluate_weighted_candidate(
            blocks_payload,
            q_mesh=q_mesh,
            local_dimension=local_dimension,
            p_weights=[1.0],
        )
        candidate["weight_search"] = {
            "search_strategy": "identity",
            "evaluated_candidates": 1,
            "weight_bound": float(weight_bound),
            "weight_points": int(weight_points),
            "best_p_weights": [1.0],
            "best_alpha_weights": [1.0],
            "best_log_weights": [0.0],
        }
        return candidate

    axis = np.linspace(-float(weight_bound), float(weight_bound), int(weight_points))
    free_coordinates = np.zeros((site_count - 1,), dtype=float)
    p_weights, alpha_weights, full_logs = _weights_from_log_coordinates(free_coordinates)
    best = _evaluate_weighted_candidate(
        blocks_payload,
        q_mesh=q_mesh,
        local_dimension=local_dimension,
        p_weights=p_weights,
    )
    best["weight_search"] = {
        "search_strategy": "coordinate",
        "evaluated_candidates": 1,
        "weight_bound": float(weight_bound),
        "weight_points": int(weight_points),
        "best_p_weights": [float(value) for value in p_weights],
        "best_alpha_weights": [float(value) for value in alpha_weights],
        "best_log_weights": [float(value) for value in full_logs],
    }
    evaluations = 1

    improved = True
    while improved:
        improved = False
        for coordinate_index in range(site_count - 1):
            local_best = best
            local_coordinates = np.array(free_coordinates, dtype=float)
            for candidate_value in axis:
                trial = np.array(free_coordinates, dtype=float)
                trial[coordinate_index] = float(candidate_value)
                p_trial, alpha_trial, full_trial = _weights_from_log_coordinates(trial)
                candidate = _evaluate_weighted_candidate(
                    blocks_payload,
                    q_mesh=q_mesh,
                    local_dimension=local_dimension,
                    p_weights=p_trial,
                )
                evaluations += 1
                if candidate["energy"] > local_best["energy"] + 1.0e-12:
                    candidate["weight_search"] = {
                        "search_strategy": "coordinate",
                        "evaluated_candidates": 0,
                        "weight_bound": float(weight_bound),
                        "weight_points": int(weight_points),
                        "best_p_weights": [float(value) for value in p_trial],
                        "best_alpha_weights": [float(value) for value in alpha_trial],
                        "best_log_weights": [float(value) for value in full_trial],
                    }
                    local_best = candidate
                    local_coordinates = trial
            if local_best["energy"] > best["energy"] + 1.0e-12:
                best = local_best
                free_coordinates = local_coordinates
                improved = True

    best["weight_search"]["evaluated_candidates"] = int(evaluations)
    return best


def _classical_state_from_ray(ray, conventions):
    normalized = _normalized_ray(ray)
    return {
        "schema_version": 1,
        "state_kind": "local_rays",
        "manifold": "CP^(N-1)",
        "basis_order": conventions["basis_order"],
        "pair_basis_order": conventions["pair_basis_order"],
        "supercell_shape": [1, 1, 1],
        "local_rays": [
            {
                "cell": [0, 0, 0],
                "vector": _serialize_vector(normalized),
            }
        ],
        "ordering": {
            "kind": "uniform",
            "supercell_shape": [1, 1, 1],
        },
    }


def _uniform_multisublattice_classical_state(dominant_rays, blocks_payload, conventions):
    local_rays = []
    for site_index, ray in enumerate(dominant_rays):
        site_metadata = (
            blocks_payload["magnetic_sites"][site_index]
            if site_index < len(blocks_payload["magnetic_sites"])
            and isinstance(blocks_payload["magnetic_sites"][site_index], dict)
            else {}
        )
        local_rays.append(
            {
                "cell": [0, 0, 0],
                "site": int(site_index),
                "label": str(site_metadata.get("label", f"site{site_index}")),
                "vector": _serialize_vector(_normalized_ray(ray)),
            }
        )
    return {
        "schema_version": 1,
        "state_kind": "local_rays",
        "manifold": "CP^(N-1)",
        "basis_order": conventions["basis_order"],
        "pair_basis_order": conventions["pair_basis_order"],
        "supercell_shape": [1, 1, 1],
        "local_rays": local_rays,
        "ordering": {
            "kind": "uniform",
            "q_vector": [0.0, 0.0, 0.0],
            "supercell_shape": [1, 1, 1],
        },
    }


def solve_cpn_generalized_lt_ground_state(
    model,
    *,
    requested_method="cpn-generalized-lt",
    mesh_shape=None,
    projector_tolerance=1.0e-8,
    starts=1,
    seed=0,
):
    if model.get("classical_manifold") != "CP^(N-1)":
        raise ValueError("cpn generalized-LT solver expects a CP^(N-1) classical payload")
    conventions = resolve_pseudospin_orbital_conventions(model)

    local_dimension = int(model["local_dimension"])
    if local_dimension <= 0:
        raise ValueError("model.local_dimension must be positive")

    blocks_payload = _lt_blocks(model)
    blocks = blocks_payload["blocks"]
    resolved_mesh_shape = _default_mesh_shape(model, mesh_shape)
    q_mesh = generate_q_mesh(resolved_mesh_shape)
    magnetic_site_count = int(blocks_payload["magnetic_site_count"])
    weighted = _search_weights(
        blocks_payload,
        q_mesh=q_mesh,
        local_dimension=local_dimension,
        magnetic_site_count=magnetic_site_count,
    )

    winning_q = list(weighted["q_vector"])
    winning_energy = float(weighted["energy"])
    winning_mode_kind = str(weighted["mode_kind"])
    winning_scaled_vector = np.array(weighted["scaled_vector"], dtype=float)
    winning_kernel = weighted["kernel"]
    optimizer_metadata = dict(weighted["uniform_optimizer"])
    p_weights = np.array(weighted["p_weights"], dtype=float)
    lowest_shell_basis = np.array(weighted.get("lowest_shell_basis", np.zeros((0, 0), dtype=float)), dtype=float)
    lowest_shell_sectors = list(weighted.get("lowest_shell_sectors", []))

    basis = blocks_payload["basis"]
    traceless_dim = _traceless_dim(local_dimension)
    projectors = []
    dominant_rays = []
    exactness_by_site = []
    for site_index in range(magnetic_site_count):
        physical_mode = float(p_weights[site_index]) * winning_scaled_vector[_traceless_slice(site_index, traceless_dim)]
        projector = np.array(basis[0], dtype=complex) / math.sqrt(float(local_dimension))
        if basis.shape[0] > 1:
            projector = projector + np.einsum("m,mab->ab", physical_mode, basis[1:], optimize=True)
        projector = 0.5 * (projector + projector.conjugate().T)
        trace_value = complex(np.trace(projector))
        if abs(trace_value) > 1.0e-14:
            projector = projector / trace_value
        exactness, dominant_ray = _projector_exactness(
            projector,
            tolerance=float(projector_tolerance),
        )
        projectors.append(projector)
        dominant_rays.append(dominant_ray)
        exactness_by_site.append(exactness)

    projector_exactness = _aggregate_projector_exactness(exactness_by_site)

    result = {
        "method": str(requested_method),
        "solver_role": "diagnostic-only",
        "diagnostic_scope": "generalized-cpn-relaxed-lt-with-commensurate-lowest-shell-lifting",
        "recommended_followup": "use the relaxed GLT result as a lower bound / ordering seed for constrained CP^(N-1) minimization; exact q=0 and exact commensurate lowest-shell lifts are diagnostic seeds, not final classical states",
        "manifold": "CP^(N-1)",
        "basis_order": conventions["basis_order"],
        "pair_basis_order": conventions["pair_basis_order"],
        "magnetic_site_count": int(magnetic_site_count),
        "energy": float(winning_energy),
        "q_vector": list(winning_q),
        "relaxed_lt": {
            "q_seed": list(winning_q),
            "lower_bound": float(winning_energy),
            "mesh_shape": [int(value) for value in resolved_mesh_shape],
            "sample_count": int(len(q_mesh)),
            "mode_kind": winning_mode_kind,
            "relaxation_space": "traceless-hermitian-projector-coefficients",
            "single_site_generalized_lt_limit": bool(magnetic_site_count == 1),
            "magnetic_site_count": int(magnetic_site_count),
            "basis_projection_imag_max": float(blocks_payload["basis_projection_imag_max"]),
            "uniform_lower_bound": float(weighted["uniform_lower_bound"]),
            "q_zero_affine_lower_bound": float(weighted["q_zero_affine_lower_bound"]),
            "best_q_mesh_lower_bound": float(weighted["best_q_mesh_lower_bound"]),
            "uniform_optimizer": optimizer_metadata,
            "q_zero_affine_optimizer": dict(weighted["q_zero_affine_optimizer"]),
            "weight_search": dict(weighted["weight_search"]),
            "lowest_shell_dimension": int(weighted.get("lowest_shell_dimension", 0)),
            "lowest_shell_sector_count": int(weighted.get("lowest_shell_sector_count", 0)),
            "lowest_shell_q_vectors": [list(sector.get("q_vector", [0.0, 0.0, 0.0])) for sector in lowest_shell_sectors],
        },
        "projector_exactness": dict(projector_exactness),
        "reconstructed_projector": {
            "matrix": [
                [[_serialize_complex(value) for value in row] for row in projector]
                for projector in projectors
            ],
            "kernel_dimension": int(winning_kernel.shape[0]) if winning_kernel is not None else 0,
        },
        "starts": int(starts),
        "seed": int(seed),
    }
    if "trace" in result["projector_exactness"]:
        result["projector_exactness"]["trace"] = dict(result["projector_exactness"]["trace"])

    if winning_q == [0.0, 0.0, 0.0] and projector_exactness["is_exact_projector_solution"]:
        if magnetic_site_count == 1:
            classical_state = _classical_state_from_ray(dominant_rays[0], conventions)
            diagnostics = diagnose_sun_gswt_classical_state(
                model,
                {
                    "shape": [1, 1, 1],
                    "local_rays": list(classical_state["local_rays"]),
                },
            )
            result["seed_candidate"] = {
                "kind": "uniform-exact-projector-seed",
                "classical_state": classical_state,
                "projector_diagnostics": diagnostics["projector_diagnostics"],
                "stationarity": diagnostics["stationarity"],
            }
            result["classical_state"] = dict(classical_state)
        else:
            classical_state = _uniform_multisublattice_classical_state(dominant_rays, blocks_payload, conventions)
            result["seed_candidate"] = {
                "kind": "uniform-exact-projector-seed-multisublattice",
                "magnetic_site_count": int(magnetic_site_count),
                "sublattice_rays": [
                    {
                        "site": int(site_index),
                        "label": blocks_payload["magnetic_sites"][site_index]["label"]
                        if site_index < len(blocks_payload["magnetic_sites"])
                        and isinstance(blocks_payload["magnetic_sites"][site_index], dict)
                        else f"site{site_index}",
                        "vector": _serialize_vector(_normalized_ray(dominant_rays[site_index])),
                    }
                    for site_index in range(magnetic_site_count)
                ],
                "projector_exactness": {
                    "sites": list(projector_exactness["sites"]),
                    "is_exact_projector_solution": True,
                },
            }
            result["classical_state"] = classical_state
        result["solver_role"] = "final"
        result["promotion_reason"] = "exact_projector_solution"
    elif any(abs(float(component)) > 1.0e-12 for component in winning_q):
        if lowest_shell_sectors:
            reconstruction = reconstruct_commensurate_relaxed_shell(
                basis=basis,
                local_dimension=local_dimension,
                sectors=lowest_shell_sectors,
                radius_sq=float(weighted["radius_sq"]),
                basis_order=conventions["basis_order"],
                pair_basis_order=conventions["pair_basis_order"],
                projector_tolerance=float(projector_tolerance),
            )
        else:
            reconstruction = reconstruct_commensurate_single_q_texture(
                basis=basis,
                local_dimension=local_dimension,
                q_vector=winning_q,
                shell_basis=lowest_shell_basis,
                radius_sq=float(weighted["radius_sq"]),
                basis_order=conventions["basis_order"],
                pair_basis_order=conventions["pair_basis_order"],
                projector_tolerance=float(projector_tolerance),
            )
        result["reconstruction"] = reconstruction
        if reconstruction.get("status") == "exact" and isinstance(reconstruction.get("classical_state"), dict):
            result["seed_candidate"] = {
                "kind": (
                    "commensurate-exact-projector-seed-multisublattice"
                    if int(magnetic_site_count) > 1
                    else "commensurate-exact-projector-seed"
                ),
                "classical_state": dict(reconstruction["classical_state"]),
                "projector_exactness": dict(reconstruction["projector_exactness"]),
                "ordering": dict(reconstruction["ordering"]),
            }
            result["classical_state"] = dict(reconstruction["classical_state"])
            result["solver_role"] = "final"
            result["promotion_reason"] = "exact_commensurate_lift"

    if str(result.get("solver_role")) != "final":
        result = finalize_cpn_glt_result(
            model,
            result,
            starts=1,
            seed=seed,
        )

    return result
