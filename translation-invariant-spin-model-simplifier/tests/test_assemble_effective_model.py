import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from assemble_effective_model import assemble_effective_model


class AssembleEffectiveModelTests(unittest.TestCase):
    def test_places_readable_blocks_in_main(self):
        readable = {
            "blocks": [{"type": "isotropic_exchange", "coefficient": 1.0, "source_terms": []}],
            "residual_terms": [],
        }
        assembled = assemble_effective_model(readable, low_weight_threshold=0.2)
        self.assertEqual(len(assembled["main"]), 1)
        self.assertEqual(assembled["main"][0]["type"], "isotropic_exchange")

    def test_low_weight_terms_are_flagged_not_dropped(self):
        readable = {
            "blocks": [],
            "residual_terms": [
                {
                    "canonical_label": "Sz@0",
                    "coefficient": 0.05,
                    "relative_weight": 0.05,
                    "body_order": 1,
                    "symmetry_annotations": [],
                }
            ],
        }
        assembled = assemble_effective_model(readable, low_weight_threshold=0.1)
        self.assertEqual(len(assembled["low_weight"]), 1)
        self.assertEqual(assembled["residual"], [])

    def test_symmetry_breaking_low_weight_term_gets_warning(self):
        readable = {
            "blocks": [],
            "residual_terms": [
                {
                    "canonical_label": "Sz@0",
                    "coefficient": 0.05,
                    "relative_weight": 0.05,
                    "body_order": 1,
                    "symmetry_annotations": ["breaks_time_reversal"],
                }
            ],
        }
        assembled = assemble_effective_model(readable, low_weight_threshold=0.1)
        self.assertIn("warning", assembled["low_weight"][0])


if __name__ == "__main__":
    unittest.main()
