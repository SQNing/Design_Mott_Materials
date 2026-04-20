import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical.generalized_lt_solver import find_generalized_lt_ground_state
from classical.lt_solver import find_lt_ground_state


def _bond(*, source, target, vector, matrix):
    return {
        "source": int(source),
        "target": int(target),
        "vector": [float(value) for value in vector],
        "matrix": [[float(value) for value in row] for row in matrix],
    }


def _spin_model(*, sublattices, bonds):
    return {
        "classical": {"method": "generalized-lt"},
        "local_dim": 2,
        "lattice": {
            "sublattices": int(sublattices),
            "dimension": 1,
            "positions": [[float(index), 0.0, 0.0] for index in range(sublattices)],
        },
        "bonds": list(bonds),
    }


class GeneralizedLtSolverTests(unittest.TestCase):
    def test_generalized_lt_improves_lt_bound_while_preserving_zero_sum_lambda_gauge(self):
        model = _spin_model(
            sublattices=2,
            bonds=[
                _bond(
                    source=0,
                    target=0,
                    vector=[0.0, 0.0, 0.0],
                    matrix=[
                        [-2.0, 0.0, 0.0],
                        [0.0, -1.0, 0.0],
                        [0.0, 0.0, -0.5],
                    ],
                )
            ],
        )

        lt_result = find_lt_ground_state(model, mesh_shape=(1, 1, 1))
        glt_result = find_generalized_lt_ground_state(
            model,
            mesh_shape=(1, 1, 1),
            lambda_bounds=(-2.0, 2.0),
            lambda_points=5,
            search_strategy="grid",
        )

        self.assertEqual(glt_result["matrix_size"], 6)
        self.assertEqual(glt_result["components_per_sublattice"], 3)
        self.assertEqual(len(glt_result["eigenspace"][0]), 6)
        self.assertAlmostEqual(sum(glt_result["lambda"]), 0.0, places=9)
        self.assertGreater(glt_result["tightened_lower_bound"], lt_result["lowest_eigenvalue"])

    def test_generalized_lt_reports_completion_metadata_for_tensor_shells(self):
        model = _spin_model(
            sublattices=2,
            bonds=[
                _bond(
                    source=0,
                    target=0,
                    vector=[0.0, 0.0, 0.0],
                    matrix=[
                        [0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0],
                    ],
                )
            ],
        )

        glt_result = find_generalized_lt_ground_state(
            model,
            mesh_shape=(1, 1, 1),
            lambda_bounds=(-1.0, 1.0),
            lambda_points=3,
            search_strategy="grid",
        )

        self.assertIn("constraint_recovery", glt_result)
        self.assertEqual(glt_result["constraint_recovery"]["status"], "completed_from_shell")
        self.assertLess(glt_result["constraint_recovery"]["max_site_norm_residual"], 1.0e-8)
        self.assertEqual(glt_result["active_shell_dimension"], 6)


if __name__ == "__main__":
    unittest.main()
