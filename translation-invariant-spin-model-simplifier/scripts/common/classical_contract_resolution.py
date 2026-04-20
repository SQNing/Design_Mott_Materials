#!/usr/bin/env python3


def _as_mapping(payload):
    return payload if isinstance(payload, dict) else None


def get_classical_state_result(payload):
    mapping = _as_mapping(payload)
    if mapping is None:
        return None

    classical_state_result = mapping.get("classical_state_result")
    if isinstance(classical_state_result, dict):
        return classical_state_result

    classical = mapping.get("classical")
    if isinstance(classical, dict):
        nested_result = classical.get("classical_state_result")
        if isinstance(nested_result, dict):
            return nested_result

    # Accept a bare classical_state_result mapping after wrapper resolution.
    if (
        isinstance(mapping.get("downstream_compatibility"), dict)
        and mapping.get("status") is not None
        and mapping.get("role") is not None
    ):
        return mapping
    if (
        isinstance(mapping.get("classical_state"), dict)
        and mapping.get("status") is not None
        and mapping.get("role") is not None
    ):
        return mapping

    return None


def get_standardized_classical_state(payload):
    classical_state_result = get_classical_state_result(payload)
    if isinstance(classical_state_result, dict):
        classical_state = classical_state_result.get("classical_state")
        if isinstance(classical_state, dict):
            return classical_state

    mapping = _as_mapping(payload)
    if mapping is None:
        return None

    classical_state = mapping.get("classical_state")
    if isinstance(classical_state, dict):
        return classical_state

    classical = mapping.get("classical")
    if isinstance(classical, dict):
        nested_state = classical.get("classical_state")
        if isinstance(nested_state, dict):
            return nested_state

    return None


def get_downstream_stage_compatibility(payload, stage_name):
    classical_state_result = get_classical_state_result(payload)
    if not isinstance(classical_state_result, dict):
        return None

    downstream_compatibility = classical_state_result.get("downstream_compatibility")
    if not isinstance(downstream_compatibility, dict):
        return None

    stage_entry = downstream_compatibility.get(stage_name)
    if isinstance(stage_entry, dict):
        return stage_entry
    return None


def get_downstream_stage_status(payload, stage_name):
    stage_compatibility = get_downstream_stage_compatibility(payload, stage_name)
    if not isinstance(stage_compatibility, dict):
        return None
    status = stage_compatibility.get("status")
    return str(status) if status is not None else None
