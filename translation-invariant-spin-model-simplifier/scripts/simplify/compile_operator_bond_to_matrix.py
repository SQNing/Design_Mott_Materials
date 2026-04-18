#!/usr/bin/env python3
import re
from fractions import Fraction
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from simplify.operator_expression_sparse_expand import (
        has_special_operator_expression_shorthand,
        sparse_expand_operator_expression,
        split_trailing_conjugate_shorthand,
        split_trailing_permutation_shorthand,
        split_trailing_site_swap_shorthand,
    )
else:
    from .operator_expression_sparse_expand import (
        has_special_operator_expression_shorthand,
        sparse_expand_operator_expression,
        split_trailing_conjugate_shorthand,
        split_trailing_permutation_shorthand,
        split_trailing_site_swap_shorthand,
    )


def _infer_spin_from_local_dimension(local_dimension):
    local_dimension = int(local_dimension)
    if local_dimension <= 0:
        raise ValueError("local Hilbert-space dimension must be positive")
    return Fraction(local_dimension - 1, 2)


def _zero_matrix(size):
    return [[0.0 + 0.0j for _ in range(size)] for _ in range(size)]


def _matrix_add(left, right):
    return [
        [left[row][col] + right[row][col] for col in range(len(left[row]))]
        for row in range(len(left))
    ]


def _matrix_scale(matrix, scalar):
    return [[scalar * value for value in row] for row in matrix]


def _kron(left, right):
    result = []
    for left_row in left:
        for right_row in right:
            row = []
            for left_value in left_row:
                row.extend(left_value * right_value for right_value in right_row)
            result.append(row)
    return result


def _spin_operator_matrices(local_dimension):
    spin = _infer_spin_from_local_dimension(local_dimension)
    values = [spin - index for index in range(int(local_dimension))]
    size = int(local_dimension)
    sz = _zero_matrix(size)
    sp = _zero_matrix(size)
    sm = _zero_matrix(size)

    for index, m_value in enumerate(values):
        sz[index][index] = float(m_value)
        if index > 0:
            coeff = (spin * (spin + 1) - m_value * (m_value + 1)) ** 0.5
            sp[index - 1][index] = complex(float(coeff))
        if index < size - 1:
            coeff = (spin * (spin + 1) - m_value * (m_value - 1)) ** 0.5
            sm[index + 1][index] = complex(float(coeff))

    sx = _matrix_scale(_matrix_add(sp, sm), 0.5)
    sy = _matrix_scale(_matrix_add(sp, _matrix_scale(sm, -1.0)), -0.5j)
    return {"Sx": sx, "Sy": sy, "Sz": sz}


def _resolve_scalar(token, parameters):
    cleaned = str(token).strip()
    if cleaned in {"i", "+i", "j", "+j"}:
        return 0.0 + 1.0j
    if cleaned in {"-i", "-j"}:
        return 0.0 - 1.0j
    try:
        return complex(float(cleaned))
    except ValueError:
        pass
    try:
        return complex(cleaned)
    except ValueError:
        pass
    pure_imaginary_i = re.fullmatch(r"(?P<imag>[+\-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+\-]?\d+)?)i$", cleaned)
    if pure_imaginary_i:
        return complex(0.0, float(pure_imaginary_i.group("imag")))
    if cleaned in parameters:
        return complex(parameters[cleaned])
    raise ValueError(f"unknown coefficient token: {cleaned}")


def _collect_compact_operator_basis_terms(expression, parameters, tolerance):
    if has_special_operator_expression_shorthand(expression):
        return []
    pattern = re.compile(
        r"(?P<coeff>[A-Za-z0-9_{}^\\.+\-']+)\s*\*\s*(?P<label>(?:S[xyz]@\d+\s*){2})"
    )
    merged = {}
    residue = str(expression or "")
    for match in pattern.finditer(str(expression or "")):
        coeff = _resolve_scalar(match.group("coeff"), parameters)
        label = " ".join(match.group("label").split())
        merged[label] = merged.get(label, 0.0 + 0.0j) + coeff
        start, end = match.span()
        residue = residue[:start] + (" " * (end - start)) + residue[end:]
    if re.sub(r"[\s+\-]", "", residue):
        return []
    return [
        {"label": label, "coefficient": coefficient}
        for label, coefficient in sorted(merged.items())
        if abs(coefficient) > tolerance
    ]


def _collect_latex_operator_terms(expression, parameters, tolerance):
    compact = re.sub(r"\s+", "", expression)
    compact = compact.replace(r"\left", "").replace(r"\right", "")
    compact = compact.replace(r"\gamma_{ij}^\ast", "")
    compact = compact.replace(r"\gamma_{ij}", "")
    compact = compact.replace(r"\nonumber\\", "")
    compact = compact.replace("&", "")
    merged = {}

    longitudinal_pattern = re.compile(r"(?P<coeff>[A-Za-z0-9_{}^\\.+\-']+)S_i\^zS_j\^z")
    for match in longitudinal_pattern.finditer(compact):
        coeff = _resolve_scalar(match.group("coeff"), parameters)
        merged["Sz@0 Sz@1"] = merged.get("Sz@0 Sz@1", 0.0 + 0.0j) + coeff

    ladder_pattern = re.compile(
        r"\\frac\{(?P<coeff>[A-Za-z0-9_{}^\\.+\-']+)\}\{2\}\(S_i\^\+S_j\^-"
        r"\+S_i\^-S_j\^\+\)"
    )
    for match in ladder_pattern.finditer(compact):
        coeff = _resolve_scalar(match.group("coeff"), parameters)
        for label in ("Sx@0 Sx@1", "Sy@0 Sy@1"):
            merged[label] = merged.get(label, 0.0 + 0.0j) + coeff

    double_raising_pattern = re.compile(
        r"\\frac\{(?P<coeff>[A-Za-z0-9_{}^\\.+\-']+)\}\{2\}\(S_i\^\+S_j\^\+"
        r"\+S_i\^-S_j\^-\)"
    )
    for match in double_raising_pattern.finditer(compact):
        coeff = _resolve_scalar(match.group("coeff"), parameters)
        merged["Sx@0 Sx@1"] = merged.get("Sx@0 Sx@1", 0.0 + 0.0j) + coeff
        merged["Sy@0 Sy@1"] = merged.get("Sy@0 Sy@1", 0.0 + 0.0j) - coeff

    zpm_pattern = re.compile(
        r"(?P<sign>[+\-]?)\\frac\{i(?P<coeff>[A-Za-z0-9_{}^\\.+\-']+)\}\{2\}"
        r"\[\(S_i\^\+\-S_i\^-\)S_j\^z\+S_i\^z\(S_j\^\+\-S_j\^-\)\]"
    )
    for match in zpm_pattern.finditer(compact):
        coeff = _resolve_scalar(match.group("coeff"), parameters)
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
        {"label": label, "coefficient": coefficient}
        for label, coefficient in sorted(merged.items())
        if abs(coefficient) > tolerance
    ]


def _expanded_terms(expression, parameters, tolerance):
    terms = _collect_compact_operator_basis_terms(expression, parameters, tolerance)
    if terms:
        return terms
    terms = sparse_expand_operator_expression(expression, parameters, tolerance)
    if terms:
        return terms
    return _collect_latex_operator_terms(expression, parameters, tolerance)


def _label_to_matrix(label, local_dimension):
    support_ops = _spin_operator_matrices(local_dimension)
    left_name, right_name = [factor.split("@")[0] for factor in label.split()]
    return _kron(support_ops[left_name], support_ops[right_name])


def compile_operator_bond_to_matrix(expression, *, local_dimension, parameters=None, tolerance=1e-9):
    terms = _expanded_terms(expression, dict(parameters or {}), tolerance)
    if not terms:
        raise ValueError("unable to compile operator text to a two-body matrix")

    size = int(local_dimension) ** 2
    matrix = _zero_matrix(size)
    for term in terms:
        term_matrix = _matrix_scale(_label_to_matrix(term["label"], local_dimension), term["coefficient"])
        matrix = _matrix_add(matrix, term_matrix)
    return matrix
