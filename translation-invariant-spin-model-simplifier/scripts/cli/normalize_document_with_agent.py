#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from input.normalize_input import normalize_freeform_text, normalize_input


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


def _classify_wrapper_result(normalized_model):
    interaction = (
        normalized_model.get("interaction", {})
        if isinstance(normalized_model.get("interaction"), dict)
        else {}
    )
    request = normalized_model.get("agent_normalization_request")
    if interaction.get("status") == "needs_input" and interaction.get("id") == "agent_document_normalization":
        return {
            "status": "needs_agent_normalization",
            "interaction": dict(interaction),
            "agent_normalization_request": dict(request) if isinstance(request, dict) else None,
            "normalized_model": normalized_model,
        }
    if interaction.get("status") == "needs_input":
        return {
            "status": "needs_input",
            "interaction": dict(interaction),
            "normalized_model": normalized_model,
        }
    return {
        "status": "ok",
        "normalized_model": normalized_model,
    }


def run_document_normalization_with_agent(
    text,
    *,
    source_path=None,
    selected_model_candidate=None,
    selected_local_bond_family=None,
    selected_coordinate_convention=None,
    agent_normalized_document=None,
):
    if agent_normalized_document is None:
        normalized_model = normalize_freeform_text(
            text,
            source_path=source_path,
            selected_model_candidate=selected_model_candidate,
            selected_local_bond_family=selected_local_bond_family,
            selected_coordinate_convention=selected_coordinate_convention,
        )
        return _classify_wrapper_result(normalized_model)

    normalized_model = normalize_input(
        {
            "representation": "natural_language",
            "description": text,
            "source_path": source_path,
            "selected_model_candidate": selected_model_candidate,
            "selected_local_bond_family": selected_local_bond_family,
            "selected_coordinate_convention": selected_coordinate_convention,
            "agent_normalized_document": agent_normalized_document,
        }
    )
    return _classify_wrapper_result(normalized_model)


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
    parser.add_argument("--selected-model-candidate", default=None)
    parser.add_argument("--selected-local-bond-family", default=None)
    parser.add_argument("--selected-coordinate-convention", default=None)
    parser.add_argument("--agent-normalized-document-json", default=None)
    parser.add_argument("--agent-normalized-document-file", default=None)
    args = parser.parse_args()

    result = run_document_normalization_with_agent(
        args.freeform,
        source_path=args.source_path,
        selected_model_candidate=args.selected_model_candidate,
        selected_local_bond_family=args.selected_local_bond_family,
        selected_coordinate_convention=args.selected_coordinate_convention,
        agent_normalized_document=_load_agent_normalized_document(args),
    )
    print(json.dumps(_json_safe(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
