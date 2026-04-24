#!/usr/bin/env python3
import math

import numpy as np

try:
    from scipy.optimize import minimize
except ImportError:  # pragma: no cover - scipy is expected in the main environment.
    minimize = None

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from classical.lt_brillouin_zone import generate_q_mesh
    from classical.lt_fourier_exchange import fourier_exchange_matrix
else:
    from .lt_brillouin_zone import generate_q_mesh
    from .lt_fourier_exchange import fourier_exchange_matrix


def _serialize_vector(values):
    return [{"real": float(np.real(value)), "imag": float(np.imag(value))} for value in values]


def _serialize_vectors(vectors):
    if vectors.ndim != 2:
        raise ValueError("vectors must be a matrix with eigenvectors stored in columns")
    return [_serialize_vector(vectors[:, index]) for index in range(vectors.shape[1])]


def _pad_q(values):
    padded = [float(value) for value in values[:3]]
    while len(padded) < 3:
        padded.append(0.0)
    return padded


def _wrap_q(values):
    wrapped = []
    for value in _pad_q(values):
        reduced = float(value) % 1.0
        if math.isclose(reduced, 1.0, abs_tol=1.0e-12):
            reduced = 0.0
        wrapped.append(reduced)
    return wrapped


def _q_distance(left, right):
    deltas = []
    for left_value, right_value in zip(_wrap_q(left), _wrap_q(right)):
        delta = abs(float(left_value) - float(right_value))
        deltas.append(min(delta, 1.0 - delta))
    return float(max(deltas) if deltas else 0.0)


def _negative_q(values):
    return _wrap_q([-float(value) for value in _pad_q(values)])


def _lowest_sector_for_q(model, q, *, degeneracy_tolerance=1.0e-9):
    wrapped_q = _wrap_q(q)
    jq = fourier_exchange_matrix(model, wrapped_q)
    eigenvalues, eigenvectors = np.linalg.eigh(jq)
    lowest = float(np.real(eigenvalues[0]))
    degenerate = np.isclose(eigenvalues, eigenvalues[0], atol=float(degeneracy_tolerance))
    eigenspace = eigenvectors[:, degenerate]
    return {
        "q": wrapped_q,
        "eigenvalue": lowest,
        "eigenvector": eigenspace[:, 0],
        "eigenspace": eigenspace,
        "matrix_size": int(jq.shape[0]),
        "shell_dimension": int(eigenspace.shape[1]),
    }


def _scan_mesh(model, q_mesh):
    return [_lowest_sector_for_q(model, q) for q in q_mesh]


def _active_axes(mesh_shape):
    return [index for index, points in enumerate(mesh_shape) if int(points) > 1]


def _refine_sector(model, seed_sector, mesh_shape):
    if minimize is None:
        sector = dict(seed_sector)
        sector["refinement"] = {"status": "scipy-unavailable", "seed_q": list(seed_sector["q"])}
        return sector

    active_axes = _active_axes(mesh_shape)
    if not active_axes:
        sector = dict(seed_sector)
        sector["refinement"] = {"status": "inactive", "seed_q": list(seed_sector["q"])}
        return sector

    initial = np.array([float(seed_sector["q"][axis]) for axis in active_axes], dtype=float)
    bounds = [(0.0, 1.0) for _ in active_axes]

    def objective(active_q):
        q_vector = list(seed_sector["q"])
        for local_index, axis in enumerate(active_axes):
            q_vector[axis] = float(active_q[local_index]) % 1.0
        return _lowest_sector_for_q(model, q_vector)["eigenvalue"]

    optimized = minimize(
        objective,
        initial,
        method="Powell",
        bounds=bounds,
        options={"maxiter": 200, "xtol": 1.0e-8, "ftol": 1.0e-10},
    )
    refined_q = list(seed_sector["q"])
    optimized_x = optimized.x if optimized.x is not None else initial
    for local_index, axis in enumerate(active_axes):
        refined_q[axis] = float(optimized_x[local_index]) % 1.0
    refined_sector = _lowest_sector_for_q(model, refined_q)
    refined_sector["refinement"] = {
        "status": "optimized" if bool(getattr(optimized, "success", False)) else "optimizer-returned",
        "seed_q": list(seed_sector["q"]),
        "optimizer_method": str(getattr(optimized, "method", "Powell")),
        "success": bool(getattr(optimized, "success", False)),
        "message": str(getattr(optimized, "message", "")),
        "nfev": int(getattr(optimized, "nfev", 0) or 0),
        "nit": int(getattr(optimized, "nit", 0) or 0),
    }
    return refined_sector


def _cluster_sectors(sectors, *, q_tolerance=1.0e-5, energy_tolerance=1.0e-8):
    clusters = []
    for sector in sectors:
        matched = False
        for cluster in clusters:
            if (
                _q_distance(cluster["q"], sector["q"]) <= float(q_tolerance)
                and abs(float(cluster["eigenvalue"]) - float(sector["eigenvalue"])) <= float(energy_tolerance)
            ):
                matched = True
                if float(sector["eigenvalue"]) < float(cluster["eigenvalue"]):
                    cluster.update(sector)
                break
        if not matched:
            clusters.append(dict(sector))
    return clusters


def _augment_with_negative_partners(model, sectors, *, q_tolerance=1.0e-5, energy_tolerance=1.0e-8):
    augmented = [dict(sector) for sector in sectors]
    for sector in list(sectors):
        partner_q = _negative_q(sector["q"])
        if _q_distance(partner_q, sector["q"]) <= float(q_tolerance):
            continue
        if any(_q_distance(existing["q"], partner_q) <= float(q_tolerance) for existing in augmented):
            continue
        partner = _lowest_sector_for_q(model, partner_q)
        if abs(float(partner["eigenvalue"]) - float(sector["eigenvalue"])) <= float(energy_tolerance):
            partner["refinement"] = {"status": "derived-minus-q-partner", "seed_q": list(sector["q"])}
            augmented.append(partner)
    return _cluster_sectors(augmented, q_tolerance=q_tolerance, energy_tolerance=energy_tolerance)


def _sector_payload(sector):
    return {
        "q": [float(value) for value in sector["q"]],
        "eigenvalue": float(sector["eigenvalue"]),
        "eigenvector": _serialize_vector(sector["eigenvector"]),
        "eigenspace": _serialize_vectors(sector["eigenspace"]),
        "shell_dimension": int(sector["shell_dimension"]),
        "refinement": dict(sector.get("refinement", {})),
    }


def find_lt_ground_state(
    model,
    mesh_shape=(33, 33, 1),
    *,
    refine_continuous=True,
    seed_energy_tolerance=1.0e-8,
    shell_energy_tolerance=1.0e-7,
    degeneracy_tolerance=1.0e-9,
):
    mesh_shape = tuple(int(value) for value in mesh_shape)
    q_mesh = generate_q_mesh(mesh_shape)
    mesh_sectors = _scan_mesh(model, q_mesh)
    best_mesh_value = min(float(sector["eigenvalue"]) for sector in mesh_sectors)

    candidate_mesh_sectors = [
        sector for sector in mesh_sectors if float(sector["eigenvalue"]) <= best_mesh_value + float(seed_energy_tolerance)
    ]
    if not candidate_mesh_sectors:
        candidate_mesh_sectors = [min(mesh_sectors, key=lambda sector: float(sector["eigenvalue"]))]

    refined_candidates = []
    if refine_continuous:
        for sector in candidate_mesh_sectors:
            refined_candidates.append(_refine_sector(model, sector, mesh_shape))
    else:
        for sector in candidate_mesh_sectors:
            copied = dict(sector)
            copied["refinement"] = {"status": "disabled", "seed_q": list(sector["q"])}
            refined_candidates.append(copied)

    clustered_candidates = _cluster_sectors(refined_candidates)
    if not clustered_candidates:
        clustered_candidates = refined_candidates

    best_energy = min(float(sector["eigenvalue"]) for sector in clustered_candidates)
    shell_sectors = [
        sector for sector in clustered_candidates if float(sector["eigenvalue"]) <= best_energy + float(shell_energy_tolerance)
    ]
    shell_sectors = _augment_with_negative_partners(
        model,
        shell_sectors,
        q_tolerance=1.0e-5,
        energy_tolerance=shell_energy_tolerance,
    )

    primary_sector = min(shell_sectors, key=lambda sector: (float(sector["eigenvalue"]), sector["q"]))
    matrix_size = int(primary_sector["matrix_size"])
    sublattice_count = max(1, int(model.get("lattice", {}).get("sublattices", 0) or 0))
    if sublattice_count == 0:
        sublattice_count = 1

    refinement_status = "disabled"
    if refine_continuous:
        refinement_status = "optimized" if any(
            sector.get("refinement", {}).get("status") == "optimized" for sector in shell_sectors
        ) else "optimizer-returned"

    return {
        "q": [float(component) for component in primary_sector["q"]],
        "lowest_eigenvalue": float(primary_sector["eigenvalue"]),
        "eigenvector": _serialize_vector(primary_sector["eigenvector"]),
        "eigenspace": _serialize_vectors(primary_sector["eigenspace"]),
        "active_shell_dimension": int(primary_sector["shell_dimension"]),
        "matrix_size": int(matrix_size),
        "sublattice_count": int(sublattice_count),
        "components_per_sublattice": int(matrix_size // sublattice_count) if matrix_size else 0,
        "mesh_shape": list(mesh_shape),
        "sample_count": len(q_mesh),
        "refinement": {
            "status": str(refinement_status),
            "enabled": bool(refine_continuous),
            "seed_count": int(len(candidate_mesh_sectors)),
            "active_axes": _active_axes(mesh_shape),
            "mesh_best_eigenvalue": float(best_mesh_value),
        },
        "minimum_shell": {
            "energy": float(best_energy),
            "shell_energy_tolerance": float(shell_energy_tolerance),
            "degeneracy_tolerance": float(degeneracy_tolerance),
            "sector_count": int(len(shell_sectors)),
            "primary_q": [float(component) for component in primary_sector["q"]],
            "sectors": [_sector_payload(sector) for sector in shell_sectors],
        },
    }
