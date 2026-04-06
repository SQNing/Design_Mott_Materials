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

    def test_render_text_includes_thermodynamics_summary_when_available(self):
        payload = {
            "normalized_model": {"local_hilbert": {"dimension": 2}},
            "canonical_model": {"one_body": [], "two_body": [], "three_body": [], "four_body": []},
            "effective_model": {"main": [], "low_weight": [], "residual": []},
            "fidelity": {
                "main_fraction": 1.0,
                "low_weight_fraction": 0.0,
                "residual_fraction": 0.0,
                "reconstruction_error": 0.0,
                "risk_notes": [],
            },
            "simplification": {"recommended": 0, "candidates": [{"name": "faithful-readable", "requires_user_confirmation": False}]},
            "projection": {"status": "not-needed"},
            "classical": {"recommended_method": "variational", "chosen_method": "variational"},
            "thermodynamics_result": {
                "sampling": {
                    "scan_order": "ascending",
                    "reuse_configuration": True,
                    "sweeps": 16,
                    "burn_in": 8,
                    "measurement_interval": 2,
                },
                "autocorrelation": {
                    "energy": [0.5, 0.75],
                    "magnetization": [0.5, 1.0],
                },
                "uncertainties": {
                    "energy": [0.01, 0.02],
                    "free_energy": [0.01, 0.03],
                    "specific_heat": [0.0, 0.05],
                    "magnetization": [0.04, 0.06],
                    "susceptibility": [0.01, 0.07],
                    "entropy": [0.0, 0.02],
                },
                "observables": {
                    "energy": [-1.0, -0.8],
                    "free_energy": [-1.0, -0.9],
                    "specific_heat": [0.0, 0.2],
                    "magnetization": [0.6, 0.2],
                    "susceptibility": [0.1, 0.3],
                    "entropy": [0.0, 0.1],
                },
                "grid": [
                    {
                        "temperature": 0.5,
                        "energy": -1.0,
                        "free_energy": -1.0,
                        "specific_heat": 0.0,
                        "magnetization": 0.6,
                        "susceptibility": 0.1,
                        "entropy": 0.0,
                    },
                    {
                        "temperature": 1.0,
                        "energy": -0.8,
                        "free_energy": -0.9,
                        "specific_heat": 0.2,
                        "magnetization": 0.2,
                        "susceptibility": 0.3,
                        "entropy": 0.1,
                    },
                ],
            },
            "linear_spin_wave": {"dispersion": []},
        }

        text = render_text(payload)

        self.assertIn("Classical thermodynamics", text)
        self.assertIn("T=0.5", text)
        self.assertIn("specific_heat=0.2", text)
        self.assertIn("susceptibility=0.3", text)
        self.assertIn("scan_order=ascending", text)
        self.assertIn("energy_stderr=0.02", text)
        self.assertIn("tau_E=0.75", text)


if __name__ == "__main__":
    unittest.main()
