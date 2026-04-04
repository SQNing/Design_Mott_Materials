import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from parse_lattice_description import parse_lattice_description


class ParseLatticeDescriptionTests(unittest.TestCase):
    def test_structured_lattice_is_returned_with_defaults(self):
        lattice = {
            "kind": "triangular",
            "dimension": 2,
            "magnetic_sites": [{"label": "A", "fractional_coordinate": [0.0, 0.0, 0.0]}],
        }
        parsed = parse_lattice_description(lattice)
        self.assertEqual(parsed["kind"], "triangular")
        self.assertEqual(parsed["dimension"], 2)
        self.assertEqual(len(parsed["magnetic_sites"]), 1)
        self.assertEqual(parsed["source"], "structured")

    def test_natural_language_honeycomb_is_parsed(self):
        parsed = parse_lattice_description(
            {"kind": "natural_language", "value": "Honeycomb lattice with two magnetic sites per unit cell and first distance shell J1"}
        )
        self.assertEqual(parsed["kind"], "honeycomb")
        self.assertEqual(parsed["dimension"], 2)
        self.assertEqual(parsed["magnetic_site_count"], 2)
        self.assertEqual(parsed["shell_labels"], ["J1"])

    def test_ambiguous_hexagonal_lattice_requests_input(self):
        parsed = parse_lattice_description({"kind": "natural_language", "value": "Hexagonal lattice with nearest-neighbor J1"})
        self.assertEqual(parsed["interaction"]["status"], "needs_input")
        self.assertIn("hexagonal", parsed["interaction"]["question"].lower())


if __name__ == "__main__":
    unittest.main()
