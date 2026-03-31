import sys
import unittest
from pathlib import Path

import numpy as np

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical_solver_driver import (
    choose_method,
    classical_energy,
    estimate_thermodynamics,
    recommend_method,
    resolve_model_bonds,
    solve_luttinger_tisza,
    solve_variational,
)


class ClassicalSolverDriverTests(unittest.TestCase):
    def test_recommend_method_prefers_luttinger_tisza_for_single_sublattice_bilinear_models(self):
        model = {"lattice": {"sublattices": 1}, "simplified_model": {"template": "xxz"}}
        self.assertEqual(recommend_method(model), "luttinger-tisza")

    def test_variational_solver_finds_ferromagnetic_alignment_for_negative_j(self):
        model = {
            "lattice": {"sublattices": 1},
            "bonds": [{"source": 0, "target": 0, "matrix": [[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]}],
        }
        result = solve_variational(model, starts=8, seed=3)
        self.assertLessEqual(result["energy"], -0.99)
        spins = np.array(result["spins"])
        self.assertAlmostEqual(float(np.linalg.norm(spins[0])), 1.0, places=6)

    def test_variational_solver_emits_structured_classical_state_for_lswt(self):
        model = {
            "lattice": {"sublattices": 1},
            "bonds": [{"source": 0, "target": 0, "matrix": [[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]}],
        }
        result = solve_variational(model, starts=8, seed=3)
        self.assertIn("classical_state", result)
        self.assertIn("site_frames", result["classical_state"])
        self.assertIn("ordering", result["classical_state"])
        self.assertEqual(result["classical_state"]["provenance"]["method"], "variational")
        self.assertTrue(result["classical_state"]["provenance"]["converged"])
        self.assertEqual(len(result["classical_state"]["site_frames"]), 1)
        self.assertAlmostEqual(result["classical_state"]["site_frames"][0]["spin_length"], 1.0, places=6)

    def test_timeout_selects_recommended_classical_method(self):
        model = {"lattice": {"sublattices": 1}, "simplified_model": {"template": "heisenberg"}}
        choice = choose_method(model, user_choice=None, timed_out=True)
        self.assertEqual(choice["method"], "luttinger-tisza")
        self.assertTrue(choice["auto_selected"])

    def test_classical_thermodynamics_returns_requested_observables(self):
        model = {
            "lattice": {"sublattices": 1},
            "bonds": [{"source": 0, "target": 0, "matrix": [[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]}],
        }
        temperatures = [0.5, 1.0]
        result = estimate_thermodynamics(model, temperatures, sweeps=8, burn_in=4, seed=1)
        self.assertEqual(
            sorted(result["observables"].keys()),
            ["energy", "entropy", "free_energy", "magnetization", "specific_heat", "susceptibility"],
        )
        self.assertEqual(len(result["grid"]), 2)

    def test_luttinger_tisza_finds_rectangular_j1_j2_stripe_order(self):
        model = {
            "lattice": {
                "sublattices": 1,
                "positions": [[0.0, 0.0, 0.0]],
                "lattice_vectors": [[3.0, 0.0, 0.0], [0.0, 8.0, 0.0], [0.0, 0.0, 8.0]],
            },
            "simplified_model": {"template": "heisenberg"},
            "bonds": [
                {"source": 0, "target": 0, "vector": [1, 0, 0], "matrix": [[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]},
                {"source": 0, "target": 0, "vector": [0, 1, 0], "matrix": [[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]},
                {"source": 0, "target": 0, "vector": [1, 1, 0], "matrix": [[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 2.0]]},
                {"source": 0, "target": 0, "vector": [1, -1, 0], "matrix": [[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 2.0]]},
            ],
        }
        result = solve_luttinger_tisza(model, grid_size=17)
        self.assertLess(result["energy"], -3.9)
        self.assertAlmostEqual(result["energy_per_unit_cell"], -4.0, places=6)
        self.assertAlmostEqual(result["magnetic_supercell_energy"], -8.0, places=6)
        self.assertEqual(result["magnetic_periods"], [1, 2, 1])
        self.assertIn("ordering", result["classical_state"])
        q_vector = result["classical_state"]["ordering"]["q_vector"]
        self.assertTrue(
            np.allclose(q_vector, [0.5, 0.0, 0.0], atol=1e-6)
            or np.allclose(q_vector, [0.0, 0.5, 0.0], atol=1e-6)
        )

    def test_luttinger_tisza_can_derive_chain_shell_bonds_from_lattice_and_j_parameters(self):
        model = {
            "lattice": {
                "kind": "orthorhombic",
                "dimension": 3,
                "sublattices": 1,
                "cell_parameters": {
                    "a": 3.0,
                    "b": 8.0,
                    "c": 8.0,
                    "alpha": 90.0,
                    "beta": 90.0,
                    "gamma": 90.0,
                },
                "positions": [[0.0, 0.0, 0.0]],
            },
            "parameters": {"J1": -1.0, "J2": 2.0},
            "simplified_model": {"template": "heisenberg"},
        }
        result = solve_luttinger_tisza(model, grid_size=129)
        self.assertAlmostEqual(result["energy_per_unit_cell"], -2.0625, places=3)
        self.assertAlmostEqual(result["q_vector"][0], 0.2300534561, places=2)
        self.assertAlmostEqual(result["q_vector"][1], 0.0, places=6)
        self.assertAlmostEqual(result["q_vector"][2], 0.0, places=6)

    def test_resolve_model_bonds_respects_exchange_mapping_shell_overrides(self):
        model = {
            "lattice": {
                "kind": "orthorhombic",
                "cell_parameters": {
                    "a": 3.0,
                    "b": 8.0,
                    "c": 8.0,
                    "alpha": 90.0,
                    "beta": 90.0,
                    "gamma": 90.0,
                },
                "positions": [[0.0, 0.0, 0.0]],
            },
            "parameters": {"J1": -1.0, "J2": 2.0},
            "exchange_mapping": {"mode": "distance-shells", "shell_map": {"J1": 1, "J2": 3}},
            "simplified_model": {"template": "heisenberg"},
        }
        bonds = resolve_model_bonds(model)
        self.assertEqual(sorted(tuple(bond["vector"]) for bond in bonds), [(0, 0, 1), (0, 1, 0), (1, 0, 0)])


if __name__ == "__main__":
    unittest.main()
