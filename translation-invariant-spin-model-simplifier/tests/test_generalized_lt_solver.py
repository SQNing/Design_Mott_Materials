import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical.generalized_lt_solver import find_generalized_lt_ground_state


class GeneralizedLTSolverTests(unittest.TestCase):
    def test_generalized_lt_can_tighten_lower_bound_for_toy_two_sublattice_model(self):
        model = {
            "lattice": {"kind": "chain", "dimension": 1, "sublattices": 2},
            "bonds": [
                {
                    "source": 1,
                    "target": 1,
                    "vector": [0, 0, 0],
                    "matrix": [
                        [-1.0, 0.0, 0.0],
                        [0.0, -1.0, 0.0],
                        [0.0, 0.0, -1.0],
                    ],
                }
            ],
        }

        result = find_generalized_lt_ground_state(model, mesh_shape=(3, 1, 1), lambda_bounds=(-1.0, 1.0), lambda_points=41)

        self.assertGreater(result["tightened_lower_bound"], -1.0)

    def test_generalized_lt_respects_zero_sum_lambda_gauge(self):
        model = {
            "lattice": {"kind": "chain", "dimension": 1, "sublattices": 2},
            "bonds": [
                {
                    "source": 0,
                    "target": 1,
                    "vector": [0, 0, 0],
                    "matrix": [
                        [1.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0],
                        [0.0, 0.0, 1.0],
                    ],
                }
            ],
        }

        result = find_generalized_lt_ground_state(model, mesh_shape=(3, 1, 1), lambda_bounds=(-1.0, 1.0), lambda_points=21)

        self.assertAlmostEqual(sum(result["lambda"]), 0.0, places=6)

    def test_generalized_lt_returns_required_output_contract(self):
        model = {
            "lattice": {"kind": "chain", "dimension": 1, "sublattices": 2},
            "bonds": [
                {
                    "source": 0,
                    "target": 1,
                    "vector": [1, 0, 0],
                    "matrix": [
                        [1.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0],
                        [0.0, 0.0, 1.0],
                    ],
                }
            ],
        }

        result = find_generalized_lt_ground_state(model, mesh_shape=(9, 1, 1), lambda_bounds=(-0.5, 0.5), lambda_points=11)

        self.assertIn("lambda", result)
        self.assertIn("tightened_lower_bound", result)
        self.assertIn("q", result)
        self.assertIn("eigenspace", result)
        self.assertEqual(len(result["lambda"]), 2)

    def test_generalized_lt_reports_optimization_metadata(self):
        model = {
            "lattice": {"kind": "chain", "dimension": 1, "sublattices": 2},
            "bonds": [
                {
                    "source": 0,
                    "target": 1,
                    "vector": [1, 0, 0],
                    "matrix": [
                        [1.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0],
                        [0.0, 0.0, 1.0],
                    ],
                }
            ],
        }

        result = find_generalized_lt_ground_state(
            model,
            mesh_shape=(9, 1, 1),
            lambda_bounds=(-0.5, 0.5),
            lambda_points=11,
            search_strategy="grid",
        )

        self.assertIn("optimization", result)
        self.assertEqual(result["optimization"]["search_strategy"], "grid")
        self.assertGreater(result["optimization"]["evaluated_candidates"], 0)

    def test_generalized_lt_accepts_coordinate_search_strategy(self):
        model = {
            "lattice": {"kind": "chain", "dimension": 1, "sublattices": 2},
            "bonds": [
                {
                    "source": 0,
                    "target": 1,
                    "vector": [0, 0, 0],
                    "matrix": [
                        [1.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0],
                        [0.0, 0.0, 1.0],
                    ],
                }
            ],
        }

        result = find_generalized_lt_ground_state(
            model,
            mesh_shape=(5, 1, 1),
            lambda_bounds=(-1.0, 1.0),
            lambda_points=11,
            search_strategy="coordinate",
        )

        self.assertEqual(result["optimization"]["search_strategy"], "coordinate")


if __name__ == "__main__":
    unittest.main()
