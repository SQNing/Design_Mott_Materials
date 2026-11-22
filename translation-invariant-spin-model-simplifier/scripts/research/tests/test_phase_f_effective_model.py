"""Stage F1: effective-model/v1 inter-chain contract landing."""
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))

from three_dimensional.examples import cubic_input
from research.workflow import prepare_research_task


def _base_request(model):
    return {"model": model, "question": "Land an upstream effective model.",
            "requested_tasks": ["classical_ground_state"],
            "budget": {"max_solver_runs": 1, "max_wall_time_seconds": 30,
                       "max_memory_mb": 1024}}


def _provenance():
    return {"dft_code": "upstream-dft", "functional": "PBEsol",
            "u_j": {"U": 4.0, "J": 0.8}, "projection_window": [-8.0, 8.0],
            "wannier_basis": "dxy-like projected orbitals", "date": "2026-11-23"}


def test_effective_model_missing_provenance_needs_input(tmp_path):
    payload = {"schema_version": "effective-model/v1",
               "model": cubic_input(-1.37, {})["model"],
               "uncertainty": {"energy": 0.05}}
    view = prepare_research_task(_base_request(payload), tmp_path / "run")
    assert view["status"] == "needs_input"
    assert "provenance" in json.dumps(view["questions"]).lower()


def test_effective_model_full_provenance_lands_and_preserves_metadata(tmp_path):
    payload = {"schema_version": "effective-model/v1",
               "model": cubic_input(-1.37, {})["model"],
               "provenance": _provenance(),
               "uncertainty": {"energy": 0.05, "method": "upstream estimate"}}
    run = tmp_path / "run"
    view = prepare_research_task(_base_request(payload), run)
    assert view["status"] == "ready"
    canonical = json.loads((run / "models/model-0001/canonical.json").read_text())
    assert canonical["effective_model_provenance"] == _provenance()
    assert canonical["effective_model_uncertainty"]["energy"] == 0.05
