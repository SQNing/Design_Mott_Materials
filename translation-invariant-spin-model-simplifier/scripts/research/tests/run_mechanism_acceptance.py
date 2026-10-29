#!/usr/bin/env python3
"""Persist generic mechanism studies, their controls and scientific limits."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))
from research.examples import retained_three_level, request_for
from research.tests.test_reductions import spin_model_with_small_term, propose_drop, spin_validation
from research.tests.test_mechanisms import (spin_plan, mechanism_action, retained_plan,
                                           retained_action, single_group_plan)
from research.workflow import prepare_research_task, execute_research_action, inspect_research_task
from research.report import render_research_report
from research.state import write_json, read_json
from research.contracts import code_identity


def request(model, question, tasks, runs):
    value = request_for(model, question, tasks)
    value["budget"]["max_solver_runs"] = runs
    return value


def assessment(run, result, conclusion, extra=None):
    return execute_research_action(run, {
        "action_id": "assessment", "type": "assess",
        "reason": "Interpret the measured responses and explicit controls.",
        "answer_status": "answered_within_scope" if result["scientific_status"] == "usable_within_scope" else "inconclusive",
        "conclusion": conclusion, "scope": result.get("validated_scope", "No numerical experiment launched."),
        "limitations": result.get("scientific_scope") or ["The declared resource budget is insufficient."],
        "evidence": (extra or []) + [{"result_id": result["result_id"],
                                     "path": "calculation.hypotheses" if "hypotheses" in result else "blocker"}]})


def summarize(run, result, output):
    before = inspect_research_task(run)["solver_runs"]
    manifest = render_research_report(run, output)
    view = inspect_research_task(run)
    assert view["solver_runs"] == before and not view["active_actions"]
    return {"scientific_status": result["scientific_status"],
            "hypotheses": [{"hypothesis_id": h["hypothesis_id"], "status": h["status"],
                            "reason": h["reason"], "response": h.get("response")}
                           for h in result.get("hypotheses", [])],
            "observations": [{"observable_id": o["observable_id"], "point_id": o["point_id"],
                             "value": o["value"], "scientific_status": o["scientific_status"]}
                            for o in result.get("observations", [])],
            "solver_runs": view["solver_runs"], "result_new_solver_runs": result.get("solver_runs", 0),
            "report": manifest["report"], "answer_status": view["answer_status"]}


def quantum_action():
    action = mechanism_action()
    action["settings"]["experiments"] = [{"case_id": "levels", "task": "quantum_low_energy",
        "settings": {"supercell_shape": [2, 2, 2], "spin": .5, "eigenvalues": 3, "seed": 31}}]
    action["settings"]["observables"] = [{"observable_id": "frequency", "case_id": "levels",
                                         "kind": "quantum_gap", "level": 2}]
    action["settings"]["hypotheses"] = action["settings"]["hypotheses"][:1]
    return action


def mc_action():
    action = mechanism_action()
    action["settings"]["experiments"] = [{"case_id": "thermal", "task": "classical_monte_carlo",
        "settings": {"supercell_shape": [2, 1, 1], "spin_length": .5, "temperatures": [.7],
                     "sweeps": 24, "burn_in": 8, "seed": 45}}]
    action["settings"]["observables"] = [{"observable_id": "frequency", "case_id": "thermal",
                                         "kind": "mc_energy_per_site", "temperature": .7}]
    action["settings"]["hypotheses"] = action["settings"]["hypotheses"][:1]
    return action


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--resume", action="store_true", help="reuse the same immutable actions and saved results")
    args = parser.parse_args()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=args.resume)
    before_runs = sum(inspect_research_task(p)["solver_runs"] for p in output.iterdir()
                      if (p / "state.json").is_file())
    summary = {"code_identity": code_identity()}
    spin = spin_model_with_small_term(.02, anisotropy=True)

    run = output / "A-reduction-to-mechanism"
    prepare_research_task(request(spin, "Can anisotropy be omitted, and which interaction controls the sampled frequencies?",
                                  ["reduction_validation", "mechanism_test"], 12), run)
    original = (run / "models/model-0001/solver_model.json").read_bytes()
    propose_drop(run)
    reduction = execute_research_action(run, spin_validation("drop"), wait=True)
    assert reduction["validation_status"] == "rejected"
    execute_research_action(run, spin_plan())
    result = execute_research_action(run, mechanism_action(), wait=True)
    assert [h["status"] for h in result["hypotheses"]] == [
        "supported_within_scope", "supported_within_scope", "refuted_within_scope", "supported_within_scope"], result
    assert result["solver_runs"] <= 8
    assert all(e["reused"] for e in result["evidence"] if e["role"] == "control")
    other = mechanism_action("finite-momentum")
    other["settings"]["observables"][0]["q"] = [.25, 0, 0]
    other["settings"]["hypotheses"] = [other["settings"]["hypotheses"][2]]
    finite_q = execute_research_action(run, other, wait=True)
    assert finite_q["hypotheses"][0]["status"] == "supported_within_scope" and finite_q["solver_runs"] == 0
    assert original == (run / "models/model-0001/solver_model.json").read_bytes()
    assessment(run, result,
        "Deleting anisotropy fails the sampled spectrum tolerance. Its isolated removal suppresses the zone-center frequency; "
        "exchange controls the frequency response at the other sampled momentum. These statements concern the specified finite model.",
        [{"result_id": reduction["result_id"], "path": "calculation.metrics"},
         {"result_id": finite_q["result_id"], "path": "calculation.hypotheses"}])
    summary["A"] = summarize(run, result, output / "A-report")
    summary["A"].update(reduction_status=reduction["validation_status"], reduction_metrics=reduction["metrics"],
                        finite_momentum_hypothesis=finite_q["hypotheses"][0],
                        finite_momentum_solver_runs=finite_q["solver_runs"])
    print("A reduction-to-mechanism complete", flush=True)

    run = output / "B-retained-levels"
    prepare_research_task(request(retained_three_level(), "Test onsite control without truncating any local levels.",
                                  ["mechanism_test"], 6), run)
    execute_research_action(run, retained_plan())
    result = execute_research_action(run, retained_action(), wait=True)
    assert all(h["status"] == "supported_within_scope" for h in result["hypotheses"]), result
    assert all(x["local_dimension"] == 3 for x in result["validated_scope"]["realized_cases"])
    assessment(run, result, "At the sampled points the selected onsite scaling raises the ordered harmonic frequency "
               "while the declared local ground-level population stays within tolerance; all three levels are retained.")
    summary["B"] = summarize(run, result, output / "B-report")
    summary["B"]["energy_responses"] = result["energy_responses"]
    print("B retained levels complete", flush=True)

    run = output / "C-finite-quantum"
    prepare_research_task(request(spin, "Test a specified finite-cluster level spacing.", ["mechanism_test"], 3), run)
    execute_research_action(run, single_group_plan())
    result = execute_research_action(run, quantum_action(), wait=True)
    assert result["hypotheses"][0]["status"] == "supported_within_scope", result
    assessment(run, result, "The explicitly selected finite-cluster level spacing increases over the sampled anisotropy factors.")
    summary["C"] = summarize(run, result, output / "C-report")
    summary["C"]["maximum_eigenpair_residual"] = max(
        max(read_json(e["path"])["calculation"]["residual_norms"]) for e in result["evidence"])
    print("C finite quantum complete", flush=True)

    run = output / "D-confounded-controls"
    prepare_research_task(request(spin, "Can simultaneous changes identify either group's mechanism?", ["mechanism_test"], 6), run)
    plan = spin_plan()
    plan["points"] = [
        {"point_id": "control", "factors": {"anisotropy": 1., "exchange": 1.}},
        {"point_id": "joint-half", "factors": {"anisotropy": .5, "exchange": .5}},
        {"point_id": "joint-quarter", "factors": {"anisotropy": .25, "exchange": .25}}]
    execute_research_action(run, plan)
    result = execute_research_action(run, mechanism_action(), wait=True)
    assert all(h["status"] == "inconclusive" for h in result["hypotheses"]), result
    assessment(run, result, "The jointly varied points do not identify either one-group mechanism; isolated controls are needed.")
    summary["D"] = summarize(run, result, output / "D-report")
    print("D missing isolated controls preserved", flush=True)

    run = output / "E-resume"
    prepare_research_task(request(spin, "Resume the same mechanism experiment.", ["mechanism_test"], 6), run)
    execute_research_action(run, single_group_plan())
    action = mechanism_action("persistent")
    action["settings"]["hypotheses"] = action["settings"]["hypotheses"][:2]
    action_path = output / "E-action.json"
    if action_path.exists():
        assert read_json(action_path) == action
    else:
        write_json(action_path, action, exclusive=True)
    started = execute_research_action(run, action)
    if not args.resume:
        assert started["execution_status"] == "running"
    command = [sys.executable, "-B", str(SCRIPTS / "cli/research_workflow.py"),
               "step", "--run-dir", str(run), "--action", str(action_path), "--wait"]
    result = json.loads(subprocess.run(command, check=True, capture_output=True, text=True, timeout=120).stdout)
    repeated = json.loads(subprocess.run(command, check=True, capture_output=True, text=True, timeout=15).stdout)
    assert result["result_id"] == repeated["result_id"]
    assert result["scientific_status"] == "usable_within_scope"
    assert inspect_research_task(run)["solver_runs"] == 6
    assessment(run, result, "Another host process recovered the same mechanism result without repeating numerical jobs.")
    summary["E"] = summarize(run, result, output / "E-report")
    summary["E"]["worker"] = started.get("worker") or next(
        s["execution"]["worker"] for s in inspect_research_task(run)["steps"] if s["action_id"] == "persistent")
    print("E resume complete", flush=True)

    run = output / "F-mc-uncertainty"
    prepare_research_task(request(spin, "Assess the scientific usability of short thermal samples.", ["mechanism_test"], 3), run)
    execute_research_action(run, single_group_plan())
    result = execute_research_action(run, mc_action(), wait=True)
    assert result["scientific_status"] == "inconclusive"
    assert all(not read_json(e["path"])["calculation"]["sampling"]["equilibration_verified"] for e in result["evidence"])
    assessment(run, result, "The recorded short MC samples do not verify equilibration and cannot establish the proposed mechanism.")
    summary["F"] = summarize(run, result, output / "F-report")
    print("F MC uncertainty preserved", flush=True)

    run = output / "G-budget"
    prepare_research_task(request(spin, "Check the full cost before a mechanism study.", ["mechanism_test"], 9), run)
    execute_research_action(run, spin_plan())
    result = execute_research_action(run, mechanism_action(), wait=True)
    assert result["blocker"] == "solver-run-budget-exhausted"
    assessment(run, result, "The planned comparison requires more numerical jobs than the declared budget allows.")
    summary["G"] = summarize(run, result, output / "G-report")
    summary["G"]["blocker"] = result["blocker"]
    assert summary["G"]["solver_runs"] == 0
    assert code_identity() == summary["code_identity"]
    after_runs = sum(inspect_research_task(p)["solver_runs"] for p in output.iterdir()
                     if (p / "state.json").is_file())
    summary["acceptance_invocation"] = {"resumed": args.resume,
        "solver_runs_before": before_runs, "solver_runs_after": after_runs,
        "additional_solver_runs": after_runs - before_runs}
    write_json(output / "summary.json", summary)
    print("MECHANISM_ACCEPTANCE_OK", output / "summary.json", flush=True)


if __name__ == "__main__":
    main()

