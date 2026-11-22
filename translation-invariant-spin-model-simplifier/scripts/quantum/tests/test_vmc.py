"""Stage E acceptance: netket VMC backend.

Fast tests run the shared small Jastrow optimization (chain N=8) once per
session and assert contract/consistency/cross-validation against ED. The
under-optimization alarm and the non-U(1) path use deliberately tiny runs.
The honeycomb Jastrow benchmark is gated on SPINFORGE_BENCHMARK=1.
"""

import os

import pytest

from helpers import chain_model, honeycomb_model, kitaev_chain_model
from three_dimensional.workflow import run_three_dimensional_workflow

BENCHMARK = os.environ.get("SPINFORGE_BENCHMARK", "").strip() in {"1", "true", "TRUE"}


def run_vmc(model, **overrides):
    request = {
        "task": "quantum_ground_state_vmc",
        "spin": 0.5,
        "supercell_shape": [8, 1, 1],
        "seed": 7,
        "vmc_n_iter": 300,
        "vmc_n_samples": 1024,
        "vmc_final_samples": 4096,
        "vmc_n_chains": 8,
        "observables": False,
        "crosscheck": True,
    }
    request.update(overrides)
    return run_three_dimensional_workflow(model, request)["calculation"]


@pytest.fixture(scope="module")
def chain_vmc():
    result = run_vmc(chain_model(1.0))
    if result["status"] == "backend-not-connected":
        pytest.skip("netket backend not connected")
    return result


def test_contract_schema_and_crosscheck(chain_vmc):
    result = chain_vmc
    assert result["status"] == "ok"
    assert result["schema_version"] == "vmc_ground_state/v1"
    assert result["method"] == "vmc-netket-rbm"
    assert result["converged"] is True
    for key in ("energy", "energy_per_site", "energy_stderr", "convergence",
                "cross_validation", "claim_level", "ansatz", "n_parameters"):
        assert key in result, key
    assert result["claim_level"] == "variational_upper_bound"
    cross = result["cross_validation"]
    assert cross["consistent"] is True
    # Jastrow on N=8 chain: within a few percent of ED, and never below it.
    ref = cross["reference_energy_per_site"]
    assert result["energy_per_site"] >= ref - 3 * result["energy_stderr"]
    assert abs(result["energy_per_site"] - ref) < 0.05


def test_energy_trajectory_recorded(chain_vmc):
    trajectory = chain_vmc["convergence"]["energy_trajectory"]
    assert len(trajectory) >= 2
    # Optimization should not make the final energy worse than the start.
    assert trajectory[-1] <= trajectory[0] + 0.05


def test_under_optimization_triggers_alarm():
    result = run_vmc(chain_model(1.0), vmc_n_iter=2, vmc_n_samples=64,
                     vmc_final_samples=128, vmc_variance_tol=1e-12,
                     crosscheck=False)
    assert result["status"] == "inconclusive"
    assert "under-optimized" in result["blocker"]
    assert result["converged"] is False


def test_non_u1_model_runs_without_sz_conservation():
    result = run_vmc(kitaev_chain_model(), supercell_shape=[6, 1, 1],
                     vmc_n_iter=150, vmc_n_samples=512,
                     vmc_final_samples=1024, crosscheck=False)
    if result["status"] == "backend-not-connected":
        pytest.skip("netket backend not connected")
    assert result["conserve_sz"] is False
    assert result["energy_per_site"] < 0.0  # Kitaev chain ground energy < 0


@pytest.mark.skipif(not BENCHMARK, reason="benchmark wall")
def test_honeycomb_jastrow_vs_ed_n16():
    # Finite-cluster honesty: same N=16 honeycomb, ED reference; Jastrow
    # must land within 1% (its known accuracy on frustrated-free AFMs).
    result = run_vmc(honeycomb_model(), supercell_shape=[4, 2, 1],
                     vmc_n_iter=400, vmc_n_samples=2048,
                     vmc_final_samples=8192, vmc_n_chains=16, crosscheck=True)
    if result["status"] == "backend-not-connected":
        pytest.skip("netket backend not connected")
    assert result["site_count"] == 16
    cross = result["cross_validation"]
    assert cross["consistent"] is True
    ref = cross["reference_energy_per_site"]
    rel = (result["energy_per_site"] - ref) / abs(ref)
    assert 0.0 <= rel < 0.01
