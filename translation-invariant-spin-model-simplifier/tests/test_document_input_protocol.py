import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from input.document_input_protocol import (
    build_intermediate_record,
    detect_input_kind,
    land_intermediate_record,
)


class DocumentInputProtocolTests(unittest.TestCase):
    def test_detect_input_kind_marks_tex_documents(self):
        result = detect_input_kind(
            source_text="\\section*{Effective Hamiltonian}\n\\begin{equation}H=...",
        )

        self.assertEqual(result["source_kind"], "tex_document")

    def test_extract_intermediate_record_separates_multiple_model_candidates(self):
        fixture = (SKILL_ROOT / "tests" / "data" / "fei2_document_input.tex").read_text(encoding="utf-8")

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/fei2_document_input.tex",
        )

        self.assertEqual(
            [candidate["name"] for candidate in record["model_candidates"]],
            ["toy", "effective", "matrix_form"],
        )
        self.assertTrue(record["ambiguities"])

    def test_land_selected_candidate_to_payload_preserves_unsupported_features(self):
        record = {
            "source_document": {"source_kind": "tex_document"},
            "selected_model_candidate": "effective",
            "model_candidates": [
                {"name": "effective", "role": "main"},
            ],
            "hamiltonian_model": {
                "operator_expression": "J * Sz@0 Sz@1 - D * Sz@0 Sz@0",
            },
            "parameter_registry": {"J": -0.236, "D": 2.165},
            "ambiguities": [],
            "unsupported_features": ["matrix_form_metadata"],
        }

        landed = land_intermediate_record(record)

        self.assertEqual(landed["representation"], "operator")
        self.assertIn("unsupported_features", landed)
        self.assertIn("matrix_form_metadata", landed["unsupported_features"])

    def test_fei2_style_fixture_requires_model_selection_before_landing(self):
        fixture = (SKILL_ROOT / "tests" / "data" / "fei2_document_input.tex").read_text(encoding="utf-8")

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/fei2_document_input.tex",
        )
        landed = land_intermediate_record(record)

        self.assertEqual(landed["interaction"]["status"], "needs_input")
        self.assertEqual(landed["interaction"]["id"], "model_candidate_selection")


if __name__ == "__main__":
    unittest.main()
