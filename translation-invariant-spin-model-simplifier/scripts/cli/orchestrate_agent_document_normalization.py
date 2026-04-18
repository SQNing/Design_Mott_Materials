#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cli.run_agent_document_normalization_demo import (
    _json_safe,
    _load_agent_normalized_document,
    run_agent_document_normalization_demo,
)


def run_agent_document_normalization_orchestrator(
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
    return run_agent_document_normalization_demo(
        text,
        source_path=source_path,
        selected_model_candidate=selected_model_candidate,
        selected_local_bond_family=selected_local_bond_family,
        selected_coordinate_convention=selected_coordinate_convention,
        output_dir=output_dir,
        agent_normalized_document=agent_normalized_document,
        agent_command=agent_command,
        use_request_example_payload=use_request_example_payload,
        max_agent_rounds=max_agent_rounds,
    )


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

    result = run_agent_document_normalization_orchestrator(
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
