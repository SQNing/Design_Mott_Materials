#!/usr/bin/env python3
import itertools
import math

import numpy as np


_SPIN_AXES = ("x", "y", "z")
_ORBITAL_AXES = ("x", "y", "z")


def _complex_from_serialized(value):
    if isinstance(value, dict):
        return complex(float(value.get("real", 0.0)), float(value.get("imag", 0.0)))
    return complex(value)


def _cartesian_from_R(R, lattice_vectors):
    lattice_vectors = np.array(lattice_vectors, dtype=float)
    return np.array(R, dtype=float) @ lattice_vectors


def _r_vectors_from_model(model):
    vectors = []
    for term in model.get("terms", []):
        if "R" in term:
            vectors.append(tuple(int(value) for value in term["R"]))
    return vectors


def _displacement_rank(model):
    lattice_vectors = model.get("lattice_vectors")
    if not lattice_vectors:
        return 1
    displacements = [
        _cartesian_from_R(term["R"], lattice_vectors)
        for term in model.get("terms", [])
        if "R" in term
    ]
    if not displacements:
        return 1
    return max(1, int(np.linalg.matrix_rank(np.array(displacements, dtype=float))))


def _represent_in_basis(vector, basis_matrix, tolerance=1e-8):
    target = np.array(vector, dtype=float)
    solution, *_ = np.linalg.lstsq(basis_matrix, target, rcond=None)
    rounded = np.rint(solution).astype(int)
    if np.max(np.abs(basis_matrix @ rounded - target)) > tolerance:
        return None
    return tuple(int(value) for value in rounded.tolist())


def build_reduced_lattice_view(model):
    r_vectors = sorted(set(_r_vectors_from_model(model)))
    if not r_vectors:
        return {
            "rank": 1,
            "basis_vectors": [(1, 0, 0)],
            "reduced_R_by_term": [(0, 0, 0) for _ in model.get("terms", [])],
        }

    rank = _displacement_rank(model)
    best_basis = None
    best_score = None

    for candidate in itertools.combinations(r_vectors, rank):
        basis_matrix = np.array(candidate, dtype=float).T
        if np.linalg.matrix_rank(basis_matrix) != rank:
            continue
        representations = [_represent_in_basis(vector, basis_matrix) for vector in r_vectors]
        if any(item is None for item in representations):
            continue
        score = sum(sum(abs(component) for component in vector) for vector in candidate)
        if best_score is None or score < best_score:
            best_basis = candidate
            best_score = score

    if best_basis is None:
        raise ValueError("could not build an integer reduced lattice basis from model R vectors")

    basis_matrix = np.array(best_basis, dtype=float).T
    reduced_R_by_term = []
    for term in model.get("terms", []):
        reduced = _represent_in_basis(term.get("R", (0, 0, 0)), basis_matrix)
        if reduced is None:
            raise ValueError("term R vector is not representable in the reduced lattice basis")
        padded = list(reduced) + [0] * (3 - len(reduced))
        reduced_R_by_term.append(tuple(int(value) for value in padded[:3]))

    return {
        "rank": int(rank),
        "basis_vectors": [list(vector) for vector in best_basis],
        "reduced_R_by_term": reduced_R_by_term,
    }


def _field_basis():
    basis = []
    for axis in _SPIN_AXES:
        basis.append(("spin", axis))
    for axis in _ORBITAL_AXES:
        basis.append(("orbital", axis))
    for spin_axis in _SPIN_AXES:
        for orbital_axis in _ORBITAL_AXES:
            basis.append(("composite", spin_axis, orbital_axis))
    return basis


def _field_index():
    mapping = {}
    basis = _field_basis()
    for index, item in enumerate(basis):
        mapping[item] = index
    return basis, mapping


def _term_channel_key(term):
    left = {(factor["field"], factor["axis"].lower()): factor for factor in term.get("factors", []) if factor["site_role"] == "left"}
    right = {(factor["field"], factor["axis"].lower()): factor for factor in term.get("factors", []) if factor["site_role"] == "right"}

    left_spin = next((axis for (field, axis) in left if field == "spin"), None)
    right_spin = next((axis for (field, axis) in right if field == "spin"), None)
    left_orbital = next((axis for (field, axis) in left if field == "orbital"), None)
    right_orbital = next((axis for (field, axis) in right if field == "orbital"), None)

    if left_spin and right_spin and not left_orbital and not right_orbital:
        return ("spin", left_spin), ("spin", right_spin)
    if left_orbital and right_orbital and not left_spin and not right_spin:
        return ("orbital", left_orbital), ("orbital", right_orbital)
    if left_spin and right_spin and left_orbital and right_orbital:
        return ("composite", left_spin, left_orbital), ("composite", right_spin, right_orbital)
    return None


def _reduced_mesh(mesh_shape, rank):
    nx, ny, nz = (int(value) for value in mesh_shape)
    shapes = [nx, ny, nz]
    for item in itertools.product(*(range(shapes[index]) for index in range(rank))):
        q = [0.0, 0.0, 0.0]
        for index in range(rank):
            denominator = max(1, shapes[index] - 1)
            q[index] = float(item[index]) / float(denominator)
        yield q


def find_pseudospin_orbital_relaxed_lt_seed(model, mesh_shape=None):
    if int(model.get("orbital_count", 0)) != 2:
        raise ValueError("relaxed LT diagnostic only supports orbital_count = 2")

    lattice_view = build_reduced_lattice_view(model)
    rank = lattice_view["rank"]
    if mesh_shape is None:
        mesh_shape = (17, 1, 1) if rank == 1 else (17, 17, 1) if rank == 2 else (9, 9, 9)

    basis, index_by_key = _field_index()
    size = len(basis)
    coupling_by_R = {}
    ignored_terms = 0

    for term, reduced_R in zip(model.get("terms", []), lattice_view["reduced_R_by_term"]):
        channel = _term_channel_key(term)
        if channel is None:
            ignored_terms += 1
            continue
        coefficient = _complex_from_serialized(term.get("coefficient", 0.0))
        if abs(coefficient.imag) > 1e-10:
            ignored_terms += 1
            continue
        matrix = coupling_by_R.setdefault(tuple(reduced_R), np.zeros((size, size), dtype=complex))
        matrix[index_by_key[channel[0]], index_by_key[channel[1]]] += complex(float(coefficient.real), 0.0)

    best_q = None
    best_value = None
    best_vector = None
    for q in _reduced_mesh(mesh_shape, rank):
        matrix = np.zeros((size, size), dtype=complex)
        for reduced_R, coupling in coupling_by_R.items():
            phase = complex(np.exp(-2.0j * math.pi * sum(q[index] * reduced_R[index] for index in range(rank))))
            matrix += coupling * phase
        matrix = 0.5 * (matrix + matrix.conj().T)
        eigenvalues, eigenvectors = np.linalg.eigh(matrix)
        minimum = float(np.real(eigenvalues[0]))
        if best_value is None or minimum < best_value:
            best_value = minimum
            best_q = [float(value) for value in q]
            best_vector = eigenvectors[:, 0]

    dominant_index = int(np.argmax(np.abs(best_vector)))
    return {
        "mode": "relaxed-lt-diagnostic",
        "q_seed": best_q,
        "lower_bound": float(best_value),
        "field_basis": [
            "S_x",
            "S_y",
            "S_z",
            "T_x",
            "T_y",
            "T_z",
            "Q_xx",
            "Q_xy",
            "Q_xz",
            "Q_yx",
            "Q_yy",
            "Q_yz",
            "Q_zx",
            "Q_zy",
            "Q_zz",
        ],
        "dominant_channel": [
            "S_x",
            "S_y",
            "S_z",
            "T_x",
            "T_y",
            "T_z",
            "Q_xx",
            "Q_xy",
            "Q_xz",
            "Q_yx",
            "Q_yy",
            "Q_yz",
            "Q_zx",
            "Q_zy",
            "Q_zz",
        ][dominant_index],
        "mesh_shape": [int(value) for value in mesh_shape],
        "ignored_term_count": int(ignored_terms),
        "reduced_lattice": {
            "rank": int(rank),
            "basis_vectors": lattice_view["basis_vectors"],
        },
    }
