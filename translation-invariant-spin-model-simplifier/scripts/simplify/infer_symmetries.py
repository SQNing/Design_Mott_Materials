#!/usr/bin/env python3
import json
import sys
from pathlib import Path


ISOTROPIC_TWO_BODY_LABELS = {"Sx@0 Sx@1", "Sy@0 Sy@1", "Sz@0 Sz@1"}


def _load_payload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _detect_from_decomposition(model):
    terms = model.get("decomposition", {}).get("terms", [])
    labels = {term.get("label") for term in terms}
    coefficients = {term.get("label"): term.get("coefficient") for term in terms}

    detected = set()
    if ISOTROPIC_TWO_BODY_LABELS.issubset(labels):
        sx = coefficients["Sx@0 Sx@1"]
        sy = coefficients["Sy@0 Sy@1"]
        sz = coefficients["Sz@0 Sz@1"]
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
