import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from common.cpn_classical_state import (
    has_spin_frame_classical_state,
    is_cpn_local_ray_classical_state,
    resolve_cpn_classical_state_payload,
    resolve_cpn_local_state,
)


def _ray(cell, entries):
    return {
        "cell": list(cell),
        "vector": [{"real": float(real), "imag": float(imag)} for real, imag in entries],
    }


class CpnClassicalStateSchemaTests(unittest.TestCase):
    def test_resolve_payload_prefers_nested_state_and_backfills_ordering_from_top_level_fields(self):
        payload = {
            "reference_state_kind": "local_rays",
            "manifold": "CP^(N-1)",
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "ansatz": "single-q-unitary-ray",
            "q_vector": [0.5, 0.0, 0.0],
            "classical_state": {
                "schema_version": 1,
                "state_kind": "local_rays",
                "manifold": "CP^(N-1)",
                "supercell_shape": [2, 1, 1],
                "local_rays": [
                    _ray([0, 0, 0], [(1.0, 0.0), (0.0, 0.0)]),
                    _ray([1, 0, 0], [(0.0, 0.0), (1.0, 0.0)]),
                ],
            },
        }

        resolved = resolve_cpn_classical_state_payload(payload)

        self.assertEqual(resolved["schema_version"], 1)
        self.assertEqual(resolved["supercell_shape"], [2, 1, 1])
        self.assertEqual(len(resolved["local_rays"]), 2)
        self.assertEqual(resolved["ordering"]["ansatz"], "single-q-unitary-ray")
        self.assertEqual(resolved["ordering"]["q_vector"], [0.5, 0.0, 0.0])
        self.assertEqual(resolved["ordering"]["supercell_shape"], [2, 1, 1])

    def test_resolve_local_state_uses_default_supercell_for_legacy_top_level_payload(self):
        payload = {
            "local_rays": [
                _ray([0, 0, 0], [(1.0, 0.0), (0.0, 0.0)]),
            ],
        }

        resolved = resolve_cpn_local_state(payload, default_supercell_shape=(3, 1, 1))

        self.assertEqual(resolved["shape"], [3, 1, 1])
        self.assertEqual(len(resolved["local_rays"]), 1)

    def test_resolve_payload_accepts_direct_canonical_classical_state_object(self):
        payload = {
            "schema_version": 1,
            "state_kind": "local_rays",
            "manifold": "CP^(N-1)",
            "supercell_shape": [2, 1, 1],
            "local_rays": [
                _ray([0, 0, 0], [(1.0, 0.0), (0.0, 0.0)]),
                _ray([1, 0, 0], [(0.0, 0.0), (1.0, 0.0)]),
            ],
            "ordering": {
                "ansatz": "single-q-unitary-ray",
                "q_vector": [0.5, 0.0, 0.0],
                "supercell_shape": [2, 1, 1],
            },
        }

        resolved = resolve_cpn_classical_state_payload(payload)

        self.assertEqual(resolved["state_kind"], "local_rays")
        self.assertEqual(resolved["manifold"], "CP^(N-1)")
        self.assertEqual(resolved["supercell_shape"], [2, 1, 1])
        self.assertEqual(len(resolved["local_rays"]), 2)
        self.assertEqual(resolved["ordering"]["ansatz"], "single-q-unitary-ray")

    def test_resolve_payload_infers_local_ray_state_kind_from_manifold_and_local_rays(self):
        payload = {
            "manifold": "CP^(N-1)",
            "supercell_shape": [2, 1, 1],
            "local_rays": [
                _ray([0, 0, 0], [(1.0, 0.0), (0.0, 0.0)]),
                _ray([1, 0, 0], [(0.0, 0.0), (1.0, 0.0)]),
            ],
        }

        resolved = resolve_cpn_classical_state_payload(payload)

        self.assertEqual(resolved["state_kind"], "local_rays")
        self.assertEqual(resolved["manifold"], "CP^(N-1)")
        self.assertEqual(len(resolved["local_rays"]), 2)

    def test_spin_frame_and_cpn_local_ray_predicates_distinguish_reference_state_kinds(self):
        spin_payload = {
            "classical_state": {
                "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}],
                "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
            }
        }
        cpn_payload = {
            "classical_state": {
                "schema_version": 1,
                "state_kind": "local_rays",
                "manifold": "CP^(N-1)",
                "supercell_shape": [2, 1, 1],
                "local_rays": [
                    _ray([0, 0, 0], [(1.0, 0.0), (0.0, 0.0)]),
                    _ray([1, 0, 0], [(0.0, 0.0), (1.0, 0.0)]),
                ],
            }
        }

        self.assertTrue(has_spin_frame_classical_state(spin_payload))
        self.assertFalse(is_cpn_local_ray_classical_state(spin_payload))
        self.assertFalse(has_spin_frame_classical_state(cpn_payload))
        self.assertTrue(is_cpn_local_ray_classical_state(cpn_payload))


if __name__ == "__main__":
    unittest.main()
