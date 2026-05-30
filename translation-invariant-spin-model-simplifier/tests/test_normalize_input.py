import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(SKILL_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from input.normalize_input import normalize_input
from input.lattice_term_boundary import convert_legacy_payload_to_lattice_term_payload
from common.lattice_term_contract import find_forbidden_legacy_fields, validate_lattice_term_payload


class NormalizeInputTests(unittest.TestCase):
    def test_agent_normalized_input_exposes_canonical_lattice_term_contract(self):
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
                                    "orbit_ref": "bond_orbit:J1",
                                    "expression": "J_1 * Sz@0 Sz@1",
                                    "pair_matrix": [[1, 0], [0, 1]],
                                    "translation": [1, 0, 0],
                                    "source": 0,
                                    "target": 1,
                                    "payload": {
                                        "kind": "bilinear_exchange_matrix",
                                        "matrix": {
                                            "storage": "dense",
                                            "shape": [3, 3],
                                            "basis_order": ["Sx", "Sy", "Sz"],
                                            "scalar_type": "real_parameter_expression",
                                            "data": [
                                                [
                                                    {"kind": "parameter_ref", "parameter_ref": "param:J1"},
                                                    {"kind": "real", "value": 0.0},
                                                    {"kind": "real", "value": 0.0},
                                                ],
                                                [
                                                    {"kind": "real", "value": 0.0},
                                                    {"kind": "parameter_ref", "parameter_ref": "param:J1"},
                                                    {"kind": "real", "value": 0.0},
                                                ],
                                                [
                                                    {"kind": "real", "value": 0.0},
                                                    {"kind": "real", "value": 0.0},
                                                    {"kind": "parameter_ref", "parameter_ref": "param:J1"},
                                                ],
                                            ],
                                        },
                                        "hermiticity": "real_bilinear",
                                        "orientation_transform": "transpose_on_reverse",
                                    },
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
                },
            }
        )

        self.assertEqual(result["schema_version"], "lattice-term-contract/v1")
        self.assertIn("local_hilbert", result)
        self.assertIn("lattice_structure", result)
        self.assertIn("symmetry", result)
        self.assertIn("term_attachments", result)
        self.assertIn("solver_request", result)
        self.assertIn("parameters", result)
        self.assertIn("provenance", result)
        self.assertTrue(result["term_attachments"]["bond_terms"])
        self.assertTrue(result["term_attachments"]["term_sets"])
        self.assertEqual(
            result["solver_request"]["selected_term_set_ref"],
            "term_set:all_compatible_document_terms",
        )
        self.assertEqual(find_forbidden_legacy_fields(result), [])
        validate_lattice_term_payload(result)

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
                                    "source_label": "1",
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

    def test_direct_structured_input_returns_contract_without_legacy_route_keys(self):
        result = normalize_input(
            {
                "representation": "operator",
                "support": [0, 1],
                "expression": "J1*Sz@0 Sz@1",
                "classical_bond_label": "spin-only",
                "selected_local_bond_bond_label": "1",
            }
        )

        self.assertEqual(result["schema_version"], "lattice-term-contract/v1")
        self.assertEqual(find_forbidden_legacy_fields(result), [])
        self.assertNotIn("classical_bond_label", result)
        self.assertNotIn("selected_local_bond_bond_label", result)
        validate_lattice_term_payload(result)

    def test_explicit_legacy_payloads_convert_through_adapter_only(self):
        result = convert_legacy_payload_to_lattice_term_payload(
            {
                "representation": "operator",
                "support": [0, 1],
                "expression": "J1*Sz@0 Sz@1",
                "classical_bond_label": "spin-only",
                "selected_local_bond_bond_label": "1",
            }
        )

        self.assertEqual(result["schema_version"], "lattice-term-contract/v1")
        self.assertEqual(find_forbidden_legacy_fields(result), [])
        validate_lattice_term_payload(result)


if __name__ == "__main__":
    unittest.main()
