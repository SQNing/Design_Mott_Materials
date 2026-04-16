#!/usr/bin/env python3
import math


def infer_payload_site_count(payload):
    site_count = int(payload.get("site_count", 0))
    if site_count > 0:
        return site_count
    positions = list(payload.get("positions", []))
    if positions:
        return len(positions)
    entries = list(payload.get("initial_local_rays", []))
    if entries:
        return max(int(item.get("site", 0)) for item in entries) + 1
    return 1


def normalized_site_phase_offsets(site_count, offsets):
    normalized = {str(site): 0.0 for site in range(int(site_count))}
    if not isinstance(offsets, dict):
        return normalized
    for key, value in offsets.items():
        normalized[str(int(key))] = normalized.get(str(int(key)), 0.0) + float(value)
    return normalized


def compare_wavevectors(left, right):
    padded_dimension = max(len(left), len(right), 3)
    padded_left = [
        float(left[axis]) if axis < len(left) else 0.0
        for axis in range(padded_dimension)
    ]
    padded_right = [
        float(right[axis]) if axis < len(right) else 0.0
        for axis in range(padded_dimension)
    ]
    max_difference = max(
        abs(float(left_value) - float(right_value))
        for left_value, right_value in zip(padded_left, padded_right)
    )
    return padded_left, padded_right, float(max_difference)


def wrap_phase_difference(value):
    return math.atan2(math.sin(float(value)), math.cos(float(value)))


def stabilize_float(value, *, digits=15):
    return float(round(float(value), int(digits)))


def supercell_site_phase_lookup(realization):
    entries = list(realization.get("supercell_site_phases", [])) if isinstance(realization, dict) else []
    lookup = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        cell = entry.get("cell")
        site = entry.get("site")
        phase = entry.get("phase")
        if not isinstance(cell, list) or len(cell) != 3 or site is None or phase is None:
            continue
        lookup[(tuple(int(value) for value in cell), int(site))] = float(phase)
    return lookup


def infer_single_q_from_supercell_site_phases(payload, realization, *, tolerance=1e-8):
    if not isinstance(realization, dict):
        return {
            "phase_sample_status": "unavailable",
            "phase_sample_inferred_q_vector": None,
            "phase_sample_effective_site_phase_offsets": None,
            "phase_sample_max_residual": None,
        }

    supercell_shape = realization.get("supercell_shape")
    if not (isinstance(supercell_shape, list) and len(supercell_shape) == 3):
        return {
            "phase_sample_status": "unavailable",
            "phase_sample_inferred_q_vector": None,
            "phase_sample_effective_site_phase_offsets": None,
            "phase_sample_max_residual": None,
        }

    phase_lookup = supercell_site_phase_lookup(realization)
    if not phase_lookup:
        return {
            "phase_sample_status": "unavailable",
            "phase_sample_inferred_q_vector": None,
            "phase_sample_effective_site_phase_offsets": None,
            "phase_sample_max_residual": None,
        }

    site_count = infer_payload_site_count(payload)
    positions = list(payload.get("positions", []))
    if len(positions) < site_count:
        positions = positions + [[0.0, 0.0, 0.0] for _ in range(site_count - len(positions))]

    inferred_q_vector = [0.0, 0.0, 0.0]
    for axis in range(3):
        extent = int(supercell_shape[axis])
        if extent <= 1:
            continue
        axis_differences = []
        for cell_x in range(int(supercell_shape[0])):
            for cell_y in range(int(supercell_shape[1])):
                for cell_z in range(int(supercell_shape[2])):
                    cell = [cell_x, cell_y, cell_z]
                    if cell[axis] >= extent - 1:
                        continue
                    next_cell = list(cell)
                    next_cell[axis] += 1
                    for site in range(site_count):
                        left_phase = phase_lookup.get((tuple(cell), site))
                        right_phase = phase_lookup.get((tuple(next_cell), site))
                        if left_phase is None or right_phase is None:
                            continue
                        axis_differences.append(wrap_phase_difference(right_phase - left_phase))
        if not axis_differences:
            continue
        reference_difference = axis_differences[0]
        max_axis_residual = max(
            abs(wrap_phase_difference(value - reference_difference))
            for value in axis_differences
        )
        if max_axis_residual > tolerance:
            return {
                "phase_sample_status": "not-single-q-reducible",
                "phase_sample_inferred_q_vector": None,
                "phase_sample_effective_site_phase_offsets": None,
                "phase_sample_max_residual": float(max_axis_residual),
            }
        inferred_q_vector[axis] = float(reference_difference / (2.0 * math.pi))

    phase_sample_effective_site_phase_offsets = {}
    reference_cell = (0, 0, 0)
    for site in range(site_count):
        phase = phase_lookup.get((reference_cell, site))
        if phase is None:
            return {
                "phase_sample_status": "unavailable",
                "phase_sample_inferred_q_vector": None,
                "phase_sample_effective_site_phase_offsets": None,
                "phase_sample_max_residual": None,
            }
        basis_position = positions[site] if site < len(positions) else [0.0, 0.0, 0.0]
        basis_phase = 2.0 * math.pi * sum(
            float(inferred_q_vector[axis]) * float(basis_position[axis])
            for axis in range(3)
        )
        phase_sample_effective_site_phase_offsets[str(site)] = stabilize_float(
            wrap_phase_difference(phase - basis_phase)
        )

    max_phase_fit_residual = 0.0
    for (cell, site), phase in phase_lookup.items():
        basis_position = positions[site] if site < len(positions) else [0.0, 0.0, 0.0]
        predicted_phase = 2.0 * math.pi * sum(
            float(inferred_q_vector[axis]) * (float(cell[axis]) + float(basis_position[axis]))
            for axis in range(3)
        ) + float(phase_sample_effective_site_phase_offsets[str(site)])
        max_phase_fit_residual = max(
            max_phase_fit_residual,
            abs(wrap_phase_difference(phase - predicted_phase)),
        )

    if max_phase_fit_residual > tolerance:
        return {
            "phase_sample_status": "not-single-q-reducible",
            "phase_sample_inferred_q_vector": None,
            "phase_sample_effective_site_phase_offsets": None,
            "phase_sample_max_residual": float(max_phase_fit_residual),
        }

    return {
        "phase_sample_status": "single-q-compatible",
        "phase_sample_inferred_q_vector": [stabilize_float(value) for value in inferred_q_vector],
        "phase_sample_effective_site_phase_offsets": phase_sample_effective_site_phase_offsets,
        "phase_sample_max_residual": stabilize_float(max_phase_fit_residual),
    }


def max_site_phase_offset_difference(left, right):
    if not isinstance(left, dict) or not isinstance(right, dict):
        return None
    sites = sorted(set(left) | set(right), key=lambda value: int(value))
    if not sites:
        return 0.0
    return max(
        abs(wrap_phase_difference(float(left.get(site, 0.0)) - float(right.get(site, 0.0))))
        for site in sites
    )


def metadata_phase_sample_cross_check(
    *,
    single_q_q_vector,
    rotating_frame_wavevector,
    realization_status,
    effective_site_phase_offsets,
    source_kind,
    phase_sample_summary,
    tolerance=1e-8,
):
    metadata_available = bool(
        source_kind in {"rotating_frame_transform", "rotating_frame_realization"}
        or realization_status in {
            "single-q-compatible",
            "composite-single-q-compatible",
            "multi-wavevector-composite",
            "units-unsupported",
        }
    )
    phase_sample_available = bool(phase_sample_summary.get("phase_sample_status") != "unavailable")

    if not metadata_available or not phase_sample_available:
        return {
            "status": "unavailable",
            "metadata_available": bool(metadata_available),
            "phase_sample_available": bool(phase_sample_available),
            "conflict_sources": [],
            "likely_conflicting_path": "unknown",
            "max_wavevector_difference": None,
            "max_site_phase_offset_difference": None,
        }

    conflict_sources = []
    phase_sample_inferred_q_vector = phase_sample_summary.get("phase_sample_inferred_q_vector")
    phase_sample_effective_site_phase_offsets = phase_sample_summary.get("phase_sample_effective_site_phase_offsets")
    phase_sample_status = str(phase_sample_summary.get("phase_sample_status", "unavailable"))

    metadata_single_q_difference = None
    phase_sample_single_q_difference = None
    metadata_phase_sample_wavevector_difference = None
    if isinstance(rotating_frame_wavevector, list):
        _, _, metadata_single_q_difference = compare_wavevectors(
            single_q_q_vector,
            rotating_frame_wavevector,
        )
    if isinstance(phase_sample_inferred_q_vector, list):
        _, _, phase_sample_single_q_difference = compare_wavevectors(
            single_q_q_vector,
            phase_sample_inferred_q_vector,
        )
    if isinstance(rotating_frame_wavevector, list) and isinstance(phase_sample_inferred_q_vector, list):
        _, _, metadata_phase_sample_wavevector_difference = compare_wavevectors(
            rotating_frame_wavevector,
            phase_sample_inferred_q_vector,
        )

    max_site_phase_offset_diff = max_site_phase_offset_difference(
        effective_site_phase_offsets,
        phase_sample_effective_site_phase_offsets,
    )

    if phase_sample_status == "single-q-compatible":
        if (
            metadata_phase_sample_wavevector_difference is not None
            and metadata_phase_sample_wavevector_difference > tolerance
        ):
            conflict_sources.append("wavevector")
        if (
            max_site_phase_offset_diff is not None
            and max_site_phase_offset_diff > tolerance
        ):
            conflict_sources.append("site_phase_offsets")
        if realization_status == "multi-wavevector-composite":
            conflict_sources.append("component_structure")
    elif phase_sample_status == "not-single-q-reducible":
        conflict_sources.append("phase_pattern")

    likely_conflicting_path = "none"
    if conflict_sources:
        likely_conflicting_path = "ambiguous"
        if "phase_pattern" in conflict_sources:
            if metadata_single_q_difference is not None and metadata_single_q_difference <= tolerance:
                likely_conflicting_path = "phase_samples"
        elif "wavevector" in conflict_sources:
            metadata_matches_single_q = (
                metadata_single_q_difference is not None and metadata_single_q_difference <= tolerance
            )
            phase_samples_match_single_q = (
                phase_sample_single_q_difference is not None and phase_sample_single_q_difference <= tolerance
            )
            if metadata_matches_single_q and not phase_samples_match_single_q:
                likely_conflicting_path = "phase_samples"
            elif phase_samples_match_single_q and not metadata_matches_single_q:
                likely_conflicting_path = "metadata"

    return {
        "status": "conflict" if conflict_sources else "consistent",
        "metadata_available": bool(metadata_available),
        "phase_sample_available": bool(phase_sample_available),
        "conflict_sources": conflict_sources,
        "likely_conflicting_path": likely_conflicting_path,
        "max_wavevector_difference": (
            stabilize_float(metadata_phase_sample_wavevector_difference)
            if metadata_phase_sample_wavevector_difference is not None
            else None
        ),
        "max_site_phase_offset_difference": (
            stabilize_float(max_site_phase_offset_diff)
            if max_site_phase_offset_diff is not None
            else None
        ),
    }


def single_q_rotating_frame_consistency(payload, *, tolerance=1e-12):
    single_q_q_vector = [float(value) for value in payload.get("q_vector", [])]
    transform = payload.get("rotating_frame_transform", {})
    realization = payload.get("rotating_frame_realization", {})
    site_count = infer_payload_site_count(payload)
    phase_sample_summary = infer_single_q_from_supercell_site_phases(
        payload,
        realization,
        tolerance=max(float(tolerance), 1e-8),
    )

    rotating_frame_wavevector = None
    wavevector_units = None
    source_kind = None
    realization_status = "unavailable"
    effective_site_phase_offsets = None

    components = list(realization.get("components", [])) if isinstance(realization, dict) else []
    if components:
        component_vectors = []
        component_units = set()
        effective_site_phase_offsets = {str(site): 0.0 for site in range(site_count)}
        for component in components:
            vector = component.get("wavevector")
            units = component.get("wavevector_units")
            if not isinstance(vector, list):
                return {
                    "status": "unavailable",
                    "single_q_q_vector": single_q_q_vector,
                    "rotating_frame_wavevector": None,
                    "wavevector_units": str(units) if units is not None else None,
                    "source_kind": "rotating_frame_realization",
                    "realization_status": "component-wavevector-unavailable",
                    "effective_site_phase_offsets": effective_site_phase_offsets,
                    **phase_sample_summary,
                    "metadata_phase_sample_cross_check": metadata_phase_sample_cross_check(
                        single_q_q_vector=single_q_q_vector,
                        rotating_frame_wavevector=None,
                        realization_status="component-wavevector-unavailable",
                        effective_site_phase_offsets=effective_site_phase_offsets,
                        source_kind="rotating_frame_realization",
                        phase_sample_summary=phase_sample_summary,
                        tolerance=max(float(tolerance), 1e-8),
                    ),
                    "max_wavevector_difference": None,
                }
            component_vectors.append([float(value) for value in vector])
            component_units.add(str(units) if units is not None else "")
            for site, value in normalized_site_phase_offsets(
                site_count,
                component.get("site_phase_offsets", {}),
            ).items():
                effective_site_phase_offsets[site] = float(effective_site_phase_offsets.get(site, 0.0)) + float(value)

        source_kind = "rotating_frame_realization"
        if component_units != {"reciprocal_lattice_units"}:
            return {
                "status": "units-unsupported",
                "single_q_q_vector": single_q_q_vector,
                "rotating_frame_wavevector": None,
                "wavevector_units": sorted(component_units),
                "source_kind": source_kind,
                "realization_status": "component-units-unsupported",
                "effective_site_phase_offsets": effective_site_phase_offsets,
                "component_count": int(len(components)),
                **phase_sample_summary,
                "metadata_phase_sample_cross_check": metadata_phase_sample_cross_check(
                    single_q_q_vector=single_q_q_vector,
                    rotating_frame_wavevector=None,
                    realization_status="component-units-unsupported",
                    effective_site_phase_offsets=effective_site_phase_offsets,
                    source_kind=source_kind,
                    phase_sample_summary=phase_sample_summary,
                    tolerance=max(float(tolerance), 1e-8),
                ),
                "max_wavevector_difference": None,
            }

        rotating_frame_wavevector = list(component_vectors[0])
        wavevector_units = "reciprocal_lattice_units"
        max_component_wavevector_difference = 0.0
        for vector in component_vectors[1:]:
            _, _, component_difference = compare_wavevectors(rotating_frame_wavevector, vector)
            max_component_wavevector_difference = max(max_component_wavevector_difference, component_difference)

        if max_component_wavevector_difference > tolerance:
            return {
                "status": "composite-incompatible",
                "single_q_q_vector": single_q_q_vector,
                "rotating_frame_wavevector": None,
                "wavevector_units": wavevector_units,
                "source_kind": source_kind,
                "realization_status": "multi-wavevector-composite",
                "effective_site_phase_offsets": effective_site_phase_offsets,
                "component_count": int(len(components)),
                "max_component_wavevector_difference": float(max_component_wavevector_difference),
                **phase_sample_summary,
                "metadata_phase_sample_cross_check": metadata_phase_sample_cross_check(
                    single_q_q_vector=single_q_q_vector,
                    rotating_frame_wavevector=None,
                    realization_status="multi-wavevector-composite",
                    effective_site_phase_offsets=effective_site_phase_offsets,
                    source_kind=source_kind,
                    phase_sample_summary=phase_sample_summary,
                    tolerance=max(float(tolerance), 1e-8),
                ),
                "max_wavevector_difference": None,
            }

        realization_status = "composite-single-q-compatible"
        padded_single_q, padded_rotating_frame, max_wavevector_difference = compare_wavevectors(
            single_q_q_vector,
            rotating_frame_wavevector,
        )
        return {
            "status": "consistent" if max_wavevector_difference <= tolerance else "mismatch",
            "single_q_q_vector": padded_single_q,
            "rotating_frame_wavevector": padded_rotating_frame,
            "wavevector_units": wavevector_units,
            "source_kind": source_kind,
            "realization_status": realization_status,
            "effective_site_phase_offsets": effective_site_phase_offsets,
            "component_count": int(len(components)),
            "tolerance": float(tolerance),
            "max_component_wavevector_difference": float(max_component_wavevector_difference),
            **phase_sample_summary,
            "metadata_phase_sample_cross_check": metadata_phase_sample_cross_check(
                single_q_q_vector=single_q_q_vector,
                rotating_frame_wavevector=padded_rotating_frame,
                realization_status=realization_status,
                effective_site_phase_offsets=effective_site_phase_offsets,
                source_kind=source_kind,
                phase_sample_summary=phase_sample_summary,
                tolerance=max(float(tolerance), 1e-8),
            ),
            "max_wavevector_difference": float(max_wavevector_difference),
        }

    if isinstance(transform, dict) and isinstance(transform.get("wavevector"), list):
        rotating_frame_wavevector = [float(value) for value in transform.get("wavevector", [])]
        wavevector_units = str(transform.get("wavevector_units", "")) or None
        source_kind = "rotating_frame_transform"
        effective_site_phase_offsets = normalized_site_phase_offsets(
            site_count,
            transform.get("sublattice_phase_offsets", {}),
        )
    elif isinstance(realization, dict) and isinstance(realization.get("wavevector"), list):
        rotating_frame_wavevector = [float(value) for value in realization.get("wavevector", [])]
        wavevector_units = str(realization.get("wavevector_units", "")) or None
        source_kind = "rotating_frame_realization"
        effective_site_phase_offsets = normalized_site_phase_offsets(
            site_count,
            realization.get("site_phase_offsets", {}),
        )

    if rotating_frame_wavevector is None:
        if phase_sample_summary.get("phase_sample_status") == "single-q-compatible":
            inferred_q_vector = list(phase_sample_summary.get("phase_sample_inferred_q_vector", []))
            padded_single_q, padded_rotating_frame, max_wavevector_difference = compare_wavevectors(
                single_q_q_vector,
                inferred_q_vector,
            )
            return {
                "status": "consistent" if max_wavevector_difference <= tolerance else "mismatch",
                "single_q_q_vector": padded_single_q,
                "rotating_frame_wavevector": padded_rotating_frame,
                "wavevector_units": "reciprocal_lattice_units",
                "source_kind": "supercell_site_phases",
                "realization_status": "phase-sampled-single-q-compatible",
                "effective_site_phase_offsets": phase_sample_summary.get("phase_sample_effective_site_phase_offsets"),
                "tolerance": float(tolerance),
                **phase_sample_summary,
                "metadata_phase_sample_cross_check": metadata_phase_sample_cross_check(
                    single_q_q_vector=single_q_q_vector,
                    rotating_frame_wavevector=None,
                    realization_status="phase-sampled-single-q-compatible",
                    effective_site_phase_offsets=phase_sample_summary.get("phase_sample_effective_site_phase_offsets"),
                    source_kind="supercell_site_phases",
                    phase_sample_summary=phase_sample_summary,
                    tolerance=max(float(tolerance), 1e-8),
                ),
                "max_wavevector_difference": float(max_wavevector_difference),
            }
        if phase_sample_summary.get("phase_sample_status") == "not-single-q-reducible":
            return {
                "status": "phase-pattern-incompatible",
                "single_q_q_vector": single_q_q_vector,
                "rotating_frame_wavevector": None,
                "wavevector_units": None,
                "source_kind": "supercell_site_phases",
                "realization_status": "supercell-site-phases-not-single-q-reducible",
                "effective_site_phase_offsets": None,
                **phase_sample_summary,
                "metadata_phase_sample_cross_check": metadata_phase_sample_cross_check(
                    single_q_q_vector=single_q_q_vector,
                    rotating_frame_wavevector=None,
                    realization_status="supercell-site-phases-not-single-q-reducible",
                    effective_site_phase_offsets=None,
                    source_kind="supercell_site_phases",
                    phase_sample_summary=phase_sample_summary,
                    tolerance=max(float(tolerance), 1e-8),
                ),
                "max_wavevector_difference": None,
            }
        return {
            "status": "unavailable",
            "single_q_q_vector": single_q_q_vector,
            "rotating_frame_wavevector": None,
            "wavevector_units": wavevector_units,
            "source_kind": source_kind,
            "realization_status": realization_status,
            "effective_site_phase_offsets": effective_site_phase_offsets,
            **phase_sample_summary,
            "metadata_phase_sample_cross_check": metadata_phase_sample_cross_check(
                single_q_q_vector=single_q_q_vector,
                rotating_frame_wavevector=None,
                realization_status=realization_status,
                effective_site_phase_offsets=effective_site_phase_offsets,
                source_kind=source_kind,
                phase_sample_summary=phase_sample_summary,
                tolerance=max(float(tolerance), 1e-8),
            ),
            "max_wavevector_difference": None,
        }

    if wavevector_units != "reciprocal_lattice_units":
        return {
            "status": "units-unsupported",
            "single_q_q_vector": single_q_q_vector,
            "rotating_frame_wavevector": rotating_frame_wavevector,
            "wavevector_units": wavevector_units,
            "source_kind": source_kind,
            "realization_status": "units-unsupported",
            "effective_site_phase_offsets": effective_site_phase_offsets,
            **phase_sample_summary,
            "metadata_phase_sample_cross_check": metadata_phase_sample_cross_check(
                single_q_q_vector=single_q_q_vector,
                rotating_frame_wavevector=rotating_frame_wavevector,
                realization_status="units-unsupported",
                effective_site_phase_offsets=effective_site_phase_offsets,
                source_kind=source_kind,
                phase_sample_summary=phase_sample_summary,
                tolerance=max(float(tolerance), 1e-8),
            ),
            "max_wavevector_difference": None,
        }

    padded_single_q, padded_rotating_frame, max_wavevector_difference = compare_wavevectors(
        single_q_q_vector,
        rotating_frame_wavevector,
    )
    return {
        "status": "consistent" if max_wavevector_difference <= tolerance else "mismatch",
        "single_q_q_vector": padded_single_q,
        "rotating_frame_wavevector": padded_rotating_frame,
        "wavevector_units": wavevector_units,
        "source_kind": source_kind,
        "realization_status": "single-q-compatible",
        "effective_site_phase_offsets": effective_site_phase_offsets,
        "tolerance": float(tolerance),
        **phase_sample_summary,
        "metadata_phase_sample_cross_check": metadata_phase_sample_cross_check(
            single_q_q_vector=single_q_q_vector,
            rotating_frame_wavevector=padded_rotating_frame,
            realization_status="single-q-compatible",
            effective_site_phase_offsets=effective_site_phase_offsets,
            source_kind=source_kind,
            phase_sample_summary=phase_sample_summary,
            tolerance=max(float(tolerance), 1e-8),
        ),
        "max_wavevector_difference": float(max_wavevector_difference),
    }


def metadata_local_rotating_frame_summary(payload, *, tolerance=1e-8):
    site_count = infer_payload_site_count(payload)
    transform = payload.get("rotating_frame_transform", {})
    realization = payload.get("rotating_frame_realization", {})

    if isinstance(transform, dict) and isinstance(transform.get("wavevector"), list):
        return {
            "status": "single-q-compatible",
            "source_kind": "rotating_frame_transform",
            "wavevector": [float(value) for value in transform.get("wavevector", [])],
            "wavevector_units": str(transform.get("wavevector_units", "")) or None,
            "effective_site_phase_offsets": normalized_site_phase_offsets(
                site_count,
                transform.get("sublattice_phase_offsets", {}),
            ),
        }

    components = list(realization.get("components", [])) if isinstance(realization, dict) else []
    if components:
        vectors = []
        units = set()
        effective_site_phase_offsets = {str(site): 0.0 for site in range(site_count)}
        for component in components:
            vector = component.get("wavevector")
            if not isinstance(vector, list):
                return {
                    "status": "unavailable",
                    "source_kind": "rotating_frame_realization",
                    "wavevector": None,
                    "wavevector_units": None,
                    "effective_site_phase_offsets": effective_site_phase_offsets,
                }
            vectors.append([float(value) for value in vector])
            units.add(str(component.get("wavevector_units", "")) or None)
            for site, value in normalized_site_phase_offsets(
                site_count,
                component.get("site_phase_offsets", {}),
            ).items():
                effective_site_phase_offsets[site] = float(effective_site_phase_offsets.get(site, 0.0)) + float(value)
        if units != {"reciprocal_lattice_units"}:
            return {
                "status": "units-unsupported",
                "source_kind": "rotating_frame_realization",
                "wavevector": None,
                "wavevector_units": sorted(units),
                "effective_site_phase_offsets": effective_site_phase_offsets,
            }
        reference_vector = vectors[0]
        max_component_wavevector_difference = 0.0
        for vector in vectors[1:]:
            _, _, difference = compare_wavevectors(reference_vector, vector)
            max_component_wavevector_difference = max(max_component_wavevector_difference, difference)
        if max_component_wavevector_difference > float(tolerance):
            return {
                "status": "multi-wavevector-composite",
                "source_kind": "rotating_frame_realization",
                "wavevector": None,
                "wavevector_units": "reciprocal_lattice_units",
                "effective_site_phase_offsets": effective_site_phase_offsets,
            }
        return {
            "status": "single-q-compatible",
            "source_kind": "rotating_frame_realization",
            "wavevector": reference_vector,
            "wavevector_units": "reciprocal_lattice_units",
            "effective_site_phase_offsets": effective_site_phase_offsets,
        }

    if isinstance(realization, dict) and isinstance(realization.get("wavevector"), list):
        return {
            "status": "single-q-compatible",
            "source_kind": "rotating_frame_realization",
            "wavevector": [float(value) for value in realization.get("wavevector", [])],
            "wavevector_units": str(realization.get("wavevector_units", "")) or None,
            "effective_site_phase_offsets": normalized_site_phase_offsets(
                site_count,
                realization.get("site_phase_offsets", {}),
            ),
        }

    return {
        "status": "unavailable",
        "source_kind": None,
        "wavevector": None,
        "wavevector_units": None,
        "effective_site_phase_offsets": None,
    }


def local_rays_rotating_frame_metadata_phase_sample_cross_check(payload, *, tolerance=1e-8):
    metadata = metadata_local_rotating_frame_summary(payload, tolerance=tolerance)
    phase_sample = infer_single_q_from_supercell_site_phases(
        payload,
        payload.get("rotating_frame_realization", {}),
        tolerance=float(tolerance),
    )

    if metadata.get("status") == "unavailable" or phase_sample.get("phase_sample_status") == "unavailable":
        return {
            "status": "unavailable",
            "conflict_sources": [],
            "likely_conflicting_path": "unknown",
            "max_wavevector_difference": None,
            "max_site_phase_offset_difference": None,
            "metadata_status": str(metadata.get("status", "unavailable")),
            "phase_sample_status": str(phase_sample.get("phase_sample_status", "unavailable")),
        }

    conflict_sources = []
    max_wavevector_difference = None
    max_site_phase_offset_diff = max_site_phase_offset_difference(
        metadata.get("effective_site_phase_offsets"),
        phase_sample.get("phase_sample_effective_site_phase_offsets"),
    )

    if metadata.get("status") == "multi-wavevector-composite":
        if phase_sample.get("phase_sample_status") == "single-q-compatible":
            conflict_sources.append("component_structure")
    elif metadata.get("status") == "single-q-compatible":
        if phase_sample.get("phase_sample_status") == "single-q-compatible":
            _, _, max_wavevector_difference = compare_wavevectors(
                metadata.get("wavevector") or [],
                phase_sample.get("phase_sample_inferred_q_vector") or [],
            )
            if max_wavevector_difference > float(tolerance):
                conflict_sources.append("wavevector")
            if (
                max_site_phase_offset_diff is not None
                and max_site_phase_offset_diff > float(tolerance)
            ):
                conflict_sources.append("site_phase_offsets")
        elif phase_sample.get("phase_sample_status") == "not-single-q-reducible":
            conflict_sources.append("phase_pattern")

    likely_conflicting_path = "none"
    if conflict_sources:
        likely_conflicting_path = "ambiguous"
        if conflict_sources == ["phase_pattern"] and metadata.get("status") == "single-q-compatible":
            likely_conflicting_path = "phase_samples"

    return {
        "status": "conflict" if conflict_sources else "consistent",
        "conflict_sources": conflict_sources,
        "likely_conflicting_path": likely_conflicting_path,
        "max_wavevector_difference": (
            stabilize_float(max_wavevector_difference)
            if max_wavevector_difference is not None
            else None
        ),
        "max_site_phase_offset_difference": (
            stabilize_float(max_site_phase_offset_diff)
            if max_site_phase_offset_diff is not None
            else None
        ),
        "metadata_status": str(metadata.get("status", "unavailable")),
        "phase_sample_status": str(phase_sample.get("phase_sample_status", "unavailable")),
    }
