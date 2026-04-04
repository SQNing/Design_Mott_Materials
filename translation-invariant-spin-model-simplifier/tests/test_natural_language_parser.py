import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from natural_language_parser import parse_controlled_natural_language


class NaturalLanguageParserTests(unittest.TestCase):
    def test_parse_controlled_text_extracts_lattice_atoms_and_j_shell_definitions(self):
        text = (
            "Orthorhombic lattice with a=3, b=8, c=8, alpha=90, beta=90, gamma=90. "
            "One magnetic atom at (0, 0, 0). "
            "Use J1 and J2 defined by first and second distance shells. "
            "Use LT then LSWT."
        )
        parsed = parse_controlled_natural_language(text)
        self.assertEqual(parsed["status"], "ok")
        self.assertEqual(parsed["lattice"]["kind"], "orthorhombic")
        self.assertAlmostEqual(parsed["lattice"]["cell_parameters"]["a"], 3.0, places=9)
        self.assertEqual(parsed["lattice"]["positions"], [[0.0, 0.0, 0.0]])
        self.assertEqual(parsed["exchange_mapping"]["mode"], "distance-shells")
        self.assertEqual(parsed["exchange_mapping"]["shell_map"], {"J1": 1, "J2": 2})
        self.assertEqual(parsed["solver_preferences"]["classical"], "luttinger-tisza")
        self.assertEqual(parsed["solver_preferences"]["lswt"], True)

    def test_parse_controlled_text_extracts_fractional_atom_label_variants(self):
        text = (
            "Rectangular lattice, a=3 b=8 c=8 alpha=90 beta=90 gamma=90. "
            "Magnetic atoms: atom1=(0,0,0), atom2=(0.5,0,0). "
            "J1/J2 by first/second distance shells."
        )
        parsed = parse_controlled_natural_language(text)
        self.assertEqual(parsed["status"], "ok")
        self.assertEqual(parsed["lattice"]["positions"], [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]])

    def test_parse_controlled_text_surfaces_question_when_exchange_mapping_is_ambiguous(self):
        text = (
            "Orthorhombic lattice with a=3, b=8, c=8, alpha=90, beta=90, gamma=90. "
            "One magnetic atom at (0, 0, 0). "
            "J1=-1, J2=2. "
            "Solve with LT."
        )
        parsed = parse_controlled_natural_language(text)
        self.assertEqual(parsed["status"], "needs_input")
        self.assertEqual(parsed["question"]["id"], "exchange_mapping")
        self.assertIn("distance shells", parsed["question"]["prompt"])

    def test_parse_controlled_text_does_not_infer_lt_from_default_word(self):
        text = (
            "Orthorhombic lattice with a=3, b=8, c=8, alpha=90, beta=90, gamma=90. "
            "One magnetic atom at (0, 0, 0). "
            "Use J1 and J2 defined by first and second distance shells. "
            "Use default settings."
        )
        parsed = parse_controlled_natural_language(text)
        self.assertEqual(parsed["status"], "ok")
        self.assertIsNone(parsed["solver_preferences"]["classical"])

    def test_parse_controlled_text_still_detects_explicit_lt_keyword(self):
        text = (
            "Orthorhombic lattice with a=3, b=8, c=8, alpha=90, beta=90, gamma=90. "
            "One magnetic atom at (0, 0, 0). "
            "Use J1 and J2 defined by first and second distance shells. "
            "Use LT."
        )
        parsed = parse_controlled_natural_language(text)
        self.assertEqual(parsed["status"], "ok")
        self.assertEqual(parsed["solver_preferences"]["classical"], "luttinger-tisza")


if __name__ == "__main__":
    unittest.main()
