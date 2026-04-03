import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical_solver_driver import estimate_thermodynamics


class ClassicalSolverDriverTests(unittest.TestCase):
    def test_thermodynamic_fluctuations_are_computed_per_temperature(self):
        model = {
            "lattice": {"sublattices": 1},
            "bonds": [
                {
                    "source": 0,
                    "target": 0,
                    "matrix": [[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]],
                }
            ],
        }
        samples = {
            1.0: [
                (np.array([[0.1, 0.0, 0.0]]), 1.0),
                (np.array([[0.5, 0.0, 0.0]]), 3.0),
                (np.array([[0.1, 0.0, 0.0]]), 1.0),
                (np.array([[0.5, 0.0, 0.0]]), 3.0),
            ],
            2.0: [
                (np.array([[0.2, 0.0, 0.0]]), 2.0),
                (np.array([[0.2, 0.0, 0.0]]), 2.0),
                (np.array([[0.2, 0.0, 0.0]]), 2.0),
                (np.array([[0.2, 0.0, 0.0]]), 2.0),
            ],
        }
        indices = {1.0: 0, 2.0: 0}

        def fake_metropolis_step(_model, _spins, temperature, _rng):
            key = float(temperature)
            spin_configuration, energy = samples[key][indices[key]]
            indices[key] += 1
            return np.array(spin_configuration, dtype=float), float(energy)

        with patch("classical_solver_driver.random_spin", return_value=np.array([0.0, 0.0, 1.0])):
            with patch("classical_solver_driver.metropolis_step", side_effect=fake_metropolis_step):
                result = estimate_thermodynamics(model, [1.0, 2.0], sweeps=4, burn_in=0, seed=0)

        observables = result["observables"]
        self.assertEqual(observables["energy"], [2.0, 2.0])
        self.assertAlmostEqual(observables["specific_heat"][0], 1.0, places=6)
        self.assertAlmostEqual(observables["specific_heat"][1], 0.0, places=6)
        self.assertAlmostEqual(observables["susceptibility"][0], 0.04, places=6)
        self.assertAlmostEqual(observables["susceptibility"][1], 0.0, places=6)
        self.assertEqual(observables["free_energy"], [None, None])
        self.assertEqual(observables["entropy"], [None, None])


if __name__ == "__main__":
    unittest.main()
