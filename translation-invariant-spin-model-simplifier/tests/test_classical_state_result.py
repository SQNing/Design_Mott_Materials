import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from common.classical_state_result import (
    build_diagnostic_classical_result,
    build_final_classical_state_result,
)


class ClassicalStateResultTests(unittest.TestCase):
    def test_spin_frame_final_result_normalizes_to_ready_lswt(self):
        classical_state = {
            "site_frames": [
                {
                    "site": 0,
                    "spin_length": 0.5,
                    "direction": [0.0, 0.0, 1.0],
                }
            ]
        }

        result = build_final_classical_state_result(classical_state)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["role"], "final")
        self.assertEqual(result["downstream_compatibility"]["lswt"]["status"], "ready")
        self.assertEqual(result["downstream_compatibility"]["gswt"]["status"], "blocked")
        self.assertEqual(result["downstream_compatibility"]["thermodynamics"]["status"], "review")

    def test_local_ray_final_result_normalizes_to_ready_gswt(self):
        classical_state = {
            "state_kind": "local_rays",
            "manifold": "CP^(N-1)",
            "supercell_shape": [1, 1, 1],
            "local_rays": [
                {
                    "cell": [0, 0, 0],
                    "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}],
                }
            ],
        }

        result = build_final_classical_state_result(classical_state)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["role"], "final")
        self.assertEqual(result["downstream_compatibility"]["lswt"]["status"], "blocked")
        self.assertEqual(result["downstream_compatibility"]["gswt"]["status"], "ready")
        self.assertEqual(result["downstream_compatibility"]["thermodynamics"]["status"], "ready")

    def test_diagnostic_result_is_marked_diagnostic_and_blocks_downstream(self):
        result = build_diagnostic_classical_result(reason="incommensurate-ordering")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["role"], "diagnostic")
        self.assertEqual(result["reason"], "incommensurate-ordering")
        statuses = {
            result["downstream_compatibility"]["lswt"]["status"],
            result["downstream_compatibility"]["gswt"]["status"],
            result["downstream_compatibility"]["thermodynamics"]["status"],
        }
        self.assertEqual(statuses, {"blocked"})
        self.assertNotIn("ready", statuses)

    def test_declared_local_ray_state_without_rays_is_not_downstream_ready(self):
        classical_state = {
            "state_kind": "local_rays",
            "manifold": "CP^(N-1)",
            "supercell_shape": [1, 1, 1],
            "local_rays": [],
        }

        result = build_final_classical_state_result(classical_state)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["role"], "final")
        self.assertEqual(result["classical_state_semantics"]["state_kind"], "local_rays_declared")
        self.assertEqual(result["classical_state_semantics"]["has_local_rays_data"], False)
        self.assertEqual(result["downstream_compatibility"]["gswt"]["status"], "blocked")
        self.assertEqual(result["downstream_compatibility"]["thermodynamics"]["status"], "blocked")

    def test_final_result_rejects_missing_classical_state(self):
        with self.assertRaises(ValueError):
            build_final_classical_state_result(None)


if __name__ == "__main__":
    unittest.main()
