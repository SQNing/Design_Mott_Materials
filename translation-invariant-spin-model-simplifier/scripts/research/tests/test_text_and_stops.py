"""Text clarification and honest stopping through the same public interface."""
import copy
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from research.workflow import prepare_research_task, execute_research_action, inspect_research_task
from three_dimensional.examples import cubic_input


def test_host_normalized_text_preserves_source_and_matches_structured_input(tmp_path):
    text = ("Simple cubic lattice, one spin per cell; nearest-neighbour isotropic exchange J=-0.93. "
            "Find a periodic reference and its harmonic modes. The spin normalization is not specified.")
    run = tmp_path / "text"
    request = {"source": {"kind": "text", "text": text},
               "question": "Find a finite reference and modes.",
               "requested_tasks": ["classical_ground_state", "harmonic_spectrum"]}
    initial = prepare_research_task(request, run)
    assert initial["status"] == "needs_input"
    # The host agent, after a researcher chooses ordinary spin S=1/2, lands the
    # model. This fixture tests the protocol; a separate transcript records the
    # actual host-agent extraction of another document.
    landed = cubic_input(-.93, {})["model"]
    supplied = execute_research_action(run, {
        "action_id": "answer", "type": "provide_input", "model": landed,
        "reason": "Researcher clarified ordinary spin S=1/2; host landed the explicit full cubic model.",
        "answers": {"classical_space": "ordinary spin", "spin_length": .5},
        "request_updates": {"normalization": {"selected_classical_bond_label": "spin-only"}}})
    independent = prepare_research_task({"model": landed, "question": request["question"]}, tmp_path / "independent")
    assert supplied["model"]["model_id"] == independent["model"]["model_id"]
    original = json.loads((run / "models/model-0001/source.json").read_text())
    assert original["text"] == text
    result = execute_research_action(run, {"action_id": "ground", "type": "calculate",
        "task": "classical_ground_state", "reason": "Use the clarified spin convention.",
        "settings": {"spin_length": .5, "supercell_shape": [2, 2, 2], "starts": 1, "seed": 9}}, wait=True)
    assert result["calculation"]["energy_per_cell"] == pytest.approx(-.6975, abs=1e-7)


def test_unsupported_backend_and_unusable_evidence_cannot_complete(tmp_path):
    run = tmp_path / "blocked"
    prepare_research_task({"model": cubic_input(-1, {})["model"], "question": "Get a finite reference.",
                           "requested_tasks": ["classical_ground_state"]}, run)
    result = execute_research_action(run, {"action_id": "backend", "type": "calculate",
        "task": "classical_ground_state", "reason": "An explicit unavailable backend must not be substituted.",
        "settings": {"backend": "unimplemented"}})
    assert result["scientific_status"] == "unsupported"
    assert inspect_research_task(run)["solver_runs"] == 0
    with pytest.raises(ValueError):
        execute_research_action(run, {"action_id": "claim", "type": "assess",
            "reason": "A failed calculation cannot answer a physical question.",
            "answer_status": "answered_within_scope", "conclusion": "Claim",
            "scope": "finite", "limitations": ["limited"],
            "evidence": [{"result_id": "backend", "path": "blocker"}]})
