#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from input import normalize_freeform_text
from input.document_input_protocol import build_intermediate_record
from input.parse_lattice_description import parse_lattice_description
from cli.build_pseudospin_orbital_payload import build_pseudospin_orbital_payload
from simplify.assemble_effective_model import assemble_effective_model
from simplify.canonicalize_terms import canonicalize_terms
from simplify.decompose_local_term import decompose_local_term
from simplify.generate_simplifications import generate_candidates
from simplify.identify_readable_blocks import identify_readable_blocks
from simplify.infer_symmetries import infer_symmetries
from simplify.score_fidelity import score_fidelity
from simplify.simplify_pseudospin_orbital_payload import simplify_pseudospin_orbital_payload


PUBLIC_AGENT_INFERRED_FIELDS = (
    "confidence",
    "recognized_items",
    "assumptions",
    "unresolved_items",
    "user_explanation",
)


def _public_agent_inferred_view(agent_inferred):
    if not isinstance(agent_inferred, dict):
        return None
    confidence = agent_inferred.get("confidence", {})
    user_explanation = agent_inferred.get("user_explanation", {})
    unresolved_items = list(agent_inferred.get("unresolved_items", []))
    public_user_explanation = dict(user_explanation) if isinstance(user_explanation, dict) else {}
    summary = public_user_explanation.get("summary")
    if isinstance(summary, str):
        for item in unresolved_items:
            field = item.get("field") if isinstance(item, dict) else None
            if isinstance(field, str) and field:
                summary = summary.replace(field, field.replace("_", " "))
        public_user_explanation["summary"] = summary
    return {
        "confidence": dict(confidence) if isinstance(confidence, dict) else {},
        "recognized_items": list(agent_inferred.get("recognized_items", [])),
        "assumptions": [],
        "unresolved_items": unresolved_items,
        "user_explanation": public_user_explanation,
    }


def _agent_inferred_materially_contributed(normalized_model):
    if not isinstance(normalized_model, dict):
        return False
    agent_inferred = normalized_model.get("agent_inferred", {})
    if not isinstance(agent_inferred, dict) or not agent_inferred:
        return False
    if normalized_model.get("landing_readiness") in {
        "agent_proposed_ok",
        "agent_proposed_needs_input",
        "unsupported_even_with_agent",
    }:
        return True
    return any(
        agent_inferred.get(field)
        for field in ("inferred_fields", "unresolved_items", "unsupported_even_with_agent")
    )


def _finalize_pipeline_result(result):
    if not isinstance(result, dict):
        return result
    if result.get("status") not in {"ok", "needs_input"}:
        return result
    normalized_model = result.get("normalized_model", {})
    if not _agent_inferred_materially_contributed(normalized_model):
        result.pop("agent_inferred", None)
        return result
    public_view = _public_agent_inferred_view(normalized_model.get("agent_inferred"))
    if public_view is not None:
        result["agent_inferred"] = public_view
    return result


def _has_matrix_form_candidate(normalized_model):
    record = normalized_model.get("document_intermediate", {})
    candidates = record.get("model_candidates", []) if isinstance(record, dict) else []
    return any(candidate.get("name") == "matrix_form" for candidate in candidates)


def _matrix_form_supports_selected_family(normalized_model):
    if not _has_matrix_form_candidate(normalized_model):
        return False
    selected_family = normalized_model.get("selected_local_bond_family")
    if not selected_family:
        return True
    source_text = normalized_model.get("document_source_text")
    if not isinstance(source_text, str) or not source_text.strip():
        return False
    record = build_intermediate_record(
        source_text=source_text,
        source_path=normalized_model.get("document_source_path"),
        selected_model_candidate="matrix_form",
        selected_local_bond_family=selected_family,
        selected_coordinate_convention=_selected_coordinate_frame(normalized_model),
    )
    local_bond_candidates = list(record.get("hamiltonian_model", {}).get("local_bond_candidates", []))
    return any(entry.get("family") == selected_family for entry in local_bond_candidates)


def _selected_coordinate_frame(normalized_model):
    selected = normalized_model.get("selected_coordinate_convention")
    if isinstance(selected, str) and selected.strip():
        return selected.strip()
    convention = normalized_model.get("coordinate_convention", {})
    if isinstance(convention, dict) and convention.get("status") == "selected":
        frame = str(convention.get("frame") or "").strip()
        if frame and frame != "unspecified":
            return frame
    return None


def _maybe_auto_fallback_to_matrix_form(normalized_model):
    unsupported_features = set(normalized_model.get("unsupported_features", []))
    anisotropic_phase_features = {
        "bond_dependent_phase_gamma_terms",
        "double_raising_lowering_exchange_terms",
        "zpm_offdiagonal_exchange_terms",
    }
    if not (unsupported_features & anisotropic_phase_features):
        return None
    if normalized_model.get("selected_model_candidate") == "matrix_form":
        return None
    if not _matrix_form_supports_selected_family(normalized_model):
        return None
    source_text = normalized_model.get("document_source_text")
    if not isinstance(source_text, str) or not source_text.strip():
        return None
    return run_text_simplification_pipeline(
        source_text,
        source_path=normalized_model.get("document_source_path"),
        selected_model_candidate="matrix_form",
        selected_local_bond_family=normalized_model.get("selected_local_bond_family"),
        selected_coordinate_convention=_selected_coordinate_frame(normalized_model),
    )


def _projection_gate(normalized_model, decomposition):
    unsupported_features = list(normalized_model.get("unsupported_features", []))
    anisotropic_phase_features = {
        "bond_dependent_phase_gamma_terms",
        "double_raising_lowering_exchange_terms",
        "zpm_offdiagonal_exchange_terms",
    }
    if any(feature in anisotropic_phase_features for feature in unsupported_features):
        return {
            "status": "needs_input",
            "stage": "decompose_local_term",
            "normalized_model": normalized_model,
            "decomposition": decomposition,
            "interaction": {
                "status": "needs_input",
                "id": "bond_phase_matrix_form_selection",
                "question": (
                    "The selected bond family contains bond-phase-dependent anisotropic terms "
                    "(for example gamma_ij, J^{\\pm\\pm}, or J^{z\\pm}) that the current "
                    "operator-basis decomposition cannot represent faithfully. Should I switch "
                    "to the equivalent matrix-form candidate, or should I project/truncate first?"
                ),
                "options": ["matrix_form", "project", "truncate"],
            },
            "unsupported_features": unsupported_features,
        }
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
        "unsupported_features": unsupported_features + ["operator_expression_decomposition_pending"],
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


def _run_many_body_hr_text_pipeline(normalized_model):
    representation = normalized_model["hamiltonian_description"]["representation"]
    structure_file = representation["structure_file"]
    hamiltonian_file = representation["hamiltonian_file"]
    try:
        parsed_payload = build_pseudospin_orbital_payload(
            poscar_path=Path(structure_file),
            hr_path=Path(hamiltonian_file),
        )
    except Exception as exc:
        return _finalize_pipeline_result({
            "status": "needs_input",
            "stage": "normalize_input",
            "normalized_model": normalized_model,
            "interaction": {
                "status": "needs_input",
                "id": "structure_parser_selection",
                "question": (
                    "I detected a many_body_hr file pair, but the structure file could not be parsed "
                    "by the current broad structure reader. Should I convert or replace the structure file?"
                ),
                "options": ["convert", "replace", "custom"],
            },
            "unsupported_features": [
                "many_body_hr_structure_parser_pending",
                f"structure_parser_error: {exc}",
            ],
        })
    summary = simplify_pseudospin_orbital_payload(parsed_payload)
    fidelity = score_fidelity(summary["effective_model"])
    return _finalize_pipeline_result({
        "status": "ok",
        "stage": "complete",
        "input_mode": "many_body_hr",
        "normalized_model": normalized_model,
        "parsed_payload": parsed_payload,
        "decomposition": summary["decomposition"],
        "canonical_model": summary["canonical_model"],
        "readable_model": summary["readable_model"],
        "effective_model": summary["effective_model"],
        "simplification": summary["simplification"],
        "fidelity": fidelity,
        "unsupported_features": list(normalized_model.get("unsupported_features", [])),
    })


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
        return _finalize_pipeline_result({
            "status": "needs_input",
            "stage": "normalize_input",
            "normalized_model": normalized_model,
            "interaction": dict(normalized_interaction),
            "unsupported_features": list(normalized_model.get("unsupported_features", [])),
        })

    if normalized_model["hamiltonian_description"]["representation"]["kind"] == "many_body_hr":
        return _run_many_body_hr_text_pipeline(normalized_model)

    lattice = parse_lattice_description(normalized_model.get("lattice_description", {}))
    lattice_interaction = lattice.get("interaction", {}) if isinstance(lattice.get("interaction"), dict) else {}
    if lattice_interaction.get("status") == "needs_input":
        lattice = _defer_lattice_resolution(normalized_model, lattice)

    decomposition = decompose_local_term(normalized_model)
    if decomposition.get("mode") == "operator" and any(term.get("label") == "raw-operator" for term in decomposition.get("terms", [])):
        fallback = _maybe_auto_fallback_to_matrix_form(normalized_model)
        if fallback is not None:
            return fallback
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
        return _finalize_pipeline_result({
            "status": "needs_input",
            "stage": "infer_symmetries",
            "normalized_model": normalized_model,
            "lattice": lattice,
            "decomposition": decomposition,
            "symmetries": symmetries,
            "interaction": dict(symmetry_interaction),
            "unsupported_features": list(normalized_model.get("unsupported_features", [])),
        })

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

    return _finalize_pipeline_result({
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
    })


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
