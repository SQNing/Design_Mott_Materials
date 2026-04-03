import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from linear_spin_wave_driver import exact_diagonalization_branch


class LinearSpinWaveDriverTests(unittest.TestCase):
    def test_exact_diagonalization_solves_spin_half_dimer(self):
        summary = exact_diagonalization_branch({"local_dim": 2, "cluster_size": 2, "exchange": 1.0})
        self.assertTrue(summary["supported"])
        self.assertAlmostEqual(summary["ground_state_energy"], -0.75, places=6)

    def test_exact_diagonalization_rejects_non_spin_half_local_space(self):
        summary = exact_diagonalization_branch({"local_dim": 3, "cluster_size": 2, "exchange": 1.0})
        self.assertFalse(summary["supported"])
        self.assertEqual(summary["reason"], "unsupported-ed-scope")

    def test_exact_diagonalization_rejects_clusters_larger_than_a_dimer(self):
        summary = exact_diagonalization_branch({"local_dim": 2, "cluster_size": 3, "exchange": 1.0})
        self.assertFalse(summary["supported"])
        self.assertEqual(summary["reason"], "unsupported-ed-scope")


if __name__ == "__main__":
    unittest.main()
