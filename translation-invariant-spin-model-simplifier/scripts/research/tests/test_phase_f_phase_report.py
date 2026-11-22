"""Stage F5: phase-map report from registry entries."""
import json
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))

from research.phase_report import render_phase_map_report


def _entry(run_dir, j2, m2, q):
    return {"schema_version": "research-registry/v1", "run_dir": run_dir,
            "recorded_at": time.time(), "question": "phase scan", "status": "ready",
            "answer_status": "answered_within_scope", "claim_level": "finite_cell_ground_state",
            "model_id": "model-x", "requested_tasks": ["classical_ground_state"],
            "phase_parameters": {"J2_J1": j2}, "solver_runs": 1, "compute_seconds": 1.0,
            "step_count": 1, "fingerprints": [],
            "results": [{"result_id": "ground", "task": "classical_ground_state",
                         "execution_status": "succeeded",
                         "scientific_status": "usable_within_scope",
                         "claim_level": "finite_cell_ground_state",
                         "energy_per_site": -0.5 - 0.01 * j2,
                         "ordering_q": q, "m2_ordering": m2}]}


def test_phase_map_report_labels_and_manifest(tmp_path):
    registry = tmp_path / "registry.jsonl"
    with registry.open("w", encoding="utf-8") as stream:
        for j2, m2, q in ((0.0, {"AF": 0.8}, [0.5, 0, 0]),
                          (0.6, {"AF": 0.01}, None)):
            stream.write(json.dumps({"type": "run_update", "time": time.time(),
                                     "entry": _entry(str(tmp_path / ("run%s" % j2)), j2, m2, q)}) + "\n")
    manifest = render_phase_map_report(registry, tmp_path / "report")
    text = Path(manifest["report"]).read_text(encoding="utf-8")
    assert "ordered@[0.5, 0, 0]" in text
    assert "paramagnetic/disordered" in text
    assert manifest["rows"][0]["claim_level"] == "finite_cell_ground_state"
    assert Path(manifest["report"]).is_file()
    assert (tmp_path / "report/phase-map.json").is_file()
