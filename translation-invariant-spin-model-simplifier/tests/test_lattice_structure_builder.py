import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(SKILL_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from common.lattice_structure_builder import (
    build_lattice_structure,
    build_symmetry_record,
    resolve_document_label_to_bond_orbit,
)


class LatticeStructureBuilderTests(unittest.TestCase):
    def test_build_lattice_structure_turns_legacy_bond_label_maps_into_canonical_bond_orbits(self):
        source_model = {
            "lattice_model": {
                "positions": [[0.0, 0.0, 0.0]],
                "bond_orbit_shell_map": {
                    "1": {"shell_index": 2, "distance": 1.0},
                },
                "bond_orbit_representative_map": {
                    "1": {"source": 0, "target": 0, "translation": [1, 0, 0]},
                },
            },
            "hamiltonian_model": {
                "local_bond_candidates": [
                    {
                        "bond_label": "1",
                        "expression": "J_1 * Sx@0 Sx@1",
                    }
                ]
            },
        }

        lattice_structure = build_lattice_structure(source_model)

        self.assertIn("basis_sites", lattice_structure)
        self.assertIn("local_frames", lattice_structure)
        self.assertIn("site_orbits", lattice_structure)
        self.assertIn("bond_orbits", lattice_structure)
        self.assertIn("higher_body_orbits", lattice_structure)
        self.assertIn("source_labels", lattice_structure)

        bond_orbits = lattice_structure["bond_orbits"]
        self.assertEqual(len(bond_orbits), 1)
        self.assertEqual(bond_orbits[0]["shell"], 2)
        self.assertEqual(bond_orbits[0]["representative"]["translation"], [1, 0, 0])
        self.assertTrue(
            all("generated_by_operation_ref" in member for member in bond_orbits[0]["members"])
        )
        self.assertTrue(
            any(member["generated_by_operation_ref"] for member in bond_orbits[0]["members"])
        )

    def test_build_symmetry_record_emits_axial_vector_rotations_for_spin_terms(self):
        source_model = {
            "hamiltonian_model": {
                "bond_terms": [
                    {
                        "bond_ref": "bond-1",
                        "support_ref": ["site:0", "site:1"],
                        "payload": {"kind": "pair_matrix"},
                    }
                ]
            }
        }

        symmetry = build_symmetry_record(source_model)

        self.assertIn("source", symmetry)
        self.assertIn("operations", symmetry)
        self.assertIn("spin_space_rotations", symmetry)
        self.assertIn("local_frame_actions", symmetry)
        self.assertIn("unresolved", symmetry)
        self.assertTrue(
            any(
                rotation.get("kind") == "axial_vector_rotation"
                for rotation in symmetry["spin_space_rotations"]
            )
        )

    def test_ambiguous_source_labels_raise_ambiguous_document_label(self):
        with self.assertRaisesRegex(ValueError, "ambiguous-document-label"):
            resolve_document_label_to_bond_orbit(
                "1",
                [
                    {"orbit_ref": "bond-orbit:1a", "source_labels": ["1"]},
                    {"orbit_ref": "bond-orbit:1b", "source_labels": ["1"]},
                ],
            )


if __name__ == "__main__":
    unittest.main()
