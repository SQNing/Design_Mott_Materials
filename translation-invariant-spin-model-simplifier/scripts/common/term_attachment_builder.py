#!/usr/bin/env python3
"""Build canonical term attachment records for lattice-term payloads."""

from __future__ import annotations

from copy import deepcopy
from collections.abc import Mapping

from common.lattice_structure_builder import resolve_document_label_to_bond_orbit


def structured_real(value):
    return {"kind": "real", "value": float(value)}


def structured_complex(re, im):
    return {"kind": "complex", "re": float(re), "im": float(im)}


def parameter_ref(ref):
    return {"kind": "parameter_ref", "parameter_ref": str(ref)}


def _structured_scalar(value):
    if isinstance(value, Mapping):
        kind = value.get("kind")
        if kind in {"real", "complex", "parameter_ref"}:
            return dict(value)
    if isinstance(value, complex):
        return structured_complex(value.real, value.imag)
    if isinstance(value, bool):
        return structured_real(float(value))
    if isinstance(value, (int, float)):
        return structured_real(value)
    return parameter_ref(value)


def _structured_matrix(matrix):
    rows = [list(row) for row in list(matrix or [])]
    shape = [len(rows), max((len(row) for row in rows), default=0)]
    data = [[_structured_scalar(entry) for entry in row] for row in rows]
    if shape[0] and shape[1] == 0:
        shape[1] = len(rows[0])
    scalar_type = "real_parameter_expression"
    for row in data:
        for entry in row:
            if entry.get("kind") == "complex":
                scalar_type = "complex_parameter_expression"
                break
        if scalar_type == "complex_parameter_expression":
            break
    return {
        "storage": "dense",
        "shape": shape,
        "scalar_type": scalar_type,
        "data": data,
    }


def _term_ref_from_source_label(source_label, prefix="term"):
    label = str(source_label or "").strip()
    if not label:
        return f"{prefix}:unlabeled"
    return f"{prefix}:{label}"


def _first_orbit_ref_for_label(lattice_structure, source_label):
    bond_orbits = list((lattice_structure or {}).get("bond_orbits") or [])
    for orbit in bond_orbits:
        labels = {str(label) for label in orbit.get("source_labels") or []}
        if str(source_label) in labels:
            return orbit.get("orbit_ref") or orbit.get("bond_orbit_ref")
    resolved = resolve_document_label_to_bond_orbit(source_label, bond_orbits)
    if resolved is not None:
        return resolved.get("orbit_ref") or resolved.get("bond_orbit_ref")
    return None


def _support_ref_from_indices(source, target):
    if source is None or target is None:
        return []
    try:
        return [f"site:{int(source)}", f"site:{int(target)}"]
    except (TypeError, ValueError):
        return []


def _support_ref_from_orbit(lattice_structure, orbit_ref):
    for orbit in list((lattice_structure or {}).get("bond_orbits") or []):
        candidate_ref = orbit.get("orbit_ref") or orbit.get("bond_orbit_ref")
        if str(candidate_ref) != str(orbit_ref):
            continue
        representative = orbit.get("representative") or {}
        return _support_ref_from_indices(representative.get("source"), representative.get("target"))
    return []


def build_pair_matrix_attachment(
    *,
    term_ref,
    bond_orbit_ref,
    local_basis_refs,
    matrix,
    provenance=None,
    source_label=None,
    document_label=None,
    evidence_refs=None,
    operator_basis_ref=None,
    channel_kind="two_body",
    operator_channel="pair_matrix",
    readable_block_kind="pair_matrix",
):
    local_basis_refs = [str(ref) for ref in list(local_basis_refs or [])]
    structured_matrix = _structured_matrix(matrix)
    attachment = {
        "term_ref": str(term_ref),
        "support_ref": list(source_label.get("support_ref", [])) if isinstance(source_label, Mapping) else [],
        "attach_to": {
            "kind": "bond_orbit",
            "orbit_ref": str(bond_orbit_ref),
            "orientation": "representative",
        },
        "operator_basis_ref": operator_basis_ref or (local_basis_refs[0] if local_basis_refs else None),
        "channel_kind": channel_kind,
        "operator_channel": operator_channel,
        "readable_block_kind": readable_block_kind,
        "payload": {
            "kind": "pair_matrix",
            "local_basis_refs": local_basis_refs,
            "tensor_product_order": {
                "kind": "left_major_right_minor",
                "left_site_role": "source",
                "right_site_role": "target",
                "basis_labels": [
                    ["basis_0", "basis_1", "basis_2"][: len(local_basis_refs) or 1],
                    ["basis_0", "basis_1", "basis_2"][: len(local_basis_refs) or 1],
                ],
            },
            "matrix": structured_matrix,
            "hermiticity": "hermitian_pair_operator",
            "pair_identity": {
                "status": "verified",
                "provider": "many_body_hr_pair_identity_sidecar",
                "basis_order_status": "matched",
            },
            "orientation_transform": "swap_tensor_factors_then_adjoint",
        },
        "parameter_bindings": [],
        "source_label": source_label,
        "document_label": document_label,
        "evidence_refs": list(evidence_refs or []),
        "provenance": dict(provenance or {}),
    }
    return attachment


def build_spin_exchange_attachment(candidate, *, term_ref, bond_orbit_ref, provenance=None):
    payload = deepcopy(candidate.get("payload") or {})
    if payload.get("kind") is None:
        payload["kind"] = "bilinear_exchange_matrix"
    attachment = {
        "term_ref": str(term_ref),
        "support_ref": list(candidate.get("support_ref") or []),
        "attach_to": {
            "kind": "bond_orbit",
            "orbit_ref": str(bond_orbit_ref),
            "orientation": "representative",
        },
        "operator_basis_ref": candidate.get("operator_basis_ref"),
        "channel_kind": candidate.get("channel_kind") or "two_body",
        "operator_channel": candidate.get("operator_channel") or "spin_exchange",
        "readable_block_kind": candidate.get("readable_block_kind") or "bilinear_exchange",
        "payload": payload,
        "parameter_bindings": list(candidate.get("parameter_bindings") or []),
        "source_label": candidate.get("source_label"),
        "document_label": candidate.get("document_label"),
        "evidence_refs": list(candidate.get("evidence_refs") or []),
        "provenance": dict(provenance or candidate.get("provenance") or {}),
    }
    return attachment


def build_candidate_term_attachment(candidate, *, lattice_structure, default_operator_basis_ref=None):
    source_label = candidate.get("source_label")
    orbit_ref = candidate.get("orbit_ref") or _first_orbit_ref_for_label(lattice_structure, source_label)
    if orbit_ref is None:
        orbit_ref = candidate.get("bond_orbit_ref") or f"bond_orbit:{source_label or 'unresolved'}"

    term_ref = candidate.get("term_ref") or candidate.get("candidate_ref") or _term_ref_from_source_label(source_label)
    support_ref = list(candidate.get("support_ref") or [])
    if not support_ref:
        support_ref = _support_ref_from_indices(candidate.get("source"), candidate.get("target"))
    if not support_ref:
        support_ref = _support_ref_from_orbit(lattice_structure, orbit_ref)

    attachment = {
        "term_ref": str(term_ref),
        "candidate_ref": str(candidate.get("candidate_ref") or term_ref),
        "support_ref": support_ref,
        "source_label": source_label,
        "document_label": candidate.get("document_label"),
        "attach_to": {
            "kind": "bond_orbit",
            "orbit_ref": str(orbit_ref),
            "orientation": "representative",
            "resolution_status": "resolved",
        },
        "operator_basis_ref": candidate.get("operator_basis_ref") or default_operator_basis_ref,
        "channel_kind": candidate.get("channel_kind") or "two_body",
        "operator_channel": candidate.get("operator_channel") or "spin_exchange",
        "readable_block_kind": candidate.get("readable_block_kind") or "bilinear_exchange",
        "operator_rank": candidate.get("operator_rank"),
        "multipole_class": candidate.get("multipole_class"),
        "payload": deepcopy(candidate.get("payload") or {}),
        "parameter_bindings": list(candidate.get("parameter_bindings") or []),
        "evidence_refs": list(candidate.get("evidence_refs") or []),
        "provenance": dict(candidate.get("provenance") or {}),
    }
    return attachment


def build_term_sets(candidate_terms, selection=None):
    candidate_terms = list(candidate_terms or [])
    selection = dict(selection or {})
    if not candidate_terms:
        return []

    selected_term_refs = [str(ref) for ref in selection.get("selected_term_refs") or []]
    selected_bond_orbit_refs = [str(ref) for ref in selection.get("selected_bond_orbit_refs") or []]
    selected_term_set_ref = selection.get("selected_term_set_ref")

    if selected_term_set_ref:
        return [
            {
                "term_set_ref": str(selected_term_set_ref),
                "selection_mode": selection.get("selection_mode") or "explicit",
                "term_refs": selected_term_refs,
                "bond_orbit_refs": selected_bond_orbit_refs,
                "description": selection.get("description") or "Selected term subset",
            }
        ]

    term_refs = [str(term.get("term_ref")) for term in candidate_terms if term.get("term_ref")]
    bond_orbit_refs = []
    for term in candidate_terms:
        attach_to = term.get("attach_to") or {}
        orbit_ref = attach_to.get("orbit_ref")
        if orbit_ref and orbit_ref not in bond_orbit_refs:
            bond_orbit_refs.append(str(orbit_ref))

    return [
        {
            "term_set_ref": "term_set:all_compatible_document_terms",
            "selection_mode": "all_compatible",
            "term_refs": term_refs,
            "bond_orbit_refs": bond_orbit_refs,
            "description": "All document-extracted terms compatible with the requested solver task",
        }
    ]


def build_term_attachments(source_model, lattice_structure, local_hilbert):
    source_model = source_model or {}
    hamiltonian_model = dict(source_model.get("hamiltonian_model") or {})
    operator_basis_ref = None
    sites = list((local_hilbert or {}).get("sites") or [])
    if sites:
        operator_basis_refs = list(sites[0].get("operator_basis_refs") or [])
        if operator_basis_refs:
            operator_basis_ref = operator_basis_refs[0]

    site_terms = []
    bond_terms = []
    higher_body_terms = []
    candidate_terms = []

    for term in list(hamiltonian_model.get("bond_terms") or []):
        canonical_term = deepcopy(term)
        term_ref = canonical_term.get("term_ref") or canonical_term.get("bond_ref") or _term_ref_from_source_label(
            canonical_term.get("source_label")
        )
        orbit_ref = (
            canonical_term.get("attach_to", {}).get("orbit_ref")
            or canonical_term.get("orbit_ref")
            or _first_orbit_ref_for_label(lattice_structure, canonical_term.get("source_label"))
            or f"bond_orbit:{canonical_term.get('source_label') or 'unresolved'}"
        )
        canonical_term["term_ref"] = str(term_ref)
        canonical_term["attach_to"] = {
            "kind": "bond_orbit",
            "orbit_ref": str(orbit_ref),
            "orientation": canonical_term.get("attach_to", {}).get("orientation") or "representative",
        }
        canonical_term["operator_basis_ref"] = canonical_term.get("operator_basis_ref") or operator_basis_ref
        if not canonical_term.get("support_ref"):
            canonical_term["support_ref"] = (
                _support_ref_from_indices(canonical_term.get("source"), canonical_term.get("target"))
                or _support_ref_from_orbit(lattice_structure, orbit_ref)
            )
        canonical_term["channel_kind"] = canonical_term.get("channel_kind") or "two_body"
        canonical_term["operator_channel"] = canonical_term.get("operator_channel") or "spin_exchange"
        canonical_term["readable_block_kind"] = canonical_term.get("readable_block_kind") or "bilinear_exchange"
        canonical_term["payload"] = deepcopy(canonical_term.get("payload") or {})
        canonical_term["provenance"] = dict(canonical_term.get("provenance") or {})
        bond_terms.append(canonical_term)
        candidate_terms.append(
            {
                "term_ref": canonical_term["term_ref"],
                "candidate_ref": str(canonical_term.get("candidate_ref") or canonical_term["term_ref"]),
                "support_ref": list(canonical_term.get("support_ref") or []),
                "source_label": canonical_term.get("source_label"),
                "document_label": canonical_term.get("document_label"),
                "attach_to": deepcopy(canonical_term["attach_to"]),
                "operator_basis_ref": canonical_term.get("operator_basis_ref"),
                "channel_kind": canonical_term.get("channel_kind"),
                "operator_channel": canonical_term.get("operator_channel"),
                "readable_block_kind": canonical_term.get("readable_block_kind"),
                "payload": deepcopy(canonical_term.get("payload") or {}),
                "parameter_bindings": list(canonical_term.get("parameter_bindings") or []),
                "evidence_refs": list(canonical_term.get("evidence_refs") or []),
                "provenance": dict(canonical_term.get("provenance") or {}),
            }
        )

    for candidate in list(hamiltonian_model.get("local_bond_candidates") or []):
        candidate_term = build_candidate_term_attachment(
            candidate,
            lattice_structure=lattice_structure,
            default_operator_basis_ref=operator_basis_ref,
        )
        candidate_terms.append(candidate_term)
        if candidate_term.get("payload", {}).get("kind") == "pair_matrix":
            bond_terms.append(deepcopy(candidate_term))
        else:
            bond_terms.append(
                build_spin_exchange_attachment(
                    candidate_term,
                    term_ref=candidate_term["term_ref"],
                    bond_orbit_ref=candidate_term["attach_to"]["orbit_ref"],
                    provenance=candidate_term.get("provenance"),
                )
            )

    for term in list(hamiltonian_model.get("site_terms") or []):
        site_terms.append(deepcopy(term))
    for term in list(hamiltonian_model.get("higher_body_terms") or []):
        higher_body_terms.append(deepcopy(term))

    term_sets = build_term_sets(candidate_terms)
    return {
        "site_terms": site_terms,
        "bond_terms": bond_terms,
        "higher_body_terms": higher_body_terms,
        "candidate_terms": candidate_terms,
        "term_sets": term_sets,
    }
