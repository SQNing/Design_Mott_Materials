import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from score_fidelity import score_fidelity


class ScoreFidelityTests(unittest.TestCase):
    def test_reports_weight_fractions_and_reconstruction_error(self):
        effective_model = {
            "main": [{"coefficient": 1.0}],
            "low_weight": [{"coefficient": 0.2}],
            "residual": [{"coefficient": 0.1}],
        }
        scored = score_fidelity(effective_model)
        self.assertAlmostEqual(scored["main_fraction"], 1.0 / 1.3)
        self.assertAlmostEqual(scored["low_weight_fraction"], 0.2 / 1.3)
        self.assertAlmostEqual(scored["residual_fraction"], 0.1 / 1.3)
        self.assertEqual(scored["reconstruction_error"], 0.0)

    def test_emits_risk_note_for_symmetry_sensitive_low_weight_terms(self):
        effective_model = {
            "main": [{"coefficient": 1.0}],
            "low_weight": [{"coefficient": 0.05, "warning": "breaks_time_reversal"}],
            "residual": [],
        }
        scored = score_fidelity(effective_model)
        self.assertTrue(scored["risk_notes"])


if __name__ == "__main__":
    unittest.main()
