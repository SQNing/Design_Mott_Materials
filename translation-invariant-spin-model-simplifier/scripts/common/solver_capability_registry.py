#!/usr/bin/env python3
"""Deterministic solver capability matching for lattice-term payloads."""

from __future__ import annotations

from copy import deepcopy
from collections.abc import Mapping


class SolverCapabilityError(ValueError):
    def __init__(self, code: str, message: str | None = None):
        self.code = code
        super().__init__(message or code)


def _raise(code: str, detail: str | None = None):
    if detail:
        raise SolverCapabilityError(code, f"{code}: {detail}")
    raise SolverCapabilityError(code)


def registered_solver_capabilities():
    return [
        {
            "solver_id": "spin_classical_solver",
            "method": "spin-only-variational",
            "tasks": ["classical_ground_state"],
            "roles": ["final"],
            "finality": "final",
            "result_contract": {
                "kind": "classical_state.spin_frame",
                "classical_state_kind": "spin_frame",
            },
            "supports": {
                "classical_space_kinds": ["unit_vector_sphere"],
                "term_payload_kinds": ["bilinear_exchange_matrix"],
            },
            "requires": {
                "local_classical_space": True,
                "bond_terms": True,
            },
            "limits": {
                "max_body_order": 2,
            },
            "promotion": {
                "can_promote_diagnostic_seed": False,
            },
            "downstream_compatibility": {
                "lswt": {"status": "ready", "recommended_backend": "linear_spin_wave"},
                "gswt": {"status": "blocked", "reason": "requires-retained-local-rays"},
                "thermodynamics": {"status": "ready", "recommended_backend": "spin_only_thermodynamics"},
            },
            "preference_priority": 100,
        },
        {
            "solver_id": "retained_local_classical_solver",
            "method": "pseudospin-restricted-product-state",
            "tasks": ["classical_ground_state"],
            "roles": ["final"],
            "finality": "final",
            "result_contract": {
                "kind": "classical_state.local_rays",
                "classical_state_kind": "local_rays",
            },
            "supports": {
                "classical_space_kinds": ["complex_projective_space"],
                "term_payload_kinds": ["pair_matrix"],
            },
            "requires": {
                "local_classical_space": True,
                "bond_terms": True,
            },
            "limits": {
                "max_body_order": 2,
            },
            "promotion": {
                "can_promote_diagnostic_seed": True,
            },
            "downstream_compatibility": {
                "lswt": {"status": "blocked", "reason": "requires-spin-frame-state"},
                "gswt": {"status": "ready", "recommended_backend": "sun_gswt"},
                "thermodynamics": {"status": "ready", "recommended_backend": "sunny_thermodynamics"},
            },
            "preference_priority": 100,
        },
    ]


def registered_research_solver_capabilities():
    """Only routes whose complete Hamiltonian is passed by research.adapters.

    Keep the legacy classical pipeline's registry unchanged: its retained-local
    bridge currently has a narrower term contract than the research bridge.

    Entries with ``connection: declared-not-connected`` are never selected by
    automatic routing; they exist so that an explicit request fails closed with
    ``backend-not-connected`` instead of an opaque no-capability error.
    """
    return [
        {"solver_id": "periodic-spin-python", "backend": "python",
         "connection": "connected",
         "tasks": ["classical_ground_state", "spin_wave_spectrum",
                   "classical_monte_carlo", "classical_finite_size",
                   "quantum_low_energy", "quantum_thermodynamics",
                   "fourier_exchange_spectrum"],
         "classical_spaces": ["unit_vector_sphere"],
         "term_families": ["bilinear_exchange_tensor", "bilinear_exchange_matrix"],
         "max_body_order": 2, "reference_kind": "spin_frame"},
        {"solver_id": "retained-local-python", "backend": "python",
         "connection": "connected",
         "tasks": ["classical_ground_state", "spin_wave_spectrum"],
         "classical_spaces": ["complex_projective_space"],
         "term_families": ["pair_matrix", "local_operator_matrix"],
         "max_body_order": 2, "reference_kind": "local_rays"},
        {"solver_id": "geometry-ewald-python", "backend": "python",
         "connection": "connected",
         "tasks": ["dipolar_ewald"], "input_kind": "dipolar_geometry"},
        {"solver_id": "sunny-sun-classical", "backend": "julia-sunny",
         "connection": "environment-gated",
         "tasks": ["classical_ground_state"],
         "classical_spaces": ["complex_projective_space"],
         "term_families": ["pair_matrix", "local_operator_matrix"],
         "max_body_order": 2, "reference_kind": "local_rays"},
        {"solver_id": "sunny-sun-thermodynamics", "backend": "julia-sunny",
         "connection": "environment-gated",
         "tasks": ["classical_monte_carlo"],
         "classical_spaces": ["complex_projective_space"],
         "term_families": ["pair_matrix", "local_operator_matrix"],
         "max_body_order": 2, "reference_kind": "local_rays"},
        # Stage D: explicit-request route only (task name or backend alias);
        # automatic routing never picks DMRG because the task list is narrow.
        # Actual Julia/ITensor availability is probed per call in adapters.py.
        {"solver_id": "quantum-dmrg-itensor", "backend": "julia-itensor",
         "connection": "connected",
         "tasks": ["quantum_ground_state_dmrg"],
         "classical_spaces": ["unit_vector_sphere"],
         "term_families": ["bilinear_exchange_tensor", "bilinear_exchange_matrix"],
         "max_body_order": 2},
        {"solver_id": "quantum-vmc-netket", "backend": "python-netket",
         "connection": "live",
         "tasks": ["quantum_ground_state_vmc"],
         "classical_spaces": ["unit_vector_sphere", "complex_projective_space"],
         "term_families": ["bilinear_exchange_tensor", "bilinear_exchange_matrix",
                           "pair_matrix", "local_operator_matrix"],
         "max_body_order": 2},
    ]


def _request_from_payload(payload, request=None):
    if isinstance(request, Mapping):
        return dict(request)
    if isinstance(payload, Mapping) and isinstance(payload.get("solver_request"), Mapping):
        return dict(payload.get("solver_request"))
    return {}


def _classical_space_kinds(payload):
    local_hilbert = payload.get("local_hilbert") if isinstance(payload, Mapping) else {}
    classical_spaces = local_hilbert.get("classical_spaces") if isinstance(local_hilbert, Mapping) else {}
    kinds = []
    if isinstance(classical_spaces, Mapping):
        for record in classical_spaces.values():
            if isinstance(record, Mapping) and record.get("kind") is not None:
                text = str(record.get("kind")).strip()
                if text and text not in kinds:
                    kinds.append(text)
    return kinds


def _term_payload_kinds(payload):
    if payload.get("schema_version") == "canonical-hamiltonian/v1":
        family_to_kind = {
            "bilinear_exchange_tensor": "bilinear_exchange_matrix",
            "bilinear_exchange_matrix": "bilinear_exchange_matrix",
            "pair_matrix": "pair_matrix",
        }
        return [
            family_to_kind.get(str(term.get("operator_family") or ""), str(term.get("operator_family") or ""))
            for term in list(payload.get("terms") or [])
            if isinstance(term, Mapping)
        ]
    term_attachments = payload.get("term_attachments") if isinstance(payload, Mapping) else {}
    kinds = []
    if not isinstance(term_attachments, Mapping):
        return kinds
    for collection_name in ("site_terms", "bond_terms", "higher_body_terms"):
        for term in list(term_attachments.get(collection_name) or []):
            if not isinstance(term, Mapping):
                continue
            term_payload = term.get("payload")
            if isinstance(term_payload, Mapping) and term_payload.get("kind") is not None:
                text = str(term_payload.get("kind")).strip()
                if text and text not in kinds:
                    kinds.append(text)
    return kinds


def _capability_supports_payload(capability, payload, request):
    task = str(request.get("task") or "classical_ground_state")
    if task not in set(capability.get("tasks") or []):
        return False

    preferred_methods = [str(method) for method in list(request.get("preferred_methods") or [])]
    if preferred_methods and "auto" not in preferred_methods and capability.get("method") not in preferred_methods:
        return False

    supports = capability.get("supports") if isinstance(capability.get("supports"), Mapping) else {}
    supported_space_kinds = set(supports.get("classical_space_kinds") or [])
    supported_term_kinds = set(supports.get("term_payload_kinds") or [])

    payload_space_kinds = set(_classical_space_kinds(payload))
    payload_term_kinds = set(_term_payload_kinds(payload))
    if supported_space_kinds and not payload_space_kinds.intersection(supported_space_kinds):
        return False
    if supported_term_kinds and not payload_term_kinds.issubset(supported_term_kinds):
        return False
    max_body_order = int((capability.get("limits") or {}).get("max_body_order", 0) or 0)
    if payload.get("schema_version") == "canonical-hamiltonian/v1" and max_body_order:
        if any(int(term.get("arity", 0)) > max_body_order for term in list(payload.get("terms") or [])):
            return False
    return True


def _ensure_supported_term_payloads(payload, capabilities):
    if payload.get("schema_version") == "canonical-hamiltonian/v1":
        return
    known = set()
    for capability in capabilities:
        supports = capability.get("supports") if isinstance(capability.get("supports"), Mapping) else {}
        known.update(str(kind) for kind in list(supports.get("term_payload_kinds") or []))
    unknown = [kind for kind in _term_payload_kinds(payload) if kind not in known]
    if unknown:
        _raise("unsupported-term-payload", ",".join(sorted(unknown)))


def match_solver_capabilities(payload, request=None, *, capabilities=None):
    payload = payload if isinstance(payload, Mapping) else {}
    capabilities = deepcopy(list(capabilities or registered_solver_capabilities()))
    request = _request_from_payload(payload, request)
    _ensure_supported_term_payloads(payload, capabilities)
    return [
        capability
        for capability in capabilities
        if _capability_supports_payload(capability, payload, request)
    ]


def select_solver_capability(payload, request=None, *, capabilities=None):
    matches = match_solver_capabilities(payload, request, capabilities=capabilities)
    if not matches:
        if isinstance(payload, Mapping) and payload.get("schema_version") == "canonical-hamiltonian/v1":
            unsupported = [
                f"{term.get('term_ref')}[{term.get('operator_family')},arity={term.get('arity')}]"
                for term in list(payload.get("terms") or [])
                if isinstance(term, Mapping)
            ]
            _raise("solver-capability-mismatch", ",".join(unsupported))
        _raise("no-solver-capability")

    matches.sort(key=lambda capability: int(capability.get("preference_priority", 0)), reverse=True)
    best_priority = int(matches[0].get("preference_priority", 0))
    tied = [capability for capability in matches if int(capability.get("preference_priority", 0)) == best_priority]
    if len(tied) > 1:
        _raise("ambiguous-solver-capability", ",".join(sorted(str(item.get("solver_id")) for item in tied)))
    return deepcopy(matches[0])


def result_contract_for_capability(capability):
    return deepcopy((capability or {}).get("result_contract") or {})
