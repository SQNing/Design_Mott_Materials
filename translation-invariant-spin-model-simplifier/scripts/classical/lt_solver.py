#!/usr/bin/env python3
import numpy as np

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from classical.lt_brillouin_zone import generate_q_mesh
    from classical.lt_fourier_exchange import fourier_exchange_matrix
else:
    from .lt_brillouin_zone import generate_q_mesh
    from .lt_fourier_exchange import fourier_exchange_matrix


def _serialize_vector(values):
    serialized = []
    for value in values:
        serialized.append({"real": float(np.real(value)), "imag": float(np.imag(value))})
    return serialized


def find_lt_ground_state(model, mesh_shape=(33, 33, 1)):
    mesh_shape = tuple(int(value) for value in mesh_shape)
    q_mesh = generate_q_mesh(mesh_shape)
    sublattice_count = max(1, int(model.get("lattice", {}).get("sublattices", 0) or 0))
    if sublattice_count == 0:
        sublattice_count = 1

    best_q = None
    best_value = None
    best_eigenvector = None
    matrix_size = None

    for q in q_mesh:
        jq = fourier_exchange_matrix(model, q)
        matrix_size = jq.shape[0]
        eigenvalues, eigenvectors = np.linalg.eigh(jq)
        index = int(np.argmin(eigenvalues))
        value = float(np.real(eigenvalues[index]))
        if best_value is None or value < best_value:
            best_value = value
            best_q = [float(component) for component in q]
            best_eigenvector = eigenvectors[:, index]

    return {
        "q": best_q,
        "lowest_eigenvalue": float(best_value),
        "eigenvector": _serialize_vector(best_eigenvector),
        "matrix_size": int(matrix_size),
        "sublattice_count": int(sublattice_count),
        "components_per_sublattice": int(matrix_size // sublattice_count) if matrix_size else 0,
        "mesh_shape": list(mesh_shape),
        "sample_count": len(q_mesh),
    }
