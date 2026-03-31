import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from write_results_bundle import write_results_bundle


class WriteResultsBundleTests(unittest.TestCase):
    def test_write_results_bundle_creates_report_and_plot_artifacts(self):
        payload = {
            "model_name": "bundle-demo",
            "normalized_model": {"local_hilbert": {"dimension": 2}},
            "simplification": {"recommended": 0, "candidates": [{"name": "template-map"}]},
            "projection": {"status": "not-needed"},
            "classical": {
                "chosen_method": "variational",
                "method_note": "Variational minimum used as the classical reference state.",
                "classical_state": {
                    "site_frames": [
                        {"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]},
                        {"site": 1, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]},
                    ],
                    "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                    "provenance": {"method": "variational", "converged": True},
                },
            },
            "lswt": {
                "status": "ok",
                "backend": {"name": "Sunny.jl"},
                "linear_spin_wave": {
                    "dispersion": [
                        {"q": [0.0, 0.0, 0.0], "bands": [0.0, 0.2], "omega": 0.0},
                        {"q": [3.141592653589793, 0.0, 0.0], "bands": [1.0, 1.2], "omega": 1.0},
                    ]
                },
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            result = write_results_bundle(payload, output_dir=tmpdir)
            output_dir = Path(tmpdir)
            self.assertEqual(result["status"], "ok")
            self.assertTrue((output_dir / "report.txt").exists())
            self.assertTrue((output_dir / "plot_payload.json").exists())
            self.assertTrue((output_dir / "lswt_dispersion.png").exists())
            self.assertTrue((output_dir / "classical_state.png").exists())
            report_text = (output_dir / "report.txt").read_text(encoding="utf-8")
            self.assertIn("Plot status: ok", report_text)
            self.assertIn("lswt_dispersion.png", report_text)
            bundle_manifest = json.loads((output_dir / "bundle_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(bundle_manifest["plots"]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
