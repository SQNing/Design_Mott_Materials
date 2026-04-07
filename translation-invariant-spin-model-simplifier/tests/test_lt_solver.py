import math
import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical.lt_solver import find_lt_ground_state


class LTSolverTests(unittest.TestCase):
    def test_antiferromagnetic_chain_minimum_is_near_half_reciprocal_lattice_unit(self):
        model = {
            "lattice": {"kind": "chain", "dimension": 1, "sublattices": 1},
            "bonds": [
                {
                    "source": 0,
                    "target": 0,
                    "vector": [1, 0, 0],
                    "matrix": [
                        [1.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0],
                        [0.0, 0.0, 1.0],
                    ],
                }
            ],
        }

        result = find_lt_ground_state(model, mesh_shape=(65, 1, 1))

        self.assertAlmostEqual(result["q"][0], 0.5, places=3)
        self.assertAlmostEqual(result["lowest_eigenvalue"], -2.0, places=3)

    def test_multi_sublattice_solver_returns_eigenspace_metadata(self):
        model = {
            "lattice": {"kind": "kagome", "dimension": 2, "sublattices": 2},
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
                },
                {
                    "source": 0,
                    "target": 1,
                    "vector": [1, 0, 0],
                    "matrix": [
                        [2.0, 0.0, 0.0],
                        [0.0, 2.0, 0.0],
                        [0.0, 0.0, 2.0],
                    ],
                },
            ],
        }

        result = find_lt_ground_state(model, mesh_shape=(17, 1, 1))

        self.assertEqual(result["matrix_size"], 2)
        self.assertIn("eigenvector", result)
        self.assertEqual(len(result["eigenvector"]), 2)
        self.assertEqual(result["mesh_shape"], [17, 1, 1])

    def test_solver_uses_full_mesh_not_only_high_symmetry_path(self):
        model = {
            "lattice": {"kind": "chain", "dimension": 1, "sublattices": 1},
            "bonds": [
                {
                    "source": 0,
                    "target": 0,
                    "vector": [1, 0, 0],
                    "matrix": [
                        [-1.0, 0.0, 0.0],
                        [0.0, -1.0, 0.0],
                        [0.0, 0.0, -1.0],
                    ],
                }
            ],
        }

        result = find_lt_ground_state(model, mesh_shape=(9, 1, 1))

        self.assertEqual(result["sample_count"], 9)
        self.assertAlmostEqual(result["q"][0], 0.0, places=6)
        self.assertAlmostEqual(result["lowest_eigenvalue"], -2.0, places=6)


if __name__ == "__main__":
    unittest.main()
