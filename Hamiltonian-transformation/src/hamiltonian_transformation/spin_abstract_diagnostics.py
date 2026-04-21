from __future__ import annotations

import numpy as np

from .spin_abstract import build_standard_spin_matrices

ABSTRACT_HAMILTONIAN_REL_TOL = 1e-8
ABSTRACT_OBSERVABLE_REL_TOL = 1e-8
ABSTRACT_ZERO_NORM_ATOL = 1e-12
ABSTRACT_COEFFICIENT_IMAG_ATOL = 1e-10


def _identity_like(operator: np.ndarray) -> np.ndarray:
    dim = operator.shape[0]
    return np.eye(dim, dtype=complex)


def build_hamiltonian_basis(
    candidate_spin: float,
    abstract_spin_operators: dict[str, np.ndarray] | None = None,
) -> tuple[str, dict[str, np.ndarray]]:
    if abstract_spin_operators is None:
        jx, jy, jz = build_standard_spin_matrices(candidate_spin)
        abstract_spin_operators = {"Jx": jx, "Jy": jy, "Jz": jz}

    jx = np.asarray(abstract_spin_operators["Jx"], dtype=complex)
    jy = np.asarray(abstract_spin_operators["Jy"], dtype=complex)
    jz = np.asarray(abstract_spin_operators["Jz"], dtype=complex)
    basis: dict[str, np.ndarray] = {"I": _identity_like(jx)}

    if np.isclose(candidate_spin, 0.0, atol=ABSTRACT_ZERO_NORM_ATOL):
        return "identity_only", basis

    basis["Jx"] = jx
    basis["Jy"] = jy
    basis["Jz"] = jz

    if candidate_spin < 1.0 and not np.isclose(candidate_spin, 1.0, atol=ABSTRACT_ZERO_NORM_ATOL):
        return "linear", basis

    basis["Q1"] = jx @ jx - jy @ jy
    basis["Q2"] = (2.0 * (jz @ jz) - (jx @ jx) - (jy @ jy)) / np.sqrt(3.0)
    basis["Q3"] = jx @ jy + jy @ jx
    basis["Q4"] = jy @ jz + jz @ jy
    basis["Q5"] = jz @ jx + jx @ jz
    return "linear_plus_quadrupolar", basis


def fit_real_hermitian_expansion(
    target: np.ndarray,
    basis: dict[str, np.ndarray],
) -> tuple[dict[str, float], float, float]:
    target_matrix = np.asarray(target, dtype=complex)
    basis_items = list(basis.items())
    design_matrix = np.column_stack([matrix.reshape(-1) for _, matrix in basis_items])
    target_vector = target_matrix.reshape(-1)
    coefficients, *_ = np.linalg.lstsq(design_matrix, target_vector, rcond=None)

    if np.any(np.abs(coefficients.imag) > ABSTRACT_COEFFICIENT_IMAG_ATOL):
        raise ValueError("coefficient_not_real_within_tolerance")

    real_coefficients = coefficients.real.astype(float)
    fitted = sum(value * matrix for value, (_, matrix) in zip(real_coefficients, basis_items))
    absolute_residual = float(np.linalg.norm(target_matrix - fitted))
    target_norm = float(np.linalg.norm(target_matrix))
    if target_norm > ABSTRACT_ZERO_NORM_ATOL:
        relative_residual = absolute_residual / target_norm
    else:
        relative_residual = absolute_residual

    coefficient_map = {
        name: float(value) for value, (name, _) in zip(real_coefficients, basis_items)
    }
    return coefficient_map, absolute_residual, relative_residual


def analyze_hamiltonian_closure(
    candidate_spin: float,
    abstract_spin_operators: dict[str, np.ndarray],
    h_low: np.ndarray,
    target_source: str,
) -> dict[str, object]:
    basis_name, basis = build_hamiltonian_basis(
        candidate_spin=candidate_spin,
        abstract_spin_operators=abstract_spin_operators,
    )
    coefficients, absolute_residual, relative_residual = fit_real_hermitian_expansion(
        target=np.asarray(h_low, dtype=complex),
        basis=basis,
    )
    return {
        "available": True,
        "target_source": target_source,
        "basis_name": basis_name,
        "basis_size": len(basis),
        "absolute_residual": absolute_residual,
        "relative_residual": relative_residual,
        "coefficients": coefficients,
        "status": "pass" if relative_residual <= ABSTRACT_HAMILTONIAN_REL_TOL else "fail",
    }


def analyze_observable_closure(
    abstract_spin_operators: dict[str, np.ndarray],
    projected_observables: dict[str, np.ndarray],
) -> dict[str, object]:
    supported_names = ["Mx", "My", "Mz"]
    tested_names = [name for name in supported_names if name in projected_observables]
    if not tested_names:
        return {
            "available": False,
            "reason": "missing_supported_observables",
        }

    basis = {
        "Jx": np.asarray(abstract_spin_operators["Jx"], dtype=complex),
        "Jy": np.asarray(abstract_spin_operators["Jy"], dtype=complex),
        "Jz": np.asarray(abstract_spin_operators["Jz"], dtype=complex),
    }
    tested_observables: dict[str, dict[str, object]] = {}
    for name in tested_names:
        try:
            coefficients, absolute_residual, relative_residual = fit_real_hermitian_expansion(
                target=np.asarray(projected_observables[name], dtype=complex),
                basis=basis,
            )
            status = "pass" if relative_residual <= ABSTRACT_OBSERVABLE_REL_TOL else "fail"
        except ValueError as exc:
            coefficients = {basis_name: 0.0 for basis_name in basis}
            absolute_residual = float("inf")
            relative_residual = float("inf")
            status = "fail"
            tested_observables[name] = {
                "absolute_residual": absolute_residual,
                "relative_residual": relative_residual,
                "coefficients": coefficients,
                "status": status,
                "fit_error": str(exc),
            }
            continue

        tested_observables[name] = {
            "absolute_residual": absolute_residual,
            "relative_residual": relative_residual,
            "coefficients": coefficients,
            "status": status,
        }

    status = (
        "pass"
        if all(item["status"] == "pass" for item in tested_observables.values())
        else "fail"
    )
    return {
        "available": True,
        "supported_names": supported_names,
        "missing_supported_observables": [name for name in supported_names if name not in tested_names],
        "tested_observables": tested_observables,
        "status": status,
    }


def summarize_abstract_diagnostics_status(
    hamiltonian_closure: dict[str, object],
    observable_closure: dict[str, object],
) -> str:
    available_sections = [hamiltonian_closure, observable_closure]
    if any(section.get("available") and section.get("status") == "fail" for section in available_sections):
        return "weak"
    if (
        hamiltonian_closure.get("available")
        and hamiltonian_closure.get("status") == "pass"
        and observable_closure.get("available")
        and observable_closure.get("status") == "pass"
    ):
        return "strong"
    return "unclear"
