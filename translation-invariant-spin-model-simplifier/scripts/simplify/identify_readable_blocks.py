#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def _load_payload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _match_isotropic_exchange(two_body_terms):
    labels = {term["canonical_label"]: term for term in two_body_terms}
    needed = ["Sx@0 Sx@1", "Sy@0 Sy@1", "Sz@0 Sz@1"]
    if not all(label in labels for label in needed):
        return None
    coefficients = [labels[label]["coefficient"] for label in needed]
    if coefficients[0] == coefficients[1] == coefficients[2]:
        return {
            "type": "isotropic_exchange",
            "source_terms": [labels[label] for label in needed],
            "coefficient": coefficients[0],
        }
    return None


def _match_dm_like(two_body_terms):
    labels = {term["canonical_label"]: term for term in two_body_terms}
    lhs = labels.get("Sx@0 Sy@1")
    rhs = labels.get("Sy@0 Sx@1")
    if lhs and rhs and lhs["coefficient"] == -rhs["coefficient"]:
        return {
            "type": "dm_like",
            "source_terms": [lhs, rhs],
            "coefficient": lhs["coefficient"],
        }
    return None


def _match_scalar_chirality(three_body_terms):
    for term in three_body_terms:
        if term["canonical_label"] == "Sx@0 Sy@1 Sz@2":
            return {
                "type": "scalar_chirality_like",
                "source_terms": [term],
                "coefficient": term["coefficient"],
            }
    return None


def identify_readable_blocks(canonical_model):
    two_body_terms = list(canonical_model.get("two_body", []))
    three_body_terms = list(canonical_model.get("three_body", []))

    blocks = []
    used = set()

    for matcher in (_match_isotropic_exchange, _match_dm_like):
        block = matcher(two_body_terms)
        if block is not None:
            blocks.append(block)
            used.update(id(term) for term in block["source_terms"])

    chirality_block = _match_scalar_chirality(three_body_terms)
    if chirality_block is not None:
        blocks.append(chirality_block)
        used.update(id(term) for term in chirality_block["source_terms"])

    residual_terms = []
    for family_key in ("one_body", "two_body", "three_body", "four_body", "higher_body"):
        for term in canonical_model.get(family_key, []):
            if id(term) not in used:
                residual_terms.append(term)

    return {"blocks": blocks, "residual_terms": residual_terms}


def main():
    payload = _load_payload(sys.argv[1]) if len(sys.argv) > 1 else json.load(sys.stdin)
    print(json.dumps(identify_readable_blocks(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
