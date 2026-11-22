"""Stage F: workspace registry and cross-run fingerprint cache."""
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))

from three_dimensional.examples import cubic_input
from research.contracts import code_identity, digest, task_code_groups
from research.registry import (find_fingerprint, load_registry, query_runs,
                               record_run)
from research.state import read_json, write_json
from research.workflow import (execute_research_action, inspect_research_task,
                               prepare_research_task)


def _request(exchange=-1.37):
    return {
        "model": cubic_input(exchange, {})["model"],
        "question": "Find a classical reference and its harmonic spectrum.",
        "requested_tasks": ["classical_ground_state", "harmonic_spectrum"],
        "budget": {"max_solver_runs": 8, "max_wall_time_seconds": 120,
                   "max_memory_mb": 2048},
    }


def _ground(action_id="ground", **settings):
    return {"action_id": action_id, "type": "calculate",
            "task": "classical_ground_state",
            "reason": "Find an actual fixed-length reference.",
            "settings": {"supercell_shape": [2, 2, 2], "spin_length": .5,
                         "starts": 2, "seed": 31, **settings}}


def _inject_completed_ground(run):
    """Install a succeeded ground step without launching a sandboxed worker."""
    action = _ground()
    state = read_json(run / "state.json")
    model_id = state["model"]["model_id"]
    identity = code_identity(groups=task_code_groups("classical_ground_state"))
    fingerprint = digest({"model_id": model_id, "task": "classical_ground_state",
                          "settings": action["settings"], "reference": None,
                          "code_identity": identity})
    now = time.time()
    directory = run / "steps" / "ground"
    write_json(directory / "action.json", action, exclusive=True)
    write_json(directory / "execution.json", {
        "status": "succeeded", "counted": True, "started_at": now - 1.0,
        "finished_at": now, "solver_runs": 1}, exclusive=True)
    result = {
        "result_id": "ground", "model_id": model_id, "task": "classical_ground_state",
        "execution_status": "succeeded", "scientific_status": "usable_within_scope",
        "reusable": True, "solver_runs": 1, "finished_at": now,
        "calculation_fingerprint": fingerprint, "code_identity": identity,
        "calculation": {"energy_per_cell": -1.0275,
                        "observables": {"static": {"energy": -1.0275}}},
    }
    write_json(directory / "result.json", result, exclusive=True)
    state["steps"].append("ground")
    write_json(run / "state.json", state)
    return result


def test_cross_run_fingerprint_cache_reuses_solver_run(tmp_path, monkeypatch):
    registry = tmp_path / "registry.jsonl"
    monkeypatch.setenv("SPINFORGE_RESEARCH_REGISTRY", str(registry))
    run1 = tmp_path / "run1"
    run2 = tmp_path / "run2"
    prepare_research_task(_request(), run1)
    prepare_research_task(_request(), run2)

    first = _inject_completed_ground(run1)
    record_run(run1, registry)
    assert inspect_research_task(run1)["solver_runs"] == 1
    entries = load_registry(registry)
    assert [entry["run_dir"] for entry in entries] == [str(run1)]
    candidate = find_fingerprint(registry, first["calculation_fingerprint"])
    assert candidate["run_dir"] == str(run1)
    assert candidate["result_id"] == "ground"

    second = execute_research_action(run2, _ground(), wait=True)
    assert second["execution_status"] == "reused"
    assert second["reused_from"] == "ground"
    assert second["reused_from_run_dir"] == str(run1)
    assert second.get("solver_runs", 0) == 0
    assert inspect_research_task(run2)["solver_runs"] == 0
    assert inspect_research_task(run1)["solver_runs"] == 1
    assert len(load_registry(registry)) == 2
    assert query_runs(registry, status="ready", task="classical_ground_state")


def test_registry_records_claim_and_result_summary(tmp_path, monkeypatch):
    registry = tmp_path / "registry.jsonl"
    monkeypatch.setenv("SPINFORGE_RESEARCH_REGISTRY", str(registry))
    run = tmp_path / "run"
    prepare_research_task(_request(), run)
    result = _inject_completed_ground(run)
    entry = record_run(run, registry)
    assert entry["run_dir"] == str(run)
    assert entry["model_id"] == result["model_id"]
    assert entry["solver_runs"] == 1
    assert entry["fingerprints"][0]["fingerprint"] == result["calculation_fingerprint"]
    summary = next(r for r in entry["results"] if r["result_id"] == "ground")
    assert summary["execution_status"] == "succeeded"
    assert summary["task"] == "classical_ground_state"
    assert summary["energy"] == -1.0275
