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


class DocumentInputProtocolTests(unittest.TestCase):
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
                            "family": "1",
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
        self.assertNotIn("selected_local_bond_family", record["hamiltonian_model"])

    def test_agent_normalized_record_falls_back_to_local_bond_candidates_without_bond_terms(self):
        agent_normalized_document = {
            "source_document": {"source_kind": "agent_normalized_document", "source_path": "paper.tex"},
            "model_candidates": [{"name": "effective", "role": "main"}],
            "candidate_models": {
                "effective": {
                    "local_bond_candidates": [
                        {
                            "family": "1",
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


if __name__ == "__main__":
    unittest.main()
