import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from decision_gates import classical_stage_decision
from build_lswt_payload import build_lswt_payload
from classical_solver_driver import run_classical_solver
from linear_spin_wave_driver import run_linear_spin_wave
from render_plots import _auto_resolution_summary, _lt_diagnostic_summary, render_plots
from render_report import render_text


class LTPipelineIntegrationTests(unittest.TestCase):
    @staticmethod
    def _dummy_lt_result():
        return {
            "q": [0.5, 0.0, 0.0],
            "lowest_eigenvalue": -2.0,
            "matrix_size": 2,
            "eigenvector": [
                {"real": 1.0, "imag": 0.0},
                {"real": 0.0, "imag": 0.0},
            ],
        }

    @staticmethod
    def _dummy_generalized_lt_result():
        return {
            "lambda": [0.2, -0.2],
            "tightened_lower_bound": -1.6,
            "q": [0.5, 0.0, 0.0],
            "eigenspace": [
                [
                    {"real": 1.0, "imag": 0.0},
                    {"real": 0.0, "imag": 0.0},
                ]
            ],
        }

    @staticmethod
    def _dummy_variational_result():
        return {"method": "variational", "energy": -1.0, "spins": [[0.0, 0.0, 1.0], [0.0, 0.0, 1.0]]}

    @staticmethod
    def _fake_classical_state(source, residual, q_vector):
        return {
            "site_frames": [
                {"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]},
                {"site": 1, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]},
            ],
            "ordering": {"kind": "commensurate", "q_vector": list(q_vector)},
            "constraint_recovery": {
                "source": source,
                "reconstruction": "single-q",
                "strong_constraint_residual": residual,
                "site_norms": [1.0, 1.0],
            },
        }

    def test_classical_stage_decision_offers_lt_and_generalized_lt_options(self):
        model = {
            "lattice": {"sublattices": 2},
            "simplified_model": {"template": "heisenberg"},
        }

        result = classical_stage_decision(model, user_choice=None, timed_out=False, allow_auto_select=False)

        self.assertEqual(result["status"], "needs_input")
        self.assertIn("luttinger-tisza", result["question"]["options"])
        self.assertIn("generalized-lt", result["question"]["options"])
        self.assertIn("variational", result["question"]["options"])

    def test_render_report_includes_lt_and_generalized_lt_diagnostics(self):
        payload = {
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
            "classical": {"chosen_method": "generalized-lt"},
            "lt_result": {
                "q": [0.5, 0.0, 0.0],
                "lowest_eigenvalue": -2.0,
                "matrix_size": 2,
                "constraint_recovery": {"strong_constraint_residual": 0.125},
            },
            "generalized_lt_result": {
                "lambda": [0.2, -0.2],
                "tightened_lower_bound": -1.6,
                "q": [0.5, 0.0, 0.0],
                "constraint_recovery": {"strong_constraint_residual": 0.0625},
            },
            "linear_spin_wave": {"dispersion": []},
        }

        text = render_text(payload)

        self.assertIn("Luttinger-Tisza diagnostics", text)
        self.assertIn("best_q=[0.5, 0.0, 0.0]", text)
        self.assertIn("lowest_eigenvalue=-2.0", text)
        self.assertIn("strong_constraint_residual=0.125", text)
        self.assertIn("Generalized LT diagnostics", text)
        self.assertIn("lambda=[0.2, -0.2]", text)
        self.assertIn("tightened_lower_bound=-1.6", text)
        self.assertIn("strong_constraint_residual=0.0625", text)

    def test_render_report_includes_auto_resolution_details_when_present(self):
        payload = {
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
                "requested_method": "auto",
                "chosen_method": "generalized-lt",
                "auto_resolution": {
                    "enabled": True,
                    "recommended_method": "luttinger-tisza",
                    "initial_method": "luttinger-tisza",
                    "resolved_method": "generalized-lt",
                    "reason": "generalized-lt-improved-residual",
                    "lt_residual": 0.6,
                    "generalized_lt_residual": 0.1,
                },
            },
            "linear_spin_wave": {"dispersion": []},
        }

        text = render_text(payload)

        self.assertIn("Classical auto-resolution:", text)
        self.assertIn("requested=auto", text)
        self.assertIn("recommended=luttinger-tisza", text)
        self.assertIn("resolved=generalized-lt", text)
        self.assertIn("reason=generalized-lt-improved-residual", text)
        self.assertIn("lt_residual=0.6", text)
        self.assertIn("generalized_lt_residual=0.1", text)

    def test_render_report_reads_nested_lswt_dispersion_and_path_metadata(self):
        payload = {
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
            "classical": {"chosen_method": "luttinger-tisza"},
            "lswt": {
                "status": "ok",
                "backend": {"name": "Sunny.jl"},
                "path": {"labels": ["G", "X"], "node_indices": [0, 1]},
                "linear_spin_wave": {
                    "dispersion": [
                        {"q": [0.0, 0.0, 0.0], "omega": 0.0, "bands": [0.0]},
                        {"q": [0.5, 0.0, 0.0], "omega": 1.0, "bands": [1.0]},
                    ]
                },
            },
        }

        text = render_text(payload)

        self.assertIn("LSWT backend: Sunny.jl", text)
        self.assertIn("LSWT path labels: ['G', 'X']", text)
        self.assertIn("q=[0.5, 0.0, 0.0] omega=1.0", text)

    def test_render_report_includes_nested_lswt_error_summary(self):
        payload = {
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
            "classical": {"chosen_method": "luttinger-tisza"},
            "lswt": {
                "status": "error",
                "backend": {"name": "Sunny.jl"},
                "path": {"labels": ["G", "X"], "node_indices": [0, 1]},
                "linear_spin_wave": {},
                "error": {"code": "missing-sunny-package", "message": "Sunny.jl is unavailable"},
            },
        }

        text = render_text(payload)

        self.assertIn("LSWT backend: Sunny.jl", text)
        self.assertIn("LSWT status: error", text)
        self.assertIn("LSWT error: missing-sunny-package Sunny.jl is unavailable", text)
        self.assertIn("Linear spin-wave points: unavailable", text)

    def test_lt_diagnostic_summary_includes_constraint_recovery_when_available(self):
        summary = _lt_diagnostic_summary(
            {
                "q": [0.5, 0.0, 0.0],
                "lowest_eigenvalue": -2.0,
                "constraint_recovery": {"strong_constraint_residual": 0.125},
            },
            label_value_pairs=[("lambda_min", -2.0)],
        )

        self.assertIn("q = [0.5, 0.0, 0.0]", summary)
        self.assertIn("lambda_min = -2.0", summary)
        self.assertIn("residual = 0.125", summary)

    def test_auto_resolution_summary_includes_reason_and_residuals(self):
        summary = _auto_resolution_summary(
            {
                "enabled": True,
                "recommended_method": "luttinger-tisza",
                "initial_method": "luttinger-tisza",
                "resolved_method": "generalized-lt",
                "reason": "generalized-lt-improved-residual",
                "lt_residual": 0.6,
                "generalized_lt_residual": 0.1,
            }
        )

        self.assertIn("recommended = luttinger-tisza", summary)
        self.assertIn("initial = luttinger-tisza", summary)
        self.assertIn("resolved = generalized-lt", summary)
        self.assertIn("reason = generalized-lt-improved-residual", summary)
        self.assertIn("lt_residual = 0.6", summary)
        self.assertIn("generalized_lt_residual = 0.1", summary)

    def test_render_plots_writes_lt_diagnostics_plot_when_lt_results_are_present(self):
        payload = {
            "model_name": "lt-diagnostics-demo",
            "classical": {
                "chosen_method": "generalized-lt",
                "classical_state": {
                    "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}],
                    "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                },
            },
            "lt_result": {
                "q": [0.5, 0.0, 0.0],
                "lowest_eigenvalue": -2.0,
                "matrix_size": 2,
                "eigenvector": [
                    [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}],
                    [{"real": 0.2, "imag": 0.0}, {"real": 0.0, "imag": 0.0}],
                ],
            },
            "generalized_lt_result": {
                "lambda": [0.2, -0.2],
                "tightened_lower_bound": -1.6,
                "q": [0.5, 0.0, 0.0],
            },
            "lswt": {"status": "error", "backend": {"name": "Sunny.jl"}, "error": {"code": "missing", "message": "x"}},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = render_plots(payload, output_dir=tmpdir)
            output_dir = Path(tmpdir)
            self.assertEqual(result["plots"]["lt_diagnostics"]["status"], "ok")
            self.assertTrue((output_dir / "lt_diagnostics.png").exists())

    def test_run_classical_solver_attaches_lt_result_when_requested(self):
        payload = {
            "lattice": {"kind": "chain", "dimension": 1, "sublattices": 1},
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

        result = run_classical_solver(payload, starts=4, seed=1)

        self.assertIn("lt_result", result)
        self.assertNotIn("generalized_lt_result", result)
        self.assertIn("variational_result", result)

    def test_run_classical_solver_attaches_generalized_lt_result_when_requested(self):
        payload = {
            "lattice": {"kind": "chain", "dimension": 1, "sublattices": 2},
            "bonds": [
                {
                    "source": 0,
                    "target": 1,
                    "vector": [1, 0, 0],
                    "matrix": [
                        [1.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0],
                        [0.0, 0.0, 1.0],
                    ],
                }
            ],
            "classical": {"method": "generalized-lt"},
        }

        result = run_classical_solver(payload, starts=4, seed=1)

        self.assertIn("generalized_lt_result", result)
        self.assertIn("lt_result", result)
        self.assertIn("variational_result", result)

    def test_run_classical_solver_recovers_classical_state_from_lt_output(self):
        payload = {
            "normalized_model": {"local_hilbert": {"dimension": 2}},
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "sublattices": 1,
                "positions": [[0.0, 0.0, 0.0]],
            },
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

        result = run_classical_solver(payload, starts=4, seed=1)

        self.assertIn("classical_state", result)
        self.assertIn("classical_state", result["classical"])
        self.assertEqual(result["classical"]["classical_state"], result["classical_state"])
        self.assertEqual(len(result["classical_state"]["site_frames"]), 1)
        self.assertAlmostEqual(result["classical_state"]["site_frames"][0]["spin_length"], 0.5, places=6)
        self.assertAlmostEqual(
            result["classical_state"]["ordering"]["q_vector"][0],
            result["lt_result"]["q"][0],
            places=6,
        )
        self.assertIn("constraint_recovery", result["lt_result"])

    def test_generalized_lt_pipeline_output_can_feed_lswt_payload_builder(self):
        payload = {
            "normalized_model": {"local_hilbert": {"dimension": 2}},
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "sublattices": 2,
                "positions": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
            },
            "simplified_model": {
                "template": "heisenberg",
                "bonds": [
                    {
                        "source": 0,
                        "target": 1,
                        "vector": [1, 0, 0],
                        "matrix": [
                            [1.0, 0.0, 0.0],
                            [0.0, 1.0, 0.0],
                            [0.0, 0.0, 1.0],
                        ],
                    }
                ],
            },
            "bonds": [
                {
                    "source": 0,
                    "target": 1,
                    "vector": [1, 0, 0],
                    "matrix": [
                        [1.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0],
                        [0.0, 0.0, 1.0],
                    ],
                }
            ],
            "classical": {"method": "generalized-lt"},
        }

        solved = run_classical_solver(payload, starts=4, seed=1)
        lswt_payload = build_lswt_payload(solved)

        self.assertEqual(lswt_payload["status"], "ok")
        self.assertEqual(len(lswt_payload["payload"]["reference_frames"]), 2)
        self.assertEqual(
            lswt_payload["payload"]["ordering"]["q_vector"],
            solved["classical"]["classical_state"]["ordering"]["q_vector"],
        )

    def test_run_classical_solver_auto_accepts_lt_when_lt_residual_is_small(self):
        payload = {
            "recommended_method": "luttinger-tisza",
            "lattice": {"kind": "chain", "dimension": 1, "sublattices": 2},
            "bonds": [{"source": 0, "target": 1, "vector": [1, 0, 0], "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]}],
            "classical": {"method": "auto"},
        }

        with patch("classical_solver_driver.find_lt_ground_state", return_value=self._dummy_lt_result()), patch(
            "classical_solver_driver.find_generalized_lt_ground_state",
            return_value=self._dummy_generalized_lt_result(),
        ) as generalized_mock, patch(
            "classical_solver_driver.solve_variational",
            return_value=self._dummy_variational_result(),
        ), patch(
            "classical_solver_driver.recover_classical_state_from_lt",
            return_value=self._fake_classical_state("lt", 0.0, [0.5, 0.0, 0.0]),
        ):
            result = run_classical_solver(payload, starts=4, seed=1)

        self.assertEqual(result["classical"]["requested_method"], "auto")
        self.assertEqual(result["classical"]["chosen_method"], "luttinger-tisza")
        self.assertTrue(result["classical"]["auto_resolution"]["enabled"])
        self.assertEqual(result["classical"]["auto_resolution"]["resolved_method"], "luttinger-tisza")
        generalized_mock.assert_not_called()

    def test_run_classical_solver_auto_upgrades_to_generalized_lt_when_it_improves_residual(self):
        payload = {
            "recommended_method": "luttinger-tisza",
            "lattice": {"kind": "chain", "dimension": 1, "sublattices": 2},
            "bonds": [{"source": 0, "target": 1, "vector": [1, 0, 0], "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]}],
            "classical": {"method": "auto"},
        }

        def fake_recover(_model, q, amplitudes, spin_length=0.5, source="lt"):
            residual = 0.6 if source == "lt" else 0.1
            return self._fake_classical_state(source, residual, q)

        with patch("classical_solver_driver.find_lt_ground_state", return_value=self._dummy_lt_result()), patch(
            "classical_solver_driver.find_generalized_lt_ground_state",
            return_value=self._dummy_generalized_lt_result(),
        ), patch(
            "classical_solver_driver.solve_variational",
            return_value=self._dummy_variational_result(),
        ), patch(
            "classical_solver_driver.recover_classical_state_from_lt",
            side_effect=fake_recover,
        ):
            result = run_classical_solver(payload, starts=4, seed=1)

        self.assertEqual(result["classical"]["chosen_method"], "generalized-lt")
        self.assertEqual(result["classical"]["auto_resolution"]["resolved_method"], "generalized-lt")
        self.assertAlmostEqual(result["classical"]["auto_resolution"]["lt_residual"], 0.6, places=6)
        self.assertAlmostEqual(result["classical"]["auto_resolution"]["generalized_lt_residual"], 0.1, places=6)
        self.assertEqual(result["classical_state"]["constraint_recovery"]["source"], "generalized-lt")

    def test_run_classical_solver_auto_falls_back_to_variational_when_generalized_lt_does_not_help(self):
        payload = {
            "recommended_method": "luttinger-tisza",
            "lattice": {"kind": "chain", "dimension": 1, "sublattices": 2},
            "bonds": [{"source": 0, "target": 1, "vector": [1, 0, 0], "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]}],
            "classical": {"method": "auto"},
        }

        def fake_recover(_model, q, amplitudes, spin_length=0.5, source="lt"):
            residual = 0.6 if source == "lt" else 0.59
            return self._fake_classical_state(source, residual, q)

        with patch("classical_solver_driver.find_lt_ground_state", return_value=self._dummy_lt_result()), patch(
            "classical_solver_driver.find_generalized_lt_ground_state",
            return_value=self._dummy_generalized_lt_result(),
        ), patch(
            "classical_solver_driver.solve_variational",
            return_value=self._dummy_variational_result(),
        ), patch(
            "classical_solver_driver.recover_classical_state_from_lt",
            side_effect=fake_recover,
        ):
            result = run_classical_solver(payload, starts=4, seed=1)

        self.assertEqual(result["classical"]["chosen_method"], "variational")
        self.assertEqual(result["classical"]["auto_resolution"]["resolved_method"], "variational")
        self.assertEqual(result["classical_state"]["constraint_recovery"]["source"], "variational")

    def test_run_classical_solver_keeps_explicit_lt_choice_even_when_residual_is_large(self):
        payload = {
            "lattice": {"kind": "chain", "dimension": 1, "sublattices": 2},
            "bonds": [{"source": 0, "target": 1, "vector": [1, 0, 0], "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]}],
            "classical": {"method": "luttinger-tisza"},
        }

        with patch("classical_solver_driver.find_lt_ground_state", return_value=self._dummy_lt_result()), patch(
            "classical_solver_driver.find_generalized_lt_ground_state",
            return_value=self._dummy_generalized_lt_result(),
        ) as generalized_mock, patch(
            "classical_solver_driver.solve_variational",
            return_value=self._dummy_variational_result(),
        ), patch(
            "classical_solver_driver.recover_classical_state_from_lt",
            return_value=self._fake_classical_state("lt", 1.0, [0.5, 0.0, 0.0]),
        ):
            result = run_classical_solver(payload, starts=4, seed=1)

        self.assertEqual(result["classical"]["requested_method"], "luttinger-tisza")
        self.assertEqual(result["classical"]["chosen_method"], "luttinger-tisza")
        self.assertFalse(result["classical"]["auto_resolution"]["enabled"])
        generalized_mock.assert_not_called()

    def test_end_to_end_auto_classical_to_lswt_to_plots_and_report(self):
        payload = {
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
            "recommended_method": "luttinger-tisza",
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "sublattices": 2,
                "positions": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
            },
            "simplified_model": {
                "template": "heisenberg",
                "bonds": [
                    {
                        "source": 0,
                        "target": 1,
                        "vector": [1, 0, 0],
                        "matrix": [
                            [1.0, 0.0, 0.0],
                            [0.0, 1.0, 0.0],
                            [0.0, 0.0, 1.0],
                        ],
                    }
                ],
            },
            "bonds": [
                {
                    "source": 0,
                    "target": 1,
                    "vector": [1, 0, 0],
                    "matrix": [
                        [1.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0],
                        [0.0, 0.0, 1.0],
                    ],
                }
            ],
            "classical": {"method": "auto"},
            "q_path": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
            "q_samples": 4,
        }

        def fake_recover(_model, q, amplitudes, spin_length=0.5, source="lt"):
            residual = 0.6 if source == "lt" else 0.1
            return self._fake_classical_state(source, residual, q)

        def fake_backend(command, check, capture_output, text):
            class Completed:
                stdout = json.dumps(
                    {
                        "status": "ok",
                        "backend": {"name": "Sunny.jl"},
                        "linear_spin_wave": {
                            "dispersion": [
                                {"q": [0.0, 0.0, 0.0], "omega": 0.0, "bands": [0.0]},
                                {"q": [0.5, 0.0, 0.0], "omega": 1.0, "bands": [1.0]},
                            ]
                        },
                    }
                )

            return Completed()

        with patch("classical_solver_driver.find_lt_ground_state", return_value=self._dummy_lt_result()), patch(
            "classical_solver_driver.find_generalized_lt_ground_state",
            return_value=self._dummy_generalized_lt_result(),
        ), patch(
            "classical_solver_driver.solve_variational",
            return_value=self._dummy_variational_result(),
        ), patch(
            "classical_solver_driver.recover_classical_state_from_lt",
            side_effect=fake_recover,
        ), patch(
            "linear_spin_wave_driver.subprocess.run",
            side_effect=fake_backend,
        ):
            solved = run_classical_solver(payload, starts=4, seed=1)
            lswt_result = run_linear_spin_wave(solved)

        solved["lswt"] = lswt_result
        text = render_text(solved)

        with tempfile.TemporaryDirectory() as tmpdir:
            plot_result = render_plots(solved, output_dir=tmpdir)
            output_dir = Path(tmpdir)
            self.assertEqual(plot_result["plots"]["lswt_dispersion"]["status"], "ok")
            self.assertTrue((output_dir / "lswt_dispersion.png").exists())

        self.assertEqual(solved["classical"]["chosen_method"], "generalized-lt")
        self.assertEqual(lswt_result["path"]["labels"], ["G", "X"])
        self.assertIn("resolved=generalized-lt", text)
        self.assertIn("LSWT path labels: ['G', 'X']", text)
        self.assertIn("q=[0.5, 0.0, 0.0] omega=1.0", text)

    def test_end_to_end_backend_error_payload_skips_lswt_plot_and_surfaces_report_error(self):
        payload = {
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
            "recommended_method": "luttinger-tisza",
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "sublattices": 1,
                "positions": [[0.0, 0.0, 0.0]],
            },
            "simplified_model": {
                "template": "heisenberg",
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
            },
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
            "q_path": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
            "q_samples": 4,
        }

        def fake_backend(command, check, capture_output, text):
            class Completed:
                stdout = json.dumps(
                    {
                        "status": "error",
                        "backend": {"name": "Sunny.jl"},
                        "linear_spin_wave": {},
                        "error": {"code": "missing-sunny-package", "message": "Sunny.jl is unavailable"},
                    }
                )

            return Completed()

        with patch("linear_spin_wave_driver.subprocess.run", side_effect=fake_backend):
            solved = run_classical_solver(payload, starts=4, seed=1)
            lswt_result = run_linear_spin_wave(solved)

        solved["lswt"] = lswt_result
        text = render_text(solved)

        with tempfile.TemporaryDirectory() as tmpdir:
            plot_result = render_plots(solved, output_dir=tmpdir)
            self.assertEqual(plot_result["status"], "partial")
            self.assertEqual(plot_result["plots"]["classical_state"]["status"], "ok")
            self.assertEqual(plot_result["plots"]["lswt_dispersion"]["status"], "skipped")
            self.assertIn("missing-sunny-package", plot_result["plots"]["lswt_dispersion"]["reason"])

        self.assertEqual(lswt_result["status"], "error")
        self.assertIn("LSWT status: error", text)
        self.assertIn("LSWT error: missing-sunny-package Sunny.jl is unavailable", text)


if __name__ == "__main__":
    unittest.main()
