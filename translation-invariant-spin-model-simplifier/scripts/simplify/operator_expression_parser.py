#!/usr/bin/env python3
import re
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from simplify.operator_expression_ast import (
        FactorNode,
        NumberNode,
        ProductNode,
        ScaledNode,
        SumNode,
        SymbolNode,
    )
else:
    from .operator_expression_ast import (
        FactorNode,
        NumberNode,
        ProductNode,
        ScaledNode,
        SumNode,
        SymbolNode,
    )


class OperatorExpressionParseError(ValueError):
    pass


_FACTOR_PATTERN = re.compile(r"(?P<label>[A-Za-z][A-Za-z0-9_]*)@(?P<site>-?\d+)$")
_SYMBOL_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_]*$")
_LATEX_SYMBOL_PATTERN = re.compile(
    r"(?:\\?[A-Za-z][A-Za-z0-9_]*)(?:_\{[^}]+\}|_[A-Za-z0-9]+)?(?:\^\{[^}]+\}|\^[A-Za-z0-9]+)?$"
)
_COMPLEX_LITERAL_PATTERN = re.compile(
    r"[+\-]?(?:(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+\-]?\d+)?)?[ij]$"
)


def _split_top_level_terms(expression):
    terms = []
    current = []
    sign = 1
    at_term_start = True
    depth = {"(": 0, "[": 0, "{": 0}
    matching = {")": "(", "]": "[", "}": "{"}

    for char in expression:
        if char in depth:
            depth[char] += 1
        elif char in matching:
            opener = matching[char]
            depth[opener] -= 1
            if depth[opener] < 0:
                raise OperatorExpressionParseError("unbalanced closing delimiter")

        top_level = all(value == 0 for value in depth.values())
        if top_level and char in "+-":
            if at_term_start:
                sign = 1 if char == "+" else -1
                continue
            term = "".join(current).strip()
            if not term:
                raise OperatorExpressionParseError("empty term in expression")
            terms.append((sign, term))
            current = []
            sign = 1 if char == "+" else -1
            at_term_start = True
            continue

        current.append(char)
        if not char.isspace():
            at_term_start = False

    if any(value != 0 for value in depth.values()):
        raise OperatorExpressionParseError("unbalanced delimiter in expression")

    term = "".join(current).strip()
    if not term:
        raise OperatorExpressionParseError("empty operator expression")
    terms.append((sign, term))
    return terms


def _parse_coefficient(token, sign):
    cleaned = token.strip()
    if not cleaned:
        raise OperatorExpressionParseError("empty coefficient token")
    try:
        return NumberNode(float(cleaned) * sign)
    except ValueError:
        pass
    if _COMPLEX_LITERAL_PATTERN.fullmatch(cleaned):
        return SymbolNode(name=cleaned, multiplier=float(sign))
    if not (_SYMBOL_PATTERN.fullmatch(cleaned) or _LATEX_SYMBOL_PATTERN.fullmatch(cleaned)):
        raise OperatorExpressionParseError(f"unsupported coefficient token: {cleaned}")
    return SymbolNode(name=cleaned, multiplier=float(sign))


def _parse_factor(token):
    match = _FACTOR_PATTERN.fullmatch(token)
    if not match:
        raise OperatorExpressionParseError(f"unsupported factor token: {token}")
    return FactorNode(label=match.group("label"), site=int(match.group("site")))


def _is_wrapped_group(token):
    text = str(token or "").strip()
    if len(text) < 2 or text[0] != "(" or text[-1] != ")":
        return False
    depth = 0
    for index, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                return False
            if depth == 0 and index != len(text) - 1:
                return False
    return depth == 0


def _split_product_items(token_string):
    items = []
    current = []
    depth = {"(": 0, "[": 0, "{": 0}
    matching = {")": "(", "]": "[", "}": "{"}

    for char in token_string:
        if char in depth:
            depth[char] += 1
        elif char in matching:
            opener = matching[char]
            depth[opener] -= 1
            if depth[opener] < 0:
                raise OperatorExpressionParseError("unbalanced closing delimiter")

        if char.isspace() and all(value == 0 for value in depth.values()):
            item = "".join(current).strip()
            if item:
                items.append(item)
            current = []
            continue
        current.append(char)

    if any(value != 0 for value in depth.values()):
        raise OperatorExpressionParseError("unbalanced delimiter in operator product")

    item = "".join(current).strip()
    if item:
        items.append(item)
    return items


def _split_top_level_multiplication(token):
    text = str(token or "").strip()
    depth = {"(": 0, "[": 0, "{": 0}
    matching = {")": "(", "]": "[", "}": "{"}

    for index, char in enumerate(text):
        if char in depth:
            depth[char] += 1
        elif char in matching:
            opener = matching[char]
            depth[opener] -= 1
            if depth[opener] < 0:
                raise OperatorExpressionParseError("unbalanced closing delimiter")
        elif char == "*" and all(value == 0 for value in depth.values()):
            return text[:index], text[index + 1 :]

    if any(value != 0 for value in depth.values()):
        raise OperatorExpressionParseError("unbalanced delimiter")
    return None


def _parse_product_item(token):
    cleaned = str(token or "").strip()
    if _is_wrapped_group(cleaned):
        return parse_operator_expression(cleaned[1:-1].strip())
    return _parse_factor(cleaned)


def _parse_product(token_string):
    pieces = _split_product_items(token_string)
    if not pieces:
        raise OperatorExpressionParseError("operator product cannot be empty")
    return ProductNode(tuple(_parse_product_item(piece) for piece in pieces))


def _parse_term(sign, token):
    coefficient_token = None
    factor_token = token
    top_level_multiplication = _split_top_level_multiplication(token)
    if top_level_multiplication is not None:
        coefficient_token, factor_token = top_level_multiplication
    else:
        pieces = _split_product_items(token)
        if len(pieces) >= 2 and not _FACTOR_PATTERN.fullmatch(pieces[0]) and not _is_wrapped_group(pieces[0]) and all(
            _FACTOR_PATTERN.fullmatch(piece) or _is_wrapped_group(piece) for piece in pieces[1:]
        ):
            coefficient_token = pieces[0]
            factor_token = " ".join(pieces[1:])
    product = _parse_product(factor_token.strip())
    if coefficient_token is None:
        if sign == 1:
            return product
        return ScaledNode(coefficient=NumberNode(-1.0), expression=product)
    coefficient = _parse_coefficient(coefficient_token, sign)
    return ScaledNode(coefficient=coefficient, expression=product)


def parse_operator_expression(expression):
    text = str(expression or "").strip()
    if not text:
        raise OperatorExpressionParseError("operator expression cannot be empty")
    terms = tuple(_parse_term(sign, token) for sign, token in _split_top_level_terms(text))
    if len(terms) == 1:
        return terms[0]
    return SumNode(terms=terms)
