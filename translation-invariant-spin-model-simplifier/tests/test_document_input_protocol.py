import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(SKILL_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from input.document_input_protocol import (
    build_intermediate_record,
    build_intermediate_record_from_agent_normalized,
    land_intermediate_record,
)
from common.term_attachment_builder import build_term_attachments


class DocumentInputProtocolTests(unittest.TestCase):
    def test_intermediate_record_exposes_canonical_lattice_structure_and_symmetry(self):
        source_text = r"""
        \section*{Effective Hamiltonian}
        The bond label H_{ij}^{(1)} is used below.
        \begin{equation}
        H_{ij}^{(1)} = J_1 * Sx@0 Sx@1 + J_1 * Sy@0 Sy@1 + J_1 * Sz@0 Sz@1
        \end{equation}
        """

        record = build_intermediate_record(source_text=source_text)

        self.assertIn("lattice_structure", record)
        self.assertIn("symmetry", record)
        self.assertIn("bond_orbits", record["lattice_structure"])
        self.assertIn("source_labels", record["lattice_structure"])
        self.assertIn("operations", record["symmetry"])
        self.assertIn("spin_space_rotations", record["symmetry"])
        self.assertIn("local_frame_actions", record["symmetry"])
        self.assertIn("unresolved", record["symmetry"])
        self.assertIn("lattice_model", record)
        self.assertIn("hamiltonian_model", record)
        attachments = build_term_attachments(
            record,
            lattice_structure=record["lattice_structure"],
            local_hilbert={
                "sites": [
                    {
                        "site_ref": "site:0",
                        "space_ref": "space:spin_s_half",
                        "basis_ref": "basis:spin_s_half",
                        "classical_space_ref": "classical_space:spin_unit_vector",
                        "operator_basis_refs": ["op_basis:spin_cartesian"],
                    }
                ],
                "basis_registry": {
                    "basis:spin_s_half": {
                        "kind": "spin_multiplet",
                        "dimension": 2,
                        "basis_order": ["m=+1/2", "m=-1/2"],
                    }
                },
                "operator_bases": {
                    "op_basis:spin_cartesian": {
                        "kind": "spin_cartesian",
                        "basis_order": ["Sx", "Sy", "Sz"],
                    }
                },
                "classical_spaces": {
                    "classical_space:spin_unit_vector": {
                        "kind": "unit_vector_sphere",
                        "dimension": 3,
                    }
                },
            },
        )
        self.assertIn("bond_terms", attachments)
        self.assertIn("term_sets", attachments)

    def test_source_text_lands_through_bond_terms_and_explicit_bond_graph(self):
        source_text = r"""
        \section*{Effective Hamiltonian}
        The bond label H_{ij}^{(1)} is used below.
        \begin{equation}
        H_{ij}^{(1)} = J_1 * Sx@0 Sx@1 + J_1 * Sy@0 Sy@1 + J_1 * Sz@0 Sz@1
        \end{equation}
        """

        record = build_intermediate_record(source_text=source_text)

        self.assertIn("bond_terms", record["hamiltonian_model"])
        self.assertIn("explicit_bond_graph", record["hamiltonian_model"])
        self.assertNotIn("local_bond_candidates", record)

        landed = land_intermediate_record(record)
        self.assertEqual(landed["representation"], "operator")
        self.assertIn("expression", landed)

    def test_agent_normalized_record_uses_bond_terms_before_local_bond_candidates(self):
        agent_normalized_document = {
            "source_document": {"source_kind": "agent_normalized_document", "source_path": "paper.tex"},
            "model_candidates": [{"name": "effective", "role": "main"}],
            "candidate_models": {
                "effective": {
                    "bond_terms": [
                        {
                            "bond_ref": "bond-1",
                            "support_ref": ["site-0", "site-1"],
                            "explicit_edge_ref": "edge-1",
                            "orbit_ref": "orbit-1",
                            "expression": "J_1 * Sz@0 Sz@1",
                            "pair_matrix": [[1, 0], [0, 1]],
                            "translation": [1, 0, 0],
                            "source": 0,
                            "target": 1,
                        }
                    ],
                    "local_bond_candidates": [
                        {
                            "source_label": "1",
                            "expression": "legacy-expression",
                        }
                    ],
                }
            },
            "system_context": {},
            "lattice_model": {},
        }

        record = build_intermediate_record_from_agent_normalized(
            agent_normalized_document,
            source_text="H = J_1 * Sz@0 Sz@1",
        )

        self.assertIn("bond_terms", record["hamiltonian_model"])
        self.assertNotIn("local_bond_candidates", record["hamiltonian_model"])
        self.assertNotIn("selected_local_bond_bond_label", record["hamiltonian_model"])

    def test_agent_normalized_record_falls_back_to_local_bond_candidates_without_bond_terms(self):
        agent_normalized_document = {
            "source_document": {"source_kind": "agent_normalized_document", "source_path": "paper.tex"},
            "model_candidates": [{"name": "effective", "role": "main"}],
            "candidate_models": {
                "effective": {
                    "local_bond_candidates": [
                        {
                            "source_label": "1",
                            "expression": "J_1 * Sz@0 Sz@1",
                        }
                    ]
                }
            },
            "system_context": {},
            "lattice_model": {},
        }

        record = build_intermediate_record_from_agent_normalized(
            agent_normalized_document,
            source_text="H = J_1 * Sz@0 Sz@1",
        )

        self.assertIn("local_bond_candidates", record["hamiltonian_model"])
        self.assertNotIn("bond_terms", record["hamiltonian_model"])

    def test_document_labels_remain_in_source_labels_not_structural_keys(self):
        source_text = r"""
        \section*{Effective Hamiltonian}
        \begin{equation}
        H_{ij}^{(1)} = J_1 * Sx@0 Sx@1
        \end{equation}
        """

        record = build_intermediate_record(source_text=source_text)
        lattice_structure = record["lattice_structure"]

        self.assertIn("source_labels", lattice_structure)
        self.assertNotIn("bond_label", lattice_structure)
        self.assertNotIn("1", lattice_structure)


if __name__ == "__main__":
    unittest.main()
