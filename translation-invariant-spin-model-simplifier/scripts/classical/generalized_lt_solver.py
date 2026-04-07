#!/usr/bin/env python3
import itertools

import numpy as np

from lt_brillouin_zone import generate_q_mesh
from lt_fourier_exchange import fourier_exchange_matrix


def _n_sublattices(model):
    if model.get("lattice", {}).get("sublattices"):
        return int(model["lattice"]["sublattices"])
    bonds = model.get("bonds", [])
    return max(max(int(bond["source"]), int(bond["target"])) for bond in bonds) + 1


def _serialize_vectors(vectors):
    serialized = []
    for vector in vectors.T:
        serialized.append(
            [{"real": float(np.real(value)), "imag": float(np.imag(value))} for value in vector]
        )
    return serialized


def _lambda_candidates(sublattice_count, lower, upper, points):
    if sublattice_count < 2:
        return [[0.0]]
    axis = np.linspace(float(lower), float(upper), int(points))
    for candidate in itertools.product(axis, repeat=sublattice_count - 1):
        candidate = [float(value) for value in candidate]
        candidate.append(float(-sum(candidate)))
        yield candidate


def _best_for_lambda(model, q_mesh, lambda_vector):
    lambda_diag = np.diag(lambda_vector)
    best_value = None
    best_q = None
    best_vectors = None

    for q in q_mesh:
        jq = fourier_exchange_matrix(model, q) + lambda_diag
        eigenvalues, eigenvectors = np.linalg.eigh(jq)
        min_value = float(np.real(eigenvalues[0]))
        if best_value is None or min_value < best_value:
            best_value = min_value
            best_q = [float(component) for component in q]
            degenerate = np.isclose(eigenvalues, eigenvalues[0], atol=1e-9)
            best_vectors = eigenvectors[:, degenerate]

    return best_value, best_q, best_vectors


def _grid_search(model, q_mesh, sublattice_count, lower, upper, lambda_points):
    best_lambda = None
    best_value = None
    best_q = None
    best_vectors = None
    evaluations = 0

    for lambda_vector in _lambda_candidates(sublattice_count, lower, upper, lambda_points):
        value, q, vectors = _best_for_lambda(model, q_mesh, np.array(lambda_vector, dtype=float))
        evaluations += 1
        if best_value is None or value > best_value:
            best_value = value
            best_lambda = lambda_vector
            best_q = q
            best_vectors = vectors

    return best_lambda, best_value, best_q, best_vectors, evaluations


def _coordinate_search(model, q_mesh, sublattice_count, lower, upper, lambda_points):
    if sublattice_count < 2:
        best_lambda = [0.0]
        best_value, best_q, best_vectors = _best_for_lambda(model, q_mesh, np.array(best_lambda, dtype=float))
        return best_lambda, best_value, best_q, best_vectors, 1

    axis = np.linspace(float(lower), float(upper), int(lambda_points))
    current = [0.0] * sublattice_count
    current_value, current_q, current_vectors = _best_for_lambda(model, q_mesh, np.array(current, dtype=float))
    evaluations = 1

    improved = True
    while improved:
        improved = False
        for index in range(sublattice_count - 1):
            best_local = current
            best_local_value = current_value
            best_local_q = current_q
            best_local_vectors = current_vectors
            for candidate_value in axis:
                trial = list(current)
                trial[index] = float(candidate_value)
                trial[-1] = float(-sum(trial[:-1]))
                value, q, vectors = _best_for_lambda(model, q_mesh, np.array(trial, dtype=float))
                evaluations += 1
                if value > best_local_value:
                    best_local = trial
                    best_local_value = value
                    best_local_q = q
                    best_local_vectors = vectors
            if best_local_value > current_value:
                current = best_local
                current_value = best_local_value
                current_q = best_local_q
                current_vectors = best_local_vectors
                improved = True

    return current, current_value, current_q, current_vectors, evaluations


def find_generalized_lt_ground_state(
    model,
    mesh_shape=(17, 17, 1),
    lambda_bounds=(-1.0, 1.0),
    lambda_points=21,
    search_strategy="grid",
):
    sublattice_count = _n_sublattices(model)
    q_mesh = generate_q_mesh(tuple(int(value) for value in mesh_shape))

    lower, upper = lambda_bounds
    if search_strategy == "grid":
        best_lambda, best_value, best_q, best_vectors, evaluations = _grid_search(
            model, q_mesh, sublattice_count, lower, upper, lambda_points
        )
    elif search_strategy == "coordinate":
        best_lambda, best_value, best_q, best_vectors, evaluations = _coordinate_search(
            model, q_mesh, sublattice_count, lower, upper, lambda_points
        )
    else:
        raise ValueError(f"unsupported search_strategy: {search_strategy}")

    return {
        "lambda": [float(value) for value in best_lambda],
        "tightened_lower_bound": float(best_value),
        "q": best_q,
        "eigenspace": _serialize_vectors(best_vectors),
        "mesh_shape": list(mesh_shape),
        "sample_count": len(q_mesh),
        "optimization": {
            "search_strategy": search_strategy,
            "evaluated_candidates": int(evaluations),
            "lambda_bounds": [float(lower), float(upper)],
            "lambda_points": int(lambda_points),
        },
    }
