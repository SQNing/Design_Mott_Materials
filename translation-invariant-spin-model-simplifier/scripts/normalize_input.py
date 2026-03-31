#!/usr/bin/env python3
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from collections.abc import Iterable
from pathlib import Path

from natural_language_parser import parse_controlled_natural_language


DEFAULT_TIMEOUTS = {
    "simplification_seconds": 600,
    "projection_seconds": 300,
    "classical_solver_seconds": 600,
}

SUPPORTED_REPRESENTATIONS = {"operator", "matrix", "natural_language"}


def _normalize_support(support):
    if isinstance(support, (str, bytes)) or not isinstance(support, Iterable):
        raise ValueError("support must be a sequence of integers")
    normalized = []
    for item in support:
        if isinstance(item, bool) or not isinstance(item, int):
            raise ValueError("support must contain integers only")
        normalized.append(item)
    return normalized


def _require_representation_value(payload, representation):
    field_map = {
        "operator": "expression",
        "matrix": "matrix",
        "natural_language": "description",
    }
    field = field_map[representation]
    if field not in payload:
        raise ValueError(f"{representation} payload requires {field}")
    value = payload.get(field)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            raise ValueError(f"{representation} payload requires non-empty {field}")
        return value
    if value is None:
        raise ValueError(f"{representation} payload requires non-empty {field}")
    if hasattr(value, "__len__") and len(value) == 0:
        raise ValueError(f"{representation} payload requires non-empty {field}")
    return value


def _infer_local_dimension_from_text(text, default=2):
    lowered = (text or "").lower()
    if re.search(r"\bspin[-\s]*one[-\s]*half\b", lowered):
        return 2
    fraction_match = re.search(r"\bspin(?:[-\s]+)?(?P<num>\d+)\s*/\s*(?P<den>\d+)\b", lowered)
    if fraction_match:
        if fraction_match.group("den") != "2":
            raise ValueError("unsupported explicit spin fraction")
        return int(fraction_match.group("num")) + 1
    match = re.search(r"\bspin(?:[-\s]+)?(?P<spin>\d+)\b", lowered)
    if match:
        return int(match.group("spin")) * 2 + 1
    return default


def _merge_lattice_fields(base_lattice, parsed_lattice):
    merged = dict(base_lattice or {})
    parsed_lattice = parsed_lattice or {}

    parsed_kind = parsed_lattice.get("kind")
    if parsed_kind and parsed_kind != "unspecified":
        merged["kind"] = parsed_kind

    for key in ("dimension", "unit_cell", "sublattices", "lattice_vectors"):
        value = parsed_lattice.get(key)
        if value not in (None, [], {}):
            merged[key] = value

    parsed_positions = parsed_lattice.get("positions")
    if parsed_positions:
        merged["positions"] = parsed_positions

    parsed_cell_parameters = parsed_lattice.get("cell_parameters")
    if parsed_cell_parameters:
        base_cell_parameters = dict(merged.get("cell_parameters", {}))
        base_cell_parameters.update(parsed_cell_parameters)
        merged["cell_parameters"] = base_cell_parameters

    return merged


def normalize_freeform_text(text):
    text = (text or "").strip()
    if not text:
        raise ValueError("freeform input must be non-empty")
    parsed = parse_controlled_natural_language(text)
    lattice = {"kind": "unspecified", "dimension": None, "unit_cell": []}
    exchange_mapping = {"mode": None, "shell_map": {}}
    solver_preferences = {"classical": None, "lswt": False}
    interaction = {"status": "ok"}
    if parsed.get("status") == "ok":
        lattice.update(parsed.get("lattice", {}))
        exchange_mapping.update(parsed.get("exchange_mapping", {}))
        solver_preferences.update(parsed.get("solver_preferences", {}))
        interaction = {"status": "ok"}
    elif parsed.get("status") == "needs_input":
        interaction = {"status": "needs_input", "question": parsed.get("question", {})}
    return {
        "system": {"name": "", "units": "arb."},
        "local_hilbert": {"dimension": _infer_local_dimension_from_text(text), "uniform": True},
        "lattice": lattice,
        "local_term": {
            "support": [],
            "representation": {"kind": "natural_language", "value": text},
        },
        "parameters": {},
        "symmetry_hints": [],
        "exchange_mapping": exchange_mapping,
        "solver_preferences": solver_preferences,
        "interaction": interaction,
        "projection": {"status": "not-needed", "heuristic": ["low-energy", "symmetry", "template"]},
        "timeouts": dict(DEFAULT_TIMEOUTS),
        "user_notes": text,
        "provenance": {
            "source_mode": "freeform",
            "parsed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
    }


def normalize_input(payload):
    representation = payload.get("representation", "operator")
    if representation not in SUPPORTED_REPRESENTATIONS:
        raise ValueError("unsupported representation")
    support = payload.get("support", [])
    support = _normalize_support(support)
    if not support and representation != "natural_language":
        raise ValueError("support must be supplied for operator or matrix inputs")
    value = _require_representation_value(payload, representation)
    local_dimension = int(payload.get("local_dim", 2))
    user_notes = payload.get("user_notes", "")
    if representation == "natural_language":
        local_dimension = _infer_local_dimension_from_text(value, local_dimension)
        if not user_notes:
            user_notes = value
    parsed_nl = parse_controlled_natural_language(value) if representation == "natural_language" else None
    normalized = {
        "system": {"name": payload.get("name", ""), "units": payload.get("units", "arb.")},
        "local_hilbert": {"dimension": local_dimension, "uniform": True},
        "lattice": payload.get("lattice", {"kind": "unspecified", "dimension": None, "unit_cell": []}),
        "local_term": {
            "support": support,
            "representation": {
                "kind": representation,
                "value": value,
            },
        },
        "parameters": payload.get("parameters", {}),
        "symmetry_hints": payload.get("symmetry_hints", []),
        "projection": {"status": "not-needed", "heuristic": ["low-energy", "symmetry", "template"]},
        "timeouts": dict(DEFAULT_TIMEOUTS),
        "user_notes": user_notes,
        "provenance": {
            "source_mode": payload.get("source_mode", representation),
            "parsed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
    }
    return {
        **normalized,
        **(
            {
                "lattice": _merge_lattice_fields(normalized["lattice"], parsed_nl.get("lattice", {})),
                "exchange_mapping": parsed_nl.get("exchange_mapping", {"mode": None, "shell_map": {}}),
                "solver_preferences": parsed_nl.get("solver_preferences", {"classical": None, "lswt": False}),
                "interaction": {
                    "status": parsed_nl.get("status", "ok"),
                    **(
                        {"question": parsed_nl.get("question", {})}
                        if parsed_nl.get("status") == "needs_input"
                        else {}
                    ),
                },
            }
            if representation == "natural_language"
            else {}
        ),
    }


def _load_payload(path):
    raw = Path(path).read_text(encoding="utf-8")
    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?")
    parser.add_argument("--freeform", default=None)
    args = parser.parse_args()
    if args.freeform is not None:
        print(json.dumps(normalize_freeform_text(args.freeform), indent=2, sort_keys=True))
        return 0
    payload = _load_payload(args.input) if args.input else json.load(sys.stdin)
    print(json.dumps(normalize_input(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
