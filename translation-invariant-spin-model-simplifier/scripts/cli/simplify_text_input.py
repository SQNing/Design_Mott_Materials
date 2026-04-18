#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from input import normalize_freeform_text
from input.unsupported_feature_catalog import unsupported_feature_details
from input.parse_lattice_description import parse_lattice_description
from simplify.assemble_effective_model import assemble_effective_model
from simplify.canonicalize_terms import canonicalize_terms
from simplify.compile_local_term_to_matrix import (
    LocalMatrixCompilationError,
    compile_local_term_to_matrix,
)
from simplify.decompose_local_term import decompose_local_term
from simplify.generate_simplifications import generate_candidates
from simplify.identify_readable_blocks import identify_readable_blocks
from simplify.infer_symmetries import infer_symmetries
from simplify.score_fidelity import score_fidelity
from cli.operator_expression_help import SUPPORTED_OPERATOR_EXPRESSION_HELP
from cli.render_simplified_model_report import render_simplified_model_report


PUBLIC_AGENT_INFERRED_FIELDS = (
    "confidence",
    "recognized_items",
    "assumptions",
    "unresolved_items",
    "user_explanation",
)


def _json_safe(value):
    if isinstance(value, complex):
        if abs(value.imag) <= 1.0e-12:
            return float(value.real)
        return {"real": float(value.real), "imag": float(value.imag)}
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


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
        "assumptions": list(agent_inferred.get("assumptions", [])),
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


def _projection_gate(normalized_model, decomposition):
    unsupported = list(normalized_model.get("unsupported_features", [])) if isinstance(normalized_model, dict) else []
    details = unsupported_feature_details(unsupported)
    blocker_text = ""
    if details:
        blocker_text = " Remaining blockers include " + ", ".join(detail["description"] for detail in details) + "."
    return {
        "status": "needs_input",
        "stage": "decompose_local_term",
        "normalized_model": normalized_model,
        "decomposition": decomposition,
        "interaction": {
            "status": "needs_input",
            "id": "projection_or_truncate",
            "question": (
                SUPPORTED_OPERATOR_EXPRESSION_HELP
                + " The current workflow still cannot map this particular operator expression into explicit spin-basis terms."
                + blocker_text
                + " "
                "Should I project or truncate the model into a supported operator basis first?"
            ),
            "options": ["project", "truncate", "custom"],
            "unsupported_feature_details": details,
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


def _maybe_compile_local_matrix_record(normalized_model):
    representation = (
        normalized_model.get("local_term", {}).get("representation", {})
        if isinstance(normalized_model.get("local_term"), dict)
        else {}
    )
    support = normalized_model.get("local_term", {}).get("support", [])
    if representation.get("kind") not in {"operator", "matrix"}:
        return None
    if len(list(support or [])) > 2:
        return None
    try:
        return compile_local_term_to_matrix(normalized_model)
    except LocalMatrixCompilationError:
        return None


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

    lattice = parse_lattice_description(normalized_model.get("lattice_description", {}))
    lattice_interaction = lattice.get("interaction", {}) if isinstance(lattice.get("interaction"), dict) else {}
    if lattice_interaction.get("status") == "needs_input":
        lattice = _defer_lattice_resolution(normalized_model, lattice)

    local_term_record = _maybe_compile_local_matrix_record(normalized_model)
    if local_term_record is not None:
        decomposition = decompose_local_term({"local_term_record": local_term_record})
    else:
        decomposition = decompose_local_term(normalized_model)
    if decomposition.get("mode") == "operator" and any(term.get("label") == "raw-operator" for term in decomposition.get("terms", [])):
        return _finalize_pipeline_result(_projection_gate(normalized_model, decomposition))

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
        "local_term_record": local_term_record,
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
    parser.add_argument("--report-md", default=None)
    parser.add_argument("--report-title", default="Simplified Model Report")
    args = parser.parse_args()

    result = run_text_simplification_pipeline(
        args.freeform,
        source_path=args.source_path,
        selected_model_candidate=args.selected_model_candidate,
        selected_local_bond_family=args.selected_local_bond_family,
        selected_coordinate_convention=args.selected_coordinate_convention,
    )
    if args.report_md:
        report_markdown = render_simplified_model_report(result, title=str(args.report_title))
        Path(args.report_md).write_text(report_markdown, encoding="utf-8")
    print(json.dumps(_json_safe(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
