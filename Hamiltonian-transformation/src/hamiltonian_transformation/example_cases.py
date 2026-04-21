from __future__ import annotations

import numpy as np

from .spin_abstract import build_standard_spin_matrices


def build_abstract_spin_only_demo_case() -> dict[str, object]:
    energies = np.array([0.0, 1.0, 2.0, 9.0], dtype=float)
    retained_eigenvectors = np.eye(4, dtype=complex)[:, :3]

    spin_one_jx, _, _ = build_standard_spin_matrices(1.0)
    operator_dict = {
        "Jx": np.zeros((4, 4), dtype=complex),
        "Jy": np.zeros((4, 4), dtype=complex),
        "Jz": np.zeros((4, 4), dtype=complex),
        "H": np.diag(energies).astype(complex),
        "Mx": np.pad(spin_one_jx, ((0, 1), (0, 1))),
    }

    return {
        "energies": energies,
        "retained_eigenvectors": retained_eigenvectors,
        "operator_dict": operator_dict,
    }
