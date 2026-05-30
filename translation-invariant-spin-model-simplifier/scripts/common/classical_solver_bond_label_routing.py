#!/usr/bin/env python3

from common.classical_bond_label_resolution import classical_bond_label_to_solver_bond_label
from common.solver_capability_registry import registered_solver_capabilities


SPIN_ONLY_EXPLICIT = "spin_only_explicit"
RETAINED_LOCAL_MULTIPLET = "retained_local_multiplet"
DIAGNOSTIC_SEED_ONLY = "diagnostic_seed_only"
SPECIALIZED_CLASSICAL_ANSATZ = "specialized_classical_ansatz"

FINAL_ROLE = "final"
DIAGNOSTIC_ROLE = "diagnostic"
SPECIALIZED_ROLE = "specialized"


_METHOD_CATALOG = {
    "variational": {
        "solver_bond_label": SPIN_ONLY_EXPLICIT,
        "role": FINAL_ROLE,
        "standardized_method": "spin-only-variational",
    },
    "luttinger-tisza": {
        "solver_bond_label": SPIN_ONLY_EXPLICIT,
        "role": FINAL_ROLE,
        "standardized_method": "spin-only-luttinger-tisza",
    },
    "generalized-lt": {
        "solver_bond_label": SPIN_ONLY_EXPLICIT,
        "role": FINAL_ROLE,
        "standardized_method": "spin-only-generalized-lt",
    },
    "restricted-product-state": {
        "solver_bond_label": RETAINED_LOCAL_MULTIPLET,
        "role": FINAL_ROLE,
        "standardized_method": "pseudospin-restricted-product-state",
    },
    "cpn-local-ray-minimize": {
        "solver_bond_label": RETAINED_LOCAL_MULTIPLET,
        "role": FINAL_ROLE,
        "standardized_method": "pseudospin-cpn-local-ray-minimize",
    },
    "sunny-cpn-minimize": {
        "solver_bond_label": RETAINED_LOCAL_MULTIPLET,
        "role": FINAL_ROLE,
        "standardized_method": "pseudospin-sunny-cpn-minimize",
    },
    "cpn-generalized-lt": {
        "solver_bond_label": DIAGNOSTIC_SEED_ONLY,
        "role": DIAGNOSTIC_ROLE,
        "standardized_method": "pseudospin-cpn-generalized-lt",
        "promotion_capable": True,
    },
    "cpn-luttinger-tisza": {
        "solver_bond_label": DIAGNOSTIC_SEED_ONLY,
        "role": DIAGNOSTIC_ROLE,
        "standardized_method": "pseudospin-cpn-luttinger-tisza",
        "promotion_capable": True,
    },
    "sun-gswt-cpn": {
        "solver_bond_label": SPECIALIZED_CLASSICAL_ANSATZ,
        "role": SPECIALIZED_ROLE,
        "standardized_method": "pseudospin-sun-gswt-cpn",
    },
    "sun-gswt-single-q": {
        "solver_bond_label": SPECIALIZED_CLASSICAL_ANSATZ,
        "role": SPECIALIZED_ROLE,
        "standardized_method": "pseudospin-sun-gswt-single-q",
    },
}


def _capability_by_method():
    return {capability["method"]: capability for capability in registered_solver_capabilities()}


def _merge_capability_metadata(metadata):
    enriched = dict(metadata)
    capability = _capability_by_method().get(enriched.get("standardized_method"))
    if capability is not None:
        enriched["capability_id"] = capability.get("solver_id")
        enriched["method"] = capability.get("method")
        enriched["roles"] = list(capability.get("roles") or [])
        enriched["result_contract"] = dict(capability.get("result_contract") or {})
        enriched["downstream_compatibility"] = dict(capability.get("downstream_compatibility") or {})
    return enriched


def resolve_classical_solver_method(method_name):
    metadata = _METHOD_CATALOG.get(str(method_name))
    if metadata is None:
        raise ValueError(f"unsupported classical solver method: {method_name}")
    return _merge_capability_metadata(metadata)


def resolve_dynamic_classical_solver_method(method_name, solver_result=None):
    metadata = resolve_classical_solver_method(method_name)
    if str(method_name) in {"cpn-generalized-lt", "cpn-luttinger-tisza"}:
        if isinstance(solver_result, dict) and str(solver_result.get("solver_role")) == FINAL_ROLE:
            metadata["solver_bond_label"] = RETAINED_LOCAL_MULTIPLET
            metadata["role"] = FINAL_ROLE
    return metadata


def standardized_method_name(method_name):
    return resolve_classical_solver_method(method_name)["standardized_method"]


def solver_bond_label_for_method(method_name):
    return resolve_classical_solver_method(method_name)["solver_bond_label"]


def solver_role_for_method(method_name):
    return resolve_classical_solver_method(method_name)["role"]


def validate_method_for_classical_bond_label(method_name, classical_bond_label):
    metadata = resolve_classical_solver_method(method_name)
    requested_solver_bond_label = classical_bond_label_to_solver_bond_label(classical_bond_label)
    method_solver_bond_label = metadata["solver_bond_label"]

    if requested_solver_bond_label == SPIN_ONLY_EXPLICIT:
        allowed = {SPIN_ONLY_EXPLICIT}
    elif requested_solver_bond_label == RETAINED_LOCAL_MULTIPLET:
        allowed = {RETAINED_LOCAL_MULTIPLET, DIAGNOSTIC_SEED_ONLY, SPECIALIZED_CLASSICAL_ANSATZ}
    else:
        allowed = {requested_solver_bond_label}

    if method_solver_bond_label not in allowed:
        raise ValueError(
            "incompatible-classical-bond_label: "
            f"method {method_name} is not valid for classical bond_label {classical_bond_label}"
        )
    return metadata
