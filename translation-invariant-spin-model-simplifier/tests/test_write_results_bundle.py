import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from write_results_bundle import write_results_bundle


class WriteResultsBundleTests(unittest.TestCase):
    def test_write_results_bundle_runs_missing_classical_and_lswt_stages(self):
        payload = {
            "model_name": "bundle-auto-demo",
            "normalized_model": {"local_hilbert": {"dimension": 2}},
            "simplification": {"recommended": 0, "candidates": [{"name": "faithful-readable"}]},
            "canonical_model": {"one_body": [], "two_body": [], "three_body": [], "four_body": [], "higher_body": []},
            "effective_model": {"main": [], "low_weight": [], "residual": []},
            "fidelity": {
                "reconstruction_error": 0.0,
                "main_fraction": 1.0,
                "low_weight_fraction": 0.0,
                "residual_fraction": 0.0,
                "risk_notes": [],
            },
            "projection": {"status": "not-needed"},
            "lattice": {"kind": "chain", "dimension": 1, "sublattices": 1, "positions": [[0.0, 0.0, 0.0]]},
            "bonds": [
                {
                    "source": 0,
                    "target": 0,
                    "vector": [1, 0, 0],
                    "matrix": [
                        [1.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0],
                        [0.0, 0.0, 1.0],
                    ],
                }
            ],
            "classical": {"method": "luttinger-tisza"},
        }

        solved_payload = {
            **payload,
            "classical": {
                "chosen_method": "luttinger-tisza",
                "classical_state": {
                    "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}],
                    "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                },
            },
            "classical_state": {
                "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}],
                "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
            },
            "lt_result": {"q": [0.5, 0.0, 0.0], "lowest_eigenvalue": -2.0, "matrix_size": 1},
            "variational_result": {"method": "variational", "energy": -1.0, "spins": [[0.0, 0.0, 1.0]]},
        }
        lswt_result = {
            "status": "ok",
            "backend": {"name": "Sunny.jl"},
            "path": {"labels": ["G", "X"], "node_indices": [0, 1]},
            "linear_spin_wave": {
                "dispersion": [
                    {"q": [0.0, 0.0, 0.0], "omega": 0.0, "bands": [0.0]},
                    {"q": [0.5, 0.0, 0.0], "omega": 1.0, "bands": [1.0]},
                ]
            },
        }

        def fake_render_plots(bundle_payload, output_dir):
            self.assertIn("classical_state", bundle_payload)
            self.assertIn("lswt", bundle_payload)
            self.assertEqual(bundle_payload["lswt"]["status"], "ok")
            return {"status": "ok", "plots": {"classical_state": {"status": "ok", "path": str(Path(output_dir) / "classical_state.png")}}}

        def fake_render_text(bundle_payload):
            self.assertIn("lswt", bundle_payload)
            return "bundle report"

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "write_results_bundle.run_classical_solver", return_value=solved_payload
        ) as classical_mock, patch(
            "write_results_bundle.run_linear_spin_wave", return_value=lswt_result
        ) as lswt_mock, patch(
            "write_results_bundle.render_plots", side_effect=fake_render_plots
        ), patch(
            "write_results_bundle.render_text", side_effect=fake_render_text
        ):
            manifest = write_results_bundle(payload, output_dir=tmpdir)
            output_dir = Path(tmpdir)
            self.assertTrue((output_dir / "report.txt").exists())
            self.assertTrue((output_dir / "bundle_manifest.json").exists())

        classical_mock.assert_called_once()
        lswt_mock.assert_called_once()
        self.assertEqual(manifest["status"], "ok")

    def test_write_results_bundle_preserves_existing_classical_and_lswt_results(self):
        payload = {
            "model_name": "bundle-existing-demo",
            "normalized_model": {"local_hilbert": {"dimension": 2}},
            "simplification": {"recommended": 0, "candidates": [{"name": "faithful-readable"}]},
            "canonical_model": {"one_body": [], "two_body": [], "three_body": [], "four_body": [], "higher_body": []},
            "effective_model": {"main": [], "low_weight": [], "residual": []},
            "fidelity": {
                "reconstruction_error": 0.0,
                "main_fraction": 1.0,
                "low_weight_fraction": 0.0,
                "residual_fraction": 0.0,
                "risk_notes": [],
            },
            "projection": {"status": "not-needed"},
            "classical": {
                "chosen_method": "luttinger-tisza",
                "classical_state": {
                    "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}],
                    "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                },
            },
            "lswt": {
                "status": "ok",
                "backend": {"name": "Sunny.jl"},
                "path": {"labels": ["G", "X"], "node_indices": [0, 1]},
                "linear_spin_wave": {"dispersion": [{"q": [0.0, 0.0, 0.0], "omega": 0.0, "bands": [0.0]}]},
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "write_results_bundle.run_classical_solver"
        ) as classical_mock, patch(
            "write_results_bundle.run_linear_spin_wave"
        ) as lswt_mock, patch(
            "write_results_bundle.render_plots",
            return_value={"status": "ok", "plots": {}},
        ), patch(
            "write_results_bundle.render_text",
            return_value="bundle report",
        ):
            manifest = write_results_bundle(payload, output_dir=tmpdir)

        classical_mock.assert_not_called()
        lswt_mock.assert_not_called()
        self.assertEqual(manifest["status"], "ok")

    def test_write_results_bundle_can_skip_auto_classical_and_lswt(self):
        payload = {
            "model_name": "bundle-skip-demo",
            "normalized_model": {"local_hilbert": {"dimension": 2}},
            "simplification": {"recommended": 0, "candidates": [{"name": "faithful-readable"}]},
            "canonical_model": {"one_body": [], "two_body": [], "three_body": [], "four_body": [], "higher_body": []},
            "effective_model": {"main": [], "low_weight": [], "residual": []},
            "fidelity": {
                "reconstruction_error": 0.0,
                "main_fraction": 1.0,
                "low_weight_fraction": 0.0,
                "residual_fraction": 0.0,
                "risk_notes": [],
            },
            "projection": {"status": "not-needed"},
            "lattice": {"kind": "chain", "dimension": 1, "sublattices": 1, "positions": [[0.0, 0.0, 0.0]]},
            "bonds": [
                {
                    "source": 0,
                    "target": 0,
                    "vector": [1, 0, 0],
                    "matrix": [
                        [1.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0],
                        [0.0, 0.0, 1.0],
                    ],
                }
            ],
            "classical": {"method": "luttinger-tisza"},
        }

        def fake_render_plots(bundle_payload, output_dir):
            self.assertNotIn("classical_state", bundle_payload)
            self.assertNotIn("lswt", bundle_payload)
            return {"status": "partial", "plots": {}}

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "write_results_bundle.run_classical_solver"
        ) as classical_mock, patch(
            "write_results_bundle.run_linear_spin_wave"
        ) as lswt_mock, patch(
            "write_results_bundle.render_plots", side_effect=fake_render_plots
        ), patch(
            "write_results_bundle.render_text",
            return_value="bundle report",
        ):
            manifest = write_results_bundle(
                payload,
                output_dir=tmpdir,
                run_missing_classical=False,
                run_missing_lswt=False,
            )

        classical_mock.assert_not_called()
        lswt_mock.assert_not_called()
        self.assertEqual(manifest["status"], "partial")


if __name__ == "__main__":
    unittest.main()
