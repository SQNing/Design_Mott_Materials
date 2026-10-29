"""Scientific acceptance checks through the public workflow, with real kernels."""
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))
from research.examples import multisublattice_spin, retained_three_level, request_for
from research.workflow import prepare_research_task, execute_research_action, inspect_research_task
from research.report import render_research_report


def action(name, task, **settings):
    return {"action_id": name, "type": "calculate", "task": task,
            "reason": "Perform the specified finite-model diagnostic.", "settings": settings}


def test_multisublattice_diagnostic_refinement_spectrum_and_assessment(tmp_path):
    run = tmp_path / "multi"
    req = request_for(multisublattice_spin(), "Find a finite-cell reference and its spectrum.",
                      ["classical_ground_state", "harmonic_spectrum"])
    view = prepare_research_task(req, run)
    assert view["status"] == "ready"
    assert view["model"]["site_count"] == 4
    assert view["model"]["term_count"] == 18
    first = execute_research_action(run, action("initial", "classical_ground_state",
        supercell_shape=[1, 1, 1], spin_length=.5, starts=1, maxiter=1, seed=28), wait=True)
    assert first["execution_status"] == "succeeded", first
    # Its single-start, finite-cell scope calls for an independent robustness check.
    assert first["diagnostics"]
    refined = execute_research_action(run, action("refine", "classical_ground_state",
        supercell_shape=[1, 1, 1], spin_length=.5, starts=4, seed=617), wait=True)
    assert refined["scientific_status"] == "usable_within_scope", refined
    expected = -.25 * 1.17 * sum(.73 + .013 * i for i in range(18))
    assert refined["calculation"]["energy_per_cell"] == pytest.approx(expected, abs=2e-7)
    spectrum_action = action("spectrum", "harmonic_spectrum", spin=.5,
        reduced_momenta=[[0, 0, 0], [.21, .17, .13], [.5, 0, 0]])
    spectrum_action["reference_result"] = "refine"
    spectrum = execute_research_action(run, spectrum_action, wait=True)
    assert spectrum["scientific_status"] == "usable_within_scope", spectrum
    assert all(len(row["bands"]) == 4 for row in spectrum["calculation"]["dispersion"])
    assert "classical_optimization" not in spectrum["calculation"]
    view = execute_research_action(run, {
        "action_id": "conclude", "type": "assess", "reason": "Interpret recorded energies and harmonic stability.",
        "answer_status": "answered_within_scope", "conclusion": "A stable finite-cell variational reference was found.",
        "scope": "The tested periodic cell and three wavevectors.",
        "limitations": ["No infinite-lattice certification."],
        "evidence": [{"result_id": "refine", "path": "calculation.energy_per_cell"},
                     {"result_id": "spectrum", "path": "calculation.stability"}]})
    assert view["answer_status"] == "answered_within_scope"
    manifest = render_research_report(run, tmp_path / "report")
    assert manifest["calculations_started"] == 0


def test_general_three_level_onsite_pair_local_rays_and_gswt(tmp_path):
    run = tmp_path / "retained"
    prepare_research_task(request_for(retained_three_level(), "Find the full retained-space reference and modes.",
                                      ["classical_ground_state", "harmonic_spectrum"]), run)
    state = execute_research_action(run, action("local-rays", "classical_ground_state",
        starts=2, seed=2, max_linear_size=1, max_sweeps=120), wait=True)
    assert state["scientific_status"] == "usable_within_scope", state
    calc = state["calculation"]
    assert calc["onsite_term_count"] == calc["pair_term_count"] == 1
    assert calc["energy_per_cell"] == pytest.approx(-.51, abs=1e-7)
    assert calc["classical_state"]["state_kind"] == "local_rays"
    assert len(calc["classical_state"]["local_rays"][0]["vector"]) == 3
    spectrum_action = action("gswt", "harmonic_spectrum", reduced_momenta=[[0, 0, 0], [.25, 0, 0]])
    spectrum_action["reference_result"] = "local-rays"
    modes = execute_research_action(run, spectrum_action, wait=True)
    assert modes["scientific_status"] == "usable_within_scope", modes
    assert modes["calculation"]["local_dimension"] == 3
    assert all(len(row["bands"]) == 2 for row in modes["calculation"]["dispersion"])
    assert modes["calculation"]["onsite_term_count"] == 1
    assert modes["reference_result"] == "local-rays"
    assert inspect_research_task(run)["solver_runs"] == 2


def test_resume_from_other_host_process_deduplicates_active_action(tmp_path):
    run = tmp_path / "resume"
    req = request_for(multisublattice_spin(), "Check continuation of a finite calculation.", ["classical_ground_state"])
    prepare_research_task(req, run)
    calculation = action("running", "classical_ground_state", supercell_shape=[2, 2, 1],
                         spin_length=.5, starts=3, seed=19)
    started = execute_research_action(run, calculation)
    assert started["execution_status"] == "running"
    again = execute_research_action(run, calculation)
    assert again["result_id"] == started["result_id"]
    assert inspect_research_task(run)["solver_runs"] == 1
    request_path = tmp_path / "action.json"
    request_path.write_text(json.dumps(calculation))
    completed = subprocess.run([sys.executable, "-B", str(SCRIPTS / "cli/research_workflow.py"),
        "step", "--run-dir", str(run), "--action", str(request_path), "--wait"],
        text=True, capture_output=True, check=True, timeout=90)
    result = json.loads(completed.stdout)
    assert result["execution_status"] == "succeeded", result
    assert inspect_research_task(run)["solver_runs"] == 1


def test_real_mc_quantum_and_resource_stop_are_not_overclaimed(tmp_path):
    from three_dimensional.examples import cubic_input
    run = tmp_path / "other-tasks"
    model = cubic_input(-.8, {})["model"]
    prepare_research_task(request_for(model, "Obtain finite-temperature samples and a tiny quantum spectrum.",
        ["classical_monte_carlo", "quantum_low_energy"]), run)
    mc = execute_research_action(run, action("mc", "classical_monte_carlo", supercell_shape=[2, 1, 1],
        spin_length=.5, temperatures=[.7, 1.1], sweeps=32, burn_in=8, seed=91), wait=True)
    assert mc["execution_status"] == "succeeded", mc
    assert mc["scientific_status"] == "inconclusive"
    assert mc["calculation"]["grid"][0]["energy_stderr"] >= 0
    assert mc["calculation"]["sampling"]["equilibration_verified"] is False
    quantum = execute_research_action(run, action("quantum", "quantum_low_energy",
        supercell_shape=[2, 2, 2], spin=.5, eigenvalues=2, seed=92), wait=True)
    assert quantum["scientific_status"] == "usable_within_scope", quantum
    assert max(quantum["calculation"]["residual_norms"]) < 1e-8
    # A separate wall-limited job must leave a terminal failure, not an orphan success.
    stopped = execute_research_action(run, action("bounded", "classical_ground_state",
        supercell_shape=[2, 2, 2], spin_length=.5, starts=4, wall_time_seconds=.001), wait=True)
    assert stopped["execution_status"] == "timed_out", stopped
    assert stopped["scientific_status"] == "inconclusive"


def test_independent_ewald_has_explicit_boundary_and_cutoff_diagnostics(tmp_path):
    run = tmp_path / "ewald"
    geometry = {"kind": "dipolar_geometry", "lattice_vectors": np.eye(3).tolist(),
                "fractional_positions": [[0, 0, 0]], "moments": [[0, 0, 1]]}
    ready = prepare_research_task(request_for(geometry, "Evaluate a separate dipolar geometry.", ["dipolar_ewald"]), run)
    assert ready["status"] == "ready"
    result = execute_research_action(run, action("dipoles", "dipolar_ewald",
        alpha=2., real_cutoff=4., reciprocal_cutoff=15., boundary="tin_foil", cutoff_tolerance=1e-4), wait=True)
    assert result["execution_status"] == "succeeded", result
    assert result["calculation"]["boundary"] == "tin_foil"
    assert result["calculation"]["cutoff_comparison"]["rigorous_error_bound"] is False
    assert "Independent dipole geometry" in " ".join(result["scientific_scope"])
