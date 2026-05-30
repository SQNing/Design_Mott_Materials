#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from input.normalize_input import normalize_freeform_text, normalize_input
from cli.simplify_text_input import collect_agent_fallback_surface


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


def _classify_wrapper_result(normalized_model, *, awaiting_agent_normalization=False):
    interaction = (
        normalized_model.get("interaction", {})
        if isinstance(normalized_model.get("interaction"), dict)
        else {}
    )
    surface = collect_agent_fallback_surface(normalized_model)
    if interaction.get("status") == "needs_input" and awaiting_agent_normalization and surface.get(
        "agent_normalization_request"
    ):
        return {
            "status": "needs_agent_normalization",
            "interaction": dict(interaction),
            "normalized_model": normalized_model,
            **surface,
        }
    if interaction.get("status") == "needs_input":
        return {
            "status": "needs_input",
            "interaction": dict(interaction),
            "normalized_model": normalized_model,
            **surface,
        }
    return {
        "status": "ok",
        "normalized_model": normalized_model,
        **surface,
    }


def _resolved_selection_context(
    *,
    selected_classical_bond_label=None,
    selected_model_candidate=None,
    selected_local_bond_bond_label=None,
    selected_coordinate_convention=None,
    agent_normalized_document=None,
):
    agent_document = agent_normalized_document if isinstance(agent_normalized_document, dict) else {}
    return {
        "selected_classical_bond_label": selected_classical_bond_label or agent_document.get("selected_classical_bond_label"),
        "selected_model_candidate": selected_model_candidate or agent_document.get("selected_model_candidate"),
        "selected_local_bond_bond_label": selected_local_bond_bond_label or agent_document.get("selected_local_bond_bond_label"),
        "selected_coordinate_convention": selected_coordinate_convention or agent_document.get("selected_coordinate_convention"),
    }


def run_document_normalization_with_agent(
    text,
    *,
    source_path=None,
    selected_classical_bond_label=None,
    selected_model_candidate=None,
    selected_local_bond_bond_label=None,
    selected_coordinate_convention=None,
    agent_normalized_document=None,
):
    selection_context = _resolved_selection_context(
        selected_classical_bond_label=selected_classical_bond_label,
        selected_model_candidate=selected_model_candidate,
        selected_local_bond_bond_label=selected_local_bond_bond_label,
        selected_coordinate_convention=selected_coordinate_convention,
        agent_normalized_document=agent_normalized_document,
    )
    if agent_normalized_document is None:
        normalized_model = normalize_freeform_text(
            text,
            source_path=source_path,
            selected_classical_bond_label=selection_context["selected_classical_bond_label"],
            selected_model_candidate=selection_context["selected_model_candidate"],
            selected_local_bond_bond_label=selection_context["selected_local_bond_bond_label"],
            selected_coordinate_convention=selection_context["selected_coordinate_convention"],
        )
        return _classify_wrapper_result(normalized_model, awaiting_agent_normalization=True)

    normalized_model = normalize_input(
        {
            "representation": "natural_language",
            "description": text,
            "source_path": source_path,
            "classical_bond_label": selection_context["selected_classical_bond_label"],
            "selected_model_candidate": selection_context["selected_model_candidate"],
            "selected_local_bond_bond_label": selection_context["selected_local_bond_bond_label"],
            "selected_coordinate_convention": selection_context["selected_coordinate_convention"],
            "agent_normalized_document": agent_normalized_document,
        }
    )
    return _classify_wrapper_result(normalized_model, awaiting_agent_normalization=False)


def _load_agent_normalized_document(args):
    if args.agent_normalized_document_json and args.agent_normalized_document_file:
        raise ValueError("provide at most one of --agent-normalized-document-json or --agent-normalized-document-file")
    if args.agent_normalized_document_json:
        return json.loads(args.agent_normalized_document_json)
    if args.agent_normalized_document_file:
        return json.loads(Path(args.agent_normalized_document_file).read_text(encoding="utf-8"))
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeform", required=True)
    parser.add_argument("--source-path", default=None)
    parser.add_argument("--selected-classical-bond_label", default=None)
    parser.add_argument("--selected-model-candidate", default=None)
    parser.add_argument("--selected-local-bond-bond_label", default=None)
    parser.add_argument("--selected-coordinate-convention", default=None)
    parser.add_argument("--agent-normalized-document-json", default=None)
    parser.add_argument("--agent-normalized-document-file", default=None)
    args = parser.parse_args()

    result = run_document_normalization_with_agent(
        args.freeform,
        source_path=args.source_path,
        selected_classical_bond_label=args.selected_classical_bond_label,
        selected_model_candidate=args.selected_model_candidate,
        selected_local_bond_bond_label=args.selected_local_bond_bond_label,
        selected_coordinate_convention=args.selected_coordinate_convention,
        agent_normalized_document=_load_agent_normalized_document(args),
    )
    print(json.dumps(_json_safe(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
