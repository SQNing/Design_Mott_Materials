#!/usr/bin/env python3
"""Persist real A/B/D/E workflow demonstrations; C is a host-agent transcript."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))
from research.examples import multisublattice_spin, retained_three_level, request_for
from research.workflow import prepare_research_task, execute_research_action, inspect_research_task
from research.report import render_research_report
from research.state import write_json
from three_dimensional.examples import cubic_input


def do(root, identifier, task, reason, reference=None, **settings):
    action = {"action_id": identifier, "type": "calculate", "task": task,
              "reason": reason, "settings": settings}
    if reference:
        action["reference_result"] = reference
    result = execute_research_action(root, action, wait=True)
    print(root.name, identifier, result["execution_status"], result["scientific_status"], flush=True)
    if result["execution_status"] not in {"succeeded", "reused"}:
        raise RuntimeError(json.dumps(result))
    return result


def assess(run, identifier, status, conclusion, evidence, scope):
    return execute_research_action(run, {
        "action_id": identifier, "type": "assess",
        "reason": "Interpret the recorded evidence within its tested scope.",
        "answer_status": status, "conclusion": conclusion, "scope": scope,
        "limitations": ["These small calculations do not establish an infinite-system phase diagram."],
        "evidence": [{"result_id": result, "path": path} for result, path in evidence]})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    summary = {}
    run = output / "A-multisublattice"
    prepare_research_task(request_for(multisublattice_spin(),
        "Find and check a finite periodic reference for this four-sublattice triclinic model.",
        ["classical_ground_state", "harmonic_spectrum"]), run)
    first = do(run, "initial", "classical_ground_state", "Obtain an initial finite-cell candidate.",
               supercell_shape=[1, 1, 1], spin_length=.5, starts=1, maxiter=1, seed=28)
    refined = do(run, "refine", "classical_ground_state",
        "The initial run has only one start; check independent seeds and tighter minimization.",
        supercell_shape=[1, 1, 1], spin_length=.5, starts=4, seed=617)
    spectrum = do(run, "spectrum", "harmonic_spectrum",
        "Check the saved candidate's stationarity and quadratic stability at three wavevectors.",
        reference="refine", spin=.5, reduced_momenta=[[0, 0, 0], [.21, .17, .13], [.5, 0, 0]])
    assert refined["scientific_status"] == spectrum["scientific_status"] == "usable_within_scope"
    assess(run, "assessment", "answered_within_scope",
        "The refined periodic candidate is stationary and harmonically stable at the sampled wavevectors.",
        [("refine", "calculation.energy_per_cell"), ("spectrum", "calculation.stability")],
        "Four-site primitive periodic cell; independent starts; three q points.")
    summary["A"] = {"energy_per_cell": refined["calculation"]["energy_per_cell"],
                    "initial_energy": first["calculation"]["energy_per_cell"],
                    "report": render_research_report(run, output / "A-report")["report"]}

    run = output / "B-retained-local"
    prepare_research_task(request_for(retained_three_level(),
        "Optimize the full three-level onsite/pair model and obtain all local harmonic modes.",
        ["classical_ground_state", "harmonic_spectrum"]), run)
    classical = do(run, "local-rays", "classical_ground_state",
        "Search the full CP local space, retaining onsite and complex pair matrix.",
        starts=2, seed=2, max_linear_size=1, max_sweeps=120)
    modes = do(run, "gswt", "harmonic_spectrum", "Reuse the local rays without another classical search.",
        reference="local-rays", reduced_momenta=[[0, 0, 0], [.25, 0, 0]])
    assert classical["scientific_status"] == modes["scientific_status"] == "usable_within_scope"
    assess(run, "assessment", "answered_within_scope",
        "A stationary retained-space product state and two stable harmonic branches were obtained.",
        [("local-rays", "calculation.energy_per_cell"), ("gswt", "calculation.stability")],
        "One-cell product state; full three-dimensional local Hilbert space; two q points.")
    summary["B"] = {"energy_per_cell": classical["calculation"]["energy_per_cell"],
                    "onsite_term_count": modes["calculation"]["onsite_term_count"],
                    "pair_term_count": modes["calculation"]["pair_term_count"],
                    "report": render_research_report(run, output / "B-report")["report"]}

    # A new process reattaches to an existing active worker, then a second process
    # repeats the completed request. Neither starts another calculation.
    run = output / "D-resume"
    prepare_research_task(request_for(multisublattice_spin(),
        "Resume an in-progress finite classical calculation.", ["classical_ground_state"]), run)
    action = {"action_id": "persistent", "type": "calculate", "task": "classical_ground_state",
              "reason": "Exercise continuation while the worker remains active.",
              "settings": {"supercell_shape": [2, 2, 1], "spin_length": .5, "starts": 3, "seed": 19}}
    path = output / "D-action.json"
    write_json(path, action)
    started = execute_research_action(run, action)
    assert started["execution_status"] == "running"
    command = [sys.executable, "-B", str(SCRIPTS / "cli/research_workflow.py"),
               "step", "--run-dir", str(run), "--action", str(path), "--wait"]
    result = json.loads(subprocess.run(command, check=True, capture_output=True, text=True, timeout=120).stdout)
    repeated = json.loads(subprocess.run(command, check=True, capture_output=True, text=True, timeout=15).stdout)
    assert result["result_id"] == repeated["result_id"]
    assert inspect_research_task(run)["solver_runs"] == 1
    assess(run, "assessment", "answered_within_scope",
        "A second host process recovered the same worker result without another solve.",
        [("persistent", "calculation.energy_per_cell")], "The recorded finite periodic classical calculation.")
    summary["D"] = {"solver_runs": 1, "worker": started["worker"],
                    "report": render_research_report(run, output / "D-report")["report"]}

    run = output / "E-mc-quantum"
    prepare_research_task(request_for(cubic_input(-.8, {})["model"],
        "Obtain small finite-temperature samples and a finite quantum spectrum.",
        ["classical_monte_carlo", "quantum_low_energy"]), run)
    mc = do(run, "mc", "classical_monte_carlo", "Check sampling and diagnostic output on a tiny periodic system.",
        supercell_shape=[2, 1, 1], spin_length=.5, temperatures=[.7, 1.1], sweeps=32, burn_in=8, seed=91)
    quantum = do(run, "quantum", "quantum_low_energy", "Check low-energy residuals for the full finite quantum model.",
        supercell_shape=[2, 2, 2], spin=.5, eigenvalues=2, seed=92)
    assert mc["scientific_status"] == "inconclusive"
    assert quantum["scientific_status"] == "usable_within_scope"
    assess(run, "assessment", "partial",
        "Finite-cluster quantum eigenpairs converged; short MC samples do not establish equilibration.",
        [("mc", "calculation.sampling"), ("quantum", "calculation.residual_norms")],
        "Tiny finite periodic systems; temperatures in model energy units with k_B=1.")
    summary["E"] = {"quantum_residuals": quantum["calculation"]["residual_norms"],
                    "mc_status": mc["scientific_status"],
                    "report": render_research_report(run, output / "E-report")["report"]}
    write_json(output / "summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
