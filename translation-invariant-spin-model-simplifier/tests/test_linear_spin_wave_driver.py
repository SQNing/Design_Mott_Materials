import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from linear_spin_wave_driver import exact_diagonalization_branch, linear_spin_wave_summary


class LinearSpinWaveDriverTests(unittest.TestCase):
    def test_linear_spin_wave_summary_returns_dispersion_and_dos(self):
        model = {
            "spin": 0.5,
            "exchange": 1.0,
            "q_grid": [0.0, 1.5707963267948966, 3.141592653589793],
        }
        summary = linear_spin_wave_summary(model)
        self.assertEqual(len(summary["dispersion"]), 3)
        self.assertIn("density_of_states", summary)

    def test_exact_diagonalization_branch_solves_spin_half_dimer(self):
        model = {"local_dim": 2, "cluster_size": 2, "exchange": 1.0}
        summary = exact_diagonalization_branch(model)
        self.assertTrue(summary["supported"])
        self.assertAlmostEqual(summary["ground_state_energy"], -0.75, places=6)


if __name__ == "__main__":
    unittest.main()
