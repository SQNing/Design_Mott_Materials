import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(SKILL_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from cli.normalize_document_with_agent import run_document_normalization_with_agent
from cli.run_agent_document_normalization_demo import (
    run_agent_document_normalization_demo,
)
from cli.run_document_reader_pipeline import run_document_reader_pipeline
from cli.simplify_text_input import run_text_simplification_pipeline


def _agent_review_model(*, interaction_id="agent_fallback_review", unresolved_items=None):
    unresolved_items = list(unresolved_items or [])
    return {
        "interaction": {
            "status": "needs_input",
            "id": interaction_id,
            "question": "I still need one more clarification before this can continue.",
        },
        "agent_normalization_request": {
            "id": "agent_document_normalization",
            "status": "recommended",
            "source_kind": "natural_language",
        },
        "landing_readiness": "agent_proposed_needs_input",
        "agent_inferred": {
            "confidence": {"level": "medium", "reason": "Recovered some structure."},
            "recognized_items": ["operator expression: J1*Sz@0 Sz@1"],
            "assumptions": [],
            "unresolved_items": unresolved_items,
            "user_explanation": {
                "summary": "The helper found a possible route, but it still needs coordinate_convention."
            },
        },
        "hamiltonian_description": {
            "representation": {"kind": "natural_language", "value": "J1*Sz@0 Sz@1"}
        },
    }


class HumanInputFallbackWrapperTests(unittest.TestCase):
    @patch("cli.normalize_document_with_agent.normalize_freeform_text")
    def test_normalize_document_wrapper_preserves_deterministic_success(self, normalize_freeform_text):
        normalize_freeform_text.return_value = {
            "hamiltonian_description": {
                "representation": {"kind": "operator", "value": "J1*Sz@0 Sz@1"}
            }
        }

        result = run_document_normalization_with_agent("J1*Sz@0 Sz@1")

        self.assertEqual(result["status"], "ok")
        self.assertNotIn("agent_normalization_request", result)
        self.assertNotIn("landing_readiness", result)
        self.assertNotIn("next_step_guidance", result)

    @patch("cli.normalize_document_with_agent.normalize_freeform_text")
    def test_normalize_document_wrapper_reports_agent_fallback_surface(self, normalize_freeform_text):
        normalize_freeform_text.return_value = _agent_review_model()

        result = run_document_normalization_with_agent("J1*Sz@0 Sz@1")

        self.assertEqual(result["status"], "needs_agent_normalization")
        self.assertEqual(result["landing_readiness"], "agent_proposed_needs_input")
        self.assertEqual(result["agent_normalization_request"]["id"], "agent_document_normalization")
        self.assertEqual(result["agent_inferred"]["recognized_items"], ["operator expression: J1*Sz@0 Sz@1"])
        self.assertIn("next_step_guidance", result)

    @patch("cli.normalize_document_with_agent.normalize_input")
    def test_normalize_document_wrapper_stops_with_unresolved_guidance_after_agent(self, normalize_input):
        normalize_input.return_value = _agent_review_model(
            interaction_id="coordinate_convention_selection",
            unresolved_items=[
                {
                    "field": "coordinate_convention",
                    "reason": "Please specify the coordinate convention before continuing.",
                }
            ],
        )

        result = run_document_normalization_with_agent(
            "J1*Sz@0 Sz@1",
            agent_normalized_document={"model_candidates": []},
        )

        self.assertEqual(result["status"], "needs_input")
        self.assertEqual(result["landing_readiness"], "agent_proposed_needs_input")
        self.assertEqual(
            result["agent_inferred"]["unresolved_items"][0]["field"],
            "coordinate_convention",
        )
        self.assertIn("coordinate convention", result["next_step_guidance"]["recommended_action"].lower())

    @patch("cli.simplify_text_input.normalize_freeform_text")
    def test_simplify_text_pipeline_surfaces_agent_result_and_guidance(self, normalize_freeform_text):
        normalize_freeform_text.return_value = _agent_review_model(
            unresolved_items=[
                {
                    "field": "coordinate_convention",
                    "reason": "Please specify the coordinate convention before continuing.",
                }
            ],
        )

        result = run_text_simplification_pipeline("J1*Sz@0 Sz@1")

        self.assertEqual(result["status"], "needs_input")
        self.assertEqual(result["landing_readiness"], "agent_proposed_needs_input")
        self.assertEqual(result["agent_normalization_request"]["id"], "agent_document_normalization")
        self.assertIn("next_step_guidance", result)
        self.assertEqual(
            result["next_step_guidance"]["unresolved_items"][0]["field"],
            "coordinate_convention",
        )

    @patch("cli.run_document_reader_pipeline.run_agent_document_normalization_orchestrator")
    def test_document_reader_pipeline_surfaces_agent_result_and_guidance(self, orchestrator):
        orchestrator.return_value = {
            "status": "needs_input",
            "interaction": {
                "status": "needs_input",
                "id": "agent_fallback_review",
                "question": "The helper still needs review.",
            },
            "normalized_model": _agent_review_model(
                unresolved_items=[
                    {
                        "field": "coordinate_convention",
                        "reason": "Please specify the coordinate convention before continuing.",
                    }
                ]
            ),
        }

        output_dir = Path(tempfile.mkdtemp())
        result = run_document_reader_pipeline("J1*Sz@0 Sz@1", output_dir=output_dir)

        self.assertEqual(result["status"], "needs_input")
        self.assertEqual(result["landing_readiness"], "agent_proposed_needs_input")
        self.assertEqual(result["agent_normalization_request"]["id"], "agent_document_normalization")
        self.assertIn("next_step_guidance", result)

    @patch("cli.run_agent_document_normalization_demo.run_document_normalization_with_agent")
    def test_agent_demo_reports_followup_guidance_when_agent_output_still_needs_input(
        self,
        run_document_normalization_with_agent_mock,
    ):
        run_document_normalization_with_agent_mock.side_effect = [
            {
                "status": "needs_agent_normalization",
                "interaction": {
                    "status": "needs_input",
                    "id": "agent_fallback_review",
                    "question": "Run the agent step.",
                },
                "agent_normalization_request": {
                    "id": "agent_document_normalization",
                    "status": "recommended",
                    "source_kind": "natural_language",
                },
                "landing_readiness": "agent_proposed_needs_input",
                "agent_inferred": {
                    "confidence": {"level": "medium", "reason": "Recovered some structure."},
                    "recognized_items": ["operator expression: J1*Sz@0 Sz@1"],
                    "assumptions": [],
                    "unresolved_items": [],
                    "user_explanation": {
                        "summary": "The helper recognized an operator expression and needs agent normalization."
                    },
                },
                "normalized_model": _agent_review_model(),
                "next_step_guidance": {
                    "summary": "The helper recognized an operator expression and needs agent normalization.",
                    "recommended_action": "Run the agent normalization step and review the result.",
                    "unresolved_items": [],
                },
            },
            {
                "status": "needs_input",
                "interaction": {
                    "status": "needs_input",
                    "id": "coordinate_convention_selection",
                    "question": "Please specify the coordinate convention before continuing.",
                },
                "agent_normalization_request": {
                    "id": "agent_document_normalization",
                    "status": "recommended",
                    "source_kind": "natural_language",
                },
                "landing_readiness": "agent_proposed_needs_input",
                "agent_inferred": {
                    "confidence": {"level": "medium", "reason": "Recovered some structure."},
                    "recognized_items": ["operator expression: J1*Sz@0 Sz@1"],
                    "assumptions": [],
                    "unresolved_items": [
                        {
                            "field": "coordinate_convention",
                            "reason": "Please specify the coordinate convention before continuing.",
                        }
                    ],
                    "user_explanation": {
                        "summary": "The helper found a possible route, but it still needs coordinate_convention."
                    },
                },
                "normalized_model": _agent_review_model(
                    interaction_id="coordinate_convention_selection",
                    unresolved_items=[
                        {
                            "field": "coordinate_convention",
                            "reason": "Please specify the coordinate convention before continuing.",
                        }
                    ],
                ),
                "next_step_guidance": {
                    "summary": "The helper found a possible route, but it still needs coordinate convention.",
                    "recommended_action": "Clarify the coordinate convention and rerun normalization.",
                    "unresolved_items": [
                        {
                            "field": "coordinate_convention",
                            "reason": "Please specify the coordinate convention before continuing.",
                        }
                    ],
                },
            },
        ]

        output_dir = Path(tempfile.mkdtemp())
        result = run_agent_document_normalization_demo(
            "J1*Sz@0 Sz@1",
            output_dir=output_dir,
            agent_normalized_document={"model_candidates": []},
        )

        self.assertEqual(result["status"], "needs_input")
        self.assertEqual(result["landing_readiness"], "agent_proposed_needs_input")
        self.assertEqual(
            result["agent_inferred"]["unresolved_items"][0]["field"],
            "coordinate_convention",
        )
        self.assertIn("next_step_guidance", result)


if __name__ == "__main__":
    unittest.main()
