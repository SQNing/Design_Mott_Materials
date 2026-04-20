#!/usr/bin/env python3

import copy

from common.classical_contract_resolution import (
    get_classical_state_result,
    get_standardized_classical_state,
)


def _resolved_classical_metadata(payload):
    classical = payload.get("classical", {}) if isinstance(payload, dict) else {}
    if not isinstance(classical, dict):
        classical = {}
    return {
        "chosen_method": classical.get("chosen_method"),
        "requested_method": classical.get("requested_method"),
        "solver_method": classical.get("solver_method"),
    }


def build_classical_output_compatibility_payload(payload):
    classical_state_result = get_classical_state_result(payload)
    if not isinstance(classical_state_result, dict):
        return {}

    classical_state = get_standardized_classical_state(payload)
    compatibility = {
        "classical_state_result": copy.deepcopy(classical_state_result),
    }
    if isinstance(classical_state, dict):
        compatibility["classical_state"] = copy.deepcopy(classical_state)

    metadata = _resolved_classical_metadata(payload)
    classical_payload = {
        key: value
        for key, value in metadata.items()
        if value is not None
    }
    classical_payload["classical_state_result"] = copy.deepcopy(classical_state_result)
    if isinstance(classical_state, dict):
        classical_payload["classical_state"] = copy.deepcopy(classical_state)
    compatibility["classical"] = classical_payload
    return compatibility
