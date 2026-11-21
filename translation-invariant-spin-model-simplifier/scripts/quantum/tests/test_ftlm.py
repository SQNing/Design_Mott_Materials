"""FTLM/TPQ finite-temperature thermodynamics tests (stage C)."""
import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import chain_model, honeycomb_model, kitaev_chain_model, \
    heisenberg_dense_reference
from three_dimensional.workflow import run_three_dimensional_workflow

BENCHMARK = (os.environ.get("SPINFORGE_BENCHMARK") == "1"
             or os.environ.get("DMM_BENCHMARK") == "1")


def run_thermo(model, **request):
    request.setdefault("task", "quantum_thermodynamics")
    request.setdefault("spin", 0.5)
    request.setdefault("seed", 11)
    result = run_three_dimensional_workflow(model, request)
    assert result["status"] == "ok", result.get("blocker")
    return result["calculation"]


def exact_partition(dense, temperatures, sz_values=None):
    """Exact E, C, chi, S per site from a dense Hamiltonian."""
    evals = np.linalg.eigvalsh(dense)
    e0 = evals[0]
    n = int(round(np.log2(dense.shape[0])))
    out = {}
    for t in temperatures:
        beta = 1.0 / t
        w = np.exp(-beta * (evals - e0))
        z = w.sum()
        e = (w * evals).sum() / z
        e2 = (w * evals ** 2).sum() / z
        entry = {"E": e / n, "C": (e2 - e ** 2) * beta ** 2 / n,
                 "S": (beta * e + np.log(z) - beta * e0) / n}
        if sz_values is not None:
            m = (w * sz_values).sum() / z
            m2 = (w * sz_values ** 2).sum() / z
            entry["chi"] = beta * (m2 - m ** 2) / n
        out[t] = entry
    return out


# ---------------------------------------------------------------------------
# Lanczos / TPQ cores

def test_lanczos_recovers_dense_spectrum_and_quadrature():
    from quantum.ftlm import _lanczos, _ritz_pairs
    rng = np.random.default_rng(0)
    a = rng.normal(size=(24, 24))
    a = a + a.T
    exact = np.linalg.eigvalsh(a)
    v0 = rng.normal(size=24)
    alphas, betas, _q = _lanczos(a, v0, 24)
    values, weights, _c = _ritz_pairs(alphas, betas)
    np.testing.assert_allclose(values, exact, atol=1e-8)
    v0n = v0 / np.linalg.norm(v0)
    beta = 1.7
    import scipy.linalg
    moment = float(v0n @ scipy.linalg.expm(-beta * a) @ v0n)
    assert np.sum(weights * np.exp(-beta * values)) == pytest.approx(moment, rel=1e-10)


def test_tpq_realization_matches_exact_expm():
    import scipy.linalg
    import scipy.sparse
    from quantum.ftlm import _tpq_realization
    rng = np.random.default_rng(2)
    a = rng.normal(size=(20, 20))
    a = a + a.T
    seed = 42
    v_expected = np.random.default_rng(seed).normal(size=20)
    v_expected /= np.linalg.norm(v_expected)
    betas, energies, energies2, _o, log_norms = _tpq_realization(
        scipy.sparse.csr_matrix(a), 60.0, 3.0, np.random.default_rng(seed),
        slice_beta=0.25)
    for i, b in enumerate(betas):
        e = scipy.linalg.expm(-b * a)
        num = float(v_expected @ e @ a @ v_expected)
        den = float(v_expected @ e @ v_expected)
        assert energies[i] == pytest.approx(num / den, abs=1e-10)
        assert log_norms[i] == pytest.approx(np.log(den), abs=1e-8)


# ---------------------------------------------------------------------------
# Contract shape

def test_contract_schema_sampling_and_error_bars():
    calc = run_thermo(chain_model(), supercell_shape=[6, 1, 1],
                      temperatures=[5.0, 1.0], samples=4, lanczos_steps=60,
                      fields=[0.5], staggered_momentum=[0.5, 0.0, 0.0])
    assert calc["schema_version"] == "thermodynamics/v1"
    assert calc["source"] == "ftlm"
    sampling = calc["sampling"]
    assert sampling["random_state_samples"] == 4
    assert sampling["lanczos_steps"] == 60
    assert sampling["seed"] == 11
    for row in calc["grid"]:
        assert set(row) >= {"temperature", "beta", "energy_per_site",
                            "heat_capacity_per_site", "entropy_per_site",
                            "uniform_susceptibility_per_site",
                            "staggered_susceptibility_zz_per_site"}
        assert row["energy_per_site"]["stderr"] is not None
    assert calc["field_scans"] and calc["field_scans"][0]["fields"] == [0.5]
    assert calc["sz_decomposition"] is True
    dims = sum(s["dimension"] for s in calc["sectors"])
    assert dims == 2 ** 6


def test_non_u1_model_skips_sz_and_rejects_fields():
    calc = run_thermo(kitaev_chain_model(), supercell_shape=[4, 1, 1],
                      temperatures=[2.0], samples=2, lanczos_steps=30)
    assert calc["sz_decomposition"] is False
    assert len(calc["sectors"]) == 1 and calc["sectors"][0]["sz_total"] is None
    result = run_three_dimensional_workflow(
        kitaev_chain_model(), {"task": "quantum_thermodynamics",
                               "supercell_shape": [4, 1, 1], "spin": 0.5,
                               "temperatures": [2.0], "fields": [0.5]})
    assert result["status"] == "invalid_request"
    assert "Sz" in result["blocker"]


# ---------------------------------------------------------------------------
# Exact small-cluster checks

def test_dimer_thermodynamics_analytic():
    # 2-site periodic chain: two bonds, H = 2 S1.S2 (singlet -1.5, triplet +0.5).
    # The Hilbert space is tiny, so FTLM typicality does not apply: converge
    # the stochastic estimator with many realizations and compare within the
    # bootstrap error bars instead of expecting machine precision.
    ts = [5.0, 1.0, 0.5, 0.3]
    calc = run_thermo(chain_model(), supercell_shape=[2, 1, 1], temperatures=ts,
                      samples=1024, lanczos_steps=10, fields=[0.7],
                      bootstrap_samples=64)
    rows = {r["temperature"]: r for r in calc["grid"]}
    for t in ts:
        beta = 1.0 / t
        z = np.exp(1.5 * beta) + 3.0 * np.exp(-0.5 * beta)
        e = (-1.5 * np.exp(1.5 * beta) + 1.5 * np.exp(-0.5 * beta)) / z
        var = (2.25 * np.exp(1.5 * beta) + 0.75 * np.exp(-0.5 * beta)) / z - e ** 2
        chi = beta * 2.0 * np.exp(-0.5 * beta) / z / 2.0
        row = rows[t]
        tol_e = max(5e-3, 3.0 * (row["energy_per_site"]["stderr"] or 0.0))
        tol_c = max(5e-3, 3.0 * (row["heat_capacity_per_site"]["stderr"] or 0.0))
        tol_chi = max(5e-3, 3.0 * (row["uniform_susceptibility_per_site"]["stderr"] or 0.0))
        assert abs(row["energy_per_site"]["value"] - e / 2.0) < tol_e
        assert abs(row["heat_capacity_per_site"]["value"] - var * beta ** 2 / 2.0) < tol_c
        assert abs(row["uniform_susceptibility_per_site"]["value"] - chi) < tol_chi
    # M(T,H) on the dimer: Z(h) = e^{1.5b} + e^{-0.5b}(1 + 2 cosh(bh))
    scan = {s["temperature"]: s for s in calc["field_scans"]}[1.0]
    beta, h = 1.0, 0.7
    zh = np.exp(1.5 * beta) + np.exp(-0.5 * beta) * (1 + 2 * np.cosh(beta * h))
    m = 2.0 * np.sinh(beta * h) * np.exp(-0.5 * beta) / zh / 2.0
    assert scan["magnetization_per_site"][0] == pytest.approx(m, abs=2e-2)


def test_chain_n8_matches_dense_partition_function():
    n = 8
    ts = [10.0, 2.0, 1.0, 0.5]
    dense = heisenberg_dense_reference(chain_model(1.0), (n, 1, 1), 0.5)
    import itertools
    digits = np.array(list(itertools.product([0, 1], repeat=n)))
    sz_of = digits.sum(axis=1) - n / 2.0
    # Sz is diagonal; resolve exact partition function per sector for chi.
    exact = {}
    evals, evecs = np.linalg.eigh(dense)
    e0 = evals[0]
    # <n|Sz_total^2|n> per eigenstate. Basis-invariant and robust to the
    # arbitrary eigenvector phases/mixing inside Sz-degenerate subspaces.
    sz2_n = (np.abs(evecs) ** 2).T @ (sz_of ** 2)
    for t in ts:
        beta = 1.0 / t
        w = np.exp(-beta * (evals - e0))
        z = w.sum()
        e = (w * evals).sum() / z
        e2 = (w * evals ** 2).sum() / z
        m2 = (w * sz2_n).sum() / z
        exact[t] = {"E": e / n, "C": (e2 - e ** 2) * beta ** 2 / n,
                    "chi": beta * m2 / n,
                    "S": (beta * e + np.log(z) - beta * e0) / n}
    # 256-dimensional Hilbert space: typicality is weak, so converge the
    # stochastic estimators with many realizations (the run is sub-second).
    calc = run_thermo(chain_model(1.0), supercell_shape=[n, 1, 1], temperatures=ts,
                      samples=512, lanczos_steps=250, bootstrap_samples=64)
    rows = {r["temperature"]: r for r in calc["grid"]}
    for t in ts:
        row = rows[t]
        tol_e = max(5e-3, 3.0 * (row["energy_per_site"]["stderr"] or 0.0))
        tol_c = max(1e-2, 3.0 * (row["heat_capacity_per_site"]["stderr"] or 0.0))
        tol_chi = max(8e-3, 3.0 * (row["uniform_susceptibility_per_site"]["stderr"] or 0.0))
        assert abs(row["energy_per_site"]["value"] - exact[t]["E"]) < tol_e
        assert abs(row["heat_capacity_per_site"]["value"] - exact[t]["C"]) < tol_c
        assert abs(row["uniform_susceptibility_per_site"]["value"] - exact[t]["chi"]) < tol_chi
        assert abs(row["entropy_per_site"]["value"] - exact[t]["S"]) < 2e-2


def test_ftlm_tpq_consistency_block_and_agreement():
    calc = run_thermo(chain_model(1.0), supercell_shape=[8, 1, 1],
                      temperatures=[5.0, 1.0, 0.5], samples=6, lanczos_steps=200,
                      method="both", bootstrap_samples=64)
    consistency = calc["consistency"]
    assert consistency is not None
    assert calc["method"] == "ftlm+tpq"
    # Two independent estimators must agree within combined 3 sigma.
    assert consistency["max_z_energy"] <= 3.0
    assert consistency["max_z_heat_capacity"] <= 3.0
    assert consistency["consistent"] is True


def test_magnetization_matches_uniform_susceptibility_fluctuation():
    # chi = dM/dh at h -> 0 must equal beta/N Var(Sz) from the zero-field run.
    ts = [2.0, 1.0]
    calc = run_thermo(chain_model(1.0), supercell_shape=[8, 1, 1], temperatures=ts,
                      samples=6, lanczos_steps=200, fields=[0.05, 0.10])
    scans = {s["temperature"]: s for s in calc["field_scans"]}
    rows = {r["temperature"]: r for r in calc["grid"]}
    for t in ts:
        m1, m2 = scans[t]["magnetization_per_site"]
        slope = (m2 - m1) / 0.05
        chi = rows[t]["uniform_susceptibility_per_site"]["value"]
        assert slope == pytest.approx(chi, rel=0.02)


def test_staggered_susceptibility_chain():
    # zz staggered susceptibility at q=pi vs dense reference.
    n = 8
    dense = heisenberg_dense_reference(chain_model(1.0), (n, 1, 1), 0.5)
    evals, evecs = np.linalg.eigh(dense)
    import itertools
    digits = np.array(list(itertools.product([0, 1], repeat=n)))
    mz = digits - 0.5
    signs = (-1.0) ** np.arange(n)
    mq = (mz * signs).sum(axis=1)  # M_pi^z on each product state
    o_n = (np.abs(evecs) ** 2).T @ (mq ** 2)
    e0 = evals[0]
    ts = [4.0, 1.0]
    calc = run_thermo(chain_model(1.0), supercell_shape=[n, 1, 1], temperatures=ts,
                      samples=6, lanczos_steps=200,
                      staggered_momentum=[0.5, 0.0, 0.0])
    rows = {r["temperature"]: r for r in calc["grid"]}
    for t in ts:
        beta = 1.0 / t
        w = np.exp(-beta * (evals - e0))
        exact = beta * float((w * o_n).sum() / w.sum()) / n
        value = rows[t]["staggered_susceptibility_zz_per_site"]["value"]
        assert value == pytest.approx(exact, rel=0.06)


# ---------------------------------------------------------------------------
# Benchmarks (SPINFORGE_BENCHMARK=1): literature anchors

@pytest.mark.skipif(not BENCHMARK, reason="benchmark wall; run with SPINFORGE_BENCHMARK=1")
def test_chain_n24_bethe_anchors():
    """N=24 Heisenberg chain vs exact Bethe-ansatz thermodynamic anchors.

    Anchors (all for H = J sum S.S, J=1, k_B=1):
    - Curie law: chi*T -> 1/4 as T -> infinity.
    - High-T specific heat: C*T^2 -> 3/16 (exact infinite-T variance).
    - Bonner-Fisher maximum: chi_max ~= 0.1469/J at T ~= 0.64 J
      (Bonner & Fisher 1964, confirmed by TBA; Kluemper & Johnston 2000).
    - Finite-T TBA value: chi(T=0.4J) ~= 0.134/J on the way down from the
      maximum (Kluemper & Johnston 2000); the Yang-Yang zero-T limit
      chi(0) = 1/pi^2 ~= 0.1013/J (Yang & Yang 1966) is only reached far
      below T=0.4J, so it acts as a strict lower bound here, not an anchor.
    """
    n = 24
    ts = [100.0, 10.0, 2.0, 1.0, 0.64, 0.4]
    calc = run_thermo(chain_model(1.0), supercell_shape=[n, 1, 1], temperatures=ts,
                      samples=6, lanczos_steps=300, bootstrap_samples=64,
                      max_memory_mb=8192)
    rows = {r["temperature"]: r for r in calc["grid"]}
    chi = lambda t: rows[t]["uniform_susceptibility_per_site"]["value"]
    cap = lambda t: rows[t]["heat_capacity_per_site"]["value"]
    # Curie anchor (2% accounts for the 1/T HTSE tail at T=100).
    assert chi(100.0) * 100.0 == pytest.approx(0.25, rel=0.02)
    # Infinite-T variance anchor.
    assert cap(100.0) * 100.0 ** 2 == pytest.approx(3.0 / 16.0, rel=0.03)
    # Bonner-Fisher maximum window (finite-size shifts are a few 1e-3 here).
    assert chi(0.64) == pytest.approx(0.1469, rel=0.04)
    # Finite-T TBA value below the maximum, with the Yang-Yang zero-T limit
    # as a strict lower bound (finite-size shifts are upward at N=24).
    assert chi(0.4) == pytest.approx(0.134, rel=0.06)
    assert chi(0.4) > 1.0 / np.pi ** 2
    assert chi(0.4) < chi(0.64)


@pytest.mark.skipif(not BENCHMARK, reason="benchmark wall; run with SPINFORGE_BENCHMARK=1")
def test_honeycomb_high_temperature_matches_classical_mc():
    """High-T cross-check: quantum FTLM vs classical Metropolis, same N=12 cell.

    Matching leading HTSE: classical exchange J_cl = S(S+1) J = 3/4 J makes the
    infinite-T variance (and hence C(T) at high T) agree exactly.
    """
    ts = [20.0, 10.0]
    calc = run_thermo(honeycomb_model(1.0), supercell_shape=[3, 2, 1],
                      temperatures=ts, samples=4, lanczos_steps=200,
                      bootstrap_samples=32, max_memory_mb=4096)
    from three_dimensional.workflow import run_three_dimensional_workflow as wf
    mc = wf(honeycomb_model(0.75), {"task": "classical_monte_carlo",
                                    "supercell_shape": [3, 2, 1], "spin_length": 1.0,
                                    "temperatures": ts, "burn_in": 2000,
                                    "sweeps": 20000, "seed": 91})
    assert mc["status"] == "ok"
    q_rows = {r["temperature"]: r for r in calc["grid"]}
    c_rows = {r["temperature"]: r for r in mc["calculation"]["grid"]}
    for t in ts:
        cq = q_rows[t]["heat_capacity_per_site"]["value"]
        cc = c_rows[t]["heat_capacity_per_site"]
        err = c_rows[t]["heat_capacity_stderr"] or 0.0
        assert abs(cq - cc) < max(0.05 * abs(cc), 4 * err, 2e-3)
