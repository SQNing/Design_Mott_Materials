import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical.cpn_generalized_lt_solver import solve_cpn_generalized_lt_ground_state


def _complex(value):
    return {"real": float(value.real), "imag": float(value.imag)}


def _serialized_tensor(local_dimension, entries):
    tensor = []
    for a in range(local_dimension):
        block_a = []
        for b in range(local_dimension):
            block_b = []
            for c in range(local_dimension):
                row = []
                for d in range(local_dimension):
                    row.append(_complex(entries.get((a, b, c, d), 0.0 + 0.0j)))
                block_b.append(row)
            block_a.append(block_b)
        tensor.append(block_a)
    return tensor


def _minimal_cpn_model():
    local_dimension = 2
    return {
        "model_version": 2,
        "model_type": "sun_gswt_classical",
        "classical_manifold": "CP^(N-1)",
        "basis_semantics": {"local_space": "pseudospin_orbital"},
        "basis_order": "orbital_major_spin_minor",
        "pair_basis_order": "site_i_major_site_j_minor",
        "retained_local_space": {
            "tensor_factor_order": "orbital_major_spin_minor",
            "factorization": {
                "kind": "orbital_times_spin",
                "spin_dimension": 2,
                "orbital_dimension": 1,
            },
        },
        "pair_operator_convention": {
            "pair_basis_order": "site_i_major_site_j_minor",
            "tensor_view": {
                "index_order": ["left_bra", "right_bra", "left_ket", "right_ket"],
            },
        },
        "operator_dictionary": {
            "local_basis_kind": "orbital_times_spin",
            "tensor_factor_order": "orbital_major_spin_minor",
            "local_operator_basis": {
                "matrix_construction": "kron(orbital, spin)",
            },
        },
        "local_dimension": local_dimension,
        "orbital_count": 1,
        "local_basis_labels": ["up", "down"],
        "positions": [[0.0, 0.0, 0.0]],
        "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "bond_count": 1,
        "bond_tensors": [
            {
                "R": [1, 0, 0],
                "distance": 1.0,
                "matrix_shape": [4, 4],
                "tensor_shape": [2, 2, 2, 2],
                "tensor": _serialized_tensor(
                    local_dimension,
                    {
                        (0, 0, 0, 0): -1.0,
                    },
                ),
            }
        ],
    }


def _two_sublattice_exact_uniform_model():
    local_dimension = 2
    return {
        "model_version": 2,
        "model_type": "sun_gswt_classical",
        "classical_manifold": "CP^(N-1)",
        "basis_semantics": {"local_space": "pseudospin_orbital"},
        "basis_order": "orbital_major_spin_minor",
        "pair_basis_order": "site_i_major_site_j_minor",
        "retained_local_space": {
            "tensor_factor_order": "orbital_major_spin_minor",
            "factorization": {
                "kind": "orbital_times_spin",
                "spin_dimension": 2,
                "orbital_dimension": 1,
            },
        },
        "pair_operator_convention": {
            "pair_basis_order": "site_i_major_site_j_minor",
            "tensor_view": {
                "index_order": ["left_bra", "right_bra", "left_ket", "right_ket"],
            },
        },
        "operator_dictionary": {
            "local_basis_kind": "orbital_times_spin",
            "tensor_factor_order": "orbital_major_spin_minor",
            "local_operator_basis": {
                "matrix_construction": "kron(orbital, spin)",
            },
        },
        "local_dimension": local_dimension,
        "orbital_count": 1,
        "local_basis_labels": ["up", "down"],
        "positions": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
        "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "magnetic_site_count": 2,
        "magnetic_sites": [
            {"index": 0, "label": "A", "position": [0.0, 0.0, 0.0]},
            {"index": 1, "label": "B", "position": [0.5, 0.0, 0.0]},
        ],
        "magnetic_site_metadata": {
            "site_pair_encoding": "explicit-source-target",
        },
        "bond_count": 1,
        "bond_tensors": [
            {
                "R": [0, 0, 0],
                "source": 0,
                "target": 1,
                "distance": 0.0,
                "matrix_shape": [4, 4],
                "tensor_shape": [2, 2, 2, 2],
                "tensor": _serialized_tensor(
                    local_dimension,
                    {
                        (0, 0, 0, 0): -1.0,
                    },
                ),
            }
        ],
    }


def _single_sublattice_exact_commensurate_q_half_model():
    local_dimension = 2
    return {
        "model_version": 2,
        "model_type": "sun_gswt_classical",
        "classical_manifold": "CP^(N-1)",
        "basis_semantics": {"local_space": "pseudospin_orbital"},
        "basis_order": "orbital_major_spin_minor",
        "pair_basis_order": "site_i_major_site_j_minor",
        "retained_local_space": {
            "tensor_factor_order": "orbital_major_spin_minor",
            "factorization": {
                "kind": "orbital_times_spin",
                "spin_dimension": 2,
                "orbital_dimension": 1,
            },
        },
        "pair_operator_convention": {
            "pair_basis_order": "site_i_major_site_j_minor",
            "tensor_view": {
                "index_order": ["left_bra", "right_bra", "left_ket", "right_ket"],
            },
        },
        "operator_dictionary": {
            "local_basis_kind": "orbital_times_spin",
            "tensor_factor_order": "orbital_major_spin_minor",
            "local_operator_basis": {
                "matrix_construction": "kron(orbital, spin)",
            },
        },
        "local_dimension": local_dimension,
        "orbital_count": 1,
        "local_basis_labels": ["up", "down"],
        "positions": [[0.0, 0.0, 0.0]],
        "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "bond_count": 1,
        "bond_tensors": [
            {
                "R": [1, 0, 0],
                "distance": 1.0,
                "matrix_shape": [4, 4],
                "tensor_shape": [2, 2, 2, 2],
                "tensor": _serialized_tensor(
                    local_dimension,
                    {
                        (0, 0, 0, 0): 0.5,
                        (0, 0, 1, 1): -0.5,
                        (1, 1, 0, 0): -0.5,
                        (1, 1, 1, 1): 0.5,
                    },
                ),
            }
        ],
    }


def _single_sublattice_x_line_degenerate_model():
    local_dimension = 2
    return {
        "model_version": 2,
        "model_type": "sun_gswt_classical",
        "classical_manifold": "CP^(N-1)",
        "basis_semantics": {"local_space": "pseudospin_orbital"},
        "basis_order": "orbital_major_spin_minor",
        "pair_basis_order": "site_i_major_site_j_minor",
        "retained_local_space": {
            "tensor_factor_order": "orbital_major_spin_minor",
            "factorization": {
                "kind": "orbital_times_spin",
                "spin_dimension": 2,
                "orbital_dimension": 1,
            },
        },
        "pair_operator_convention": {
            "pair_basis_order": "site_i_major_site_j_minor",
            "tensor_view": {
                "index_order": ["left_bra", "right_bra", "left_ket", "right_ket"],
            },
        },
        "operator_dictionary": {
            "local_basis_kind": "orbital_times_spin",
            "tensor_factor_order": "orbital_major_spin_minor",
            "local_operator_basis": {
                "matrix_construction": "kron(orbital, spin)",
            },
        },
        "local_dimension": local_dimension,
        "orbital_count": 1,
        "local_basis_labels": ["up", "down"],
        "positions": [[0.0, 0.0, 0.0]],
        "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "bond_count": 1,
        "bond_tensors": [
            {
                "R": [1, 0, 0],
                "distance": 1.0,
                "matrix_shape": [4, 4],
                "tensor_shape": [2, 2, 2, 2],
                "tensor": _serialized_tensor(
                    local_dimension,
                    {
                        (0, 0, 0, 0): 0.5,
                        (0, 0, 1, 1): -0.5,
                        (1, 1, 0, 0): -0.5,
                        (1, 1, 1, 1): 0.5,
                    },
                ),
            }
        ],
    }


def _two_sublattice_exact_commensurate_q_half_model():
    local_dimension = 2
    return {
        "model_version": 2,
        "model_type": "sun_gswt_classical",
        "classical_manifold": "CP^(N-1)",
        "basis_semantics": {"local_space": "pseudospin_orbital"},
        "basis_order": "orbital_major_spin_minor",
        "pair_basis_order": "site_i_major_site_j_minor",
        "retained_local_space": {
            "tensor_factor_order": "orbital_major_spin_minor",
            "factorization": {
                "kind": "orbital_times_spin",
                "spin_dimension": 2,
                "orbital_dimension": 1,
            },
        },
        "pair_operator_convention": {
            "pair_basis_order": "site_i_major_site_j_minor",
            "tensor_view": {
                "index_order": ["left_bra", "right_bra", "left_ket", "right_ket"],
            },
        },
        "operator_dictionary": {
            "local_basis_kind": "orbital_times_spin",
            "tensor_factor_order": "orbital_major_spin_minor",
            "local_operator_basis": {
                "matrix_construction": "kron(orbital, spin)",
            },
        },
        "local_dimension": local_dimension,
        "orbital_count": 1,
        "local_basis_labels": ["up", "down"],
        "positions": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
        "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "magnetic_site_count": 2,
        "magnetic_sites": [
            {"index": 0, "label": "A", "position": [0.0, 0.0, 0.0]},
            {"index": 1, "label": "B", "position": [0.5, 0.0, 0.0]},
        ],
        "magnetic_site_metadata": {
            "site_pair_encoding": "explicit-source-target",
        },
        "bond_count": 2,
        "bond_tensors": [
            {
                "R": [1, 0, 0],
                "source": 0,
                "target": 0,
                "distance": 1.0,
                "matrix_shape": [4, 4],
                "tensor_shape": [2, 2, 2, 2],
                "tensor": _serialized_tensor(
                    local_dimension,
                    {
                        (0, 0, 0, 0): 0.5,
                        (0, 0, 1, 1): -0.5,
                        (1, 1, 0, 0): -0.5,
                        (1, 1, 1, 1): 0.5,
                    },
                ),
            },
            {
                "R": [1, 0, 0],
                "source": 1,
                "target": 1,
                "distance": 1.0,
                "matrix_shape": [4, 4],
                "tensor_shape": [2, 2, 2, 2],
                "tensor": _serialized_tensor(
                    local_dimension,
                    {
                        (0, 0, 0, 0): 0.5,
                        (0, 0, 1, 1): -0.5,
                        (1, 1, 0, 0): -0.5,
                        (1, 1, 1, 1): 0.5,
                    },
                ),
            },
        ],
    }


class CpnGeneralizedLtSolverTests(unittest.TestCase):
    def test_solver_recovers_uniform_rank_one_projector_for_simple_diagonal_model(self):
        result = solve_cpn_generalized_lt_ground_state(
            _minimal_cpn_model(),
            requested_method="cpn-generalized-lt",
            mesh_shape=(9, 1, 1),
            projector_tolerance=1.0e-8,
        )

        self.assertEqual(result["method"], "cpn-generalized-lt")
        self.assertEqual(result["solver_role"], "final")
        self.assertEqual(result["promotion_reason"], "exact_projector_solution")
        self.assertIn("relaxed_lt", result)
        self.assertAlmostEqual(result["q_vector"][0], 0.0, places=12)
        self.assertAlmostEqual(result["relaxed_lt"]["q_seed"][0], 0.0, places=12)
        self.assertTrue(result["projector_exactness"]["is_exact_projector_solution"])
        self.assertIn("classical_state", result)
        self.assertIn("seed_candidate", result)
        self.assertEqual(result["seed_candidate"]["projector_diagnostics"]["ordering_kind"], "uniform")
        self.assertLess(result["seed_candidate"]["stationarity"]["max_residual_norm"], 1.0e-8)
        state = result["classical_state"]
        self.assertEqual(state["supercell_shape"], [1, 1, 1])
        vector = state["local_rays"][0]["vector"]
        self.assertAlmostEqual(vector[0]["real"], 1.0, places=6)
        self.assertAlmostEqual(vector[1]["real"], 0.0, places=6)

    def test_solver_supports_multisublattice_weighted_glt_and_reconstructs_uniform_seed_candidate(self):
        result = solve_cpn_generalized_lt_ground_state(
            _two_sublattice_exact_uniform_model(),
            requested_method="cpn-generalized-lt",
            mesh_shape=(5, 1, 1),
            projector_tolerance=1.0e-8,
        )

        self.assertEqual(result["method"], "cpn-generalized-lt")
        self.assertEqual(result["solver_role"], "final")
        self.assertEqual(result["promotion_reason"], "exact_projector_solution")
        self.assertEqual(result["magnetic_site_count"], 2)
        self.assertEqual(result["relaxed_lt"]["magnetic_site_count"], 2)
        self.assertEqual(result["relaxed_lt"]["weight_search"]["search_strategy"], "coordinate")
        self.assertGreaterEqual(result["relaxed_lt"]["weight_search"]["evaluated_candidates"], 1)
        self.assertEqual(len(result["relaxed_lt"]["weight_search"]["best_p_weights"]), 2)
        self.assertEqual(len(result["relaxed_lt"]["weight_search"]["best_alpha_weights"]), 2)
        self.assertAlmostEqual(result["q_vector"][0], 0.0, places=12)
        self.assertTrue(result["projector_exactness"]["is_exact_projector_solution"])
        self.assertIn("seed_candidate", result)
        self.assertEqual(result["seed_candidate"]["kind"], "uniform-exact-projector-seed-multisublattice")
        self.assertEqual(len(result["seed_candidate"]["sublattice_rays"]), 2)
        self.assertIn("classical_state", result)
        self.assertEqual(len(result["classical_state"]["local_rays"]), 2)
        first = result["seed_candidate"]["sublattice_rays"][0]["vector"]
        second = result["seed_candidate"]["sublattice_rays"][1]["vector"]
        self.assertAlmostEqual(first[0]["real"], 1.0, places=6)
        self.assertAlmostEqual(second[0]["real"], 1.0, places=6)

    def test_solver_reconstructs_exact_commensurate_nonzero_q_seed_candidate(self):
        result = solve_cpn_generalized_lt_ground_state(
            _single_sublattice_exact_commensurate_q_half_model(),
            requested_method="cpn-generalized-lt",
            mesh_shape=(5, 1, 1),
            projector_tolerance=1.0e-8,
        )

        self.assertEqual(result["method"], "cpn-generalized-lt")
        self.assertEqual(result["solver_role"], "final")
        self.assertEqual(result["promotion_reason"], "exact_commensurate_lift")
        self.assertAlmostEqual(result["q_vector"][0], 0.5, places=12)
        self.assertIn("reconstruction", result)
        self.assertEqual(result["reconstruction"]["status"], "exact")
        self.assertEqual(result["reconstruction"]["ordering"]["kind"], "commensurate-single-q")
        self.assertEqual(result["reconstruction"]["ordering"]["supercell_shape"], [2, 1, 1])
        self.assertIn("seed_candidate", result)
        self.assertEqual(result["seed_candidate"]["kind"], "commensurate-exact-projector-seed")
        state = result["classical_state"]
        self.assertEqual(state["supercell_shape"], [2, 1, 1])
        self.assertEqual(len(state["local_rays"]), 2)
        first = state["local_rays"][0]["vector"]
        second = state["local_rays"][1]["vector"]
        self.assertAlmostEqual(first[0]["real"], 1.0, places=6)
        self.assertAlmostEqual(first[1]["real"], 0.0, places=6)
        self.assertAlmostEqual(second[0]["real"], 0.0, places=6)
        self.assertAlmostEqual(second[1]["real"], 1.0, places=6)

    def test_solver_reconstructs_exact_multisublattice_commensurate_nonzero_q_seed_candidate(self):
        result = solve_cpn_generalized_lt_ground_state(
            _two_sublattice_exact_commensurate_q_half_model(),
            requested_method="cpn-generalized-lt",
            mesh_shape=(5, 1, 1),
            projector_tolerance=1.0e-8,
        )

        self.assertEqual(result["method"], "cpn-generalized-lt")
        self.assertEqual(result["solver_role"], "final")
        self.assertEqual(result["promotion_reason"], "exact_commensurate_lift")
        self.assertEqual(result["magnetic_site_count"], 2)
        self.assertAlmostEqual(result["q_vector"][0], 0.5, places=12)
        self.assertEqual(result["relaxed_lt"]["lowest_shell_dimension"], 2)
        self.assertIn("reconstruction", result)
        self.assertEqual(result["reconstruction"]["status"], "exact")
        self.assertEqual(result["reconstruction"]["ordering"]["kind"], "commensurate-single-q")
        self.assertEqual(result["reconstruction"]["ordering"]["supercell_shape"], [2, 1, 1])
        self.assertIn("seed_candidate", result)
        self.assertEqual(result["seed_candidate"]["kind"], "commensurate-exact-projector-seed-multisublattice")
        state = result["classical_state"]
        self.assertEqual(state["supercell_shape"], [2, 1, 1])
        self.assertEqual(len(state["local_rays"]), 4)
        entries = {(tuple(item["cell"]), int(item["site"])) for item in state["local_rays"]}
        self.assertEqual(entries, {((0, 0, 0), 0), ((0, 0, 0), 1), ((1, 0, 0), 0), ((1, 0, 0), 1)})

    def test_solver_passes_degenerate_nonzero_q_sectors_to_generalized_reconstruction(self):
        observed = {}

        def fake_reconstruct(**kwargs):
            observed["q_vectors"] = [list(sector["q_vector"]) for sector in kwargs["sectors"]]
            observed["sector_count"] = len(kwargs["sectors"])
            return {
                "status": "approximate",
                "ordering": {
                    "kind": "commensurate-multi-q",
                    "q_vectors": list(observed["q_vectors"]),
                    "supercell_shape": [2, 2, 1],
                },
                "lowest_shell_dimension": 2,
                "mixing_strategy": "test-double",
                "mixing_coefficients": [1.0, 0.0],
                "sector_phases": [0.0 for _ in kwargs["sectors"]],
                "projector_exactness": {
                    "trace_residual": 0.0,
                    "hermiticity_residual": 0.0,
                    "negativity_residual": 0.0,
                    "purity_residual": 1.0e-2,
                    "rank_one_residual": 1.0e-2,
                    "is_exact_projector_solution": False,
                    "cells": [],
                },
                "classical_state": {
                    "schema_version": 1,
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "basis_order": "orbital_major_spin_minor",
                    "pair_basis_order": "site_i_major_site_j_minor",
                    "supercell_shape": [2, 2, 1],
                    "local_rays": [],
                    "ordering": {
                        "kind": "commensurate-multi-q",
                        "q_vectors": list(observed["q_vectors"]),
                        "supercell_shape": [2, 2, 1],
                    },
                },
                "obstruction_report": {"reason": "test double"},
            }

        with patch(
            "classical.cpn_generalized_lt_solver.reconstruct_commensurate_relaxed_shell",
            side_effect=fake_reconstruct,
        ):
            result = solve_cpn_generalized_lt_ground_state(
                _single_sublattice_x_line_degenerate_model(),
                requested_method="cpn-generalized-lt",
                mesh_shape=(3, 3, 1),
                projector_tolerance=1.0e-8,
            )

        self.assertEqual(result["method"], "cpn-generalized-lt")
        self.assertEqual(result["solver_role"], "diagnostic-only")
        self.assertIn("reconstruction", result)
        self.assertEqual(result["reconstruction"]["status"], "approximate")
        self.assertGreaterEqual(observed["sector_count"], 2)
        self.assertIn([0.5, 0.0, 0.0], observed["q_vectors"])
        self.assertIn([0.5, 0.5, 0.0], observed["q_vectors"])


if __name__ == "__main__":
    unittest.main()
