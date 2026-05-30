import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(SKILL_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from input.agent_fallback import build_agent_inferred
from input.normalize_input import normalize_freeform_text, normalize_input


class HumanInputFallbackPolicyTests(unittest.TestCase):
    def test_agent_fallback_reports_expression_hint_and_next_step(self):
        proposal = build_agent_inferred(
            source_text="H = J1*(Sz@0 Sz@1 + 0.5*(Sp@0 Sm@1 + Sm@0 Sp@1)) + hx*Sz@0",
            intermediate_record={},
            normalization_context={},
        )

        agent = proposal["agent_inferred"]
        summary = agent["user_explanation"]["summary"].lower()
        recognized = " | ".join(agent["recognized_items"]).lower()

        self.assertIn("spin operator expression", summary)
        self.assertIn("script-consumable", summary)
        self.assertIn("operator expression", recognized)

    def test_freeform_operator_like_human_input_triggers_agent_fallback(self):
        result = normalize_freeform_text(
            "H = J1*(Sz@0 Sz@1 + 0.5*(Sp@0 Sm@1 + Sm@0 Sp@1)) + hx*Sz@0",
            selected_classical_bond_label="spin-only",
        )

        self.assertEqual(result.get("interaction", {}).get("id"), "agent_fallback_review")
        self.assertEqual(result.get("agent_normalization_request", {}).get("source_kind"), "natural_language")

    def test_structured_payload_still_bypasses_agent_fallback(self):
        result = normalize_input(
            {
                "representation": "operator",
                "support": [0, 1],
                "expression": "J1*Sz@0 Sz@1",
                "classical_bond_label": "spin-only",
                "source_mode": "operator",
            }
        )

        self.assertIsNone(result.get("agent_normalization_request"))
        self.assertIsNone(result.get("landing_readiness"))


if __name__ == "__main__":
    unittest.main()
