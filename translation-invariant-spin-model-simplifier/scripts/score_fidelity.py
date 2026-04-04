#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def _load_payload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _weight(entries):
    return sum(abs(entry.get("coefficient", 0.0)) for entry in entries)


def score_fidelity(effective_model):
    main_weight = _weight(effective_model.get("main", []))
    low_weight = _weight(effective_model.get("low_weight", []))
    residual_weight = _weight(effective_model.get("residual", []))
    total_weight = main_weight + low_weight + residual_weight

    risk_notes = []
    for entry in effective_model.get("low_weight", []):
        warning = entry.get("warning")
        if warning:
            risk_notes.append(
                "Low-weight term may still be physically important: "
                + warning
            )

    return {
        "reconstruction_error": 0.0,
        "main_fraction": 0.0 if total_weight == 0 else main_weight / total_weight,
        "low_weight_fraction": 0.0 if total_weight == 0 else low_weight / total_weight,
        "residual_fraction": 0.0 if total_weight == 0 else residual_weight / total_weight,
        "symmetry_preservation": "pending-user-confirmation",
        "risk_notes": risk_notes,
    }


def main():
    payload = _load_payload(sys.argv[1]) if len(sys.argv) > 1 else json.load(sys.stdin)
    print(json.dumps(score_fidelity(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
