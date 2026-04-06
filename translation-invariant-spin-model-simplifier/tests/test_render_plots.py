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

    def test_render_plots_writes_thermodynamics_plot_when_available(self):
        payload = {
            "model_name": "thermo-demo",
            "classical": {
                "chosen_method": "variational",
                "classical_state": {
                    "site_frames": [
                        {"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]},
                    ],
                    "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                    "provenance": {"method": "variational", "converged": True},
                },
            },
            "thermodynamics_result": {
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
            "lswt": {
                "status": "error",
                "backend": {"name": "Sunny.jl"},
                "error": {"code": "missing-sunny-package", "message": "not installed"},
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            result = render_plots(payload, output_dir=tmpdir)
            output_dir = Path(tmpdir)
            self.assertEqual(result["plots"]["thermodynamics"]["status"], "ok")
            self.assertTrue((output_dir / "thermodynamics.png").exists())
            self.assertGreater((output_dir / "thermodynamics.png").stat().st_size, 0)

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

    def test_render_plots_expands_commensurate_state_to_at_least_two_by_two_magnetic_cells(self):
        payload = {
            "model_name": "stripe-demo",
            "lattice": {
                "kind": "rectangular",
                "lattice_vectors": [[3.0, 0.0, 0.0], [0.0, 8.0, 0.0], [0.0, 0.0, 8.0]],
                "positions": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
            },
            "classical": {
                "chosen_method": "luttinger-tisza",
                "classical_state": {
                    "site_frames": [
                        {"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]},
                        {"site": 1, "spin_length": 0.5, "direction": [0.0, 0.0, -1.0]},
                    ],
                    "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.5, 0.0]},
                    "provenance": {"method": "luttinger-tisza", "converged": True},
                },
            },
            "lswt": {
                "status": "ok",
                "backend": {"name": "Sunny.jl"},
                "path": {"labels": ["G", "X", "S", "Y", "G"], "node_indices": [0, 8, 16, 24, 32]},
                "linear_spin_wave": {
                    "dispersion": [
                        {"q": [0.0, 0.0, 0.0], "bands": [0.0], "omega": 0.0},
                        {"q": [0.5, 0.0, 0.0], "bands": [1.0], "omega": 1.0},
                    ]
                },
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            render_plots(payload, output_dir=tmpdir)
            plot_payload = json.loads((Path(tmpdir) / "plot_payload.json").read_text(encoding="utf-8"))
            self.assertEqual(plot_payload["classical_state"]["magnetic_periods"], [1, 2, 1])
            self.assertEqual(plot_payload["classical_state"]["repeat_cells"], [2, 4, 1])
            self.assertEqual(plot_payload["classical_state"]["spatial_dimension"], 2)
            self.assertEqual(len(plot_payload["classical_state"]["expanded_sites"]), 16)
            self.assertEqual(len(plot_payload["classical_state"]["basis_legend"]), 2)
            self.assertEqual(plot_payload["classical_state"]["render_mode"], "structure")
            self.assertTrue(plot_payload["classical_state"]["unit_cell_segments"])
            self.assertEqual(plot_payload["classical_state"]["view"]["projection"], "3d")
            self.assertEqual(plot_payload["classical_state"]["style"]["atom_fill"], "#c9c9c9")
            self.assertEqual(plot_payload["classical_state"]["style"]["spin_color"], "#d00000")
            self.assertGreater(plot_payload["classical_state"]["style"]["arrow_length_factor"], 0.3)
            self.assertEqual(plot_payload["classical_state"]["display_rotation"]["kind"], "global")
            self.assertEqual(len(plot_payload["classical_state"]["lattice_labels"]), 2)
            self.assertEqual(plot_payload["classical_state"]["lattice_labels"][0]["text"], "a1")


if __name__ == "__main__":
    unittest.main()
