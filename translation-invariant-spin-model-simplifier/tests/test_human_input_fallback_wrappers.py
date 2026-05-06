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

    @patch("cli.simplify_text_input.normalize_freeform_text")
    def test_simplify_text_pipeline_keeps_clear_structured_case_deterministic(self, normalize_freeform_text):
        normalize_freeform_text.return_value = {
            "hamiltonian_description": {
                "representation": {"kind": "operator", "value": "J1*Sz@0 Sz@1"}
            },
            "local_term": {
                "representation": {"kind": "operator", "value": "J1*Sz@0 Sz@1"},
                "support": [0, 1],
            },
            "lattice_description": {"kind": "natural_language", "value": "chain"},
            "lattice": {"kind": "chain", "dimension": 1, "unit_cell": []},
            "coordinate_convention": {
                "frame": "global_cartesian",
                "axis_labels": ["x", "y", "z"],
                "axis_mapping": {},
                "bond_overrides": {},
                "family_overrides": {},
                "quantization_axis": None,
                "raw_description": "",
                "resolved_axis_labels": ["x", "y", "z"],
                "resolved_frame": "global_cartesian",
                "rotation_matrix": None,
                "status": "resolved",
            },
            "magnetic_order": {
                "kind": "unspecified",
                "raw_description": "",
                "reference_frame": {"kind": "laboratory", "phase_origin": None},
                "status": "unspecified",
                "wavevector": [],
                "wavevector_units": None,
            },
            "parameters": {"J1": 1.0},
            "projection": {"status": "not-needed", "heuristic": ["low-energy"]},
            "provenance": {"source_mode": "operator"},
            "rotating_frame": {"kind": "not-needed", "status": "not-needed"},
            "rotating_frame_transform": {"kind": "not-needed", "status": "not-needed"},
            "symmetry_hints": [],
            "system": {"name": "", "units": "unspecified"},
            "timeouts": {
                "classical_solver_seconds": 600,
                "projection_seconds": 300,
                "simplification_seconds": 600,
            },
            "user_notes": "J1*Sz@0 Sz@1",
            "user_required_symmetries": [],
            "allowed_breaking": [],
            "local_hilbert": {"dimension": 2, "uniform": True},
        }

        result = run_text_simplification_pipeline("J1*Sz@0 Sz@1")

        self.assertEqual(result["status"], "ok")
        self.assertNotIn("agent_normalization_request", result)
        self.assertNotIn("landing_readiness", result)
        self.assertNotIn("agent_inferred", result)
        self.assertNotIn("next_step_guidance", result)

    @patch("cli.simplify_text_input.normalize_freeform_text")
    def test_simplify_text_pipeline_suppresses_stale_agent_request_for_clear_case(self, normalize_freeform_text):
        normalize_freeform_text.return_value = {
            "hamiltonian_description": {
                "representation": {"kind": "operator", "value": "J1*Sz@0 Sz@1"}
            },
            "local_term": {
                "representation": {"kind": "operator", "value": "J1*Sz@0 Sz@1"},
                "support": [0, 1],
            },
            "lattice_description": {"kind": "natural_language", "value": "chain"},
            "lattice": {"kind": "chain", "dimension": 1, "unit_cell": []},
            "coordinate_convention": {
                "frame": "global_cartesian",
                "axis_labels": ["x", "y", "z"],
                "axis_mapping": {},
                "bond_overrides": {},
                "family_overrides": {},
                "quantization_axis": None,
                "raw_description": "",
                "resolved_axis_labels": ["x", "y", "z"],
                "resolved_frame": "global_cartesian",
                "rotation_matrix": None,
                "status": "resolved",
            },
            "magnetic_order": {
                "kind": "unspecified",
                "raw_description": "",
                "reference_frame": {"kind": "laboratory", "phase_origin": None},
                "status": "unspecified",
                "wavevector": [],
                "wavevector_units": None,
            },
            "parameters": {"J1": 1.0},
            "projection": {"status": "not-needed", "heuristic": ["low-energy"]},
            "provenance": {"source_mode": "operator"},
            "rotating_frame": {"kind": "not-needed", "status": "not-needed"},
            "rotating_frame_transform": {"kind": "not-needed", "status": "not-needed"},
            "symmetry_hints": [],
            "system": {"name": "", "units": "unspecified"},
            "timeouts": {
                "classical_solver_seconds": 600,
                "projection_seconds": 300,
                "simplification_seconds": 600,
            },
            "user_notes": "J1*Sz@0 Sz@1",
            "user_required_symmetries": [],
            "allowed_breaking": [],
            "local_hilbert": {"dimension": 2, "uniform": True},
            "agent_normalization_request": {
                "id": "agent_document_normalization",
                "status": "recommended",
                "source_kind": "natural_language",
            },
        }

        result = run_text_simplification_pipeline("J1*Sz@0 Sz@1")

        self.assertEqual(result["status"], "ok")
        self.assertNotIn("agent_normalization_request", result)
        self.assertNotIn("landing_readiness", result)
        self.assertNotIn("agent_inferred", result)
        self.assertNotIn("next_step_guidance", result)

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

    @patch("cli.run_document_reader_pipeline.run_agent_document_normalization_orchestrator")
    @patch("cli.run_document_reader_pipeline.run_simplification_from_normalized_model")
    def test_document_reader_pipeline_keeps_clear_structured_case_deterministic(
        self,
        run_simplification_from_normalized_model_mock,
        orchestrator,
    ):
        orchestrator.return_value = {
            "status": "ok",
            "normalized_model": {
                "hamiltonian_description": {
                    "representation": {"kind": "operator", "value": "J1*Sz@0 Sz@1"}
                },
                "local_term": {
                    "representation": {"kind": "operator", "value": "J1*Sz@0 Sz@1"},
                    "support": [0, 1],
                },
                "lattice_description": {"kind": "natural_language", "value": "chain"},
                "lattice": {"kind": "chain", "dimension": 1, "unit_cell": []},
                "coordinate_convention": {
                    "frame": "global_cartesian",
                    "axis_labels": ["x", "y", "z"],
                    "axis_mapping": {},
                    "bond_overrides": {},
                    "family_overrides": {},
                    "quantization_axis": None,
                    "raw_description": "",
                    "resolved_axis_labels": ["x", "y", "z"],
                    "resolved_frame": "global_cartesian",
                    "rotation_matrix": None,
                    "status": "resolved",
                },
                "magnetic_order": {
                    "kind": "unspecified",
                    "raw_description": "",
                    "reference_frame": {"kind": "laboratory", "phase_origin": None},
                    "status": "unspecified",
                    "wavevector": [],
                    "wavevector_units": None,
                },
                "parameters": {"J1": 1.0},
                "projection": {"status": "not-needed", "heuristic": ["low-energy"]},
                "provenance": {"source_mode": "operator"},
                "rotating_frame": {"kind": "not-needed", "status": "not-needed"},
                "rotating_frame_transform": {"kind": "not-needed", "status": "not-needed"},
                "symmetry_hints": [],
                "system": {"name": "", "units": "unspecified"},
                "timeouts": {
                    "classical_solver_seconds": 600,
                    "projection_seconds": 300,
                    "simplification_seconds": 600,
                },
                "user_notes": "J1*Sz@0 Sz@1",
                "user_required_symmetries": [],
                "allowed_breaking": [],
                "local_hilbert": {"dimension": 2, "uniform": True},
                "classical_family": "spin-only",
                "classical_family_metadata": {
                    "family": "spin-only",
                    "solver_family": "spin_only_explicit",
                    "sources": ["payload"],
                    "intrinsic": False,
                },
            },
        }
        run_simplification_from_normalized_model_mock.return_value = {
            "status": "ok",
            "stage": "complete",
            "normalized_model": orchestrator.return_value["normalized_model"],
        }

        output_dir = Path(tempfile.mkdtemp())
        result = run_document_reader_pipeline("J1*Sz@0 Sz@1", output_dir=output_dir)

        self.assertEqual(result["status"], "ok")
        self.assertNotIn("agent_normalization_request", result)
        self.assertNotIn("landing_readiness", result)
        self.assertNotIn("agent_inferred", result)
        self.assertNotIn("next_step_guidance", result)

    @patch("cli.run_document_reader_pipeline.run_agent_document_normalization_orchestrator")
    @patch("cli.run_document_reader_pipeline.run_simplification_from_normalized_model")
    def test_document_reader_pipeline_suppresses_stale_agent_request_for_clear_case(
        self,
        run_simplification_from_normalized_model_mock,
        orchestrator,
    ):
        normalized_model = {
            "hamiltonian_description": {
                "representation": {"kind": "operator", "value": "J1*Sz@0 Sz@1"}
            },
            "local_term": {
                "representation": {"kind": "operator", "value": "J1*Sz@0 Sz@1"},
                "support": [0, 1],
            },
            "lattice_description": {"kind": "natural_language", "value": "chain"},
            "lattice": {"kind": "chain", "dimension": 1, "unit_cell": []},
            "coordinate_convention": {
                "frame": "global_cartesian",
                "axis_labels": ["x", "y", "z"],
                "axis_mapping": {},
                "bond_overrides": {},
                "family_overrides": {},
                "quantization_axis": None,
                "raw_description": "",
                "resolved_axis_labels": ["x", "y", "z"],
                "resolved_frame": "global_cartesian",
                "rotation_matrix": None,
                "status": "resolved",
            },
            "magnetic_order": {
                "kind": "unspecified",
                "raw_description": "",
                "reference_frame": {"kind": "laboratory", "phase_origin": None},
                "status": "unspecified",
                "wavevector": [],
                "wavevector_units": None,
            },
            "parameters": {"J1": 1.0},
            "projection": {"status": "not-needed", "heuristic": ["low-energy"]},
            "provenance": {"source_mode": "operator"},
            "rotating_frame": {"kind": "not-needed", "status": "not-needed"},
            "rotating_frame_transform": {"kind": "not-needed", "status": "not-needed"},
            "symmetry_hints": [],
            "system": {"name": "", "units": "unspecified"},
            "timeouts": {
                "classical_solver_seconds": 600,
                "projection_seconds": 300,
                "simplification_seconds": 600,
            },
            "user_notes": "J1*Sz@0 Sz@1",
            "user_required_symmetries": [],
            "allowed_breaking": [],
            "local_hilbert": {"dimension": 2, "uniform": True},
            "classical_family": "spin-only",
            "classical_family_metadata": {
                "family": "spin-only",
                "solver_family": "spin_only_explicit",
                "sources": ["payload"],
                "intrinsic": False,
            },
            "agent_normalization_request": {
                "id": "agent_document_normalization",
                "status": "recommended",
                "source_kind": "natural_language",
            },
        }
        orchestrator.return_value = {
            "status": "ok",
            "normalized_model": normalized_model,
        }
        run_simplification_from_normalized_model_mock.return_value = {
            "status": "ok",
            "stage": "complete",
            "normalized_model": normalized_model,
        }

        output_dir = Path(tempfile.mkdtemp())
        result = run_document_reader_pipeline("J1*Sz@0 Sz@1", output_dir=output_dir)

        self.assertEqual(result["status"], "ok")
        self.assertNotIn("agent_normalization_request", result)
        self.assertNotIn("landing_readiness", result)
        self.assertNotIn("agent_inferred", result)
        self.assertNotIn("next_step_guidance", result)

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
