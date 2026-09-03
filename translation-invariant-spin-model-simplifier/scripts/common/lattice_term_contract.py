#!/usr/bin/env python3
"""Validation helpers for the lattice term contract."""

from __future__ import annotations

from collections.abc import Mapping


REQUIRED_TOP_LEVEL_KEYS = {
    "schema_version",
    "local_hilbert",
    "lattice_structure",
    "symmetry",
    "term_attachments",
    "solver_request",
    "parameters",
    "provenance",
}

FORBIDDEN_LEGACY_FIELDS = {
    "bond_label",
    "classical_bond_label",
    "model_bond_label",
    "solver_bond_label",
    "selected_local_bond_bond_label",
    "bond_orbit_shell_map",
    "bond_orbit_representative_map",
    "multipole_class",
    "multipole_classes",
    "q_path_lattice_class",
    "adapter_bond_label",
    "input_bond_label",
}


class ContractValidationError(ValueError):
    def __init__(self, code: str, message: str | None = None):
        self.code = code
        super().__init__(message or code)


def _raise(code: str, detail: str | None = None):
    if detail:
        raise ContractValidationError(code, f"{code}: {detail}")
    raise ContractValidationError(code)


def _require_mapping(value, code: str):
    if not isinstance(value, Mapping):
        _raise(code)
    return value


def find_forbidden_legacy_fields(payload):
    findings = []

    def walk(value, path):
        if isinstance(value, Mapping):
            for key, child in value.items():
                child_path = path + [str(key)]
                if str(key) in FORBIDDEN_LEGACY_FIELDS:
                    findings.append({"path": ".".join(child_path), "field": str(key)})
                walk(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, path + [str(index)])

    walk(payload, [])
    return findings


def validate_local_hilbert(payload):
    local_hilbert = _require_mapping(payload.get("local_hilbert"), "local-hilbert-must-be-object")
    sites = list(local_hilbert.get("sites") or [])
    basis_registry = _require_mapping(local_hilbert.get("basis_registry"), "basis-registry-must-be-object")
    operator_bases = _require_mapping(local_hilbert.get("operator_bases"), "operator-bases-must-be-object")
    classical_spaces = _require_mapping(local_hilbert.get("classical_spaces"), "classical-spaces-must-be-object")

    site_refs = set()
    dimensions_by_site_ref = {}
    for site in sites:
        _require_mapping(site, "site-record-must-be-object")
        site_ref = str(site.get("site_ref") or "")
        basis_ref = str(site.get("basis_ref") or "")
        classical_space_ref = str(site.get("classical_space_ref") or "")
        if not site_ref:
            _raise("site-ref-required")
        if basis_ref not in basis_registry:
            _raise("unknown-basis-ref", basis_ref)
        if classical_space_ref and classical_space_ref not in classical_spaces:
            _raise("unknown-classical-space-ref", classical_space_ref)
        for operator_basis_ref in list(site.get("operator_basis_refs") or []):
            if operator_basis_ref not in operator_bases:
                _raise("unknown-operator-basis-ref", str(operator_basis_ref))
        basis = _require_mapping(basis_registry[basis_ref], "basis-record-must-be-object")
        try:
            dimension = int(basis.get("dimension"))
        except (TypeError, ValueError):
            _raise("invalid-local-dimension", basis_ref)
        if dimension <= 0:
            _raise("invalid-local-dimension", basis_ref)
        site_refs.add(site_ref)
        dimensions_by_site_ref[site_ref] = dimension

    if not site_refs:
        _raise("local-hilbert-sites-required")

    return {
        "site_refs": site_refs,
        "dimensions_by_site_ref": dimensions_by_site_ref,
    }


def validate_lattice_structure(payload):
    lattice_structure = _require_mapping(payload.get("lattice_structure"), "lattice-structure-must-be-object")
    bond_orbits = lattice_structure.get("bond_orbits", [])
    if not isinstance(bond_orbits, list):
        _raise("bond-orbits-must-be-list")
    return lattice_structure


def validate_symmetry(payload):
    return _require_mapping(payload.get("symmetry"), "symmetry-must-be-object")


def _validate_scalar(value):
    if not isinstance(value, Mapping):
        return
    kind = value.get("kind")
    if kind == "real":
        if "value" not in value:
            _raise("invalid-real-scalar")
        return
    if kind == "complex":
        if "re" not in value or "im" not in value:
            _raise("invalid-complex-scalar")
        return
    if kind == "parameter_ref":
        if not value.get("parameter_ref"):
            _raise("invalid-parameter-ref")
        return
    if kind == "structured_matrix":
        _validate_structured_matrix(value)


def _validate_structured_matrix(matrix):
    _require_mapping(matrix, "matrix-must-be-object")
    shape = matrix.get("shape")
    if shape is not None:
        if not isinstance(shape, list) or len(shape) != 2:
            _raise("invalid-matrix-shape")
        for value in shape:
            if not isinstance(value, int) or value <= 0:
                _raise("invalid-matrix-shape")
    for row in list(matrix.get("entries") or []):
        if isinstance(row, list):
            for scalar in row:
                _validate_scalar(scalar)
        else:
            _validate_scalar(row)


def validate_parameters(payload):
    parameters = payload.get("parameters")
    if parameters is None:
        _raise("parameters-required")
    _require_mapping(parameters, "parameters-must-be-object")
    return parameters


def _site_dimension(context, site_ref):
    try:
        return context["dimensions_by_site_ref"][site_ref]
    except KeyError:
        _raise("unknown-site-ref", str(site_ref))


def validate_term_attachments(payload, context=None):
    context = context or validate_local_hilbert(payload)
    term_attachments = _require_mapping(payload.get("term_attachments"), "term-attachments-must-be-object")
    for key in ("site_terms", "bond_terms", "higher_body_terms"):
        if key not in term_attachments:
            term_attachments[key] = []
        if not isinstance(term_attachments[key], list):
            _raise(f"{key.replace('_', '-')}-must-be-list")

    for term in term_attachments["site_terms"]:
        _require_mapping(term, "site-term-must-be-object")
        site_ref = term.get("site_ref")
        if site_ref is not None:
            _site_dimension(context, site_ref)
        payload_record = term.get("payload")
        if isinstance(payload_record, Mapping) and isinstance(payload_record.get("matrix"), Mapping):
            _validate_structured_matrix(payload_record["matrix"])

    for term in term_attachments["bond_terms"]:
        _require_mapping(term, "bond-term-must-be-object")
        support = list(term.get("support_ref") or [])
        if len(support) != 2:
            _raise("bond-term-support-must-have-two-sites")
        left_dimension = _site_dimension(context, support[0])
        right_dimension = _site_dimension(context, support[1])
        payload_record = _require_mapping(term.get("payload"), "term-payload-must-be-object")
        matrix = payload_record.get("matrix")
        if isinstance(matrix, Mapping):
            _validate_structured_matrix(matrix)
            if payload_record.get("kind") == "pair_matrix":
                expected = [left_dimension * right_dimension, left_dimension * right_dimension]
                shape = list(matrix.get("shape") or [])
                if shape and shape != expected:
                    _raise("matrix-shape-mismatch", f"expected {expected}, got {shape}")

    for term in term_attachments["higher_body_terms"]:
        _require_mapping(term, "higher-body-term-must-be-object")
        participates_in_symmetry_contract = any(
            key in term for key in ("arity", "cluster", "operator_family")
        )
        if not participates_in_symmetry_contract:
            continue
        try:
            arity = int(term.get("arity"))
        except (TypeError, ValueError):
            _raise("higher-body-arity-invalid")
        if arity < 3:
            _raise("higher-body-arity-invalid")
        cluster = term.get("cluster")
        if not isinstance(cluster, list) or len(cluster) != arity:
            _raise("higher-body-cluster-size-mismatch")
        for entry in cluster:
            _require_mapping(entry, "higher-body-cluster-entry-must-be-object")
            if entry.get("site") is None and entry.get("site_ref") is None:
                _raise("higher-body-cluster-site-required")
            translation = entry.get("translation", [0, 0, 0])
            if not isinstance(translation, list) or len(translation) != 3:
                _raise("higher-body-cluster-translation-invalid")
        if not str(term.get("operator_family") or "").strip():
            _raise("higher-body-operator-family-required")
        if not isinstance(term.get("permutation_action"), Mapping):
            _raise("higher-body-permutation-action-required")
        if not isinstance(term.get("adjoint_action"), Mapping):
            _raise("higher-body-adjoint-action-required")
        if "coefficient" in term:
            _validate_scalar(term["coefficient"])

    return term_attachments


def validate_lattice_term_payload(payload):
    _require_mapping(payload, "payload-must-be-object")
    missing = sorted(REQUIRED_TOP_LEVEL_KEYS.difference(payload))
    if missing:
        _raise("missing-required-top-level-key", ",".join(missing))
    findings = find_forbidden_legacy_fields(payload)
    if findings:
        _raise("forbidden-legacy-field", findings[0]["path"])

    context = validate_local_hilbert(payload)
    validate_lattice_structure(payload)
    validate_symmetry(payload)
    validate_parameters(payload)
    validate_term_attachments(payload, context)
    _require_mapping(payload.get("solver_request"), "solver-request-must-be-object")
    _require_mapping(payload.get("provenance"), "provenance-must-be-object")
    return payload
