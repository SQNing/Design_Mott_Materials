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

    def test_priority_corrections_prefer_attachment_language_over_bond_label_language(self):
        corrections = _priority_corrections_from_findings(
            [
                {
                    "id": "selected_bond_orbit_missing_in_matrix_form",
                    "selected_bond_orbit_ref": "bond_orbit:1",
                }
            ]
        )

        joined = " ".join(corrections).lower()

        self.assertIn("attachment", joined)
        self.assertNotIn("bond_label", joined)

    def test_verifier_reports_attachment_mismatch_without_bond_label_only_language(self):
        report = verify_agent_normalized_document(
            {
                "candidate_models": {
                    "effective": {
                        "bond_terms": [
                            {"orbit_ref": "bond_orbit:1", "expression": "J1*Sz@0 Sz@1", "evidence_refs": ["eq1"]}
                        ]
                    },
                    "matrix_form": {
                        "bond_terms": [
                            {"orbit_ref": "bond_orbit:2", "expression": "J2*Sz@0 Sz@1", "evidence_refs": ["eq2"]}
                        ]
                    },
                }
            },
            selected_bond_orbit_ref="bond_orbit:1",
        )

        mismatch_messages = [
            finding["message"]
            for finding in report["findings"]
            if finding.get("id") == "selected_bond_orbit_missing_in_matrix_form"
        ]

        finding_ids = [finding.get("id", "") for finding in report["findings"]]
        self.assertTrue(mismatch_messages)
        self.assertTrue(any("attachment" in message.lower() for message in mismatch_messages))
        self.assertTrue(all("bond_label" not in message.lower() for message in mismatch_messages))
        self.assertTrue(all("bond_label" not in finding_id.lower() for finding_id in finding_ids))


if __name__ == "__main__":
    unittest.main()
