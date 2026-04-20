import copy
import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from common.classical_contract_resolution import (  # noqa: E402
    get_classical_state_result,
    get_classical_supercell_shape,
    get_classical_ordering,
    get_downstream_stage_compatibility,
    get_downstream_stage_status,
    get_standardized_classical_state,
)
from common.classical_state_result import build_final_classical_state_result  # noqa: E402
from common.cpn_classical_state import resolve_cpn_classical_state_payload  # noqa: E402


class ClassicalContractResolutionTests(unittest.TestCase):
    def test_get_classical_state_result_resolves_top_level_and_nested(self):
        top_level = {"classical_state_result": {"status": "ok", "role": "final"}}
        nested = {"classical": {"classical_state_result": {"status": "ok", "role": "diagnostic"}}}

        self.assertEqual(get_classical_state_result(top_level), top_level["classical_state_result"])
        self.assertEqual(get_classical_state_result(nested), nested["classical"]["classical_state_result"])

    def test_get_classical_state_result_prefers_top_level_wrapper_over_payload_like_fields(self):
        wrapped_contract = {"status": "ok", "role": "final", "classical_state": {"site_frames": []}}
        payload = {
            "status": "partial",
            "classical_state": {"site_frames": [{"site": 0}]},
            "classical_state_result": wrapped_contract,
        }

        self.assertEqual(get_classical_state_result(payload), wrapped_contract)

    def test_get_classical_state_result_accepts_bare_contract_mapping(self):
        bare_contract = {
            "status": "ok",
            "role": "final",
            "classical_state": {"site_frames": [{"site": 0}]},
            "downstream_compatibility": {"lswt": {"status": "ready"}},
        }

        self.assertEqual(get_classical_state_result(bare_contract), bare_contract)

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

    def test_get_standardized_classical_state_prefers_top_level_legacy_state_over_nested_legacy_state(self):
        top_level = {"site_frames": [{"site": 0, "spin_length": 1.0, "direction": [1.0, 0.0, 0.0]}]}
        nested = {"site_frames": [{"site": 1, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}]}
        payload = {"classical_state": top_level, "classical": {"classical_state": nested}}

        self.assertEqual(get_standardized_classical_state(payload), top_level)

    def test_get_standardized_classical_state_can_prefer_nested_legacy_state_for_compatibility(self):
        payload = {
            "classical_state": {},
            "classical": {
                "classical_state": {
                    "site_frames": [{"site": 1, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}]
                }
            },
        }

        self.assertEqual(
            get_standardized_classical_state(payload, prefer_nested_legacy=True),
            payload["classical"]["classical_state"],
        )

    def test_get_classical_state_result_rejects_partial_bare_mapping_without_downstream_compatibility(self):
        partial_mapping = {
            "status": "ok",
            "role": "final",
            "classical_state": {"site_frames": [{"site": 0}]},
        }

        self.assertIsNone(get_classical_state_result(partial_mapping))

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

    def test_stage_helpers_return_none_when_requested_stage_is_missing(self):
        classical_state_result = {
            "status": "ok",
            "role": "final",
            "downstream_compatibility": {"gswt": {"status": "ready"}},
        }

        self.assertIsNone(get_downstream_stage_compatibility(classical_state_result, "lswt"))
        self.assertIsNone(get_downstream_stage_status(classical_state_result, "lswt"))

    def test_stage_helpers_return_none_when_standardized_contract_missing(self):
        payload = {"classical_state": {"site_frames": []}}

        self.assertIsNone(get_classical_state_result(payload))
        self.assertIsNone(get_downstream_stage_compatibility(payload, "lswt"))
        self.assertIsNone(get_downstream_stage_status(payload, "lswt"))

    def test_helpers_do_not_mutate_payload(self):
        payload = {
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "classical_state": {"site_frames": []},
                "downstream_compatibility": {"lswt": {"status": "ready"}},
            },
            "classical_state": {"site_frames": [{"site": 0}]},
            "classical": {"classical_state": {"site_frames": [{"site": 1}]}}
        }
        original = copy.deepcopy(payload)

        get_classical_state_result(payload)
        get_standardized_classical_state(payload)
        get_downstream_stage_compatibility(payload, "lswt")
        get_downstream_stage_status(payload, "lswt")

        self.assertEqual(payload, original)

    def test_helpers_accept_real_contract_builder_output(self):
        classical_state = {
            "site_frames": [
                {
                    "site": 0,
                    "spin_length": 0.5,
                    "direction": [0.0, 0.0, 1.0],
                }
            ]
        }
        contract = build_final_classical_state_result(classical_state)

        self.assertEqual(get_classical_state_result(contract), contract)
        self.assertEqual(get_standardized_classical_state(contract), classical_state)
        self.assertEqual(get_downstream_stage_status(contract, "lswt"), "ready")

    def test_resolve_cpn_classical_state_payload_prefers_standardized_wrapper_over_legacy_state(self):
        standardized_state = {
            "schema_version": 1,
            "state_kind": "local_rays",
            "manifold": "CP^(N-1)",
            "supercell_shape": [2, 1, 1],
            "local_rays": [
                {
                    "cell": [0, 0, 0],
                    "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}],
                }
            ],
        }
        legacy_state = {
            "schema_version": 1,
            "state_kind": "legacy-top-level",
            "supercell_shape": [1, 1, 1],
            "local_rays": [],
        }
        payload = {
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "downstream_compatibility": {"gswt": {"status": "ready"}},
                "classical_state": standardized_state,
            },
            "classical_state": legacy_state,
        }

        resolved = resolve_cpn_classical_state_payload(payload)

        self.assertEqual(resolved["state_kind"], "local_rays")
        self.assertEqual(resolved["manifold"], "CP^(N-1)")
        self.assertEqual(resolved["supercell_shape"], [2, 1, 1])
        self.assertEqual(resolved["local_rays"], standardized_state["local_rays"])

    def test_classical_ordering_and_supercell_shape_prefer_standardized_contract(self):
        standardized_state = {
            "supercell_shape": [3, 1, 1],
            "ordering": {"ansatz": "single-q-spiral", "q_vector": [0.25, 0.0, 0.0], "supercell_shape": [3, 1, 1]},
        }
        legacy_state = {
            "supercell_shape": [7, 1, 1],
            "ordering": {"ansatz": "legacy", "q_vector": [0.5, 0.0, 0.0], "supercell_shape": [7, 1, 1]},
        }
        payload = {
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "downstream_compatibility": {"lswt": {"status": "ready"}},
                "classical_state": standardized_state,
            },
            "classical_state": legacy_state,
            "classical": {"classical_state": legacy_state},
        }

        self.assertEqual(get_classical_ordering(payload), standardized_state["ordering"])
        self.assertEqual(get_classical_supercell_shape(payload), [3, 1, 1])

    def test_classical_ordering_and_supercell_shape_fall_back_to_legacy_state_without_contract(self):
        legacy_state = {
            "supercell_shape": [5, 1, 1],
            "ordering": {"ansatz": "single-q-spiral", "q_vector": [0.2, 0.0, 0.0], "supercell_shape": [5, 1, 1]},
        }
        payload = {"classical": {"classical_state": legacy_state}}

        self.assertEqual(get_classical_ordering(payload, prefer_nested_legacy=True), legacy_state["ordering"])
        self.assertEqual(get_classical_supercell_shape(payload, prefer_nested_legacy=True), [5, 1, 1])


if __name__ == "__main__":
    unittest.main()
