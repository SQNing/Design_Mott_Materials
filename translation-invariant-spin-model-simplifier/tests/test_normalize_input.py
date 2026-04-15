import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from input.normalize_input import normalize_input


class NormalizeInputTests(unittest.TestCase):
    def test_many_body_hr_representation_is_accepted_with_required_paths(self):
        payload = {
            "representation": "many_body_hr",
            "structure_file": "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR",
            "hamiltonian_file": "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat",
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["hamiltonian_description"]["representation"]["kind"], "many_body_hr")
        self.assertEqual(
            normalized["hamiltonian_description"]["representation"]["structure_file"],
            payload["structure_file"],
        )
        self.assertEqual(
            normalized["hamiltonian_description"]["representation"]["hamiltonian_file"],
            payload["hamiltonian_file"],
        )
        self.assertEqual(normalized["basis_semantics"]["local_space"], "pseudospin_orbital")
        self.assertEqual(normalized["basis_order"], "orbital_major_spin_minor")

    def test_many_body_hr_requires_structure_and_hamiltonian_paths(self):
        with self.assertRaises(ValueError):
            normalize_input({"representation": "many_body_hr", "structure_file": "POSCAR"})

        with self.assertRaises(ValueError):
            normalize_input({"representation": "many_body_hr", "hamiltonian_file": "VR_hr.dat"})

    def test_existing_operator_input_path_still_works(self):
        payload = {
            "representation": "operator",
            "support": [0, 1],
            "expression": "J * Sx@0 Sx@1",
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["hamiltonian_description"]["representation"]["kind"], "operator")
        self.assertEqual(normalized["hamiltonian_description"]["support"], [0, 1])

    def test_normalize_input_accepts_document_intermediate_that_lands_to_operator(self):
        payload = {
            "representation": "natural_language",
            "description": "Effective Hamiltonian text",
            "document_intermediate": {
                "source_document": {"source_kind": "tex_document"},
                "model_candidates": [{"name": "effective", "role": "main"}],
                "hamiltonian_model": {"operator_expression": "J * Sz@0 Sz@1"},
                "parameter_registry": {"J": -0.236},
                "ambiguities": [],
                "unsupported_features": ["matrix_form_metadata"],
            },
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["local_term"]["representation"]["kind"], "operator")
        self.assertEqual(normalized["local_term"]["representation"]["value"], "J * Sz@0 Sz@1")
        self.assertEqual(normalized["local_term"]["support"], [0, 1])
        self.assertEqual(normalized["parameters"], {"J": -0.236})

    def test_normalize_input_preserves_needs_input_from_document_intermediate(self):
        payload = {
            "representation": "natural_language",
            "description": "Toy plus effective Hamiltonian",
            "document_intermediate": {
                "source_document": {"source_kind": "tex_document"},
                "model_candidates": [
                    {"name": "toy", "role": "simplified"},
                    {"name": "effective", "role": "main"},
                ],
                "ambiguities": [
                    {
                        "id": "model_candidate_selection",
                        "blocks_landing": True,
                        "question": "Multiple Hamiltonian candidates were detected. Which one should I use?",
                    }
                ],
                "unsupported_features": ["matrix_form_metadata"],
            },
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["interaction"]["status"], "needs_input")
        self.assertEqual(normalized["interaction"]["id"], "model_candidate_selection")
        self.assertEqual(normalized["unsupported_features"], ["matrix_form_metadata"])
        self.assertEqual(normalized["local_term"]["representation"]["kind"], "natural_language")


if __name__ == "__main__":
    unittest.main()
