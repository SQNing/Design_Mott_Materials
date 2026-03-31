import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from render_report import render_text


class RenderReportTests(unittest.TestCase):
    def test_render_text_includes_candidates_and_solver_choices(self):
        payload = {
            "normalized_model": {"local_hilbert": {"dimension": 2}},
            "simplification": {"recommended": 0, "candidates": [{"name": "symmetry-preserving"}]},
            "projection": {"status": "not-needed"},
            "classical": {"recommended_method": "variational", "chosen_method": "variational"},
            "linear_spin_wave": {"dispersion": [{"q": 0.0, "omega": 0.0}]},
        }
        text = render_text(payload)
        self.assertIn("Recommended simplification", text)
        self.assertIn("Chosen classical method", text)


if __name__ == "__main__":
    unittest.main()
