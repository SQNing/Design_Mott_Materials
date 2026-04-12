import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from cli.write_results_bundle import main, write_results_bundle


class WriteResultsBundleTests(unittest.TestCase):
    def test_write_results_bundle_main_maps_cli_flags_to_stage_controls(self):
        payload_path = Path(tempfile.gettempdir()) / "bundle-cli-demo.json"
        payload_path.write_text("{}", encoding="utf-8")

        with patch.object(
            sys,
            "argv",
            [
                "write_results_bundle.py",
                str(payload_path),
                "--output-dir",
                "/tmp/bundle-cli-out",
                "--no-auto-classical",
                "--no-auto-thermodynamics",
                "--no-auto-gswt",
                "--no-auto-lswt",
            ],
        ), patch(
            "cli.write_results_bundle.write_results_bundle",
            return_value={"status": "ok"},
        ) as bundle_mock, patch(
            "builtins.print"
        ):
            exit_code = main()

        bundle_mock.assert_called_once()
        _payload_arg = bundle_mock.call_args.args[0]
        self.assertEqual(bundle_mock.call_args.kwargs["output_dir"], "/tmp/bundle-cli-out")
        self.assertFalse(bundle_mock.call_args.kwargs["run_missing_classical"])
        self.assertFalse(bundle_mock.call_args.kwargs["run_missing_thermodynamics"])
        self.assertFalse(bundle_mock.call_args.kwargs["run_missing_gswt"])
        self.assertFalse(bundle_mock.call_args.kwargs["run_missing_lswt"])
        self.assertEqual(exit_code, 0)
        payload_path.unlink(missing_ok=True)

    def test_documented_results_bundle_example_runs_without_lswt(self):
        example_path = (
            Path(__file__).resolve().parents[1] / "scripts" / "results_bundle_example.json"
        )
        payload = json.loads(example_path.read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = write_results_bundle(
                payload,
                output_dir=tmpdir,
                run_missing_lswt=False,
            )
            output_dir = Path(tmpdir)

            self.assertTrue((output_dir / "report.txt").exists())
            self.assertTrue((output_dir / "bundle_manifest.json").exists())

        self.assertEqual(manifest["status"], "partial")
        self.assertTrue(manifest["stages"]["classical"]["present"])
        self.assertTrue(manifest["stages"]["classical"]["auto_ran"])
        self.assertTrue(manifest["stages"]["thermodynamics"]["present"])
        self.assertTrue(manifest["stages"]["thermodynamics"]["auto_ran"])
        self.assertFalse(manifest["stages"]["gswt"]["present"])
        self.assertFalse(manifest["stages"]["gswt"]["auto_ran"])
        self.assertFalse(manifest["stages"]["lswt"]["present"])
        self.assertFalse(manifest["stages"]["lswt"]["auto_ran"])

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
            "thermodynamics": {"temperatures": [0.5, 1.0]},
        }

        solved_payload = {
            **payload,
            "gswt_payload": {
                "backend": "Sunny.jl",
                "mode": "SUN",
                "payload_kind": "sun_gswt_prototype",
                "local_dimension": 2,
                "orbital_count": 1,
                "pair_couplings": [{"R": [1, 0, 0], "pair_matrix": [], "tensor_shape": [2, 2, 2, 2]}],
                "initial_local_rays": [{"cell": [0, 0, 0], "vector": [{"real": 1.0, "imag": 0.0}]}],
                "supercell_shape": [1, 1, 1],
            },
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
        thermodynamics_result = {
            "grid": [
                {"temperature": 0.5, "energy": -1.0, "free_energy": -1.0, "specific_heat": 0.0, "magnetization": 1.0, "susceptibility": 0.0, "entropy": 0.0},
                {"temperature": 1.0, "energy": -0.8, "free_energy": -0.9, "specific_heat": 0.2, "magnetization": 0.5, "susceptibility": 0.1, "entropy": 0.1},
            ]
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
        gswt_result = {
            "status": "stub",
            "backend": {"name": "Sunny.jl", "mode": "SUN"},
            "payload_kind": "sun_gswt_prototype",
            "diagnostics": {"pair_coupling_count": 1, "local_dimension": 2, "ray_count": 1},
        }

        def fake_render_plots(bundle_payload, output_dir):
            self.assertIn("classical_state", bundle_payload)
            self.assertIn("gswt", bundle_payload)
            self.assertIn("lswt", bundle_payload)
            self.assertIn("thermodynamics_result", bundle_payload)
            self.assertEqual(bundle_payload["lswt"]["status"], "ok")
            return {"status": "ok", "plots": {"classical_state": {"status": "ok", "path": str(Path(output_dir) / "classical_state.png")}}}

        def fake_render_text(bundle_payload):
            self.assertIn("gswt", bundle_payload)
            self.assertIn("lswt", bundle_payload)
            self.assertIn("thermodynamics_result", bundle_payload)
            return "bundle report"

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "cli.write_results_bundle.run_classical_solver", return_value=solved_payload
        ) as classical_mock, patch(
            "cli.write_results_bundle.estimate_thermodynamics", return_value=thermodynamics_result
        ) as thermo_mock, patch(
            "cli.write_results_bundle.run_sun_gswt", return_value=gswt_result
        ) as gswt_mock, patch(
            "cli.write_results_bundle.run_linear_spin_wave", return_value=lswt_result
        ) as lswt_mock, patch(
            "cli.write_results_bundle.render_plots", side_effect=fake_render_plots
        ), patch(
            "cli.write_results_bundle.render_text", side_effect=fake_render_text
        ):
            manifest = write_results_bundle(payload, output_dir=tmpdir)
            output_dir = Path(tmpdir)
            self.assertTrue((output_dir / "report.txt").exists())
            self.assertTrue((output_dir / "bundle_manifest.json").exists())

        classical_mock.assert_called_once()
        thermo_mock.assert_called_once()
        gswt_mock.assert_called_once()
        lswt_mock.assert_called_once()
        self.assertEqual(manifest["status"], "ok")
        self.assertTrue(manifest["stages"]["classical"]["present"])
        self.assertTrue(manifest["stages"]["classical"]["auto_ran"])
        self.assertEqual(manifest["stages"]["classical"]["chosen_method"], "luttinger-tisza")
        self.assertTrue(manifest["stages"]["thermodynamics"]["present"])
        self.assertTrue(manifest["stages"]["thermodynamics"]["auto_ran"])
        self.assertTrue(manifest["stages"]["gswt"]["present"])
        self.assertTrue(manifest["stages"]["gswt"]["auto_ran"])
        self.assertEqual(manifest["stages"]["gswt"]["status"], "stub")
        self.assertEqual(manifest["stages"]["gswt"]["backend"], "Sunny.jl")
        self.assertTrue(manifest["stages"]["lswt"]["present"])
        self.assertTrue(manifest["stages"]["lswt"]["auto_ran"])
        self.assertEqual(manifest["stages"]["lswt"]["status"], "ok")
        self.assertEqual(manifest["stages"]["lswt"]["backend"], "Sunny.jl")

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
            "thermodynamics": {"temperatures": [0.5, 1.0]},
            "thermodynamics_result": {"grid": [{"temperature": 0.5, "energy": -1.0}]},
            "gswt_payload": {"payload_kind": "sun_gswt_prototype", "backend": "Sunny.jl"},
            "gswt": {
                "status": "stub",
                "backend": {"name": "Sunny.jl", "mode": "SUN"},
                "payload_kind": "sun_gswt_prototype",
            },
            "lswt": {
                "status": "ok",
                "backend": {"name": "Sunny.jl"},
                "path": {"labels": ["G", "X"], "node_indices": [0, 1]},
                "linear_spin_wave": {"dispersion": [{"q": [0.0, 0.0, 0.0], "omega": 0.0, "bands": [0.0]}]},
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "cli.write_results_bundle.run_classical_solver"
        ) as classical_mock, patch(
            "cli.write_results_bundle.estimate_thermodynamics"
        ) as thermo_mock, patch(
            "cli.write_results_bundle.run_sun_gswt"
        ) as gswt_mock, patch(
            "cli.write_results_bundle.run_linear_spin_wave"
        ) as lswt_mock, patch(
            "cli.write_results_bundle.render_plots",
            return_value={"status": "ok", "plots": {}},
        ), patch(
            "cli.write_results_bundle.render_text",
            return_value="bundle report",
        ):
            manifest = write_results_bundle(payload, output_dir=tmpdir)

        classical_mock.assert_not_called()
        thermo_mock.assert_not_called()
        gswt_mock.assert_not_called()
        lswt_mock.assert_not_called()
        self.assertEqual(manifest["status"], "ok")
        self.assertTrue(manifest["stages"]["classical"]["present"])
        self.assertFalse(manifest["stages"]["classical"]["auto_ran"])
        self.assertEqual(manifest["stages"]["classical"]["chosen_method"], "luttinger-tisza")
        self.assertTrue(manifest["stages"]["thermodynamics"]["present"])
        self.assertFalse(manifest["stages"]["thermodynamics"]["auto_ran"])
        self.assertTrue(manifest["stages"]["gswt"]["present"])
        self.assertFalse(manifest["stages"]["gswt"]["auto_ran"])
        self.assertEqual(manifest["stages"]["gswt"]["status"], "stub")
        self.assertTrue(manifest["stages"]["lswt"]["present"])
        self.assertFalse(manifest["stages"]["lswt"]["auto_ran"])
        self.assertEqual(manifest["stages"]["lswt"]["status"], "ok")

    def test_write_results_bundle_summarizes_thermodynamics_configuration_in_manifest(self):
        payload = {
            "model_name": "bundle-thermo-summary-demo",
            "normalized_model": {"local_hilbert": {"dimension": 4}},
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
            "classical": {"chosen_method": "sunny-cpn-minimize"},
            "thermodynamics": {
                "profile": "smoke",
                "backend_method": "sunny-local-sampler",
                "temperatures": [0.2, 0.4],
                "sweeps": 10,
                "burn_in": 5,
                "measurement_interval": 1,
                "proposal": "delta",
                "proposal_scale": 0.1,
            },
            "thermodynamics_result": {
                "backend": {"name": "Sunny.jl", "mode": "SUN", "sampler": "sunny-local-sampler"},
                "configuration": {
                    "profile": "smoke",
                    "backend_method": "sunny-local-sampler",
                    "temperatures": [0.2, 0.4],
                    "sweeps": 10,
                    "burn_in": 5,
                    "measurement_interval": 1,
                    "proposal": "delta",
                    "proposal_scale": 0.1,
                },
                "grid": [{"temperature": 0.2, "energy": -0.1}],
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "cli.write_results_bundle.render_plots",
            return_value={"status": "ok", "plots": {}},
        ), patch(
            "cli.write_results_bundle.render_text",
            return_value="bundle report",
        ):
            manifest = write_results_bundle(
                payload,
                output_dir=tmpdir,
                run_missing_classical=False,
                run_missing_thermodynamics=False,
                run_missing_gswt=False,
                run_missing_lswt=False,
            )

        self.assertTrue(manifest["stages"]["thermodynamics"]["present"])
        self.assertEqual(manifest["stages"]["thermodynamics"]["profile"], "smoke")
        self.assertEqual(manifest["stages"]["thermodynamics"]["backend_method"], "sunny-local-sampler")
        self.assertEqual(manifest["stages"]["thermodynamics"]["sweeps"], 10)
        self.assertEqual(manifest["stages"]["thermodynamics"]["burn_in"], 5)
        self.assertEqual(manifest["stages"]["thermodynamics"]["measurement_interval"], 1)

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
            "thermodynamics": {"temperatures": [0.5, 1.0]},
        }

        def fake_render_plots(bundle_payload, output_dir):
            self.assertNotIn("classical_state", bundle_payload)
            self.assertNotIn("lswt", bundle_payload)
            self.assertNotIn("thermodynamics_result", bundle_payload)
            return {"status": "partial", "plots": {}}

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "cli.write_results_bundle.run_classical_solver"
        ) as classical_mock, patch(
            "cli.write_results_bundle.estimate_thermodynamics"
        ) as thermo_mock, patch(
            "cli.write_results_bundle.run_sun_gswt"
        ) as gswt_mock, patch(
            "cli.write_results_bundle.run_linear_spin_wave"
        ) as lswt_mock, patch(
            "cli.write_results_bundle.render_plots", side_effect=fake_render_plots
        ), patch(
            "cli.write_results_bundle.render_text",
            return_value="bundle report",
        ):
            manifest = write_results_bundle(
                payload,
                output_dir=tmpdir,
                run_missing_classical=False,
                run_missing_thermodynamics=False,
                run_missing_gswt=False,
                run_missing_lswt=False,
            )

        classical_mock.assert_not_called()
        thermo_mock.assert_not_called()
        gswt_mock.assert_not_called()
        lswt_mock.assert_not_called()
        self.assertEqual(manifest["status"], "partial")
        self.assertFalse(manifest["stages"]["classical"]["present"])
        self.assertFalse(manifest["stages"]["classical"]["auto_ran"])
        self.assertFalse(manifest["stages"]["thermodynamics"]["present"])
        self.assertFalse(manifest["stages"]["thermodynamics"]["auto_ran"])
        self.assertFalse(manifest["stages"]["gswt"]["present"])
        self.assertFalse(manifest["stages"]["gswt"]["auto_ran"])
        self.assertFalse(manifest["stages"]["lswt"]["present"])
        self.assertFalse(manifest["stages"]["lswt"]["auto_ran"])

    def test_write_results_bundle_preserves_explicit_cpn_plot_skip_reason_in_manifest_and_report(self):
        payload = {
            "model_name": "bundle-cpn-demo",
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
                "chosen_method": "sunny-cpn-minimize",
                "classical_state": {
                    "schema_version": 1,
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "supercell_shape": [2, 1, 1],
                    "local_rays": [
                        {"cell": [0, 0, 0], "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}]},
                        {"cell": [1, 0, 0], "vector": [{"real": 0.0, "imag": 0.0}, {"real": 1.0, "imag": 0.0}]},
                    ],
                    "ordering": {
                        "ansatz": "single-q-unitary-ray",
                        "q_vector": [0.5, 0.0, 0.0],
                        "supercell_shape": [2, 1, 1],
                    },
                },
            },
            "plots": {},
        }

        def fake_render_plots(bundle_payload, output_dir):
            self.assertEqual(bundle_payload["classical"]["classical_state"]["state_kind"], "local_rays")
            return {
                "status": "partial",
                "plots": {
                    "classical_state": {
                        "status": "skipped",
                        "path": None,
                        "reason": "Classical-state plotting for CP^(N-1) local-ray states is not implemented yet",
                    },
                    "lswt_dispersion": {"status": "skipped", "path": None, "reason": "LSWT result unavailable"},
                    "thermodynamics": {"status": "skipped", "path": None, "reason": ""},
                    "lt_diagnostics": {"status": "skipped", "path": None, "reason": ""},
                },
            }

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "cli.write_results_bundle.render_plots",
            side_effect=fake_render_plots,
        ), patch(
            "cli.write_results_bundle.render_text",
            wraps=__import__("output.render_report", fromlist=["render_text"]).render_text,
        ):
            manifest = write_results_bundle(
                payload,
                output_dir=tmpdir,
                run_missing_classical=False,
                run_missing_thermodynamics=False,
                run_missing_gswt=False,
                run_missing_lswt=False,
            )
            report_text = (Path(tmpdir) / "report.txt").read_text(encoding="utf-8")

        self.assertEqual(manifest["status"], "partial")
        self.assertEqual(manifest["plots"]["plots"]["classical_state"]["status"], "skipped")
        self.assertIn("CP^(N-1)", manifest["plots"]["plots"]["classical_state"]["reason"])
        self.assertIn("classical_state: skipped", report_text)
        self.assertIn("CP^(N-1)", report_text)

    def test_write_results_bundle_does_not_auto_run_spin_lswt_for_cpn_local_rays(self):
        payload = {
            "model_name": "bundle-cpn-gswt-only-demo",
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
                "chosen_method": "sunny-cpn-minimize",
                "classical_state": {
                    "schema_version": 1,
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "supercell_shape": [2, 1, 1],
                    "local_rays": [
                        {"cell": [0, 0, 0], "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}]},
                        {"cell": [1, 0, 0], "vector": [{"real": 0.0, "imag": 0.0}, {"real": 1.0, "imag": 0.0}]},
                    ],
                    "ordering": {
                        "ansatz": "single-q-unitary-ray",
                        "q_vector": [0.5, 0.0, 0.0],
                        "supercell_shape": [2, 1, 1],
                    },
                },
            },
            "gswt_payload": {
                "payload_kind": "sun_gswt_prototype",
                "backend": "Sunny.jl",
                "classical_reference": {
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "frame_construction": "first-column-is-reference-ray",
                },
                "supercell_shape": [2, 1, 1],
                "initial_local_rays": [
                    {"cell": [0, 0, 0], "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}]},
                    {"cell": [1, 0, 0], "vector": [{"real": 0.0, "imag": 0.0}, {"real": 1.0, "imag": 0.0}]},
                ],
            },
        }
        gswt_result = {
            "status": "ok",
            "backend": {"name": "Sunny.jl", "mode": "SUN"},
            "payload_kind": "sun_gswt_prototype",
        }

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "cli.write_results_bundle.run_sun_gswt", return_value=gswt_result
        ) as gswt_mock, patch(
            "cli.write_results_bundle.run_linear_spin_wave"
        ) as lswt_mock, patch(
            "cli.write_results_bundle.render_plots",
            return_value={"status": "partial", "plots": {}},
        ), patch(
            "cli.write_results_bundle.render_text",
            return_value="bundle report",
        ):
            manifest = write_results_bundle(payload, output_dir=tmpdir)

        gswt_mock.assert_called_once()
        lswt_mock.assert_not_called()
        self.assertTrue(manifest["stages"]["gswt"]["present"])
        self.assertTrue(manifest["stages"]["gswt"]["auto_ran"])
        self.assertFalse(manifest["stages"]["lswt"]["present"])
        self.assertFalse(manifest["stages"]["lswt"]["auto_ran"])

    def test_write_results_bundle_dispatches_python_glswt_payload_to_python_driver(self):
        payload = {
            "model_name": "bundle-python-gswt-demo",
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
            "projection": {"status": "many_body_hr-pseudospin_orbital"},
            "classical": {
                "chosen_method": "sunny-cpn-minimize",
                "classical_state": {
                    "schema_version": 1,
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "basis_order": "orbital_major_spin_minor",
                    "pair_basis_order": "site_i_major_site_j_minor",
                    "supercell_shape": [1, 1, 1],
                    "local_rays": [
                        {"cell": [0, 0, 0], "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}]},
                    ],
                },
            },
            "classical_state": {
                "schema_version": 1,
                "state_kind": "local_rays",
                "manifold": "CP^(N-1)",
                "basis_order": "orbital_major_spin_minor",
                "pair_basis_order": "site_i_major_site_j_minor",
                "supercell_shape": [1, 1, 1],
                "local_rays": [
                    {"cell": [0, 0, 0], "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}]},
                ],
            },
            "gswt_payload": {
                "payload_kind": "python_glswt_local_rays",
                "backend": "python",
                "classical_reference": {
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "frame_construction": "first-column-is-reference-ray",
                },
                "supercell_shape": [1, 1, 1],
                "initial_local_rays": [
                    {"cell": [0, 0, 0], "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}]},
                ],
            },
        }
        gswt_result = {
            "status": "ok",
            "backend": {"name": "python-glswt"},
            "payload_kind": "python_glswt_local_rays",
        }

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "cli.write_results_bundle.run_python_glswt_driver", return_value=gswt_result
        ) as python_gswt_mock, patch(
            "cli.write_results_bundle.run_sun_gswt"
        ) as sunny_gswt_mock, patch(
            "cli.write_results_bundle.run_linear_spin_wave"
        ) as lswt_mock, patch(
            "cli.write_results_bundle.render_plots",
            return_value={"status": "partial", "plots": {}},
        ), patch(
            "cli.write_results_bundle.render_text",
            return_value="bundle report",
        ):
            manifest = write_results_bundle(payload, output_dir=tmpdir)

        python_gswt_mock.assert_called_once()
        sunny_gswt_mock.assert_not_called()
        lswt_mock.assert_not_called()
        self.assertTrue(manifest["stages"]["gswt"]["present"])
        self.assertTrue(manifest["stages"]["gswt"]["auto_ran"])
        self.assertEqual(manifest["stages"]["gswt"]["backend"], "python-glswt")

    def test_write_results_bundle_dispatches_single_q_python_glswt_payload_to_python_driver(self):
        payload = {
            "model_name": "bundle-python-single-q-gswt-demo",
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
            "projection": {"status": "many_body_hr-pseudospin_orbital"},
            "classical": {
                "chosen_method": "sun-gswt-single-q",
                "classical_state": {
                    "schema_version": 1,
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "basis_order": "orbital_major_spin_minor",
                    "pair_basis_order": "site_i_major_site_j_minor",
                    "supercell_shape": [5, 1, 1],
                    "local_rays": [
                        {"cell": [0, 0, 0], "vector": [{"real": 1.0, "imag": 0.0}, {"real": 1.0, "imag": 0.0}]},
                    ],
                },
            },
            "classical_state": {
                "schema_version": 1,
                "state_kind": "local_rays",
                "manifold": "CP^(N-1)",
                "basis_order": "orbital_major_spin_minor",
                "pair_basis_order": "site_i_major_site_j_minor",
                "supercell_shape": [5, 1, 1],
                "local_rays": [
                    {"cell": [0, 0, 0], "vector": [{"real": 1.0, "imag": 0.0}, {"real": 1.0, "imag": 0.0}]},
                ],
            },
            "gswt_payload": {
                "payload_kind": "python_glswt_single_q_z_harmonic",
                "backend": "python",
                "q_vector": [0.2, 0.0, 0.0],
                "z_harmonic_cutoff": 1,
                "z_harmonics": [
                    {
                        "harmonic": 0,
                        "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}],
                    }
                ],
                "phase_grid_size": 32,
                "sideband_cutoff": 2,
            },
        }
        gswt_result = {
            "status": "ok",
            "backend": {"name": "python-glswt"},
            "payload_kind": "python_glswt_single_q_z_harmonic",
        }

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "cli.write_results_bundle.run_python_glswt_driver", return_value=gswt_result
        ) as python_gswt_mock, patch(
            "cli.write_results_bundle.run_sun_gswt"
        ) as sunny_gswt_mock, patch(
            "cli.write_results_bundle.run_linear_spin_wave"
        ) as lswt_mock, patch(
            "cli.write_results_bundle.render_plots",
            return_value={"status": "partial", "plots": {}},
        ), patch(
            "cli.write_results_bundle.render_text",
            return_value="bundle report",
        ):
            manifest = write_results_bundle(payload, output_dir=tmpdir)

        python_gswt_mock.assert_called_once()
        sunny_gswt_mock.assert_not_called()
        lswt_mock.assert_not_called()
        self.assertTrue(manifest["stages"]["gswt"]["present"])
        self.assertTrue(manifest["stages"]["gswt"]["auto_ran"])
        self.assertEqual(manifest["stages"]["gswt"]["backend"], "python-glswt")

    def test_write_results_bundle_records_lswt_failure_interpretation_in_manifest(self):
        payload = {
            "model_name": "bundle-lswt-failure-demo",
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
            "lswt": {
                "status": "error",
                "backend": {"name": "Sunny.jl"},
                "path": {"labels": ["G", "X"]},
                "error": {
                    "code": "backend-execution-failed",
                    "message": "Instability at wavevector q = [0.0625, 0.0, 0.0]",
                },
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "cli.write_results_bundle.render_plots",
            return_value={"status": "partial", "plots": {}},
        ), patch(
            "cli.write_results_bundle.render_text",
            return_value="bundle report",
        ):
            manifest = write_results_bundle(
                payload,
                output_dir=tmpdir,
                run_missing_classical=False,
                run_missing_thermodynamics=False,
                run_missing_gswt=False,
                run_missing_lswt=False,
            )

        self.assertEqual(manifest["stages"]["lswt"]["status"], "error")
        self.assertIn("interpretation", manifest["stages"]["lswt"])
        self.assertIn("unstable", manifest["stages"]["lswt"]["interpretation"])
        self.assertIn("likely_cause", manifest["stages"]["lswt"])
        self.assertIn("stable expansion point", manifest["stages"]["lswt"]["likely_cause"])
        self.assertEqual(len(manifest["stages"]["lswt"]["next_steps"]), 3)


if __name__ == "__main__":
    unittest.main()
