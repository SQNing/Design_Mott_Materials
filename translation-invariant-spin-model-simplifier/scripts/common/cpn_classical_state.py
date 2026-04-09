#!/usr/bin/env python3


def resolve_cpn_classical_state_payload(payload, *, default_supercell_shape=None):
    if not isinstance(payload, dict):
        return {}

    nested_state = payload.get("classical_state")
    resolved = dict(nested_state) if isinstance(nested_state, dict) else {}

    fallback_shape = None
    if default_supercell_shape is not None:
        fallback_shape = [int(value) for value in default_supercell_shape]

    fallbacks = {
        "schema_version": payload.get("schema_version", 1),
        "state_kind": payload.get("state_kind", payload.get("reference_state_kind")),
        "manifold": payload.get("manifold"),
        "basis_order": payload.get("basis_order"),
        "pair_basis_order": payload.get("pair_basis_order"),
        "supercell_shape": payload.get("supercell_shape", fallback_shape),
        "local_rays": payload.get("local_rays"),
        "ordering": payload.get("ordering"),
        "ansatz": payload.get("ansatz"),
        "q_vector": payload.get("q_vector"),
    }
    for key, value in fallbacks.items():
        if resolved.get(key) is None and value is not None:
            resolved[key] = value

    ordering = resolved.get("ordering")
    if not isinstance(ordering, dict):
        ordering = {}
    if ordering.get("ansatz") is None and resolved.get("ansatz") is not None:
        ordering["ansatz"] = resolved["ansatz"]
    if ordering.get("q_vector") is None and resolved.get("q_vector") is not None:
        ordering["q_vector"] = resolved["q_vector"]
    if ordering.get("supercell_shape") is None and resolved.get("supercell_shape") is not None:
        ordering["supercell_shape"] = resolved["supercell_shape"]
    if ordering:
        resolved["ordering"] = ordering

    return resolved


def resolve_cpn_local_state(payload, *, default_supercell_shape=None):
    state = resolve_cpn_classical_state_payload(payload, default_supercell_shape=default_supercell_shape)
    local_rays = state.get("local_rays")
    shape = state.get("supercell_shape")
    if not local_rays or not shape:
        return None
    return {
        "shape": [int(value) for value in shape],
        "local_rays": list(local_rays),
    }
