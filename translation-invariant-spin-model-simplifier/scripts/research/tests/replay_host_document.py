#!/usr/bin/env python3
"""Replay the recorded host-agent decisions for C, not an automatic text parser."""
import argparse
import json
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))
from research.workflow import prepare_research_task, execute_research_action, inspect_research_task
from research.report import render_research_report
from research.state import write_json
from three_dimensional.examples import cubic_input


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    root = Path(args.output_dir).resolve()
    root.mkdir(parents=True, exist_ok=False)
    fixtures = SCRIPTS / "research/fixtures"
    request = {"source": {"kind": "document", "path": str(fixtures / "host-document-C.txt")},
               "question": "Find the requested finite reference and spectrum after clarifying operator normalization.",
               "requested_tasks": ["classical_ground_state", "harmonic_spectrum"]}
    view = prepare_research_task(request, root / "C-host-document")
    assert view["status"] == "needs_input"
    write_json(root / "C-prepare-view.json", view)
    # This landing reproduces the host's recorded interpretation, not an LLM
    # callback or an expectation injected into a numerical solver.
    model = cubic_input(-.93, {})["model"]
    model["units"] = {"energy": "dimensionless model units", "hbar": 1}
    view = execute_research_action(root / "C-host-document", {
        "action_id": "host-clarification", "type": "provide_input",
        "reason": "Replay the host extraction and the explicit scripted spin-1/2 clarification.",
        "answers": {"operator_normalization": (fixtures / "host-clarification-C.txt").read_text(),
                    "answer_source": "scripted acceptance fixture"},
        "model": model})
    control = prepare_research_task({"model": model, "question": "Structured control."},
                                    root / "C-structured-control")
    assert view["model"]["model_id"] == control["model"]["model_id"]
    ground = execute_research_action(root / "C-host-document", {
        "action_id": "host-ground", "type": "calculate", "task": "classical_ground_state",
        "reason": "Use the clarified physical operator convention.",
        "settings": {"supercell_shape": [2, 2, 2], "spin_length": .5, "starts": 2, "seed": 87}}, wait=True)
    assert ground["scientific_status"] == "usable_within_scope"
    modes = execute_research_action(root / "C-host-document", {
        "action_id": "host-spectrum", "type": "calculate", "task": "harmonic_spectrum",
        "reference_result": "host-ground", "reason": "Check stability about the saved stationary reference.",
        "settings": {"spin": .5, "reduced_momenta": [[0, 0, 0], [.5, 0, 0]]}}, wait=True)
    assert modes["scientific_status"] == "usable_within_scope"
    execute_research_action(root / "C-host-document", {
        "action_id": "host-interpretation", "type": "assess",
        "reason": "Replay the host's finite-scope interpretation of the recorded diagnostics.",
        "answer_status": "answered_within_scope",
        "conclusion": "A stationary finite-cell reference is harmonically stable at the requested momenta.",
        "scope": "2x2x2 periodic cell; two sampled wavevectors.",
        "limitations": ["No infinite-system claim; modes are folded by the reference supercell.",
                       "The clarification is a scripted acceptance reply."],
        "evidence": [{"result_id": "host-ground", "path": "calculation.energy_per_cell"},
                     {"result_id": "host-spectrum", "path": "calculation.stability"}]})
    manifest = render_research_report(root / "C-host-document", root / "C-report")
    assert inspect_research_task(root / "C-host-document")["solver_runs"] == 2
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
