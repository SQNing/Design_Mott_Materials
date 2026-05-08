import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(SKILL_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from input.normalize_input import normalize_input


class NormalizeInputTests(unittest.TestCase):
    def test_agent_normalized_input_keeps_bond_terms_primary_when_present(self):
        result = normalize_input(
            {
                "representation": "natural_language",
                "description": "H = J_1 * Sz@0 Sz@1",
                "agent_normalized_document": {
                    "source_document": {"source_kind": "agent_normalized_document"},
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
                },
            }
        )

        self.assertIn("bond_terms", result["document_intermediate"]["hamiltonian_model"])
        self.assertNotIn("local_bond_candidates", result["document_intermediate"]["hamiltonian_model"])


if __name__ == "__main__":
    unittest.main()
