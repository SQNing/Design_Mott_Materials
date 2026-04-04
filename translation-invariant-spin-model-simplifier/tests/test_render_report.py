import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from render_report import render_text


class RenderReportTests(unittest.TestCase):
    def test_render_text_includes_layered_model_and_fidelity_sections(self):
        payload = {
            "normalized_model": {"local_hilbert": {"dimension": 2}},
            "canonical_model": {"one_body": [], "two_body": [{"canonical_label": "Sx@0 Sx@1"}], "three_body": [], "four_body": []},
            "effective_model": {
                "main": [{"type": "isotropic_exchange", "coefficient": 1.0}],
                "low_weight": [{"canonical_label": "Sz@0", "coefficient": 0.05, "warning": "breaks_time_reversal"}],
                "residual": [{"canonical_label": "Sx@0 Sy@1 Sz@2", "coefficient": 0.1}],
            },
            "fidelity": {
                "main_fraction": 0.8,
                "low_weight_fraction": 0.1,
                "residual_fraction": 0.1,
                "reconstruction_error": 0.0,
                "risk_notes": ["Low-weight term may still be physically important"],
            },
            "simplification": {"recommended": 0, "candidates": [{"name": "faithful-readable", "requires_user_confirmation": False}]},
            "projection": {"status": "not-needed"},
            "classical": {"recommended_method": "variational", "chosen_method": "variational"},
            "linear_spin_wave": {"dispersion": [{"q": 0.0, "omega": 0.0}]},
        }
        text = render_text(payload)
        self.assertIn("Recommended simplification", text)
        self.assertIn("Canonical model summary", text)
        self.assertIn("Readable main model", text)
        self.assertIn("Low-weight terms", text)
        self.assertIn("Residual terms", text)
        self.assertIn("Fidelity report", text)
        self.assertIn("Chosen classical method", text)


if __name__ == "__main__":
    unittest.main()
