import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from decision_gates import classical_stage_decision
from build_lswt_payload import build_lswt_payload
from classical_solver_driver import run_classical_solver
from render_plots import _lt_diagnostic_summary, render_plots
from render_report import render_text


class LTPipelineIntegrationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
