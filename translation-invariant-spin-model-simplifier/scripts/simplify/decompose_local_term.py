#!/usr/bin/env python3
import argparse
import json
import re
import sys
from fractions import Fraction
from itertools import product
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from simplify.operator_expression_sparse_expand import sparse_expand_operator_expression
    from simplify.spin_multipole_basis import product_spin_multipole_basis
else:
    from .operator_expression_sparse_expand import sparse_expand_operator_expression
    from .spin_multipole_basis import product_spin_multipole_basis


def _identity(size):
    return [[1.0 + 0.0j if row == col else 0.0 + 0.0j for col in range(size)] for row in range(size)]


def _matrix_scale(matrix, scalar):
    return [[scalar * value for value in row] for row in matrix]


def _matrix_multiply(left, right):
    rows = len(left)
    inner = len(right)
    cols = len(right[0])
    result = [[0.0 + 0.0j for _ in range(cols)] for _ in range(rows)]
    for row in range(rows):
        for col in range(cols):
            total = 0.0 + 0.0j
            for pivot in range(inner):
                total += left[row][pivot] * right[pivot][col]
            result[row][col] = total
    return result


def _matrix_shape(matrix):
    return len(matrix), len(matrix[0]) if matrix else 0


def _matrix_dagger(matrix):
    rows = len(matrix)
    cols = len(matrix[0])
    return [[complex(matrix[row][col]).conjugate() for row in range(rows)] for col in range(cols)]


def _matrix_trace(matrix):
    return sum(matrix[index][index] for index in range(len(matrix)))


def _kron(left, right):
    result = []
    for left_row in left:
        for right_row in right:
            row = []
            for left_value in left_row:
                row.extend(left_value * right_value for right_value in right_row)
            result.append(row)
    return result


def spin_half_basis():
    return {
        "I": _identity(2),
        "Sx": _matrix_scale([[0.0, 1.0], [1.0, 0.0]], 0.5),
        "Sy": _matrix_scale([[0.0, -1.0j], [1.0j, 0.0]], 0.5),
        "Sz": _matrix_scale([[1.0, 0.0], [0.0, -1.0]], 0.5),
    }


def product_basis(support):
    labels = []
    operators = []
    basis = spin_half_basis()
    for names in product(["I", "Sx", "Sy", "Sz"], repeat=len(support)):
        label_parts = [f"{name}@{site}" for site, name in zip(support, names) if name != "I"]
        operator = [[1.0 + 0.0j]]
        for name in names:
            operator = _kron(operator, basis[name])
        labels.append(" ".join(label_parts) or "identity")
        operators.append(operator)
    return labels, operators


def _coerce_matrix(value):
    if not isinstance(value, list) or not value:
        raise ValueError("matrix shape must match support size")
    matrix = []
    expected_cols = None
    for row in value:
        if not isinstance(row, list) or not row:
            raise ValueError("matrix shape must match support size")
        if expected_cols is None:
            expected_cols = len(row)
        elif len(row) != expected_cols:
            raise ValueError("matrix shape must match support size")
        matrix.append([complex(entry) for entry in row])
    return matrix


def _real_if_close(value, tolerance):
    if abs(value.imag) <= tolerance:
        return float(value.real)
    return value


def _resolve_scalar(token, parameters):
    cleaned = str(token).strip()
    if not cleaned:
        raise ValueError("empty coefficient token")
    try:
        return complex(float(cleaned))
    except ValueError:
        pass
    if cleaned in parameters:
        return complex(parameters[cleaned])
    raise ValueError(f"unknown coefficient token: {cleaned}")


def _collect_operator_basis_terms(expression, parameters, tolerance):
    pattern = re.compile(
        r"(?P<coeff>[A-Za-z0-9_{}^\\.+\-']+)\s*\*\s*(?P<label>(?:S[xyz]@\d+\s*)+)"
    )
    merged = {}
    for match in pattern.finditer(expression):
        try:
            coeff = _resolve_scalar(match.group("coeff"), parameters)
        except ValueError:
            return []
        label = " ".join(match.group("label").split())
        merged[label] = merged.get(label, 0.0 + 0.0j) + coeff
    return [
        {"label": label, "coefficient": _real_if_close(coefficient, tolerance)}
        for label, coefficient in sorted(merged.items())
        if abs(coefficient) > tolerance
    ]


def _collect_latex_operator_terms(expression, parameters, tolerance):
    compact = re.sub(r"\s+", "", expression)
    compact = compact.replace(r"\left", "").replace(r"\right", "")
    merged = {}

    longitudinal_pattern = re.compile(r"(?P<coeff>[A-Za-z0-9_{}^\\.+\-']+)S_i\^zS_j\^z")
    for match in longitudinal_pattern.finditer(compact):
        try:
            coeff = _resolve_scalar(match.group("coeff"), parameters)
        except ValueError:
            return []
        merged["Sz@0 Sz@1"] = merged.get("Sz@0 Sz@1", 0.0 + 0.0j) + coeff

    ladder_pattern = re.compile(
        r"\\frac\{(?P<coeff>[A-Za-z0-9_{}^\\.+\-']+)\}\{2\}\(S_i\^\+S_j\^-"
        r"\+S_i\^-S_j\^\+\)"
    )
    for match in ladder_pattern.finditer(compact):
        try:
            coeff = _resolve_scalar(match.group("coeff"), parameters)
        except ValueError:
            return []
        for label in ("Sx@0 Sx@1", "Sy@0 Sy@1"):
            merged[label] = merged.get(label, 0.0 + 0.0j) + coeff

    double_raising_pattern = re.compile(
        r"\\frac\{(?P<coeff>[A-Za-z0-9_{}^\\.+\-']+)\}\{2\}\(S_i\^\+S_j\^\+"
        r"\+S_i\^-S_j\^-\)"
    )
    for match in double_raising_pattern.finditer(compact):
        try:
            coeff = _resolve_scalar(match.group("coeff"), parameters)
        except ValueError:
            return []
        merged["Sx@0 Sx@1"] = merged.get("Sx@0 Sx@1", 0.0 + 0.0j) + coeff
        merged["Sy@0 Sy@1"] = merged.get("Sy@0 Sy@1", 0.0 + 0.0j) - coeff

    zpm_pattern = re.compile(
        r"(?P<sign>[+\-]?)\\frac\{i(?P<coeff>[A-Za-z0-9_{}^\\.+\-']+)\}\{2\}"
        r"\[\(S_i\^\+\-S_i\^-\)S_j\^z\+S_i\^z\(S_j\^\+\-S_j\^-\)\]"
    )
    for match in zpm_pattern.finditer(compact):
        try:
            coeff = _resolve_scalar(match.group("coeff"), parameters)
        except ValueError:
            return []
        sign = match.group("sign")
        prefactor = coeff if sign == "-" else -coeff
        for label in ("Sy@0 Sz@1", "Sz@0 Sy@1"):
            merged[label] = merged.get(label, 0.0 + 0.0j) + prefactor

    residue = longitudinal_pattern.sub("", compact)
    residue = ladder_pattern.sub("", residue)
    residue = double_raising_pattern.sub("", residue)
    residue = zpm_pattern.sub("", residue)
    if re.search(r"S_[ij]\^[xyz\+\-]", residue):
        return []

    return [
        {"label": label, "coefficient": _real_if_close(coefficient, tolerance)}
        for label, coefficient in sorted(merged.items())
        if abs(coefficient) > tolerance
    ]


def _decompose_operator_expression(expression, parameters, tolerance):
    parameters = dict(parameters or {})
    terms = _collect_operator_basis_terms(expression, parameters, tolerance)
    if not terms:
        terms = _collect_latex_operator_terms(expression, parameters, tolerance)
    if not terms:
        terms = sparse_expand_operator_expression(expression, parameters, tolerance)
    if terms:
        return {"mode": "operator-basis", "terms": terms}
    return {
        "mode": "operator",
        "terms": [
            {
                "label": "raw-operator",
                "coefficient": 1.0,
                "value": expression,
            }
        ],
    }


def _decompose_operator_family_collection(collection, parameters, tolerance):
    combined_terms = []
    for entry in collection:
        family = entry.get("family")
        expression = entry.get("expression", "")
        decomposition = _decompose_operator_expression(expression, parameters, tolerance)
        if decomposition.get("mode") != "operator-basis":
            raw_terms = []
            for term in decomposition.get("terms", []):
                raw_term = dict(term)
                if family is not None:
                    raw_term["family"] = family
                raw_terms.append(raw_term)
            return {"mode": decomposition.get("mode", "operator"), "terms": raw_terms}
        for term in decomposition.get("terms", []):
            annotated = dict(term)
            if family is not None:
                annotated["family"] = family
            combined_terms.append(annotated)
    return {"mode": "operator-basis", "terms": combined_terms}


def _infer_spin_from_local_dimension(local_dimension):
    local_dimension = int(local_dimension)
    if local_dimension <= 0:
        raise ValueError("local Hilbert-space dimension must be positive")
    return Fraction(local_dimension - 1, 2)


def _validate_matrix_shape(matrix, support, local_dimension):
    expected_size = int(local_dimension) ** len(support)
    rows, cols = _matrix_shape(matrix)
    if rows != expected_size or cols != expected_size:
        raise ValueError(f"matrix shape must be {expected_size}x{expected_size} for support size {len(support)}")


def _validate_hermitian(matrix, tolerance):
    dagger = _matrix_dagger(matrix)
    rows, cols = _matrix_shape(matrix)
    for row in range(rows):
        for col in range(cols):
            if abs(matrix[row][col] - dagger[row][col]) > tolerance:
                raise ValueError("matrix input must be Hermitian")


def decompose_local_term(normalized, tolerance=1e-9):
    representation = normalized["local_term"]["representation"]
    support = normalized["local_term"]["support"]
    if representation["kind"] == "operator":
        return _decompose_operator_expression(
            representation["value"],
            normalized.get("parameters", {}),
            tolerance,
        )
    if representation["kind"] == "operator_family_collection":
        return _decompose_operator_family_collection(
            representation["value"],
            normalized.get("parameters", {}),
            tolerance,
        )
    if representation["kind"] != "matrix":
        raise ValueError("unsupported representation kind for decomposition")
    local_dimension = int(normalized["local_hilbert"]["dimension"])
    spin = _infer_spin_from_local_dimension(local_dimension)
    matrix = _coerce_matrix(representation["value"])
    _validate_matrix_shape(matrix, support, local_dimension)
    _validate_hermitian(matrix, tolerance)
    labels, operators = product_spin_multipole_basis(spin, support)
    terms = []
    for label, operator in zip(labels, operators):
        denom = _matrix_trace(_matrix_multiply(_matrix_dagger(operator), operator)).real
        coeff = _matrix_trace(_matrix_multiply(_matrix_dagger(operator), matrix)) / denom
        if abs(coeff) > tolerance:
            terms.append({"label": label, "coefficient": _real_if_close(coeff, tolerance)})
    return {"mode": "spin-multipole-basis", "terms": terms}


def _load_payload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?")
    args = parser.parse_args()
    payload = _load_payload(args.input) if args.input else json.load(sys.stdin)
    print(json.dumps(decompose_local_term(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
