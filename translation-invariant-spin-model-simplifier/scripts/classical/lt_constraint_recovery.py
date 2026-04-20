#!/usr/bin/env python3
import fractions
import math

import numpy as np

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from classical.lt_tensor_constraint_completion import complete_lt_constraints
else:
    from .lt_tensor_constraint_completion import complete_lt_constraints


def reconstruct_single_q_real_space_state(positions, q, amplitudes):
    q_vector = np.array([float(value) for value in q], dtype=float)
    while len(q_vector) < 3:
        q_vector = np.append(q_vector, 0.0)

    spins = []
    for position, amplitude in zip(positions, amplitudes):
        position_vector = np.array([float(value) for value in position], dtype=float)
        while len(position_vector) < 3:
            position_vector = np.append(position_vector, 0.0)
        phase = 2.0 * math.pi * float(np.dot(q_vector, position_vector))
        complex_spin = amplitude * np.exp(1j * phase)
        spins.append(np.array([float(np.real(complex_spin)), float(np.imag(complex_spin)), 0.0]))
    return spins


def strong_constraint_residual(spins):
    residual = 0.0
    for spin in spins:
        norm_sq = float(np.dot(spin, spin))
        residual += (norm_sq - 1.0) ** 2
    return float(residual)


def _normalize_direction(spin):
    vector = np.array(spin, dtype=float)
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        return [0.0, 0.0, 1.0], 0.0
    return [float(value) / norm for value in vector], norm


def _pad_vector(values):
    padded = [float(value) for value in values[:3]]
    while len(padded) < 3:
        padded.append(0.0)
    return padded


def _complex_from_serialized(value):
    if isinstance(value, dict):
        return complex(float(value.get("real", 0.0)), float(value.get("imag", 0.0)))
    return complex(value)


def _basis_positions(model, site_count):
    lattice = model.get("lattice", {})
    positions = []
    for index in range(site_count):
        basis_positions = lattice.get("positions") or []
        if basis_positions and index < len(basis_positions):
            position = basis_positions[index]
        elif basis_positions and len(basis_positions) == 1:
            position = basis_positions[0]
        else:
            position = [0.0, 0.0, 0.0]
        positions.append(_pad_vector(position))
    return positions


def _infer_ordering_kind(q, tolerance=1e-6, max_denominator=12):
    q_vector = _pad_vector(q)
    for value in q_vector:
        if abs(value) <= tolerance:
            continue
        fraction = fractions.Fraction(value).limit_denominator(max_denominator)
        if abs(float(fraction) - value) > tolerance:
            return "incommensurate"
    return "commensurate"


def recover_classical_state_from_lt(model, q, amplitudes, spin_length=0.5, source="lt"):
    padded_q = _pad_vector(q)
    padded_amplitudes = [_complex_from_serialized(value) for value in amplitudes]
    model_site_count = max(
        int(model.get("lattice", {}).get("sublattices", 0) or 0),
        len(model.get("lattice", {}).get("positions") or []),
        1,
    )
    if len(padded_amplitudes) == 3 * model_site_count:
        completion = complete_lt_constraints({"q": padded_q, "eigenspace": [padded_amplitudes]}, model)
        site_frames = []
        for frame in completion["site_frames"]:
            site_frames.append(
                {
                    "site": int(frame["site"]),
                    "spin_length": float(spin_length),
                    "direction": list(frame["direction"]),
                }
            )
        return {
            "site_frames": site_frames,
            "ordering": {
                "kind": _infer_ordering_kind(padded_q),
                "q_vector": padded_q,
            },
            "constraint_recovery": {
                "source": str(source),
                "reconstruction": "tensor-single-q",
                "status": completion["status"],
                "strong_constraint_residual": completion["strong_constraint_residual"],
                "max_site_norm_residual": completion["max_site_norm_residual"],
                "site_norms": completion["site_norms"],
                "combination_coefficients": completion["combination_coefficients"],
                "variational_seed": completion["variational_seed"],
            },
        }

    site_count = max(len(padded_amplitudes), model_site_count, 1)
    positions = _basis_positions(model, site_count)
    while len(padded_amplitudes) < site_count:
        padded_amplitudes.append(0.0 + 0.0j)

    spins = reconstruct_single_q_real_space_state(positions, padded_q, padded_amplitudes)
    site_frames = []
    site_norms = []
    for index, spin in enumerate(spins):
        direction, norm = _normalize_direction(spin)
        site_frames.append(
            {
                "site": int(index),
                "spin_length": float(spin_length),
                "direction": direction,
            }
        )
        site_norms.append(float(norm))

    return {
        "site_frames": site_frames,
        "ordering": {
            "kind": _infer_ordering_kind(padded_q),
            "q_vector": padded_q,
        },
        "constraint_recovery": {
            "source": str(source),
            "reconstruction": "single-q",
            "strong_constraint_residual": strong_constraint_residual(spins),
            "site_norms": site_norms,
        },
    }
