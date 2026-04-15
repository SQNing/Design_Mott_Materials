#!/usr/bin/env python3

import math

import numpy as np


def _serialize_complex(value):
    return {"real": float(np.real(value)), "imag": float(np.imag(value))}


def certify_projector_matrix(matrix, *, tolerance=1.0e-8):
    projector = np.array(matrix, dtype=complex)
    hermitian_part = 0.5 * (projector + projector.conjugate().T)
    eigenvalues = np.linalg.eigvalsh(hermitian_part)
    eigenvalues = np.array(sorted((float(value) for value in eigenvalues), reverse=True), dtype=float)
    dominant = float(eigenvalues[0]) if eigenvalues.size else 0.0
    negativity = float(sum(max(0.0, -value) for value in eigenvalues))
    purity = float(np.real(np.trace(hermitian_part @ hermitian_part)))
    trace_value = complex(np.trace(projector))
    rank_one_residual = float(
        math.sqrt((1.0 - dominant) ** 2 + sum(value * value for value in eigenvalues[1:]))
    )
    certificate = {
        "trace": _serialize_complex(trace_value),
        "trace_residual_upper_bound": float(abs(trace_value - 1.0)),
        "hermiticity_residual_upper_bound": float(np.linalg.norm(projector - projector.conjugate().T)),
        "negativity_residual_upper_bound": float(negativity),
        "purity_residual_upper_bound": float(abs(purity - 1.0)),
        "rank_one_residual_upper_bound": rank_one_residual,
        "dominant_eigenvalue_lower_bound": float(dominant),
        "eigenvalues": [float(value) for value in eigenvalues],
    }
    certificate["status"] = (
        "certified"
        if certificate["trace_residual_upper_bound"] <= float(tolerance)
        and certificate["hermiticity_residual_upper_bound"] <= float(tolerance)
        and certificate["negativity_residual_upper_bound"] <= float(tolerance)
        and certificate["purity_residual_upper_bound"] <= float(tolerance)
        and certificate["rank_one_residual_upper_bound"] <= float(tolerance)
        else "refuted"
    )
    return certificate


def certify_projector_collection(matrices, *, tolerance=1.0e-8):
    certificates = [certify_projector_matrix(matrix, tolerance=tolerance) for matrix in matrices]
    if not certificates:
        return {"status": "inconclusive", "sites": []}
    aggregate = {
        "status": "certified" if all(item["status"] == "certified" for item in certificates) else "refuted",
        "sites": certificates,
        "trace_residual_upper_bound": max(item["trace_residual_upper_bound"] for item in certificates),
        "hermiticity_residual_upper_bound": max(item["hermiticity_residual_upper_bound"] for item in certificates),
        "negativity_residual_upper_bound": max(item["negativity_residual_upper_bound"] for item in certificates),
        "purity_residual_upper_bound": max(item["purity_residual_upper_bound"] for item in certificates),
        "rank_one_residual_upper_bound": max(item["rank_one_residual_upper_bound"] for item in certificates),
    }
    return aggregate
