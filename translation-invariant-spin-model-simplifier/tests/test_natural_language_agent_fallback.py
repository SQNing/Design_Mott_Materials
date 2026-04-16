import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from input.agent_fallback import build_agent_inferred, render_recognized_items


class NaturalLanguageAgentFallbackTests(unittest.TestCase):
    def test_build_agent_inferred_marks_safe_hr_file_pair_as_agent_proposed_ok(self):
        proposal = build_agent_inferred(
            source_text="use structure.cif and wannier90_hr.dat for the effective Hamiltonian",
            intermediate_record={"model_candidates": [{"name": "effective"}]},
            normalization_context={},
        )

        self.assertEqual(proposal["landing_readiness"], "agent_proposed_ok")
        self.assertEqual(
            proposal["agent_inferred"]["inferred_fields"]["input_family"],
            "many_body_hr",
        )
        self.assertIn(
            "structure.cif",
            "\n".join(proposal["agent_inferred"]["user_explanation"]["recognized"]),
        )

    def test_build_agent_inferred_keeps_coordinate_convention_as_hard_gate(self):
        proposal = build_agent_inferred(
            source_text="use the effective Hamiltonian with family 1 terms",
            intermediate_record={"model_candidates": [{"name": "effective"}]},
            normalization_context={"selected_local_bond_family": "1"},
        )

        self.assertEqual(proposal["landing_readiness"], "agent_proposed_needs_input")
        self.assertEqual(
            proposal["agent_inferred"]["unresolved_items"][0]["field"],
            "coordinate_convention",
        )

    def test_build_agent_inferred_marks_low_confidence_dialogue_as_non_landing(self):
        proposal = build_agent_inferred(
            source_text="maybe something like a layered spin model with some anisotropy",
            intermediate_record={"model_candidates": []},
            normalization_context={},
        )

        self.assertEqual(proposal["landing_readiness"], "agent_proposed_needs_input")
        self.assertEqual(proposal["agent_inferred"]["confidence"]["level"], "low")
        self.assertEqual(proposal["agent_inferred"]["status"], "rejected")

    def test_render_recognized_items_is_derived_view_not_new_evidence_store(self):
        rendered = render_recognized_items(
            source_spans=[{"text": "structure.cif", "role": "structure_path_hint"}],
            extracted_evidence=[{"text": "effective Hamiltonian", "role": "model_keyword"}],
        )

        self.assertEqual(
            rendered,
            [
                "structure file: structure.cif",
                "model keyword: effective Hamiltonian",
            ],
        )


if __name__ == "__main__":
    unittest.main()
