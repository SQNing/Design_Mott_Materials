import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from render_report import render_text


class RenderReportTests(unittest.TestCase):
    def test_render_text_includes_sunny_backend_and_classical_method_on_success(self):
        payload = {
            "normalized_model": {"local_hilbert": {"dimension": 2}},
            "simplification": {"recommended": 0, "candidates": [{"name": "symmetry-preserving"}]},
            "projection": {"status": "not-needed"},
            "classical": {
                "recommended_method": "variational",
                "chosen_method": "variational",
                "method_note": "Variational minimum used as the classical reference state.",
            },
            "lswt": {
                "status": "ok",
                "backend": {"name": "Sunny.jl"},
                "linear_spin_wave": {"dispersion": [{"q": [0.0, 0.0, 0.0], "omega": 0.0}]},
            },
            "plots": {
                "status": "ok",
                "plots": {
                    "classical_state": {"status": "ok", "path": "/tmp/classical_state.png"},
                    "lswt_dispersion": {"status": "ok", "path": "/tmp/lswt_dispersion.png"},
                },
            },
        }
        text = render_text(payload)
        self.assertIn("Recommended simplification", text)
        self.assertIn("Chosen classical method", text)
        self.assertIn("Sunny.jl", text)
        self.assertIn("LSWT status: ok", text)
        self.assertIn("classical_state.png", text)
        self.assertIn("lswt_dispersion.png", text)

    def test_render_text_reports_partial_stop_when_lswt_does_not_run(self):
        payload = {
            "normalized_model": {"local_hilbert": {"dimension": 2}},
            "simplification": {"recommended": 0, "candidates": [{"name": "template-map"}]},
            "projection": {"status": "not-needed"},
            "classical": {
                "recommended_method": "luttinger-tisza",
                "chosen_method": "variational",
                "method_note": "Classical result remains valid and can seed LSWT once the backend is available.",
            },
            "lswt": {
                "status": "error",
                "backend": {"name": "Sunny.jl"},
                "error": {
                    "code": "missing-sunny-package",
                    "message": "Sunny.jl is not available in the active Julia environment",
                },
            },
            "plots": {
                "status": "partial",
                "plots": {
                    "classical_state": {"status": "ok", "path": "/tmp/classical_state.png"},
                    "lswt_dispersion": {
                        "status": "skipped",
                        "path": None,
                        "reason": "missing-sunny-package: Sunny.jl is not available in the active Julia environment",
                    },
                },
            },
        }
        text = render_text(payload)
        self.assertIn("Classical result remains valid", text)
        self.assertIn("missing-sunny-package", text)
        self.assertIn("Next step", text)
        self.assertIn("Plot status: partial", text)
        self.assertIn("Plot skip", text)


if __name__ == "__main__":
    unittest.main()
