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


def normalize_local_space_mode(local_space_mode):
    if local_space_mode is None:
        return "auto"
    normalized = str(local_space_mode).strip().lower().replace("_", "-")
    if normalized not in {"auto", "orbital-times-spin", "generic-multiplet"}:
        raise ValueError(
            "local_space_mode must be one of 'auto', 'orbital-times-spin', or 'generic-multiplet'"
        )
    return normalized


def resolve_local_space_spec(local_dimension, local_space_mode="auto", orbital_count=None):
    local_dimension = int(local_dimension)
    if local_dimension <= 0:
        raise ValueError("local_dimension must be positive")

    normalized_mode = normalize_local_space_mode(local_space_mode)
    if normalized_mode == "auto":
        if orbital_count is not None:
            normalized_mode = "orbital-times-spin"
        elif local_dimension % 2 == 0:
            normalized_mode = "orbital-times-spin"
        else:
            normalized_mode = "generic-multiplet"

    if normalized_mode == "orbital-times-spin":
        inferred_orbital_count = infer_orbital_count(local_dimension)
        if orbital_count is None:
            orbital_count = inferred_orbital_count
        orbital_count = int(orbital_count)
        if orbital_count != inferred_orbital_count:
            raise ValueError("orbital_count is inconsistent with the inferred local dimension")
        return {
            "mode": normalized_mode,
            "kind": "orbital_times_spin",
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "local_basis_kind": "orbital_times_spin",
            "matrix_construction": "kron(orbital, spin)",
            "local_dimension": local_dimension,
            "orbital_count": orbital_count,
            "spin_dimension": 2,
        }

    if orbital_count is not None:
        raise ValueError("orbital_count cannot be specified for generic-multiplet local spaces")
    return {
        "mode": normalized_mode,
        "kind": "generic_multiplet",
        "basis_order": "retained_state_index",
        "pair_basis_order": "site_i_major_site_j_minor",
        "local_basis_kind": "generic_multiplet",
        "matrix_construction": "local_generator_basis",
        "local_dimension": local_dimension,
        "multiplet_dimension": local_dimension,
    }


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
    return _single_factor_generator_basis(orbital_count, prefix="orbital")


def _single_factor_generator_basis(local_dimension, prefix):
    local_dimension = int(local_dimension)
    if local_dimension <= 0:
        raise ValueError("local_dimension must be positive")

    identity = np.eye(local_dimension, dtype=complex) / math.sqrt(float(local_dimension))
    basis = [{"label": f"{prefix}_I", "matrix": identity}]

    for left in range(local_dimension):
        for right in range(left + 1, local_dimension):
            sym = np.zeros((local_dimension, local_dimension), dtype=complex)
            sym[left, right] = 1.0
            sym[right, left] = 1.0
            basis.append(
                {
                    "label": f"{prefix}_SYM_{left + 1}_{right + 1}",
                    "matrix": sym / math.sqrt(2.0),
                }
            )

            asym = np.zeros((local_dimension, local_dimension), dtype=complex)
            asym[left, right] = -1.0j
            asym[right, left] = 1.0j
            basis.append(
                {
                    "label": f"{prefix}_ASYM_{left + 1}_{right + 1}",
                    "matrix": asym / math.sqrt(2.0),
                }
            )

    for rank in range(1, local_dimension):
        diag = np.zeros((local_dimension, local_dimension), dtype=complex)
        for index in range(rank):
            diag[index, index] = 1.0
        diag[rank, rank] = -float(rank)
        normalization = math.sqrt(float(rank * (rank + 1)))
        basis.append(
            {
                "label": f"{prefix}_DIAG_{rank}",
                "matrix": diag / normalization,
            }
        )

    return basis


def build_local_operator_basis(local_space_spec_or_orbital_count, local_dimension=None):
    if isinstance(local_space_spec_or_orbital_count, dict):
        spec = dict(local_space_spec_or_orbital_count)
    else:
        orbital_count = int(local_space_spec_or_orbital_count)
        if orbital_count <= 0:
            raise ValueError("orbital_count must be positive")
        inferred_local_dimension = int(local_dimension) if local_dimension is not None else 2 * orbital_count
        spec = resolve_local_space_spec(
            inferred_local_dimension,
            local_space_mode="orbital-times-spin",
            orbital_count=orbital_count,
        )

    if spec["kind"] == "orbital_times_spin":
        orbital_count = int(spec["orbital_count"])
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

    return _single_factor_generator_basis(int(spec["local_dimension"]), prefix="multiplet")


def build_local_basis_labels(local_space_spec):
    if local_space_spec["kind"] == "orbital_times_spin":
        orbital_count = int(local_space_spec["orbital_count"])
        if orbital_count == 1:
            return ["up", "down"]
        labels = []
        for orbital in range(1, orbital_count + 1):
            labels.append(f"up_orb{orbital}")
            labels.append(f"down_orb{orbital}")
        return labels

    return [f"state_{index}" for index in range(1, int(local_space_spec["local_dimension"]) + 1)]


def project_two_site_bond_matrix(
    bond_matrix,
    orbital_count=None,
    coefficient_tolerance=1e-10,
    local_space_mode="auto",
):
    bond_matrix = np.array(bond_matrix, dtype=complex)
    if bond_matrix.ndim != 2 or bond_matrix.shape[0] != bond_matrix.shape[1]:
        raise ValueError("bond_matrix must be a square matrix")

    local_dimension = infer_local_dimension_from_num_wann(bond_matrix.shape[0])
    local_space_spec = resolve_local_space_spec(
        local_dimension,
        local_space_mode=local_space_mode,
        orbital_count=orbital_count,
    )
    local_basis = build_local_operator_basis(local_space_spec)
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
        "basis_order": str(local_space_spec["basis_order"]),
        "pair_basis_order": str(local_space_spec["pair_basis_order"]),
        "factorization": {
            key: value
            for key, value in local_space_spec.items()
            if key not in {"mode", "basis_order", "pair_basis_order", "local_basis_kind", "matrix_construction"}
        },
        "local_basis_kind": str(local_space_spec["local_basis_kind"]),
        "matrix_construction": str(local_space_spec["matrix_construction"]),
        "local_basis_labels": build_local_basis_labels(local_space_spec),
        "operator_basis": [element["label"] for element in local_basis],
        "coefficients": coefficients,
    }
