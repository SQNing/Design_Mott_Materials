import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from identify_readable_blocks import identify_readable_blocks


class IdentifyReadableBlocksTests(unittest.TestCase):
    def test_identifies_isotropic_exchange_block(self):
        canonical = {
            "two_body": [
                {"canonical_label": "Sx@0 Sx@1", "coefficient": 1.0, "relative_weight": 1.0, "body_order": 2},
                {"canonical_label": "Sy@0 Sy@1", "coefficient": 1.0, "relative_weight": 1.0, "body_order": 2},
                {"canonical_label": "Sz@0 Sz@1", "coefficient": 1.0, "relative_weight": 1.0, "body_order": 2},
            ]
        }
        blocks = identify_readable_blocks(canonical)
        self.assertEqual(blocks["blocks"][0]["type"], "isotropic_exchange")

    def test_identifies_dm_like_block(self):
        canonical = {
            "two_body": [
                {"canonical_label": "Sx@0 Sy@1", "coefficient": 0.3, "relative_weight": 1.0, "body_order": 2},
                {"canonical_label": "Sy@0 Sx@1", "coefficient": -0.3, "relative_weight": 1.0, "body_order": 2},
            ]
        }
        blocks = identify_readable_blocks(canonical)
        self.assertEqual(blocks["blocks"][0]["type"], "dm_like")

    def test_identifies_scalar_chirality_block(self):
        canonical = {
            "three_body": [
                {"canonical_label": "Sx@0 Sy@1 Sz@2", "coefficient": 0.2, "relative_weight": 1.0, "body_order": 3},
            ]
        }
        blocks = identify_readable_blocks(canonical)
        self.assertEqual(blocks["blocks"][0]["type"], "scalar_chirality_like")

    def test_leaves_unmatched_terms_in_residual(self):
        canonical = {
            "four_body": [
                {"canonical_label": "Sx@0 Sy@1 Sz@2 Sx@3", "coefficient": 0.1, "relative_weight": 1.0, "body_order": 4},
            ]
        }
        blocks = identify_readable_blocks(canonical)
        self.assertEqual(blocks["blocks"], [])
        self.assertEqual(blocks["residual_terms"][0]["canonical_label"], "Sx@0 Sy@1 Sz@2 Sx@3")


if __name__ == "__main__":
    unittest.main()
