#!/usr/bin/env python3


SPIN_ONLY_EXPLICIT = "spin_only_explicit"
RETAINED_LOCAL_MULTIPLET = "retained_local_multiplet"
DIAGNOSTIC_SEED_ONLY = "diagnostic_seed_only"
SPECIALIZED_CLASSICAL_ANSATZ = "specialized_classical_ansatz"

FINAL_ROLE = "final"
DIAGNOSTIC_ROLE = "diagnostic"
SPECIALIZED_ROLE = "specialized"


_METHOD_CATALOG = {
    "variational": {
        "solver_family": SPIN_ONLY_EXPLICIT,
        "role": FINAL_ROLE,
        "standardized_method": "spin-only-variational",
    },
    "luttinger-tisza": {
        "solver_family": SPIN_ONLY_EXPLICIT,
        "role": FINAL_ROLE,
        "standardized_method": "spin-only-luttinger-tisza",
    },
    "generalized-lt": {
        "solver_family": SPIN_ONLY_EXPLICIT,
        "role": FINAL_ROLE,
        "standardized_method": "spin-only-generalized-lt",
    },
    "restricted-product-state": {
        "solver_family": RETAINED_LOCAL_MULTIPLET,
        "role": FINAL_ROLE,
        "standardized_method": "pseudospin-restricted-product-state",
    },
    "cpn-local-ray-minimize": {
        "solver_family": RETAINED_LOCAL_MULTIPLET,
        "role": FINAL_ROLE,
        "standardized_method": "pseudospin-cpn-local-ray-minimize",
    },
    "sunny-cpn-minimize": {
        "solver_family": RETAINED_LOCAL_MULTIPLET,
        "role": FINAL_ROLE,
        "standardized_method": "pseudospin-sunny-cpn-minimize",
    },
    "cpn-generalized-lt": {
        "solver_family": DIAGNOSTIC_SEED_ONLY,
        "role": DIAGNOSTIC_ROLE,
        "standardized_method": "pseudospin-cpn-generalized-lt",
    },
    "cpn-luttinger-tisza": {
        "solver_family": DIAGNOSTIC_SEED_ONLY,
        "role": DIAGNOSTIC_ROLE,
        "standardized_method": "pseudospin-cpn-luttinger-tisza",
    },
    "sun-gswt-cpn": {
        "solver_family": SPECIALIZED_CLASSICAL_ANSATZ,
        "role": SPECIALIZED_ROLE,
        "standardized_method": "pseudospin-sun-gswt-cpn",
    },
    "sun-gswt-single-q": {
        "solver_family": SPECIALIZED_CLASSICAL_ANSATZ,
        "role": SPECIALIZED_ROLE,
        "standardized_method": "pseudospin-sun-gswt-single-q",
    },
}


def resolve_classical_solver_method(method_name):
    metadata = _METHOD_CATALOG.get(str(method_name))
    if metadata is None:
        raise ValueError(f"unsupported classical solver method: {method_name}")
    return dict(metadata)


def standardized_method_name(method_name):
    return resolve_classical_solver_method(method_name)["standardized_method"]


def solver_family_for_method(method_name):
    return resolve_classical_solver_method(method_name)["solver_family"]


def solver_role_for_method(method_name):
    return resolve_classical_solver_method(method_name)["role"]
