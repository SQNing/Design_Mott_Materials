#!/usr/bin/env python3
import re
from fractions import Fraction


def _infer_spin_from_local_dimension(local_dimension):
    local_dimension = int(local_dimension)
    if local_dimension <= 0:
        raise ValueError("local Hilbert-space dimension must be positive")
    return Fraction(local_dimension - 1, 2)


def _zero_matrix(size):
    return [[0.0 + 0.0j for _ in range(size)] for _ in range(size)]


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


def compile_onsite_term_to_matrix(expression, *, local_dimension, parameters=None):
    parameters = dict(parameters or {})
    compact = re.sub(r"\s+", "", str(expression or ""))
    match = re.fullmatch(r"(?P<coeff>[A-Za-z0-9_{}^\\.+\-']+)\*\(Sz@0\)\^2", compact)
    if not match:
        raise ValueError("unsupported onsite operator expression")

    coeff_token = match.group("coeff")
    try:
        coefficient = complex(float(coeff_token))
    except ValueError:
        if coeff_token not in parameters:
            raise ValueError(f"unknown onsite coefficient token: {coeff_token}")
        coefficient = complex(parameters[coeff_token])

    sz = _spin_operator_matrices(local_dimension)["Sz"]
    return _matrix_scale(_matrix_multiply(sz, sz), coefficient)
