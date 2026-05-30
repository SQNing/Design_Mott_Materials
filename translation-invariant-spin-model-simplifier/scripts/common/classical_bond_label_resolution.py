#!/usr/bin/env python3


_PUBLIC_TO_INTERNAL = {
    "spin-only": "spin_only_explicit",
    "spin_only": "spin_only_explicit",
    "spin only": "spin_only_explicit",
    "cpn": "retained_local_multiplet",
}

_INTERNAL_TO_PUBLIC = {
    "spin_only_explicit": "spin-only",
    "retained_local_multiplet": "cpn",
}

_INPUT_ACCEPTANCE_INTRINSIC_FAMILIES = {
    "many_body_hr": "cpn",
}

_INPUT_ACCEPTANCE_AMBIGUOUS_REPRESENTATIONS = {
    "natural_language",
    "operator",
    "operator_channel_collection",
    "matrix",
}


def normalize_classical_bond_label_label(label):
    if label is None:
        return None
    normalized = str(label).strip().lower().replace("_", "-")
    if normalized == "spin only":
        normalized = "spin-only"
    if normalized not in {"spin-only", "cpn"}:
        raise ValueError(f"unsupported classical bond_label label: {label}")
    return normalized


def classical_bond_label_to_solver_bond_label(label):
    normalized = normalize_classical_bond_label_label(label)
    return _PUBLIC_TO_INTERNAL[normalized]


def solver_bond_label_to_classical_bond_label(solver_bond_label):
    normalized = str(solver_bond_label).strip()
    if normalized not in _INTERNAL_TO_PUBLIC:
        raise ValueError(f"unsupported solver bond_label for classical bond_label conversion: {solver_bond_label}")
    return _INTERNAL_TO_PUBLIC[normalized]


def _extract_payload_bond_label(payload):
    if not isinstance(payload, dict):
        return None
    if payload.get("classical_bond_label") is not None:
        return payload.get("classical_bond_label")
    return None


def _extract_bridge_bond_label(bridge_metadata):
    if not isinstance(bridge_metadata, dict):
        return None
    return bridge_metadata.get("classical_bond_label", bridge_metadata.get("bond_label"))


def resolve_classical_bond_label(*, requested_bond_label=None, payload=None, bridge_metadata=None):
    explicit_sources = []
    for source_name, source_value in (
        ("requested", requested_bond_label),
        ("payload", _extract_payload_bond_label(payload)),
        ("bridge", _extract_bridge_bond_label(bridge_metadata)),
    ):
        if source_value is None:
            continue
        explicit_sources.append((source_name, normalize_classical_bond_label_label(source_value)))

    if not explicit_sources:
        raise ValueError("missing-classical-bond_label: no explicit classical bond_label was provided")

    resolved_public = explicit_sources[0][1]
    for source_name, candidate in explicit_sources[1:]:
        if candidate != resolved_public:
            raise ValueError(
                "conflicting-classical-bond_label: "
                f"explicit classical bond_label sources disagree ({explicit_sources[0][0]}={resolved_public}, "
                f"{source_name}={candidate})"
            )

    return {
        "classical_bond_label": resolved_public,
        "solver_bond_label": classical_bond_label_to_solver_bond_label(resolved_public),
        "sources": [name for name, _ in explicit_sources],
    }


def build_classical_bond_label_selection_interaction():
    return {
        "status": "needs_input",
        "id": "classical_bond_label_selection",
        "question": (
            "This input can be interpreted either as a spin-only model or as a CP^(N-1) "
            "multiplet model. Which classical bond_label should the workflow use?"
        ),
        "options": ["spin-only", "cpn"],
    }


def resolve_input_acceptance_classical_bond_label(*, payload=None, representation=None, requested_bond_label=None):
    payload = payload if isinstance(payload, dict) else {}
    resolved_representation = representation or payload.get("representation")

    intrinsic_bond_label = _INPUT_ACCEPTANCE_INTRINSIC_FAMILIES.get(resolved_representation)
    if intrinsic_bond_label is not None:
        resolution = resolve_classical_bond_label(
            requested_bond_label=requested_bond_label or intrinsic_bond_label,
            payload={**payload, "classical_bond_label": intrinsic_bond_label},
        )
        return {
            "status": "resolved",
            **resolution,
            "intrinsic": True,
        }

    explicit_bond_label = _extract_payload_bond_label(payload)
    if requested_bond_label is not None or explicit_bond_label is not None:
        resolution = resolve_classical_bond_label(
            requested_bond_label=requested_bond_label,
            payload=payload,
        )
        return {
            "status": "resolved",
            **resolution,
            "intrinsic": False,
        }

    if resolved_representation in _INPUT_ACCEPTANCE_AMBIGUOUS_REPRESENTATIONS:
        return {
            "status": "needs_input",
            "interaction": build_classical_bond_label_selection_interaction(),
        }

    return {
        "status": "unresolved",
        "interaction": None,
    }
