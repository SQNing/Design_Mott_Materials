#!/usr/bin/env python3


def _candidate_classical_state_payload(payload):
    if not isinstance(payload, dict):
        return {}

    nested_state = payload.get("classical_state")
    if isinstance(nested_state, dict):
        return nested_state

    classical = payload.get("classical")
    if isinstance(classical, dict):
        classical_state = classical.get("classical_state")
        if isinstance(classical_state, dict):
            return classical_state

    return payload


def _nested_classical_state_payload(payload):
    if not isinstance(payload, dict):
        return None

    nested_state = payload.get("classical_state")
    if isinstance(nested_state, dict):
        return nested_state

    classical = payload.get("classical")
    if isinstance(classical, dict):
        classical_state = classical.get("classical_state")
        if isinstance(classical_state, dict):
            return classical_state

    return None


def resolve_cpn_classical_state_payload(payload, *, default_supercell_shape=None):
    if not isinstance(payload, dict):
        return {}

    nested_state = _nested_classical_state_payload(payload)
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

    if resolved.get("state_kind") is None and resolved.get("local_rays"):
        resolved["state_kind"] = "local_rays"
    if resolved.get("manifold") is None and resolved.get("local_rays"):
        resolved["manifold"] = "CP^(N-1)"

    return resolved


def has_spin_frame_classical_state(payload):
    classical_state = _candidate_classical_state_payload(payload)
    frames = classical_state.get("site_frames", [])
    return bool(frames)


def is_cpn_local_ray_classical_state(payload, *, default_supercell_shape=None):
    classical_state = _candidate_classical_state_payload(payload)
    resolved_state = resolve_cpn_classical_state_payload(
        classical_state,
        default_supercell_shape=default_supercell_shape,
    )
    local_rays = resolved_state.get("local_rays", [])
    if not local_rays:
        return False
    state_kind = resolved_state.get("state_kind")
    manifold = resolved_state.get("manifold")
    return state_kind == "local_rays" or manifold == "CP^(N-1)"


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
