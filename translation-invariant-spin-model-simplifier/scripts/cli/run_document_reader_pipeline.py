#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cli.orchestrate_agent_document_normalization import (
    run_agent_document_normalization_orchestrator,
)
from cli.render_simplified_model_report import render_simplified_model_report
from cli.simplify_text_input import run_simplification_from_normalized_model


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


def _write_json(path, payload):
    Path(path).write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True), encoding="utf-8")


def _load_agent_normalized_document(args):
    if args.agent_normalized_document_json and args.agent_normalized_document_file:
        raise ValueError("provide at most one of --agent-normalized-document-json or --agent-normalized-document-file")
    if args.agent_normalized_document_json:
        return json.loads(args.agent_normalized_document_json)
    if args.agent_normalized_document_file:
        return json.loads(Path(args.agent_normalized_document_file).read_text(encoding="utf-8"))
    return None


def _base_artifacts(output_dir):
    output_dir = Path(output_dir)
    return {
        "output_dir": str(output_dir),
        "document_orchestration_dir": str(output_dir / "document_orchestration"),
        "simplification_dir": str(output_dir / "simplification"),
        "final_pipeline_result": str(output_dir / "final_pipeline_result.json"),
    }


def _write_text(path, text):
    Path(path).write_text(str(text), encoding="utf-8")


def _write_document_orchestration_artifacts(output_dir, orchestration):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "final_result.json", orchestration)


def _write_simplification_artifacts(output_dir, simplification):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "pipeline_result.json", simplification)
    if simplification.get("effective_model") is not None:
        _write_json(output_dir / "effective_model.json", simplification.get("effective_model"))
    if simplification.get("simplification") is not None:
        _write_json(
            output_dir / "simplification_candidates.json",
            simplification.get("simplification"),
        )
    report_markdown = render_simplified_model_report(
        simplification,
        title="Document Reader Simplified Model Report",
    )
    _write_text(output_dir / "report.md", report_markdown)


def run_document_reader_pipeline(
    text,
    *,
    source_path=None,
    selected_model_candidate=None,
    selected_local_bond_family=None,
    selected_coordinate_convention=None,
    output_dir,
    agent_normalized_document=None,
    agent_command=None,
    use_request_example_payload=False,
    max_agent_rounds=1,
):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    document_output_dir = output_dir / "document_orchestration"
    simplification_output_dir = output_dir / "simplification"
    document_output_dir.mkdir(parents=True, exist_ok=True)
    simplification_output_dir.mkdir(parents=True, exist_ok=True)

    orchestration = run_agent_document_normalization_orchestrator(
        text,
        source_path=source_path,
        selected_model_candidate=selected_model_candidate,
        selected_local_bond_family=selected_local_bond_family,
        selected_coordinate_convention=selected_coordinate_convention,
        output_dir=document_output_dir,
        agent_normalized_document=agent_normalized_document,
        agent_command=agent_command,
        use_request_example_payload=use_request_example_payload,
        max_agent_rounds=max_agent_rounds,
    )
    _write_document_orchestration_artifacts(document_output_dir, orchestration)
    artifacts = _base_artifacts(output_dir)

    if orchestration.get("status") != "ok":
        result = {
            "status": orchestration.get("status"),
            "stage": "document_orchestration",
            "document_orchestration_status": orchestration.get("status"),
            "simplification_status": None,
            "normalized_model": orchestration.get("normalized_model"),
            "interaction": orchestration.get("interaction"),
            "agent_normalization_request": orchestration.get("agent_normalization_request"),
            "agent_review": orchestration.get("agent_review"),
            "document_orchestration": orchestration,
            "artifacts": artifacts,
        }
        _write_json(output_dir / "final_pipeline_result.json", result)
        return result

    normalized_model = orchestration.get("normalized_model", {})
    simplification = run_simplification_from_normalized_model(normalized_model)
    _write_simplification_artifacts(simplification_output_dir, simplification)
    result = {
        **simplification,
        "document_orchestration_status": orchestration.get("status"),
        "simplification_status": simplification.get("status"),
        "document_orchestration": orchestration,
        "artifacts": artifacts,
    }
    _write_json(output_dir / "final_pipeline_result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeform", required=True)
    parser.add_argument("--source-path", default=None)
    parser.add_argument("--selected-model-candidate", default=None)
    parser.add_argument("--selected-local-bond-family", default=None)
    parser.add_argument("--selected-coordinate-convention", default=None)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--agent-normalized-document-json", default=None)
    parser.add_argument("--agent-normalized-document-file", default=None)
    parser.add_argument("--agent-command", default=None)
    parser.add_argument("--use-request-example-payload", action="store_true")
    parser.add_argument("--max-agent-rounds", type=int, default=1)
    args = parser.parse_args()

    result = run_document_reader_pipeline(
        args.freeform,
        source_path=args.source_path,
        selected_model_candidate=args.selected_model_candidate,
        selected_local_bond_family=args.selected_local_bond_family,
        selected_coordinate_convention=args.selected_coordinate_convention,
        output_dir=args.output_dir,
        agent_normalized_document=_load_agent_normalized_document(args),
        agent_command=args.agent_command,
        use_request_example_payload=bool(args.use_request_example_payload),
        max_agent_rounds=int(args.max_agent_rounds),
    )
    print(json.dumps(_json_safe(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
