#!/usr/bin/env python3


def _normalize_wavevector(vector):
    if not isinstance(vector, list):
        return []
    return [float(value) for value in vector]


def _normalize_phase_offsets(offsets):
    if not isinstance(offsets, dict):
        return {}
    normalized = {}
    for key, value in offsets.items():
        normalized[str(key)] = float(value)
    return normalized


def normalize_rotating_frame_transform(transform):
    if not isinstance(transform, dict):
        return None
    kind = str(transform.get("kind", "")).strip()
    if not kind or kind == "not-needed":
        return None

    normalized = {
        "status": str(transform.get("status", "explicit")),
        "kind": kind,
    }
    for key in ("source_frame_kind", "source_order_kind", "wavevector_units", "phase_rule", "phase_origin", "rotation_axis"):
        value = transform.get(key)
        if value is not None:
            normalized[key] = str(value)
    if "wavevector" in transform:
        normalized["wavevector"] = _normalize_wavevector(transform.get("wavevector"))
    if "sublattice_phase_offsets" in transform:
        normalized["sublattice_phase_offsets"] = _normalize_phase_offsets(transform.get("sublattice_phase_offsets"))
    return normalized


def resolve_rotating_frame_transform(model):
    if not isinstance(model, dict):
        return None

    candidates = [
        model.get("rotating_frame_transform"),
        (model.get("effective_model", {}) or {}).get("rotating_frame_transform"),
        (model.get("normalized_model", {}) or {}).get("rotating_frame_transform"),
    ]
    for candidate in candidates:
        normalized = normalize_rotating_frame_transform(candidate)
        if normalized is not None:
            return normalized
    return None
