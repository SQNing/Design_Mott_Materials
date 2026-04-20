#!/usr/bin/env python3

import copy

from common.classical_contract_resolution import get_classical_state_result


_SINGLE_Q_WRAPPER_KEYS = ("reference_ray", "generator_matrix", "site_ansatz", "ansatz_stationarity")


def has_single_q_wrapper_metadata(payload):
    return isinstance(payload, dict) and any(payload.get(key) is not None for key in _SINGLE_Q_WRAPPER_KEYS)


def resolve_rich_single_q_wrapper(source_state):
    if not isinstance(source_state, dict):
        return None
    if has_single_q_wrapper_metadata(source_state):
        return source_state

    compatibility_state = source_state.get("classical_state")
    if has_single_q_wrapper_metadata(compatibility_state):
        return compatibility_state

    classical = source_state.get("classical")
    if isinstance(classical, dict):
        if has_single_q_wrapper_metadata(classical):
            return classical
        nested_state = classical.get("classical_state")
        if has_single_q_wrapper_metadata(nested_state):
            return nested_state

    return None


def resolve_contract_aware_classical_reference_payload(source_state):
    if not isinstance(source_state, dict):
        return source_state

    classical_state_result = get_classical_state_result(source_state)
    standardized_state = (
        classical_state_result.get("classical_state")
        if isinstance(classical_state_result, dict)
        else None
    )
    rich_wrapper = resolve_rich_single_q_wrapper(source_state)
    if isinstance(rich_wrapper, dict):
        rich_wrapper_copy = copy.deepcopy(rich_wrapper)
        if isinstance(standardized_state, dict):
            return {
                **rich_wrapper_copy,
                "classical_state": copy.deepcopy(standardized_state),
            }
        return rich_wrapper_copy

    if isinstance(standardized_state, dict):
        return copy.deepcopy(standardized_state)
    return source_state
