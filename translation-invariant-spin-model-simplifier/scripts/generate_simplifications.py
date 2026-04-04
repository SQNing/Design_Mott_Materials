#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


def faithful_candidate(effective_model):
    return {
        "name": "faithful-readable",
        "main": list(effective_model.get("main", [])),
        "low_weight": list(effective_model.get("low_weight", [])),
        "residual": list(effective_model.get("residual", [])),
        "dropped_terms": [],
        "rationale": "Preserve the readable main model while keeping low-weight and residual structure visible.",
        "requires_user_confirmation": False,
    }


def readable_core_candidate(effective_model):
    return {
        "name": "readable-core",
        "main": list(effective_model.get("main", [])),
        "low_weight": [],
        "residual": list(effective_model.get("residual", [])),
        "dropped_terms": [],
        "rationale": "Hide low-weight terms from the core readable view without deleting them from the model state.",
        "requires_user_confirmation": False,
    }


def aggressive_minimal_candidate(effective_model):
    return {
        "name": "aggressive-minimal",
        "main": list(effective_model.get("main", [])),
        "low_weight": [],
        "residual": [],
        "dropped_terms": [term.get("canonical_label", term.get("type", "term")) for term in effective_model.get("low_weight", [])]
        + [term.get("canonical_label", term.get("type", "term")) for term in effective_model.get("residual", [])],
        "rationale": "Present only the main readable model. This is concise but may hide physically relevant weak or unmatched terms.",
        "requires_user_confirmation": True,
    }


def resolve_candidate_choice(summary, user_choice=None, timed_out=False):
    if user_choice is not None:
        return {"selected": int(user_choice), "auto_selected": False}
    if timed_out:
        return {"selected": int(summary["recommended"]), "auto_selected": True}
    return {"selected": None, "auto_selected": False}


def resolve_projection_choice(needs_projection, user_choice=None, timed_out=False):
    if not needs_projection:
        return {"action": "not-needed", "auto_selected": False}
    if user_choice in {"project", "truncate"}:
        return {"action": user_choice, "auto_selected": False}
    if timed_out:
        return {"action": "apply-default-projection", "auto_selected": True}
    return {"action": "await-user-choice", "auto_selected": False}


def generate_candidates(model, relative_threshold=0.1):
    del relative_threshold
    effective_model = model["effective_model"]
    candidates = [
        faithful_candidate(effective_model),
        readable_core_candidate(effective_model),
        aggressive_minimal_candidate(effective_model),
    ]
    return {"recommended": 0, "candidates": candidates}


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
