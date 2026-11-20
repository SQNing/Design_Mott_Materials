"""Sector ED solver correctness: exact limits, sector decomposition, guards."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import chain_model, heisenberg_dense_reference, honeycomb_model, kitaev_chain_model
from three_dimensional.workflow import run_three_dimensional_workflow


def run_ed(model, **request):
    result = _run_raw(model, **request)
    assert result["status"] == "ok", result.get("blocker")
    return result["calculation"]


def _run_raw(model, **request):
    request.setdefault("task", "quantum_low_energy")
    request.setdefault("spin", 0.5)
    request.setdefault("seed", 7)
    return run_three_dimensional_workflow(model, request)


def test_dimer_singlet_energy():
    # Two sites coupled by 2 x J/2 bonds on a length-2 periodic cell.
    calc = run_ed(chain_model(0.5), supercell_shape=[2, 1, 1], sz_total=0, eigenvalues=2)
    assert calc["eigenvalues"][0] == pytest.approx(-0.75, abs=1e-12)
    assert calc["sector"]["sector_dimension"] == 2


def test_dimer_spin_gap_via_compare_sectors():
    calc = run_ed(chain_model(0.5), supercell_shape=[2, 1, 1], sz_total=0,
                  eigenvalues=1, compare_sectors=[{"sz_total": 1}])
    assert calc["compare_sectors"][0]["eigenvalues"][0] == pytest.approx(0.25, abs=1e-12)
    assert calc["compare_sectors"][0]["sector"]["sz_total"] == 1


def test_fully_polarized_sector_is_exact():
    calc = run_ed(chain_model(1.0), supercell_shape=[6, 1, 1], sz_total=3, eigenvalues=1)
    assert calc["sector"]["sector_dimension"] == 1
    assert calc["eigenvalues"][0] == pytest.approx(6 * 0.25, abs=1e-12)


def test_ferromagnet_cubic_energy_per_site():
    calc = run_ed(_cubic_fm(), supercell_shape=[2, 2, 2], eigenvalues=2)
    assert calc["energy_per_site"] == pytest.approx(-0.75, abs=1e-10)


def _cubic_fm():
    from three_dimensional.examples import cubic_input
    return cubic_input(-1.0, {})["model"]


def test_legacy_sixteen_site_ferromagnet():
    calc = run_ed(_cubic_fm(), supercell_shape=[2, 2, 4], eigenvalues=2)
    np.testing.assert_allclose(calc["eigenvalues"], [-12, -12], atol=1e-8)
    assert calc["hilbert_dimension"] == 65536
    assert calc["dense_hamiltonian_allocated"] is False


def test_magnon_dispersion_momentum_convention():
    # One down spin on a length-4 ferromagnetic chain: E(k) = NJ/4 + J(cos k - 1).
    for n in range(4):
        calc = run_ed(chain_model(1.0), supercell_shape=[4, 1, 1], sz_total=1,
                      momentum=[n, 0, 0], eigenvalues=1)
        expected = 4 * 0.25 + (np.cos(2 * np.pi * n / 4) - 1.0)
        assert calc["eigenvalues"][0] == pytest.approx(expected, abs=1e-12)


def test_full_spectrum_decomposes_into_momentum_sectors():
    shape = [4, 1, 1]
    full = run_ed(chain_model(), supercell_shape=shape, sz_total=0, eigenvalues=6)
    union = []
    for n in range(4):
        sector = run_ed(chain_model(), supercell_shape=shape, sz_total=0,
                        momentum=[n, 0, 0], eigenvalues=6)
        union.extend(sector["eigenvalues"])
    np.testing.assert_allclose(np.sort(union), np.sort(full["eigenvalues"]), atol=1e-10)


def test_sz_sectors_decompose_full_basis():
    shape = [4, 1, 1]
    full = run_ed(chain_model(), supercell_shape=shape, eigenvalues=16)
    union = []
    for sz in (-2, -1, 0, 1, 2):
        sector = run_ed(chain_model(), supercell_shape=shape, sz_total=float(sz),
                        eigenvalues=16)
        union.extend(sector["eigenvalues"])
    np.testing.assert_allclose(np.sort(union), np.sort(full["eigenvalues"]), atol=1e-10)


def test_sector_hamiltonian_matches_dense_reference():
    dense = heisenberg_dense_reference(chain_model(), (4, 1, 1), 0.5)
    expected = np.linalg.eigvalsh(dense)
    full = run_ed(chain_model(), supercell_shape=[4, 1, 1], eigenvalues=16)
    np.testing.assert_allclose(np.sort(full["eigenvalues"]), expected, atol=1e-10)


def test_sz_sector_rejected_without_u1_conservation():
    result = _run_raw(kitaev_chain_model(), supercell_shape=[4, 1, 1], sz_total=0,
                      eigenvalues=2)
    assert result["status"] == "invalid_request"
    assert "conserve total Sz" in result["blocker"]


def test_momentum_sector_allowed_without_u1():
    # Kitaev chain: translation still commutes; momentum sectors must
    # reproduce the full-basis spectrum.
    shape = [4, 1, 1]
    full = run_ed(kitaev_chain_model(), supercell_shape=shape, eigenvalues=16)
    union = []
    for n in range(4):
        sector = run_ed(kitaev_chain_model(), supercell_shape=shape,
                        momentum=[n, 0, 0], eigenvalues=16)
        union.extend(sector["eigenvalues"])
    np.testing.assert_allclose(np.sort(union), np.sort(full["eigenvalues"]), atol=1e-10)


def test_memory_guard_rejects_tiny_budget():
    result = _run_raw(chain_model(), supercell_shape=[16, 1, 1], sz_total=0,
                      eigenvalues=2, max_memory_mb=1e-6)
    assert result["status"] == "invalid_request"
    assert "max_memory_mb" in result["blocker"]


def test_eigenvalue_count_and_residuals():
    calc = run_ed(chain_model(), supercell_shape=[8, 1, 1], sz_total=0,
                  momentum=[0, 0, 0], eigenvalues=5)
    assert len(calc["eigenvalues"]) == 5
    assert max(calc["residual_norms"]) < 1e-8
    assert calc["eigenvector_orthogonality_error"] < 1e-8
    assert calc["converged"] is True


def test_sector_block_fields():
    calc = run_ed(chain_model(), supercell_shape=[6, 1, 1], sz_total=0,
                  momentum=[0, 0, 0], eigenvalues=2)
    sector = calc["sector"]
    assert sector["basis_kind"] == "sz+momentum"
    assert sector["sz_total"] == 0
    assert sector["momentum"] == [0, 0, 0]
    assert sector["hilbert_dimension"] == 64
    assert sector["sector_dimension"] < sector["sz_basis_dimension"]


def test_spin_one_chain_sector():
    calc = run_ed(chain_model(1.0), supercell_shape=[3, 1, 1], spin=1,
                  sz_total=0, eigenvalues=3)
    dense = heisenberg_dense_reference(chain_model(1.0), (3, 1, 1), 1)
    expected = np.linalg.eigvalsh(dense)
    # The Sz=0 sector contains the ground state (singlet).
    assert calc["eigenvalues"][0] == pytest.approx(expected[0], abs=1e-10)


def test_honeycomb_small_cluster_against_dense():
    dense = heisenberg_dense_reference(honeycomb_model(), (1, 2, 1), 0.5)
    expected = np.linalg.eigvalsh(dense)[:4]
    calc = run_ed(honeycomb_model(), supercell_shape=[1, 2, 1], eigenvalues=4)
    np.testing.assert_allclose(calc["eigenvalues"], expected, atol=1e-10)
    assert calc["site_count"] == 4


def test_anisotropic_dm_bond_complex_sector():
    matrix = [[1.0, 0.3, 0], [-0.3, 1.0, 0], [0, 0, 0.7]]  # DM z: conserves Sz
    from helpers import spin_bond_model
    model = spin_bond_model(np.eye(3), [[0, 0, 0]], [(0, 0, (1, 0, 0), matrix)])
    full = run_ed(model, supercell_shape=[3, 1, 1], eigenvalues=8)
    union = []
    for sz in (-1.5, -0.5, 0.5, 1.5):
        sector = run_ed(model, supercell_shape=[3, 1, 1], sz_total=sz, eigenvalues=8)
        union.extend(sector["eigenvalues"])
    np.testing.assert_allclose(np.sort(union), np.sort(full["eigenvalues"]), atol=1e-10)


def test_j1j2_sector_decomposition_against_dense():
    # Frustrated next-neighbour chain: momentum-resolved Sz=0 union must
    # reproduce the dense Sz=0 block exactly.
    import itertools
    model = chain_model(1.0, second_neighbor=0.35)
    dense = heisenberg_dense_reference(model, (8, 1, 1), 0.5)
    selected = [i for i, digits in enumerate(itertools.product([0, 1], repeat=8))
                if sum(digits) == 4]
    expected = np.linalg.eigvalsh(dense[np.ix_(selected, selected)])
    union = []
    for n in range(8):
        sector = run_ed(model, supercell_shape=[8, 1, 1], sz_total=0,
                        momentum=[n, 0, 0], eigenvalues=100000)
        union.extend(sector["eigenvalues"])
    np.testing.assert_allclose(np.sort(union), expected, atol=1e-9)


def test_compare_sectors_flag_propagates_convergence():
    calc = run_ed(chain_model(), supercell_shape=[4, 1, 1], sz_total=0, eigenvalues=2,
                  compare_sectors=[{"sz_total": 1}, {"sz_total": 1, "momentum": [2, 0, 0]}])
    assert calc["converged"] is True
    assert all(entry["converged"] for entry in calc["compare_sectors"])
    assert calc["compare_sectors"][1]["sector"]["momentum"] == [2, 0, 0]
