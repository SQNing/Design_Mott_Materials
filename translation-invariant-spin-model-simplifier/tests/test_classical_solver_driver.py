import sys
import unittest
from pathlib import Path

import numpy as np

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical_solver_driver import choose_method, classical_energy, estimate_thermodynamics, recommend_method, solve_variational


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


if __name__ == "__main__":
    unittest.main()
