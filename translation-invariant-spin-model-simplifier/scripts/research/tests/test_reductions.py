"""Reduction tests keep physical expectations outside model and solver inputs."""
import copy
import json
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common.canonical_hamiltonian import compile_canonical_hamiltonian
from research.contracts import restore_complex
from research.examples import retained_three_level, multisublattice_spin, request_for
from research.reductions import transform_model
from research.workflow import prepare_research_task, execute_research_action, inspect_research_task
from research.report import render_research_report


def test_projection_matches_direct_complex_matrix_elements_and_preserves_source():
    full = compile_canonical_hamiltonian(retained_three_level())
    original = copy.deepcopy(full)
    embedding = np.array([[1, 0], [0, 1], [0, 0]], dtype=complex)
    reduced, mapping = transform_model(full, {
        "kind": "project_local_space", "isometry": embedding.tolist(), "basis_labels": ["g", "e1"]})
    assert full == original
    assert mapping["full_dimension"] == 3 and mapping["reduced_dimension"] == 2
    for before, after in zip(full["terms"], reduced["terms"]):
        matrix = np.asarray(restore_complex(before["coefficient"]), dtype=complex)
        lift = embedding if before["arity"] == 1 else np.kron(embedding, embedding)
        assert np.allclose(after["coefficient"], lift.conj().T @ matrix @ lift)
    assert reduced["local_hilbert"]["classical_spaces"]["space"]["dimension"] == 2
    assert len(reduced["local_hilbert"]["operator_bases"]["basis"]["symmetry_actions"]["identity"]["matrix"]) == 4


def test_invalid_subspace_and_undeclared_term_selection_are_rejected():
    full = compile_canonical_hamiltonian(retained_three_level())
    with pytest.raises(ValueError, match="orthonormal"):
        transform_model(full, {"kind": "project_local_space", "isometry": [[1, 1], [0, 0], [0, 0]]})
    with pytest.raises(ValueError, match="unknown"):
        transform_model(full, {"kind": "drop_terms", "term_refs": ["missing"]})
    # A symmetry action exchanging g and e2 cannot preserve span(g,e1).
    u = np.array([[0, 0, 1], [0, 1, 0], [1, 0, 0]])
    full["local_hilbert"]["operator_bases"]["basis"]["symmetry_actions"]["identity"]["matrix"] = np.kron(u, u).tolist()
    with pytest.raises(ValueError, match="subspace"):
        transform_model(full, {"kind": "project_local_space", "isometry": [[1, 0], [0, 1], [0, 0]]})


def validation(candidate, identifier="validate", tolerance=.03):
    return {"action_id": identifier, "type": "calculate", "task": "reduction_validation",
            "reason": "Compare the proposed physical approximation with the full model.",
            "settings": {"candidate_id": candidate, "energy_window_max": 2.0,
                "experiments": [
                    {"case_id": "reference", "task": "classical_ground_state",
                     "settings": {"starts": 2, "seed": 6, "max_linear_size": 1, "max_sweeps": 100},
                     "metrics": {"energy_per_cell": tolerance, "full_energy_penalty": tolerance,
                                 "projector_distance": .05}},
                    {"case_id": "modes", "task": "harmonic_spectrum",
                     "reference_case": "reference", "settings": {"reduced_momenta": [[0, 0, 0], [.25, 0, 0]]},
                     "metrics": {"spectrum": tolerance}}]}}


def test_three_to_two_level_validation_and_cache_survive_new_tolerances(tmp_path):
    run = tmp_path / "projection"
    model = retained_three_level()
    model["term_attachments"]["site_terms"][0]["payload"]["matrix"]["data"][2][2] = 10.
    request = request_for(model, "Can two retained levels reproduce the low-energy sector?", ["reduction_validation"])
    request["budget"]["max_solver_runs"] = 4
    prepare_research_task(request, run)
    proposed = execute_research_action(run, {"action_id": "two-level", "type": "propose_reduction",
        "reason": "Test the explicitly selected two-level subspace; keep the full model as control.",
        "transformation": {"kind": "project_local_space", "isometry": [[1, 0], [0, 1], [0, 0]],
                           "basis_labels": ["g", "e1"]}})
    assert proposed["status"] == "ready"
    result = execute_research_action(run, validation("two-level"), wait=True)
    assert result["validation_status"] == "accepted_within_scope", result
    assert result["solver_runs"] == 4
    repeat = execute_research_action(run, validation("two-level", "tighter", tolerance=.01), wait=True)
    assert repeat["validation_status"] == "accepted_within_scope", repeat
    assert repeat["solver_runs"] == 0
    assert inspect_research_task(run)["solver_runs"] == 4
    identical = execute_research_action(run, validation("two-level", "identical"), wait=True)
    assert identical["execution_status"] == "reused" and identical["solver_runs"] == 0
    assert inspect_research_task(run)["solver_runs"] == 4
    manifest = render_research_report(run, tmp_path / "report")
    assert "accepted_within_scope" in Path(manifest["report"]).read_text()


def test_a_projection_that_discards_the_ground_level_is_rejected(tmp_path):
    run = tmp_path / "bad-projection"
    prepare_research_task(request_for(retained_three_level(), "Test a candidate subspace.",
                                      ["reduction_validation"]), run)
    execute_research_action(run, {"action_id": "wrong-levels", "type": "propose_reduction",
        "reason": "The demonstration tests that a bad truncation is detected.",
        "transformation": {"kind": "project_local_space", "isometry": [[0, 0], [1, 0], [0, 1]]}})
    result = execute_research_action(run, validation("wrong-levels"), wait=True)
    assert result["validation_status"] == "rejected", result
    assert any(m["outcome"] == "fail" for m in result["metrics"])
    assert result["scientific_status"] == "usable_within_scope"
    assessed = execute_research_action(run, {"action_id": "conclusion", "type": "assess",
        "reason": "A reliable counterexample answers whether this truncation meets the selected tolerances.",
        "answer_status": "answered_within_scope", "conclusion": "This selected subspace fails the tested tolerances.",
        "scope": "The recorded finite-cell classical and sampled harmonic observables.",
        "limitations": ["No claim about untested parameters or alternative subspaces."],
        "evidence": [{"result_id": "validate", "path": "calculation.metrics"}]})
    assert assessed["answer_status"] == "answered_within_scope"


def test_full_comparison_cost_is_reserved_before_launch(tmp_path):
    run = tmp_path / "budget"
    request = request_for(retained_three_level(), "Test with an insufficient numerical budget.",
                          ["reduction_validation"])
    request["budget"]["max_solver_runs"] = 3
    prepare_research_task(request, run)
    execute_research_action(run, {"action_id": "candidate", "type": "propose_reduction",
        "reason": "Select two levels.", "transformation": {
            "kind": "project_local_space", "isometry": [[1, 0], [0, 1], [0, 0]]}})
    result = execute_research_action(run, validation("candidate"), wait=True)
    assert result["scientific_status"] == "inconclusive"
    assert result["blocker"] == "solver-run-budget-exhausted"
    assert inspect_research_task(run)["solver_runs"] == 0


def spin_model_with_small_term(coefficient, *, anisotropy=False):
    from research.examples import _base, _term
    model = _base({"kind": "unit_vector_sphere", "dimension": 3},
                  {"kind": "spin_vector", "labels": ["Sx", "Sy", "Sz"]}, [[0., 0., 0.]])
    for i, shift in enumerate(([1, 0, 0], [0, 1, 0], [0, 0, 1])):
        model["term_attachments"]["bond_terms"].append(
            _term("exchange:%s" % i, [0, 0], [[0, 0, 0], shift],
                  "bilinear_exchange_matrix", (-np.eye(3)).tolist()))
    matrix = np.diag([0., 0., -coefficient]) if anisotropy else -coefficient * np.eye(3)
    model["term_attachments"]["bond_terms"].append(
        _term("small", [0, 0], [[0, 0, 0], [1, 0, 0]], "bilinear_exchange_matrix", matrix.tolist()))
    return model


def spin_validation(candidate, identifier="validate"):
    return {"action_id": identifier, "type": "calculate", "task": "reduction_validation",
            "reason": "Check energy, correlations and harmonic excitations in the same finite cell.",
            "settings": {"candidate_id": candidate, "experiments": [
                {"case_id": "reference", "task": "classical_ground_state",
                 "settings": {"supercell_shape": [1, 1, 1], "spin_length": .5, "starts": 3, "seed": 18},
                 "metrics": {"energy_per_cell": .01, "full_energy_penalty": .01, "spin_correlations": .01}},
                {"case_id": "modes", "task": "harmonic_spectrum", "reference_case": "reference",
                 "settings": {"spin": .5, "reduced_momenta": [[0, 0, 0], [.25, 0, 0]]},
                 "metrics": {"spectrum": .005}}]}}


def propose_drop(run, identifier="drop"):
    return execute_research_action(run, {"action_id": identifier, "type": "propose_reduction",
        "reason": "Test the small term explicitly against the complete Hamiltonian.",
        "transformation": {"kind": "drop_terms", "term_refs": ["small"]}})


@pytest.mark.parametrize("coefficient,anisotropy,expected", [
    (.001, False, "accepted_within_scope"), (.02, True, "rejected")])
def test_weak_terms_and_small_gap_setting_terms_are_distinguished(tmp_path, coefficient, anisotropy, expected):
    run = tmp_path / "drop"
    prepare_research_task(request_for(spin_model_with_small_term(coefficient, anisotropy=anisotropy),
                                     "Can the selected small term be neglected?", ["reduction_validation"]), run)
    original = (run / "models/model-0001/solver_model.json").read_bytes()
    candidate = propose_drop(run)
    assert candidate["status"] == "ready", candidate
    result = execute_research_action(run, spin_validation("drop"), wait=True)
    assert result["validation_status"] == expected, result
    energy = next(m for m in result["metrics"] if m["name"] == "energy_per_cell")
    assert energy["outcome"] == "pass"
    if expected == "rejected":
        assert any(m["name"] == "spectrum" and m["outcome"] == "fail" for m in result["metrics"]), result
    assert original == (run / "models/model-0001/solver_model.json").read_bytes()
    assert inspect_research_task(run)["solver_runs"] == 4


def test_stale_candidate_and_action_id_collision_are_rejected(tmp_path):
    run = tmp_path / "stale"
    prepare_research_task(request_for(spin_model_with_small_term(.001), "Test revisions.",
                                     ["reduction_validation"]), run)
    propose_drop(run)
    with pytest.raises(ValueError, match="action_id already"):
        execute_research_action(run, spin_validation("drop", "drop"))
    execute_research_action(run, {"action_id": "revision", "type": "provide_input",
        "reason": "Revise the model parameter.", "model": spin_model_with_small_term(.002)})
    with pytest.raises(ValueError, match="different full model"):
        execute_research_action(run, spin_validation("drop"))
    assert inspect_research_task(run)["reductions"][0]["current_parent"] is False


def test_projection_accepts_general_complex_isometry_and_projects_every_operator():
    full = compile_canonical_hamiltonian(retained_three_level())
    raw = np.array([[1, .2j], [.3j, .8], [.2, .5j]])
    embedding = np.linalg.qr(raw)[0]
    reduced, mapping = transform_model(full, {"kind": "project_local_space", "isometry": embedding.tolist()})
    rng = np.random.default_rng(7)
    for before, after in zip(full["terms"], reduced["terms"]):
        h = np.asarray(restore_complex(before["coefficient"]))
        low = np.asarray(after["coefficient"])
        dimension = embedding.shape[1] ** before["arity"]
        v = rng.normal(size=dimension) + 1j * rng.normal(size=dimension)
        v /= np.linalg.norm(v)
        lift = embedding if before["arity"] == 1 else np.kron(embedding, embedding)
        assert np.vdot(v, low @ v) == pytest.approx(np.vdot(lift @ v, h @ (lift @ v)))
    assert mapping["orthogonality_residual"] < 1e-10


def test_energy_window_boundary_empty_sector_and_mode_count_are_not_silently_matched():
    from research.reduction_validation import compare_experiment
    exp = {"case_id": "bands", "task": "spin_wave_spectrum", "metrics": {"spectrum": .01}}
    def spectrum(bands):
        return {"scientific_status": "usable_within_scope", "calculation": {
            "supercell_shape": [1, 1, 1], "dispersion": [{"q": [0, 0, 0], "bands": bands}]}}
    for full, candidate, window, expected in [
        ([.4, 1.005], [.4], 1., "inconclusive"),
        ([.4, .8], [.4], 1., "fail"),
        ([2., 3.], [2.], 1., "inconclusive")]:
        result = compare_experiment(exp, spectrum(full), spectrum(candidate), {}, {},
                                    {"energy_window_max": window})
        assert result[0]["outcome"] == expected


def test_lower_lifted_energy_invalidates_full_reference(monkeypatch):
    from research import reduction_validation as module
    exp = {"case_id": "ground", "task": "classical_ground_state",
           "metrics": {"energy_per_cell": 1., "full_energy_penalty": 1., "spin_correlations": 1.}}
    monkeypatch.setattr(module, "_classical_observables", lambda *args: (-2., "spin_correlations", 0.))
    full = {"scientific_status": "usable_within_scope", "calculation": {"energy_per_cell": -1.}}
    candidate = {"scientific_status": "usable_within_scope", "calculation": {"energy_per_cell": -1.}}
    metrics = module.compare_experiment(exp, full, candidate, {}, {}, {})
    assert all(m["outcome"] == "inconclusive" for m in metrics)
    assert all("refine" in m["reason"] for m in metrics)


def test_incomplete_control_and_mc_are_inconclusive():
    from research.reduction_validation import compare_experiment
    exp = {"case_id": "thermal", "task": "classical_monte_carlo", "metrics": {"mc_energy_per_site": .1}}
    result = {"scientific_status": "inconclusive", "calculation": {}}
    assert compare_experiment(exp, result, result, {}, {}, {})[0]["outcome"] == "inconclusive"


def test_symmetry_related_terms_cannot_be_dropped_individually(tmp_path):
    from three_dimensional.examples import cubic_input
    run = tmp_path / "symmetry"
    prepare_research_task(request_for(cubic_input(-1., {})["model"], "Test a symmetry-breaking deletion.",
                                     ["reduction_validation"]), run)
    full = json.loads((run / "models/model-0001/solver_model.json").read_text())
    result = execute_research_action(run, {"action_id": "invalid", "type": "propose_reduction",
        "reason": "Check the original structural symmetry after deleting one bond.",
        "transformation": {"kind": "drop_terms", "term_refs": [full["terms"][0]["term_ref"]]}})
    assert result["status"] == "rejected"
    with pytest.raises(ValueError, match="symmetry gate"):
        execute_research_action(run, spin_validation("invalid"))
    assert inspect_research_task(run)["solver_runs"] == 0


def test_quantum_comparison_and_real_mc_do_not_overclaim(tmp_path):
    run = tmp_path / "quantum-mc"
    prepare_research_task(request_for(spin_model_with_small_term(.001), "Check finite quantum and thermal evidence.",
                                     ["reduction_validation"]), run)
    propose_drop(run)
    action = spin_validation("drop")
    action["settings"]["experiments"][-1] = {
        "case_id": "quantum", "task": "quantum_low_energy",
        "settings": {"supercell_shape": [2, 2, 2], "spin": .5, "eigenvalues": 2, "seed": 31},
        "metrics": {"quantum_gaps": .01}}
    result = execute_research_action(run, action, wait=True)
    assert result["validation_status"] == "accepted_within_scope", result
    action["action_id"] = "with-mc"
    action["settings"]["experiments"].append({
        "case_id": "thermal", "task": "classical_monte_carlo",
        "settings": {"supercell_shape": [2, 1, 1], "spin_length": .5,
                     "temperatures": [.7], "sweeps": 24, "burn_in": 8, "seed": 45},
        "metrics": {"mc_energy_per_site": .1}})
    result = execute_research_action(run, action, wait=True)
    assert result["validation_status"] == "inconclusive", result
    assert result["solver_runs"] == 2
    assert inspect_research_task(run)["solver_runs"] == 6


def test_failed_subcalls_are_charged_but_not_reused_as_completed_physics(tmp_path):
    run = tmp_path / "failed-subcalls"
    prepare_research_task(request_for(retained_three_level(), "Record and retry failed calculations.",
                                     ["reduction_validation"]), run)
    execute_research_action(run, {"action_id": "candidate", "type": "propose_reduction",
        "reason": "Select two levels for comparison.",
        "transformation": {"kind": "project_local_space", "isometry": [[1, 0], [0, 1], [0, 0]]}})
    action = validation("candidate")
    # The existing numerical adapter rejects this settings error at execution.
    action["settings"]["experiments"][0]["settings"]["max_linear_size"] = 0
    first = execute_research_action(run, action, wait=True)
    assert first["validation_status"] == "inconclusive" and first["solver_runs"] == 2, first
    assert first["reusable"] is False
    assert not list((run / "validation-cache").glob("*.json"))
    action["action_id"] = "retry"
    second = execute_research_action(run, action, wait=True)
    assert second["execution_status"] == "succeeded" and second["solver_runs"] == 2
    assert inspect_research_task(run)["solver_runs"] == 4


def test_cache_integrity_is_checked_before_budget_or_launch(tmp_path):
    run = tmp_path / "cache"
    prepare_research_task(request_for(spin_model_with_small_term(.001), "Check saved evidence integrity.",
                                     ["reduction_validation"]), run)
    propose_drop(run)
    execute_research_action(run, spin_validation("drop"), wait=True)
    path = next((run / "validation-cache").glob("*.json"))
    saved = json.loads(path.read_text())
    saved["calculation"]["edited_after_computation"] = True
    path.write_text(json.dumps(saved))
    with pytest.raises(ValueError, match="cache"):
        execute_research_action(run, spin_validation("drop", "again"))
    assert inspect_research_task(run)["solver_runs"] == 4
