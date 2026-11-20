"""Benchmark wall: sector ED against exact Bethe-ansatz and literature values.

These tests are slower than unit tests (N=24 sector solves) and run in the
authoritative acceptance pass; they are skipped unless SPINFORGE_BENCHMARK=1.
"""

import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import chain_model, honeycomb_model
from three_dimensional.workflow import run_three_dimensional_workflow

_BENCHMARK_ON = (os.environ.get("SPINFORGE_BENCHMARK") == "1"
                 or os.environ.get("DMM_BENCHMARK") == "1")  # legacy flag
pytestmark = pytest.mark.skipif(not _BENCHMARK_ON,
                                reason="benchmark wall; run with SPINFORGE_BENCHMARK=1")


def bethe_ground_state_energy(n_sites, exchange=1.0, iterations=2000, damping=0.5):
    """XXX chain ground-state energy from the real Bethe roots (N even).

    Equations: N * acot(2 lambda_j) = pi I_j + sum_k acot(lambda_j - lambda_k),
    I_j half-integers -(M-1)/2 .. (M-1)/2 for M = N/2 down spins.
    Energy: E = N J/4 - (J/2) sum_j 1/(lambda_j^2 + 1/4).
    """
    M = n_sites // 2
    quantum_numbers = np.arange(M) - (M - 1) / 2.0
    lam = 0.5 * np.tan(np.pi * quantum_numbers / n_sites)
    for _step in range(iterations):
        diff = lam[:, None] - lam[None, :]
        np.fill_diagonal(diff, 1.0)  # placeholder; excluded below
        pair = np.arctan(diff)  # atan(lambda_j - lambda_k)
        np.fill_diagonal(pair, 0.0)  # k == j term is excluded from the sum
        rhs = np.pi * quantum_numbers + pair.sum(axis=1)
        target = 0.5 * np.tan(rhs / n_sites)
        shift = np.max(np.abs(target - lam))
        lam = (1 - damping) * lam + damping * target
        if shift < 1e-13:
            break
    energy = n_sites * exchange / 4.0 - exchange / 2.0 * np.sum(1.0 / (lam ** 2 + 0.25))
    return float(energy)


def run_ed(model, **request):
    request.setdefault("task", "quantum_low_energy")
    request.setdefault("spin", 0.5)
    request.setdefault("seed", 7)
    result = run_three_dimensional_workflow(model, request)
    assert result["status"] == "ok", result.get("blocker")
    return result["calculation"]


def test_bethe_solver_recovers_small_cluster_energies():
    # Self-check of the independent Bethe solver against exact small-cluster ED.
    assert bethe_ground_state_energy(4) == pytest.approx(-2.0, abs=1e-10)
    calc = run_ed(chain_model(), supercell_shape=[6, 1, 1], sz_total=0, eigenvalues=1)
    assert bethe_ground_state_energy(6) == pytest.approx(calc["eigenvalues"][0], abs=1e-10)


def test_heisenberg_chain_n24_matches_bethe_ansatz():
    calc = run_ed(chain_model(), supercell_shape=[24, 1, 1], sz_total=0,
                  momentum=[0, 0, 0], eigenvalues=2, max_memory_mb=8192)
    reference = bethe_ground_state_energy(24)
    assert calc["eigenvalues"][0] == pytest.approx(reference, abs=1e-10)
    assert calc["sector"]["sector_dimension"] < 200000


def test_heisenberg_chain_n24_sector_decomposition_consistency():
    # The k=0 ground state must coincide with the lowest Sz=0 eigenvalue.
    sz_only = run_ed(chain_model(), supercell_shape=[16, 1, 1], sz_total=0, eigenvalues=1)
    per_k = [run_ed(chain_model(), supercell_shape=[16, 1, 1], sz_total=0,
                    momentum=[n, 0, 0], eigenvalues=1)["eigenvalues"][0]
             for n in range(16)]
    assert min(per_k) == pytest.approx(sz_only["eigenvalues"][0], abs=1e-10)


# Thermodynamic-limit QMC value: Albuquerque et al., PRB 84, 024406 (2011).
HONEYCOMB_QMC_E0_PER_SITE = -0.54455


def test_honeycomb_n24_sector_consistency_and_literature_window():
    shape = [4, 3, 1]
    settings = dict(supercell_shape=shape, eigenvalues=2, max_memory_mb=8192)
    k0 = run_ed(honeycomb_model(), sz_total=0, momentum=[0, 0, 0], **settings)
    sz_only = run_ed(honeycomb_model(), sz_total=0, **settings)
    # Exact internal cross-check: momentum resolution must reproduce the
    # Sz-sector ground state to solver tolerance.
    assert k0["eigenvalues"][0] == pytest.approx(sz_only["eigenvalues"][0], abs=1e-8)
    e0 = k0["energy_per_site"]
    # Honeycomb ED clusters approach e_inf from below (N=2: -0.75 -> N=24:
    # -0.5557); the N=24 value must sit inside the finite-size window below
    # the QMC thermodynamic result.
    assert HONEYCOMB_QMC_E0_PER_SITE - 2e-2 <= e0 < HONEYCOMB_QMC_E0_PER_SITE


def test_honeycomb_n24_structure_factor_neel():
    calc = run_ed(honeycomb_model(), supercell_shape=[4, 3, 1], sz_total=0,
                  momentum=[0, 0, 0], eigenvalues=1, max_memory_mb=8192,
                  observables=["structure_factor"])
    factor = calc["observables"]["static"]["structure_factor"]
    points = factor["points"]
    assert all(p["s_q"] >= -1e-10 for p in points)  # spectral positivity
    # Antiferromagnetic correlations invert the nearest-neighbour form factor:
    # the plain S(q) must peak at the grid minimum of Re phi(q), and S(Gamma)
    # must lie far below the peak.
    deltas = [(1 / 3, 1 / 3), (-2 / 3, 1 / 3), (1 / 3, -2 / 3)]

    def re_phi(q):
        return sum(np.cos(2 * np.pi * (q[0] * d[0] + q[1] * d[1])) for d in deltas)

    phi_min = min(re_phi(p["q"]) for p in points)
    peak = factor["ordering_q"]
    assert abs(re_phi(peak) - phi_min) < 1e-9
    s_at = {tuple(p["q"]): p["s_q"] for p in points}
    assert s_at[tuple(peak)] > 3 * s_at[(0.0, 0.0, 0.0)]


def test_level_statistics_integrable_vs_frustrated():
    # Adjacent-gap ratio in a symmetry-resolved mid-spectrum window: the
    # integrable Heisenberg chain stays Poisson-like while the nonintegrable
    # J1-J2 chain drifts toward GOE (finite N=16 keeps it below the 0.5307
    # asymptote; the qualitative separation is the signature here).
    def mean_r(model, shape):
        calc = run_ed(model, supercell_shape=shape, sz_total=0, momentum=[1, 0, 0],
                      eigenvalues=100000, observables=["level_statistics"],
                      level_statistics_window=[0.25, 0.75])
        stats = calc["observables"]["static"]["level_statistics"]
        assert stats["count"] >= 100
        return stats["mean_r"]
    integrable = mean_r(chain_model(1.0), [16, 1, 1])
    frustrated = mean_r(chain_model(1.0, second_neighbor=0.24), [16, 1, 1])
    assert integrable < 0.44
    assert frustrated > integrable + 0.04
