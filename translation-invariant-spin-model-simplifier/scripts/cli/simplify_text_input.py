#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from input import normalize_freeform_text
from input.parse_lattice_description import parse_lattice_description
from simplify.assemble_effective_model import assemble_effective_model
from simplify.canonicalize_terms import canonicalize_terms
from simplify.decompose_local_term import decompose_local_term
from simplify.generate_simplifications import generate_candidates
from simplify.identify_readable_blocks import identify_readable_blocks
from simplify.infer_symmetries import infer_symmetries
from simplify.score_fidelity import score_fidelity


def _projection_gate(normalized_model, decomposition):
    return {
        "status": "needs_input",
        "stage": "decompose_local_term",
        "normalized_model": normalized_model,
        "decomposition": decomposition,
        "interaction": {
            "status": "needs_input",
            "id": "projection_or_truncate",
            "question": (
                "The current workflow cannot yet map this operator expression into explicit spin-basis terms. "
                "Should I project or truncate the model into a supported operator basis first?"
            ),
            "options": ["project", "truncate", "custom"],
        },
        "unsupported_features": ["operator_expression_decomposition_pending"],
    }


def _defer_lattice_resolution(normalized_model, lattice):
    deferred = dict(normalized_model.get("lattice", {}))
    deferred.setdefault("kind", "unspecified")
    deferred.setdefault("dimension", None)
    deferred.setdefault("unit_cell", [])
    deferred["source"] = "deferred-natural-language"
    deferred["raw_description"] = normalized_model.get("lattice_description", {}).get("value", "")
    if isinstance(lattice.get("interaction"), dict):
        deferred["interaction"] = dict(lattice["interaction"])
    return deferred


def run_text_simplification_pipeline(
    text,
    *,
    source_path=None,
    selected_model_candidate=None,
    selected_local_bond_family=None,
    selected_coordinate_convention=None,
):
    normalized_model = normalize_freeform_text(
        text,
        source_path=source_path,
        selected_model_candidate=selected_model_candidate,
        selected_local_bond_family=selected_local_bond_family,
        selected_coordinate_convention=selected_coordinate_convention,
    )
    normalized_interaction = (
        normalized_model.get("interaction", {})
        if isinstance(normalized_model.get("interaction"), dict)
        else {}
    )
    if normalized_interaction.get("status") == "needs_input":
        return {
            "status": "needs_input",
            "stage": "normalize_input",
            "normalized_model": normalized_model,
            "interaction": dict(normalized_interaction),
            "unsupported_features": list(normalized_model.get("unsupported_features", [])),
        }

    lattice = parse_lattice_description(normalized_model.get("lattice_description", {}))
    lattice_interaction = lattice.get("interaction", {}) if isinstance(lattice.get("interaction"), dict) else {}
    if lattice_interaction.get("status") == "needs_input":
        lattice = _defer_lattice_resolution(normalized_model, lattice)

    decomposition = decompose_local_term(normalized_model)
    if decomposition.get("mode") == "operator" and any(term.get("label") == "raw-operator" for term in decomposition.get("terms", [])):
        return _projection_gate(normalized_model, decomposition)

    symmetry_model = {
        "decomposition": decomposition,
        "user_required_symmetries": normalized_model.get("user_required_symmetries", []),
        "allowed_breaking": normalized_model.get("allowed_breaking", []),
    }
    symmetries = infer_symmetries(symmetry_model)
    symmetry_interaction = (
        symmetries.get("interaction", {})
        if isinstance(symmetries.get("interaction"), dict)
        else {}
    )
    if symmetry_interaction.get("status") == "needs_input":
        return {
            "status": "needs_input",
            "stage": "infer_symmetries",
            "normalized_model": normalized_model,
            "lattice": lattice,
            "decomposition": decomposition,
            "symmetries": symmetries,
            "interaction": dict(symmetry_interaction),
            "unsupported_features": list(normalized_model.get("unsupported_features", [])),
        }

    canonical_model = canonicalize_terms({"decomposition": decomposition})
    readable_model = identify_readable_blocks(
        canonical_model,
        coordinate_convention=normalized_model.get("coordinate_convention", {}),
    )
    effective_model = assemble_effective_model(readable_model)
    effective_model["coordinate_convention"] = dict(
        normalized_model.get("coordinate_convention", {})
    )
    effective_model["rotating_frame_transform"] = dict(
        normalized_model.get("rotating_frame_transform", {})
    )
    fidelity = score_fidelity(effective_model)
    simplification = generate_candidates({"effective_model": effective_model})

    return {
        "status": "ok",
        "stage": "complete",
        "normalized_model": normalized_model,
        "lattice": lattice,
        "decomposition": decomposition,
        "symmetries": symmetries,
        "canonical_model": canonical_model,
        "readable_model": readable_model,
        "effective_model": effective_model,
        "fidelity": fidelity,
        "simplification": simplification,
        "unsupported_features": list(normalized_model.get("unsupported_features", [])),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeform", required=True)
    parser.add_argument("--source-path", default=None)
    parser.add_argument("--selected-model-candidate", default=None)
    parser.add_argument("--selected-local-bond-family", default=None)
    parser.add_argument("--selected-coordinate-convention", default=None)
    args = parser.parse_args()

    result = run_text_simplification_pipeline(
        args.freeform,
        source_path=args.source_path,
        selected_model_candidate=args.selected_model_candidate,
        selected_local_bond_family=args.selected_local_bond_family,
        selected_coordinate_convention=args.selected_coordinate_convention,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
