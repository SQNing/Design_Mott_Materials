import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from generate_simplifications import generate_candidates, resolve_candidate_choice, resolve_projection_choice


class GenerateSimplificationsTests(unittest.TestCase):
    def test_three_candidates_are_generated_for_xxz_like_terms(self):
        model = {
            "decomposition": {
                "terms": [
                    {"label": "Sx@0 Sx@1", "coefficient": 1.0},
                    {"label": "Sy@0 Sy@1", "coefficient": 1.0},
                    {"label": "Sz@0 Sz@1", "coefficient": 1.4},
                    {"label": "Sz@0", "coefficient": 0.05},
                ]
            }
        }
        summary = generate_candidates(model, relative_threshold=0.1)
        self.assertEqual(len(summary["candidates"]), 3)
        self.assertIn(summary["recommended"], {0, 1, 2})

    def test_template_mapping_labels_xxz(self):
        model = {
            "decomposition": {
                "terms": [
                    {"label": "Sx@0 Sx@1", "coefficient": 1.0},
                    {"label": "Sy@0 Sy@1", "coefficient": 1.0},
                    {"label": "Sz@0 Sz@1", "coefficient": 1.2},
                ]
            }
        }
        summary = generate_candidates(model, relative_threshold=0.05)
        names = [candidate["name"] for candidate in summary["candidates"]]
        self.assertIn("template-map", names)

    def test_timeout_uses_recommended_candidate_and_projection(self):
        model = {
            "decomposition": {
                "terms": [
                    {"label": "Sx@0 Sx@1", "coefficient": 1.0},
                    {"label": "Sy@0 Sy@1", "coefficient": 1.0},
                    {"label": "Sz@0 Sz@1", "coefficient": 1.1},
                ]
            }
        }
        summary = generate_candidates(model, relative_threshold=0.05)
        choice = resolve_candidate_choice(summary, user_choice=None, timed_out=True)
        projection = resolve_projection_choice(needs_projection=True, user_choice=None, timed_out=True)
        self.assertEqual(choice["selected"], summary["recommended"])
        self.assertEqual(projection["action"], "apply-default-projection")


if __name__ == "__main__":
    unittest.main()
