import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical import classical_solver_driver


def _spin_only_payload(method, *, sublattices=1):
    return {
        "classical": {"method": method},
        "local_dim": 2,
        "lattice": {"sublattices": sublattices, "dimension": 1},
        "bonds": [
            {
                "source": 0,
                "target": 0,
                "vector": [0.0, 0.0, 0.0],
                "matrix": [
                    [1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.0, 0.0, 1.0],
                ],
            }
        ],
    }


class ClassicalSolverLayerAdapterTests(unittest.TestCase):
    def test_spin_only_variational_result_includes_normalized_classical_state_result(self):
        payload = _spin_only_payload("variational")

        with patch.object(
            classical_solver_driver,
            "solve_variational",
            return_value={"method": "variational", "energy": -1.25, "spins": [[0.0, 0.0, 1.0]]},
        ):
            result = classical_solver_driver.run_classical_solver(payload, starts=1, seed=0)

        self.assertIn("classical_state_result", result)
        self.assertIn("variational_result", result)
        self.assertIn("classical_state", result)

        standardized = result["classical_state_result"]
        self.assertEqual(standardized["status"], "ok")
        self.assertEqual(standardized["role"], "final")
        self.assertEqual(standardized["solver_family"], "spin_only_explicit")
        self.assertEqual(standardized["method"], "spin-only-variational")
        self.assertEqual(standardized["energy"], -1.25)
        self.assertEqual(standardized["classical_state"], result["classical_state"])
        self.assertEqual(standardized["ordering"], result["classical_state"]["ordering"])
        self.assertEqual(standardized["downstream_compatibility"]["lswt"]["status"], "ready")
        self.assertEqual(standardized["downstream_compatibility"]["gswt"]["status"], "blocked")

    def test_spin_only_luttinger_tisza_result_normalizes_ordering_energy_and_compatibility(self):
        payload = _spin_only_payload("luttinger-tisza")
        recovered_state = {
            "site_frames": [
                {
                    "site": 0,
                    "spin_length": 0.5,
                    "direction": [1.0, 0.0, 0.0],
                }
            ],
            "ordering": {
                "kind": "single-q",
                "q_vector": [0.5, 0.0, 0.0],
                "supercell_shape": [2, 1, 1],
            },
            "constraint_recovery": {"strong_constraint_residual": 0.0},
        }

        with (
            patch.object(
                classical_solver_driver,
                "find_lt_ground_state",
                return_value={
                    "q": [0.5, 0.0, 0.0],
                    "lowest_eigenvalue": -2.0,
                    "eigenvector": [{"real": 1.0, "imag": 0.0}],
                },
            ),
            patch.object(
                classical_solver_driver,
                "recover_classical_state_from_lt",
                return_value=recovered_state,
            ),
            patch.object(
                classical_solver_driver,
                "solve_variational",
                return_value={"method": "variational", "energy": -1.0, "spins": [[0.0, 0.0, 1.0]]},
            ),
        ):
            result = classical_solver_driver.run_classical_solver(payload, starts=1, seed=0)

        standardized = result["classical_state_result"]
        self.assertEqual(standardized["role"], "final")
        self.assertEqual(standardized["solver_family"], "spin_only_explicit")
        self.assertEqual(standardized["method"], "spin-only-luttinger-tisza")
        self.assertEqual(standardized["ordering"], recovered_state["ordering"])
        self.assertEqual(standardized["energy"], -2.0)
        self.assertEqual(standardized["supercell_shape"], [2, 1, 1])
        self.assertEqual(standardized["downstream_compatibility"]["lswt"]["status"], "ready")
        self.assertEqual(standardized["downstream_compatibility"]["gswt"]["status"], "blocked")
        self.assertEqual(standardized["downstream_compatibility"]["thermodynamics"]["status"], "review")
        self.assertIn("lt_result", result)

    def test_spin_only_generalized_lt_result_uses_generalized_method_mapping(self):
        payload = _spin_only_payload("generalized-lt", sublattices=2)
        recovered_state = {
            "site_frames": [
                {
                    "site": 0,
                    "spin_length": 0.5,
                    "direction": [0.0, 1.0, 0.0],
                }
            ],
            "ordering": {
                "kind": "single-q",
                "q_vector": [0.25, 0.25, 0.0],
                "supercell_shape": [2, 2, 1],
            },
            "constraint_recovery": {"strong_constraint_residual": 0.0},
        }

        with (
            patch.object(
                classical_solver_driver,
                "find_lt_ground_state",
                return_value={
                    "q": [0.25, 0.25, 0.0],
                    "lowest_eigenvalue": -1.8,
                    "eigenvector": [{"real": 1.0, "imag": 0.0}],
                },
            ),
            patch.object(
                classical_solver_driver,
                "find_generalized_lt_ground_state",
                return_value={
                    "q": [0.25, 0.25, 0.0],
                    "tightened_lower_bound": -2.2,
                    "eigenspace": [[{"real": 1.0, "imag": 0.0}]],
                },
            ),
            patch.object(
                classical_solver_driver,
                "recover_classical_state_from_lt",
                return_value=recovered_state,
            ),
            patch.object(
                classical_solver_driver,
                "solve_variational",
                return_value={"method": "variational", "energy": -1.0, "spins": [[0.0, 0.0, 1.0]]},
            ),
        ):
            result = classical_solver_driver.run_classical_solver(payload, starts=1, seed=0)

        standardized = result["classical_state_result"]
        self.assertEqual(standardized["solver_family"], "spin_only_explicit")
        self.assertEqual(standardized["method"], "spin-only-generalized-lt")
        self.assertEqual(standardized["ordering"], recovered_state["ordering"])
        self.assertEqual(standardized["energy"], -2.2)
        self.assertIn("generalized_lt_result", result)


if __name__ == "__main__":
    unittest.main()
