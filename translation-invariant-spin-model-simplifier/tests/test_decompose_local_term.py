import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from decompose_local_term import decompose_local_term


class DecomposeLocalTermTests(unittest.TestCase):
    def test_spin_half_two_site_matrix_decomposes_into_szsz(self):
        matrix = [
            [0.25, 0.0, 0.0, 0.0],
            [0.0, -0.25, 0.0, 0.0],
            [0.0, 0.0, -0.25, 0.0],
            [0.0, 0.0, 0.0, 0.25],
        ]
        normalized = {
            "local_hilbert": {"dimension": 2},
            "local_term": {
                "support": [0, 1],
                "representation": {"kind": "matrix", "value": matrix},
            },
        }
        decomposition = decompose_local_term(normalized)
        labels = {term["label"]: round(term["coefficient"], 6) for term in decomposition["terms"]}
        self.assertAlmostEqual(labels["Sz@0 Sz@1"], 1.0)

    def test_nontrivial_support_indices_are_preserved_in_labels(self):
        matrix = [
            [0.25, 0.0, 0.0, 0.0],
            [0.0, -0.25, 0.0, 0.0],
            [0.0, 0.0, -0.25, 0.0],
            [0.0, 0.0, 0.0, 0.25],
        ]
        normalized = {
            "local_hilbert": {"dimension": 2},
            "local_term": {
                "support": [2, 5],
                "representation": {"kind": "matrix", "value": matrix},
            },
        }
        decomposition = decompose_local_term(normalized)
        labels = {term["label"]: round(term["coefficient"], 6) for term in decomposition["terms"]}
        self.assertAlmostEqual(labels["Sz@2 Sz@5"], 1.0)

    def test_operator_payload_passes_through_with_spin_mode_and_value(self):
        normalized = {
            "local_hilbert": {"dimension": 2},
            "local_term": {
                "support": [0, 1],
                "representation": {"kind": "operator", "value": "J * Sz(0) * Sz(1)"},
            },
        }
        decomposition = decompose_local_term(normalized)
        self.assertEqual(decomposition["mode"], "operator")
        self.assertEqual(decomposition["terms"][0]["value"], "J * Sz(0) * Sz(1)")

    def test_unsupported_representation_kind_is_rejected(self):
        normalized = {
            "local_hilbert": {"dimension": 2},
            "local_term": {
                "support": [0, 1],
                "representation": {"kind": "natural_language", "value": "nearest-neighbor Ising"},
            },
        }
        with self.assertRaisesRegex(ValueError, "unsupported representation"):
            decompose_local_term(normalized)

    def test_shape_mismatch_is_rejected(self):
        normalized = {
            "local_hilbert": {"dimension": 2},
            "local_term": {
                "support": [0, 1],
                "representation": {
                    "kind": "matrix",
                    "value": [[1.0, 0.0], [0.0, 1.0]],
                },
            },
        }
        with self.assertRaisesRegex(ValueError, "matrix shape"):
            decompose_local_term(normalized)

    def test_non_hermitian_matrix_is_rejected(self):
        normalized = {
            "local_hilbert": {"dimension": 2},
            "local_term": {
                "support": [0],
                "representation": {
                    "kind": "matrix",
                    "value": [[0.0, 1.0], [0.0, 0.0]],
                },
            },
        }
        with self.assertRaisesRegex(ValueError, "Hermitian"):
            decompose_local_term(normalized)


if __name__ == "__main__":
    unittest.main()
