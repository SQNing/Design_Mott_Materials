import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from generate_simplifications import generate_candidates, resolve_candidate_choice, resolve_projection_choice


class GenerateSimplificationsTests(unittest.TestCase):
    def test_three_layered_candidates_are_generated_from_effective_model(self):
        model = {
            "effective_model": {
                "main": [{"type": "xxz_like", "coefficient": 1.0}],
                "low_weight": [{"canonical_label": "Sz@0", "coefficient": 0.05}],
                "residual": [{"canonical_label": "Sx@0 Sy@1 Sz@2", "coefficient": 0.1}],
            }
        }
        summary = generate_candidates(model)
        self.assertEqual(len(summary["candidates"]), 3)
        self.assertEqual(summary["candidates"][summary["recommended"]]["name"], "faithful-readable")

    def test_low_weight_terms_are_not_silently_dropped(self):
        model = {
            "effective_model": {
                "main": [{"type": "isotropic_exchange", "coefficient": 1.0}],
                "low_weight": [{"canonical_label": "Sz@0", "coefficient": 0.05}],
                "residual": [],
            }
        }
        summary = generate_candidates(model)
        faithful = summary["candidates"][0]
        self.assertEqual(faithful["name"], "faithful-readable")
        self.assertEqual(len(faithful["low_weight"]), 1)
        self.assertEqual(faithful["dropped_terms"], [])

    def test_aggressive_minimal_requires_explicit_selection(self):
        model = {"effective_model": {"main": [{"type": "isotropic_exchange", "coefficient": 1.0}], "low_weight": [], "residual": []}}
        summary = generate_candidates(model)
        choice = resolve_candidate_choice(summary, user_choice=None, timed_out=True)
        self.assertEqual(choice["selected"], summary["recommended"])
        self.assertEqual(summary["candidates"][choice["selected"]]["name"], "faithful-readable")


if __name__ == "__main__":
    unittest.main()
