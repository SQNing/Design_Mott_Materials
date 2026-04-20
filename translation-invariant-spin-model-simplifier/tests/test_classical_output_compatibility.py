import copy
import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from common.classical_output_compatibility import build_classical_output_compatibility_payload  # noqa: E402


def _standardized_contract():
    return {
        "status": "ok",
        "role": "final",
        "solver_family": "retained_local_multiplet",
        "method": "pseudospin-cpn-local-ray-minimize",
        "downstream_compatibility": {
            "lswt": {"status": "blocked", "reason": "requires-spin-frame-site-frames"},
            "gswt": {"status": "ready"},
            "thermodynamics": {"status": "ready"},
        },
        "classical_state": {
            "state_kind": "local_rays",
            "manifold": "CP^(N-1)",
            "supercell_shape": [1, 1, 1],
            "custom_annotation": {"source": "contract"},
            "local_rays": [
                {
                    "cell": [0, 0, 0],
                    "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}],
                }
            ],
        },
    }


class ClassicalOutputCompatibilityTests(unittest.TestCase):
    def test_shim_emits_top_level_and_nested_legacy_mirrors_from_contract(self):
        payload = {"classical_state_result": _standardized_contract()}

        compatibility = build_classical_output_compatibility_payload(payload)

        self.assertEqual(compatibility["classical_state_result"]["method"], "pseudospin-cpn-local-ray-minimize")
        self.assertEqual(compatibility["classical"]["classical_state_result"]["solver_family"], "retained_local_multiplet")
        self.assertEqual(compatibility["classical_state"]["custom_annotation"]["source"], "contract")
        self.assertEqual(compatibility["classical"]["classical_state"]["manifold"], "CP^(N-1)")

    def test_shim_preserves_chosen_and_requested_method_as_compatibility_fields(self):
        payload = {
            "classical_state_result": _standardized_contract(),
            "classical": {
                "chosen_method": "legacy-method",
                "requested_method": "auto",
                "solver_method": "backend-method",
            },
        }

        compatibility = build_classical_output_compatibility_payload(payload)

        self.assertEqual(compatibility["classical"]["chosen_method"], "legacy-method")
        self.assertEqual(compatibility["classical"]["requested_method"], "auto")
        self.assertEqual(compatibility["classical"]["solver_method"], "backend-method")
        self.assertEqual(compatibility["classical_state_result"]["method"], "pseudospin-cpn-local-ray-minimize")

    def test_shim_accepts_bare_standardized_contract_mapping(self):
        contract = _standardized_contract()

        compatibility = build_classical_output_compatibility_payload(contract)

        self.assertEqual(compatibility["classical_state_result"]["method"], "pseudospin-cpn-local-ray-minimize")
        self.assertEqual(compatibility["classical_state"]["supercell_shape"], [1, 1, 1])
        self.assertEqual(compatibility["classical"]["classical_state"]["state_kind"], "local_rays")

    def test_shim_returns_empty_mapping_when_standardized_contract_absent(self):
        payload = {"classical": {"chosen_method": "legacy-method"}}

        compatibility = build_classical_output_compatibility_payload(payload)

        self.assertEqual(compatibility, {})

    def test_shim_does_not_mutate_inputs_or_share_mirror_references(self):
        payload = {
            "classical_state_result": _standardized_contract(),
            "classical": {
                "chosen_method": "legacy-method",
                "requested_method": "auto",
            },
        }
        original = copy.deepcopy(payload)

        compatibility = build_classical_output_compatibility_payload(payload)
        compatibility["classical_state"]["custom_annotation"]["source"] = "mutated"
        compatibility["classical"]["classical_state_result"]["method"] = "changed"

        self.assertEqual(payload, original)
        self.assertEqual(payload["classical_state_result"]["method"], "pseudospin-cpn-local-ray-minimize")
        self.assertEqual(payload["classical_state_result"]["classical_state"]["custom_annotation"]["source"], "contract")


if __name__ == "__main__":
    unittest.main()
