#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from input.natural_language_parser import detect_controlled_natural_language_ambiguity
else:
    from .natural_language_parser import detect_controlled_natural_language_ambiguity


COMMON_DIMENSIONS = {
    "chain": 1,
    "square": 2,
    "triangular": 2,
    "honeycomb": 2,
    "kagome": 2,
    "cubic": 3,
}


def _load_payload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _normalize_structured_lattice(lattice):
    normalized = dict(lattice)
    normalized.setdefault("dimension", COMMON_DIMENSIONS.get(normalized.get("kind")))
    normalized.setdefault("magnetic_sites", [])
    normalized.setdefault("magnetic_site_count", len(normalized["magnetic_sites"]))
    normalized.setdefault("shell_labels", [])
    normalized["source"] = "structured"
    return normalized


def _parse_shell_labels(text):
    labels = re.findall(r"\b(J\d+)\b", text, flags=re.IGNORECASE)
    return [label.upper() for label in labels]


def _parse_magnetic_site_count(text):
    lowered = text.lower()
    digit_match = re.search(r"\b(\d+)\s+magnetic sites?\s+per\s+unit\s+cell\b", lowered)
    if digit_match:
        return int(digit_match.group(1))
    word_map = {"one": 1, "two": 2, "three": 3, "four": 4}
    word_match = re.search(r"\b(one|two|three|four)\s+magnetic sites?\s+per\s+unit\s+cell\b", lowered)
    if word_match:
        return word_map[word_match.group(1)]
    return None


def _needs_input(question, options, question_id="lattice_kind"):
    return {"interaction": {"status": "needs_input", "id": question_id, "question": question, "options": options}}


def _parse_natural_language_lattice(text):
    ambiguity = detect_controlled_natural_language_ambiguity(text)
    if ambiguity is not None:
        question = ambiguity["question"]
        return _needs_input(
            question["prompt"],
            question.get("options", []),
            question_id=question["id"],
        )

    lowered = text.lower()
    if "hexagonal lattice" in lowered:
        return _needs_input(
            "You described a hexagonal lattice. Should this be interpreted as a honeycomb spin lattice or a triangular Bravais lattice?",
            ["honeycomb", "triangular", "custom"],
        )

    kind = None
    for candidate in COMMON_DIMENSIONS:
        if (
            f"{candidate} lattice" in lowered
            or f"{candidate}-lattice" in lowered
            or f"{candidate} layer" in lowered
            or f"{candidate} layers" in lowered
            or f"{candidate} plane" in lowered
            or f"{candidate} planes" in lowered
            or f"{candidate} network" in lowered
        ):
            kind = candidate
            break
    if kind is None:
        return _needs_input(
            "I could not determine the lattice kind from the description. Which lattice should I use?",
            ["chain", "square", "triangular"],
        )

    return {
        "kind": kind,
        "dimension": COMMON_DIMENSIONS[kind],
        "magnetic_sites": [],
        "magnetic_site_count": _parse_magnetic_site_count(text),
        "shell_labels": _parse_shell_labels(text),
        "source": "natural_language",
        "raw_description": text,
    }


def parse_lattice_description(lattice_description):
    if isinstance(lattice_description, str):
        lattice_description = {"kind": "natural_language", "value": lattice_description}
    if not isinstance(lattice_description, dict):
        raise ValueError("lattice_description must be a mapping or string")

    kind = lattice_description.get("kind")
    if kind == "natural_language":
        return _parse_natural_language_lattice(lattice_description.get("value", ""))
    return _normalize_structured_lattice(lattice_description)


def main():
    payload = _load_payload(sys.argv[1]) if len(sys.argv) > 1 else json.load(sys.stdin)
    print(json.dumps(parse_lattice_description(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
