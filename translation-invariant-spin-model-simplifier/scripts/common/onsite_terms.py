#!/usr/bin/env python3

from pathlib import Path
import re
import sys
import math

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from simplify.operator_expression_sparse_expand import sparse_expand_operator_expression
else:
    from simplify.operator_expression_sparse_expand import sparse_expand_operator_expression


SUPPORTED_ONSITE_KINDS = {
    "quadratic_spin_cartesian",
    "linear_spin_cartesian",
    "local_operator_matrix",
}


def _normalize_site_scope(site_scope):
    if not isinstance(site_scope, dict):
        raise ValueError("site_scope must be a mapping")
    kind = str(site_scope.get("kind", "")).strip()
    if kind != "site":
        raise ValueError(f"unsupported site_scope kind: {kind!r}")
    if "site" not in site_scope:
        raise ValueError("site_scope must include site")
    return {"kind": "site", "site": int(site_scope["site"])}


def _normalize_operator_basis(operator_basis):
    if not isinstance(operator_basis, dict):
        raise ValueError("operator_basis must be a mapping")
    family = str(operator_basis.get("family", "")).strip()
    if not family:
        raise ValueError("operator_basis must include family")
    normalized = {"family": family}
    if "components" in operator_basis:
        normalized["components"] = [str(value) for value in operator_basis["components"]]
    if "labels" in operator_basis:
        normalized["labels"] = [str(value) for value in operator_basis["labels"]]
    return normalized


def _normalize_frame(frame, *, kind):
    if not isinstance(frame, dict):
        raise ValueError(f"{kind} onsite terms require frame metadata")
    frame_kind = str(frame.get("kind", "")).strip()
    if not frame_kind:
        raise ValueError(f"{kind} onsite terms require frame.kind")
    normalized = {"kind": frame_kind}
    if "axes" in frame:
        normalized["axes"] = [str(value) for value in frame["axes"]]
    return normalized


def _normalize_real_matrix(matrix):
    if not isinstance(matrix, list) or not matrix:
        raise ValueError("payload.matrix must be a non-empty list")
    size = len(matrix)
    normalized = []
    for row in matrix:
        if not isinstance(row, list) or len(row) != size:
            raise ValueError("payload.matrix must be square")
        normalized.append([float(value) for value in row])
    return normalized


def _normalize_real_vector(vector):
    if not isinstance(vector, list) or len(vector) != 3:
        raise ValueError("payload.vector must be a 3-element list")
    return [float(value) for value in vector]


def _validate_local_dimension(matrix, local_dimension):
    if local_dimension is None:
        return
    if len(matrix) != int(local_dimension):
        raise ValueError("onsite term matrix shape must match local_dimension")


def _canonicalize_single_onsite_term(term, *, local_dimension=None):
    if not isinstance(term, dict):
        raise ValueError("onsite term must be a mapping")
    kind = str(term.get("kind", "")).strip()
    if kind not in SUPPORTED_ONSITE_KINDS:
        raise ValueError(f"unsupported onsite term kind: {kind!r}")

    payload = term.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("onsite term payload must be a mapping")

    normalized = {
        "kind": kind,
        "site_scope": _normalize_site_scope(term.get("site_scope")),
        "operator_basis": _normalize_operator_basis(term.get("operator_basis")),
        "frame": _normalize_frame(term.get("frame"), kind=kind),
        "provenance": dict(term.get("provenance", {})),
    }

    if kind == "quadratic_spin_cartesian":
        matrix = _normalize_real_matrix(payload.get("matrix"))
        if len(matrix) != 3:
            raise ValueError("quadratic_spin_cartesian onsite terms require a 3x3 matrix")
        normalized["payload"] = {"matrix": matrix}
    elif kind == "linear_spin_cartesian":
        normalized["payload"] = {"vector": _normalize_real_vector(payload.get("vector"))}
    else:
        matrix = _normalize_real_matrix(payload.get("matrix"))
        _validate_local_dimension(matrix, local_dimension)
        normalized["payload"] = {"matrix": matrix}

    return normalized


def validate_onsite_terms(onsite_terms, *, local_dimension=None):
    return canonicalize_onsite_terms(onsite_terms, local_dimension=local_dimension)


def canonicalize_onsite_terms(onsite_terms, *, local_dimension=None):
    if onsite_terms is None:
        return []
    if not isinstance(onsite_terms, list):
        raise ValueError("onsite_terms must be a list")
    return [
        _canonicalize_single_onsite_term(term, local_dimension=local_dimension)
        for term in onsite_terms
    ]


def _frame_from_coordinate_convention(coordinate_convention):
    convention = dict(coordinate_convention or {})
    frame_kind = str(convention.get("frame") or "global_cartesian")
    axes = list(convention.get("axis_labels") or [])
    if not axes:
        axes = ["x", "y", "z"] if frame_kind != "global_crystallographic" else ["a", "b", "c"]
    return {"kind": frame_kind, "axes": [str(value) for value in axes]}


def _spin_cartesian_operator_matrices(local_dimension):
    local_dimension = int(local_dimension)
    if local_dimension < 2:
        raise ValueError("local_dimension must be at least 2")

    spin = 0.5 * float(local_dimension - 1)
    sz = np.zeros((local_dimension, local_dimension), dtype=complex)
    sp = np.zeros((local_dimension, local_dimension), dtype=complex)
    sm = np.zeros((local_dimension, local_dimension), dtype=complex)

    for row in range(local_dimension):
        m_row = spin - float(row)
        sz[row, row] = m_row
        if row + 1 < local_dimension:
            m_col = m_row - 1.0
            coefficient = math.sqrt(max(0.0, spin * (spin + 1.0) - m_col * (m_col + 1.0)))
            sp[row, row + 1] = coefficient
            sm[row + 1, row] = coefficient

    sx = 0.5 * (sp + sm)
    sy = -0.5j * (sp - sm)
    return sx, sy, sz


def linear_spin_cartesian_operator_matrix(vector, *, local_dimension):
    coefficients = np.array(_normalize_real_vector(list(vector)), dtype=float)
    sx, sy, sz = _spin_cartesian_operator_matrices(local_dimension)
    return coefficients[0] * sx + coefficients[1] * sy + coefficients[2] * sz


def _coerce_real_coefficient(value, *, tolerance=1.0e-9):
    try:
        coefficient = complex(value)
    except TypeError:
        coefficient = complex(float(value))
    if abs(coefficient.imag) > tolerance:
        raise ValueError("quadratic spin-cartesian onsite terms require real coefficients")
    return float(coefficient.real)


def _quadratic_spin_cartesian_from_operator_expression(expression, *, parameters, site, coordinate_convention):
    terms = sparse_expand_operator_expression(str(expression or ""), dict(parameters or {}), 1.0e-9)
    if not terms:
        return None

    axis_index = {"Sx": 0, "Sy": 1, "Sz": 2}
    matrix = [[0.0, 0.0, 0.0] for _ in range(3)]
    saw_term = False

    for term in terms:
        label = str(term.get("label", "")).strip()
        if not label or label == "identity":
            return None
        factors = label.split()
        if len(factors) != 2:
            return None
        parsed = []
        for factor in factors:
            match = re.fullmatch(r"(S[xyz])@(-?\d+)", factor)
            if not match:
                return None
            operator, factor_site = match.groups()
            if int(factor_site) != int(site):
                return None
            parsed.append(operator)
        coefficient = _coerce_real_coefficient(term.get("coefficient", 0.0))
        matrix[axis_index[parsed[0]]][axis_index[parsed[1]]] += coefficient
        saw_term = True

    if not saw_term:
        return None

    return {
        "kind": "quadratic_spin_cartesian",
        "site_scope": {"kind": "site", "site": int(site)},
        "operator_basis": {"family": "spin_cartesian", "components": ["Sx", "Sy", "Sz"]},
        "frame": _frame_from_coordinate_convention(coordinate_convention),
        "payload": {"matrix": matrix},
        "provenance": {"source_kind": "normalized_local_term", "source_representation": "operator"},
    }


def _resolve_parameter_value(parameters, token):
    raw_value = dict(parameters or {}).get(token)
    if isinstance(raw_value, dict):
        raw_value = raw_value.get("value")
    if raw_value is None:
        return None
    return _coerce_real_coefficient(raw_value)


def _quadratic_spin_cartesian_from_document_source_text(
    source_text,
    *,
    parameters,
    site,
    coordinate_convention,
):
    text = str(source_text or "")
    if not text.strip():
        return None

    pattern = re.compile(
        r"(?P<sign>[+-]?)\s*"
        r"(?P<coefficient>[A-Za-z][A-Za-z0-9_{}'^\\]*)\s*"
        r"\\sum_\{?[A-Za-z]\}?\s*"
        r"\(\s*S_[A-Za-z]\^(?:\{(?P<axis_braced>[xyz])\}|(?P<axis_plain>[xyz]))\s*\)\s*\^2",
        re.IGNORECASE,
    )

    axis_index = {"x": 0, "y": 1, "z": 2}
    matrix = [[0.0, 0.0, 0.0] for _ in range(3)]
    saw_term = False
    seen_terms = set()

    for match in pattern.finditer(text):
        coefficient_token = str(match.group("coefficient") or "").strip()
        coefficient_value = _resolve_parameter_value(parameters, coefficient_token)
        if coefficient_value is None:
            continue
        axis = str(match.group("axis_braced") or match.group("axis_plain") or "").lower()
        if axis not in axis_index:
            continue
        sign = -1.0 if str(match.group("sign") or "") == "-" else 1.0
        signature = (sign, coefficient_token, axis)
        if signature in seen_terms:
            continue
        seen_terms.add(signature)
        matrix[axis_index[axis]][axis_index[axis]] += sign * coefficient_value
        saw_term = True

    if not saw_term:
        return None

    return {
        "kind": "quadratic_spin_cartesian",
        "site_scope": {"kind": "site", "site": int(site)},
        "operator_basis": {"family": "spin_cartesian", "components": ["Sx", "Sy", "Sz"]},
        "frame": _frame_from_coordinate_convention(coordinate_convention),
        "payload": {"matrix": matrix},
        "provenance": {
            "source_kind": "document_source_text",
            "source_representation": "latex_document",
        },
    }


def derive_canonical_onsite_terms_from_normalized_payload(normalized):
    if not isinstance(normalized, dict):
        return []

    explicit_onsite_terms = normalized.get("onsite_terms")
    if explicit_onsite_terms is not None:
        local_dimension = normalized.get("local_hilbert", {}).get("dimension")
        return canonicalize_onsite_terms(explicit_onsite_terms, local_dimension=local_dimension)

    local_term = normalized.get("local_term", {})
    if isinstance(local_term, dict):
        support = list(local_term.get("support") or [])
        representation = local_term.get("representation", {})
        if len(support) == 1 and isinstance(representation, dict) and representation.get("kind") == "operator":
            quadratic = _quadratic_spin_cartesian_from_operator_expression(
                representation.get("value"),
                parameters=normalized.get("parameters", {}),
                site=int(support[0]),
                coordinate_convention=normalized.get("coordinate_convention", {}),
            )
            if quadratic is not None:
                return canonicalize_onsite_terms([quadratic])

    document_intermediate = normalized.get("document_intermediate", {})
    document_source_text = normalized.get("document_source_text")
    if not document_source_text and isinstance(document_intermediate, dict):
        document_source_text = document_intermediate.get("source_text")

    document_quadratic = _quadratic_spin_cartesian_from_document_source_text(
        document_source_text,
        parameters=normalized.get("parameters", {}),
        site=0,
        coordinate_convention=normalized.get("coordinate_convention", {}),
    )
    if document_quadratic is not None:
        return canonicalize_onsite_terms([document_quadratic])
    return []
