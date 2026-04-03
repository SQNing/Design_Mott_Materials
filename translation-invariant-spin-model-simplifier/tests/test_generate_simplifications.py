import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from generate_simplifications import generate_candidates


def _template_for_terms(terms):
    summary = generate_candidates({"decomposition": {"terms": terms}}, relative_threshold=0.05)
    return summary["candidates"][2]["template"]


class GenerateSimplificationsTests(unittest.TestCase):
    def test_template_mapping_labels_heisenberg_when_all_components_match(self):
        template = _template_for_terms(
            [
                {"label": "Sx@0 Sx@1", "coefficient": 1.0},
                {"label": "Sy@0 Sy@1", "coefficient": 1.0},
                {"label": "Sz@0 Sz@1", "coefficient": 1.0},
            ]
        )
        self.assertEqual(template, "heisenberg")

    def test_template_mapping_labels_xxz_when_exactly_two_components_match(self):
        template = _template_for_terms(
            [
                {"label": "Sx@0 Sx@1", "coefficient": 1.0},
                {"label": "Sy@0 Sy@1", "coefficient": 1.0},
                {"label": "Sz@0 Sz@1", "coefficient": 1.4},
            ]
        )
        self.assertEqual(template, "xxz")

    def test_template_mapping_labels_xyz_when_all_components_differ(self):
        template = _template_for_terms(
            [
                {"label": "Sx@0 Sx@1", "coefficient": 1.0},
                {"label": "Sy@0 Sy@1", "coefficient": 2.0},
                {"label": "Sz@0 Sz@1", "coefficient": 3.0},
            ]
        )
        self.assertEqual(template, "xyz")


if __name__ == "__main__":
    unittest.main()
