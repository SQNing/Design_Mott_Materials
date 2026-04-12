#!/usr/bin/env python3
import math
import sys
from pathlib import Path

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lswt.single_q_z_harmonic_glswt_solver import solve_single_q_z_harmonic_glswt


def _complex_from_serialized(value):
    if isinstance(value, dict):
        return complex(float(value.get("real", 0.0)), float(value.get("imag", 0.0)))
    return complex(value)


def _deserialize_vector(serialized):
    return np.array([_complex_from_serialized(value) for value in serialized], dtype=complex)


def _deserialize_pair_matrix(serialized):
    return np.array(
        [[_complex_from_serialized(value) for value in row] for row in serialized],
        dtype=complex,
    )


def _pair_matrix_to_tensor(pair_matrix, local_dimension):
    return np.array(pair_matrix, dtype=complex).reshape(
        local_dimension,
        local_dimension,
        local_dimension,
        local_dimension,
    )


def _normalize(vector, *, tolerance=1e-12):
    vector = np.array(vector, dtype=complex)
    norm = float(np.linalg.norm(vector))
    if norm <= tolerance:
        raise ValueError("vector norm must be nonzero")
    return vector / norm


def build_local_frame(reference_ray, *, tolerance=1e-12):
    reference_ray = _normalize(reference_ray, tolerance=tolerance)
    local_dimension = int(reference_ray.shape[0])
    columns = [reference_ray]

    for basis_index in range(local_dimension):
        candidate = np.zeros(local_dimension, dtype=complex)
        candidate[basis_index] = 1.0
        for column in columns:
            candidate = candidate - np.vdot(column, candidate) * column
        norm = float(np.linalg.norm(candidate))
        if norm > tolerance:
            columns.append(candidate / norm)
        if len(columns) == local_dimension:
            break

    if len(columns) != local_dimension:
        raise ValueError("failed to build a complete local orthonormal frame")
    return np.column_stack(columns)


def _cell_tuples(shape):
    return [tuple(int(value) for value in index) for index in np.ndindex(tuple(shape))]


def _cell_lookup(shape):
    cells = _cell_tuples(shape)
    return cells, {cell: index for index, cell in enumerate(cells)}


def _deserialize_local_rays(payload):
    shape = tuple(int(value) for value in payload["supercell_shape"])
    local_dimension = int(payload["local_dimension"])
    rays = np.zeros(shape + (local_dimension,), dtype=complex)
    for item in payload.get("initial_local_rays", []):
        cell = tuple(int(value) for value in item["cell"])
        rays[cell] = _normalize(_deserialize_vector(item["vector"]))
    for cell in np.ndindex(shape):
        if np.linalg.norm(rays[cell]) <= 1e-12:
            raise ValueError(f"missing local ray for magnetic-cell coordinate {cell}")
    return rays


def _wrap_cell_and_translation(cell, displacement, shape):
    target = []
    translation = []
    for axis in range(3):
        total = int(cell[axis]) + int(displacement[axis])
        size = int(shape[axis])
        wrapped = total % size
        target.append(wrapped)
        translation.append((total - wrapped) // size)
    return tuple(target), tuple(translation)


def _negate_translation(translation):
    return tuple(-int(value) for value in translation)


def _phase_from_k_and_translation(q_vector, translation):
    return np.exp(
        2.0j
        * np.pi
        * sum(float(q_vector[axis]) * float(translation[axis]) for axis in range(3))
    )


def _block_add(mapping, key, value):
    if key not in mapping:
        mapping[key] = np.array(value, dtype=complex)
    else:
        mapping[key] = mapping[key] + np.array(value, dtype=complex)


def _rotated_pair_tensor(pair_matrix, frame_left, frame_right):
    local_dimension = int(frame_left.shape[0])
    tensor = _pair_matrix_to_tensor(pair_matrix, local_dimension)
    return np.einsum(
        "ABCD,Aa,Bb,Cc,Dd->abcd",
        tensor,
        frame_left.conjugate(),
        frame_left,
        frame_right.conjugate(),
        frame_right,
        optimize=True,
    )


def _quadratic_terms(payload):
    local_dimension = int(payload["local_dimension"])
    if local_dimension < 2:
        raise ValueError("python GLSWT requires local_dimension >= 2")
    shape = tuple(int(value) for value in payload["supercell_shape"])
    excited_dimension = local_dimension - 1
    rays = _deserialize_local_rays(payload)
    cells, lookup = _cell_lookup(shape)
    frames = {cell: build_local_frame(rays[cell]) for cell in cells}

    linear_dag = np.zeros((len(cells), excited_dimension), dtype=complex)
    linear_ann = np.zeros((len(cells), excited_dimension), dtype=complex)
    normal_terms = {}
    pair_terms = {}

    for source_cell in cells:
        source_index = lookup[source_cell]
        source_frame = frames[source_cell]
        for coupling in payload.get("pair_couplings", []):
            displacement = tuple(int(value) for value in coupling.get("R", [0, 0, 0]))
            target_cell, translation = _wrap_cell_and_translation(source_cell, displacement, shape)
            target_index = lookup[target_cell]
            target_frame = frames[target_cell]
            rotated = _rotated_pair_tensor(
                _deserialize_pair_matrix(coupling["pair_matrix"]),
                source_frame,
                target_frame,
            )

            e00 = complex(rotated[0, 0, 0, 0])
            identity = np.eye(excited_dimension, dtype=complex)

            linear_dag[source_index] += rotated[1:, 0, 0, 0]
            linear_ann[source_index] += rotated[0, 1:, 0, 0]
            linear_dag[target_index] += rotated[0, 0, 1:, 0]
            linear_ann[target_index] += rotated[0, 0, 0, 1:]

            _block_add(
                normal_terms,
                (source_index, source_index, (0, 0, 0)),
                rotated[1:, 1:, 0, 0] - e00 * identity,
            )
            _block_add(
                normal_terms,
                (target_index, target_index, (0, 0, 0)),
                rotated[0, 0, 1:, 1:] - e00 * identity,
            )
            _block_add(
                normal_terms,
                (source_index, target_index, translation),
                rotated[1:, 0, 0, 1:],
            )
            _block_add(
                normal_terms,
                (target_index, source_index, _negate_translation(translation)),
                np.transpose(rotated[0, 1:, 1:, 0]),
            )
            _block_add(
                pair_terms,
                (source_index, target_index, translation),
                rotated[1:, 0, 1:, 0],
            )

    return {
        "shape": shape,
        "cell_count": len(cells),
        "excited_dimension": excited_dimension,
        "linear_dag": linear_dag,
        "linear_ann": linear_ann,
        "normal_terms": normal_terms,
        "pair_terms": pair_terms,
        "frames": frames,
    }


def _assemble_k_blocks(terms, q_vector):
    cell_count = int(terms["cell_count"])
    excited_dimension = int(terms["excited_dimension"])
    mode_count = cell_count * excited_dimension
    normal = np.zeros((mode_count, mode_count), dtype=complex)
    pair = np.zeros((mode_count, mode_count), dtype=complex)

    for (source, target, translation), block in terms["normal_terms"].items():
        phase = _phase_from_k_and_translation(q_vector, translation)
        row = slice(source * excited_dimension, (source + 1) * excited_dimension)
        col = slice(target * excited_dimension, (target + 1) * excited_dimension)
        normal[row, col] += phase * block

    for (source, target, translation), block in terms["pair_terms"].items():
        phase = _phase_from_k_and_translation(q_vector, translation)
        row = slice(source * excited_dimension, (source + 1) * excited_dimension)
        col = slice(target * excited_dimension, (target + 1) * excited_dimension)
        pair[row, col] += phase * block

    normal = 0.5 * (normal + normal.conjugate().T)
    pair = 0.5 * (pair + pair.T)
    return normal, pair


def _positive_branches(eigenvalues, mode_count, *, tolerance=1e-8):
    stable_positive = [
        value
        for value in eigenvalues
        if float(np.real(value)) > tolerance and abs(float(np.imag(value))) <= tolerance
    ]
    stable_zero = [
        value
        for value in eigenvalues
        if abs(float(np.real(value))) <= tolerance and abs(float(np.imag(value))) <= tolerance
    ]
    stable_positive = sorted(
        stable_positive,
        key=lambda value: (float(np.real(value)), abs(float(np.imag(value)))),
    )
    stable_zero = sorted(stable_zero, key=lambda value: abs(float(np.imag(value))))
    selected = stable_positive + stable_zero
    return selected[:mode_count]


def _stationarity_diagnostics(terms, *, tolerance=1e-8):
    site_entries = []
    max_norm = 0.0
    for site_index in range(int(terms["cell_count"])):
        dag_norm = float(np.linalg.norm(terms["linear_dag"][site_index]))
        ann_norm = float(np.linalg.norm(terms["linear_ann"][site_index]))
        residual_norm = max(dag_norm, ann_norm)
        max_norm = max(max_norm, residual_norm)
        site_entries.append(
            {
                "site": int(site_index),
                "creation_linear_norm": dag_norm,
                "annihilation_linear_norm": ann_norm,
                "linear_term_norm": residual_norm,
            }
        )
    return {
        "scope": "full-local-tangent",
        "tolerance": float(tolerance),
        "linear_term_max_norm": max_norm,
        "linear_term_mean_norm": float(
            sum(entry["linear_term_norm"] for entry in site_entries) / len(site_entries)
        )
        if site_entries
        else 0.0,
        "is_stationary": bool(max_norm <= tolerance),
        "sites": site_entries,
    }


def _dispersion_diagnostics(dispersion, *, soft_mode_tolerance=-1e-8):
    if not dispersion:
        return {
            "omega_min": None,
            "omega_max": None,
            "omega_min_q_vector": None,
            "soft_mode_count": 0,
            "soft_mode_q_points": [],
        }

    omega_min = None
    omega_max = None
    omega_min_q = None
    soft_mode_q_points = []
    for point in dispersion:
        bands = [float(value) for value in point.get("bands", [])]
        if not bands:
            continue
        point_min = min(bands)
        point_max = max(bands)
        if omega_min is None or point_min < omega_min:
            omega_min = point_min
            omega_min_q = list(point.get("q", []))
        if omega_max is None or point_max > omega_max:
            omega_max = point_max
        if point_min < soft_mode_tolerance:
            soft_mode_q_points.append(list(point.get("q", [])))
    return {
        "omega_min": omega_min,
        "omega_max": omega_max,
        "omega_min_q_vector": omega_min_q,
        "soft_mode_threshold": float(soft_mode_tolerance),
        "soft_mode_count": int(len(soft_mode_q_points)),
        "soft_mode_q_points": soft_mode_q_points,
    }


def _solve_local_rays_python_glswt(payload, *, stationarity_tolerance=1e-8, eigenvalue_tolerance=1e-8):
    terms = _quadratic_terms(payload)
    mode_count = int(terms["cell_count"] * terms["excited_dimension"])
    dispersion = []
    max_antihermitian_norm = 0.0
    max_pair_asymmetry_norm = 0.0
    max_complex_eigenvalue_count = 0

    for q_vector in payload.get("q_path", []):
        q_vector = [float(value) for value in q_vector]
        normal, pair = _assemble_k_blocks(terms, q_vector)
        max_antihermitian_norm = max(
            max_antihermitian_norm,
            float(np.linalg.norm(normal - normal.conjugate().T)),
        )
        max_pair_asymmetry_norm = max(
            max_pair_asymmetry_norm,
            float(np.linalg.norm(pair - pair.T)),
        )

        dynamical_matrix = np.block(
            [
                [normal, pair],
                [-pair.conjugate(), -normal.conjugate()],
            ]
        )
        eigenvalues = np.linalg.eigvals(dynamical_matrix)
        max_complex_eigenvalue_count = max(
            max_complex_eigenvalue_count,
            int(sum(abs(float(np.imag(value))) > eigenvalue_tolerance for value in eigenvalues)),
        )
        positive = _positive_branches(eigenvalues, mode_count, tolerance=eigenvalue_tolerance)
        bands = [float(np.real(value)) for value in positive]
        dispersion.append(
            {
                "q": q_vector,
                "bands": bands,
                "omega": float(min(bands)) if bands else None,
            }
        )

    stationarity = _stationarity_diagnostics(terms, tolerance=stationarity_tolerance)
    return {
        "status": "ok",
        "backend": {"name": "python-glswt", "implementation": "local-frame-quadratic-expansion"},
        "payload_kind": str(payload.get("payload_kind", "python_glswt_local_rays")),
        "dispersion": dispersion,
        "path": dict(payload.get("path", {})),
        "classical_reference": dict(payload.get("classical_reference", {})),
        "ordering": dict(payload.get("ordering", {})),
        "diagnostics": {
            "stationarity": stationarity,
            "dispersion": _dispersion_diagnostics(dispersion),
            "bogoliubov": {
                "mode_count": int(mode_count),
                "max_A_antihermitian_norm": max_antihermitian_norm,
                "max_B_asymmetry_norm": max_pair_asymmetry_norm,
                "max_complex_eigenvalue_count": int(max_complex_eigenvalue_count),
            },
        },
    }


def solve_python_glswt(payload, *, stationarity_tolerance=1e-8, eigenvalue_tolerance=1e-8):
    payload_kind = str(payload.get("payload_kind", "python_glswt_local_rays"))
    if payload_kind == "python_glswt_single_q_z_harmonic":
        return solve_single_q_z_harmonic_glswt(
            payload,
            stationarity_tolerance=stationarity_tolerance,
            eigenvalue_tolerance=eigenvalue_tolerance,
        )
    return _solve_local_rays_python_glswt(
        payload,
        stationarity_tolerance=stationarity_tolerance,
        eigenvalue_tolerance=eigenvalue_tolerance,
    )
