#!/usr/bin/env python3
import itertools
import math
from fractions import Fraction
from math import gcd

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


def _deserialize_mode_descriptors(relaxed_solution):
    descriptors = []
    if isinstance(relaxed_solution.get("minimum_shell"), dict):
        for sector_index, sector in enumerate(relaxed_solution.get("minimum_shell", {}).get("sectors", [])):
            q_vector = _pad_vector(sector.get("q", relaxed_solution.get("q", [0.0, 0.0, 0.0])))
            serialized_modes = sector.get("eigenspace") or sector.get("modes") or []
            if not serialized_modes and sector.get("eigenvector"):
                serialized_modes = [sector.get("eigenvector")]
            for mode_index, serialized_mode in enumerate(serialized_modes):
                mode = np.array([_complex_from_serialized(value) for value in serialized_mode], dtype=complex)
                if mode.size:
                    descriptors.append(
                        {
                            "q": q_vector,
                            "mode": mode,
                            "sector_index": int(sector_index),
                            "mode_index": int(mode_index),
                        }
                    )
    else:
        q_vector = _pad_vector(relaxed_solution.get("q", [0.0, 0.0, 0.0]))
        if "eigenspace" in relaxed_solution:
            serialized_modes = relaxed_solution.get("eigenspace") or []
        elif "eigenvector" in relaxed_solution:
            serialized_modes = [relaxed_solution.get("eigenvector") or []]
        else:
            serialized_modes = relaxed_solution.get("modes") or []
        for mode_index, serialized_mode in enumerate(serialized_modes):
            mode = np.array([_complex_from_serialized(value) for value in serialized_mode], dtype=complex)
            if mode.size:
                descriptors.append(
                    {
                        "q": q_vector,
                        "mode": mode,
                        "sector_index": 0,
                        "mode_index": int(mode_index),
                    }
                )
    if not descriptors:
        raise ValueError("relaxed_solution must include at least one LT mode")
    return descriptors


def _phase_factor(q_vector, position):
    return np.exp(2.0j * np.pi * float(np.dot(q_vector, position)))


def _combined_single_q_mode(mode_descriptors, coefficients):
    combined = np.zeros(len(mode_descriptors[0]["mode"]), dtype=complex)
    for coefficient, descriptor in zip(coefficients, mode_descriptors):
        combined += complex(coefficient) * descriptor["mode"]
    return combined


def _mode_q_key(q_vector, *, tolerance=1.0e-8):
    values = []
    for value in _pad_vector(q_vector):
        reduced = float(value) % 1.0
        if abs(reduced - 1.0) <= tolerance:
            reduced = 0.0
        values.append(round(reduced, 8))
    return tuple(values)


def _unique_q_vectors(mode_descriptors):
    unique = []
    seen = set()
    for descriptor in mode_descriptors:
        key = _mode_q_key(descriptor["q"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(_pad_vector(descriptor["q"]))
    return unique


def _reconstruct_spins_for_positions(model, mode_descriptors, coefficients, positions):
    mode_length = len(mode_descriptors[0]["mode"])
    site_count = _site_count(model, mode_length)
    spins = []
    for site_index in range(site_count):
        position = np.array(positions[site_index], dtype=float)
        spin = np.zeros(3, dtype=float)
        for coefficient, descriptor in zip(coefficients, mode_descriptors):
            block = descriptor["mode"][3 * site_index : 3 * (site_index + 1)]
            phase = _phase_factor(np.array(_pad_vector(descriptor["q"]), dtype=float), position)
            spin += np.real(complex(coefficient) * block * phase).astype(float)
        spins.append(spin)
    return spins


def _lcm(left, right):
    left = int(left)
    right = int(right)
    if left == 0 or right == 0:
        return max(abs(left), abs(right))
    return abs(left * right) // gcd(left, right)


def _rationalize_q_vector(q_vector, *, tolerance=1.0e-8, max_denominator=256):
    rational = []
    for component in _pad_vector(q_vector):
        value = float(component) % 1.0
        if abs(value) <= tolerance or abs(value - 1.0) <= tolerance:
            rational.append({"numerator": 0, "denominator": 1, "value": 0.0})
            continue
        fraction = Fraction(value).limit_denominator(int(max_denominator))
        reduced = float(fraction)
        if abs(reduced - value) > tolerance:
            return None
        rational.append(
            {
                "numerator": int(fraction.numerator),
                "denominator": int(fraction.denominator),
                "value": reduced,
            }
        )
    return rational


def _minimal_commensurate_supercell_shape_for_q_vectors(q_vectors, *, tolerance=1.0e-8, max_denominator=256):
    shape = [1, 1, 1]
    for q_vector in q_vectors:
        rational_q = _rationalize_q_vector(q_vector, tolerance=tolerance, max_denominator=max_denominator)
        if rational_q is None:
            return None
        for axis, component in enumerate(rational_q):
            numerator = int(component["numerator"])
            denominator = int(component["denominator"])
            if numerator != 0:
                shape[axis] = _lcm(shape[axis], denominator)
    return shape


def _magnetic_cells(supercell_shape):
    for cell_x in range(int(supercell_shape[0])):
        for cell_y in range(int(supercell_shape[1])):
            for cell_z in range(int(supercell_shape[2])):
                yield [cell_x, cell_y, cell_z]


def _norm_sq_samples(model, mode_descriptors, coefficients, *, tolerance=1.0e-8):
    mode_length = len(mode_descriptors[0]["mode"])
    site_count = _site_count(model, mode_length)
    positions = _basis_positions(model, site_count)
    unique_q = _unique_q_vectors(mode_descriptors)
    supercell_shape = _minimal_commensurate_supercell_shape_for_q_vectors(unique_q, tolerance=tolerance)

    if supercell_shape is not None:
        samples = []
        for cell in _magnetic_cells(supercell_shape):
            orbit_positions = []
            for site_index in range(site_count):
                orbit_positions.append(
                    np.array(cell, dtype=float) + np.array(positions[site_index], dtype=float)
                )
            spins = _reconstruct_spins_for_positions(model, mode_descriptors, coefficients, orbit_positions)
            for spin in spins:
                samples.append(float(np.dot(spin, spin)))
        return samples, supercell_shape

    if len(unique_q) == 1:
        combined = _combined_single_q_mode(mode_descriptors, coefficients)
        samples = []
        for site_index in range(site_count):
            block = combined[3 * site_index : 3 * (site_index + 1)]
            real_part = np.real(block)
            imag_part = np.imag(block)
            samples.append(0.5 * float(np.dot(real_part, real_part) + np.dot(imag_part, imag_part)))
        return samples, None

    return None, None


def _normalize_coefficients_for_spin_length(model, mode_descriptors, coefficients, *, tolerance=1.0e-8):
    norm_sq_samples, _supercell_shape = _norm_sq_samples(
        model,
        mode_descriptors,
        coefficients,
        tolerance=tolerance,
    )
    if not norm_sq_samples:
        return None
    numerator = float(sum(norm_sq_samples))
    denominator = float(sum(value * value for value in norm_sq_samples))
    if denominator <= tolerance or numerator <= tolerance:
        return None
    scale = math.sqrt(numerator / denominator)
    return [complex(scale) * complex(value) for value in coefficients]


def _pairwise_isotropic_completion_coefficients(mode_descriptors, *, tolerance=1.0e-12):
    shell_size = len(mode_descriptors)
    for left in range(shell_size):
        for right in range(left + 1, shell_size):
            left_mode = np.array(mode_descriptors[left]["mode"], dtype=complex)
            right_mode = np.array(mode_descriptors[right]["mode"], dtype=complex)
            g_left_left = complex(np.dot(left_mode, left_mode))
            g_left_right = complex(np.dot(left_mode, right_mode))
            g_right_right = complex(np.dot(right_mode, right_mode))

            if abs(g_right_right) <= tolerance:
                continue

            discriminant = g_left_right * g_left_right - g_right_right * g_left_left
            roots = [
                (-g_left_right + np.lib.scimath.sqrt(discriminant)) / g_right_right,
                (-g_left_right - np.lib.scimath.sqrt(discriminant)) / g_right_right,
            ]
            for root in roots:
                candidate = [0.0j] * shell_size
                candidate[left] = 1.0 + 0.0j
                candidate[right] = complex(root)
                yield candidate


def _translation_orbit_norm_residuals(model, mode_descriptors, coefficients, *, tolerance=1.0e-8):
    mode_length = len(mode_descriptors[0]["mode"])
    site_count = _site_count(model, mode_length)
    positions = _basis_positions(model, site_count)
    unique_q = _unique_q_vectors(mode_descriptors)
    supercell_shape = _minimal_commensurate_supercell_shape_for_q_vectors(unique_q, tolerance=tolerance)
    site_residuals = [0.0 for _ in range(site_count)]

    if supercell_shape is not None:
        for cell in _magnetic_cells(supercell_shape):
            orbit_positions = []
            for site_index in range(site_count):
                orbit_positions.append(
                    np.array(cell, dtype=float) + np.array(positions[site_index], dtype=float)
                )
            spins = _reconstruct_spins_for_positions(model, mode_descriptors, coefficients, orbit_positions)
            for site_index, spin in enumerate(spins):
                norm_sq = float(np.dot(spin, spin))
                site_residuals[site_index] = max(site_residuals[site_index], abs(norm_sq - 1.0))
        return {
            "site_residuals": [float(value) for value in site_residuals],
            "supercell_shape": [int(value) for value in supercell_shape],
            "phase_orbit_kind": "commensurate-supercell",
        }

    if len(unique_q) == 1:
        combined = _combined_single_q_mode(mode_descriptors, coefficients)
        for site_index in range(site_count):
            block = combined[3 * site_index : 3 * (site_index + 1)]
            real_part = np.real(block)
            imag_part = np.imag(block)
            real_norm_sq = float(np.dot(real_part, real_part))
            imag_norm_sq = float(np.dot(imag_part, imag_part))
            cross_term = float(np.dot(real_part, imag_part))
            offset = 0.5 * (real_norm_sq + imag_norm_sq) - 1.0
            cosine = 0.5 * (real_norm_sq - imag_norm_sq)
            sine = -cross_term
            site_residuals[site_index] = abs(offset) + math.sqrt(cosine * cosine + sine * sine)
        return {
            "site_residuals": [float(value) for value in site_residuals],
            "supercell_shape": None,
            "phase_orbit_kind": "dense-phase-fallback",
        }

    return {
        "site_residuals": [1.0 for _ in site_residuals],
        "supercell_shape": None,
        "phase_orbit_kind": "unsupported-multisector-dense",
    }


def _site_norms(spins):
    return [float(np.linalg.norm(spin)) for spin in spins]


def _site_norm_residuals(spins):
    residuals = []
    for spin in spins:
        norm_sq = float(np.dot(spin, spin))
        residuals.append(abs(norm_sq - 1.0))
    return residuals


def _normalize_direction(spin):
    vector = np.array(spin, dtype=float)
    norm = float(np.linalg.norm(vector))
    if norm <= 1.0e-12:
        return [0.0, 0.0, 1.0]
    return [float(value) / norm for value in vector]


def _site_frames(spins):
    return [{"site": int(index), "direction": _normalize_direction(spin)} for index, spin in enumerate(spins)]


def _serialize_coefficients(coefficients):
    return [_serialize_complex(value) for value in coefficients]


def _serialize_variational_seed(model, mode_descriptors, coefficients):
    unique_q = _unique_q_vectors(mode_descriptors)
    positions = _basis_positions(model, _site_count(model, len(mode_descriptors[0]["mode"])))
    if len(unique_q) == 1:
        spins = _reconstruct_spins_for_positions(model, mode_descriptors, coefficients, positions)
        return {
            "kind": "single_q",
            "q_vector": _pad_vector(unique_q[0]),
            "site_spins": [[float(component) for component in spin] for spin in spins],
        }

    supercell_shape = _minimal_commensurate_supercell_shape_for_q_vectors(unique_q)
    if supercell_shape is None:
        return {"kind": "unsupported-multisector"}

    site_spins = []
    for cell in _magnetic_cells(supercell_shape):
        orbit_positions = []
        for site_index in range(len(positions)):
            orbit_positions.append(np.array(cell, dtype=float) + np.array(positions[site_index], dtype=float))
        spins = _reconstruct_spins_for_positions(model, mode_descriptors, coefficients, orbit_positions)
        for site_index, spin in enumerate(spins):
            site_spins.append(
                {
                    "cell": [int(value) for value in cell],
                    "site": int(site_index),
                    "spin": [float(component) for component in spin],
                }
            )
    return {
        "kind": "explicit_supercell",
        "supercell_shape": [int(value) for value in supercell_shape],
        "site_spins": site_spins,
    }


def _candidate_summary(model, mode_descriptors, coefficients):
    positions = _basis_positions(model, _site_count(model, len(mode_descriptors[0]["mode"])))
    spins = _reconstruct_spins_for_positions(model, mode_descriptors, coefficients, positions)
    residuals = _site_norm_residuals(spins)
    translation_orbit = _translation_orbit_norm_residuals(model, mode_descriptors, coefficients)
    total_site_residuals = [
        max(float(local_residual), float(translation_residual))
        for local_residual, translation_residual in zip(residuals, translation_orbit["site_residuals"])
    ]
    return {
        "site_frames": _site_frames(spins),
        "site_norms": _site_norms(spins),
        "max_site_norm_residual": float(max(total_site_residuals) if total_site_residuals else 0.0),
        "strong_constraint_residual": float(sum(value * value for value in total_site_residuals)),
        "combination_coefficients": _serialize_coefficients(coefficients),
        "variational_seed": _serialize_variational_seed(model, mode_descriptors, coefficients),
        "translation_orbit": translation_orbit,
        "shell_sector_count": int(len(unique_q := _unique_q_vectors(mode_descriptors))),
        "shell_q_vectors": [_pad_vector(q_vector) for q_vector in unique_q],
    }


def complete_lt_constraints(relaxed_solution, model, *, tolerance=1.0e-8):
    mode_descriptors = _deserialize_mode_descriptors(relaxed_solution)
    mode_length = len(mode_descriptors[0]["mode"])
    if any(len(descriptor["mode"]) != mode_length for descriptor in mode_descriptors):
        raise ValueError("all LT modes in a relaxed solution must have the same length")
    if mode_length % 3 != 0:
        raise ValueError("tensor LT modes must have a length divisible by 3")

    best = None

    def consider(coefficients, status):
        nonlocal best
        summary = _candidate_summary(model, mode_descriptors, coefficients)
        summary["status"] = status
        if best is None or summary["max_site_norm_residual"] < best["max_site_norm_residual"]:
            best = summary

    for index in range(len(mode_descriptors)):
        coefficients = [0.0j] * len(mode_descriptors)
        coefficients[index] = 1.0 + 0.0j
        normalized = _normalize_coefficients_for_spin_length(
            model,
            mode_descriptors,
            coefficients,
            tolerance=tolerance,
        )
        if normalized is None:
            continue
        consider(normalized, "exact_relaxed_hit")

    if best is not None and best["max_site_norm_residual"] <= tolerance:
        return best

    grouped = {}
    for index, descriptor in enumerate(mode_descriptors):
        grouped.setdefault(_mode_q_key(descriptor["q"]), []).append(index)

    for indices in grouped.values():
        if len(indices) <= 1:
            continue
        local_descriptors = [mode_descriptors[index] for index in indices]
        for local_coefficients in _pairwise_isotropic_completion_coefficients(local_descriptors, tolerance=tolerance):
            coefficients = [0.0j] * len(mode_descriptors)
            for local_index, global_index in enumerate(indices):
                coefficients[global_index] = local_coefficients[local_index]
            normalized = _normalize_coefficients_for_spin_length(
                model,
                mode_descriptors,
                coefficients,
                tolerance=tolerance,
            )
            if normalized is None:
                continue
            consider(normalized, "completed_from_shell")
            if best is not None and best["max_site_norm_residual"] <= tolerance:
                return best

    axis = [-1.0, 0.0, 1.0, 1.0j, -1.0j]
    if len(mode_descriptors) <= 6:
        for candidate in itertools.product(axis, repeat=len(mode_descriptors)):
            if all(abs(value) <= 1.0e-12 for value in candidate):
                continue
            if sum(abs(value) > 1.0e-12 for value in candidate) <= 1:
                continue
            normalized = _normalize_coefficients_for_spin_length(
                model,
                mode_descriptors,
                [complex(value) for value in candidate],
                tolerance=tolerance,
            )
            if normalized is None:
                continue
            consider(normalized, "completed_from_shell")
            if best is not None and best["max_site_norm_residual"] <= tolerance:
                return best

    if best is None and isinstance(relaxed_solution.get("minimum_shell"), dict):
        fallback_solution = {"q": relaxed_solution.get("q", [0.0, 0.0, 0.0])}
        if relaxed_solution.get("eigenspace"):
            fallback_solution["eigenspace"] = relaxed_solution.get("eigenspace")
        elif relaxed_solution.get("eigenvector"):
            fallback_solution["eigenvector"] = relaxed_solution.get("eigenvector")
        if fallback_solution.get("eigenspace") or fallback_solution.get("eigenvector"):
            fallback = complete_lt_constraints(fallback_solution, model, tolerance=tolerance)
            fallback["shell_fallback"] = {
                "status": "single-q-fallback",
                "from_minimum_shell": True,
            }
            return fallback

    if best is None:
        raise ValueError("unable to construct any LT completion candidate")
    best["status"] = "requires_variational_polish"
    return best
