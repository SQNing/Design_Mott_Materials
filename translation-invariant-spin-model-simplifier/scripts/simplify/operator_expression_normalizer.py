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
        return f"{_LATEX_COMPONENT_MAP[component]}@{site_order[site_label]}"

    compact = re.sub(r"\s+", " ", str(expression or "").strip())
    return _LATEX_FACTOR_PATTERN.sub(replace_factor, compact)


def _normalize_ast_node(ast_node):
    if ast_node.kind == "sum":
        monomials = []
        for term in ast_node.terms:
            monomials.extend(_normalize_ast_node(term))
        return monomials

    coefficient = {
        "coefficient_kind": "number",
        "coefficient_value": 1.0,
    }
    product = ast_node
    if ast_node.kind == "scaled":
        product = ast_node.expression
        if ast_node.coefficient.kind == "number":
            coefficient = {
                "coefficient_kind": "number",
                "coefficient_value": ast_node.coefficient.value,
            }
        else:
            coefficient = {
                "coefficient_kind": "symbol",
                "coefficient_name": ast_node.coefficient.name,
                "coefficient_multiplier": ast_node.coefficient.multiplier,
            }

    return [
        {
            **coefficient,
            "factors": tuple((factor.label, factor.site) for factor in product.factors),
        }
    ]


def normalize_operator_expression(expression):
    compact = _latex_to_compact(expression)
    ast = parse_operator_expression(compact)
    return _normalize_ast_node(ast)
