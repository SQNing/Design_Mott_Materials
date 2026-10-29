#!/usr/bin/env python3
"""Persist real reduction comparisons and resumability evidence."""
import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))
# These are test inputs and host actions, never expected answers passed to solvers.
from research.tests.test_reductions import (
    spin_model_with_small_term, spin_validation, validation, propose_drop)
from research.examples import retained_three_level, request_for
from research.workflow import prepare_research_task, execute_research_action, inspect_research_task
from research.report import render_research_report
from research.state import write_json


def assess(run, result, conclusion):
    return execute_research_action(run, {
        "action_id": "assessment", "type": "assess",
        "reason": "Interpret the saved comparison in its recorded scope.",
        "answer_status": "answered_within_scope", "conclusion": conclusion,
        "scope": result["validated_scope"],
        "limitations": result["scientific_scope"],
        "evidence": [{"result_id": result["result_id"], "path": "calculation.metrics"}]})


def summarize(run, result, report_dir):
    before = inspect_research_task(run)["solver_runs"]
    manifest = render_research_report(run, report_dir)
    after = inspect_research_task(run)
    assert after["solver_runs"] == before and not after["active_actions"]
    return {"verdict": result.get("validation_status"),
            "scientific_status": result["scientific_status"],
            "solver_runs": after["solver_runs"], "metrics": result.get("metrics"),
            "report": manifest["report"], "model_id": after["model"]["model_id"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    output = Path(parser.parse_args().output_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    summary = {}
    for name, strength, anisotropy, expected in [
        ("A-weak-exchange", .001, False, "accepted_within_scope"),
        ("B-small-anisotropy", .02, True, "rejected")]:
        run = output / name
        prepare_research_task(request_for(spin_model_with_small_term(strength, anisotropy=anisotropy),
            "Can the explicitly selected interaction be neglected for these observables?",
            ["reduction_validation"]), run)
        original = (run / "models/model-0001/solver_model.json").read_bytes()
        candidate = propose_drop(run)
        assert candidate["status"] == "ready"
        result = execute_research_action(run, spin_validation("drop"), wait=True)
        assert result["validation_status"] == expected, result
        assert original == (run / "models/model-0001/solver_model.json").read_bytes()
        assess(run, result, "The candidate " + ("meets" if expected == "accepted_within_scope" else "fails") +
               " the specified tolerances for the recorded finite observables.")
        summary[name] = summarize(run, result, output / (name + "-report"))
        print(name, expected, flush=True)

    for name, embedding, expected in [
        ("C-two-level", [[1, 0], [0, 1], [0, 0]], "accepted_within_scope"),
        ("D-wrong-subspace", [[0, 0], [1, 0], [0, 1]], "rejected")]:
        run = output / name
        model = retained_three_level()
        model["term_attachments"]["site_terms"][0]["payload"]["matrix"]["data"][2][2] = 10.
        request = request_for(model, "Does the selected two-level projection preserve the tested low-energy sector?",
                              ["reduction_validation"])
        request["budget"]["max_solver_runs"] = 4
        prepare_research_task(request, run)
        execute_research_action(run, {"action_id": "candidate", "type": "propose_reduction",
            "reason": "Check this explicit local subspace against all three retained states.",
            "transformation": {"kind": "project_local_space", "isometry": embedding}})
        result = execute_research_action(run, validation("candidate"), wait=True)
        assert result["validation_status"] == expected, result
        if expected == "accepted_within_scope":
            tighter = execute_research_action(run, validation("candidate", "tighter", .01), wait=True)
            assert tighter["validation_status"] == expected and tighter["solver_runs"] == 0
            wide_action = validation("candidate", "wide-window")
            wide_action["settings"]["energy_window_max"] = 20.
            wide = execute_research_action(run, wide_action, wait=True)
            assert wide["validation_status"] == "rejected" and wide["solver_runs"] == 0
            summary["C-window-comparison"] = {
                "narrow_window_verdict": result["validation_status"], "tighter_tolerance_solver_runs": 0,
                "wide_window_verdict": wide["validation_status"], "wide_window_solver_runs": 0,
                "wide_window_metrics": wide["metrics"]}
        assess(run, result, "The selected local subspace " +
               ("meets" if expected == "accepted_within_scope" else "fails") +
               " the recorded low-energy tolerances; no conclusion applies above the tested window.")
        summary[name] = summarize(run, result, output / (name + "-report"))
        print(name, expected, flush=True)

    run = output / "E-resume"
    prepare_research_task(request_for(spin_model_with_small_term(.001),
        "Resume the same full/candidate comparison from another host process.", ["reduction_validation"]), run)
    propose_drop(run)
    action = spin_validation("drop", "persistent")
    action_path = output / "E-action.json"
    write_json(action_path, action)
    started = execute_research_action(run, action)
    assert started["execution_status"] == "running"
    command = [sys.executable, "-B", str(SCRIPTS / "cli/research_workflow.py"),
               "step", "--run-dir", str(run), "--action", str(action_path), "--wait"]
    result = json.loads(subprocess.run(command, check=True, capture_output=True, text=True, timeout=120).stdout)
    again = json.loads(subprocess.run(command, check=True, capture_output=True, text=True, timeout=15).stdout)
    assert result["validation_status"] == "accepted_within_scope"
    assert again["result_id"] == result["result_id"]
    assert inspect_research_task(run)["solver_runs"] == 4
    assess(run, result, "The same finite comparison was recovered without extra solver calls.")
    summary["E-resume"] = summarize(run, result, output / "E-resume-report")
    summary["E-resume"]["worker"] = started["worker"]
    print("E-resume", result["validation_status"], flush=True)

    run = output / "F-budget"
    request = request_for(spin_model_with_small_term(.001), "Check the cost before launching a comparison.",
                          ["reduction_validation"])
    request["budget"]["max_solver_runs"] = 3
    prepare_research_task(request, run)
    propose_drop(run)
    result = execute_research_action(run, spin_validation("drop"), wait=True)
    assert result["blocker"] == "solver-run-budget-exhausted"
    summary["F-budget"] = summarize(run, result, output / "F-budget-report")
    summary["F-budget"]["blocker"] = result["blocker"]
    assert summary["F-budget"]["solver_runs"] == 0
    write_json(output / "summary.json", summary)
    print("ACCEPTANCE_OK", output / "summary.json", flush=True)


if __name__ == "__main__":
    main()

