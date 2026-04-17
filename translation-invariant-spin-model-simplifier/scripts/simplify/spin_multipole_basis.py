#!/usr/bin/env python3
from __future__ import annotations

import math
from fractions import Fraction
from itertools import product


def _parse_half_integer(value, *, allow_negative):
    if isinstance(value, Fraction):
        parsed = value
    elif isinstance(value, int):
        parsed = Fraction(value, 1)
    elif isinstance(value, float):
        parsed = Fraction(value).limit_denominator(2)
    elif isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must be non-empty")
        parsed = Fraction(cleaned)
    else:
        raise ValueError(f"unsupported value type: {type(value).__name__}")

    if not allow_negative and parsed < 0:
        raise ValueError("spin value must be non-negative")
    if parsed.denominator not in {1, 2}:
        raise ValueError("value must be integer or half-integer")
    doubled = parsed * 2
    if doubled.denominator != 1:
        raise ValueError("value must be integer or half-integer")
    return parsed


def parse_spin_value(value):
    return _parse_half_integer(value, allow_negative=False)


def _parse_magnetic_value(value):
    return _parse_half_integer(value, allow_negative=True)


def local_dimension_for_spin(spin):
    parsed = parse_spin_value(spin)
    return int(parsed * 2 + 1)


def supported_ranks(spin):
    parsed = parse_spin_value(spin)
    return list(range(0, int(parsed * 2) + 1))


def _magnetic_quantum_numbers(spin):
    doubled = int(parse_spin_value(spin) * 2)
    return [Fraction(value, 2) for value in range(-doubled, doubled + 1, 2)]


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


def _matrix_trace_conjugate_product(left, right):
    total = 0.0 + 0.0j
    for row in range(len(left)):
        for col in range(len(left[row])):
            total += complex(left[row][col]).conjugate() * right[row][col]
    return total


def _real_if_close(value, tolerance=1e-12):
    if abs(complex(value).imag) <= tolerance:
        return float(complex(value).real)
    return complex(value)


def _factorial(number):
    return math.gamma(float(number) + 1.0)


def _triangle_condition(j1, j2, j3):
    return abs(j1 - j2) <= j3 <= j1 + j2


def _wigner_3j(j1, j2, j3, m1, m2, m3):
    j1 = parse_spin_value(j1)
    j2 = parse_spin_value(j2)
    j3 = parse_spin_value(j3)
    m1 = _parse_magnetic_value(m1)
    m2 = _parse_magnetic_value(m2)
    m3 = _parse_magnetic_value(m3)

    if m1 + m2 + m3 != 0:
        return 0.0
    if not _triangle_condition(j1, j2, j3):
        return 0.0
    if any(abs(m) > j for m, j in ((m1, j1), (m2, j2), (m3, j3))):
        return 0.0

    phase_exponent = int(j1 - j2 - m3)
    delta = (
        _factorial(j1 + j2 - j3)
        * _factorial(j1 - j2 + j3)
        * _factorial(-j1 + j2 + j3)
        / _factorial(j1 + j2 + j3 + 1)
    )
    prefactor = ((-1) ** phase_exponent) * math.sqrt(float(delta))

    norm = math.sqrt(
        float(
            _factorial(j1 + m1)
            * _factorial(j1 - m1)
            * _factorial(j2 + m2)
            * _factorial(j2 - m2)
            * _factorial(j3 + m3)
            * _factorial(j3 - m3)
        )
    )

    lower = max(
        0,
        int(j2 - j3 - m1),
        int(j1 - j3 + m2),
    )
    upper = min(
        int(j1 + j2 - j3),
        int(j1 - m1),
        int(j2 + m2),
    )

    summation = 0.0
    for z in range(lower, upper + 1):
        denominator = (
            _factorial(z)
            * _factorial(j1 + j2 - j3 - z)
            * _factorial(j1 - m1 - z)
            * _factorial(j2 + m2 - z)
            * _factorial(j3 - j2 + m1 + z)
            * _factorial(j3 - j1 - m2 + z)
        )
        summation += ((-1) ** z) / float(denominator)

    return prefactor * norm * summation


def _clebsch_gordan(j1, m1, j2, m2, j, m):
    j1 = parse_spin_value(j1)
    j2 = parse_spin_value(j2)
    j = parse_spin_value(j)
    m1 = _parse_magnetic_value(m1)
    m2 = _parse_magnetic_value(m2)
    m = _parse_magnetic_value(m)
    if m1 + m2 != m:
        return 0.0
    phase = (-1) ** int(j1 - j2 + m)
    return phase * math.sqrt(float(2 * j + 1)) * _wigner_3j(j1, j2, j, m1, m2, -m)


def _spherical_tensor_basis(spin):
    spin = parse_spin_value(spin)
    states = _magnetic_quantum_numbers(spin)
    size = len(states)
    basis = []
    norm_factor = math.sqrt(float(2 * spin + 1))

    for rank in supported_ranks(spin):
        for q in range(-rank, rank + 1):
            matrix = _zero_matrix(size)
            for row, m_prime in enumerate(states):
                for col, m in enumerate(states):
                    coefficient = _clebsch_gordan(spin, m, Fraction(rank, 1), Fraction(q, 1), spin, m_prime)
                    matrix[row][col] = coefficient / norm_factor
            basis.append({"rank": rank, "q": q, "matrix": matrix})
    return basis


def _component_name(rank, q):
    if rank == 0:
        return "0"
    if rank == 1:
        if q == 0:
            return "z"
        if q == 1:
            return "x"
        if q == -1:
            return "y"
    if q == 0:
        return "0"
    return f"c{q}" if q > 0 else f"s{abs(q)}"


def _combine_tesseral(rank, positive, negative):
    if rank == 1:
        x_matrix = _matrix_scale(
            _matrix_add(_matrix_scale(negative["matrix"], -1.0), positive["matrix"]),
            1.0 / math.sqrt(2.0),
        )
        y_matrix = _matrix_scale(
            _matrix_add(positive["matrix"], negative["matrix"]),
            (0.0 - 1.0j) / math.sqrt(2.0),
        )
        return [
            {"rank": rank, "component": "x", "label": "T1_x", "matrix": x_matrix},
            {"rank": rank, "component": "y", "label": "T1_y", "matrix": y_matrix},
        ]

    cosine = _matrix_scale(
        _matrix_add(
            positive["matrix"],
            _matrix_scale(negative["matrix"], ((-1) ** positive["q"])),
        ),
        1.0 / math.sqrt(2.0),
    )
    sine = _matrix_scale(
        _matrix_add(
            positive["matrix"],
            _matrix_scale(negative["matrix"], -((-1) ** positive["q"])),
        ),
        (0.0 - 1.0j) / math.sqrt(2.0),
    )
    q = positive["q"]
    return [
        {"rank": rank, "component": f"c{q}", "label": f"T{rank}_c{q}", "matrix": cosine},
        {"rank": rank, "component": f"s{q}", "label": f"T{rank}_s{q}", "matrix": sine},
    ]


def build_spin_multipole_basis(spin):
    spherical = _spherical_tensor_basis(spin)
    by_rank = {}
    for element in spherical:
        by_rank.setdefault(element["rank"], {})[element["q"]] = element

    basis = []
    for rank in sorted(by_rank):
        rank_elements = by_rank[rank]
        zero = rank_elements.get(0)
        if zero is not None:
            basis.append(
                {
                    "rank": rank,
                    "component": _component_name(rank, 0),
                    "label": f"T{rank}_{_component_name(rank, 0)}",
                    "matrix": zero["matrix"],
                }
            )
        for q in range(1, rank + 1):
            basis.extend(_combine_tesseral(rank, rank_elements[q], rank_elements[-q]))

    expected_dimension = local_dimension_for_spin(spin) ** 2
    if len(basis) != expected_dimension:
        raise ValueError(
            f"constructed basis has dimension {len(basis)}, expected {expected_dimension} for spin {spin}"
        )

    for element in basis:
        norm = _matrix_trace_conjugate_product(element["matrix"], element["matrix"])
        if abs(norm - 1.0) > 1e-8:
            element["matrix"] = _matrix_scale(element["matrix"], 1.0 / math.sqrt(float(norm.real)))

    return basis


def product_spin_multipole_basis(spin, support):
    support = list(support)
    local_basis = build_spin_multipole_basis(spin)
    labels = []
    operators = []

    for elements in product(local_basis, repeat=len(support)):
        label_parts = []
        operator = [[1.0 + 0.0j]]
        for site, element in zip(support, elements):
            if element["rank"] != 0:
                label_parts.append(f"{element['label']}@{site}")
            operator = _kron(operator, element["matrix"])
        labels.append(" ".join(label_parts) or "identity")
        operators.append(operator)

    return labels, operators
