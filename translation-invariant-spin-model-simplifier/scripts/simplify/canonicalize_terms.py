#!/usr/bin/env python3
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


BODY_ORDER_KEYS = {
    1: "one_body",
    2: "two_body",
    3: "three_body",
    4: "four_body",
}


def _load_payload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _parse_label_factors(label):
    if not label or label == "identity":
        return []
    factors = []
    for factor in label.split():
        match = re.fullmatch(r"([A-Za-z0-9_]+)@(-?\d+)", factor)
        if not match:
            raise ValueError(f"unsupported factor label: {factor}")
        operator, site = match.groups()
        factors.append((int(site), operator))
    return factors


def _canonical_label(label):
    factors = sorted(_parse_label_factors(label), key=lambda item: (item[0], item[1]))
    return " ".join(f"{operator}@{site}" for site, operator in factors)


def _decomposition_terms(model):
    if isinstance(model, dict) and isinstance(model.get("terms"), list):
        return model["terms"]
    return model.get("decomposition", {}).get("terms", [])


def canonicalize_terms(model):
    grouped = {
        "one_body": [],
        "two_body": [],
        "three_body": [],
        "four_body": [],
        "higher_body": [],
    }
    merged = defaultdict(float)

    for term in _decomposition_terms(model):
        canonical_label = _canonical_label(term["label"])
        merged[canonical_label] += term["coefficient"]

    grouped_terms = defaultdict(list)
    for canonical_label, coefficient in merged.items():
        support = [site for site, _operator in sorted(_parse_label_factors(canonical_label), key=lambda item: (item[0], item[1]))]
        body_order = len(support)
        family_key = BODY_ORDER_KEYS.get(body_order, "higher_body")
        grouped_terms[family_key].append(
            {
                "canonical_label": canonical_label,
                "coefficient": coefficient,
                "support": support,
                "body_order": body_order,
                "absolute_weight": abs(coefficient),
                "symmetry_annotations": [],
            }
        )

    for family_key, terms in grouped_terms.items():
        max_weight = max((term["absolute_weight"] for term in terms), default=0.0)
        for term in sorted(terms, key=lambda item: (-item["absolute_weight"], item["canonical_label"])):
            term["relative_weight"] = 0.0 if max_weight == 0 else term["absolute_weight"] / max_weight
            grouped[family_key].append(term)

    return grouped


def main():
    payload = _load_payload(sys.argv[1]) if len(sys.argv) > 1 else json.load(sys.stdin)
    print(json.dumps(canonicalize_terms(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
