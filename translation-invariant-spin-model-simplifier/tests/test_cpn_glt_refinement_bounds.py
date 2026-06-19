import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from classical.cpn_generalized_lt_solver import solve_cpn_generalized_lt_ground_state


def _single_site_model():
    return {
        "classical_manifold": "CP^(N-1)",
        "local_dimension": 2,
        "magnetic_site_count": 1,
        "bond_tensors": [],
    }


def _weighted_candidate():
    return {
        "energy": -1.0,
        "q_vector": [0.0, 0.0, 0.0],
        "mode_kind": "uniform-trust-region",
        "scaled_vector": np.zeros((3,), dtype=float),
        "kernel": np.zeros((3, 3), dtype=float),
        "constant_term": 0.0,
        "radius_sq": 1.0,
        "uniform_lower_bound": -1.5,
        "q_zero_affine_lower_bound": -1.5,
        "best_q_mesh_lower_bound": -1.0,
        "uniform_optimizer": {"mode": "uniform-trust-region"},
        "q_zero_affine_optimizer": {"mode": "uniform-trust-region"},
        "p_weights": [1.0],
        "alpha_weights": [1.0],
        "lowest_shell_basis": np.zeros((3, 0), dtype=float),
        "lowest_shell_dimension": 0,
        "lowest_shell_sectors": [],
        "lowest_shell_sector_count": 0,
        "weight_search": {"best_p_weights": [1.0]},
    }


def _continuous_eigenvalue_refinement():
    return {
        "status": "refined",
        "accepted": True,
        "converged": True,
        "seed_q_vector": [0.0, 0.0, 0.0],
        "refined_q_vector": [0.0, 0.0, 0.0],
        "seed_lower_bound": -1.0,
        "refined_lower_bound": -1.0,
    }


def _continuous_refinement():
    return {
        "status": "refined",
        "accepted": True,
        "converged": True,
        "seed_q_vector": [0.0, 0.0, 0.0],
        "refined_q_vector": [0.0, 0.0, 0.0],
        "seed_p_weights": [1.0],
        "refined_p_weights": [1.0],
        "energy_upper_bound": -0.75,
    }


def test_generalized_lt_exposes_relaxed_seed_and_promotion_path():
    with patch(
        "classical.cpn_generalized_lt_solver._search_weights",
        return_value=_weighted_candidate(),
    ), patch(
        "classical.cpn_generalized_lt_solver._continuous_refine_relaxed_eigenvalue_candidate",
        side_effect=lambda model, blocks_payload, weighted, **kwargs: dict(
            weighted,
            continuous_eigenvalue_refinement=_continuous_eigenvalue_refinement(),
            weight_search=dict(
                weighted.get("weight_search", {}),
                continuous_eigenvalue_refinement=_continuous_eigenvalue_refinement(),
            ),
        ),
    ), patch(
        "classical.cpn_generalized_lt_solver._continuous_refine_weighted_candidate",
        side_effect=lambda model, blocks_payload, weighted: dict(
            weighted,
            continuous_refinement=_continuous_refinement(),
            weight_search=dict(
                weighted.get("weight_search", {}),
                continuous_refinement=_continuous_refinement(),
            ),
        ),
    ), patch(
        "classical.cpn_generalized_lt_solver.generate_q_mesh",
        return_value=[[0.0, 0.0, 0.0]],
    ), patch(
        "classical.cpn_generalized_lt_solver.finalize_cpn_glt_result",
        side_effect=lambda *args, **kwargs: args[1],
    ):
        result = solve_cpn_generalized_lt_ground_state(_single_site_model(), mesh_shape=(16, 1, 1))

    relaxed = result["relaxed_lt"]
    seed_candidate = relaxed["seed_candidate"]
    promotion_path = result["promotion_path"]

    assert result["solver_role"] == "diagnostic-only"
    assert result["energy"] == pytest.approx(-1.0)
    assert relaxed["lower_bound"] == pytest.approx(-1.0)
    assert relaxed["best_q_mesh_lower_bound"] == pytest.approx(-1.0)
    assert seed_candidate["kind"] == "relaxed-lt-seed"
    assert seed_candidate["source"] == "cpn-generalized-lt"
    assert seed_candidate["lower_bound"] == pytest.approx(relaxed["lower_bound"])
    assert "energy_upper_bound" not in seed_candidate
    assert relaxed["continuous_eigenvalue_refinement"]["accepted"] is True
    assert relaxed["continuous_eigenvalue_refinement"]["converged"] is True
    assert result["continuous_refinement"]["energy_upper_bound"] == pytest.approx(-0.75)
    assert promotion_path["accepted"] is True
    assert promotion_path["converged"] is True
    assert promotion_path["seed_candidate"]["kind"] == "relaxed-lt-seed"
    assert promotion_path["continuous_refinement"]["energy_upper_bound"] == pytest.approx(-0.75)


def test_generalized_lt_keeps_lower_bound_separate_from_feasible_upper_bound():
    with patch(
        "classical.cpn_generalized_lt_solver._search_weights",
        return_value=_weighted_candidate(),
    ), patch(
        "classical.cpn_generalized_lt_solver._continuous_refine_relaxed_eigenvalue_candidate",
        side_effect=lambda model, blocks_payload, weighted, **kwargs: dict(
            weighted,
            continuous_eigenvalue_refinement=_continuous_eigenvalue_refinement(),
            weight_search=dict(
                weighted.get("weight_search", {}),
                continuous_eigenvalue_refinement=_continuous_eigenvalue_refinement(),
            ),
        ),
    ), patch(
        "classical.cpn_generalized_lt_solver._continuous_refine_weighted_candidate",
        side_effect=lambda model, blocks_payload, weighted: dict(
            weighted,
            continuous_refinement=_continuous_refinement(),
            weight_search=dict(
                weighted.get("weight_search", {}),
                continuous_refinement=_continuous_refinement(),
            ),
        ),
    ), patch(
        "classical.cpn_generalized_lt_solver.generate_q_mesh",
        return_value=[[0.5, 0.0, 0.0]],
    ), patch(
        "classical.cpn_generalized_lt_solver.finalize_cpn_glt_result",
        side_effect=lambda *args, **kwargs: args[1],
    ):
        result = solve_cpn_generalized_lt_ground_state(_single_site_model(), mesh_shape=(16, 1, 1))

    assert result["relaxed_lt"]["lower_bound"] == pytest.approx(-1.0)
    assert result["relaxed_lt"]["seed_candidate"]["lower_bound"] == pytest.approx(-1.0)
    assert result["promotion_path"]["continuous_refinement"]["energy_upper_bound"] == pytest.approx(-0.75)
    assert result["energy"] == pytest.approx(-1.0)
    assert result.get("promotion_reason") is None
    assert "energy_upper_bound" not in result["relaxed_lt"]["seed_candidate"]
