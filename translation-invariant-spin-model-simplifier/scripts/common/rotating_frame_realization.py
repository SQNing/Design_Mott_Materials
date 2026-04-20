#!/usr/bin/env python3
import math
from itertools import product

from common.classical_contract_resolution import get_classical_supercell_shape
from common.rotating_frame_metadata import resolve_rotating_frame_transform


def _normalize_wavevector(vector):
    if not isinstance(vector, list):
        return []
    return [float(value) for value in vector]


def _normalize_phase_offsets(offsets):
    if not isinstance(offsets, dict):
        return {}
    return {str(key): float(value) for key, value in offsets.items()}


def _normalize_realization_component(component):
    if not isinstance(component, dict):
        return None
    normalized = {}
    for key in (
        "kind",
        "source_transform_kind",
        "source_order_kind",
        "wavevector_units",
        "phase_rule",
        "rotation_axis",
        "phase_coordinate_semantics",
    ):
        value = component.get(key)
        if value is not None:
            normalized[key] = str(value)
    if "wavevector" in component:
        normalized["wavevector"] = _normalize_wavevector(component.get("wavevector"))
    if "site_phase_offsets" in component:
        normalized["site_phase_offsets"] = _normalize_phase_offsets(component.get("site_phase_offsets"))
    return normalized or None


def _normalize_components(components):
    if not isinstance(components, list):
        return []
    normalized = []
    for component in components:
        item = _normalize_realization_component(component)
        if item is not None:
            normalized.append(item)
    return normalized


def _normalize_realization(realization):
    if not isinstance(realization, dict):
        return None
    kind = str(realization.get("kind", "")).strip()
    if not kind or kind == "not-needed":
        return None

    normalized = {
        "status": str(realization.get("status", "explicit")),
        "kind": kind,
    }
    for key in (
        "source_transform_kind",
        "source_order_kind",
        "wavevector_units",
        "phase_rule",
        "rotation_axis",
        "phase_coordinate_semantics",
        "composition_rule",
    ):
        value = realization.get(key)
        if value is not None:
            normalized[key] = str(value)
    if "wavevector" in realization:
        normalized["wavevector"] = _normalize_wavevector(realization.get("wavevector"))
    if "site_phase_offsets" in realization:
        normalized["site_phase_offsets"] = _normalize_phase_offsets(realization.get("site_phase_offsets"))
    if "supercell_site_phases" in realization:
        normalized["supercell_site_phases"] = list(realization.get("supercell_site_phases") or [])
    if "supercell_shape" in realization:
        normalized["supercell_shape"] = [int(value) for value in realization.get("supercell_shape", [])]
    components = _normalize_components(realization.get("components"))
    if components:
        normalized["components"] = components
        normalized["component_count"] = len(components)
    return normalized


def _compile_realization_from_transform(transform):
    if transform is None:
        return None

    source_frame_kind = str(transform.get("source_frame_kind", "")).strip()
    if source_frame_kind == "single_q_rotating_frame":
        kind = "single_q_site_phase_rotation"
    else:
        kind = "generic_site_phase_rotation"

    units = transform.get("wavevector_units")
    if units == "reciprocal_lattice_units":
        phase_coordinate_semantics = "fractional_direct_positions_with_two_pi_factor"
    elif units == "cartesian_reciprocal":
        phase_coordinate_semantics = "cartesian_positions"
    else:
        phase_coordinate_semantics = "unspecified"

    return {
        "status": str(transform.get("status", "explicit")),
        "kind": kind,
        "source_transform_kind": str(transform.get("kind", "site_phase_rotation")),
        "source_order_kind": str(transform.get("source_order_kind", "")),
        "wavevector": _normalize_wavevector(transform.get("wavevector")),
        "wavevector_units": str(units) if units is not None else None,
        "phase_rule": str(transform.get("phase_rule", "")),
        "rotation_axis": str(transform.get("rotation_axis", "")),
        "site_phase_offsets": _normalize_phase_offsets(transform.get("sublattice_phase_offsets", {})),
        "phase_coordinate_semantics": phase_coordinate_semantics,
    }


def _resolve_lattice_positions(model):
    if not isinstance(model, dict):
        return []
    positions = model.get("positions")
    if isinstance(positions, list) and positions:
        return [[float(value) for value in position] for position in positions]
    lattice = model.get("lattice", {})
    positions = lattice.get("positions")
    if isinstance(positions, list) and positions:
        return [[float(value) for value in position] for position in positions]
    return []


def _resolve_lattice_vectors(model):
    if not isinstance(model, dict):
        return []
    vectors = model.get("lattice_vectors")
    if isinstance(vectors, list) and vectors:
        return [[float(value) for value in vector] for vector in vectors]
    lattice = model.get("lattice", {})
    vectors = lattice.get("lattice_vectors")
    if isinstance(vectors, list) and vectors:
        return [[float(value) for value in vector] for vector in vectors]
    return []


def _resolve_supercell_shape(model):
    if not isinstance(model, dict):
        return None
    candidate_paths = [
        model.get("supercell_shape"),
        (model.get("ordering", {}) or {}).get("supercell_shape"),
        (model.get("classical", {}) or {}).get("supercell_shape"),
        get_classical_supercell_shape(model, prefer_nested_legacy=True),
    ]
    for candidate in candidate_paths:
        if isinstance(candidate, list) and len(candidate) == 3:
            return [int(value) for value in candidate]
    return None


def _fractional_to_cartesian(fractional, lattice_vectors):
    cartesian = [0.0, 0.0, 0.0]
    for axis, coefficient in enumerate(fractional):
        if axis >= len(lattice_vectors):
            break
        vector = lattice_vectors[axis]
        for component in range(min(3, len(vector))):
            cartesian[component] += float(coefficient) * float(vector[component])
    return cartesian


def _phase_for_position(realization, position, lattice_vectors):
    wavevector = list(realization.get("wavevector") or [])
    units = realization.get("wavevector_units")
    if units == "reciprocal_lattice_units":
        return 2.0 * math.pi * sum(
            float(wavevector[axis]) * float(position[axis])
            for axis in range(min(len(wavevector), len(position)))
        )
    if units == "cartesian_reciprocal":
        cartesian = _fractional_to_cartesian(position, lattice_vectors)
        return sum(
            float(wavevector[axis]) * float(cartesian[axis])
            for axis in range(min(len(wavevector), len(cartesian)))
        )
    return None


def _resolve_phase_coordinate_semantics(realization):
    explicit = realization.get("phase_coordinate_semantics")
    if explicit is not None:
        return str(explicit)
    components = list(realization.get("components") or [])
    semantics = {
        str(component.get("phase_coordinate_semantics", "")).strip()
        for component in components
        if str(component.get("phase_coordinate_semantics", "")).strip()
    }
    if len(semantics) == 1:
        return next(iter(semantics))
    if len(semantics) > 1:
        return "mixed-component-semantics"
    return ""


def _site_phase_offset(realization, site_index):
    offsets = realization.get("site_phase_offsets", {})
    if not isinstance(offsets, dict):
        return 0.0
    return float(offsets.get(str(site_index), 0.0))


def _phase_components(realization):
    components = list(realization.get("components") or [])
    if components:
        return components
    return [realization]


def _supercell_site_phases(realization, model):
    supercell_shape = _resolve_supercell_shape(model)
    positions = _resolve_lattice_positions(model)
    if supercell_shape is None or not positions:
        return None, None

    lattice_vectors = _resolve_lattice_vectors(model)
    samples = []
    for cell in product(*(range(extent) for extent in supercell_shape)):
        for site_index, basis_position in enumerate(positions):
            fractional_position = [
                float(cell[axis]) + (float(basis_position[axis]) if axis < len(basis_position) else 0.0)
                for axis in range(3)
            ]
            phase = 0.0
            for component in _phase_components(realization):
                component_phase = _phase_for_position(component, fractional_position, lattice_vectors)
                if component_phase is None:
                    return None, None
                phase += component_phase + _site_phase_offset(component, site_index)
            samples.append(
                {
                    "cell": [int(value) for value in cell],
                    "site": int(site_index),
                    "phase": float(phase),
                }
            )
    return samples, supercell_shape


def resolve_rotating_frame_realization(model):
    if not isinstance(model, dict):
        return None

    candidates = [
        model.get("rotating_frame_realization"),
        (model.get("effective_model", {}) or {}).get("rotating_frame_realization"),
        (model.get("normalized_model", {}) or {}).get("rotating_frame_realization"),
    ]
    realization = None
    for candidate in candidates:
        realization = _normalize_realization(candidate)
        if realization is not None:
            break

    if realization is None:
        realization = _compile_realization_from_transform(resolve_rotating_frame_transform(model))
    if realization is None:
        return None
    realization = dict(realization)
    phase_coordinate_semantics = _resolve_phase_coordinate_semantics(realization)
    if phase_coordinate_semantics:
        realization["phase_coordinate_semantics"] = phase_coordinate_semantics
    if isinstance(realization.get("components"), list):
        realization["component_count"] = len(realization.get("components", []))
        realization.setdefault("composition_rule", "sum_site_phases")

    samples, supercell_shape = _supercell_site_phases(realization, model)
    if samples is not None:
        realization["supercell_shape"] = [int(value) for value in supercell_shape]
        realization["supercell_site_phases"] = samples
    return realization


def resolve_supercell_site_phase_entries(model):
    realization = resolve_rotating_frame_realization(model)
    if not isinstance(realization, dict):
        return []
    entries = realization.get("supercell_site_phases")
    if not isinstance(entries, list):
        return []
    normalized = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        cell = entry.get("cell")
        site = entry.get("site")
        phase = entry.get("phase")
        if not isinstance(cell, list) or site is None or phase is None:
            continue
        normalized.append(
            {
                "cell": [int(value) for value in cell],
                "site": int(site),
                "phase": float(phase),
            }
        )
    return normalized


def summarize_rotating_frame_realization(model, *, application_kind, consumed=True, gauge_alignment_applied=None, reason=None):
    realization = resolve_rotating_frame_realization(model)
    if not isinstance(realization, dict):
        return None
    site_phase_entries = realization.get("supercell_site_phases")
    site_phase_count = len(site_phase_entries) if isinstance(site_phase_entries, list) else 0
    summary = {
        "consumed": bool(consumed),
        "application_kind": str(application_kind),
        "realization_kind": str(realization.get("kind", "")),
        "source_transform_kind": str(realization.get("source_transform_kind", "")),
        "phase_coordinate_semantics": str(realization.get("phase_coordinate_semantics", "")),
        "site_phase_count": int(site_phase_count),
    }
    if "component_count" in realization:
        summary["component_count"] = int(realization.get("component_count", 0))
    if "composition_rule" in realization:
        summary["composition_rule"] = str(realization.get("composition_rule", ""))
    if isinstance(realization.get("supercell_shape"), list):
        summary["supercell_shape"] = [int(value) for value in realization.get("supercell_shape", [])]
    if gauge_alignment_applied is not None:
        summary["gauge_alignment_applied"] = bool(gauge_alignment_applied)
    if reason is not None:
        summary["reason"] = str(reason)
    return summary
