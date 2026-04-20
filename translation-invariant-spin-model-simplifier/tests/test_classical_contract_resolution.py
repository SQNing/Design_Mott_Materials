import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from common.classical_contract_resolution import (  # noqa: E402
    get_classical_state_result,
    get_downstream_stage_compatibility,
    get_downstream_stage_status,
    get_standardized_classical_state,
)


class ClassicalContractResolutionTests(unittest.TestCase):
    def test_get_classical_state_result_resolves_top_level_and_nested(self):
        top_level = {"classical_state_result": {"status": "ok", "role": "final"}}
        nested = {"classical": {"classical_state_result": {"status": "ok", "role": "diagnostic"}}}

        self.assertEqual(get_classical_state_result(top_level), top_level["classical_state_result"])
        self.assertEqual(get_classical_state_result(nested), nested["classical"]["classical_state_result"])

    def test_get_standardized_classical_state_prefers_contract_over_legacy(self):
        standardized = {"site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}]}
        legacy = {"site_frames": [{"site": 0, "spin_length": 1.0, "direction": [1.0, 0.0, 0.0]}]}
        payload = {
            "classical_state_result": {"status": "ok", "role": "final", "classical_state": standardized},
            "classical_state": legacy,
            "classical": {"classical_state": legacy},
        }

        self.assertEqual(get_standardized_classical_state(payload), standardized)

    def test_get_standardized_classical_state_falls_back_to_legacy_state(self):
        legacy = {"site_frames": [{"site": 0, "spin_length": 1.0, "direction": [1.0, 0.0, 0.0]}]}
        payload = {"classical": {"classical_state": legacy}}

        self.assertEqual(get_standardized_classical_state(payload), legacy)

    def test_stage_compatibility_and_status_resolve_from_downstream_compatibility(self):
        classical_state_result = {
            "status": "ok",
            "role": "final",
            "downstream_compatibility": {
                "lswt": {"status": "ready"},
                "gswt": {"status": "blocked", "reason": "requires-local-ray-cpn-state"},
                "thermodynamics": {"status": "review", "reason": "requires-caller-confirmed-support"},
            },
        }

        self.assertEqual(
            get_downstream_stage_compatibility(classical_state_result, "gswt"),
            {"status": "blocked", "reason": "requires-local-ray-cpn-state"},
        )
        self.assertEqual(get_downstream_stage_status(classical_state_result, "gswt"), "blocked")

    def test_stage_helpers_return_none_when_standardized_contract_missing(self):
        payload = {"classical_state": {"site_frames": []}}

        self.assertIsNone(get_classical_state_result(payload))
        self.assertIsNone(get_downstream_stage_compatibility(payload, "lswt"))
        self.assertIsNone(get_downstream_stage_status(payload, "lswt"))


if __name__ == "__main__":
    unittest.main()

