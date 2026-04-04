import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from infer_symmetries import infer_symmetries


class InferSymmetriesTests(unittest.TestCase):
    def test_detects_translation_and_hermiticity_from_normalized_model(self):
        model = {
            "lattice_description": {"kind": "triangular", "dimension": 2},
            "hamiltonian_description": {"representation": {"kind": "operator", "value": "J * Sx(0) * Sx(1)"}},
            "user_required_symmetries": [],
            "allowed_breaking": [],
        }
        inferred = infer_symmetries(model)
        self.assertIn("translation", inferred["detected_symmetries"])
        self.assertIn("hermiticity", inferred["detected_symmetries"])

    def test_detects_su2_for_isotropic_exchange_terms(self):
        model = {
            "decomposition": {
                "terms": [
                    {"label": "Sx@0 Sx@1", "coefficient": 1.0},
                    {"label": "Sy@0 Sy@1", "coefficient": 1.0},
                    {"label": "Sz@0 Sz@1", "coefficient": 1.0},
                ]
            },
            "user_required_symmetries": [],
            "allowed_breaking": [],
        }
        inferred = infer_symmetries(model)
        self.assertIn("su2_spin", inferred["detected_symmetries"])

    def test_requests_confirmation_for_required_but_undetected_symmetry(self):
        model = {
            "decomposition": {
                "terms": [
                    {"label": "Sx@0 Sx@1", "coefficient": 1.0},
                    {"label": "Sy@0 Sy@1", "coefficient": 1.0},
                    {"label": "Sz@0 Sz@1", "coefficient": 1.2},
                ]
            },
            "user_required_symmetries": ["su2_spin"],
            "allowed_breaking": [],
        }
        inferred = infer_symmetries(model)
        self.assertEqual(inferred["interaction"]["status"], "needs_input")
        self.assertIn("su2_spin", inferred["interaction"]["question"])


if __name__ == "__main__":
    unittest.main()
