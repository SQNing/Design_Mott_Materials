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


def _bond_matrix(matrix):
    array = np.array(matrix, dtype=complex)
    if array.shape != (3, 3):
        raise ValueError("bond matrix must be 3x3")
    return array


def _block_slice(site_index):
    start = 3 * int(site_index)
    return slice(start, start + 3)


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
    jq = np.zeros((3 * sublattice_count, 3 * sublattice_count), dtype=complex)

    for bond in model.get("bonds", []):
        source = int(bond["source"])
        target = int(bond["target"])
        matrix = _bond_matrix(bond["matrix"])
        phase = _phase_factor(q, bond.get("vector", [0.0, 0.0, 0.0]))
        source_block = _block_slice(source)
        target_block = _block_slice(target)
        jq[source_block, target_block] += matrix * phase
        if source != target or any(abs(float(value)) > 1e-12 for value in bond.get("vector", [])):
            jq[target_block, source_block] += matrix.conjugate().T * phase.conjugate()

    return jq
