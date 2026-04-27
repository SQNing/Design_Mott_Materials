#!/usr/bin/env python3

from copy import deepcopy


def _require_dict(payload):
    if not isinstance(payload, dict):
        raise ValueError("cpn-pair-model-payload-must-be-dict")


def _matrix_shape(matrix):
    rows = len(matrix)
    cols = len(matrix[0]) if rows else 0
    return [rows, cols]


def _validate_serialized_matrix(matrix, *, expected_shape, error_code):
    if not isinstance(matrix, list):
        raise ValueError(error_code)
    actual_shape = _matrix_shape(matrix)
    if actual_shape != list(expected_shape):
        raise ValueError(error_code)


def normalize_cpn_pair_model(payload):
    _require_dict(payload)
    normalized = deepcopy(payload)
    normalized.setdefault("schema_version", 1)
    normalized.setdefault("model_family", "cpn_pair_model")
    normalized.setdefault("classical_family", "cpn")
    normalized.setdefault("onsite_terms", [])
    normalized.setdefault("bond_terms", [])
    normalized.setdefault("pair_operator_convention", {})
    normalized["pair_operator_convention"].setdefault("representation", "pair_matrix")
    normalized["pair_operator_convention"].setdefault("pair_basis_order", "site_i_major_site_j_minor")
    normalized["pair_operator_convention"].setdefault(
        "tensor_view",
        {
            "kind": "K_ab_cd",
            "index_order": ["left_bra", "right_bra", "left_ket", "right_ket"],
        },
    )
    normalized.setdefault("provenance", {})
    return normalized


def validate_cpn_pair_model(payload):
    _require_dict(payload)
    if str(payload.get("model_family")) != "cpn_pair_model":
        raise ValueError("unsupported-model-family")
    if str(payload.get("classical_family")) != "cpn":
        raise ValueError("unsupported-classical-family")

    local_dimension = int(payload.get("local_dimension", 0))
    if local_dimension <= 0:
        raise ValueError("invalid-local-dimension")

    pair_operator_convention = dict(payload.get("pair_operator_convention") or {})
    if str(pair_operator_convention.get("pair_basis_order")) != "site_i_major_site_j_minor":
        raise ValueError("unsupported-pair-basis-order")

    bond_terms = list(payload.get("bond_terms") or [])
    expected_pair_shape = [local_dimension * local_dimension, local_dimension * local_dimension]
    for term in bond_terms:
        if not isinstance(term, dict):
            raise ValueError("bond-term-must-be-dict")
        if "source" not in term or "target" not in term or "translation" not in term:
            raise ValueError("bond-term-missing-site-identity")
        translation = list(term.get("translation") or [])
        if len(translation) != 3:
            raise ValueError("bond-term-translation-must-have-length-3")
        matrix_shape = list(term.get("matrix_shape") or [])
        if matrix_shape and matrix_shape != expected_pair_shape:
            raise ValueError("pair-matrix-dimension-mismatch")
        _validate_serialized_matrix(
            term.get("pair_matrix"),
            expected_shape=expected_pair_shape,
            error_code="pair-matrix-dimension-mismatch",
        )

    onsite_terms = list(payload.get("onsite_terms") or [])
    for term in onsite_terms:
        if not isinstance(term, dict):
            raise ValueError("onsite-term-must-be-dict")
        if term.get("kind") != "local_operator_matrix":
            continue
        matrix = term.get("payload", {}).get("matrix")
        _validate_serialized_matrix(
            matrix,
            expected_shape=[local_dimension, local_dimension],
            error_code="onsite-matrix-dimension-mismatch",
        )

    return payload
