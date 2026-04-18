#!/usr/bin/env python3
import re
from collections import defaultdict
from itertools import permutations
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
_PURE_IMAGINARY_I_PATTERN = re.compile(r"(?P<imag>[+\-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+\-]?\d+)?)i$")


def _resolve_scalar_token(token):
    cleaned = str(token or "").strip()
    if not cleaned:
        raise OperatorExpressionParseError("empty coefficient token")

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

    match = _PURE_IMAGINARY_I_PATTERN.fullmatch(cleaned)
    if match:
        return complex(0.0, float(match.group("imag")))

    raise OperatorExpressionParseError(f"unknown coefficient token: {cleaned}")


def _unwrap_conjugate_shorthand_token(token):
    text = str(token or "").strip()
    while True:
        match = re.fullmatch(r"\\(?:mathrm|text)\{(.+)\}", text, flags=re.IGNORECASE)
        if not match:
            break
        text = match.group(1).strip()
    return text


def _unwrap_shorthand_token(token):
    text = _unwrap_conjugate_shorthand_token(token)
    while len(text) >= 2 and text[0] == "(" and text[-1] == ")":
        depth = 0
        wrapped = True
        for index, char in enumerate(text):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth < 0:
                    wrapped = False
                    break
                if depth == 0 and index != len(text) - 1:
                    wrapped = False
                    break
        if not wrapped or depth != 0:
            break
        text = text[1:-1].strip()
    return text


def _split_trailing_plus_shorthand(expression, classifier):
    text = str(expression or "").strip()
    if not text:
        return None

    depth = {"(": 0, "[": 0, "{": 0}
    matching = {")": "(", "]": "[", "}": "{"}
    last_top_level_plus = None

    for index, char in enumerate(text):
        if char in depth:
            depth[char] += 1
        elif char in matching:
            opener = matching[char]
            depth[opener] -= 1
            if depth[opener] < 0:
                return None
        elif char == "+" and all(value == 0 for value in depth.values()):
            last_top_level_plus = index

    if any(value != 0 for value in depth.values()) or last_top_level_plus is None:
        return None

    base_expression = text[:last_top_level_plus].strip()
    trailing_token = text[last_top_level_plus + 1 :].strip()
    shorthand_kind = classifier(trailing_token)
    if not base_expression or shorthand_kind is None:
        return None
    return base_expression, shorthand_kind


def _classify_trailing_conjugate_shorthand(token):
    cleaned = re.sub(r"\s+", "", _unwrap_shorthand_token(token)).lower()
    if cleaned in {"h.c.", "h.c", "hc", "hermitianconjugate"}:
        return "hc"
    if cleaned in {"c.c.", "c.c", "cc", "complexconjugate"}:
        return "cc"
    return None


def _classify_trailing_site_swap_shorthand(token):
    cleaned = re.sub(r"\s+", "", _unwrap_shorthand_token(token)).lower()
    if cleaned in {"i<->j", "j<->i", r"i\leftrightarrowj", r"j\leftrightarrowi"}:
        return "swap_first_two_sites"
    if cleaned in {"perm.", "perm", "permutation"}:
        return "swap_first_two_sites"
    return None


def _classify_trailing_permutation_shorthand(token):
    cleaned = re.sub(r"\s+", "", _unwrap_shorthand_token(token)).lower()
    if cleaned in {
        "cyclicperm.",
        "cyclicperm",
        "cyclicpermutation",
        "cyclicpermutations",
    }:
        return "cyclic_permutations"
    if cleaned in {
        "allpermutations",
        "allpermutation",
        "allperm.",
        "allperm",
    }:
        return "all_permutations"
    return None


def split_trailing_conjugate_shorthand(expression):
    return _split_trailing_plus_shorthand(expression, _classify_trailing_conjugate_shorthand)


def split_trailing_site_swap_shorthand(expression):
    return _split_trailing_plus_shorthand(expression, _classify_trailing_site_swap_shorthand)


def split_trailing_permutation_shorthand(expression):
    return _split_trailing_plus_shorthand(expression, _classify_trailing_permutation_shorthand)


def split_outer_projection_wrapper(expression):
    text = str(expression or "").strip()
    if not text:
        return None

    prefixes = [
        ("Re", "real_part"),
        ("Im", "imaginary_part"),
        (r"\mathrm{Re}", "real_part"),
        (r"\mathrm{Im}", "imaginary_part"),
        (r"\text{Re}", "real_part"),
        (r"\text{Im}", "imaginary_part"),
        (r"\operatorname{Re}", "real_part"),
        (r"\operatorname{Im}", "imaginary_part"),
    ]

    for prefix, kind in prefixes:
        if not text.startswith(prefix):
            continue
        if len(text) <= len(prefix):
            continue
        opener = text[len(prefix)]
        if opener not in {"[", "("}:
            continue
        closer = "]" if opener == "[" else ")"
        depth = {"(": 0, "[": 0, "{": 0}
        matching = {")": "(", "]": "[", "}": "{"}
        for index in range(len(prefix), len(text)):
            char = text[index]
            if char in depth:
                depth[char] += 1
            elif char in matching:
                open_char = matching[char]
                depth[open_char] -= 1
                if depth[open_char] < 0:
                    return None
                if (
                    char == closer
                    and open_char == opener
                    and all(value == 0 for value in depth.values())
                ):
                    inner = text[len(prefix) + 1 : index].strip()
                    trailing = text[index + 1 :].strip()
                    if inner and not trailing:
                        return inner, kind
                    break
    return None


def has_special_operator_expression_shorthand(expression):
    return any(
        check(expression) is not None
        for check in (
            split_outer_projection_wrapper,
            split_trailing_conjugate_shorthand,
            split_trailing_site_swap_shorthand,
            split_trailing_permutation_shorthand,
        )
    )


def _swap_first_two_sites_in_label(label):
    factors = []
    for factor in str(label or "").split():
        match = re.fullmatch(r"(?P<name>[A-Za-z0-9_]+)@(?P<site>-?\d+)", factor)
        if not match:
            raise OperatorExpressionParseError(f"unsupported factor label in shorthand expansion: {factor}")
        factors.append((match.group("name"), int(match.group("site"))))

    support = sorted({site for _, site in factors})
    if len(support) < 2:
        return " ".join(f"{name}@{site}" for name, site in factors)

    left_site, right_site = support[:2]
    swapped = []
    for name, site in factors:
        if site == left_site:
            swapped_site = right_site
        elif site == right_site:
            swapped_site = left_site
        else:
            swapped_site = site
        swapped.append((name, swapped_site))

    swapped.sort(key=lambda item: (item[1], item[0]))
    return " ".join(f"{name}@{site}" for name, site in swapped)


def _permuted_label(label, site_mapping):
    factors = []
    for factor in str(label or "").split():
        match = re.fullmatch(r"(?P<name>[A-Za-z0-9_]+)@(?P<site>-?\d+)", factor)
        if not match:
            raise OperatorExpressionParseError(f"unsupported factor label in shorthand expansion: {factor}")
        site = int(match.group("site"))
        factors.append((match.group("name"), site_mapping.get(site, site)))
    return " ".join(f"{name}@{site}" for name, site in factors)


def _support_permutations(label, kind):
    support = []
    for factor in str(label or "").split():
        match = re.fullmatch(r"(?P<name>[A-Za-z0-9_]+)@(?P<site>-?\d+)", factor)
        if not match:
            raise OperatorExpressionParseError(f"unsupported factor label in shorthand expansion: {factor}")
        site = int(match.group("site"))
        if site not in support:
            support.append(site)

    if len(support) < 2:
        return [{site: site for site in support}]

    if kind == "cyclic_permutations":
        mappings = []
        for shift in range(len(support)):
            rotated = support[shift:] + support[:shift]
            mappings.append(dict(zip(support, rotated)))
        return mappings

    if kind == "all_permutations":
        return [dict(zip(support, ordering)) for ordering in permutations(support)]

    raise OperatorExpressionParseError(f"unsupported permutation shorthand kind: {kind}")


def _resolve_monomial_coefficient(monomial, parameters):
    kind = monomial.get("coefficient_kind", "number")
    if kind == "number":
        return complex(monomial.get("coefficient_value", 1.0))
    if kind == "symbol":
        name = monomial.get("coefficient_name")
        multiplier = float(monomial.get("coefficient_multiplier", 1.0))
        if name in parameters:
            return complex(parameters[name]) * multiplier
        return _resolve_scalar_token(name) * multiplier
    if kind == "symbol_product":
        value = complex(float(monomial.get("coefficient_multiplier", 1.0)))
        for name in monomial.get("coefficient_names", ()):
            if name in parameters:
                value *= complex(parameters[name])
            else:
                value *= _resolve_scalar_token(name)
        return value
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
    projection_wrapper = split_outer_projection_wrapper(expression)
    if projection_wrapper is not None:
        inner_expression, projection_kind = projection_wrapper
        inner_terms = sparse_expand_operator_expression(inner_expression, parameters, tolerance)
        projected = []
        for term in inner_terms:
            coefficient = complex(term["coefficient"])
            value = coefficient.real if projection_kind == "real_part" else coefficient.imag
            if abs(value) > tolerance:
                projected.append({"label": term["label"], "coefficient": float(value)})
        return projected

    shorthand = split_trailing_conjugate_shorthand(expression)
    if shorthand is not None:
        base_expression, _ = shorthand
        base_terms = sparse_expand_operator_expression(base_expression, parameters, tolerance)
        merged = defaultdict(complex)
        for term in base_terms:
            label = term["label"]
            coefficient = complex(term["coefficient"])
            merged[label] += coefficient
            merged[label] += coefficient.conjugate()
        return [
            {"label": label, "coefficient": _real_if_close(coefficient, tolerance)}
            for label, coefficient in sorted(merged.items())
            if abs(coefficient) > tolerance
        ]

    site_swap_shorthand = split_trailing_site_swap_shorthand(expression)
    if site_swap_shorthand is not None:
        base_expression, _ = site_swap_shorthand
        base_terms = sparse_expand_operator_expression(base_expression, parameters, tolerance)
        merged = defaultdict(complex)
        for term in base_terms:
            label = str(term["label"])
            coefficient = complex(term["coefficient"])
            merged[label] += coefficient
            merged[_swap_first_two_sites_in_label(label)] += coefficient
        return [
            {"label": label, "coefficient": _real_if_close(coefficient, tolerance)}
            for label, coefficient in sorted(merged.items())
            if abs(coefficient) > tolerance
        ]

    permutation_shorthand = split_trailing_permutation_shorthand(expression)
    if permutation_shorthand is not None:
        base_expression, permutation_kind = permutation_shorthand
        base_terms = sparse_expand_operator_expression(base_expression, parameters, tolerance)
        merged = defaultdict(complex)
        for term in base_terms:
            label = str(term["label"])
            coefficient = complex(term["coefficient"])
            for site_mapping in _support_permutations(label, permutation_kind):
                merged[_permuted_label(label, site_mapping)] += coefficient
        return [
            {"label": label, "coefficient": _real_if_close(coefficient, tolerance)}
            for label, coefficient in sorted(merged.items())
            if abs(coefficient) > tolerance
        ]

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
