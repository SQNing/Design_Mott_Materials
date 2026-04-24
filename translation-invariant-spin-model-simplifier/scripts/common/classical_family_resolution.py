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


def normalize_classical_family_label(label):
    if label is None:
        return None
    normalized = str(label).strip().lower().replace("_", "-")
    if normalized == "spin only":
        normalized = "spin-only"
    if normalized not in {"spin-only", "cpn"}:
        raise ValueError(f"unsupported classical family label: {label}")
    return normalized


def classical_family_to_solver_family(label):
    normalized = normalize_classical_family_label(label)
    return _PUBLIC_TO_INTERNAL[normalized]


def solver_family_to_classical_family(solver_family):
    normalized = str(solver_family).strip()
    if normalized not in _INTERNAL_TO_PUBLIC:
        raise ValueError(f"unsupported solver family for classical family conversion: {solver_family}")
    return _INTERNAL_TO_PUBLIC[normalized]


def _extract_payload_family(payload):
    if not isinstance(payload, dict):
        return None
    if payload.get("classical_family") is not None:
        return payload.get("classical_family")
    metadata = payload.get("classical_family_metadata")
    if isinstance(metadata, dict) and metadata.get("family") is not None:
        return metadata.get("family")
    return None


def _extract_bridge_family(bridge_metadata):
    if not isinstance(bridge_metadata, dict):
        return None
    return bridge_metadata.get("classical_family", bridge_metadata.get("family"))


def resolve_classical_family(*, requested_family=None, payload=None, bridge_metadata=None):
    explicit_sources = []
    for source_name, source_value in (
        ("requested", requested_family),
        ("payload", _extract_payload_family(payload)),
        ("bridge", _extract_bridge_family(bridge_metadata)),
    ):
        if source_value is None:
            continue
        explicit_sources.append((source_name, normalize_classical_family_label(source_value)))

    if not explicit_sources:
        raise ValueError("missing-classical-family: no explicit classical family was provided")

    resolved_public = explicit_sources[0][1]
    for source_name, candidate in explicit_sources[1:]:
        if candidate != resolved_public:
            raise ValueError(
                "conflicting-classical-family: "
                f"explicit classical family sources disagree ({explicit_sources[0][0]}={resolved_public}, "
                f"{source_name}={candidate})"
            )

    return {
        "classical_family": resolved_public,
        "solver_family": classical_family_to_solver_family(resolved_public),
        "sources": [name for name, _ in explicit_sources],
    }
