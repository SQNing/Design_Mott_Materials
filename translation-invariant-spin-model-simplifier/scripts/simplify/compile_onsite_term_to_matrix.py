#!/usr/bin/env python3
import re
from fractions import Fraction

from simplify.operator_expression_sparse_expand import sparse_expand_operator_expression


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

    sx = _matrix_scale(
        [[sp[row][col] + sm[row][col] for col in range(size)] for row in range(size)],
        0.5,
    )
    sy = _matrix_scale(
        [[sp[row][col] - sm[row][col] for col in range(size)] for row in range(size)],
        -0.5j,
    )
    return {"Sx": sx, "Sy": sy, "Sz": sz}


def _normalize_supported_onsite_expression(expression):
    def _expand_power(match):
        operator = match.group("operator")
        power = int(match.group("power"))
        return " ".join(operator for _ in range(power))

    compact = re.sub(r"\s+", "", str(expression or ""))
    compact = compact.replace(r"\left", "").replace(r"\right", "")
    compact = compact.replace("S_i^x", "Sx@0")
    compact = compact.replace("S_i^y", "Sy@0")
    compact = compact.replace("S_i^z", "Sz@0")
    compact = re.sub(
        r"^(?P<coeff>[A-Za-z0-9_{}^\\.+\-']+)(?=(?:\(|S[xyz]@0))",
        r"\g<coeff>*",
        compact,
        count=1,
    )
    compact = re.sub(
        r"\((?P<operator>S[xyz]@0)\)\^(?P<power>\d+)",
        _expand_power,
        compact,
    )
    return compact


def _label_to_onsite_matrix(label, local_dimension):
    factors = str(label or "").split()
    if not factors:
        raise ValueError("unsupported onsite operator expression")

    support_ops = _spin_operator_matrices(local_dimension)
    matrix = None
    for factor in factors:
        match = re.fullmatch(r"(?P<operator>S[xyz])@(?P<site>-?\d+)", factor)
        if not match or int(match.group("site")) != 0:
            raise ValueError("unsupported onsite operator expression")
        operator_matrix = support_ops[match.group("operator")]
        matrix = operator_matrix if matrix is None else _matrix_multiply(matrix, operator_matrix)
    return matrix


def compile_onsite_term_to_matrix(expression, *, local_dimension, parameters=None):
    parameters = dict(parameters or {})
    compact = _normalize_supported_onsite_expression(expression)
    terms = sparse_expand_operator_expression(compact, parameters, 1e-9)
    if not terms:
        raise ValueError("unsupported onsite operator expression")

    size = int(local_dimension)
    matrix = _zero_matrix(size)
    for term in terms:
        term_matrix = _matrix_scale(
            _label_to_onsite_matrix(term["label"], local_dimension),
            term["coefficient"],
        )
        matrix = _matrix_add(matrix, term_matrix)
    return matrix
