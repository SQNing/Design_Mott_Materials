"""Mechanism expectations are confined to tests, never numerical inputs."""
import copy
import json
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common.canonical_hamiltonian import compile_canonical_hamiltonian
from research.contracts import restore_complex
from research.examples import retained_three_level, request_for
from research.mechanisms import scale_terms
from research.mechanism_analysis import evaluate_hypothesis
from research.workflow import prepare_research_task, execute_research_action, inspect_research_task
from research.report import render_research_report
from research.tests.test_reductions import spin_model_with_small_term


def spin_plan(identifier="couplings"):
    return {"action_id": identifier, "type": "propose_mechanism",
        "reason": "Distinguish the roles of anisotropy and isotropic exchange in sampled excitations.",
        "question": "Which interaction controls the frequency at the selected momentum?",
        "groups": [
            {"group_id": "anisotropy", "term_refs": ["small"], "description": "Uniaxial exchange anisotropy."},
            {"group_id": "exchange", "term_refs": ["exchange:0", "exchange:1", "exchange:2"],
             "description": "The isotropic exchange background."}],
        "points": [
            {"point_id": "control", "factors": {"anisotropy": 1., "exchange": 1.}},
            {"point_id": "anisotropy-off", "factors": {"anisotropy": 0., "exchange": 1.}},
            {"point_id": "anisotropy-half", "factors": {"anisotropy": .5, "exchange": 1.}},
            {"point_id": "exchange-off", "factors": {"anisotropy": 1., "exchange": 0.}},
            {"point_id": "exchange-half", "factors": {"anisotropy": 1., "exchange": .5}}]}


def mechanism_action(identifier="response"):
    return {"action_id": identifier, "type": "calculate", "task": "mechanism_test",
        "reason": "Measure controlled responses and test the stated mechanism hypotheses.",
        "settings": {"mechanism_id": "couplings", "experiments": [
            {"case_id": "reference", "task": "classical_ground_state",
             "settings": {"supercell_shape": [1, 1, 1], "spin_length": .5, "starts": 3, "seed": 18}},
            {"case_id": "modes", "task": "harmonic_spectrum", "reference_case": "reference",
             "settings": {"spin": .5, "reduced_momenta": [[0, 0, 0], [.25, 0, 0]]}}],
            "observables": [{"observable_id": "frequency", "case_id": "modes",
                             "kind": "harmonic_frequency", "q": [0, 0, 0], "band_index": 0}],
            "hypotheses": [
                {"hypothesis_id": "anisotropy-response", "statement": "Anisotropy raises the sampled frequency.",
                 "kind": "monotonic_response", "group_id": "anisotropy", "observable_id": "frequency",
                 "direction": "increasing", "min_effect": .015, "numerical_tolerance": 1e-7},
                {"hypothesis_id": "anisotropy-necessary", "statement": "Anisotropy is necessary for this finite frequency.",
                 "kind": "necessary_in_context", "group_id": "anisotropy", "observable_id": "frequency",
                 "present_above": .01, "absent_below": .0001, "numerical_tolerance": 1e-7},
                {"hypothesis_id": "exchange-response", "statement": "Exchange raises the sampled frequency.",
                 "kind": "monotonic_response", "group_id": "exchange", "observable_id": "frequency",
                 "direction": "increasing", "min_effect": .015, "numerical_tolerance": 1e-7},
                {"hypothesis_id": "exchange-insensitive", "statement": "This frequency is insensitive to exchange.",
                 "kind": "insensitive_response", "group_id": "exchange", "observable_id": "frequency",
                 "max_change": .00001, "numerical_tolerance": 1e-7}] }}


def prepare_spin(run, budget=10):
    request = request_for(spin_model_with_small_term(.02, anisotropy=True),
                          "Identify which interaction controls the sampled excitation.", ["mechanism_test"])
    request["budget"]["max_solver_runs"] = budget
    prepare_research_task(request, run)
    return execute_research_action(run, spin_plan())


def test_scaling_preserves_complex_operators_and_original():
    full = compile_canonical_hamiltonian(retained_three_level())
    original = copy.deepcopy(full)
    scaled = scale_terms(full, [{"group_id": "pair", "term_refs": ["pair:general"],
                                 "description": "Scale the complete pair operator."}], {"pair": -.5})
    assert full == original
    for before, after in zip(full["terms"], scaled["terms"]):
        a = np.asarray(restore_complex(before["coefficient"]))
        b = np.asarray(restore_complex(after["coefficient"]))
        assert np.allclose(b, a * (-.5 if before["term_ref"] == "pair:general" else 1.))
        assert np.allclose(b, b.conj().T)


def test_real_interventions_distinguish_mechanisms_and_reuse_observable_changes(tmp_path):
    run = tmp_path / "spin"
    plan = prepare_spin(run)
    assert plan["status"] == "ready", plan
    original = (run / "models/model-0001/solver_model.json").read_bytes()
    result = execute_research_action(run, mechanism_action(), wait=True)
    assert result["scientific_status"] == "usable_within_scope", result
    statuses = {h["hypothesis_id"]: h["status"] for h in result["hypotheses"]}
    assert statuses == {"anisotropy-response": "supported_within_scope",
                        "anisotropy-necessary": "supported_within_scope",
                        "exchange-response": "refuted_within_scope",
                        "exchange-insensitive": "supported_within_scope"}, result
    assert result["solver_runs"] == 10
    for item in result["energy_responses"]:
        if item["scientific_status"] == "usable_within_scope":
            assert item["direct_energy_change"] + item["relaxation_energy_change"] == pytest.approx(
                item["total_energy_change"], abs=1e-10)
    at_q = mechanism_action("other-momentum")
    at_q["settings"]["observables"][0]["q"] = [.25, 0, 0]
    at_q["settings"]["hypotheses"] = [at_q["settings"]["hypotheses"][2]]
    changed = execute_research_action(run, at_q, wait=True)
    assert changed["hypotheses"][0]["status"] == "supported_within_scope", changed
    assert changed["solver_runs"] == 0
    assert inspect_research_task(run)["solver_runs"] == 10
    assert original == (run / "models/model-0001/solver_model.json").read_bytes()
    report = render_research_report(run, tmp_path / "report")
    text = Path(report["report"]).read_text()
    assert "anisotropy-response" in text and "refuted_within_scope" in text
    assert inspect_research_task(run)["solver_runs"] == 10


def test_insufficient_budget_stops_before_any_mechanism_solve(tmp_path):
    run = tmp_path / "budget"
    prepare_spin(run, budget=9)
    result = execute_research_action(run, mechanism_action(), wait=True)
    assert result["blocker"] == "solver-run-budget-exhausted"
    assert inspect_research_task(run)["solver_runs"] == 0


def test_confounded_and_two_point_trends_remain_inconclusive():
    hypothesis = mechanism_action()["settings"]["hypotheses"][0]
    plan = spin_plan()
    points = plan["points"][:3]
    values = {p["point_id"]: {"value": .02 * p["factors"]["anisotropy"],
                            "scientific_status": "usable_within_scope", "evidence": {}}
              for p in points}
    assert evaluate_hypothesis(hypothesis, points, values, "control")["status"] == "supported_within_scope"
    assert evaluate_hypothesis(hypothesis, points[:2], values, "control")["status"] == "inconclusive"
    points[1]["factors"]["exchange"] = .5
    points[2]["factors"]["exchange"] = .2
    assert evaluate_hypothesis(hypothesis, points, values, "control")["status"] == "inconclusive"


@pytest.mark.parametrize("defect", ["unknown", "overlap", "duplicate-point", "missing-control"])
def test_invalid_plans_fail_before_creating_a_study(tmp_path, defect):
    run = tmp_path / "invalid"
    request = request_for(spin_model_with_small_term(.02, anisotropy=True), "Check intervention inputs.", ["mechanism_test"])
    prepare_research_task(request, run)
    action = spin_plan()
    if defect == "unknown":
        action["groups"][0]["term_refs"] = ["not-present"]
    elif defect == "overlap":
        action["groups"][1]["term_refs"].append("small")
    elif defect == "duplicate-point":
        action["points"][-1]["factors"] = dict(action["points"][0]["factors"])
    else:
        action["points"] = action["points"][1:]
    with pytest.raises(ValueError):
        execute_research_action(run, action)
    assert not inspect_research_task(run)["mechanisms"]
    assert inspect_research_task(run)["solver_runs"] == 0


def test_symmetry_breaking_interventions_do_not_get_a_lower_group(tmp_path):
    from three_dimensional.examples import cubic_input
    run = tmp_path / "symmetry"
    prepare_research_task(request_for(cubic_input(-1., {})["model"], "Check structural symmetry.", ["mechanism_test"]), run)
    full = json.loads((run / "models/model-0001/solver_model.json").read_text())
    record = execute_research_action(run, {
        "action_id": "couplings", "type": "propose_mechanism", "reason": "Test one declared bond term.",
        "question": "Can this isolated bond change preserve the declared structural symmetry?",
        "groups": [{"group_id": "selected", "term_refs": [full["terms"][0]["term_ref"]],
                    "description": "One symmetry-related bond."}],
        "points": [{"point_id": "control", "factors": {"selected": 1.}},
                   {"point_id": "half", "factors": {"selected": .5}}]})
    assert record["status"] == "rejected"
    with pytest.raises(ValueError, match="symmetry gate"):
        execute_research_action(run, mechanism_action())
    assert inspect_research_task(run)["solver_runs"] == 0


def test_model_revision_invalidates_the_mechanism_plan(tmp_path):
    run = tmp_path / "revision"
    prepare_spin(run)
    execute_research_action(run, {"action_id": "new-model", "type": "provide_input",
        "reason": "The physical anisotropy was revised.", "model": spin_model_with_small_term(.03, anisotropy=True)})
    with pytest.raises(ValueError, match="different full model"):
        execute_research_action(run, mechanism_action())
    assert inspect_research_task(run)["mechanisms"][0]["current_parent"] is False


def retained_plan():
    return {"action_id": "levels", "type": "propose_mechanism", "reason": "Vary the complete onsite matrix.",
        "question": "How do the local levels affect the sampled excitations and ground-state population?",
        "groups": [{"group_id": "onsite", "term_refs": ["onsite:levels"], "description": "All onsite matrix elements."}],
        "points": [{"point_id": "half", "factors": {"onsite": .5}},
                   {"point_id": "control", "factors": {"onsite": 1.}},
                   {"point_id": "strong", "factors": {"onsite": 1.5}}]}


def retained_action(identifier="levels-response"):
    return {"action_id": identifier, "type": "calculate", "task": "mechanism_test",
        "reason": "Compare full three-level references and harmonic modes.",
        "settings": {"mechanism_id": "levels", "experiments": [
            {"case_id": "rays", "task": "classical_ground_state",
             "settings": {"starts": 2, "seed": 6, "max_linear_size": 1, "max_sweeps": 100}},
            {"case_id": "modes", "task": "harmonic_spectrum", "reference_case": "rays",
             "settings": {"reduced_momenta": [[0, 0, 0], [.25, 0, 0]]}}],
            "observables": [
                {"observable_id": "frequency", "case_id": "modes", "kind": "harmonic_frequency",
                 "q": [0, 0, 0], "band_index": 0},
                {"observable_id": "population", "case_id": "rays", "kind": "local_population", "basis_index": 0}],
            "hypotheses": [
                {"hypothesis_id": "levels-raise-mode", "statement": "Stronger onsite splitting raises the selected mode.",
                 "kind": "monotonic_response", "group_id": "onsite", "observable_id": "frequency",
                 "direction": "increasing", "min_effect": .7, "numerical_tolerance": 1e-6},
                {"hypothesis_id": "population-preserved", "statement": "The selected local ground-level population remains unchanged.",
                 "kind": "insensitive_response", "group_id": "onsite", "observable_id": "population",
                 "max_change": 1e-5, "numerical_tolerance": 1e-7}] }}


def test_retained_local_mechanism_keeps_all_three_levels(tmp_path):
    run = tmp_path / "retained"
    request = request_for(retained_three_level(), "Test onsite control of excitations.", ["mechanism_test"])
    request["budget"]["max_solver_runs"] = 6
    prepare_research_task(request, run)
    plan = execute_research_action(run, retained_plan())
    assert all(p["model"]["local_spaces"]["space"]["dimension"] == 3 for p in plan["points"])
    result = execute_research_action(run, retained_action(), wait=True)
    assert result["scientific_status"] == "usable_within_scope", result
    assert all(h["status"] == "supported_within_scope" for h in result["hypotheses"]), result
    assert result["solver_runs"] == 6
    assert all(r["local_dimension"] == 3 for r in result["validated_scope"]["realized_cases"])


def single_group_plan():
    plan = spin_plan()
    plan["groups"] = plan["groups"][:1]
    plan["points"] = plan["points"][:3]
    for point in plan["points"]:
        point["factors"].pop("exchange")
    return plan


def test_finite_quantum_mechanism_uses_explicit_level_spacing(tmp_path):
    run = tmp_path / "quantum"
    request = request_for(spin_model_with_small_term(.02, anisotropy=True), "Test a finite-cluster level spacing.",
                          ["mechanism_test"])
    request["budget"]["max_solver_runs"] = 3
    prepare_research_task(request, run)
    execute_research_action(run, single_group_plan())
    action = mechanism_action()
    action["settings"]["experiments"] = [{"case_id": "levels", "task": "quantum_low_energy",
        "settings": {"supercell_shape": [2, 2, 2], "spin": .5, "eigenvalues": 3, "seed": 31}}]
    action["settings"]["observables"] = [{"observable_id": "frequency", "case_id": "levels",
                                          "kind": "quantum_gap", "level": 2}]
    action["settings"]["hypotheses"] = action["settings"]["hypotheses"][:1]
    result = execute_research_action(run, action, wait=True)
    assert result["hypotheses"][0]["status"] == "supported_within_scope", result
    assert result["solver_runs"] == 3
    assert not result["energy_responses"]


def test_unverified_mc_cannot_support_a_mechanism(tmp_path):
    run = tmp_path / "thermal"
    request = request_for(spin_model_with_small_term(.02, anisotropy=True), "Test thermal evidence.", ["mechanism_test"])
    request["budget"]["max_solver_runs"] = 3
    prepare_research_task(request, run)
    execute_research_action(run, single_group_plan())
    action = mechanism_action()
    action["settings"]["experiments"] = [{"case_id": "thermal", "task": "classical_monte_carlo",
        "settings": {"supercell_shape": [2, 1, 1], "spin_length": .5, "temperatures": [.7],
                     "sweeps": 24, "burn_in": 8, "seed": 45}}]
    action["settings"]["observables"] = [{"observable_id": "frequency", "case_id": "thermal",
                                          "kind": "mc_energy_per_site", "temperature": .7}]
    action["settings"]["hypotheses"] = action["settings"]["hypotheses"][:1]
    result = execute_research_action(run, action, wait=True)
    assert result["scientific_status"] == "inconclusive", result
    assert result["hypotheses"][0]["status"] == "inconclusive"
    assert result["solver_runs"] == 3


def test_effect_threshold_boundary_is_not_called_support():
    h = mechanism_action()["settings"]["hypotheses"][0]
    points = spin_plan()["points"][:3]
    values = {p["point_id"]: {"value": .015 * p["factors"]["anisotropy"],
                            "scientific_status": "usable_within_scope", "evidence": {}} for p in points}
    result = evaluate_hypothesis(h, points, values, "control")
    assert result["status"] == "inconclusive"
    values["anisotropy-half"]["value"] = .1
    result = evaluate_hypothesis(h, points, values, "control")
    assert result["status"] == "refuted_within_scope"


def test_lower_energy_state_invalidates_all_full_reference_comparisons(monkeypatch):
    from research import mechanism_observables as module
    plan = {"baseline_point_id": "base", "points": [{"point_id": "base"}, {"point_id": "other"}]}
    experiments = {"ground": {"task": "classical_ground_state"}}
    results = {("ground", label): {"scientific_status": "usable_within_scope",
        "calculation": {"label": label, "supercell_shape": [1, 1, 1], "spin_length": .5,
                        "energy_per_cell": energy}} for label, energy in [("base", -1.), ("other", -2.)]}
    models = {label: {"model": {"label": label}} for label in ["base", "other"]}
    energies = {("base", "base"): -1., ("base", "other"): -1.5,
                ("other", "base"): -1.1, ("other", "other"): -2.}
    monkeypatch.setattr(module, "evaluate_state_energy",
                        lambda model, calc: energies[(model["label"], calc["label"])])
    rows, invalid = module.classical_energy_responses(plan, experiments, results, models, 1e-7)
    assert all(r["scientific_status"] == "inconclusive" for r in rows)
    assert set(invalid) == {("ground", "base"), ("ground", "other")}


def test_evidence_names_do_not_collide_between_case_and_point_ids(tmp_path):
    run = tmp_path / "names"
    prepare_research_task(request_for(spin_model_with_small_term(.02, anisotropy=True), "Preserve distinct evidence.",
                                     ["mechanism_test"]), run)
    plan = single_group_plan()
    plan["points"][0]["point_id"] = "b"
    plan["points"][1]["point_id"] = "a-b"
    execute_research_action(run, plan)
    action = mechanism_action()
    physical = action["settings"]["experiments"][0]["settings"]
    action["settings"]["experiments"] = [
        {"case_id": "r-a", "task": "classical_ground_state", "settings": physical},
        {"case_id": "r", "task": "classical_ground_state", "settings": physical}]
    action["settings"]["observables"] = [
        {"observable_id": "energy", "case_id": "r-a", "kind": "energy_per_cell"}]
    action["settings"]["hypotheses"] = [
        {"hypothesis_id": "energy-response", "statement": "Anisotropy lowers the finite reference energy.",
         "kind": "monotonic_response", "group_id": "anisotropy", "observable_id": "energy",
         "direction": "decreasing", "min_effect": .001, "numerical_tolerance": 1e-7}]
    result = execute_research_action(run, action, wait=True)
    assert result["execution_status"] == "succeeded", result
    assert result["hypotheses"][0]["status"] == "supported_within_scope", result
    paths = [e["path"] for e in result["evidence"]]
    assert len(paths) == len(set(paths)) == 6
    assert result["solver_runs"] == 3



def test_absent_baseline_phenomenon_cannot_support_necessity():
    hypothesis = mechanism_action()["settings"]["hypotheses"][1]
    points = spin_plan()["points"]
    values = {p["point_id"]: {"value": 0., "scientific_status": "usable_within_scope", "evidence": {}}
              for p in points}
    assert evaluate_hypothesis(hypothesis, points, values, "control")["status"] == "inconclusive"


def test_necessity_uses_its_paired_endpoints_without_requiring_an_intermediate_state():
    h = mechanism_action()["settings"]["hypotheses"][1]
    points = spin_plan()["points"][:3]
    values = {p["point_id"]: {"value": .02 * p["factors"]["anisotropy"],
                            "scientific_status": "usable_within_scope", "evidence": {}} for p in points}
    values["anisotropy-half"]["scientific_status"] = "inconclusive"
    result = evaluate_hypothesis(h, points, values, "control")
    assert result["status"] == "supported_within_scope"
    assert set(result["used_points"]) == {"control", "anisotropy-off"}


def test_reduction_and_mechanism_share_the_same_complete_model_calculations(tmp_path):
    from research.tests.test_reductions import propose_drop, spin_validation
    run = tmp_path / "pipeline"
    request = request_for(spin_model_with_small_term(.02, anisotropy=True),
                          "Explain why a small term cannot be discarded.", ["reduction_validation", "mechanism_test"])
    request["budget"]["max_solver_runs"] = 8
    prepare_research_task(request, run)
    propose_drop(run)
    reduction = execute_research_action(run, spin_validation("drop"), wait=True)
    assert reduction["validation_status"] == "rejected"
    execute_research_action(run, single_group_plan())
    action = mechanism_action("mechanism")
    action["settings"]["hypotheses"] = action["settings"]["hypotheses"][:2]
    result = execute_research_action(run, action, wait=True)
    assert result["scientific_status"] == "usable_within_scope", result
    assert 0 < result["solver_runs"] <= 4
    assert all(e["reused"] for e in result["evidence"] if e["role"] == "control")
    assert inspect_research_task(run)["solver_runs"] <= 8

