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


def _multipole_metadata(operator):
    if operator in {"Sx", "Sy", "Sz"}:
        return {"rank": 1, "family": "dipole"}
    match = re.fullmatch(r"T(?P<rank>\d+)_[A-Za-z0-9_]+", operator)
    if not match:
        return None
    rank = int(match.group("rank"))
    if rank == 0:
        family = "identity"
    elif rank == 1:
        family = "dipole"
    elif rank == 2:
        family = "quadrupole"
    else:
        family = "higher_multipole"
    return {"rank": rank, "family": family}


def _label_multipole_metadata(canonical_label):
    factors = _parse_label_factors(canonical_label)
    metadata = [_multipole_metadata(operator) for _site, operator in factors]
    metadata = [entry for entry in metadata if entry is not None]
    if not metadata:
        return {}

    ranks = sorted({entry["rank"] for entry in metadata})
    families = sorted({entry["family"] for entry in metadata})
    result = {
        "multipole_ranks": ranks,
        "multipole_families": families,
    }
    if len(ranks) == 1:
        result["multipole_rank"] = ranks[0]
    if len(families) == 1:
        result["multipole_family"] = families[0]
    else:
        result["multipole_family"] = "mixed"
    return result


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
    term_metadata = {}

    for term in _decomposition_terms(model):
        canonical_label = _canonical_label(term["label"])
        family = term.get("family")
        merge_key = (family, canonical_label)
        merged[merge_key] += term["coefficient"]
        metadata = {"family": family}
        if isinstance(model.get("decomposition"), dict):
            source_backbone = model["decomposition"].get("source_backbone")
            if source_backbone is not None:
                metadata["source_backbone"] = source_backbone
        for field in ("source_geometry_class",):
            if term.get(field) is not None:
                metadata[field] = term.get(field)
        term_metadata[merge_key] = metadata

    grouped_terms = defaultdict(list)
    for merge_key, coefficient in merged.items():
        family, canonical_label = merge_key
        support = sorted({site for site, _operator in _parse_label_factors(canonical_label)})
        body_order = len(support)
        family_key = BODY_ORDER_KEYS.get(body_order, "higher_body")
        entry = {
            "canonical_label": canonical_label,
            "coefficient": coefficient,
            "support": support,
            "body_order": body_order,
            "absolute_weight": abs(coefficient),
            "symmetry_annotations": [],
        }
        entry.update(_label_multipole_metadata(canonical_label))
        for key, value in term_metadata[merge_key].items():
            if value is not None:
                entry[key] = value
        grouped_terms[family_key].append(entry)

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
