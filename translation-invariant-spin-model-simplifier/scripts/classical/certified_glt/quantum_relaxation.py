#!/usr/bin/env python3

import numpy as np

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from classical.cpn_local_ray_energy import deserialize_matrix, deserialize_tensor
else:
    from ..cpn_local_ray_energy import deserialize_matrix, deserialize_tensor


def _site_count(model):
    return max(1, int(model.get("magnetic_site_count", 1)))


def _linear_index(cell_index, site_index, shape, site_count):
    flat_cell = int(np.ravel_multi_index(tuple(cell_index), tuple(shape)))
    return int(flat_cell * int(site_count) + int(site_index))


def _mod_index(index, shape):
    return tuple(int(index[axis]) % int(shape[axis]) for axis in range(3))


def _one_site_operator(matrix, target, total_sites, local_dimension):
    operator = np.array([[1.0 + 0.0j]], dtype=complex)
    for site in range(int(total_sites)):
        factor = np.array(matrix, dtype=complex) if int(site) == int(target) else np.eye(int(local_dimension), dtype=complex)
        operator = np.kron(operator, factor)
    return operator


def _two_site_operator(tensor, left, right, total_sites, local_dimension):
    dim = int(local_dimension)
    total_dimension = dim ** int(total_sites)
    operator = np.zeros((total_dimension, total_dimension), dtype=complex)
    for left_a in range(dim):
        for left_b in range(dim):
            for right_c in range(dim):
                for right_d in range(dim):
                    coefficient = complex(tensor[left_a, left_b, right_c, right_d])
                    if abs(coefficient) <= 1.0e-15:
                        continue
                    left_matrix = np.zeros((dim, dim), dtype=complex)
                    right_matrix = np.zeros((dim, dim), dtype=complex)
                    left_matrix[left_a, left_b] = 1.0
                    right_matrix[right_c, right_d] = 1.0
                    operator += coefficient * _one_site_operator(left_matrix, left, total_sites, dim) @ _one_site_operator(
                        right_matrix,
                        right,
                        total_sites,
                        dim,
                    )
    return operator


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
            tangent = np.copysign(1.0, tau) / (abs(tau) + np.sqrt(1.0 + tau * tau))
        cosine = 1.0 / np.sqrt(1.0 + tangent * tangent)
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


def build_finite_supercell_quantum_hamiltonian(model, *, supercell_shape):
    if model.get("classical_manifold") != "CP^(N-1)":
        raise ValueError("quantum relaxation expects a CP^(N-1) model")
    shape = tuple(max(1, int(value)) for value in supercell_shape)
    local_dimension = int(model["local_dimension"])
    site_count = _site_count(model)
    total_sites = int(np.prod(shape)) * int(site_count)
    hilbert_dimension = int(local_dimension) ** int(total_sites)
    hamiltonian = np.zeros((hilbert_dimension, hilbert_dimension), dtype=complex)

    for cell_index in np.ndindex(shape):
        for onsite in model.get("onsite_terms", []):
            target = _linear_index(cell_index, int(onsite.get("site", 0)), shape, site_count)
            hamiltonian += _one_site_operator(
                deserialize_matrix(onsite["matrix"]),
                target,
                total_sites,
                local_dimension,
            )

        for bond in model.get("bond_tensors", []):
            source = int(bond.get("source", 0))
            target_site = int(bond.get("target", 0))
            right_cell = _mod_index(
                tuple(int(cell_index[axis]) + int(bond["R"][axis]) for axis in range(3)),
                shape,
            )
            left = _linear_index(cell_index, source, shape, site_count)
            right = _linear_index(right_cell, target_site, shape, site_count)
            hamiltonian += _two_site_operator(
                deserialize_tensor(bond["tensor"]),
                left,
                right,
                total_sites,
                local_dimension,
            )

    return 0.5 * (hamiltonian + hamiltonian.conjugate().T)


def certify_quantum_relaxation_lower_bound(model, *, supercell_shape=(1, 1, 1), max_hilbert_dimension=256):
    shape = tuple(max(1, int(value)) for value in supercell_shape)
    local_dimension = int(model["local_dimension"])
    site_count = _site_count(model)
    total_sites = int(np.prod(shape)) * int(site_count)
    hilbert_dimension = int(local_dimension) ** int(total_sites)
    if hilbert_dimension > int(max_hilbert_dimension):
        return {
            "status": "skipped",
            "method": "finite-supercell-exact-diagonalization",
            "reason": "hilbert_dimension_exceeds_limit",
            "hilbert_dimension": int(hilbert_dimension),
            "max_hilbert_dimension": int(max_hilbert_dimension),
            "supercell_shape": [int(value) for value in shape],
            "estimated_total_sites": int(total_sites),
        }
    hamiltonian = build_finite_supercell_quantum_hamiltonian(model, supercell_shape=shape)
    real_symmetric = np.array(np.real(np.real_if_close(0.5 * (hamiltonian + hamiltonian.conjugate().T), tol=1000.0)), dtype=float)
    eigenvalues, _ = _jacobi_real_symmetric_eigh(real_symmetric)
    cell_count = int(np.prod(shape))
    lower_bound = float(np.min(np.real(eigenvalues)) / float(cell_count))
    return {
        "status": "certified",
        "method": "finite-supercell-exact-diagonalization",
        "lower_bound": lower_bound,
        "hilbert_dimension": int(hilbert_dimension),
        "supercell_shape": [int(value) for value in shape],
        "cell_count": int(cell_count),
    }
