import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from output.render_report import render_text


class RenderReportTests(unittest.TestCase):
    def test_render_text_includes_gswt_classical_reference_and_ordering_summary(self):
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
            "classical": {"chosen_method": "sunny-cpn-minimize"},
            "gswt": {
                "status": "ok",
                "backend": {"name": "Sunny.jl", "mode": "SUN"},
                "payload_kind": "sun_gswt_prototype",
                "classical_reference": {
                    "schema_version": 1,
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "frame_construction": "first-column-is-reference-ray",
                },
                "ordering": {
                    "ansatz": "single-q-unitary-ray",
                    "q_vector": [0.5, 0.0, 0.0],
                    "supercell_shape": [2, 1, 1],
                    "compatibility_with_supercell": {"kind": "commensurate"},
                },
            },
            "lswt": {"status": "skipped", "error": {"code": "missing", "message": "unavailable"}},
        }

        text = render_text(payload)

        self.assertIn("GSWT backend: Sunny.jl", text)
        self.assertIn("GSWT status: ok", text)
        self.assertIn("GSWT reference state: local_rays", text)
        self.assertIn("manifold=CP^(N-1)", text)
        self.assertIn("frame=first-column-is-reference-ray", text)
        self.assertIn("GSWT ordering: ansatz=single-q-unitary-ray", text)
        self.assertIn("q_vector=[0.5, 0.0, 0.0]", text)
        self.assertIn("compatibility=commensurate", text)


if __name__ == "__main__":
    unittest.main()
