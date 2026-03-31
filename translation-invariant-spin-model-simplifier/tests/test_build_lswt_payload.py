import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from build_lswt_payload import build_lswt_payload


class BuildLswtPayloadTests(unittest.TestCase):
    def test_build_payload_normalizes_bilinear_bonds_and_reference_frames(self):
        model = {
            "lattice": {"kind": "chain", "dimension": 1, "unit_cell": [0], "sublattices": 1},
            "simplified_model": {
                "template": "xyz",
                "bonds": [
                    {
                        "source": 0,
                        "target": 0,
                        "vector": [1, 0, 0],
                        "matrix": [[1.0, 0.1, 0.0], [0.1, 0.8, 0.0], [0.0, 0.0, 1.2]],
                    }
                ],
            },
            "classical_state": {
                "site_frames": [
                    {"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]},
                ],
                "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                "provenance": {"method": "variational", "converged": True},
            },
            "q_path": [[0.0, 0.0, 0.0], [3.141592653589793, 0.0, 0.0]],
        }
        result = build_lswt_payload(model)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["payload"]["backend"], "Sunny.jl")
        self.assertEqual(result["payload"]["bonds"][0]["exchange_matrix"][0][1], 0.1)
        self.assertEqual(result["payload"]["reference_frames"][0]["spin_length"], 0.5)
        self.assertEqual(result["payload"]["q_path"][-1][0], 3.141592653589793)

    def test_build_payload_rejects_unsupported_non_bilinear_scope(self):
        model = {
            "lattice": {"kind": "chain", "dimension": 1, "unit_cell": [0], "sublattices": 1},
            "simplified_model": {
                "template": "generic",
                "three_body_terms": [
                    {"sites": [0, 1, 2], "coefficient": 1.0, "label": "Sz@0 Sz@1 Sz@2"},
                ],
            },
            "classical_state": {
                "site_frames": [
                    {"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]},
                ],
                "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                "provenance": {"method": "variational", "converged": True},
            },
        }
        result = build_lswt_payload(model)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "unsupported-model-scope")


if __name__ == "__main__":
    unittest.main()
