import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical.build_spin_only_solver_payload import build_spin_only_solver_payload


class BuildSpinOnlySolverPayloadTests(unittest.TestCase):
    def test_builder_maps_selected_xxz_block_to_minimal_classical_payload(self):
        result = build_spin_only_solver_payload(
            {
                "normalized_model": {
                    "selected_model_candidate": "effective",
                    "selected_local_bond_family": "2a'",
                    "selected_coordinate_convention": "global_crystallographic",
                    "local_hilbert": {"dimension": 3},
                    "lattice": {
                        "kind": "trigonal",
                        "dimension": 3,
                        "cell_parameters": {
                            "a": 4.05012,
                            "b": 4.05012,
                            "c": 6.75214,
                            "alpha": 90.0,
                            "beta": 90.0,
                            "gamma": 120.0,
                        },
                        "positions": [[0.0, 0.0, 0.0]],
                        "family_shell_map": {"2a'": {"shell_index": 6, "distance": 9.736622}},
                    },
                },
                "effective_model": {
                    "main": [
                        {
                            "type": "xxz_exchange",
                            "family": "2a'",
                            "coefficient_xy": 0.068,
                            "coefficient_z": 0.073,
                        }
                    ]
                },
            }
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(
            result["payload"]["bonds"][0]["matrix"],
            [
                [0.068, 0.0, 0.0],
                [0.0, 0.068, 0.0],
                [0.0, 0.0, 0.073],
            ],
        )
        self.assertEqual(result["payload"]["bridge_metadata"]["selected_family"], "2a'")

    def test_builder_rejects_all_family_bridge_requests(self):
        with self.assertRaisesRegex(ValueError, "selected_local_bond_family"):
            build_spin_only_solver_payload(
                {
                    "normalized_model": {
                        "selected_local_bond_family": "all",
                    }
                }
            )

    def test_builder_rejects_unsupported_readable_block_types(self):
        with self.assertRaisesRegex(ValueError, "unsupported readable block"):
            build_spin_only_solver_payload(
                {
                    "normalized_model": {
                        "selected_local_bond_family": "2a'",
                        "lattice": {
                            "family_shell_map": {
                                "2a'": {"shell_index": 6, "distance": 9.736622}
                            }
                        },
                    },
                    "effective_model": {
                        "main": [
                            {
                                "type": "higher_multipole_coupling",
                                "family": "2a'",
                            }
                        ]
                    },
                }
            )

    def test_builder_accepts_single_familyless_main_block_after_family_selection(self):
        result = build_spin_only_solver_payload(
            {
                "normalized_model": {
                    "selected_model_candidate": "effective",
                    "selected_local_bond_family": "2a'",
                    "selected_coordinate_convention": "global_crystallographic",
                    "local_hilbert": {"dimension": 3},
                    "lattice": {
                        "kind": "trigonal",
                        "dimension": 3,
                        "cell_parameters": {
                            "a": 4.05012,
                            "b": 4.05012,
                            "c": 6.75214,
                            "alpha": 90.0,
                            "beta": 90.0,
                            "gamma": 120.0,
                        },
                        "positions": [[0.0, 0.0, 0.0]],
                        "family_shell_map": {"2a'": {"shell_index": 6, "distance": 9.736622}},
                    },
                },
                "effective_model": {
                    "main": [
                        {
                            "type": "xxz_exchange",
                            "coefficient_xy": 0.068,
                            "coefficient_z": 0.073,
                        }
                    ]
                },
            }
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["payload"]["bridge_metadata"]["selected_family"], "2a'")
        self.assertEqual(result["payload"]["simplified_model"]["template"], "xxz")
        self.assertEqual(result["payload"]["effective_model"]["main"][0]["type"], "xxz_exchange")


if __name__ == "__main__":
    unittest.main()
