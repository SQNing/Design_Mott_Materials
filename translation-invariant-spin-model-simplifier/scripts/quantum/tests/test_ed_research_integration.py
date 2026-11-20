"""End-to-end research workflow integration for sector ED (tasks B1/B4/B5)."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import chain_model
from research.contracts import validate_observables_block
from research.examples import request_for
from research.mechanism_observables import read_observable, validate_observables
from research.report import render_research_report
from research.workflow import execute_research_action, prepare_research_task


def action(name, task, **settings):
    return {"action_id": name, "type": "calculate", "task": task,
            "reason": "Finite-cluster ED diagnostic with sector resolution.",
            "settings": settings}


def test_research_quantum_action_with_sectors_and_observables(tmp_path):
    run = tmp_path / "quantum-sectors"
    prepare_research_task(request_for(chain_model(1.0),
                                      "Resolve the finite-chain ground state by symmetry sector.",
                                      ["quantum_low_energy"]), run)
    result = execute_research_action(run, action(
        "ed", "quantum_low_energy", supercell_shape=[8, 1, 1], spin=0.5,
        sz_total=0, momentum=[0, 0, 0], eigenvalues=4, seed=11,
        compare_sectors=[{"sz_total": 1, "momentum": [0, 0, 0]}],
        observables=["gaps", "correlations", "structure_factor", "level_statistics"]),
        wait=True)
    assert result["execution_status"] == "succeeded", result
    assert result["scientific_status"] == "usable_within_scope", result
    kinds = {entry["kind"] for entry in result["diagnostics"]}
    assert {"ed_convergence", "sector_resolution"} <= kinds
    sector = result["calculation"]["sector"]
    assert sector["basis_kind"] == "sz+momentum"
    assert sector["sector_dimension"] < sector["sz_basis_dimension"]
    block = validate_observables_block(result["calculation"]["observables"],
                                       backend="ed-sparse-sector")
    assert block["provenance"]["sector"] == {"sz_total": 0, "momentum": [0, 0, 0]}
    assert any("no thermodynamic-limit" in scope for scope in result["scientific_scope"])
    manifest = render_research_report(run, tmp_path / "report")
    assert manifest["report"]
    report_text = (tmp_path / "report" / "report.md").read_text(encoding="utf-8")
    assert "sz+momentum" in report_text


def test_research_quantum_dimension_guard_blocks_oversized_cluster(tmp_path):
    run = tmp_path / "quantum-oversized"
    prepare_research_task(request_for(chain_model(1.0),
                                      "Attempt an oversized ED cluster.",
                                      ["quantum_low_energy"]), run)
    result = execute_research_action(run, action(
        "too-big", "quantum_low_energy", supercell_shape=[24, 1, 1], spin=0.5,
        eigenvalues=2), wait=True)
    assert result["execution_status"] == "failed" or result["scientific_status"] == "unsupported"
    assert "dimension-exceeded" in str(result.get("blocker"))


def test_spin_correlation_observable_validation():
    model = chain_model(1.0)
    experiments = {"case": {"task": "quantum_low_energy",
                            "settings": {"supercell_shape": [4, 1, 1], "spin": 0.5,
                                         "eigenvalues": 2,
                                         "observables": ["correlations"]}}}
    validate_observables([{"observable_id": "c01", "case_id": "case",
                           "kind": "spin_correlation", "site_i": 0, "site_j": 1}],
                         experiments, model)
    with pytest.raises(ValueError, match="correlations"):
        bad = {"case": {"task": "quantum_low_energy",
                        "settings": {"supercell_shape": [4, 1, 1], "spin": 0.5,
                                     "eigenvalues": 2}}}
        validate_observables([{"observable_id": "c01", "case_id": "case",
                               "kind": "spin_correlation", "site_i": 0, "site_j": 1}], bad, model)
    with pytest.raises(ValueError, match="outside"):
        validate_observables([{"observable_id": "c01", "case_id": "case",
                               "kind": "spin_correlation", "site_i": 0, "site_j": 99}],
                             experiments, model)


def test_spin_correlation_read_observable():
    result = {"scientific_status": "usable_within_scope",
              "calculation": {"observables": {"static": {"correlations": {
                  "matrix": [[0.75, -0.5], [-0.5, 0.75]]}}}}}
    record = read_observable({"observable_id": "c01", "kind": "spin_correlation",
                              "site_i": 0, "site_j": 1}, result,
                             {"path": "results/x.json", "job_fingerprint": "fp"})
    assert record["scientific_status"] == "usable_within_scope"
    assert record["value"] == pytest.approx(-0.5)
    assert record["evidence"]["calculation_path"] == "calculation.observables.static.correlations"


def test_mechanism_spin_correlation_end_to_end(tmp_path):
    from research.tests.test_mechanisms import mechanism_action, spin_plan
    from research.tests.test_reductions import spin_model_with_small_term
    run = tmp_path / "mechanism-correlation"
    request = request_for(spin_model_with_small_term(.02, anisotropy=True),
                          "Test dimensionless correlation response.", ["mechanism_test"])
    request["budget"]["max_solver_runs"] = 6
    prepare_research_task(request, run)
    execute_research_action(run, spin_plan())
    act = mechanism_action()
    act["settings"]["experiments"] = [{"case_id": "levels", "task": "quantum_low_energy",
        "settings": {"supercell_shape": [2, 2, 2], "spin": .5, "eigenvalues": 1,
                     "sz_total": 0, "seed": 31, "observables": ["correlations"]}}]
    act["settings"]["observables"] = [{"observable_id": "corr01", "case_id": "levels",
                                       "kind": "spin_correlation", "site_i": 0, "site_j": 1}]
    act["settings"]["hypotheses"] = [
        {"hypothesis_id": "correlation-robust-to-exchange-rescale",
         "statement": "Halving the exchange with a small fixed anisotropy barely moves the "
                      "dimensionless near-neighbour correlation.",
         "kind": "insensitive_response", "group_id": "exchange",
         "observable_id": "corr01", "max_change": 0.05, "numerical_tolerance": 1e-10}]
    result = execute_research_action(run, act, wait=True)
    assert result["scientific_status"] == "usable_within_scope", result
    assert result["hypotheses"][0]["status"] == "supported_within_scope", result
    observation = result["observations"][0]
    assert observation["value"] is not None
    # Cross-check against a direct ED run of the base model.
    from three_dimensional.workflow import run_three_dimensional_workflow
    direct = run_three_dimensional_workflow(
        spin_model_with_small_term(.02, anisotropy=True),
        {"task": "quantum_low_energy", "supercell_shape": [2, 2, 2], "spin": .5,
         "eigenvalues": 1, "sz_total": 0, "seed": 31, "observables": ["correlations"]})
    matrix = direct["calculation"]["observables"]["static"]["correlations"]["matrix"]
    assert observation["value"] == pytest.approx(matrix[0][1], abs=1e-10)
