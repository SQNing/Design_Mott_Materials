#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cli.normalize_document_with_agent import run_document_normalization_with_agent
from input.agent_document_prompt_builder import (
    build_agent_document_prompt_bundle,
    build_agent_document_followup_prompt_bundle,
    render_agent_document_prompt,
    render_agent_document_followup_prompt,
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


def _write_json(path, payload):
    Path(path).write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True), encoding="utf-8")


def _write_text(path, text):
    Path(path).write_text(str(text), encoding="utf-8")


def _execute_agent_command(agent_command, prompt_text):
    if isinstance(agent_command, str):
        completed = subprocess.run(
            agent_command,
            input=prompt_text,
            capture_output=True,
            text=True,
            shell=True,
            check=True,
        )
    else:
        completed = subprocess.run(
            list(agent_command),
            input=prompt_text,
            capture_output=True,
            text=True,
            check=True,
        )
    stdout = (completed.stdout or "").strip()
    if not stdout:
        raise ValueError("agent command returned empty stdout; expected agent_normalized_document JSON")
    return json.loads(stdout)


def _current_agent_document_from_final_result(final_result):
    normalized_model = dict((final_result or {}).get("normalized_model") or {})
    document_intermediate = dict(normalized_model.get("document_intermediate") or {})
    return {
        "source_document": dict((document_intermediate.get("source_document") or {})),
        "model_candidates": list(document_intermediate.get("model_candidates") or []),
        "candidate_models": dict(document_intermediate.get("candidate_models") or {}),
        "parameter_registry": dict(document_intermediate.get("parameter_registry_metadata") or document_intermediate.get("parameter_registry") or {}),
        "evidence_items": list(document_intermediate.get("evidence_items") or []),
        "unresolved_items": list(document_intermediate.get("unresolved_items") or []),
        "unsupported_features": list(document_intermediate.get("unsupported_features") or []),
    }


def _followup_selection_context_from_final_result(final_result):
    normalized_model = dict((final_result or {}).get("normalized_model") or {})
    document_intermediate = dict(normalized_model.get("document_intermediate") or {})
    return {
        "selected_model_candidate": document_intermediate.get("selected_model_candidate"),
        "selected_local_bond_family": document_intermediate.get("selected_local_bond_family"),
        "selected_coordinate_convention": document_intermediate.get("selected_coordinate_convention"),
    }


def _build_followup_prompt_artifacts(source_text, final_result):
    normalized_model = dict((final_result or {}).get("normalized_model") or {})
    document_intermediate = dict(normalized_model.get("document_intermediate") or {})
    verification_report = dict(document_intermediate.get("verification_report") or {})
    if verification_report.get("status") != "needs_review":
        return None
    current_agent_document = _current_agent_document_from_final_result(final_result)
    selection_context = _followup_selection_context_from_final_result(final_result)
    bundle = build_agent_document_followup_prompt_bundle(
        source_text,
        current_agent_document,
        verification_report,
        selection_context=selection_context,
    )
    prompt = render_agent_document_followup_prompt(
        source_text,
        current_agent_document,
        verification_report,
        selection_context=selection_context,
    )
    return {
        "bundle": bundle,
        "prompt": prompt,
    }


def _classify_agent_review_category(findings):
    evidence_only_ids = {
        "parameter_registry_missing_evidence",
        "candidate_models_missing_evidence",
        "parameter_entry_missing_evidence",
        "candidate_model_missing_evidence",
        "candidate_model_entry_missing_evidence",
    }
    evidence_present = False
    semantic_present = False
    for entry in list(findings or []):
        if not isinstance(entry, dict):
            continue
        finding_id = str(entry.get("id") or "").strip()
        if not finding_id:
            continue
        if finding_id in evidence_only_ids:
            evidence_present = True
        else:
            semantic_present = True
    if evidence_present and semantic_present:
        return "mixed"
    if evidence_present:
        return "evidence_gap"
    if semantic_present:
        return "semantic_conflict"
    return "needs_review"


def _recommended_next_step_for_review_category(review_category):
    if review_category == "evidence_gap":
        return (
            "Add explicit evidence_refs/evidence_values for the kept entries, then rerun the agent revision or review manually."
        )
    if review_category == "semantic_conflict":
        return (
            "Revise the agent output against the latest followup prompt, then inspect the remaining semantic conflicts manually if they persist."
        )
    if review_category == "mixed":
        return (
            "First restore the evidence-backed entries, then rerun the latest followup prompt to resolve the remaining semantic conflicts."
        )
    return "Run another agent revision using the latest followup prompt, or inspect the remaining findings manually."


def _build_agent_review_summary(source_text, final_result, *, completed_agent_rounds, stop_reason):
    normalized_model = dict((final_result or {}).get("normalized_model") or {})
    document_intermediate = dict(normalized_model.get("document_intermediate") or {})
    verification_report = dict(document_intermediate.get("verification_report") or {})
    if verification_report.get("status") != "needs_review":
        return None

    current_agent_document = _current_agent_document_from_final_result(final_result)
    selection_context = _followup_selection_context_from_final_result(final_result)
    followup_bundle = build_agent_document_followup_prompt_bundle(
        source_text,
        current_agent_document,
        verification_report,
        selection_context=selection_context,
    )
    findings = list(verification_report.get("findings") or [])
    review_category = _classify_agent_review_category(findings)
    return {
        "status": "needs_review",
        "reason": str(stop_reason or "review_requested"),
        "review_category": review_category,
        "completed_agent_rounds": int(completed_agent_rounds),
        "remaining_finding_ids": [
            str(entry.get("id"))
            for entry in findings
            if isinstance(entry, dict) and entry.get("id")
        ],
        "remaining_findings": findings,
        "priority_corrections": list(followup_bundle.get("priority_corrections") or []),
        "selection_context": selection_context,
        "recommended_next_step": _recommended_next_step_for_review_category(review_category),
    }


def _write_followup_prompt_artifacts(output_dir, source_text, final_result, *, prefix=None):
    artifacts = _build_followup_prompt_artifacts(source_text, final_result)
    if artifacts is None:
        return False
    bundle = artifacts["bundle"]
    prompt = artifacts["prompt"]
    if prefix:
        _write_json(output_dir / f"{prefix}_followup_prompt_bundle.json", bundle)
        _write_text(output_dir / f"{prefix}_followup_agent_prompt.txt", prompt)
    _write_json(output_dir / "followup_prompt_bundle.json", bundle)
    _write_text(output_dir / "followup_agent_prompt.txt", prompt)
    return True


def run_agent_document_normalization_demo(
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

    step1 = run_document_normalization_with_agent(
        text,
        source_path=source_path,
        selected_model_candidate=selected_model_candidate,
        selected_local_bond_family=selected_local_bond_family,
        selected_coordinate_convention=selected_coordinate_convention,
        agent_normalized_document=None,
    )
    _write_json(output_dir / "step1_request.json", step1)

    if step1.get("status") != "needs_agent_normalization":
        _write_json(output_dir / "final_result.json", step1)
        return step1

    request = dict(step1.get("agent_normalization_request", {}))
    prompt_bundle = build_agent_document_prompt_bundle(text, request)
    prompt_text = render_agent_document_prompt(text, request)
    _write_json(output_dir / "prompt_bundle.json", prompt_bundle)
    _write_text(output_dir / "agent_prompt.txt", prompt_text)

    chosen_agent_payload = agent_normalized_document
    if chosen_agent_payload is None and agent_command is not None:
        chosen_agent_payload = _execute_agent_command(agent_command, prompt_text)
    if chosen_agent_payload is None and use_request_example_payload:
        chosen_agent_payload = (
            ((step1.get("agent_normalization_request") or {}).get("example_payload"))
            if isinstance(step1, dict)
            else None
        )
    if chosen_agent_payload is None:
        return step1

    current_payload = chosen_agent_payload
    final_result = step1
    total_rounds = max(1, int(max_agent_rounds))
    completed_rounds = 0
    stop_reason = None
    for round_index in range(1, total_rounds + 1):
        _write_json(output_dir / f"round{round_index}_agent_normalized_document.json", current_payload)
        if round_index == 1:
            _write_json(output_dir / "agent_normalized_document.json", current_payload)
        final_result = run_document_normalization_with_agent(
            text,
            source_path=source_path,
            selected_model_candidate=selected_model_candidate,
            selected_local_bond_family=selected_local_bond_family,
            selected_coordinate_convention=selected_coordinate_convention,
            agent_normalized_document=current_payload,
        )
        completed_rounds = round_index
        _write_json(output_dir / f"round{round_index}_final_result.json", final_result)
        _write_json(output_dir / "final_result.json", final_result)
        wrote_followup = _write_followup_prompt_artifacts(
            output_dir,
            text,
            final_result,
            prefix=f"round{round_index}",
        )
        if not wrote_followup:
            stop_reason = "accepted"
            break
        if agent_command is None:
            stop_reason = "review_requested"
            break
        if round_index >= total_rounds:
            stop_reason = "max_agent_rounds_exhausted"
            break
        current_payload = _execute_agent_command(
            agent_command,
            (output_dir / f"round{round_index}_followup_agent_prompt.txt").read_text(encoding="utf-8"),
        )
    if stop_reason is None:
        stop_reason = "accepted"
    agent_review = _build_agent_review_summary(
        text,
        final_result,
        completed_agent_rounds=completed_rounds,
        stop_reason=stop_reason,
    )
    if agent_review is not None:
        final_result = dict(final_result)
        final_result["status"] = "needs_review"
        final_result["agent_review"] = agent_review
        _write_json(output_dir / "agent_review.json", agent_review)
        _write_json(output_dir / "final_result.json", final_result)
    return final_result


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
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--agent-normalized-document-json", default=None)
    parser.add_argument("--agent-normalized-document-file", default=None)
    parser.add_argument("--agent-command", default=None)
    parser.add_argument("--use-request-example-payload", action="store_true")
    parser.add_argument("--max-agent-rounds", type=int, default=1)
    args = parser.parse_args()

    result = run_agent_document_normalization_demo(
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
