#!/usr/bin/env python3
import math


def _as_float_triplet(vector):
    values = [float(component) for component in vector]
    while len(values) < 3:
        values.append(0.0)
    return values[:3]


def _dot(left, right):
    return sum(float(left[index]) * float(right[index]) for index in range(3))


def _norm(vector):
    return math.sqrt(_dot(vector, vector))


def vector_rank(vectors, tolerance=1e-9):
    orthonormal_basis = []
    for vector in vectors:
        residual = _as_float_triplet(vector)
        for basis_vector in orthonormal_basis:
            projection = _dot(residual, basis_vector)
            residual = [
                residual[axis] - projection * basis_vector[axis]
                for axis in range(3)
            ]
        norm = _norm(residual)
        if norm > tolerance:
            orthonormal_basis.append([value / norm for value in residual])
    return len(orthonormal_basis)


def lattice_vectors_from_cell_parameters(cell_parameters):
    a = float(cell_parameters["a"])
    b = float(cell_parameters["b"])
    c = float(cell_parameters["c"])
    alpha = math.radians(float(cell_parameters["alpha"]))
    beta = math.radians(float(cell_parameters["beta"]))
    gamma = math.radians(float(cell_parameters["gamma"]))

    ax = a
    ay = 0.0
    az = 0.0

    bx = b * math.cos(gamma)
    by = b * math.sin(gamma)
    bz = 0.0

    cx = c * math.cos(beta)
    sin_gamma = math.sin(gamma)
    if abs(sin_gamma) <= 1e-12:
        raise ValueError("gamma produces a singular lattice basis")
    cy = c * (math.cos(alpha) - math.cos(beta) * math.cos(gamma)) / sin_gamma
    cz_sq = c * c - cx * cx - cy * cy
    cz = math.sqrt(max(0.0, cz_sq))
    return [
        [ax, ay, az],
        [bx, by, bz],
        [cx, cy, cz],
    ]


def resolve_lattice_vectors(lattice):
    if lattice.get("lattice_vectors"):
        return [_as_float_triplet(vector) for vector in lattice["lattice_vectors"]]
    if lattice.get("cell_parameters"):
        return lattice_vectors_from_cell_parameters(lattice["cell_parameters"])
    return [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]


def lattice_vector_rank(lattice, tolerance=1e-9):
    return vector_rank(resolve_lattice_vectors(lattice), tolerance=tolerance)


def fractional_to_cartesian(fractional_positions, lattice_vectors):
    vectors = [_as_float_triplet(vector) for vector in lattice_vectors]
    cartesian_positions = []
    for position in fractional_positions:
        frac = _as_float_triplet(position)
        cartesian_positions.append(
            [
                frac[0] * vectors[0][axis] + frac[1] * vectors[1][axis] + frac[2] * vectors[2][axis]
                for axis in range(3)
            ]
        )
    return cartesian_positions


def _group_shells(entries, shell_count, tolerance):
    grouped = []
    for entry in entries:
        if not grouped or abs(entry["distance"] - grouped[-1]["distance"]) > tolerance:
            grouped.append({"distance": entry["distance"], "pairs": [entry["pair"]]})
        else:
            grouped[-1]["pairs"].append(entry["pair"])
        if len(grouped) >= shell_count and entry["distance"] - grouped[-1]["distance"] > tolerance:
            break
    return grouped[:shell_count]


def enumerate_neighbor_shells(lattice_vectors, fractional_positions, shell_count=3, max_translation=2, tolerance=1e-9):
    vectors = resolve_lattice_vectors({"lattice_vectors": lattice_vectors})
    cartesian_positions = fractional_to_cartesian(fractional_positions, vectors)
    entries = []
    for source_index, source in enumerate(cartesian_positions):
        for target_index, target_frac in enumerate(fractional_positions):
            target_base = _as_float_triplet(target_frac)
            for ta in range(-max_translation, max_translation + 1):
                for tb in range(-max_translation, max_translation + 1):
                    for tc in range(-max_translation, max_translation + 1):
                        if source_index == target_index and ta == tb == tc == 0:
                            continue
                        translated_frac = [
                            target_base[0] + ta,
                            target_base[1] + tb,
                            target_base[2] + tc,
                        ]
                        translated_cart = fractional_to_cartesian([translated_frac], vectors)[0]
                        delta = [translated_cart[axis] - source[axis] for axis in range(3)]
                        distance = _norm(delta)
                        if distance <= tolerance:
                            continue
                        entries.append(
                            {
                                "distance": distance,
                                "pair": {
                                    "source": source_index,
                                    "target": target_index,
                                    "translation": (ta, tb, tc),
                                    "delta": delta,
                                },
                            }
                        )
    entries.sort(key=lambda item: (round(item["distance"], 12), item["pair"]["translation"], item["pair"]["target"]))
    return _group_shells(entries, shell_count=shell_count, tolerance=tolerance)


def _exchange_matrix_from_scalar(value):
    scalar = float(value)
    return [
        [scalar, 0.0, 0.0],
        [0.0, scalar, 0.0],
        [0.0, 0.0, scalar],
    ]


def _canonicalize_pair(source, target, translation):
    translation_tuple = tuple(int(component) for component in translation)
    inverse = tuple(-component for component in translation_tuple)
    canonical_translation = translation_tuple
    for component in translation_tuple:
        if component < 0:
            canonical_translation = inverse
            return (int(target), int(source), canonical_translation)
        if component > 0:
            return (int(source), int(target), canonical_translation)
    forward_key = (int(source), int(target), translation_tuple)
    inverse_key = (int(target), int(source), inverse)
    return min(forward_key, inverse_key)


def _sorted_shell_parameter_items(parameters):
    shell_items = []
    for key, value in parameters.items():
        if not isinstance(key, str) or not key.startswith("J"):
            continue
        suffix = key[1:]
        if not suffix.isdigit():
            continue
        shell_items.append((int(suffix), key, float(value)))
    shell_items.sort(key=lambda item: item[0])
    return shell_items


def _normalize_shell_override(shell_map_override):
    normalized = {}
    for label, shell_index in (shell_map_override or {}).items():
        if not isinstance(label, str):
            continue
        try:
            resolved_index = int(shell_index)
        except (TypeError, ValueError):
            continue
        if resolved_index <= 0:
            continue
        normalized[label.upper()] = resolved_index
    return normalized


def build_isotropic_heisenberg_bonds_from_parameters(
    lattice,
    parameters,
    max_shell=None,
    max_translation=2,
    tolerance=1e-9,
    shell_map_override=None,
):
    shell_items = _sorted_shell_parameter_items(parameters)
    if not shell_items:
        return [], {}

    normalized_override = _normalize_shell_override(shell_map_override)
    requested_shell_indices = [
        normalized_override.get(label.upper(), index) for index, label, _value in shell_items
    ]
    shell_count = max_shell or max(requested_shell_indices)
    lattice_vectors = resolve_lattice_vectors(lattice)
    positions = lattice.get("positions") or [[0.0, 0.0, 0.0]]
    shells = enumerate_neighbor_shells(
        lattice_vectors,
        positions,
        shell_count=shell_count,
        max_translation=max_translation,
        tolerance=tolerance,
    )

    shell_map = {}
    bonds = []
    shell_lookup = {shell_index + 1: shell for shell_index, shell in enumerate(shells)}
    for fallback_index, label, value in shell_items:
        requested_shell_index = normalized_override.get(label.upper(), fallback_index)
        shell = shell_lookup.get(requested_shell_index)
        if shell is None:
            continue
        shell_map[label] = {
            "shell_index": requested_shell_index,
            "distance": shell["distance"],
            "pair_count": len(shell["pairs"]),
        }
        seen_pairs = set()
        for pair in shell["pairs"]:
            canonical = _canonicalize_pair(pair["source"], pair["target"], pair["translation"])
            if canonical in seen_pairs:
                continue
            seen_pairs.add(canonical)
            canonical_source, canonical_target, canonical_translation = canonical
            bonds.append(
                {
                    "shell_index": requested_shell_index,
                    "shell_label": label,
                    "source": canonical_source,
                    "target": canonical_target,
                    "vector": list(canonical_translation),
                    "delta": [
                        float(component)
                        for component in fractional_to_cartesian([canonical_translation], lattice_vectors)[0]
                    ],
                    "distance": float(shell["distance"]),
                    "matrix": _exchange_matrix_from_scalar(value),
                }
            )
    return bonds, shell_map
