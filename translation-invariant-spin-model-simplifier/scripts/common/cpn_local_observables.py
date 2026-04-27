#!/usr/bin/env python3
import math

import numpy as np

from common.cpn_classical_state import resolve_cpn_classical_state_payload


def _complex_from_serialized(value):
    if isinstance(value, dict):
        return complex(float(value.get("real", 0.0)), float(value.get("imag", 0.0)))
    return complex(value)


def _deserialize_vector(entries):
    return np.array([_complex_from_serialized(value) for value in entries], dtype=complex)


def _infer_local_dimension(payload, classical_state):
    retained_local_space = payload.get("retained_local_space", {})
    dimension = retained_local_space.get("dimension")
    if dimension is not None:
        return int(dimension)

    local_basis_labels = payload.get("local_basis_labels", [])
    if local_basis_labels:
        return int(len(local_basis_labels))

    local_rays = classical_state.get("local_rays", [])
    if local_rays:
        return int(len(local_rays[0].get("vector", [])))
    raise ValueError("cannot infer local_dimension for CP^(N-1) local-ray observables")


def _factorization_kind(payload):
    retained_local_space = payload.get("retained_local_space", {})
    factorization = retained_local_space.get("factorization", {})
    return str(factorization.get("kind") or "orbital_times_spin")


def _infer_orbital_count(payload, local_dimension):
    retained_local_space = payload.get("retained_local_space", {})
    factorization = retained_local_space.get("factorization", {})
    orbital_count = factorization.get("orbital_count")
    if orbital_count is not None:
        return int(orbital_count)
    if int(local_dimension) % 2 != 0:
        raise ValueError("CP^(N-1) local-ray observables require an even local dimension for orbital_major_spin_minor")
    return max(1, int(local_dimension) // 2)


def _basis_group_labels(payload, orbital_count):
    labels = payload.get("local_basis_labels", [])
    grouped = []
    if len(labels) >= 2 * int(orbital_count):
        for orbital_index in range(int(orbital_count)):
            up_label = str(labels[2 * orbital_index])
            down_label = str(labels[2 * orbital_index + 1])
            if up_label.startswith("up_") and down_label.startswith("down_") and up_label[3:] == down_label[5:]:
                grouped.append(up_label[3:])
                continue
            if up_label.startswith("up") and down_label.startswith("down"):
                up_suffix = up_label[2:].lstrip("_")
                down_suffix = down_label[4:].lstrip("_")
                if up_suffix and up_suffix == down_suffix:
                    grouped.append(up_suffix)
                    continue
            grouped.append(f"orb{orbital_index + 1}")
        return grouped
    return [f"orb{orbital_index + 1}" for orbital_index in range(int(orbital_count))]


def _expectation(vector, operator):
    return float(np.real(np.vdot(vector, operator @ vector)))


def build_cpn_local_observable_summary(payload, classical_state):
    resolved_state = resolve_cpn_classical_state_payload(classical_state)
    local_rays = resolved_state.get("local_rays", [])
    if not local_rays:
        return None

    local_dimension = _infer_local_dimension(payload, resolved_state)
    factorization_kind = _factorization_kind(payload)
    if factorization_kind == "generic_multiplet":
        basis_labels = list(payload.get("local_basis_labels") or [])
        if len(basis_labels) != int(local_dimension):
            basis_labels = [f"state_{index + 1}" for index in range(int(local_dimension))]

        observables = []
        for item in local_rays:
            vector = _deserialize_vector(item.get("vector", []))
            if vector.size != int(local_dimension):
                raise ValueError(
                    f"local ray at cell {item.get('cell')} has dimension {vector.size}, expected {local_dimension}"
                )
            norm = float(np.linalg.norm(vector))
            if norm <= 1e-14:
                raise ValueError(f"local ray at cell {item.get('cell')} must not be zero")
            vector = vector / norm
            basis_probabilities = [float(np.abs(value) ** 2) for value in vector]
            dominant_basis_index = int(np.argmax(basis_probabilities)) if basis_probabilities else 0
            observables.append(
                {
                    "cell": [int(value) for value in item.get("cell", [0, 0, 0])],
                    "basis_probabilities": basis_probabilities,
                    "basis_probability_map": {
                        basis_labels[index]: float(basis_probabilities[index]) for index in range(int(local_dimension))
                    },
                    "dominant_basis_index": dominant_basis_index,
                    "dominant_basis_label": basis_labels[dominant_basis_index],
                    "dominant_basis_weight": float(basis_probabilities[dominant_basis_index]) if basis_probabilities else 0.0,
                }
            )

        return {
            "local_dimension": int(local_dimension),
            "factorization_kind": "generic_multiplet",
            "basis_labels": basis_labels,
            "local_observables": observables,
        }

    orbital_count = _infer_orbital_count(payload, local_dimension)
    if int(local_dimension) != 2 * int(orbital_count):
        raise ValueError("local_dimension must equal 2 * orbital_count for orbital_major_spin_minor")

    sigma_x = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=complex)
    sigma_y = np.array([[0.0, -1.0j], [1.0j, 0.0]], dtype=complex)
    sigma_z = np.array([[1.0, 0.0], [0.0, -1.0]], dtype=complex)
    spin_identity = np.eye(2, dtype=complex)
    orbital_identity = np.eye(int(orbital_count), dtype=complex)
    spin_operators = [
        np.kron(orbital_identity, sigma_x),
        np.kron(orbital_identity, sigma_y),
        np.kron(orbital_identity, sigma_z),
    ]

    orbital_operators = None
    if int(orbital_count) == 2:
        orbital_operators = [
            np.kron(sigma_x, spin_identity),
            np.kron(sigma_y, spin_identity),
            np.kron(sigma_z, spin_identity),
        ]

    orbital_labels = _basis_group_labels(payload, orbital_count)
    observables = []
    for item in local_rays:
        vector = _deserialize_vector(item.get("vector", []))
        if vector.size != int(local_dimension):
            raise ValueError(
                f"local ray at cell {item.get('cell')} has dimension {vector.size}, expected {local_dimension}"
            )
        norm = float(np.linalg.norm(vector))
        if norm <= 1e-14:
            raise ValueError(f"local ray at cell {item.get('cell')} must not be zero")
        vector = vector / norm

        spin_expectation = [_expectation(vector, operator) for operator in spin_operators]
        spin_polarization_norm = float(math.sqrt(sum(value * value for value in spin_expectation)))
        orbital_weights = [
            float(np.sum(np.abs(vector[2 * orbital_index : 2 * orbital_index + 2]) ** 2))
            for orbital_index in range(int(orbital_count))
        ]
        dominant_orbital_index = int(np.argmax(orbital_weights)) if orbital_weights else 0
        orbital_weight_map = {
            orbital_labels[orbital_index]: float(orbital_weights[orbital_index])
            for orbital_index in range(int(orbital_count))
        }

        observable = {
            "cell": [int(value) for value in item.get("cell", [0, 0, 0])],
            "spin_expectation": [float(value) for value in spin_expectation],
            "spin_polarization_norm": spin_polarization_norm,
            "orbital_weights": [float(value) for value in orbital_weights],
            "orbital_weight_map": orbital_weight_map,
            "dominant_orbital_index": dominant_orbital_index,
            "dominant_orbital_label": orbital_labels[dominant_orbital_index],
            "dominant_orbital_weight": float(orbital_weights[dominant_orbital_index]) if orbital_weights else 0.0,
        }
        if orbital_operators is not None:
            orbital_expectation = [_expectation(vector, operator) for operator in orbital_operators]
            observable["orbital_expectation"] = [float(value) for value in orbital_expectation]
            observable["orbital_polarization_norm"] = float(
                math.sqrt(sum(value * value for value in orbital_expectation))
            )
        observables.append(observable)

    return {
        "local_dimension": int(local_dimension),
        "factorization_kind": "orbital_times_spin",
        "orbital_count": int(orbital_count),
        "orbital_labels": orbital_labels,
        "local_observables": observables,
    }
