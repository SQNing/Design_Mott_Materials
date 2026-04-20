#!/usr/bin/env python3
import itertools
import math

import numpy as np


def _complex_from_serialized(value):
    if isinstance(value, dict):
        return complex(float(value.get("real", 0.0)), float(value.get("imag", 0.0)))
    return complex(value)


def _serialize_complex(value):
    return {"real": float(np.real(value)), "imag": float(np.imag(value))}


def _pad_vector(values):
    padded = [float(value) for value in values[:3]]
    while len(padded) < 3:
        padded.append(0.0)
    return padded


def _basis_positions(model, site_count):
    lattice = model.get("lattice", {})
    positions = []
    basis_positions = lattice.get("positions") or []
    for index in range(int(site_count)):
        if basis_positions and index < len(basis_positions):
            position = basis_positions[index]
        elif basis_positions and len(basis_positions) == 1:
            position = basis_positions[0]
        else:
            position = [0.0, 0.0, 0.0]
        positions.append(_pad_vector(position))
    return positions


def _site_count(model, vector_length):
    lattice = model.get("lattice", {})
    explicit = lattice.get("sublattices")
    if explicit is not None:
        return max(1, int(explicit))
    positions = lattice.get("positions") or []
    if positions:
        return max(1, len(positions))
    if int(vector_length) % 3 != 0:
        raise ValueError("component-resolved LT vector length must be divisible by 3")
    return max(1, int(vector_length) // 3)


def _deserialize_modes(relaxed_solution):
    if "eigenspace" in relaxed_solution:
        serialized_modes = relaxed_solution.get("eigenspace") or []
    elif "eigenvector" in relaxed_solution:
        serialized_modes = [relaxed_solution.get("eigenvector") or []]
    else:
        serialized_modes = relaxed_solution.get("modes") or []

    modes = []
    for serialized_mode in serialized_modes:
        mode = np.array([_complex_from_serialized(value) for value in serialized_mode], dtype=complex)
        if mode.size:
            modes.append(mode)
    if not modes:
        raise ValueError("relaxed_solution must include at least one LT mode")
    return modes


def _phase_factor(q_vector, position):
    return np.exp(2.0j * np.pi * float(np.dot(q_vector, position)))


def _reconstruct_spins(model, q, modes, coefficients):
    q_vector = np.array(_pad_vector(q), dtype=float)
    mode_length = len(modes[0])
    site_count = _site_count(model, mode_length)
    positions = _basis_positions(model, site_count)

    combined = np.zeros(mode_length, dtype=complex)
    for coefficient, mode in zip(coefficients, modes):
        combined += complex(coefficient) * mode

    spins = []
    for site_index in range(site_count):
        block = combined[3 * site_index : 3 * (site_index + 1)]
        phase = _phase_factor(q_vector, np.array(positions[site_index], dtype=float))
        spins.append(np.real(block * phase).astype(float))
    return spins


def _site_norms(spins):
    return [float(np.linalg.norm(spin)) for spin in spins]


def _site_norm_residuals(spins):
    residuals = []
    for spin in spins:
        norm_sq = float(np.dot(spin, spin))
        residuals.append(abs(norm_sq - 1.0))
    return residuals


def _strong_constraint_residual(spins):
    total = 0.0
    for spin in spins:
        norm_sq = float(np.dot(spin, spin))
        total += (norm_sq - 1.0) ** 2
    return float(total)


def _normalize_direction(spin):
    vector = np.array(spin, dtype=float)
    norm = float(np.linalg.norm(vector))
    if norm <= 1.0e-12:
        return [0.0, 0.0, 1.0]
    return [float(value) / norm for value in vector]


def _site_frames(spins):
    frames = []
    for index, spin in enumerate(spins):
        frames.append({"site": int(index), "direction": _normalize_direction(spin)})
    return frames


def _serialize_coefficients(coefficients):
    return [_serialize_complex(value) for value in coefficients]


def _serialize_variational_seed(spins, q):
    return {
        "q_vector": _pad_vector(q),
        "site_spins": [[float(component) for component in spin] for spin in spins],
    }


def _candidate_summary(spins, q, coefficients):
    residuals = _site_norm_residuals(spins)
    return {
        "site_frames": _site_frames(spins),
        "site_norms": _site_norms(spins),
        "max_site_norm_residual": float(max(residuals) if residuals else 0.0),
        "strong_constraint_residual": _strong_constraint_residual(spins),
        "combination_coefficients": _serialize_coefficients(coefficients),
        "variational_seed": _serialize_variational_seed(spins, q),
    }


def complete_lt_constraints(relaxed_solution, model, *, tolerance=1.0e-8):
    q_vector = _pad_vector(relaxed_solution.get("q", [0.0, 0.0, 0.0]))
    modes = _deserialize_modes(relaxed_solution)
    mode_length = len(modes[0])
    if any(len(mode) != mode_length for mode in modes):
        raise ValueError("all LT modes in a relaxed solution must have the same length")
    if mode_length % 3 != 0:
        raise ValueError("tensor LT modes must have a length divisible by 3")

    best = None

    def consider(coefficients, status):
        nonlocal best
        spins = _reconstruct_spins(model, q_vector, modes, coefficients)
        summary = _candidate_summary(spins, q_vector, coefficients)
        summary["status"] = status
        if best is None or summary["max_site_norm_residual"] < best["max_site_norm_residual"]:
            best = summary

    for index in range(len(modes)):
        coefficients = [0.0j] * len(modes)
        coefficients[index] = 1.0 + 0.0j
        consider(coefficients, "exact_relaxed_hit")

    if best is not None and best["max_site_norm_residual"] <= tolerance:
        return best

    if len(modes) > 1:
        axis = [-1.0, 0.0, 1.0]
        for candidate in itertools.product(axis, repeat=len(modes)):
            if all(abs(value) <= 1.0e-12 for value in candidate):
                continue
            if sum(abs(value) > 1.0e-12 for value in candidate) <= 1:
                continue
            consider([complex(value) for value in candidate], "completed_from_shell")
            if best is not None and best["max_site_norm_residual"] <= tolerance:
                return best

    if best is None:
        raise ValueError("unable to construct any LT completion candidate")
    best["status"] = "requires_variational_polish"
    return best
