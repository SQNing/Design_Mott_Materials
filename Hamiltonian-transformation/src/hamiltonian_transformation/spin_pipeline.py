from __future__ import annotations

import numpy as np

from .spin_abstract import build_standard_spin_matrices
from .spin_diagnostics import (
    candidate_spin_from_dimension,
    casimir_eigenvalue_spread,
    compute_isolation_metrics,
    ladder_connectivity_ok,
    su2_cyclic_residuals,
    sz_eigenvalues_match_spin,
)
from .spin_projection import project_operator

DIAGNOSTIC_ATOL = 1e-8


def analyze_low_energy_spin_manifold(
    energies: np.ndarray,
    retained_eigenvectors: np.ndarray,
    operator_dict: dict,
) -> dict[str, object]:
    retained_dim = retained_eigenvectors.shape[1]
    if retained_dim == 0:
        raise ValueError("Cannot analyze spin manifold: retained dimension must be positive.")
    if retained_dim >= len(energies):
        raise ValueError(
            "Cannot compute delta_out: no excluded higher level is available for the retained manifold."
        )
    delta_in, delta_out = compute_isolation_metrics(energies=energies, retained_dim=retained_dim)
    candidate_spin = candidate_spin_from_dimension(retained_dim)
    projected_operators = {
        name: project_operator(np.asarray(operator), retained_eigenvectors)
        for name, operator in operator_dict.items()
    }
    result: dict[str, object] = {
        "delta_in": delta_in,
        "delta_out": delta_out,
        "candidate_spin": candidate_spin,
        "projected_operators": projected_operators,
    }

    jx = projected_operators.get("Jx")
    jy = projected_operators.get("Jy")
    jz = projected_operators.get("Jz")
    has_required_generators = jx is not None and jy is not None and jz is not None
    if not has_required_generators:
        result["physical_diagnostics"] = {
            "available": False,
            "reason": "missing_required_generators",
            "criteria_pass": None,
        }
        result["decision"] = "generic_multiplet"
        return result

    r_xy, r_yz, r_zx = su2_cyclic_residuals(jx, jy, jz)
    casimir_spread = casimir_eigenvalue_spread(jx, jy, jz)
    sz_match = sz_eigenvalues_match_spin(jz, spin=candidate_spin, atol=DIAGNOSTIC_ATOL)
    ladder_ok = ladder_connectivity_ok(jx, jy, jz, atol=DIAGNOSTIC_ATOL)
    physical_criteria_pass = (
        max(r_xy, r_yz, r_zx) <= DIAGNOSTIC_ATOL
        and casimir_spread <= DIAGNOSTIC_ATOL
        and sz_match
        and ladder_ok
    )
    result["physical_diagnostics"] = {
        "available": True,
        "commutator_residuals": {"xy": r_xy, "yz": r_yz, "zx": r_zx},
        "casimir_eigenvalue_spread": casimir_spread,
        "sz_spectrum_match": sz_match,
        "ladder_connectivity_ok": ladder_ok,
        "criteria_pass": physical_criteria_pass,
    }

    if physical_criteria_pass:
        result["decision"] = "physical_spin"
        return result

    abstract_jx, abstract_jy, abstract_jz = build_standard_spin_matrices(candidate_spin)
    result["decision"] = "abstract_spin_only"
    result["abstract_spin_operators"] = {
        "Jx": abstract_jx,
        "Jy": abstract_jy,
        "Jz": abstract_jz,
    }
    return result
