from __future__ import annotations

import numpy as np


def compute_isolation_metrics(energies: np.ndarray, retained_dim: int) -> tuple[float, float]:
    delta_in = float(energies[retained_dim - 1] - energies[0])
    delta_out = float(energies[retained_dim] - energies[0])
    return delta_in, delta_out


def candidate_spin_from_dimension(retained_dim: int) -> float:
    if retained_dim <= 0:
        raise ValueError("retained_dim must be positive")
    return (retained_dim - 1) / 2


def commutator_residual(jx: np.ndarray, jy: np.ndarray, jz: np.ndarray) -> float:
    residual = jx @ jy - jy @ jx - 1j * jz
    return float(np.linalg.norm(residual))


def su2_cyclic_residuals(
    jx: np.ndarray, jy: np.ndarray, jz: np.ndarray
) -> tuple[float, float, float]:
    r_xy = commutator_residual(jx, jy, jz)
    r_yz = commutator_residual(jy, jz, jx)
    r_zx = commutator_residual(jz, jx, jy)
    return r_xy, r_yz, r_zx


def projected_casimir(jx: np.ndarray, jy: np.ndarray, jz: np.ndarray) -> np.ndarray:
    return jx @ jx + jy @ jy + jz @ jz


def casimir_eigenvalue_spread(jx: np.ndarray, jy: np.ndarray, jz: np.ndarray) -> float:
    eigenvalues = np.linalg.eigvals(projected_casimir(jx, jy, jz))
    return float(np.max(np.abs(eigenvalues - np.mean(eigenvalues))))


def sz_eigenvalues_match_spin(sz: np.ndarray, spin: float, atol: float = 1e-8) -> bool:
    expected_dim = int(round(2 * spin + 1))
    if sz.shape != (expected_dim, expected_dim):
        return False
    expected = np.linspace(-spin, spin, expected_dim)
    observed = np.linalg.eigvalsh(sz)
    return bool(np.allclose(observed, expected, atol=atol))


def ladder_connectivity_ok(
    jx: np.ndarray, jy: np.ndarray, sz: np.ndarray, atol: float = 1e-8
) -> bool:
    raising = jx + 1j * jy
    eigenvalues, eigenvectors = np.linalg.eigh(sz)
    order = np.argsort(eigenvalues)
    basis = eigenvectors[:, order]
    raising_in_basis = basis.conj().T @ raising @ basis
    n_states = raising_in_basis.shape[0]
    for idx in range(n_states - 1):
        if abs(raising_in_basis[idx + 1, idx]) <= atol:
            return False
    return True
