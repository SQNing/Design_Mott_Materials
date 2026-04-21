import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical.build_spin_only_solver_payload import build_spin_only_solver_payload


def _trigonal_lattice_with_shells():
    return {
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
        "family_shell_map": {
            "1": {"shell_index": 1, "distance": 4.05012},
            "2a'": {"shell_index": 6, "distance": 9.736622},
        },
    }


class BuildSpinOnlySolverPayloadV2aTests(unittest.TestCase):
    def test_builder_expands_selected_family_to_full_shell_bond_set(self):
        payload = {
            "normalized_model": {
                "selected_model_candidate": "effective",
                "selected_local_bond_family": "2a'",
                "selected_coordinate_convention": "global_crystallographic",
                "local_hilbert": {"dimension": 3},
                "lattice": _trigonal_lattice_with_shells(),
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

        result = build_spin_only_solver_payload(payload)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["payload"]["bridge_metadata"]["expansion_mode"], "full_shell")
        self.assertGreater(len(result["payload"]["bonds"]), 1)
        self.assertEqual({bond["family"] for bond in result["payload"]["bonds"]}, {"2a'"})
        self.assertEqual({bond["shell_index"] for bond in result["payload"]["bonds"]}, {6})

    def test_builder_assembles_all_families_in_shell_order(self):
        payload = {
            "normalized_model": {
                "selected_model_candidate": "effective",
                "selected_local_bond_family": "all",
                "selected_coordinate_convention": "global_crystallographic",
                "local_hilbert": {"dimension": 3},
                "lattice": _trigonal_lattice_with_shells(),
            },
            "effective_model": {
                "main": [
                    {
                        "type": "xxz_exchange",
                        "family": "2a'",
                        "coefficient_xy": 0.068,
                        "coefficient_z": 0.073,
                    },
                    {
                        "type": "symmetric_exchange_matrix",
                        "family": "1",
                        "matrix": [
                            [-0.397, 0.0, 0.0],
                            [0.0, -0.075, -0.261],
                            [0.0, -0.261, -0.236],
                        ],
                    },
                    {
                        "type": "shell_resolved_exchange",
                        "shells": [
                            {
                                "family": "1",
                                "type": "symmetric_exchange_matrix",
                                "shell_index": 1,
                                "matrix": [
                                    [-0.397, 0.0, 0.0],
                                    [0.0, -0.075, -0.261],
                                    [0.0, -0.261, -0.236],
                                ],
                            },
                            {
                                "family": "2a'",
                                "type": "xxz_exchange",
                                "shell_index": 6,
                                "coefficient_xy": 0.068,
                                "coefficient_z": 0.073,
                            },
                        ],
                    },
                ]
            },
        }

        result = build_spin_only_solver_payload(payload)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["payload"]["bridge_metadata"]["expansion_mode"], "all_families")
        self.assertEqual(result["payload"]["bridge_metadata"]["family_order"], ["1", "2a'"])
        self.assertEqual({bond["family"] for bond in result["payload"]["bonds"]}, {"1", "2a'"})

    def test_builder_prefers_family_blocks_over_shell_summary_for_input_authority(self):
        payload = {
            "normalized_model": {
                "selected_model_candidate": "effective",
                "selected_local_bond_family": "all",
                "selected_coordinate_convention": "global_crystallographic",
                "local_hilbert": {"dimension": 3},
                "lattice": _trigonal_lattice_with_shells(),
            },
            "effective_model": {
                "main": [
                    {
                        "type": "xxz_exchange",
                        "family": "2a'",
                        "coefficient_xy": 0.068,
                        "coefficient_z": 0.073,
                    },
                    {
                        "type": "symmetric_exchange_matrix",
                        "family": "1",
                        "matrix": [
                            [-0.397, 0.0, 0.0],
                            [0.0, -0.075, -0.261],
                            [0.0, -0.261, -0.236],
                        ],
                    },
                    {
                        "type": "shell_resolved_exchange",
                        "shells": [
                            {
                                "family": "1",
                                "type": "symmetric_exchange_matrix",
                                "shell_index": 1,
                                "matrix": [
                                    [-0.397, 0.0, 0.0],
                                    [0.0, -0.075, -0.261],
                                    [0.0, -0.261, -0.236],
                                ],
                            },
                            {
                                "family": "2a'",
                                "type": "xxz_exchange",
                                "shell_index": 6,
                                "coefficient_xy": 0.068,
                                "coefficient_z": 0.073,
                            },
                        ],
                    },
                ]
            },
        }

        result = build_spin_only_solver_payload(payload)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(
            result["payload"]["bridge_metadata"]["input_precedence"],
            "family_blocks_over_shell_summary",
        )
        family_summaries = {
            entry["family"]: entry for entry in result["payload"]["bridge_metadata"]["family_summaries"]
        }
        self.assertEqual(family_summaries["1"]["block_type"], "symmetric_exchange_matrix")

    def test_builder_rejects_all_mode_when_any_family_is_unbridgeable(self):
        payload = {
            "normalized_model": {
                "selected_model_candidate": "effective",
                "selected_local_bond_family": "all",
                "selected_coordinate_convention": "global_crystallographic",
                "local_hilbert": {"dimension": 3},
                "lattice": _trigonal_lattice_with_shells(),
            },
            "effective_model": {
                "main": [
                    {
                        "type": "xxz_exchange",
                        "family": "2a'",
                        "coefficient_xy": 0.068,
                        "coefficient_z": 0.073,
                    },
                    {
                        "type": "higher_multipole_coupling",
                        "family": "1",
                    },
                ]
            },
        }

        with self.assertRaisesRegex(ValueError, "unsupported families"):
            build_spin_only_solver_payload(payload)


if __name__ == "__main__":
    unittest.main()
