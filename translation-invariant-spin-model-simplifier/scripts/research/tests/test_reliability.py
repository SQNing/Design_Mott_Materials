"""Recovery accounting and explicit ground-state claims through public APIs."""
import copy
import json
from pathlib import Path
import socket
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from research.state import collect_steps, compute_seconds, read_json, write_json
from research.workflow import prepare_research_task, execute_research_action, inspect_research_task
from research.report import render_research_report
from three_dimensional.examples import cubic_input


def interrupted_step(root, elapsed=4.25):
    step = root / "steps" / "interrupted"
    write_json(step / "execution.json", {
        "status": "running", "counted": True, "started_at": 1000.,
        "timeout_seconds": 30., "solver_runs": 1,
        "worker": {"host": socket.gethostname(), "pid": 2147483647, "start_ticks": "0"}})
    write_json(step / "action.json", {"action_id": "interrupted", "type": "calculate",
        "task": "classical_ground_state", "reason": "Retain a previously interrupted calculation."})
    if elapsed is not None:
        write_json(step / "timing.json", {"result_id": "interrupted", "elapsed_seconds": elapsed,
            "updated_at": 1000.+elapsed, "terminal": False})
    return step


def test_interrupted_legacy_duration_does_not_grow_with_idle_clock(monkeypatch):
    steps = [{"execution": {"status": "interrupted", "counted": True,
              "started_at": 1000., "timeout_seconds": 30.}}]
    monkeypatch.setattr("research.state.time.time", lambda: 5000.)
    first = compute_seconds(steps)
    monkeypatch.setattr("research.state.time.time", lambda: 500000.)
    assert compute_seconds(steps) == first == 30.


def test_interrupted_checkpoint_is_charged_once_without_rewriting_old_records(tmp_path, monkeypatch):
    step = interrupted_step(tmp_path)
    before = (step / "execution.json").read_bytes()
    monkeypatch.setattr("research.state.time.time", lambda: 5000.)
    steps = collect_steps(tmp_path, {"steps": ["interrupted"]})
    assert steps[0]["execution"]["status"] == "interrupted"
    assert compute_seconds(steps) == 4.25
    assert steps[0]["execution"]["time_accounting"]["uncertain"] is True
    monkeypatch.setattr("research.state.time.time", lambda: 500000.)
    assert compute_seconds(collect_steps(tmp_path, {"steps": ["interrupted"]})) == 4.25
    assert (step / "execution.json").read_bytes() == before


def test_completed_child_supplies_duration_when_supervisor_was_lost(tmp_path):
    step = interrupted_step(tmp_path)
    write_json(step / "computation-result.json", {"compute_seconds": 5.5, "finished_at": 1005.5})
    steps = collect_steps(tmp_path, {"steps": ["interrupted"]})
    assert compute_seconds(steps) == 5.5
    assert steps[0]["execution"]["time_accounting"]["uncertain"] is False


def test_slow_startup_record_read_is_not_counted_twice(tmp_path, monkeypatch):
    from research import worker
    directory = tmp_path / "timing"
    write_json(directory / "execution.json", {"started_at": 1000.})
    clock = {"wall": 1001., "monotonic": 10.}
    original_read = worker.read_json

    def slow_read(path):
        if path.name == "execution.json":
            clock["wall"] += 3.
            clock["monotonic"] += 3.
        return original_read(path)

    class FinishedChild:
        pid = 2147483647
        returncode = 0

        def poll(self):
            return self.returncode

    monkeypatch.setattr(worker, "read_json", slow_read)
    monkeypatch.setattr(worker.time, "time", lambda: clock["wall"])
    monkeypatch.setattr(worker.time, "monotonic", lambda: clock["monotonic"])
    monkeypatch.setattr(worker.subprocess, "Popen", lambda *args, **kwargs: FinishedChild())
    worker.supervise(directory, {"result_id": "timing", "model_id": "model", "task": "classical_ground_state",
        "timeout": 30., "code_identity": {}})
    assert read_json(directory / "result.json")["compute_seconds"] == 4.
    assert read_json(directory / "timing.json")["elapsed_seconds"] == 4.


def request(model=None):
    return {"model": model or cubic_input(-1., {})["model"],
        "question": "Find and explicitly assess a finite-cell reference.",
        "requested_tasks": ["classical_ground_state"],
        "budget": {"max_solver_runs": 6, "max_wall_time_seconds": 60., "max_memory_mb": 2048}}


def ground(identifier="ground", **settings):
    return {"action_id": identifier, "type": "calculate", "task": "classical_ground_state",
        "reason": "Check the complete finite periodic model.",
        "settings": {"supercell_shape": [2, 2, 2], "spin_length": .5,
                     "starts": 1, "seed": 17, **settings}}


def assessment(identifier, claim, result="ground"):
    return {"action_id": identifier, "type": "assess", "claim_level": claim,
        "reason": "Limit the physical statement to its numerical evidence.",
        "answer_status": "answered_within_scope", "conclusion": "The declared claim is supported.",
        "scope": "The recorded finite periodic cell.", "limitations": ["No thermodynamic-limit proof."],
        "evidence": [{"result_id": result, "path": "calculation.energy_per_cell"}]}


def test_public_resume_uses_recorded_time_and_new_result_has_terminal_timing(tmp_path):
    run = tmp_path / "run"
    prepare_research_task(request(), run)
    interrupted_step(run)
    state = read_json(run / "state.json")
    state["steps"].append("interrupted")
    write_json(run / "state.json", state)
    assert inspect_research_task(run)["compute_seconds"] == 4.25
    result = execute_research_action(run, ground(), wait=True)
    assert result["execution_status"] == "succeeded", result
    assert result["compute_seconds"] > 0
    timing = read_json(run / "steps/ground/timing.json")
    assert timing["terminal"] is True
    view = inspect_research_task(run)
    assert view["solver_runs"] == 2
    assert view["compute_seconds"] == pytest.approx(4.25 + result["compute_seconds"])
    assert view["compute_seconds"] < 60.


def test_finite_cell_claim_and_report_use_bound_evidence_without_new_solves(tmp_path):
    run = tmp_path / "run"
    prepare_research_task(request(), run)
    result = execute_research_action(run, ground(), wait=True)
    assert result["calculation"]["ground_state_evidence"]["finite_cell_status"] == "bound_saturated"
    view = execute_research_action(run, assessment("claim", "finite_cell_ground_state"))
    assert view["answer_status"] == "answered_within_scope"
    before = view["solver_runs"]
    manifest = render_research_report(run, tmp_path / "report")
    text = Path(manifest["report"]).read_text()
    assert "bound_saturated" in text and "finite_cell_ground_state" in text
    assert inspect_research_task(run)["solver_runs"] == before


def test_stationary_unverified_state_cannot_support_finite_cell_claim(tmp_path):
    model = cubic_input(1., {})["model"]
    # These symmetry-complete R=2 bonds are constant on the requested cell.
    for term in copy.deepcopy(model["term_attachments"]["bond_terms"]):
        term["term_ref"] += ":second"
        for endpoint in term["cluster"]:
            endpoint["translation"] = [2*v for v in endpoint["translation"]]
        term["payload"]["matrix"] = (-.01*np.eye(3)).tolist()
        model["term_attachments"]["bond_terms"].append(term)
    run = tmp_path / "run"
    prepare_research_task(request(model), run)
    result = execute_research_action(run, ground(
        initial_spins=[[0., 0., .5]]*8, fourier_seed_recovery=False), wait=True)
    assert result["scientific_status"] == "usable_within_scope"
    assert result["calculation"]["stationarity_max_norm"] < 1e-8
    with pytest.raises(ValueError, match="finite.cell.*bound|bound.*finite.cell"):
        execute_research_action(run, assessment("overclaim", "finite_cell_ground_state"))
    view = execute_research_action(run, assessment("reference", "stationary_reference"))
    assert view["answer_status"] == "answered_within_scope"


def test_finite_evidence_cannot_be_promoted_to_thermodynamic_claim(tmp_path):
    run = tmp_path / "run"
    prepare_research_task(request(), run)
    execute_research_action(run, ground(), wait=True)
    with pytest.raises(ValueError, match="thermodynamic"):
        execute_research_action(run, assessment("overclaim", "thermodynamic_ground_state"))
