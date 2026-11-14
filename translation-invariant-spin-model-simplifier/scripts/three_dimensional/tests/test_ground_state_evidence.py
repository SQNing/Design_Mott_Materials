"""Finite-cell evidence and feasible LT recovery; no assumed phase labels."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from three_dimensional.spin_system import PeriodicSpinSystem, minimize_fixed_length


def system(bonds, shape, basis=1):
    payload = {"lattice_structure": {"basis_sites": [{"position": [0., 0., 0.]}]*basis},
        "bonds": [{"source":i,"target":j,"vector":v,"matrix":np.asarray(m).tolist()}
                  for i,j,v,m in bonds]}
    return PeriodicSpinSystem(payload, shape)


def chain():
    return system([(0,0,[1,0,0],np.eye(3)), (0,0,[4,0,0],-.01*np.eye(3))], [4,1,1])


def test_stationary_high_energy_search_is_retained_and_recovered():
    original = [[0.,0.,.5]]*4
    result = minimize_fixed_length(chain(), {"spin_length":.5,"starts":1,"initial_spins":original})
    assert result["energy_per_cell"] == pytest.approx(-.2525, abs=1e-10)
    initial = result["initial_search"]
    assert initial["energy_per_cell"] == pytest.approx(.2475)
    np.testing.assert_allclose(initial["spins"],original)
    assert len(initial["starts"]) == 1
    assert result["ground_state_evidence"]["finite_cell_status"] == "bound_saturated"
    assert result["ground_state_evidence"]["infinite_lattice_status"] == "not_certified"
    assert result["recovery"]["accepted"] is True
    assert result["recovery"]["additional_starts"] == 1
    np.testing.assert_allclose(np.linalg.norm(result["spins"],axis=1),.5,atol=1e-12)


def test_recovery_can_be_disabled_without_certifying_a_stationary_state():
    result = minimize_fixed_length(chain(), {"spin_length":.5,"starts":1,
        "initial_spins":[[0.,0.,.5]]*4,"fourier_seed_recovery":False})
    assert result["status"] == "ok"  # usable as a stationary reference only
    assert result["energy_per_cell"] == pytest.approx(.2475)
    assert result["ground_state_evidence"]["stationary"] is True
    assert result["ground_state_evidence"]["finite_cell_status"] == "not_certified"
    assert result["recovery"]["attempted"] is False


def test_unequal_local_lengths_in_the_lt_mode_do_not_certify_a_loose_bound():
    model = system([(0,0,[1,0,0],np.eye(3)),(1,1,[1,0,0],-.1*np.eye(3))],[2,1,1],basis=2)
    result = minimize_fixed_length(model,{"spin_length":.5,"starts":2,"seed":7})
    assert result["energy_per_cell"] == pytest.approx(-.275,abs=1e-9)
    assert result["finite_cell_bound_gap"] > .2
    assert result["ground_state_evidence"]["finite_cell_status"] == "not_certified"
    assert result["recovery"]["attempted"] is False
    assert "local" in result["recovery"]["reason"].lower()
    np.testing.assert_allclose(np.linalg.norm(result["spins"],axis=1),.5,atol=1e-12)


def test_anisotropic_feasible_mode_is_checked_as_a_full_spin_tensor():
    model = system([(0,0,[1,0,0],-np.diag([.4,.7,1.]))],[2,1,1])
    result = minimize_fixed_length(model,{"spin_length":.5,"starts":1,"initial_spins":[[.5,0,0]]*2})
    assert result["energy_per_cell"] == pytest.approx(-.25,abs=1e-10)
    assert result["recovery"]["accepted"] is True
    assert result["ground_state_evidence"]["finite_cell_status"] == "bound_saturated"


def test_complex_two_sublattice_mode_respects_fourier_phase_and_lengths():
    bonds=[]
    shells={1:[[0,0,0],[-1,0,0],[0,-1,0]],
            2:[[1,0,0],[0,1,0],[1,-1,0]],
            3:[[-1,-1,0],[1,-1,0],[-1,1,0]]}
    for shell,strength in [(1,1.),(2,.3),(3,.05)]:
        for left in ([0,1] if shell==2 else [0]):
            for v in shells[shell]:
                bonds.append((left,left if shell==2 else 1,v,strength*np.eye(3)))
    bonds.extend((i,i,[6,0,0],-.001*np.eye(3)) for i in [0,1])
    model=system(bonds,[6,6,1],basis=2)
    result=minimize_fixed_length(model,{"spin_length":.5,"starts":1,"initial_spins":[[0.,0.,.5]]*72})
    assert result["energy_per_cell"] == pytest.approx(-.4255,abs=1e-10)
    assert result["ground_state_evidence"]["finite_cell_status"] == "bound_saturated"
    assert result["recovery"]["accepted"] is True
    np.testing.assert_allclose(np.linalg.norm(result["spins"],axis=1),.5,atol=1e-12)


def test_a_state_below_the_numerical_bound_is_an_inconsistency(monkeypatch):
    model=chain()
    monkeypatch.setattr(model,'finite_cell_lower_bound',lambda _s:(1.,[0.,0.,0.]))
    result=minimize_fixed_length(model,{"spin_length":.5,"starts":1,"seed":3})
    assert result["status"] == "inconclusive"
    assert result["ground_state_evidence"]["finite_cell_status"] == "inconsistent_bound"
