import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from linear_spin_wave_driver import run_linear_spin_wave
from render_plots import render_plots


class RenderPlotsTests(unittest.TestCase):
    def test_render_plots_writes_payload_and_two_pngs_for_successful_lswt(self):
        payload = {
            "model_name": "fm-heisenberg-demo",
            "classical": {
                "chosen_method": "variational",
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
            result = render_plots(payload, output_dir=tmpdir)
            output_dir = Path(tmpdir)
            self.assertEqual(result["status"], "ok")
            self.assertTrue((output_dir / "plot_payload.json").exists())
            self.assertTrue((output_dir / "lswt_dispersion.png").exists())
            self.assertTrue((output_dir / "classical_state.png").exists())
            plot_payload = json.loads((output_dir / "plot_payload.json").read_text(encoding="utf-8"))
            self.assertEqual(plot_payload["metadata"]["backend"], "Sunny.jl")
            self.assertEqual(plot_payload["lswt_dispersion"]["band_count"], 2)

    def test_render_plots_keeps_classical_plot_when_lswt_failed(self):
        payload = {
            "model_name": "unstable-demo",
            "classical": {
                "chosen_method": "variational",
                "classical_state": {
                    "site_frames": [
                        {"site": 0, "spin_length": 0.5, "direction": [1.0, 0.0, 0.0]},
                    ],
                    "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                    "provenance": {"method": "variational", "converged": True},
                },
            },
            "lswt": {
                "status": "error",
                "backend": {"name": "Sunny.jl"},
                "error": {"code": "backend-execution-failed", "message": "Instability"},
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            result = render_plots(payload, output_dir=tmpdir)
            output_dir = Path(tmpdir)
            self.assertEqual(result["status"], "partial")
            self.assertTrue((output_dir / "plot_payload.json").exists())
            self.assertTrue((output_dir / "classical_state.png").exists())
            self.assertFalse((output_dir / "lswt_dispersion.png").exists())
            self.assertEqual(result["plots"]["lswt_dispersion"]["status"], "skipped")
            self.assertIn("backend-execution-failed", result["plots"]["lswt_dispersion"]["reason"])

    def test_render_plots_with_real_minimal_sunny_example(self):
        model = {
            "lattice": {"kind": "chain", "dimension": 1, "unit_cell": [0], "sublattices": 1},
            "simplified_model": {
                "template": "heisenberg",
                "bonds": [
                    {
                        "source": 0,
                        "target": 0,
                        "vector": [1, 0, 0],
                        "matrix": [
                            [-1.0, 0.0, 0.0],
                            [0.0, -1.0, 0.0],
                            [0.0, 0.0, -1.0],
                        ],
                    }
                ],
            },
            "classical_state": {
                "site_frames": [
                    {"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]},
                ],
                "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                "provenance": {"method": "variational", "converged": True},
            },
            "q_path": [[0.0, 0.0, 0.0], [3.141592653589793, 0.0, 0.0]],
        }
        lswt = run_linear_spin_wave(model, julia_cmd="julia")
        self.assertEqual(lswt["status"], "ok")
        payload = {
            "model_name": "real-minimal-sunny-example",
            "classical": {
                "chosen_method": "variational",
                "classical_state": model["classical_state"],
            },
            "lswt": lswt,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            result = render_plots(payload, output_dir=tmpdir)
            output_dir = Path(tmpdir)
            self.assertEqual(result["status"], "ok")
            self.assertTrue((output_dir / "plot_payload.json").exists())
            self.assertGreater((output_dir / "plot_payload.json").stat().st_size, 0)
            self.assertTrue((output_dir / "lswt_dispersion.png").exists())
            self.assertGreater((output_dir / "lswt_dispersion.png").stat().st_size, 0)
            self.assertTrue((output_dir / "classical_state.png").exists())
            self.assertGreater((output_dir / "classical_state.png").stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
