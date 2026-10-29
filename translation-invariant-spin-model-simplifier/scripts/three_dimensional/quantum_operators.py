"""Spin representation and finite pair Hamiltonians shared by GSWT and ED."""

import numpy as np
from common.model_analysis import _spin_matrices


def spin_operators(spin):
    spin = float(spin)
    dimension = int(round(2 * spin + 1))
    if spin <= 0 or not np.isfinite(spin) or abs(dimension - (2 * spin + 1)) > 1e-12:
        raise ValueError("spin must be a positive integer or half-integer")
    operators = _spin_matrices(dimension)
    return np.array([operators[label] for label in ("Sx", "Sy", "Sz")])


def pair_operator(matrix, operators):
    dimension = operators.shape[1]
    result = np.zeros((dimension ** 2, dimension ** 2), dtype=complex)
    for a in range(3):
        for b in range(3):
            result += matrix[a, b] * np.kron(operators[a], operators[b])
    return result
