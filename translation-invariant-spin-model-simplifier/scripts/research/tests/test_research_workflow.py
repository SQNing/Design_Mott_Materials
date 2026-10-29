"""User-level research journeys; scientific expectations stay in tests."""
import copy
import json
import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))

from three_dimensional.examples import cubic_input
from research.workflow import (
    prepare_research_task, inspect_research_task, execute_research_action,
)
from research.report import render_research_report


def request(exchange=-1.37):
    return {
        "model": cubic_input(exchange, {})["model"],
        "question": "Find a classical reference and its harmonic spectrum.",
        "requested_tasks": ["classical_ground_state", "harmonic_spectrum"],
        "budget": {"max_solver_runs": 8, "max_wall_time_seconds": 120,
                   "max_memory_mb": 2048},
    }


def ground(action_id="ground", **settings):
    return {"action_id": action_id, "type": "calculate",
            "task": "classical_ground_state",
            "reason": "Find an actual fixed-length reference.",
            "settings": {"supercell_shape": [2, 2, 2], "spin_length": .5,
                         "starts": 2, "seed": 31, **settings}}


def test_new_model_runs_and_reference_is_reused_for_spectrum(tmp_path):
    run = tmp_path / "run"
    ready = prepare_research_task(request(), run)
    assert ready["status"] == "ready"
    assert ready["model"]["term_count"] == 3
    result = execute_research_action(run, ground(), wait=True)
    assert result["execution_status"] == "succeeded"
    assert result["scientific_status"] == "usable_within_scope"
    assert result["calculation"]["energy_per_cell"] == pytest.approx(-1.0275, abs=1e-8)
    spectrum = execute_research_action(run, {
        "action_id": "spectrum", "type": "calculate", "task": "harmonic_spectrum",
        "reason": "Check the reference stability at specified wavevectors.",
        "reference_result": "ground",
        "settings": {"spin": .5, "reduced_momenta": [[0, 0, 0], [.5, 0, 0]]},
    }, wait=True)
    assert spectrum["execution_status"] == "succeeded"
    assert "classical_optimization" not in spectrum["calculation"]
    assert spectrum["reference_result"] == "ground"
    assert spectrum["calculation"]["supercell_shape"] == [2, 2, 2]
    before = inspect_research_task(run)
    manifest = render_research_report(run, tmp_path / "report")
    assert Path(manifest["report"]).is_file()
    after = inspect_research_task(run)
    assert before["solver_runs"] == after["solver_runs"] == 2
    assert "finite" in Path(manifest["report"]).read_text().lower()


def test_missing_physics_can_be_supplied_without_replacing_source(tmp_path):
    run = tmp_path / "run"
    incomplete = request()
    del incomplete["model"]["symmetry"]
    view = prepare_research_task(incomplete, run)
    assert view["status"] == "needs_input"
    assert "symmetry" in json.dumps(view["questions"]).lower()
    supplied = execute_research_action(run, {
        "action_id": "supply-symmetry", "type": "provide_input",
        "reason": "User supplied the structural symmetry.",
        "model_patch": {"symmetry": request()["model"]["symmetry"]},
    })
    assert supplied["status"] == "ready"
    assert supplied["model"]["version"] == 2
    assert "symmetry" not in json.loads((run / "models/model-0001/source.json").read_text())


def test_same_action_is_idempotent_and_model_revision_invalidates_reference(tmp_path):
    run = tmp_path / "run"
    prepare_research_task(request(), run)
    first = execute_research_action(run, ground(), wait=True)
    again = execute_research_action(run, ground(), wait=True)
    assert again["result_id"] == first["result_id"]
    assert inspect_research_task(run)["solver_runs"] == 1
    copied = execute_research_action(run, ground("same-settings"), wait=True)
    assert copied["execution_status"] == "reused"
    assert copied["reused_from"] == "ground"
    assert inspect_research_task(run)["solver_runs"] == 1
    revised = request(-1.1)["model"]
    execute_research_action(run, {"action_id": "revision", "type": "provide_input",
        "reason": "User explicitly changed the exchange.", "model": revised})
    with pytest.raises(ValueError, match="reference.*model"):
        execute_research_action(run, {
            "action_id": "stale-spectrum", "type": "calculate",
            "task": "harmonic_spectrum", "reference_result": "ground",
            "reason": "A stale reference must be rejected.",
            "settings": {"spin": .5, "reduced_momenta": [[0, 0, 0]]},
        })


def test_budget_and_unsupported_terms_stop_without_dropping_terms(tmp_path):
    limited = request()
    limited["budget"]["max_solver_runs"] = 1
    run = tmp_path / "budget"
    prepare_research_task(limited, run)
    execute_research_action(run, ground(), wait=True)
    blocked = execute_research_action(run, ground("more", seed=2))
    assert blocked["scientific_status"] == "inconclusive"
    assert blocked["blocker"] == "solver-run-budget-exhausted"
    assert inspect_research_task(run)["solver_runs"] == 1

    model = request()
    extra = copy.deepcopy(model["model"]["term_attachments"]["bond_terms"])
    for term in extra:
        term["term_ref"] += ":K"
        term["payload"] = {"kind": "biquadratic_exchange", "coefficient": .12}
    model["model"]["term_attachments"]["bond_terms"].extend(extra)
    bad_run = tmp_path / "unsupported"
    view = prepare_research_task(model, bad_run)
    assert view["status"] in {"unsupported", "ready"}
    if view["status"] == "ready":
        outcome = execute_research_action(bad_run, ground(), wait=True)
        assert outcome["scientific_status"] == "unsupported"
    assert inspect_research_task(bad_run)["model"]["source_term_count"] == 6


def test_unmeasured_fidelity_is_not_reported_as_zero():
    from simplify.score_fidelity import score_fidelity
    score = score_fidelity({"main": [{"coefficient": 1}], "residual": []})
    assert score["reconstruction_error"] is None
    assert score["assessment"] == "not_assessed"

