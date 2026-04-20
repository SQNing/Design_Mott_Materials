import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from output import render_plots, render_report


class OutputClassicalContractRenderingTests(unittest.TestCase):
    def test_render_report_prefers_standardized_classical_metadata(self):
        payload = {
            "normalized_model": {"local_hilbert": {"dimension": 2}},
            "simplification": {
                "recommended": 0,
                "candidates": [{"name": "demo-candidate"}],
            },
            "effective_model": {"main": [], "low_weight": [], "residual": []},
            "fidelity": {"risk_notes": []},
            "projection": {"status": "many_body_hr-pseudospin_orbital"},
            "classical": {},
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "solver_family": "retained_local_multiplet",
                "method": "pseudospin-cpn-local-ray-minimize",
                "downstream_compatibility": {
                    "lswt": {"status": "blocked", "reason": "requires-spin-frame-site-frames"},
                    "gswt": {"status": "ready"},
                    "thermodynamics": {"status": "ready"},
                },
                "classical_state": {
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "supercell_shape": [1, 1, 1],
                    "local_rays": [
                        {
                            "cell": [0, 0, 0],
                            "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}],
                        }
                    ],
                },
            },
        }

        report = render_report.render_text(payload)

        self.assertIn("Chosen classical method: pseudospin-cpn-local-ray-minimize", report)
        self.assertIn("Classical solver role: final", report)
        self.assertIn("Classical solver family: retained_local_multiplet", report)
        self.assertIn("Classical downstream compatibility:", report)
        self.assertIn("gswt=ready", report)

    def test_render_plots_get_classical_state_accepts_standardized_result_wrapper(self):
        payload = {
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "classical_state": {
                    "site_frames": [
                        {
                            "site": 0,
                            "spin_length": 0.5,
                            "direction": [0.0, 0.0, 1.0],
                        }
                    ],
                    "ordering": {"kind": "commensurate"},
                },
            }
        }

        classical_state = render_plots._get_classical_state(payload)

        self.assertEqual(len(classical_state["site_frames"]), 1)
        self.assertEqual(classical_state["ordering"]["kind"], "commensurate")

    def test_render_plots_summary_prefers_standardized_method_role_and_family(self):
        payload = {
            "classical": {"chosen_method": "legacy-method"},
            "classical_state_result": {
                "status": "ok",
                "role": "diagnostic",
                "solver_family": "diagnostic_seed_only",
                "method": "pseudospin-cpn-generalized-lt",
            },
        }
        classical_state = {
            "render_mode": "structure",
            "spatial_dimension": 2,
            "state_kind": "local_rays",
            "manifold": "CP^(N-1)",
        }

        lines = render_plots._classical_summary_lines(payload, classical_state)

        self.assertIn("method=pseudospin-cpn-generalized-lt", lines[0])
        self.assertIn("role=diagnostic", lines[0])
        self.assertIn("solver_family=diagnostic_seed_only", lines[0])

    def test_plot_payload_metadata_prefers_standardized_classical_method(self):
        payload = {
            "classical": {"chosen_method": "legacy-method"},
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "method": "spin-only-variational",
            },
            "lswt": {"status": "ok", "backend": {"name": "Sunny.jl"}, "linear_spin_wave": {"dispersion": []}},
            "gswt": {},
        }

        with patch.object(render_plots, "_build_classical_plot_state", return_value={"site_frames": []}):
            plot_payload = render_plots._build_plot_payload(payload)

        self.assertEqual(plot_payload["metadata"]["classical_method"], "spin-only-variational")


if __name__ == "__main__":
    unittest.main()
