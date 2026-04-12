#!/usr/bin/env python3
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


ISOTROPIC_TWO_BODY_LABELS = {"Sx@0 Sx@1", "Sy@0 Sy@1", "Sz@0 Sz@1"}
SPIN_OPERATORS = {"Sx", "Sy", "Sz"}


def _load_payload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _spin_only_two_body_terms(terms):
    grouped = defaultdict(dict)
    pattern = re.compile(r"(S[xyz])@(-?\d+)")

    for term in terms:
        label = str(term.get("label", ""))
        factors = pattern.findall(label)
        if len(factors) != 2:
            continue
        if " " not in label:
            continue

        parsed = []
        for operator, site in factors:
            if operator not in SPIN_OPERATORS:
                parsed = []
                break
            parsed.append((int(site), operator))
        if len(parsed) != 2:
            continue

        parsed.sort(key=lambda item: (item[0], item[1]))
        support = tuple(site for site, _operator in parsed)
        canonical_label = " ".join(f"{operator}@{site}" for site, operator in parsed)
        grouped[support][canonical_label] = term.get("coefficient")
    return grouped


def _detect_from_decomposition(model):
    terms = model.get("decomposition", {}).get("terms", [])
    detected = set()
    for support, coefficients in _spin_only_two_body_terms(terms).items():
        expected_labels = {
            f"Sx@{support[0]} Sx@{support[1]}",
            f"Sy@{support[0]} Sy@{support[1]}",
            f"Sz@{support[0]} Sz@{support[1]}",
        }
        if set(coefficients) != expected_labels:
            continue
        sx = coefficients[f"Sx@{support[0]} Sx@{support[1]}"]
        sy = coefficients[f"Sy@{support[0]} Sy@{support[1]}"]
        sz = coefficients[f"Sz@{support[0]} Sz@{support[1]}"]
        if sx == sy == sz:
            detected.add("su2_spin")
        elif sx == sy:
            detected.add("u1_spin")
    return detected


def _make_confirmation_question(missing):
    labels = ", ".join(sorted(missing))
    return {
        "status": "needs_input",
        "question": f"I could not confirm the required symmetry constraint(s): {labels}. Should I enforce them anyway or treat them as approximate?",
        "options": ["enforce-required", "treat-as-approximate", "custom"],
    }


def infer_symmetries(model):
    detected = {"translation", "hermiticity"}
    detected.update(_detect_from_decomposition(model))

    user_required = set(model.get("user_required_symmetries", []))
    allowed_breaking = set(model.get("allowed_breaking", []))
    missing_required = sorted(user_required - detected - allowed_breaking)

    result = {
        "detected_symmetries": sorted(detected),
        "user_required_symmetries": sorted(user_required),
        "allowed_breaking": sorted(allowed_breaking),
    }
    if missing_required:
        result["interaction"] = _make_confirmation_question(missing_required)
    return result


def main():
    payload = _load_payload(sys.argv[1]) if len(sys.argv) > 1 else json.load(sys.stdin)
    print(json.dumps(infer_symmetries(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
