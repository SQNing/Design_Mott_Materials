import copy
import sys
import unittest
from pathlib import Path

import numpy as np


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from common.classical_reference_payloads import (  # noqa: E402
    has_single_q_wrapper_metadata,
    resolve_contract_aware_classical_reference_payload,
    resolve_rich_single_q_wrapper,
)


def _serialize_complex(value):
    return {"real": float(np.real(value)), "imag": float(np.imag(value))}


def _serialize_vector(vector):
    return [_serialize_complex(value) for value in vector]


def _serialize_matrix(matrix):
    return [[_serialize_complex(value) for value in row] for row in matrix]


def _single_q_wrapper():
    classical_state = {
        "schema_version": 1,
        "state_kind": "local_rays",
        "manifold": "CP^(N-1)",
        "supercell_shape": [5, 1, 1],
        "local_rays": [
            {
                "cell": [0, 0, 0],
                "vector": _serialize_vector(np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)),
            }
        ],
        "ordering": {"ansatz": "single-q-unitary-ray", "q_vector": [0.2, 0.0, 0.0]},
    }
    return {
        "method": "sun-gswt-classical-single-q",
        "ansatz": "single-q-unitary-ray",
        "q_vector": [0.2, 0.0, 0.0],
        "ansatz_stationarity": {
            "best_objective": -0.75,
            "optimizer_success": True,
            "optimizer_method": "L-BFGS-B",
            "optimization_mode": "direct-joint",
        },
        "reference_ray": _serialize_vector(np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)),
        "generator_matrix": _serialize_matrix(np.array([[0.0, 0.0], [0.0, 1.0]], dtype=complex)),
        "classical_state": classical_state,
    }


class ClassicalReferencePayloadTests(unittest.TestCase):
    def test_has_single_q_wrapper_metadata_detects_wrapper_fields(self):
        self.assertTrue(has_single_q_wrapper_metadata(_single_q_wrapper()))
        self.assertFalse(has_single_q_wrapper_metadata({"classical_state": {"supercell_shape": [1, 1, 1]}}))

    def test_resolve_rich_single_q_wrapper_accepts_top_level_nested_and_classical_bundle_inputs(self):
        wrapper = _single_q_wrapper()
        nested_top_level = {"classical_state": wrapper}
        nested_classical = {"classical": {"classical_state": wrapper}}

        self.assertEqual(resolve_rich_single_q_wrapper(wrapper), wrapper)
        self.assertEqual(resolve_rich_single_q_wrapper(nested_top_level), wrapper)
        self.assertEqual(resolve_rich_single_q_wrapper(nested_classical), wrapper)

    def test_resolve_contract_aware_payload_prefers_standardized_contract_for_canonical_state(self):
        wrapper = _single_q_wrapper()
        standardized_state = copy.deepcopy(wrapper["classical_state"])
        standardized_state["supercell_shape"] = [3, 1, 1]
        payload = {
            **wrapper,
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "downstream_compatibility": {"gswt": {"status": "ready"}},
                "classical_state": standardized_state,
            },
        }

        resolved = resolve_contract_aware_classical_reference_payload(payload)

        self.assertEqual(resolved["classical_state"], standardized_state)
        self.assertEqual(resolved["reference_ray"], wrapper["reference_ray"])
        self.assertEqual(resolved["generator_matrix"], wrapper["generator_matrix"])

    def test_resolve_contract_aware_payload_accepts_bare_standardized_contract(self):
        standardized_state = _single_q_wrapper()["classical_state"]
        contract = {
            "status": "ok",
            "role": "final",
            "downstream_compatibility": {"gswt": {"status": "ready"}},
            "classical_state": standardized_state,
        }

        self.assertEqual(resolve_contract_aware_classical_reference_payload(contract), standardized_state)

    def test_resolve_contract_aware_payload_accepts_nested_bundle_shape(self):
        wrapper = _single_q_wrapper()
        standardized_state = copy.deepcopy(wrapper["classical_state"])
        standardized_state["supercell_shape"] = [5, 1, 1]
        payload = {
            "classical": {
                "classical_state": {
                    **wrapper,
                    "classical_state": {
                        **wrapper["classical_state"],
                        "supercell_shape": [7, 1, 1],
                    },
                },
                "classical_state_result": {
                    "status": "ok",
                    "role": "final",
                    "downstream_compatibility": {"gswt": {"status": "ready"}},
                    "classical_state": standardized_state,
                },
            }
        }

        resolved = resolve_contract_aware_classical_reference_payload(payload)

        self.assertEqual(resolved["classical_state"], standardized_state)
        self.assertEqual(resolved["q_vector"], [0.2, 0.0, 0.0])

    def test_resolve_contract_aware_payload_returns_original_when_no_contract_or_wrapper_exists(self):
        payload = {"classical_state": {"supercell_shape": [2, 1, 1]}}

        resolved = resolve_contract_aware_classical_reference_payload(payload)

        self.assertIs(resolved, payload)

    def test_helpers_do_not_mutate_input_payloads(self):
        payload = {
            **_single_q_wrapper(),
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "downstream_compatibility": {"gswt": {"status": "ready"}},
                "classical_state": copy.deepcopy(_single_q_wrapper()["classical_state"]),
            },
        }
        original = copy.deepcopy(payload)

        has_single_q_wrapper_metadata(payload)
        resolve_rich_single_q_wrapper(payload)
        resolve_contract_aware_classical_reference_payload(payload)

        self.assertEqual(payload, original)


if __name__ == "__main__":
    unittest.main()
