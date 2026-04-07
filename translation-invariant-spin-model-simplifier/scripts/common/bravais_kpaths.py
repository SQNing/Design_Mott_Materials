#!/usr/bin/env python3
import math
import numpy as np

from lattice_geometry import resolve_lattice_vectors


def _vector_norm(vector):
    return math.sqrt(sum(float(value) * float(value) for value in vector))


def _dot(left, right):
    return sum(float(left[index]) * float(right[index]) for index in range(3))


def _angle_degrees(left, right):
    left_norm = _vector_norm(left)
    right_norm = _vector_norm(right)
    if left_norm <= 1e-12 or right_norm <= 1e-12:
        return 0.0
    cosine = max(-1.0, min(1.0, _dot(left, right) / (left_norm * right_norm)))
    return math.degrees(math.acos(cosine))


def infer_bravais_family(lattice, spatial_dimension):
    kind = str(lattice.get("kind", "")).lower()
    vectors = resolve_lattice_vectors(lattice)
    lengths = [_vector_norm(vector) for vector in vectors]

    if spatial_dimension <= 1:
        return "chain"

    if spatial_dimension == 2:
        if any(token in kind for token in {"triangular", "honeycomb", "kagome", "hexagonal"}):
            return "hexagonal"
        if "square" in kind:
            return "square"
        if "rect" in kind:
            return "rectangular"
        gamma = _angle_degrees(vectors[0], vectors[1])
        if abs(lengths[0] - lengths[1]) <= 1e-6:
            if abs(gamma - 90.0) <= 1e-3:
                return "square"
            if abs(gamma - 60.0) <= 1e-3 or abs(gamma - 120.0) <= 1e-3:
                return "hexagonal"
        return "rectangular"

    if "hexagonal" in kind:
        return "hexagonal"
    if "tetragonal" in kind:
        return "tetragonal"
    if "cubic" in kind:
        return "cubic"
    if "orthorhombic" in kind:
        return "orthorhombic"

    alpha = _angle_degrees(vectors[1], vectors[2])
    beta = _angle_degrees(vectors[0], vectors[2])
    gamma = _angle_degrees(vectors[0], vectors[1])
    all_right_angles = all(abs(angle - 90.0) <= 1e-3 for angle in (alpha, beta, gamma))

    if all_right_angles:
        if abs(lengths[0] - lengths[1]) <= 1e-6 and abs(lengths[1] - lengths[2]) <= 1e-6:
            return "cubic"
        if abs(lengths[0] - lengths[1]) <= 1e-6 and abs(lengths[2] - lengths[0]) > 1e-6:
            return "tetragonal"
        return "orthorhombic"

    if abs(lengths[0] - lengths[1]) <= 1e-6 and abs(alpha - 90.0) <= 1e-3 and abs(beta - 90.0) <= 1e-3 and (
        abs(gamma - 120.0) <= 1e-3 or abs(gamma - 60.0) <= 1e-3
    ):
        return "hexagonal"

    return "orthorhombic"


def _user_lengths_and_angles(lattice):
    vectors = resolve_lattice_vectors(lattice)
    lengths = [_vector_norm(vector) for vector in vectors]
    alpha = _angle_degrees(vectors[1], vectors[2])
    beta = _angle_degrees(vectors[0], vectors[2])
    gamma = _angle_degrees(vectors[0], vectors[1])
    return vectors, lengths, alpha, beta, gamma


def canonical_direct_basis(lattice, spatial_dimension):
    family = infer_bravais_family(lattice, spatial_dimension)
    _vectors, lengths, alpha, beta, gamma = _user_lengths_and_angles(lattice)

    if spatial_dimension <= 1:
        a = lengths[0] if lengths and lengths[0] > 1e-12 else 1.0
        b = lengths[1] if len(lengths) > 1 and lengths[1] > 1e-12 else 1.0
        c = lengths[2] if len(lengths) > 2 and lengths[2] > 1e-12 else 1.0
        basis = [[a, 0.0, 0.0], [0.0, b, 0.0], [0.0, 0.0, c]]
        return family, basis

    if spatial_dimension == 2:
        c = lengths[2] if len(lengths) > 2 and lengths[2] > 1e-12 else 1.0
        if family == "hexagonal":
            a = 0.5 * (lengths[0] + lengths[1])
            basis = [[a, 0.0, 0.0], [-0.5 * a, math.sqrt(3.0) * 0.5 * a, 0.0], [0.0, 0.0, c]]
            return family, basis
        if family == "square":
            a = 0.5 * (lengths[0] + lengths[1])
            basis = [[a, 0.0, 0.0], [0.0, a, 0.0], [0.0, 0.0, c]]
            return family, basis
        a = lengths[0] if lengths[0] > 1e-12 else 1.0
        b = lengths[1] if lengths[1] > 1e-12 else 1.0
        basis = [[a, 0.0, 0.0], [0.0, b, 0.0], [0.0, 0.0, c]]
        return family, basis

    if family == "cubic":
        a = sum(lengths[:3]) / 3.0
        basis = [[a, 0.0, 0.0], [0.0, a, 0.0], [0.0, 0.0, a]]
        return family, basis

    if family == "tetragonal":
        sorted_lengths = sorted(lengths[:3])
        c = max(sorted_lengths)
        a = 0.5 * (sorted_lengths[0] + sorted_lengths[1])
        basis = [[a, 0.0, 0.0], [0.0, a, 0.0], [0.0, 0.0, c]]
        return family, basis

    if family == "hexagonal":
        c = max(lengths[:3])
        in_plane = sorted(lengths[:3])[:2]
        a = 0.5 * (in_plane[0] + in_plane[1])
        basis = [[a, 0.0, 0.0], [-0.5 * a, math.sqrt(3.0) * 0.5 * a, 0.0], [0.0, 0.0, c]]
        return family, basis

    a = lengths[0] if lengths[0] > 1e-12 else 1.0
    b = lengths[1] if lengths[1] > 1e-12 else 1.0
    c = lengths[2] if lengths[2] > 1e-12 else 1.0
    basis = [[a, 0.0, 0.0], [0.0, b, 0.0], [0.0, 0.0, c]]
    return family, basis


def transform_kpoints_to_user_convention(points, lattice, spatial_dimension):
    _family, canonical_basis = canonical_direct_basis(lattice, spatial_dimension)
    user_basis = resolve_lattice_vectors(lattice)
    canonical_cols = np.array(canonical_basis, dtype=float).T
    user_cols = np.array(user_basis, dtype=float).T
    transform = user_cols.T @ np.linalg.inv(canonical_cols).T
    transformed = []
    for point in points:
        q_std = np.array(point, dtype=float)
        transformed.append((transform @ q_std).tolist())
    return transformed


def default_high_symmetry_path(lattice, spatial_dimension):
    family, _canonical_basis = canonical_direct_basis(lattice, spatial_dimension)

    lookup = {
        "chain": {
            "labels": ["G", "X"],
            "points": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
        },
        "square": {
            "labels": ["G", "X", "M", "G"],
            "points": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0], [0.5, 0.5, 0.0], [0.0, 0.0, 0.0]],
        },
        "rectangular": {
            "labels": ["G", "X", "S", "Y", "G"],
            "points": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0], [0.5, 0.5, 0.0], [0.0, 0.5, 0.0], [0.0, 0.0, 0.0]],
        },
        "hexagonal": {
            "labels": ["G", "K", "M", "G"],
            "points": [[0.0, 0.0, 0.0], [1.0 / 3.0, 1.0 / 3.0, 0.0], [0.5, 0.0, 0.0], [0.0, 0.0, 0.0]],
        },
        "cubic": {
            "labels": ["G", "X", "M", "G", "R", "X"],
            "points": [
                [0.0, 0.0, 0.0],
                [0.5, 0.0, 0.0],
                [0.5, 0.5, 0.0],
                [0.0, 0.0, 0.0],
                [0.5, 0.5, 0.5],
                [0.5, 0.0, 0.0],
            ],
        },
        "tetragonal": {
            "labels": ["G", "X", "M", "G", "Z", "R", "A", "Z"],
            "points": [
                [0.0, 0.0, 0.0],
                [0.5, 0.0, 0.0],
                [0.5, 0.5, 0.0],
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 0.5],
                [0.5, 0.0, 0.5],
                [0.5, 0.5, 0.5],
                [0.0, 0.0, 0.5],
            ],
        },
        "orthorhombic": {
            "labels": ["G", "X", "S", "Y", "G", "Z", "U", "R", "T", "Z"],
            "points": [
                [0.0, 0.0, 0.0],
                [0.5, 0.0, 0.0],
                [0.5, 0.5, 0.0],
                [0.0, 0.5, 0.0],
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 0.5],
                [0.5, 0.0, 0.5],
                [0.5, 0.5, 0.5],
                [0.0, 0.5, 0.5],
                [0.0, 0.0, 0.5],
            ],
        },
    }

    nodes = lookup.get(family, lookup["orthorhombic" if spatial_dimension >= 3 else "rectangular"])
    return family, {
        "labels": list(nodes["labels"]),
        "points": transform_kpoints_to_user_convention(nodes["points"], lattice, spatial_dimension),
    }
