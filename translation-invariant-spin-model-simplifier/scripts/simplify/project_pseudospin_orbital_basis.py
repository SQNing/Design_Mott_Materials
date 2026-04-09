#!/usr/bin/env python3
import math

import numpy as np


def infer_local_dimension_from_num_wann(num_wann):
    num_wann = int(num_wann)
    if num_wann <= 0:
        raise ValueError("num_wann must be positive")
    local_dimension = int(round(math.sqrt(num_wann)))
    if local_dimension * local_dimension != num_wann:
        raise ValueError("num_wann does not define an integer local dimension for a two-site tensor-product space")
    return local_dimension


def infer_orbital_count(local_dimension):
    local_dimension = int(local_dimension)
    if local_dimension <= 0 or local_dimension % 2 != 0:
        raise ValueError("local dimension must be a positive even integer")
    return local_dimension // 2


def _spin_basis():
    identity = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=complex) / math.sqrt(2.0)
    sigma_x = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=complex) / math.sqrt(2.0)
    sigma_y = np.array([[0.0, -1.0j], [1.0j, 0.0]], dtype=complex) / math.sqrt(2.0)
    sigma_z = np.array([[1.0, 0.0], [0.0, -1.0]], dtype=complex) / math.sqrt(2.0)
    return [
        {"label": "spin_I", "matrix": identity},
        {"label": "spin_X", "matrix": sigma_x},
        {"label": "spin_Y", "matrix": sigma_y},
        {"label": "spin_Z", "matrix": sigma_z},
    ]


def _orbital_basis_two_level():
    identity = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=complex) / math.sqrt(2.0)
    tau_x = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=complex) / math.sqrt(2.0)
    tau_y = np.array([[0.0, -1.0j], [1.0j, 0.0]], dtype=complex) / math.sqrt(2.0)
    tau_z = np.array([[1.0, 0.0], [0.0, -1.0]], dtype=complex) / math.sqrt(2.0)
    return [
        {"label": "orbital_I", "matrix": identity},
        {"label": "orbital_X", "matrix": tau_x},
        {"label": "orbital_Y", "matrix": tau_y},
        {"label": "orbital_Z", "matrix": tau_z},
    ]


def _orbital_basis_general(orbital_count):
    identity = np.eye(orbital_count, dtype=complex) / math.sqrt(float(orbital_count))
    basis = [{"label": "orbital_I", "matrix": identity}]

    for left in range(orbital_count):
        for right in range(left + 1, orbital_count):
            sym = np.zeros((orbital_count, orbital_count), dtype=complex)
            sym[left, right] = 1.0
            sym[right, left] = 1.0
            basis.append(
                {
                    "label": f"orbital_SYM_{left + 1}_{right + 1}",
                    "matrix": sym / math.sqrt(2.0),
                }
            )

            asym = np.zeros((orbital_count, orbital_count), dtype=complex)
            asym[left, right] = -1.0j
            asym[right, left] = 1.0j
            basis.append(
                {
                    "label": f"orbital_ASYM_{left + 1}_{right + 1}",
                    "matrix": asym / math.sqrt(2.0),
                }
            )

    for rank in range(1, orbital_count):
        diag = np.zeros((orbital_count, orbital_count), dtype=complex)
        for index in range(rank):
            diag[index, index] = 1.0
        diag[rank, rank] = -float(rank)
        normalization = math.sqrt(float(rank * (rank + 1)))
        basis.append(
            {
                "label": f"orbital_DIAG_{rank}",
                "matrix": diag / normalization,
            }
        )

    return basis


def build_local_operator_basis(orbital_count):
    orbital_count = int(orbital_count)
    if orbital_count <= 0:
        raise ValueError("orbital_count must be positive")

    spin_basis = _spin_basis()
    orbital_basis = _orbital_basis_two_level() if orbital_count == 2 else _orbital_basis_general(orbital_count)

    basis = []
    for spin_element in spin_basis:
        for orbital_element in orbital_basis:
            basis.append(
                {
                    "label": f"{spin_element['label']}__{orbital_element['label']}",
                    # The declared local basis order is
                    # |up,1>, |down,1>, |up,2>, |down,2>, ...
                    # so the local Hilbert-space tensor order is orbital ⊗ spin.
                    "matrix": np.kron(orbital_element["matrix"], spin_element["matrix"]),
                }
            )
    return basis


def project_two_site_bond_matrix(bond_matrix, orbital_count=None, coefficient_tolerance=1e-10):
    bond_matrix = np.array(bond_matrix, dtype=complex)
    if bond_matrix.ndim != 2 or bond_matrix.shape[0] != bond_matrix.shape[1]:
        raise ValueError("bond_matrix must be a square matrix")

    local_dimension = infer_local_dimension_from_num_wann(bond_matrix.shape[0])
    inferred_orbital_count = infer_orbital_count(local_dimension)
    if orbital_count is None:
        orbital_count = inferred_orbital_count
    orbital_count = int(orbital_count)
    if orbital_count != inferred_orbital_count:
        raise ValueError("orbital_count is inconsistent with the inferred local dimension")

    local_basis = build_local_operator_basis(orbital_count)
    if len(local_basis) != local_dimension * local_dimension:
        raise ValueError("local operator basis dimension does not match local Hilbert-space dimension")

    coefficients = []
    for left in local_basis:
        for right in local_basis:
            basis_matrix = np.kron(left["matrix"], right["matrix"])
            coefficient = np.trace(basis_matrix.conj().T @ bond_matrix)
            if abs(coefficient) > coefficient_tolerance:
                coefficients.append(
                    {
                        "left_label": left["label"],
                        "right_label": right["label"],
                        "coefficient": coefficient,
                    }
                )

    return {
        "local_dimension": local_dimension,
        "orbital_count": orbital_count,
        "basis_order": "orbital_major_spin_minor",
        "operator_basis": [element["label"] for element in local_basis],
        "coefficients": coefficients,
    }
