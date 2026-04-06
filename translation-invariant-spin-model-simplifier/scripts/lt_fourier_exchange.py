#!/usr/bin/env python3
import cmath
import math

import numpy as np


def _n_sublattices(model):
    if model.get("lattice", {}).get("sublattices"):
        return int(model["lattice"]["sublattices"])
    bonds = model.get("bonds", [])
    if not bonds:
        raise ValueError("model must include at least one bond")
    return max(max(int(bond["source"]), int(bond["target"])) for bond in bonds) + 1


def _isotropic_heisenberg_scalar(matrix, tolerance=1e-9):
    array = np.array(matrix, dtype=float)
    if array.shape != (3, 3):
        raise ValueError("bond matrix must be 3x3")
    diagonal = np.diag(array)
    if not (
        abs(diagonal[0] - diagonal[1]) <= tolerance
        and abs(diagonal[1] - diagonal[2]) <= tolerance
        and np.allclose(array - np.diag(diagonal), 0.0, atol=tolerance)
    ):
        raise ValueError("LT Fourier exchange currently supports isotropic Heisenberg bond matrices only")
    return float(np.mean(diagonal))


def _phase_factor(q, vector):
    q_vector = [float(value) for value in q]
    translation = [float(value) for value in vector]
    while len(q_vector) < 3:
        q_vector.append(0.0)
    while len(translation) < 3:
        translation.append(0.0)
    phase = 2.0 * math.pi * sum(q_vector[index] * translation[index] for index in range(3))
    return cmath.exp(-1j * phase)


def fourier_exchange_matrix(model, q):
    sublattice_count = _n_sublattices(model)
    jq = np.zeros((sublattice_count, sublattice_count), dtype=complex)

    for bond in model.get("bonds", []):
        source = int(bond["source"])
        target = int(bond["target"])
        scalar = _isotropic_heisenberg_scalar(bond["matrix"])
        phase = _phase_factor(q, bond.get("vector", [0.0, 0.0, 0.0]))
        jq[source, target] += scalar * phase
        if source != target or any(abs(float(value)) > 1e-12 for value in bond.get("vector", [])):
            jq[target, source] += scalar * phase.conjugate()

    return jq
