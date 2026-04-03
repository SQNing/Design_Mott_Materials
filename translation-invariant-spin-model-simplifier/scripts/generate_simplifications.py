#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


def _sorted_terms(terms):
    return sorted(terms, key=lambda item: (-abs(item["coefficient"]), item["label"]))


def _nearly_equal(left, right, tolerance=1e-9):
    return abs(float(left) - float(right)) <= tolerance


def symmetry_candidate(terms):
    merged = {}
    for term in terms:
        merged.setdefault(term["label"], 0.0)
        merged[term["label"]] += term["coefficient"]
    return {
        "name": "symmetry-preserving",
        "terms": [{"label": key, "coefficient": value} for key, value in sorted(merged.items())],
        "dropped_terms": [],
        "rationale": "Keep all symmetry-allowed terms and combine duplicate operator labels.",
    }


def energy_pruned_candidate(terms, relative_threshold):
    scale = max(abs(term["coefficient"]) for term in terms) if terms else 0.0
    kept = []
    dropped = []
    for term in terms:
        if scale and abs(term["coefficient"]) / scale < relative_threshold:
            dropped.append(term["label"])
        else:
            kept.append(term)
    return {
        "name": "energy-pruned",
        "terms": _sorted_terms(kept),
        "dropped_terms": dropped,
        "rationale": "Discard parametrically small terms relative to the dominant coupling scale.",
    }


def template_candidate(terms):
    coefficients = {}
    for term in terms:
        coefficients.setdefault(term["label"], 0.0)
        coefficients[term["label"]] += float(term["coefficient"])

    labels = set(coefficients)
    template = "generic"
    pair_labels = {"Sx@0 Sx@1", "Sy@0 Sy@1", "Sz@0 Sz@1"}
    if labels == pair_labels:
        jx = coefficients["Sx@0 Sx@1"]
        jy = coefficients["Sy@0 Sy@1"]
        jz = coefficients["Sz@0 Sz@1"]
        equal_pairs = [_nearly_equal(jx, jy), _nearly_equal(jx, jz), _nearly_equal(jy, jz)]
        if all(equal_pairs):
            template = "heisenberg"
        elif any(equal_pairs):
            template = "xxz"
        else:
            template = "xyz"
    return {
        "name": "template-map",
        "template": template,
        "terms": _sorted_terms(terms),
        "dropped_terms": [],
        "rationale": "Map the model onto the closest named spin Hamiltonian when possible.",
    }


def resolve_candidate_choice(summary, user_choice=None, timed_out=False, allow_auto_select=False):
    if user_choice is not None:
        return {"selected": int(user_choice), "auto_selected": False}
    if allow_auto_select:
        return {"selected": int(summary["recommended"]), "auto_selected": True}
    return {"selected": None, "auto_selected": False}


def resolve_projection_choice(needs_projection, user_choice=None, timed_out=False, allow_auto_select=False):
    if not needs_projection:
        return {"action": "not-needed", "auto_selected": False}
    if user_choice in {"project", "truncate"}:
        return {"action": user_choice, "auto_selected": False}
    if allow_auto_select:
        return {"action": "apply-default-projection", "auto_selected": True}
    return {"action": "await-user-choice", "auto_selected": False}


def generate_candidates(model, relative_threshold=0.1):
    terms = model["decomposition"]["terms"]
    candidates = [
        symmetry_candidate(terms),
        energy_pruned_candidate(terms, relative_threshold),
        template_candidate(terms),
    ]
    recommended = 2 if candidates[2].get("template") != "generic" else 0
    return {"recommended": recommended, "candidates": candidates}


def _load_payload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?")
    parser.add_argument("--relative-threshold", type=float, default=0.1)
    args = parser.parse_args()
    payload = _load_payload(args.input) if args.input else json.load(sys.stdin)
    print(json.dumps(generate_candidates(payload, relative_threshold=args.relative_threshold), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
