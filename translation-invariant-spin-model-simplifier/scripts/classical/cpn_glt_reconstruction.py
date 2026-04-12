#!/usr/bin/env python3
import math
from fractions import Fraction
from math import gcd

import numpy as np

try:
    from scipy.optimize import minimize
except ImportError:  # pragma: no cover - scipy is expected in the main environment, but keep a fallback.
    minimize = None


def _serialize_complex(value):
    return {"real": float(np.real(value)), "imag": float(np.imag(value))}


def _serialize_vector(vector):
    return [_serialize_complex(value) for value in vector]


def _normalized_ray(vector):
    ray = np.array(vector, dtype=complex)
    norm = float(np.linalg.norm(ray))
    if norm <= 1.0e-14:
        raise ValueError("local ray must not be zero")
    ray = ray / norm
    for value in ray:
        if abs(value) > 1.0e-12:
            ray = ray / (value / abs(value))
            break
    return ray


def _normalized_real_vector(vector):
    candidate = np.array(vector, dtype=float)
    norm = float(np.linalg.norm(candidate))
    if norm <= 1.0e-14:
        candidate = np.zeros_like(candidate)
        candidate[0] = 1.0
        return candidate
    return candidate / norm


def _projector_exactness(projector, *, tolerance):
    hermitian_part = 0.5 * (projector + projector.conjugate().T)
    eigenvalues, eigenvectors = np.linalg.eigh(hermitian_part)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = np.array(eigenvalues[order], dtype=float)
    eigenvectors = np.array(eigenvectors[:, order], dtype=complex)

    dominant = float(eigenvalues[0]) if eigenvalues.size else 0.0
    negativity = float(sum(max(0.0, -value) for value in eigenvalues))
    purity = float(np.real(np.trace(hermitian_part @ hermitian_part)))
    trace_value = complex(np.trace(projector))
    residual = {
        "trace": trace_value,
        "trace_residual": float(abs(trace_value - 1.0)),
        "hermiticity_residual": float(np.linalg.norm(projector - projector.conjugate().T)),
        "negativity_residual": float(negativity),
        "purity_residual": float(abs(purity - 1.0)),
        "rank_one_residual": float(
            math.sqrt((1.0 - dominant) ** 2 + sum(value * value for value in eigenvalues[1:]))
        ),
        "eigenvalues": [float(value) for value in eigenvalues],
        "dominant_eigenvalue": float(dominant),
        "is_exact_projector_solution": False,
    }
    residual["is_exact_projector_solution"] = bool(
        residual["trace_residual"] <= tolerance
        and residual["hermiticity_residual"] <= tolerance
        and residual["negativity_residual"] <= tolerance
        and residual["purity_residual"] <= tolerance
        and residual["rank_one_residual"] <= tolerance
    )
    return residual, eigenvectors[:, 0] if eigenvectors.size else np.zeros((projector.shape[0],), dtype=complex)


def rationalize_q_vector(q_vector, *, tolerance=1.0e-8, max_denominator=12):
    rational = []
    for component in q_vector:
        value = float(component) % 1.0
        if abs(value - 1.0) <= float(tolerance) or abs(value) <= float(tolerance):
            rational.append({"numerator": 0, "denominator": 1, "value": 0.0})
            continue
        fraction = Fraction(value).limit_denominator(int(max_denominator))
        reduced = float(fraction)
        if abs(reduced - value) > float(tolerance):
            return None
        numerator = int(fraction.numerator)
        denominator = int(fraction.denominator)
        rational.append(
            {
                "numerator": numerator,
                "denominator": denominator,
                "value": float(numerator / denominator),
            }
        )
    return rational


def minimal_commensurate_supercell(rational_q):
    shape = []
    for component in rational_q:
        numerator = int(component["numerator"])
        denominator = int(component["denominator"])
        shape.append(1 if numerator == 0 else denominator)
    return [int(value) for value in shape]


def _lcm(left, right):
    left = int(left)
    right = int(right)
    if left == 0 or right == 0:
        return max(abs(left), abs(right))
    return abs(left * right) // gcd(left, right)


def _combined_commensurate_supercell(rational_qs):
    shape = [1, 1, 1]
    for rational_q in rational_qs:
        sector_shape = minimal_commensurate_supercell(rational_q)
        shape = [_lcm(shape[axis], sector_shape[axis]) for axis in range(3)]
    return [int(value) for value in shape]


def _magnetic_cells(supercell_shape):
    for ix in range(int(supercell_shape[0])):
        for iy in range(int(supercell_shape[1])):
            for iz in range(int(supercell_shape[2])):
                yield [ix, iy, iz]


def _aggregate_exactness(cell_entries):
    if not cell_entries:
        return {
            "trace_residual": 0.0,
            "hermiticity_residual": 0.0,
            "negativity_residual": 0.0,
            "purity_residual": 0.0,
            "rank_one_residual": 0.0,
            "is_exact_projector_solution": False,
            "cells": [],
        }

    return {
        "trace_residual": max(float(entry["trace_residual"]) for entry in cell_entries),
        "hermiticity_residual": max(float(entry["hermiticity_residual"]) for entry in cell_entries),
        "negativity_residual": max(float(entry["negativity_residual"]) for entry in cell_entries),
        "purity_residual": max(float(entry["purity_residual"]) for entry in cell_entries),
        "rank_one_residual": max(float(entry["rank_one_residual"]) for entry in cell_entries),
        "is_exact_projector_solution": all(bool(entry["is_exact_projector_solution"]) for entry in cell_entries),
        "cells": list(cell_entries),
    }


def _score_exactness(aggregate):
    return (
        float(aggregate["rank_one_residual"]),
        float(aggregate["purity_residual"]),
        float(aggregate["negativity_residual"]),
        float(aggregate["trace_residual"]),
        float(aggregate["hermiticity_residual"]),
    )


def _mixing_objective(aggregate):
    return float(
        aggregate["rank_one_residual"] ** 2
        + aggregate["purity_residual"] ** 2
        + aggregate["negativity_residual"] ** 2
        + aggregate["trace_residual"] ** 2
        + aggregate["hermiticity_residual"] ** 2
    )


def _mixing_seed_vectors(shell_dimension):
    seeds = []
    identity = np.eye(int(shell_dimension), dtype=float)
    for index in range(int(shell_dimension)):
        seeds.append(identity[index])
    if int(shell_dimension) >= 2:
        for left in range(int(shell_dimension)):
            for right in range(left + 1, int(shell_dimension)):
                sum_seed = np.zeros((int(shell_dimension),), dtype=float)
                sum_seed[left] = 1.0
                sum_seed[right] = 1.0
                diff_seed = np.zeros((int(shell_dimension),), dtype=float)
                diff_seed[left] = 1.0
                diff_seed[right] = -1.0
                seeds.append(_normalized_real_vector(sum_seed))
                seeds.append(_normalized_real_vector(diff_seed))
    seeds.append(_normalized_real_vector(np.ones((int(shell_dimension),), dtype=float)))
    return seeds


def _build_texture_candidate(
    *,
    basis,
    local_dimension,
    q_values,
    supercell_shape,
    magnetic_site_count,
    mode_vector,
    theta,
    shell_dimension,
    basis_order,
    pair_basis_order,
    projector_tolerance,
    mixing_strategy,
    mixing_coefficients,
):
    radius_mode = np.array(mode_vector, dtype=float)
    local_rays = []
    cell_exactness = []

    traceless_dim = max(0, int(local_dimension) * int(local_dimension) - 1)
    for cell in _magnetic_cells(supercell_shape):
        phase = 2.0 * math.pi * sum(float(q_values[axis]) * float(cell[axis]) for axis in range(3)) + float(theta)
        modulation = math.cos(phase)
        for site_index in range(magnetic_site_count):
            site_mode = modulation * radius_mode[
                site_index * traceless_dim : (site_index + 1) * traceless_dim
            ]
            projector = np.array(basis[0], dtype=complex) / math.sqrt(float(local_dimension))
            if basis.shape[0] > 1:
                projector = projector + np.einsum("m,mab->ab", site_mode, basis[1:], optimize=True)
            projector = 0.5 * (projector + projector.conjugate().T)
            trace_value = complex(np.trace(projector))
            if abs(trace_value) > 1.0e-14:
                projector = projector / trace_value

            exactness, dominant_ray = _projector_exactness(
                projector,
                tolerance=float(projector_tolerance),
            )
            cell_exactness.append(
                {
                    "cell": [int(value) for value in cell],
                    "site": int(site_index),
                    "trace_residual": float(exactness["trace_residual"]),
                    "hermiticity_residual": float(exactness["hermiticity_residual"]),
                    "negativity_residual": float(exactness["negativity_residual"]),
                    "purity_residual": float(exactness["purity_residual"]),
                    "rank_one_residual": float(exactness["rank_one_residual"]),
                    "is_exact_projector_solution": bool(exactness["is_exact_projector_solution"]),
                }
            )
            ray_entry = {
                "cell": [int(value) for value in cell],
                "vector": _serialize_vector(_normalized_ray(dominant_ray)),
            }
            if int(magnetic_site_count) > 1:
                ray_entry["site"] = int(site_index)
            local_rays.append(ray_entry)

    aggregate = _aggregate_exactness(cell_exactness)
    candidate = {
        "status": "exact" if aggregate["is_exact_projector_solution"] else "approximate",
        "lowest_shell_dimension": int(shell_dimension),
        "mixing_strategy": str(mixing_strategy),
        "best_phase": float(theta),
        "mixing_coefficients": [float(value) for value in mixing_coefficients],
        "projector_exactness": aggregate,
        "classical_state": {
            "schema_version": 1,
            "state_kind": "local_rays",
            "manifold": "CP^(N-1)",
            "basis_order": str(basis_order),
            "pair_basis_order": str(pair_basis_order),
            "supercell_shape": [int(value) for value in supercell_shape],
            "local_rays": list(local_rays),
        },
    }
    return candidate


def reconstruct_commensurate_relaxed_shell(
    *,
    basis,
    local_dimension,
    sectors,
    radius_sq,
    basis_order,
    pair_basis_order,
    projector_tolerance=1.0e-8,
    phase_grid_size=32,
    q_tolerance=1.0e-8,
    max_denominator=12,
):
    if not sectors:
        raise ValueError("at least one sector is required for commensurate shell reconstruction")

    rational_qs = []
    normalized_sectors = []
    for sector in sectors:
        q_vector = [float(value) for value in sector.get("q_vector", [0.0, 0.0, 0.0])]
        rational_q = rationalize_q_vector(q_vector, tolerance=q_tolerance, max_denominator=max_denominator)
        if rational_q is None:
            return {
                "status": "incommensurate",
                "reason": "at least one q-sector could not be rationalized within tolerance",
                "ordering": {
                    "kind": "incommensurate-diagnostic",
                    "q_vectors": [list(item.get("q_vector", [0.0, 0.0, 0.0])) for item in sectors],
                },
                "obstruction_report": {
                    "reason": "commensurate supercell could not be inferred for all q-sectors",
                },
            }
        shell_basis = np.array(sector.get("shell_basis", []), dtype=float)
        if shell_basis.ndim == 1:
            shell_basis = shell_basis[:, np.newaxis]
        rational_qs.append(rational_q)
        normalized_sectors.append(
            {
                "q_vector": q_vector,
                "rational_q": rational_q,
                "shell_basis": shell_basis,
                "q_values": [float(component["value"]) for component in rational_q],
                "shell_dimension": int(shell_basis.shape[1]),
            }
        )

    traceless_dim = max(0, int(local_dimension) * int(local_dimension) - 1)
    if traceless_dim <= 0:
        raise ValueError("local_dimension must be at least 1")

    magnetic_site_count = None
    total_shell_dimension = 0
    for sector in normalized_sectors:
        shell_basis = sector["shell_basis"]
        if shell_basis.shape[0] % traceless_dim != 0:
            raise ValueError("shell basis dimension is incompatible with local_dimension")
        sector_site_count = max(1, int(shell_basis.shape[0] // traceless_dim))
        if magnetic_site_count is None:
            magnetic_site_count = sector_site_count
        elif int(magnetic_site_count) != int(sector_site_count):
            raise ValueError("all sectors must use the same magnetic_site_count")
        total_shell_dimension += int(sector["shell_dimension"])

    magnetic_site_count = int(magnetic_site_count or 1)
    supercell_shape = _combined_commensurate_supercell(rational_qs)
    ordering_kind = "commensurate-single-q" if len(normalized_sectors) == 1 else "commensurate-multi-q"
    ordering = {
        "kind": ordering_kind,
        "q_vector": list(normalized_sectors[0]["q_vector"]) if len(normalized_sectors) == 1 else None,
        "q_vectors": [list(sector["q_vector"]) for sector in normalized_sectors],
        "supercell_shape": [int(value) for value in supercell_shape],
    }

    radius = math.sqrt(max(0.0, float(radius_sq)))
    basis = np.array(basis, dtype=complex)
    phase_count = max(1, int(phase_grid_size))
    phase_seeds = [2.0 * math.pi * float(index) / float(phase_count) for index in range(phase_count)]

    def unpack(parameters):
        coefficients = _normalized_real_vector(parameters[:total_shell_dimension])
        phases = [float(value) for value in parameters[total_shell_dimension:]]
        return coefficients, phases

    def candidate_for_parameters(parameters):
        coefficients, phases = unpack(parameters)
        mode_by_sector = []
        offset = 0
        for sector in normalized_sectors:
            shell_dim = int(sector["shell_dimension"])
            sector_coeffs = coefficients[offset : offset + shell_dim]
            mode_by_sector.append(np.array(sector["shell_basis"] @ sector_coeffs, dtype=float))
            offset += shell_dim

        local_rays = []
        cell_exactness = []
        for cell in _magnetic_cells(supercell_shape):
            total_mode = np.zeros((magnetic_site_count * traceless_dim,), dtype=float)
            for sector_index, sector in enumerate(normalized_sectors):
                phase = 2.0 * math.pi * sum(
                    float(sector["q_values"][axis]) * float(cell[axis]) for axis in range(3)
                ) + float(phases[sector_index])
                total_mode += radius * math.cos(phase) * mode_by_sector[sector_index]

            for site_index in range(magnetic_site_count):
                site_mode = total_mode[site_index * traceless_dim : (site_index + 1) * traceless_dim]
                projector = np.array(basis[0], dtype=complex) / math.sqrt(float(local_dimension))
                if basis.shape[0] > 1:
                    projector = projector + np.einsum("m,mab->ab", site_mode, basis[1:], optimize=True)
                projector = 0.5 * (projector + projector.conjugate().T)
                trace_value = complex(np.trace(projector))
                if abs(trace_value) > 1.0e-14:
                    projector = projector / trace_value

                exactness, dominant_ray = _projector_exactness(
                    projector,
                    tolerance=float(projector_tolerance),
                )
                cell_exactness.append(
                    {
                        "cell": [int(value) for value in cell],
                        "site": int(site_index),
                        "trace_residual": float(exactness["trace_residual"]),
                        "hermiticity_residual": float(exactness["hermiticity_residual"]),
                        "negativity_residual": float(exactness["negativity_residual"]),
                        "purity_residual": float(exactness["purity_residual"]),
                        "rank_one_residual": float(exactness["rank_one_residual"]),
                        "is_exact_projector_solution": bool(exactness["is_exact_projector_solution"]),
                    }
                )
                ray_entry = {
                    "cell": [int(value) for value in cell],
                    "vector": _serialize_vector(_normalized_ray(dominant_ray)),
                }
                if magnetic_site_count > 1:
                    ray_entry["site"] = int(site_index)
                local_rays.append(ray_entry)

        aggregate = _aggregate_exactness(cell_exactness)
        candidate = {
            "status": "exact" if aggregate["is_exact_projector_solution"] else "approximate",
            "ordering": dict(ordering),
            "lowest_shell_dimension": int(total_shell_dimension),
            "mixing_strategy": "single-sector-phase-grid" if len(normalized_sectors) == 1 and total_shell_dimension == 1 else "multi-sector-mixing-search",
            "best_phase": float(phases[0]) if len(phases) == 1 else None,
            "sector_phases": [float(value) for value in phases],
            "mixing_coefficients": [float(value) for value in coefficients],
            "projector_exactness": aggregate,
            "classical_state": {
                "schema_version": 1,
                "state_kind": "local_rays",
                "manifold": "CP^(N-1)",
                "basis_order": str(basis_order),
                "pair_basis_order": str(pair_basis_order),
                "supercell_shape": [int(value) for value in supercell_shape],
                "local_rays": list(local_rays),
                "ordering": dict(ordering),
            },
        }
        if not aggregate["is_exact_projector_solution"]:
            candidate["obstruction_report"] = {
                "reason": "commensurate reconstruction did not yield exact rank-one local projectors",
                "max_rank_one_residual": float(aggregate["rank_one_residual"]),
                "max_purity_residual": float(aggregate["purity_residual"]),
            }
        return candidate

    best = None

    def record(candidate):
        nonlocal best
        if best is None or _score_exactness(candidate["projector_exactness"]) < _score_exactness(best["projector_exactness"]):
            best = candidate
        return bool(candidate["projector_exactness"]["is_exact_projector_solution"])

    coefficient_seeds = _mixing_seed_vectors(total_shell_dimension)
    phase_seed_lists = [phase_seeds for _ in normalized_sectors]

    for coefficient_seed in coefficient_seeds:
        phase_mesh = np.array(np.meshgrid(*phase_seed_lists, indexing="ij")).reshape(len(normalized_sectors), -1).T
        for phases in phase_mesh:
            seed = np.concatenate([np.array(coefficient_seed, dtype=float), np.array(phases, dtype=float)])
            candidate = candidate_for_parameters(seed)
            if record(candidate):
                return candidate
            if minimize is not None:
                optimized = minimize(
                    lambda parameters: _mixing_objective(candidate_for_parameters(parameters)["projector_exactness"]),
                    seed,
                    method="Powell",
                    options={"maxiter": 300, "xtol": 1.0e-10, "ftol": 1.0e-12},
                )
                candidate = candidate_for_parameters(optimized.x)
                if record(candidate):
                    return candidate

    return best


def reconstruct_commensurate_single_q_texture(
    *,
    basis,
    local_dimension,
    q_vector,
    shell_basis,
    radius_sq,
    basis_order,
    pair_basis_order,
    projector_tolerance=1.0e-8,
    phase_grid_size=32,
    q_tolerance=1.0e-8,
    max_denominator=12,
):
    return reconstruct_commensurate_relaxed_shell(
        basis=basis,
        local_dimension=local_dimension,
        sectors=[{"q_vector": list(q_vector), "shell_basis": np.array(shell_basis, dtype=float)}],
        radius_sq=radius_sq,
        basis_order=basis_order,
        pair_basis_order=pair_basis_order,
        projector_tolerance=projector_tolerance,
        phase_grid_size=phase_grid_size,
        q_tolerance=q_tolerance,
        max_denominator=max_denominator,
    )
