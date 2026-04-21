import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

try:
    from common import document_reader_downstream_orchestration as orchestration  # noqa: E402
except ImportError:
    orchestration = None


def _spin_only_payload(*, with_thermodynamics=True, with_gswt_payload=False):
    payload = {
        "bonds": [
            {
                "source": 0,
                "target": 0,
                "vector": [0, 0, 0],
                "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            }
        ],
        "classical_state_result": {
            "status": "ok",
            "role": "final",
            "method": "spin-only-luttinger-tisza",
            "solver_family": "spin_only_explicit",
        },
    }
    if with_thermodynamics:
        payload["thermodynamics"] = {"temperatures": [0.1, 0.2]}
    if with_gswt_payload:
        payload["gswt_payload"] = {"payload_kind": "python_glswt_local_rays"}
    return payload


class DocumentReaderDownstreamOrchestrationTests(unittest.TestCase):
    def test_collects_all_supported_routes(self):
        self.assertIsNotNone(orchestration)

        route_map = {
            "lswt": {"status": "ready", "enabled": True, "recommended_backend": "linear_spin_wave"},
            "gswt": {"status": "blocked", "enabled": False, "reason": "missing-gswt-payload"},
            "thermodynamics": {
                "status": "review",
                "enabled": True,
                "recommended_backend": "spin_only_thermodynamics",
            },
        }

        with patch.object(
            orchestration,
            "resolve_downstream_stage_route",
            side_effect=lambda payload, stage_name: route_map[stage_name],
        ):
            result = orchestration.orchestrate_document_reader_downstream(_spin_only_payload())

        self.assertEqual(result["downstream_routes"]["lswt"]["status"], "ready")
        self.assertEqual(result["downstream_routes"]["gswt"]["status"], "blocked")
        self.assertEqual(result["downstream_routes"]["thermodynamics"]["status"], "review")

    def test_executes_only_the_approved_stage_subset_by_default(self):
        self.assertIsNotNone(orchestration)

        route_map = {
            "lswt": {"status": "ready", "enabled": True, "recommended_backend": "linear_spin_wave"},
            "gswt": {"status": "blocked", "enabled": False, "reason": "missing-gswt-payload"},
            "thermodynamics": {
                "status": "review",
                "enabled": True,
                "recommended_backend": "spin_only_thermodynamics",
            },
        }

        with (
            patch.object(
                orchestration,
                "resolve_downstream_stage_route",
                side_effect=lambda payload, stage_name: route_map[stage_name],
            ),
            patch.object(
                orchestration,
                "execute_downstream_stage",
                side_effect=lambda payload, stage_name: {"status": "ok", "stage": stage_name},
            ) as execute_stage,
        ):
            result = orchestration.orchestrate_document_reader_downstream(_spin_only_payload())

        self.assertIn("lswt", result["downstream_results"])
        self.assertNotIn("gswt", result["downstream_results"])
        self.assertNotIn("thermodynamics", result["downstream_results"])
        self.assertEqual(
            result["downstream_summary"]["thermodynamics"]["execution_decision"],
            "skipped_review",
        )
        self.assertEqual(execute_stage.call_count, 1)

    def test_marks_thermodynamics_missing_inputs_as_configuration_block(self):
        self.assertIsNotNone(orchestration)

        route_map = {
            "lswt": {"status": "ready", "enabled": True, "recommended_backend": "linear_spin_wave"},
            "gswt": {"status": "blocked", "enabled": False, "reason": "missing-gswt-payload"},
            "thermodynamics": {
                "status": "ready",
                "enabled": True,
                "recommended_backend": "spin_only_thermodynamics",
            },
        }

        with (
            patch.object(
                orchestration,
                "resolve_downstream_stage_route",
                side_effect=lambda payload, stage_name: route_map[stage_name],
            ),
            patch.object(
                orchestration,
                "execute_downstream_stage",
                side_effect=lambda payload, stage_name: {"status": "ok", "stage": stage_name},
            ),
        ):
            result = orchestration.orchestrate_document_reader_downstream(
                _spin_only_payload(with_thermodynamics=False)
            )

        self.assertEqual(
            result["downstream_summary"]["thermodynamics"]["execution_decision"],
            "blocked_missing_inputs",
        )
        self.assertEqual(result["downstream_status"], "partial")

    def test_preserves_route_evidence_when_stage_execution_fails(self):
        self.assertIsNotNone(orchestration)

        route_map = {
            "lswt": {"status": "ready", "enabled": True, "recommended_backend": "linear_spin_wave"},
            "gswt": {"status": "blocked", "enabled": False, "reason": "missing-gswt-payload"},
            "thermodynamics": {
                "status": "review",
                "enabled": True,
                "recommended_backend": "spin_only_thermodynamics",
            },
        }

        def _execute(payload, stage_name):
            if stage_name == "lswt":
                raise RuntimeError("lswt backend exploded")
            return {"status": "ok", "stage": stage_name}

        with (
            patch.object(
                orchestration,
                "resolve_downstream_stage_route",
                side_effect=lambda payload, stage_name: route_map[stage_name],
            ),
            patch.object(orchestration, "execute_downstream_stage", side_effect=_execute),
        ):
            result = orchestration.orchestrate_document_reader_downstream(_spin_only_payload())

        self.assertEqual(result["downstream_status"], "error")
        self.assertEqual(result["downstream_results"]["lswt"]["status"], "error")
        self.assertEqual(result["downstream_routes"]["gswt"]["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
