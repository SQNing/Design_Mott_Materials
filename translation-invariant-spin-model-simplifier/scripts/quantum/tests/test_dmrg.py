"""DMRG backend tests (stage D): OpSum compiler, driver, ED cross-checks."""
import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import chain_model, honeycomb_model, kitaev_chain_model
from three_dimensional.workflow import run_three_dimensional_workflow

BENCHMARK = (os.environ.get("SPINFORGE_BENCHMARK") == "1"
             or os.environ.get("DMM_BENCHMARK") == "1")


def _backend_available():
    from research.adapters import _dmrg_capability
    return _dmrg_capability()["status"] == "supported"


BACKEND = _backend_available()
NEEDS_BACKEND = pytest.mark.skipif(not BACKEND,
                                   reason="ITensor DMRG backend not connected")


def run_dmrg(model, **request):
    request.setdefault("task", "quantum_ground_state_dmrg")
    request.setdefault("spin", 0.5)
    result = run_three_dimensional_workflow(model, request)
    return result


# ---------------------------------------------------------------------------
# OpSum compiler (pure Python, always runs)

def test_opsum_compiler_chain_terms_and_u1():
    from classical.build_spin_only_solver_payload import compile_canonical_hamiltonian
    from three_dimensional.workflow import (run_hamiltonian_symmetry_gate,
                                            SymmetryGateRequest, global_spin_payload)
    from three_dimensional.spin_system import PeriodicSpinSystem
    from quantum.mpo_compiler import compile_opsum
    gate = run_hamiltonian_symmetry_gate(
        compile_canonical_hamiltonian(chain_model(1.0)),
        SymmetryGateRequest(repair=False))
    system = PeriodicSpinSystem(global_spin_payload(gate), [4, 1, 1])
    spec = compile_opsum(system, 0.5)
    assert spec["format"] == "spinforge-opsum/v1"
    assert spec["site_count"] == 4 and spec["local_dim"] == 2
    assert spec["conserve_sz"] is True
    assert spec["geometry"] == "chain"
    # 4-site periodic chain: 4 nearest-neighbour bonds (images merged per pair
    # for L=2 only; L=4 keeps 4 distinct pairs).
    assert len(spec["bonds"]) == 4
    for bond in spec["bonds"]:
        ops = {(t[0], t[1]): t[2] for t in bond["terms"]}
        assert ops == {("Sx", "Sx"): 1.0, ("Sy", "Sy"): 1.0, ("Sz", "Sz"): 1.0}


def test_opsum_compiler_snake_order_strip_and_non_u1():
    from classical.build_spin_only_solver_payload import compile_canonical_hamiltonian
    from three_dimensional.workflow import (run_hamiltonian_symmetry_gate,
                                            SymmetryGateRequest, global_spin_payload)
    from three_dimensional.spin_system import PeriodicSpinSystem
    from quantum.mpo_compiler import compile_opsum
    gate = run_hamiltonian_symmetry_gate(
        compile_canonical_hamiltonian(honeycomb_model(1.0)),
        SymmetryGateRequest(repair=False))
    system = PeriodicSpinSystem(global_spin_payload(gate), [3, 2, 1])
    spec = compile_opsum(system, 0.5)
    assert spec["geometry"] == "strip"
    assert sorted(spec["mps_order"]) == list(range(system.site_count))
    # Interior honeycomb bonds stay short-range in snake order; only the
    # periodic wrap bonds may span the whole MPS chain.
    interior = [b for b in spec["bonds"]
                if abs(b["target"] - b["source"]) <= 2 * system.basis_count]
    assert len(interior) >= len(spec["bonds"]) - 2 * system.shape[1]

    gate = run_hamiltonian_symmetry_gate(
        compile_canonical_hamiltonian(kitaev_chain_model()),
        SymmetryGateRequest(repair=False))
    system = PeriodicSpinSystem(global_spin_payload(gate), [4, 1, 1])
    spec = compile_opsum(system, 0.5)
    assert spec["conserve_sz"] is False


def test_dmrg_rejects_3d_supercell():
    from classical.build_spin_only_solver_payload import compile_canonical_hamiltonian
    from three_dimensional.workflow import (run_hamiltonian_symmetry_gate,
                                            SymmetryGateRequest, global_spin_payload)
    from three_dimensional.spin_system import PeriodicSpinSystem
    from quantum.mpo_compiler import compile_opsum
    gate = run_hamiltonian_symmetry_gate(
        compile_canonical_hamiltonian(chain_model(1.0)),
        SymmetryGateRequest(repair=False))
    system = PeriodicSpinSystem(global_spin_payload(gate), [2, 2, 2])
    with pytest.raises(ValueError, match="strips"):
        compile_opsum(system, 0.5)


def test_explicit_route_reports_connection_status():
    from research.adapters import capability_for
    capability = capability_for(chain_model(), "quantum_ground_state_dmrg",
                                {"backend": "dmrg"})
    if BACKEND:
        assert capability["status"] == "supported"
        assert capability["solver_id"] == "quantum-dmrg-itensor"
    else:
        assert capability["status"] == "unsupported"
        assert "backend-not-connected" in capability["blocker"]


# ---------------------------------------------------------------------------
# End-to-end (require Julia + ITensor)

@NEEDS_BACKEND
def test_dmrg_dimer_ground_state_energy():
    # 2-site periodic chain: two bonds, H = 2 S1.S2, singlet E0 = -3/2.
    result = run_dmrg(chain_model(), supercell_shape=[2, 1, 1],
                      dmrg_sweeps=8, dmrg_maxdim=32, dmrg_noise=0.0)
    calc = result["calculation"]
    assert result["status"] == "ok", result.get("blocker") or calc.get("blocker")
    assert calc["converged"] is True
    assert calc["energy"] == pytest.approx(-1.5, abs=1e-10)
    assert calc["claim_level"] == "finite_cell_ground_state"


@NEEDS_BACKEND
def test_dmrg_chain_n8_matches_ed_energy_and_correlations():
    n = 8
    shape = [n, 1, 1]
    common = dict(supercell_shape=shape, spin=0.5)
    ed = run_three_dimensional_workflow(
        chain_model(1.0), {"task": "quantum_low_energy", "eigenvalues": 2,
                           "observables": ["correlations"], **common})
    assert ed["status"] == "ok"
    dmrg = run_dmrg(chain_model(1.0), dmrg_sweeps=10, dmrg_maxdim=128,
                    dmrg_noise=0.0, **common)
    calc = dmrg["calculation"]
    assert dmrg["status"] == "ok", dmrg.get("blocker") or calc.get("blocker")
    assert calc["converged"] is True
    e_ed = ed["calculation"]["eigenvalues"][0]
    assert calc["energy"] == pytest.approx(e_ed, abs=1e-8)
    # DMRG is variational: never below the ED ground state.
    assert calc["energy"] >= e_ed - 1e-12
    # Spin-spin correlations C_ij = <S_i.S_j> on the ground state (MPS order
    # is the natural chain order for 1D).
    obs = calc["observables"]
    dot = np.asarray(obs["correlation_dot_flat"]).reshape(n, n)
    c_ed = np.asarray(
        ed["calculation"]["observables"]["static"]["correlations"]["matrix"])
    assert np.max(np.abs(dot - c_ed)) < 1e-6
    # Entanglement entropy profile is symmetric and positive in the middle.
    ent = np.asarray(obs["bond_entropies"])
    assert len(ent) == n - 1
    assert np.all(ent > -1e-12)
    assert ent[n // 2 - 1] > 0.5


@NEEDS_BACKEND
def test_dmrg_convergence_diagnostics_and_honest_inconclusive():
    # Starve the run: 1 sweep at tiny maxdim must not report converged.
    result = run_dmrg(chain_model(1.0), supercell_shape=[12, 1, 1], spin=0.5,
                      dmrg_sweeps=1, dmrg_maxdim=2, dmrg_noise=0.0)
    calc = result["calculation"]
    assert calc["converged"] is False
    assert result["status"] in {"inconclusive", "ok"}
    convergence = calc["convergence"]
    assert set(convergence) >= {"variance", "delta_e_last_sweep",
                                "truncation_discard", "criteria",
                                "sweep_energies", "sweep_maxlinkdim"}
    assert len(convergence["sweep_energies"]) == 1


@NEEDS_BACKEND
def test_dmrg_strip_geometry_runs():
    result = run_dmrg(honeycomb_model(1.0), supercell_shape=[3, 2, 1], spin=0.5,
                      dmrg_sweeps=10, dmrg_maxdim=128, dmrg_noise=0.0)
    calc = result["calculation"]
    assert result["status"] == "ok", result.get("blocker") or calc.get("blocker")
    assert calc["geometry"] == "strip"
    # Cross-check against ED on the same 12-site cell.
    ed = run_three_dimensional_workflow(
        honeycomb_model(1.0), {"task": "quantum_low_energy",
                               "supercell_shape": [3, 2, 1], "spin": 0.5,
                               "eigenvalues": 1})
    assert calc["energy"] == pytest.approx(
        ed["calculation"]["eigenvalues"][0], abs=1e-7)


@NEEDS_BACKEND
@pytest.mark.skipif(not BENCHMARK,
                    reason="benchmark wall; run with SPINFORGE_BENCHMARK=1")
def test_dmrg_chain_n100_bethe_anchor():
    # Periodic Heisenberg chain N=100, E/N vs Bethe 1/4 - ln 2 (rel < 1e-6).
    result = run_dmrg(chain_model(1.0), supercell_shape=[100, 1, 1], spin=0.5,
                      dmrg_sweeps=14, dmrg_maxdim=500, dmrg_noise=0.0,
                      dmrg_cutoff=1e-14, observables=False,
                      dmrg_timeout_seconds=7200)
    calc = result["calculation"]
    assert result["status"] == "ok", result.get("blocker") or calc.get("blocker")
    assert calc["converged"] is True
    bethe = 0.25 - np.log(2.0)
    assert calc["energy_per_site"] == pytest.approx(bethe, rel=1e-6)
