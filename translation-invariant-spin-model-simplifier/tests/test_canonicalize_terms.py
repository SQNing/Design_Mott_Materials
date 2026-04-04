import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from canonicalize_terms import canonicalize_terms


class CanonicalizeTermsTests(unittest.TestCase):
    def test_groups_terms_by_body_order(self):
        model = {
            "decomposition": {
                "terms": [
                    {"label": "Sz@0", "coefficient": 0.3},
                    {"label": "Sx@0 Sx@1", "coefficient": 1.0},
                    {"label": "Sx@0 Sy@1 Sz@2", "coefficient": 0.2},
                    {"label": "Sx@0 Sy@1 Sz@2 Sx@3", "coefficient": 0.1},
                ]
            }
        }
        canonical = canonicalize_terms(model)
        self.assertEqual(len(canonical["one_body"]), 1)
        self.assertEqual(len(canonical["two_body"]), 1)
        self.assertEqual(len(canonical["three_body"]), 1)
        self.assertEqual(len(canonical["four_body"]), 1)

    def test_merges_equivalent_labels_after_support_normalization(self):
        model = {
            "decomposition": {
                "terms": [
                    {"label": "Sx@1 Sx@0", "coefficient": 1.0},
                    {"label": "Sx@0 Sx@1", "coefficient": 0.5},
                ]
            }
        }
        canonical = canonicalize_terms(model)
        self.assertEqual(len(canonical["two_body"]), 1)
        self.assertEqual(canonical["two_body"][0]["canonical_label"], "Sx@0 Sx@1")
        self.assertAlmostEqual(canonical["two_body"][0]["coefficient"], 1.5)

    def test_computes_relative_weight_within_body_order_family(self):
        model = {
            "decomposition": {
                "terms": [
                    {"label": "Sx@0 Sx@1", "coefficient": 2.0},
                    {"label": "Sz@0 Sz@1", "coefficient": 0.5},
                ]
            }
        }
        canonical = canonicalize_terms(model)
        weights = {term["canonical_label"]: term["relative_weight"] for term in canonical["two_body"]}
        self.assertEqual(weights["Sx@0 Sx@1"], 1.0)
        self.assertEqual(weights["Sz@0 Sz@1"], 0.25)


if __name__ == "__main__":
    unittest.main()
