import json
import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(SKILL_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from input.agent_document_normalization_template import build_agent_document_normalization_template
from input.agent_document_prompt_builder import _priority_corrections_from_findings
from input.verify_agent_normalized_document import verify_agent_normalized_document


class NaturalLanguageAgentFallbackTests(unittest.TestCase):
    def test_template_example_keeps_structure_first_attachment_refs(self):
        bundle = build_agent_document_normalization_template()
        example_text = json.dumps(bundle["example_payload"], sort_keys=True)
        prompt_notes = "\n".join(bundle["prompt_notes"]).lower()

        self.assertIn("structure-first", prompt_notes)
        for needle in (
            "site_ref",
            "bond_ref",
            "orbit_ref",
            "explicit_edge_ref",
            "support_ref",
        ):
            self.assertIn(needle, example_text)

    def test_priority_corrections_prefer_attachment_language_over_family_language(self):
        corrections = _priority_corrections_from_findings(
            [
                {
                    "id": "selected_local_bond_family_missing_in_matrix_form",
                    "selected_local_bond_family": "1",
                }
            ]
        )

        joined = " ".join(corrections).lower()

        self.assertIn("attachment", joined)
        self.assertNotIn("family", joined)

    def test_verifier_reports_attachment_mismatch_without_family_only_language(self):
        report = verify_agent_normalized_document(
            {
                "candidate_models": {
                    "effective": {
                        "local_bond_candidates": [
                            {"family": "1", "expression": "J1*Sz@0 Sz@1", "evidence_refs": ["eq1"]}
                        ]
                    },
                    "matrix_form": {
                        "local_bond_candidates": [
                            {"family": "2", "expression": "J2*Sz@0 Sz@1", "evidence_refs": ["eq2"]}
                        ]
                    },
                }
            },
            selected_local_bond_family="1",
        )

        family_mismatch_messages = [
            finding["message"]
            for finding in report["findings"]
            if finding.get("id") == "selected_local_bond_family_missing_in_matrix_form"
        ]

        self.assertTrue(family_mismatch_messages)
        self.assertTrue(any("attachment" in message.lower() for message in family_mismatch_messages))
        self.assertTrue(all("family" not in message.lower() for message in family_mismatch_messages))


if __name__ == "__main__":
    unittest.main()
