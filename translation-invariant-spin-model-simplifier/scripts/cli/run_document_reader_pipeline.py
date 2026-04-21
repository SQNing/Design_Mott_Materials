#!/usr/bin/env python3
import argparse
from copy import deepcopy
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from classical.build_spin_only_solver_payload import build_spin_only_solver_payload
    from classical.classical_solver_driver import run_classical_solver
    from common.document_reader_downstream_orchestration import orchestrate_document_reader_downstream
else:
    from classical.build_spin_only_solver_payload import build_spin_only_solver_payload
    from classical.classical_solver_driver import run_classical_solver
    from common.document_reader_downstream_orchestration import orchestrate_document_reader_downstream

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
        "classical_dir": str(output_dir / "classical"),
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


def _write_classical_bridge_artifacts(output_dir, bridge_payload, solver_result=None):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "solver_payload.json", bridge_payload)
    if solver_result is not None:
        _write_json(output_dir / "solver_result.json", solver_result)


def _write_downstream_artifacts(output_dir, downstream_result):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "downstream_routes.json", downstream_result.get("downstream_routes", {}))
    _write_json(output_dir / "downstream_results.json", downstream_result.get("downstream_results", {}))
    _write_json(output_dir / "downstream_summary.json", downstream_result.get("downstream_summary", {}))


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
    emit_spin_only_solver_payload=False,
    run_spin_only_classical_solver=False,
    run_downstream_stages=False,
    allow_review_downstream=False,
):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    document_output_dir = output_dir / "document_orchestration"
    simplification_output_dir = output_dir / "simplification"
    classical_output_dir = output_dir / "classical"
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

    if emit_spin_only_solver_payload or run_spin_only_classical_solver:
        try:
            bridge_result = build_spin_only_solver_payload(result)
            bridge_payload = bridge_result.get("payload", {})
            solver_result = None
            if run_spin_only_classical_solver:
                solver_result = run_classical_solver(deepcopy(bridge_payload))
            _write_classical_bridge_artifacts(classical_output_dir, bridge_payload, solver_result=solver_result)
            result["bridge_status"] = bridge_result.get("status")
            result["bridge_payload"] = bridge_payload
            if solver_result is not None:
                result["classical_solver"] = solver_result
            artifacts["solver_payload"] = str(classical_output_dir / "solver_payload.json")
            if solver_result is not None:
                artifacts["solver_result"] = str(classical_output_dir / "solver_result.json")
            if run_downstream_stages and solver_result is not None:
                downstream_payload = deepcopy(bridge_payload)
                if isinstance(solver_result, dict):
                    downstream_payload.update(deepcopy(solver_result))
                downstream_result = orchestrate_document_reader_downstream(
                    downstream_payload,
                    allow_review_execution=bool(allow_review_downstream),
                )
                _write_downstream_artifacts(classical_output_dir, downstream_result)
                result["downstream_status"] = downstream_result.get("downstream_status")
                result["downstream_routes"] = downstream_result.get("downstream_routes", {})
                result["downstream_results"] = downstream_result.get("downstream_results", {})
                result["downstream_summary"] = downstream_result.get("downstream_summary", {})
                artifacts["downstream_routes"] = str(classical_output_dir / "downstream_routes.json")
                artifacts["downstream_results"] = str(classical_output_dir / "downstream_results.json")
                artifacts["downstream_summary"] = str(classical_output_dir / "downstream_summary.json")
        except Exception as exc:
            result["bridge_status"] = "error"
            result["bridge_error"] = {"message": str(exc)}

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
    parser.add_argument("--emit-spin-only-solver-payload", action="store_true")
    parser.add_argument("--run-spin-only-classical-solver", action="store_true")
    parser.add_argument("--run-downstream-stages", action="store_true")
    parser.add_argument("--allow-review-downstream", action="store_true")
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
        emit_spin_only_solver_payload=bool(args.emit_spin_only_solver_payload),
        run_spin_only_classical_solver=bool(args.run_spin_only_classical_solver),
        run_downstream_stages=bool(args.run_downstream_stages),
        allow_review_downstream=bool(args.allow_review_downstream),
    )
    print(json.dumps(_json_safe(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
