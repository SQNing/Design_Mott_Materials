#!/usr/bin/env python3
import math
import sys
from pathlib import Path

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.quadratic_phase_dressing import (
    resolve_quadratic_phase_dressing,
    summarize_quadratic_phase_dressing,
)
from common.rotating_frame_consistency import (
    compare_wavevectors as _compare_wavevectors,
    infer_single_q_from_supercell_site_phases as _infer_single_q_from_supercell_site_phases,
    local_rays_rotating_frame_metadata_phase_sample_cross_check as _common_local_rays_rotating_frame_metadata_phase_sample_cross_check,
    max_site_phase_offset_difference as _common_max_site_phase_offset_difference,
    metadata_local_rotating_frame_summary as _common_metadata_local_rotating_frame_summary,
    normalized_site_phase_offsets as _normalized_site_phase_offsets,
    stabilize_float as _stabilize_float,
    wrap_phase_difference as _wrap_phase_difference,
)
from common.rotating_frame_realization import (
    resolve_supercell_site_phase_entries,
    summarize_rotating_frame_realization,
)
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


def _mode_site_lookup(shape, site_count):
    cells = _cell_tuples(shape)
    mode_sites = []
    for cell in cells:
        for site in range(int(site_count)):
            mode_sites.append((cell, int(site)))
    return mode_sites, {mode_site: index for index, mode_site in enumerate(mode_sites)}


def _load_local_rays(payload):
    shape = tuple(int(value) for value in payload["supercell_shape"])
    local_dimension = int(payload["local_dimension"])
    entries = list(payload.get("initial_local_rays", []))
    site_count = 1
    if entries:
        site_count = max(1, max(int(item.get("site", 0)) for item in entries) + 1)
    rays = np.zeros(shape + (site_count, local_dimension), dtype=complex)
    for item in entries:
        cell = tuple(int(value) for value in item["cell"])
        site = int(item.get("site", 0))
        rays[cell + (site,)] = _normalize(_deserialize_vector(item["vector"]))
    for cell in np.ndindex(shape):
        for site in range(site_count):
            if np.linalg.norm(rays[cell + (site,)]) <= 1e-12:
                raise ValueError(f"missing local ray for magnetic-cell coordinate {cell} site {site}")
    return rays


def _deserialize_local_rays(payload):
    rays = _load_local_rays(payload)
    return _apply_rotating_frame_realization_to_local_rays(payload, rays)


def _apply_rotating_frame_realization_to_local_rays(payload, rays):
    rotating_frame = summarize_rotating_frame_realization(
        payload,
        application_kind="local-ray-gauge-alignment",
        consumed=True,
    )
    if rotating_frame is None:
        return rays, None

    entries = resolve_supercell_site_phase_entries(payload)
    if not entries:
        rotating_frame["gauge_alignment_applied"] = False
        rotating_frame["reason"] = "no-supercell-site-phases"
        return rays, rotating_frame
    phase_by_site_cell = {
        (tuple(int(value) for value in entry["cell"]), int(entry["site"])): float(entry["phase"])
        for entry in entries
    }
    aligned = np.array(rays, copy=True)
    for cell in np.ndindex(rays.shape[:3]):
        for site in range(int(rays.shape[3])):
            key = (tuple(int(value) for value in cell), int(site))
            if key not in phase_by_site_cell:
                rotating_frame["gauge_alignment_applied"] = False
                rotating_frame["reason"] = f"missing-site-phase-for-cell-{cell}-site-{site}"
                return rays, rotating_frame
            aligned[cell + (site,)] *= np.exp(-1.0j * float(phase_by_site_cell[key]))

    rotating_frame["gauge_alignment_applied"] = True
    return aligned, rotating_frame


def _resolve_site_phase_map(payload, *, site_count):
    entries = resolve_supercell_site_phase_entries(payload)
    if not entries:
        return None, "no-supercell-site-phases"

    phase_by_site_cell = {
        (tuple(int(value) for value in entry["cell"]), int(entry["site"])): float(entry["phase"])
        for entry in entries
    }
    shape = tuple(int(value) for value in payload["supercell_shape"])
    for cell in np.ndindex(shape):
        for site in range(int(site_count)):
            key = (tuple(int(value) for value in cell), int(site))
            if key not in phase_by_site_cell:
                return None, f"missing-site-phase-for-cell-{cell}-site-{site}"
    return phase_by_site_cell, None


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


def _phase_factor_from_rule(rule, source_phase, target_phase):
    if rule == "target_minus_source":
        argument = float(target_phase) - float(source_phase)
    elif rule == "minus_source_minus_target":
        argument = -float(source_phase) - float(target_phase)
    elif rule == "source_plus_target":
        argument = float(source_phase) + float(target_phase)
    elif rule == "minus_source":
        argument = -float(source_phase)
    elif rule == "source":
        argument = float(source_phase)
    else:
        argument = 0.0
    return np.exp(1.0j * argument)


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


def _quadratic_terms_from_rays(payload, rays, *, rotating_frame=None, phase_dressing=None, phase_by_site_cell=None):
    local_dimension = int(payload["local_dimension"])
    if local_dimension < 2:
        raise ValueError("python GLSWT requires local_dimension >= 2")
    shape = tuple(int(value) for value in payload["supercell_shape"])
    site_count = int(rays.shape[3])
    excited_dimension = local_dimension - 1
    cells = _cell_tuples(shape)
    mode_sites, lookup = _mode_site_lookup(shape, site_count)
    frames = {
        mode_site: build_local_frame(rays[mode_site[0] + (mode_site[1],)])
        for mode_site in mode_sites
    }
    channel_rules = {}
    if isinstance(phase_dressing, dict):
        channel_rules = dict(phase_dressing.get("channel_phase_rules", {}))

    linear_dag = np.zeros((len(mode_sites), excited_dimension), dtype=complex)
    linear_ann = np.zeros((len(mode_sites), excited_dimension), dtype=complex)
    normal_terms = {}
    pair_terms = {}

    for source_cell in cells:
        for coupling in payload.get("pair_couplings", []):
            source_site = int(coupling.get("source", 0))
            target_site = int(coupling.get("target", 0))
            if not 0 <= source_site < site_count:
                raise ValueError(
                    f"pair coupling source site {source_site} out of range for site_count={site_count}"
                )
            if not 0 <= target_site < site_count:
                raise ValueError(
                    f"pair coupling target site {target_site} out of range for site_count={site_count}"
                )
            displacement = tuple(int(value) for value in coupling.get("R", [0, 0, 0]))
            target_cell, translation = _wrap_cell_and_translation(source_cell, displacement, shape)
            source_mode_site = (source_cell, source_site)
            target_mode_site = (target_cell, target_site)
            source_index = lookup[source_mode_site]
            target_index = lookup[target_mode_site]
            source_frame = frames[source_mode_site]
            target_frame = frames[target_mode_site]
            source_phase = (
                float(phase_by_site_cell.get(source_mode_site, 0.0))
                if isinstance(phase_by_site_cell, dict)
                else 0.0
            )
            target_phase = (
                float(phase_by_site_cell.get(target_mode_site, 0.0))
                if isinstance(phase_by_site_cell, dict)
                else 0.0
            )
            rotated = _rotated_pair_tensor(
                _deserialize_pair_matrix(coupling["pair_matrix"]),
                source_frame,
                target_frame,
            )

            e00 = complex(rotated[0, 0, 0, 0])
            identity = np.eye(excited_dimension, dtype=complex)

            linear_dag[source_index] += _phase_factor_from_rule(
                channel_rules.get("linear_creation", "identity"),
                source_phase,
                target_phase,
            ) * rotated[1:, 0, 0, 0]
            linear_ann[source_index] += _phase_factor_from_rule(
                channel_rules.get("linear_annihilation", "identity"),
                source_phase,
                target_phase,
            ) * rotated[0, 1:, 0, 0]
            linear_dag[target_index] += _phase_factor_from_rule(
                channel_rules.get("linear_creation", "identity"),
                target_phase,
                source_phase,
            ) * rotated[0, 0, 1:, 0]
            linear_ann[target_index] += _phase_factor_from_rule(
                channel_rules.get("linear_annihilation", "identity"),
                target_phase,
                source_phase,
            ) * rotated[0, 0, 0, 1:]

            _block_add(
                normal_terms,
                (source_index, source_index, (0, 0, 0)),
                _phase_factor_from_rule(
                    channel_rules.get("normal", "identity"),
                    source_phase,
                    source_phase,
                )
                * (rotated[1:, 1:, 0, 0] - e00 * identity),
            )
            _block_add(
                normal_terms,
                (target_index, target_index, (0, 0, 0)),
                _phase_factor_from_rule(
                    channel_rules.get("normal", "identity"),
                    target_phase,
                    target_phase,
                )
                * (rotated[0, 0, 1:, 1:] - e00 * identity),
            )
            _block_add(
                normal_terms,
                (source_index, target_index, translation),
                _phase_factor_from_rule(
                    channel_rules.get("normal", "identity"),
                    source_phase,
                    target_phase,
                )
                * rotated[1:, 0, 0, 1:],
            )
            _block_add(
                normal_terms,
                (target_index, source_index, _negate_translation(translation)),
                _phase_factor_from_rule(
                    channel_rules.get("normal", "identity"),
                    target_phase,
                    source_phase,
                )
                * np.transpose(rotated[0, 1:, 1:, 0]),
            )
            _block_add(
                pair_terms,
                (source_index, target_index, translation),
                _phase_factor_from_rule(
                    channel_rules.get("pair", "identity"),
                    source_phase,
                    target_phase,
                )
                * rotated[1:, 0, 1:, 0],
            )

    return {
        "shape": shape,
        "site_count": site_count,
        "mode_site_count": len(mode_sites),
        "mode_sites": mode_sites,
        "excited_dimension": excited_dimension,
        "linear_dag": linear_dag,
        "linear_ann": linear_ann,
        "normal_terms": normal_terms,
        "pair_terms": pair_terms,
        "frames": frames,
        "rotating_frame": rotating_frame,
    }


def _assemble_k_blocks(terms, q_vector):
    mode_site_count = int(terms["mode_site_count"])
    excited_dimension = int(terms["excited_dimension"])
    mode_count = mode_site_count * excited_dimension
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
    mode_sites = list(terms.get("mode_sites", []))
    for site_index in range(int(terms["mode_site_count"])):
        dag_norm = float(np.linalg.norm(terms["linear_dag"][site_index]))
        ann_norm = float(np.linalg.norm(terms["linear_ann"][site_index]))
        residual_norm = max(dag_norm, ann_norm)
        max_norm = max(max_norm, residual_norm)
        mode_site = mode_sites[site_index] if site_index < len(mode_sites) else ((0, 0, 0), 0)
        site_entries.append(
            {
                "cell": [int(value) for value in mode_site[0]],
                "site": int(mode_site[1]),
                "mode_site_index": int(site_index),
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


def _infer_local_payload_site_count(payload):
    positions = list(payload.get("positions", []))
    if positions:
        return len(positions)
    entries = list(payload.get("initial_local_rays", []))
    if entries:
        return max(int(item.get("site", 0)) for item in entries) + 1
    return 1


def _metadata_local_rotating_frame_summary(payload, *, tolerance=1e-8):
    return _common_metadata_local_rotating_frame_summary(payload, tolerance=tolerance)


def _max_site_phase_offset_difference(left, right):
    return _common_max_site_phase_offset_difference(left, right)


def _local_rays_rotating_frame_metadata_phase_sample_cross_check(payload, *, tolerance=1e-8):
    return _common_local_rays_rotating_frame_metadata_phase_sample_cross_check(
        payload,
        tolerance=tolerance,
    )


def _max_matrix_map_difference(left, right):
    keys = set(left) | set(right)
    if not keys:
        return 0.0
    max_norm = 0.0
    for key in keys:
        left_value = left.get(key)
        right_value = right.get(key)
        if left_value is None:
            difference = np.array(right_value, dtype=complex)
        elif right_value is None:
            difference = np.array(left_value, dtype=complex)
        else:
            difference = np.array(left_value, dtype=complex) - np.array(right_value, dtype=complex)
        max_norm = max(max_norm, float(np.linalg.norm(difference)))
    return max_norm


def _max_linear_difference(left_terms, right_terms):
    max_norm = 0.0
    for key in ("linear_dag", "linear_ann"):
        left_value = np.array(left_terms.get(key), dtype=complex)
        right_value = np.array(right_terms.get(key), dtype=complex)
        max_norm = max(max_norm, float(np.linalg.norm(left_value - right_value)))
    return max_norm


def _quadratic_phase_dressing_consistency(gauge_terms, explicit_terms, *, reason=None, tolerance=1e-8):
    if explicit_terms is None:
        return {
            "status": "unsupported",
            "reason": str(reason or "explicit-block-dressing-unavailable"),
        }
    max_normal = _max_matrix_map_difference(gauge_terms.get("normal_terms", {}), explicit_terms.get("normal_terms", {}))
    max_pair = _max_matrix_map_difference(gauge_terms.get("pair_terms", {}), explicit_terms.get("pair_terms", {}))
    max_linear = _max_linear_difference(gauge_terms, explicit_terms)
    return {
        "status": "consistent" if max(max_normal, max_pair, max_linear) <= float(tolerance) else "inconsistent",
        "tolerance": float(tolerance),
        "max_normal_term_difference": float(max_normal),
        "max_pair_term_difference": float(max_pair),
        "max_linear_term_difference": float(max_linear),
    }


def _quadratic_terms(payload):
    raw_rays = _load_local_rays(payload)
    aligned_rays, rotating_frame = _apply_rotating_frame_realization_to_local_rays(payload, np.array(raw_rays, copy=True))
    gauge_terms = _quadratic_terms_from_rays(
        payload,
        aligned_rays,
        rotating_frame=rotating_frame,
    )

    phase_dressing = resolve_quadratic_phase_dressing(payload)
    phase_by_site_cell, phase_reason = _resolve_site_phase_map(
        payload,
        site_count=int(raw_rays.shape[3]),
    )
    explicit_terms = None
    if isinstance(phase_dressing, dict) and isinstance(phase_by_site_cell, dict):
        explicit_terms = _quadratic_terms_from_rays(
            payload,
            raw_rays,
            rotating_frame=rotating_frame,
            phase_dressing=phase_dressing,
            phase_by_site_cell=phase_by_site_cell,
        )
    consistency = _quadratic_phase_dressing_consistency(
        gauge_terms,
        explicit_terms,
        reason=phase_reason,
    )

    mode = str(payload.get("quadratic_phase_dressing_mode", "gauge_alignment"))
    if mode == "explicit_block_dressing" and explicit_terms is not None:
        active_terms = dict(explicit_terms)
        quadratic_phase_dressing = summarize_quadratic_phase_dressing(
            payload,
            application_kind="explicit-block-dressing",
            consumed=True,
        )
    else:
        active_terms = dict(gauge_terms)
        quadratic_phase_dressing = summarize_quadratic_phase_dressing(
            payload,
            application_kind="gauge-alignment-subsumes-explicit-block-dressing",
            consumed=True,
            reason=phase_reason if mode == "explicit_block_dressing" and explicit_terms is None else None,
        )

    active_terms["quadratic_phase_dressing"] = quadratic_phase_dressing
    active_terms["quadratic_phase_dressing_consistency"] = consistency
    active_terms["rotating_frame_metadata_phase_sample_cross_check"] = (
        _local_rays_rotating_frame_metadata_phase_sample_cross_check(payload)
    )
    return active_terms


def _solve_local_rays_python_glswt(payload, *, stationarity_tolerance=1e-8, eigenvalue_tolerance=1e-8):
    terms = _quadratic_terms(payload)
    mode_count = int(terms["mode_site_count"] * terms["excited_dimension"])
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
    quadratic_phase_dressing = terms.get("quadratic_phase_dressing")
    quadratic_phase_dressing_consistency = terms.get("quadratic_phase_dressing_consistency")
    rotating_frame_metadata_phase_sample_cross_check = terms.get("rotating_frame_metadata_phase_sample_cross_check")
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
            **({"quadratic_phase_dressing": quadratic_phase_dressing} if isinstance(quadratic_phase_dressing, dict) else {}),
            **(
                {"quadratic_phase_dressing_consistency": quadratic_phase_dressing_consistency}
                if isinstance(quadratic_phase_dressing_consistency, dict)
                else {}
            ),
            **({"rotating_frame": dict(terms["rotating_frame"])} if isinstance(terms.get("rotating_frame"), dict) else {}),
            **(
                {"rotating_frame_metadata_phase_sample_cross_check": rotating_frame_metadata_phase_sample_cross_check}
                if isinstance(rotating_frame_metadata_phase_sample_cross_check, dict)
                else {}
            ),
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
