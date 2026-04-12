#!/usr/bin/env python3
import re


def _extract_number(text, pattern):
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return float(match.group(1))


def _extract_cell_parameters(text):
    mapping = {
        "a": r"\ba\s*=\s*([-+]?\d*\.?\d+)",
        "b": r"\bb\s*=\s*([-+]?\d*\.?\d+)",
        "c": r"\bc\s*=\s*([-+]?\d*\.?\d+)",
        "alpha": r"\balpha\s*=\s*([-+]?\d*\.?\d+)",
        "beta": r"\bbeta\s*=\s*([-+]?\d*\.?\d+)",
        "gamma": r"\bgamma\s*=\s*([-+]?\d*\.?\d+)",
    }
    values = {}
    for key, pattern in mapping.items():
        value = _extract_number(text, pattern)
        if value is not None:
            values[key] = value
    return values


def _infer_lattice_kind(text):
    lowered = text.lower()
    if "orthorhombic" in lowered:
        return "orthorhombic"
    if "rectangular" in lowered:
        return "rectangular"
    if "square" in lowered:
        return "square"
    if "chain" in lowered:
        return "chain"
    return "unspecified"


def _extract_positions(text):
    positions = []
    for match in re.finditer(
        r"(?:atom\d+|atom\s*\d+|one magnetic atom at|magnetic atom at)\s*[:=]?\s*\(\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*\)",
        text,
        flags=re.IGNORECASE,
    ):
        positions.append([float(match.group(1)), float(match.group(2)), float(match.group(3))])
    return positions


def _extract_explicit_shell_map(text):
    explicit = {}
    normalized = re.sub(r"\s+", " ", text)
    for match in re.finditer(
        r"\b(J\d+)\s*(?:and\s*(J\d+)\s*)?defined by\s*(first|second|third|\d+)(?:\s*and\s*(first|second|third|\d+))?\s*distance shells",
        normalized,
        flags=re.IGNORECASE,
    ):
        labels = [match.group(1)]
        if match.group(2):
            labels.append(match.group(2))
        ordinals = [match.group(3)]
        if match.group(4):
            ordinals.append(match.group(4))
        if len(labels) == len(ordinals):
            for label, ordinal in zip(labels, ordinals):
                explicit[label.upper()] = _ordinal_to_index(ordinal)
    simple = re.search(r"\bJ1\s*/\s*J2\s*by\s*first\s*/\s*second\s*distance shells\b", normalized, flags=re.IGNORECASE)
    if simple:
        explicit["J1"] = 1
        explicit["J2"] = 2
    return explicit


def _ordinal_to_index(token):
    lowered = str(token).lower()
    mapping = {"first": 1, "second": 2, "third": 3}
    if lowered in mapping:
        return mapping[lowered]
    return int(lowered)


def _extract_solver_preferences(text):
    lowered = text.lower()
    explicit_lt = re.search(r"(?<![a-z0-9])lt(?![a-z0-9])", lowered) or re.search(r"luttinger[\s-]*tisza", lowered)
    return {
        "classical": "luttinger-tisza" if explicit_lt else None,
        "lswt": "lswt" in lowered or "spin wave" in lowered,
    }


def _extract_parameter_mentions(text):
    labels = []
    for match in re.finditer(r"\b(J\d+)\b", text, flags=re.IGNORECASE):
        label = match.group(1).upper()
        if label not in labels:
            labels.append(label)
    return labels


def _lattice_ambiguity(text):
    lowered = (text or "").lower()
    if "hexagonal lattice" in lowered:
        return {
            "id": "lattice_kind",
            "prompt": (
                "You described a hexagonal lattice. Should this be interpreted as a honeycomb spin lattice "
                "or a triangular Bravais lattice?"
            ),
            "options": ["honeycomb", "triangular", "custom"],
        }
    return None


def _exchange_mapping_ambiguity(parameter_mentions, exchange_shell_map):
    if parameter_mentions and not exchange_shell_map:
        return {
            "id": "exchange_mapping",
            "prompt": (
                "J labels were detected, but the text does not say whether they follow distance shells "
                "or user-defined exchange paths. Please specify the mapping, for example 'J1/J2 by "
                "first/second distance shells'."
            ),
        }
    return None


def detect_controlled_natural_language_ambiguity(text):
    parameter_mentions = _extract_parameter_mentions(text)
    exchange_shell_map = _extract_explicit_shell_map(text)
    lattice_question = _lattice_ambiguity(text)
    mapping_question = _exchange_mapping_ambiguity(parameter_mentions, exchange_shell_map)

    if lattice_question and mapping_question:
        return {
            "status": "needs_input",
            "question": {
                "id": "lattice_and_exchange_mapping",
                "prompt": (
                    "You described a hexagonal lattice and used J labels without specifying their mapping. "
                    "Please clarify whether the lattice should be treated as honeycomb, triangular, or custom, "
                    "and also specify whether J1/J2 follow distance shells or user-defined exchange paths "
                    "(for example 'J1/J2 by first/second distance shells')."
                ),
                "options": lattice_question["options"],
            },
        }
    if lattice_question:
        return {"status": "needs_input", "question": lattice_question}
    if mapping_question:
        return {"status": "needs_input", "question": mapping_question}
    return None


def parse_controlled_natural_language(text):
    text = (text or "").strip()
    if not text:
        return {
            "status": "needs_input",
            "question": {"id": "description", "prompt": "Please provide a non-empty controlled natural-language model description."},
        }

    ambiguity = detect_controlled_natural_language_ambiguity(text)
    if ambiguity is not None:
        return ambiguity

    cell_parameters = _extract_cell_parameters(text)
    positions = _extract_positions(text)
    exchange_shell_map = _extract_explicit_shell_map(text)
    solver_preferences = _extract_solver_preferences(text)

    lattice = {
        "kind": _infer_lattice_kind(text),
        "cell_parameters": cell_parameters,
        "positions": positions,
    }
    return {
        "status": "ok",
        "lattice": lattice,
        "exchange_mapping": {
            "mode": "distance-shells" if exchange_shell_map else None,
            "shell_map": exchange_shell_map,
        },
        "solver_preferences": solver_preferences,
        "source_text": text,
    }
