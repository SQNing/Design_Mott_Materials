#!/usr/bin/env python3

from common.rotating_frame_realization import resolve_rotating_frame_realization


def _normalize_channel_phase_rules(rules):
    if not isinstance(rules, dict):
        return {}
    return {str(key): str(value) for key, value in rules.items()}


def _normalize_quadratic_phase_dressing(dressing):
    if not isinstance(dressing, dict):
        return None
    kind = str(dressing.get("kind", "")).strip()
    if not kind or kind == "not-needed":
        return None
    normalized = {
        "status": str(dressing.get("status", "explicit")),
        "kind": kind,
        "source_realization_kind": str(dressing.get("source_realization_kind", "")),
        "phase_coordinate_semantics": str(dressing.get("phase_coordinate_semantics", "")),
        "channel_phase_rules": _normalize_channel_phase_rules(dressing.get("channel_phase_rules", {})),
        "site_phase_count": int(dressing.get("site_phase_count", 0)),
    }
    if "component_count" in dressing:
        normalized["component_count"] = int(dressing.get("component_count", 0))
    if "composition_rule" in dressing:
        normalized["composition_rule"] = str(dressing.get("composition_rule", ""))
    if isinstance(dressing.get("supercell_shape"), list):
        normalized["supercell_shape"] = [int(value) for value in dressing.get("supercell_shape", [])]
    return normalized


def _compile_from_realization(realization):
    if not isinstance(realization, dict):
        return None
    site_phase_entries = realization.get("supercell_site_phases")
    site_phase_count = len(site_phase_entries) if isinstance(site_phase_entries, list) else 0
    dressing = {
        "status": "explicit",
        "kind": "site_phase_gauge_rules",
        "source_realization_kind": str(realization.get("kind", "")),
        "phase_coordinate_semantics": str(realization.get("phase_coordinate_semantics", "")),
        "channel_phase_rules": {
            "normal": "target_minus_source",
            "pair": "minus_source_minus_target",
            "pair_conjugate": "source_plus_target",
            "linear_creation": "minus_source",
            "linear_annihilation": "source",
        },
        "site_phase_count": int(site_phase_count),
    }
    if "component_count" in realization:
        dressing["component_count"] = int(realization.get("component_count", 0))
    if "composition_rule" in realization:
        dressing["composition_rule"] = str(realization.get("composition_rule", ""))
    if isinstance(realization.get("supercell_shape"), list):
        dressing["supercell_shape"] = [int(value) for value in realization.get("supercell_shape", [])]
    return dressing


def resolve_quadratic_phase_dressing(model):
    if not isinstance(model, dict):
        return None

    candidates = [
        model.get("quadratic_phase_dressing"),
        (model.get("effective_model", {}) or {}).get("quadratic_phase_dressing"),
        (model.get("normalized_model", {}) or {}).get("quadratic_phase_dressing"),
    ]
    for candidate in candidates:
        normalized = _normalize_quadratic_phase_dressing(candidate)
        if normalized is not None:
            return normalized

    realization = resolve_rotating_frame_realization(model)
    if realization is None:
        return None
    return _compile_from_realization(realization)


def summarize_quadratic_phase_dressing(model, *, application_kind, consumed=True, reason=None):
    dressing = resolve_quadratic_phase_dressing(model)
    if dressing is None:
        return None
    summary = dict(dressing)
    summary["consumed"] = bool(consumed)
    summary["application_kind"] = str(application_kind)
    if reason is not None:
        summary["reason"] = str(reason)
    return summary
