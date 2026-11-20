"""Sector basis construction: enumeration, translation orbits, momentum reps."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from quantum.ed_sectors import (enumerate_states, momentum_phases, momentum_sector,
                                spin_digit_data, state_powers, translation_group,
                                trivial_sector)


def test_full_basis_enumeration_count_and_order():
    states, codes = enumerate_states(5, 0.5)
    assert states.shape == (32, 5)
    assert np.all(np.diff(codes) > 0)


def test_sz_sector_enumeration_count_binomial():
    states, codes = enumerate_states(8, 0.5, sz_total=0)
    assert len(states) == 70  # C(8, 4)
    assert np.all(np.diff(codes) > 0)
    assert np.all(states.astype(int).sum(axis=1) == 4)


def test_sz_sector_spin_one_count():
    # Coefficient of x^4 in (1 + x + x^2)^4.
    states, _codes = enumerate_states(4, 1, sz_total=0)
    assert len(states) == 19


def test_sz_total_parity_mismatch_rejected():
    with pytest.raises(ValueError, match="sz_total"):
        enumerate_states(3, 0.5, sz_total=0)  # 3 half-integers cannot sum to 0


def test_sz_total_out_of_range_rejected():
    with pytest.raises(ValueError, match="sz_total"):
        enumerate_states(4, 0.5, sz_total=3)


def test_spin_digit_data_rejects_invalid_spin():
    with pytest.raises(ValueError, match="spin"):
        spin_digit_data(0.3)


def test_state_powers_site_zero_most_significant():
    powers = state_powers(3, 2)
    assert powers.tolist() == [4, 2, 1]


def test_translation_group_order_and_permutation():
    coords, perms = translation_group((4, 3, 1), 2)
    assert len(coords) == 12
    for perm in perms:
        assert sorted(perm.tolist()) == list(range(24))


def test_translation_group_rejects_bad_shape():
    with pytest.raises(ValueError, match="supercell"):
        translation_group((0, 2, 2), 1)


def test_momentum_phases_integer_check():
    coords, _perms = translation_group((4, 1, 1), 1)
    with pytest.raises(ValueError, match="momentum"):
        momentum_phases(coords, (4, 1, 1), [0.5, 0, 0])
    phases = momentum_phases(coords, (4, 1, 1), [1, 0, 0])
    assert abs(phases[0] - 1.0) < 1e-12  # identity translation


def _chain_sector(n, sz_total, momentum):
    states, codes = enumerate_states(n, 0.5, sz_total=sz_total)
    coords, perms = translation_group((n, 1, 1), 1)
    phases = momentum_phases(coords, (n, 1, 1), momentum)
    return momentum_sector(states, codes, perms, phases), states


def test_momentum_sector_dimensions_four_site_sz0():
    # N=4, Sz=0: six states, orbits {0011,0110,1100,1001} (size 4) and
    # {0101,1010} (size 2, stabilized by T^2). k=0 keeps both; k=pi keeps
    # both (T^2 phase = 1); k=pi/2 drops the size-2 orbit.
    sector_k0, _states = _chain_sector(4, 0, [0, 0, 0])
    assert sector_k0["dimension"] == 2
    sector_kpi, _states = _chain_sector(4, 0, [2, 0, 0])
    assert sector_kpi["dimension"] == 2
    sector_kpi2, _states = _chain_sector(4, 0, [1, 0, 0])
    assert sector_kpi2["dimension"] == 1
    assert sector_kpi2["orbits_total"] == 2
    assert sector_kpi2["dimension"] == sector_kpi2["orbits_total"] - 1


def test_momentum_sector_coefficients_normalized():
    sector, states = _chain_sector(6, 0, [0, 0, 0])
    rep_of, coeff = sector["rep_of"], sector["coeff"]
    for r in range(sector["dimension"]):
        members = np.flatnonzero(rep_of == r)
        assert len(members) > 0
        assert abs(np.sum(np.abs(coeff[members]) ** 2) - 1.0) < 1e-12


def test_momentum_sector_counts_cover_sz_basis():
    # Sum over all momenta of the sector dimensions equals the Sz-basis size.
    states, codes = enumerate_states(6, 0.5, sz_total=0)
    coords, perms = translation_group((6, 1, 1), 1)
    total = 0
    for n in range(6):
        phases = momentum_phases(coords, (6, 1, 1), [n, 0, 0])
        sector = momentum_sector(states, codes, perms, phases)
        total += sector["dimension"]
    assert total == len(states)


def test_trivial_sector_identity():
    states, codes = enumerate_states(3, 0.5, sz_total=0.5)
    sector = trivial_sector(states)
    assert sector["dimension"] == len(states)
    assert np.all(sector["coeff"] == 1.0)
    assert np.all(sector["rep_of"] == np.arange(len(states)))
