import io
import sys
import unittest
from pathlib import Path
from unittest import mock

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from normalize_input import main, normalize_input, normalize_freeform_text


class NormalizeInputTests(unittest.TestCase):
    def test_operator_payload_is_normalized(self):
        payload = {
            "representation": "operator",
            "expression": "J * Sx(0) * Sx(1) + J * Sy(0) * Sy(1) + J * Sz(0) * Sz(1)",
            "local_dim": 2,
            "support": [0, 1],
            "lattice": {"kind": "bravais", "dimension": 1},
        }
        normalized = normalize_input(payload)
        self.assertEqual(normalized["local_hilbert"]["dimension"], 2)
        self.assertEqual(normalized["local_term"]["representation"]["kind"], "operator")
        self.assertEqual(normalized["local_term"]["support"], [0, 1])

    def test_matrix_payload_uses_matrix_field(self):
        payload = {
            "representation": "matrix",
            "expression": "should not win",
            "matrix": "[[0, 1], [1, 0]]",
            "local_dim": 2,
            "support": [0, 1],
        }
        normalized = normalize_input(payload)
        self.assertEqual(normalized["local_term"]["representation"]["kind"], "matrix")
        self.assertEqual(normalized["local_term"]["representation"]["value"], "[[0, 1], [1, 0]]")

    def test_invalid_representation_is_rejected(self):
        payload = {
            "representation": "bogus",
            "expression": "J * Sz(0) * Sz(1)",
            "local_dim": 2,
            "support": [0, 1],
        }
        with self.assertRaises(ValueError):
            normalize_input(payload)

    def test_missing_required_representation_content_is_rejected(self):
        payload = {
            "representation": "operator",
            "local_dim": 2,
            "support": [0, 1],
        }
        with self.assertRaises(ValueError):
            normalize_input(payload)

    def test_malformed_support_is_rejected(self):
        payload = {
            "representation": "operator",
            "expression": "J * Sz(0) * Sz(1)",
            "local_dim": 2,
            "support": "01",
        }
        with self.assertRaises(ValueError):
            normalize_input(payload)

    def test_natural_language_input_preserves_summary(self):
        summary = "Spin-one-half kagome model with nearest-neighbor XXZ exchange and out-of-plane DM terms."
        normalized = normalize_freeform_text(summary)
        self.assertEqual(normalized["local_term"]["representation"]["kind"], "natural_language")
        self.assertEqual(normalized["user_notes"], summary)
        self.assertIn("parameters", normalized)
        self.assertIn("symmetry_hints", normalized)

    def test_freeform_spin_one_infers_local_dimension(self):
        normalized = normalize_freeform_text("Spin-1 triangular-lattice antiferromagnet with easy-plane anisotropy")
        self.assertEqual(normalized["local_hilbert"]["dimension"], 3)

    def test_freeform_spin_three_halves_infers_local_dimension(self):
        normalized = normalize_freeform_text("Spin-3/2 kagome antiferromagnet with anisotropy")
        self.assertEqual(normalized["local_hilbert"]["dimension"], 4)

    def test_freeform_spaced_fraction_spin_three_halves_infers_local_dimension(self):
        normalized = normalize_freeform_text("Spin 3 / 2 kagome antiferromagnet with anisotropy")
        self.assertEqual(normalized["local_hilbert"]["dimension"], 4)

    def test_structured_natural_language_spin_three_halves_infers_local_dimension(self):
        payload = {
            "representation": "natural_language",
            "description": "Spin-3/2 triangular-lattice antiferromagnet with anisotropy.",
        }
        normalized = normalize_input(payload)
        self.assertEqual(normalized["local_hilbert"]["dimension"], 4)
        self.assertEqual(normalized["user_notes"], payload["description"])

    def test_structured_natural_language_spaced_fraction_infers_local_dimension(self):
        payload = {
            "representation": "natural_language",
            "description": "Spin 3 / 2 triangular-lattice antiferromagnet with anisotropy.",
        }
        normalized = normalize_input(payload)
        self.assertEqual(normalized["local_hilbert"]["dimension"], 4)
        self.assertEqual(normalized["user_notes"], payload["description"])

    def test_unsupported_spin_fractions_are_rejected(self):
        cases = [
            ("spin-2/3 kagome antiferromagnet", normalize_freeform_text),
            ("spin-7/4 kagome antiferromagnet", normalize_freeform_text),
            ("spin 2 / 3 kagome antiferromagnet", normalize_freeform_text),
            ("spin 7 / 4 kagome antiferromagnet", normalize_freeform_text),
            (
                {
                    "representation": "natural_language",
                    "description": "spin-2/3 kagome antiferromagnet",
                },
                normalize_input,
            ),
            (
                {
                    "representation": "natural_language",
                    "description": "spin-7/4 kagome antiferromagnet",
                },
                normalize_input,
            ),
            (
                {
                    "representation": "natural_language",
                    "description": "spin 2 / 3 kagome antiferromagnet",
                },
                normalize_input,
            ),
            (
                {
                    "representation": "natural_language",
                    "description": "spin 7 / 4 kagome antiferromagnet",
                },
                normalize_input,
            ),
        ]
        for payload, func in cases:
            with self.subTest(payload=payload, func=func.__name__):
                with self.assertRaises(ValueError):
                    func(payload)

    def test_structured_natural_language_preserves_description_in_user_notes(self):
        payload = {
            "representation": "natural_language",
            "description": "Square-lattice spin-1 Heisenberg model with single-ion anisotropy.",
            "local_dim": 99,
        }
        normalized = normalize_input(payload)
        self.assertEqual(normalized["user_notes"], payload["description"])
        self.assertEqual(normalized["local_hilbert"]["dimension"], 3)

    def test_controlled_natural_language_populates_structured_lattice_and_solver_hints(self):
        payload = {
            "representation": "natural_language",
            "description": (
                "Orthorhombic lattice with a=3, b=8, c=8, alpha=90, beta=90, gamma=90. "
                "One magnetic atom at (0, 0, 0). "
                "Use J1 and J2 defined by first and second distance shells. "
                "Use LT then LSWT."
            ),
        }
        normalized = normalize_input(payload)
        self.assertEqual(normalized["lattice"]["kind"], "orthorhombic")
        self.assertAlmostEqual(normalized["lattice"]["cell_parameters"]["a"], 3.0, places=9)
        self.assertEqual(normalized["lattice"]["positions"], [[0.0, 0.0, 0.0]])
        self.assertEqual(normalized["exchange_mapping"]["shell_map"], {"J1": 1, "J2": 2})
        self.assertEqual(normalized["solver_preferences"]["classical"], "luttinger-tisza")
        self.assertTrue(normalized["solver_preferences"]["lswt"])
        self.assertEqual(normalized["interaction"]["status"], "ok")

    def test_ambiguous_controlled_natural_language_surfaces_clarification_question(self):
        payload = {
            "representation": "natural_language",
            "description": (
                "Orthorhombic lattice with a=3, b=8, c=8, alpha=90, beta=90, gamma=90. "
                "One magnetic atom at (0, 0, 0). J1=-1, J2=2. Use LT."
            ),
        }
        normalized = normalize_input(payload)
        self.assertEqual(normalized["interaction"]["status"], "needs_input")
        self.assertEqual(normalized["interaction"]["question"]["id"], "exchange_mapping")

    def test_structured_natural_language_preserves_explicit_lattice_when_parser_has_no_override(self):
        payload = {
            "representation": "natural_language",
            "description": "Spin-1/2 Heisenberg model.",
            "lattice": {
                "kind": "orthorhombic",
                "positions": [[0.0, 0.0, 0.0]],
                "cell_parameters": {
                    "a": 3.0,
                    "b": 8.0,
                    "c": 8.0,
                    "alpha": 90.0,
                    "beta": 90.0,
                    "gamma": 90.0,
                },
            },
        }
        normalized = normalize_input(payload)
        self.assertEqual(normalized["lattice"]["kind"], "orthorhombic")
        self.assertEqual(normalized["lattice"]["positions"], [[0.0, 0.0, 0.0]])
        self.assertAlmostEqual(normalized["lattice"]["cell_parameters"]["a"], 3.0, places=9)

    def test_blank_freeform_input_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_freeform_text("   ")

    def test_cli_explicit_empty_freeform_is_routed_to_validation(self):
        stdin_payload = io.StringIO('{"representation": "operator", "expression": "J", "support": [0]}')
        with mock.patch.object(sys, "argv", ["normalize_input.py", "--freeform", ""]), mock.patch.object(sys, "stdin", stdin_payload):
            with self.assertRaises(ValueError):
                main()


if __name__ == "__main__":
    unittest.main()
