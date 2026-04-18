#!/usr/bin/env python3
import re
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from simplify.operator_expression_parser import parse_operator_expression
else:
    from .operator_expression_parser import parse_operator_expression


_LATEX_FACTOR_PATTERN = re.compile(r"S_(?P<site>[A-Za-z])\^(?P<component>[xyz\+\-])")
_LATEX_COMPONENT_MAP = {
    "x": "Sx",
    "y": "Sy",
    "z": "Sz",
    "+": "Sp",
    "-": "Sm",
}


def _latex_to_compact(expression):
    site_order = {}

    def replace_factor(match):
        site_label = match.group("site")
        if site_label not in site_order:
            site_order[site_label] = len(site_order)
        component = match.group("component")
        return f" {_LATEX_COMPONENT_MAP[component]}@{site_order[site_label]} "

    compact = re.sub(r"\s+", " ", str(expression or "").strip())
    compact = compact.replace(r"\left", "").replace(r"\right", "")
    compact = _LATEX_FACTOR_PATTERN.sub(replace_factor, compact)
    compact = re.sub(r"(?<=[A-Za-z0-9_}])\(", " (", compact)
    compact = re.sub(r"\)\(", ") (", compact)
    compact = re.sub(r"\)(?=[A-Za-z])", ") ", compact)
    return re.sub(r"\s+", " ", compact).strip()


def _number_coefficient(value):
    return {
        "coefficient_kind": "number",
        "coefficient_value": float(value),
    }


def _symbol_coefficient(name, multiplier=1.0):
    return {
        "coefficient_kind": "symbol",
        "coefficient_name": str(name),
        "coefficient_multiplier": float(multiplier),
    }


def _symbol_product_coefficient(names, multiplier=1.0):
    return {
        "coefficient_kind": "symbol_product",
        "coefficient_names": tuple(str(name) for name in names),
        "coefficient_multiplier": float(multiplier),
    }


def _combine_coefficients(left, right):
    left_kind = left.get("coefficient_kind", "number")
    right_kind = right.get("coefficient_kind", "number")

    if left_kind == "number" and right_kind == "number":
        return _number_coefficient(
            float(left.get("coefficient_value", 1.0)) * float(right.get("coefficient_value", 1.0))
        )

    if left_kind == "symbol" and right_kind == "number":
        return _symbol_coefficient(
            left.get("coefficient_name"),
            float(left.get("coefficient_multiplier", 1.0)) * float(right.get("coefficient_value", 1.0)),
        )

    if left_kind == "number" and right_kind == "symbol":
        return _symbol_coefficient(
            right.get("coefficient_name"),
            float(left.get("coefficient_value", 1.0)) * float(right.get("coefficient_multiplier", 1.0)),
        )

    if left_kind == "symbol" and right_kind == "symbol":
        return _symbol_product_coefficient(
            (left.get("coefficient_name"), right.get("coefficient_name")),
            float(left.get("coefficient_multiplier", 1.0)) * float(right.get("coefficient_multiplier", 1.0)),
        )

    if left_kind == "symbol_product" and right_kind == "number":
        return _symbol_product_coefficient(
            left.get("coefficient_names", ()),
            float(left.get("coefficient_multiplier", 1.0)) * float(right.get("coefficient_value", 1.0)),
        )

    if left_kind == "number" and right_kind == "symbol_product":
        return _symbol_product_coefficient(
            right.get("coefficient_names", ()),
            float(left.get("coefficient_value", 1.0)) * float(right.get("coefficient_multiplier", 1.0)),
        )

    if left_kind == "symbol_product" and right_kind == "symbol":
        return _symbol_product_coefficient(
            tuple(left.get("coefficient_names", ())) + (right.get("coefficient_name"),),
            float(left.get("coefficient_multiplier", 1.0)) * float(right.get("coefficient_multiplier", 1.0)),
        )

    if left_kind == "symbol" and right_kind == "symbol_product":
        return _symbol_product_coefficient(
            (left.get("coefficient_name"),) + tuple(right.get("coefficient_names", ())),
            float(left.get("coefficient_multiplier", 1.0)) * float(right.get("coefficient_multiplier", 1.0)),
        )

    if left_kind == "symbol_product" and right_kind == "symbol_product":
        return _symbol_product_coefficient(
            tuple(left.get("coefficient_names", ())) + tuple(right.get("coefficient_names", ())),
            float(left.get("coefficient_multiplier", 1.0)) * float(right.get("coefficient_multiplier", 1.0)),
        )

    raise ValueError(f"unsupported symbolic coefficient product: {left_kind} * {right_kind}")


def _normalize_factor_node(ast_node):
    return [
        {
            **_number_coefficient(1.0),
            "factors": ((ast_node.label, ast_node.site),),
        }
    ]


def _normalize_ast_node(ast_node):
    if ast_node.kind == "factor":
        return _normalize_factor_node(ast_node)

    if ast_node.kind == "sum":
        monomials = []
        for term in ast_node.terms:
            monomials.extend(_normalize_ast_node(term))
        return monomials

    if ast_node.kind == "scaled":
        coefficient = _number_coefficient(1.0)
        if ast_node.coefficient.kind == "number":
            coefficient = _number_coefficient(ast_node.coefficient.value)
        else:
            coefficient = _symbol_coefficient(ast_node.coefficient.name, ast_node.coefficient.multiplier)
        monomials = []
        for monomial in _normalize_ast_node(ast_node.expression):
            combined = _combine_coefficients(coefficient, monomial)
            monomials.append({**combined, "factors": monomial["factors"]})
        return monomials

    if ast_node.kind == "product":
        monomials = [{**_number_coefficient(1.0), "factors": ()}]
        for factor in ast_node.factors:
            factor_monomials = _normalize_ast_node(factor)
            distributed = []
            for left in monomials:
                for right in factor_monomials:
                    combined = _combine_coefficients(left, right)
                    distributed.append(
                        {
                            **combined,
                            "factors": tuple(left["factors"]) + tuple(right["factors"]),
                        }
                    )
            monomials = distributed
        return monomials

    raise ValueError(f"unsupported AST node kind: {ast_node.kind}")


def normalize_operator_expression(expression):
    compact = _latex_to_compact(expression)
    ast = parse_operator_expression(compact)
    return _normalize_ast_node(ast)
