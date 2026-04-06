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
    integrated_autocorrelation_time,
    recommend_method,
    resolve_temperature_schedule,
    run_classical_solver,
    solve_variational,
    summarize_thermodynamics,
)


class ClassicalSolverDriverTests(unittest.TestCase):
    def test_recommend_method_prefers_luttinger_tisza_for_single_sublattice_bilinear_models(self):
        model = {"lattice": {"sublattices": 1}, "simplified_model": {"template": "xxz"}}
        self.assertEqual(recommend_method(model), "luttinger-tisza")

    def test_recommend_method_accepts_effective_model_main_block(self):
        model = {
            "lattice": {"sublattices": 1},
            "effective_model": {"main": [{"type": "isotropic_exchange", "coefficient": 1.0}]},
        }
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
        self.assertTrue(np.allclose(result["observables"]["energy"], [-1.0, -1.0]))
        self.assertTrue(np.allclose(result["observables"]["specific_heat"], [0.0, 0.0]))
        self.assertTrue(np.allclose(result["observables"]["free_energy"], [-1.0, -1.0]))
        self.assertTrue(np.allclose(result["observables"]["entropy"], [0.0, 0.0]))

    def test_summarize_thermodynamics_uses_fluctuation_formulas_and_thermodynamic_integration(self):
        temperatures = [2.0, 1.0]
        energy_samples = [[0.0, 2.0], [1.0, 3.0]]
        magnetization_samples = [[1.0, -1.0], [2.0, 0.0]]

        result = summarize_thermodynamics(
            temperatures,
            energy_samples,
            magnetization_samples,
            high_temperature_entropy=0.0,
            energy_infinite_temperature=0.0,
        )

        self.assertEqual(result["observables"]["energy"], [1.0, 2.0])
        self.assertEqual(result["observables"]["magnetization"], [0.0, 1.0])
        self.assertTrue(np.allclose(result["observables"]["specific_heat"], [0.25, 1.0]))
        self.assertTrue(np.allclose(result["observables"]["susceptibility"], [0.5, 1.0]))
        self.assertTrue(np.allclose(result["observables"]["free_energy"], [0.5, 1.0]))
        self.assertTrue(np.allclose(result["observables"]["entropy"], [0.25, 1.0]))

    def test_run_classical_solver_includes_requested_thermodynamics(self):
        payload = {
            "lattice": {"sublattices": 1},
            "bonds": [{"source": 0, "target": 0, "matrix": [[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]}],
            "thermodynamics": {"temperatures": [0.5, 1.0], "sweeps": 8, "burn_in": 4},
        }

        result = run_classical_solver(payload, starts=4, seed=1)

        self.assertIn("variational_result", result)
        self.assertIn("thermodynamics_result", result)
        self.assertEqual(len(result["thermodynamics_result"]["grid"]), 2)
        self.assertEqual(
            sorted(result["thermodynamics_result"]["observables"].keys()),
            ["energy", "entropy", "free_energy", "magnetization", "specific_heat", "susceptibility"],
        )

    def test_summarize_thermodynamics_reports_uncertainties_and_autocorrelation(self):
        temperatures = [2.0, 1.0]
        energy_samples = [[0.0, 1.0, 2.0, 3.0], [0.0, 2.0, 2.0, 4.0]]
        magnetization_samples = [[1.0, -1.0, 0.0, 2.0], [2.0, 0.0, 1.0, -1.0]]

        result = summarize_thermodynamics(
            temperatures,
            energy_samples,
            magnetization_samples,
            high_temperature_entropy=0.0,
            energy_infinite_temperature=0.0,
        )

        self.assertIn("uncertainties", result)
        self.assertIn("autocorrelation", result)
        self.assertEqual(sorted(result["uncertainties"].keys()), ["energy", "entropy", "free_energy", "magnetization", "specific_heat", "susceptibility"])
        self.assertEqual(sorted(result["autocorrelation"].keys()), ["energy", "magnetization"])
        self.assertEqual(len(result["uncertainties"]["energy"]), 2)
        self.assertEqual(len(result["autocorrelation"]["energy"]), 2)
        self.assertGreaterEqual(result["uncertainties"]["energy"][0], 0.0)
        self.assertGreaterEqual(result["uncertainties"]["specific_heat"][1], 0.0)

    def test_integrated_autocorrelation_time_vanishes_for_constant_series(self):
        self.assertEqual(integrated_autocorrelation_time([1.0, 1.0, 1.0, 1.0]), 0.0)

    def test_temperature_schedule_can_sort_ascending_or_descending(self):
        temperatures = [1.0, 0.25, 0.5]
        self.assertEqual(resolve_temperature_schedule(temperatures, "ascending"), [(1, 0.25), (2, 0.5), (0, 1.0)])
        self.assertEqual(resolve_temperature_schedule(temperatures, "descending"), [(0, 1.0), (2, 0.5), (1, 0.25)])


if __name__ == "__main__":
    unittest.main()
