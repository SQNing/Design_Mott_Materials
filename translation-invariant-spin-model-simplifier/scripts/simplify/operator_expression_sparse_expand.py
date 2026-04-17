#!/usr/bin/env python3
import re
from collections import defaultdict
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from simplify.operator_expression_normalizer import normalize_operator_expression
    from simplify.operator_expression_parser import OperatorExpressionParseError
else:
    from .operator_expression_normalizer import normalize_operator_expression
    from .operator_expression_parser import OperatorExpressionParseError


_MULTIPOLE_PATTERN = re.compile(r"T\d+_[A-Za-z0-9_]+$")


def _resolve_monomial_coefficient(monomial, parameters):
    kind = monomial.get("coefficient_kind", "number")
    if kind == "number":
        return complex(monomial.get("coefficient_value", 1.0))
    if kind == "symbol":
        name = monomial.get("coefficient_name")
        if name not in parameters:
            raise OperatorExpressionParseError(f"unknown coefficient token: {name}")
        multiplier = float(monomial.get("coefficient_multiplier", 1.0))
        return complex(parameters[name]) * multiplier
    raise OperatorExpressionParseError(f"unsupported coefficient kind: {kind}")


def _expand_local_factor(label, site):
    if label in {"Sx", "Sy", "Sz"} or _MULTIPOLE_PATTERN.fullmatch(label):
        return [((label, site), 1.0 + 0.0j)]
    if label == "Sp":
        return [(("Sx", site), 1.0 + 0.0j), (("Sy", site), 0.0 + 1.0j)]
    if label == "Sm":
        return [(("Sx", site), 1.0 + 0.0j), (("Sy", site), 0.0 - 1.0j)]
    raise OperatorExpressionParseError(f"unsupported factor token: {label}@{site}")


def _real_if_close(value, tolerance):
    if abs(value.imag) <= tolerance:
        return float(value.real)
    return value


def sparse_expand_operator_expression(expression, parameters=None, tolerance=1e-9):
    try:
        monomials = normalize_operator_expression(expression)
    except OperatorExpressionParseError:
        return []

    merged = defaultdict(complex)
    parameters = dict(parameters or {})
    for monomial in monomials:
        coefficient = _resolve_monomial_coefficient(monomial, parameters)
        expanded_terms = [([], coefficient)]
        for label, site in monomial.get("factors", ()):
            local_expansion = _expand_local_factor(label, site)
            next_terms = []
            for factors, prefactor in expanded_terms:
                for factor_entry, local_coeff in local_expansion:
                    next_terms.append((factors + [factor_entry], prefactor * local_coeff))
            expanded_terms = next_terms
        for factors, prefactor in expanded_terms:
            if abs(prefactor) <= tolerance:
                continue
            label = " ".join(f"{factor_label}@{site}" for factor_label, site in factors)
            merged[label] += prefactor

    return [
        {"label": label, "coefficient": _real_if_close(coefficient, tolerance)}
        for label, coefficient in sorted(merged.items())
        if abs(coefficient) > tolerance
    ]
