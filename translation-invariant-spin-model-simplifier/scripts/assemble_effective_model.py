#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def _load_payload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def assemble_effective_model(readable_model, low_weight_threshold=0.1):
    assembled = {
        "main": list(readable_model.get("blocks", [])),
        "low_weight": [],
        "residual": [],
    }

    for term in readable_model.get("residual_terms", []):
        if term.get("relative_weight", 0.0) < low_weight_threshold:
            flagged = dict(term)
            if term.get("symmetry_annotations"):
                flagged["warning"] = (
                    "Low-weight term carries symmetry-breaking annotations: "
                    + ", ".join(term["symmetry_annotations"])
                )
            assembled["low_weight"].append(flagged)
        else:
            assembled["residual"].append(term)

    return assembled


def main():
    payload = _load_payload(sys.argv[1]) if len(sys.argv) > 1 else json.load(sys.stdin)
    print(json.dumps(assemble_effective_model(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
