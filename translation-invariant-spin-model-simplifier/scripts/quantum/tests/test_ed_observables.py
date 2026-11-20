"""ED observables: correlations, structure factor, entanglement, level statistics."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import chain_model, honeycomb_model
from research.contracts import validate_observables_block
from three_dimensional.workflow import run_three_dimensional_workflow


def run_ed(model, **request):
    request.setdefault("task", "quantum_low_energy")
    request.setdefault("spin", 0.5)
    request.setdefault("seed", 7)
    result = run_three_dimensional_workflow(model, request)
    assert result["status"] == "ok", result.get("blocker")
    return result["calculation"]


def test_dimer_correlations_exact():
    calc = run_ed(chain_model(0.5), supercell_shape=[2, 1, 1], sz_total=0,
                  eigenvalues=1, observables=["correlations"])
    matrix = np.asarray(calc["observables"]["static"]["correlations"]["matrix"])
    np.testing.assert_allclose(matrix, [[0.75, -0.75], [-0.75, 0.75]], atol=1e-10)


def test_correlation_diagonal_is_s_s_plus_one():
    calc = run_ed(chain_model(1.0), supercell_shape=[6, 1, 1], sz_total=0,
                  momentum=[0, 0, 0], eigenvalues=1, observables=["correlations"])
    matrix = np.asarray(calc["observables"]["static"]["correlations"]["matrix"])
    np.testing.assert_allclose(np.diag(matrix), 0.75, atol=1e-12)
    np.testing.assert_allclose(matrix, matrix.T, atol=1e-12)


def test_dimer_entanglement_one_bit():
    calc = run_ed(chain_model(0.5), supercell_shape=[2, 1, 1], sz_total=0,
                  eigenvalues=1, observables=["entanglement"])
    entropy = calc["observables"]["static"]["entanglement"]
    assert entropy["entropy_base"] == 2
    assert entropy["von_neumann_entropy"] == pytest.approx(1.0, abs=1e-12)
    assert entropy["schmidt_values_above_1e-8"] == 2


def test_dimer_structure_factor_antiferromagnetic():
    calc = run_ed(chain_model(0.5), supercell_shape=[2, 1, 1], sz_total=0,
                  eigenvalues=1, observables=["structure_factor"])
    factor = calc["observables"]["static"]["structure_factor"]
    points = {tuple(p["q"]): p["s_q"] for p in factor["points"]}
    assert points[(0.0, 0.0, 0.0)] == pytest.approx(0.0, abs=1e-12)
    assert points[(0.5, 0.0, 0.0)] == pytest.approx(1.5, abs=1e-10)
    assert factor["ordering_q"] == [0.5, 0.0, 0.0]
    assert factor["m2_ordering"] == pytest.approx(0.75, abs=1e-10)


def test_ferromagnet_structure_factor_at_q_zero():
    calc = run_ed(chain_model(-1.0), supercell_shape=[4, 1, 1], sz_total=2,
                  eigenvalues=1, observables=["structure_factor"])
    factor = calc["observables"]["static"]["structure_factor"]
    points = {tuple(p["q"]): p["s_q"] for p in factor["points"]}
    # Fully polarized state: S(0) = S(S+1) + (N-1) S^2 = <S_tot^2>/N,
    # and S(q != 0) = S(S+1) - S^2 (only the self-correlation survives).
    assert points[(0.0, 0.0, 0.0)] == pytest.approx(1.5, abs=1e-12)
    assert points[(0.5, 0.0, 0.0)] == pytest.approx(0.5, abs=1e-12)


def test_default_q_grid_covers_cluster_momenta():
    calc = run_ed(chain_model(1.0), supercell_shape=[6, 1, 1], sz_total=0,
                  eigenvalues=1, observables=["structure_factor"])
    points = calc["observables"]["static"]["structure_factor"]["points"]
    assert len(points) == 6


def test_gaps_block_and_sector_gaps():
    calc = run_ed(chain_model(0.5), supercell_shape=[2, 1, 1], sz_total=0,
                  eigenvalues=2, compare_sectors=[{"sz_total": 1}],
                  observables=["gaps"])
    gaps = calc["observables"]["static"]["gaps"]
    assert gaps["excitation_gaps"][0] == pytest.approx(1.0, abs=1e-10)
    assert gaps["sector_gaps"][0]["value"] == pytest.approx(1.0, abs=1e-10)
    assert gaps["sector_gaps"][0]["compare_sector"]["sz_total"] == 1


def test_level_statistics_too_few_levels():
    calc = run_ed(chain_model(0.5), supercell_shape=[2, 1, 1], sz_total=0,
                  eigenvalues=2, observables=["level_statistics"])
    stats = calc["observables"]["static"]["level_statistics"]
    assert stats["mean_r"] is None


def test_level_statistics_chain_range():
    calc = run_ed(chain_model(1.0), supercell_shape=[10, 1, 1], sz_total=0,
                  momentum=[0, 0, 0], eigenvalues=15, observables=["level_statistics"])
    stats = calc["observables"]["static"]["level_statistics"]
    assert stats["count"] >= 8
    assert 0.0 < stats["mean_r"] < 1.0
    assert stats["reference"] == {"poisson": 0.3863, "goe": 0.5307}


def test_observables_block_contract_validation():
    calc = run_ed(chain_model(0.5), supercell_shape=[2, 1, 1], sz_total=0,
                  eigenvalues=1, observables=["gaps", "correlations"])
    block = validate_observables_block(calc["observables"], backend="ed-sparse-sector")
    assert block["schema_version"] == "observables/v1"
    assert block["dynamic"]["status"] == "deferred"
    with pytest.raises(ValueError, match="backend mismatch"):
        validate_observables_block(calc["observables"], backend="other")


def test_unknown_observable_rejected():
    result = run_three_dimensional_workflow(chain_model(), {
        "task": "quantum_low_energy", "supercell_shape": [2, 1, 1], "spin": 0.5,
        "eigenvalues": 1, "observables": ["pair_distribution_function"]})
    assert result["status"] == "invalid_request"
    assert "unknown ED observables" in result["blocker"]


def test_entanglement_cut_validation():
    result = run_three_dimensional_workflow(chain_model(), {
        "task": "quantum_low_energy", "supercell_shape": [4, 1, 1], "spin": 0.5,
        "sz_total": 0, "eigenvalues": 1,
        "observables": ["entanglement"], "entanglement_cut": [0, 1, 2, 3]})
    assert result["status"] == "invalid_request"
    assert "proper subset" in result["blocker"]


def test_entanglement_explicit_cut_matches_default_half():
    full = run_ed(chain_model(1.0), supercell_shape=[8, 1, 1], sz_total=0,
                  momentum=[0, 0, 0], eigenvalues=1, observables=["entanglement"])
    explicit = run_ed(chain_model(1.0), supercell_shape=[8, 1, 1], sz_total=0,
                      momentum=[0, 0, 0], eigenvalues=1, observables=["entanglement"],
                      entanglement_cut=[0, 1, 2, 3])
    assert (explicit["observables"]["static"]["entanglement"]["von_neumann_entropy"] ==
            pytest.approx(
                full["observables"]["static"]["entanglement"]["von_neumann_entropy"],
                abs=1e-10))


def test_honeycomb_ground_state_correlations_sum_rule():
    # sum_ij <S_i.S_j> = <S_total^2> >= 0 and exact singlet gives 0;
    # here just check the energy identity E = sum_bonds J <S_i.S_j> consistent
    # with the correlation matrix on a 2x1x1 cell (8 bonds... count from bonds).
    calc = run_ed(honeycomb_model(), supercell_shape=[1, 1, 1], eigenvalues=1,
                  observables=["correlations"])
    matrix = np.asarray(calc["observables"]["static"]["correlations"]["matrix"])
    # Single cell: two sites, three bonds between them (including self-images).
    assert matrix[0, 1] == pytest.approx(calc["eigenvalues"][0] / 3.0, abs=1e-10)


def test_local_moment_zero_in_sz_zero_sector():
    calc = run_ed(chain_model(1.0), supercell_shape=[6, 1, 1], sz_total=0,
                  momentum=[0, 0, 0], eigenvalues=1, observables=["correlations"])
    moments = calc["observables"]["static"]["correlations"]["local_moment"]["values"]
    np.testing.assert_allclose(moments, 0.0, atol=1e-12)
