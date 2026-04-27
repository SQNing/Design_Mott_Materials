import sys
import unittest
from pathlib import Path

import numpy as np


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


def _trigonal_lattice_with_representatives():
    lattice = _trigonal_lattice_with_shells()
    lattice["symmetry_positions"] = [
        [0.0, 0.0, 0.0],
        [1.0 / 3.0, 2.0 / 3.0, 1.0 / 4.0],
        [2.0 / 3.0, 1.0 / 3.0, 3.0 / 4.0],
    ]
    lattice["symmetry_types"] = ["Fe", "I", "I"]
    lattice["family_representative_map"] = {
        "1": {
            "source": 0,
            "target": 0,
            "translation": [1, 0, 0],
            "coordinate_convention": "global_crystallographic",
        },
        "2a'": {
            "source": 0,
            "target": 0,
            "translation": [1, 2, 1],
            "coordinate_convention": "global_crystallographic",
        },
        "2b'": {
            "source": 0,
            "target": 0,
            "translation": [1, 2, -1],
            "coordinate_convention": "global_crystallographic",
        },
    }
    return lattice


class BuildSpinOnlySolverPayloadV2aTests(unittest.TestCase):
    @staticmethod
    def _with_spin_only_family(payload):
        payload = dict(payload)
        payload["classical_family"] = "spin-only"
        return payload

    def test_builder_requires_explicit_spin_only_family(self):
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

        with self.assertRaisesRegex(ValueError, "missing-classical-family"):
            build_spin_only_solver_payload(payload)

    def test_builder_lifts_onsite_terms_to_top_level_payload(self):
        payload = self._with_spin_only_family({
            "normalized_model": {
                "selected_model_candidate": "effective",
                "selected_local_bond_family": "2a'",
                "selected_coordinate_convention": "global_crystallographic",
                "local_hilbert": {"dimension": 3},
                "lattice": _trigonal_lattice_with_shells(),
                "onsite_terms": [
                    {
                        "kind": "quadratic_spin_cartesian",
                        "site_scope": {"kind": "site", "site": 0},
                        "payload": {
                            "matrix": [
                                [0.0, 0.0, 0.0],
                                [0.0, 0.0, 0.0],
                                [0.0, 0.0, -2.165],
                            ]
                        },
                    }
                ],
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
        })

        result = build_spin_only_solver_payload(payload)

        self.assertEqual(result["status"], "ok")
        self.assertIn("onsite_terms", result["payload"])
        self.assertEqual(
            result["payload"]["onsite_terms"][0]["payload"]["matrix"],
            [
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0],
                [0.0, 0.0, -2.165],
            ],
        )

    def test_builder_expands_selected_family_to_full_shell_bond_set(self):
        payload = self._with_spin_only_family({
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
        })

        result = build_spin_only_solver_payload(payload)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["payload"]["bridge_metadata"]["expansion_mode"], "full_shell")
        self.assertGreater(len(result["payload"]["bonds"]), 1)
        self.assertEqual({bond["family"] for bond in result["payload"]["bonds"]}, {"2a'"})
        self.assertEqual({bond["shell_index"] for bond in result["payload"]["bonds"]}, {6})

    def test_builder_rotates_global_family_one_matrix_across_symmetry_related_bonds(self):
        payload = self._with_spin_only_family({
            "normalized_model": {
                "selected_model_candidate": "effective",
                "selected_local_bond_family": "1",
                "selected_coordinate_convention": "global_crystallographic",
                "local_hilbert": {"dimension": 3},
                "lattice": _trigonal_lattice_with_shells(),
            },
            "effective_model": {
                "main": [
                    {
                        "type": "symmetric_exchange_matrix",
                        "family": "1",
                        "matrix": [
                            [-0.397, 0.0, 0.0],
                            [0.0, -0.075, -0.261],
                            [0.0, -0.261, -0.236],
                        ],
                    }
                ]
            },
        })

        result = build_spin_only_solver_payload(payload)

        self.assertEqual(result["status"], "ok")
        bonds_by_vector = {tuple(bond["vector"]): bond for bond in result["payload"]["bonds"]}
        self.assertTrue(
            np.allclose(
                bonds_by_vector[(1, 0, 0)]["matrix"],
                [
                    [-0.397, 0.0, 0.0],
                    [0.0, -0.075, -0.261],
                    [0.0, -0.261, -0.236],
                ],
                atol=1.0e-12,
            )
        )
        self.assertTrue(
            np.allclose(
                bonds_by_vector[(0, 1, 0)]["matrix"],
                [
                    [-0.1555, 0.13943009000929465, 0.2260326303877385],
                    [0.13943009000929465, -0.3165, 0.1305],
                    [0.2260326303877385, 0.1305, -0.236],
                ],
                atol=1.0e-12,
            )
        )
        self.assertTrue(
            np.allclose(
                bonds_by_vector[(1, 1, 0)]["matrix"],
                [
                    [-0.1555, -0.13943009000929465, -0.2260326303877385],
                    [-0.13943009000929465, -0.3165, 0.1305],
                    [-0.2260326303877385, 0.1305, -0.236],
                ],
                atol=1.0e-12,
            )
        )

    def test_builder_assembles_all_families_in_shell_order(self):
        payload = self._with_spin_only_family({
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
        })

        result = build_spin_only_solver_payload(payload)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["payload"]["bridge_metadata"]["expansion_mode"], "all_families")
        self.assertEqual(result["payload"]["bridge_metadata"]["family_order"], ["1", "2a'"])
        self.assertEqual({bond["family"] for bond in result["payload"]["bonds"]}, {"1", "2a'"})

    def test_builder_uses_representative_bond_orbit_instead_of_full_shell_when_available(self):
        payload = self._with_spin_only_family({
            "normalized_model": {
                "selected_model_candidate": "effective",
                "selected_local_bond_family": "2a'",
                "selected_coordinate_convention": "global_crystallographic",
                "local_hilbert": {"dimension": 3},
                "lattice": _trigonal_lattice_with_representatives(),
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
        })

        result = build_spin_only_solver_payload(payload)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["payload"]["bridge_metadata"]["expansion_mode"], "representative_orbit")
        self.assertEqual(
            {tuple(bond["vector"]) for bond in result["payload"]["bonds"]},
            {(1, -1, 1), (1, 2, 1), (2, 1, -1)},
        )
        self.assertNotIn((1, 2, -1), {tuple(bond["vector"]) for bond in result["payload"]["bonds"]})

    def test_builder_assembles_all_families_from_representative_orbits_when_available(self):
        payload = self._with_spin_only_family({
            "normalized_model": {
                "selected_model_candidate": "effective",
                "selected_local_bond_family": "all",
                "selected_coordinate_convention": "global_crystallographic",
                "local_hilbert": {"dimension": 3},
                "lattice": _trigonal_lattice_with_representatives(),
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
                        "type": "xxz_exchange",
                        "family": "2b'",
                        "coefficient_xy": 0.168,
                        "coefficient_z": 0.173,
                    },
                ]
            },
        })

        result = build_spin_only_solver_payload(payload)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["payload"]["bridge_metadata"]["expansion_mode"], "all_families")
        family_summaries = {
            entry["family"]: entry for entry in result["payload"]["bridge_metadata"]["family_summaries"]
        }
        self.assertEqual(family_summaries["2a'"]["expansion_mode"], "representative_orbit")
        self.assertEqual(family_summaries["2b'"]["expansion_mode"], "representative_orbit")
        bonds_by_family = {}
        for bond in result["payload"]["bonds"]:
            bonds_by_family.setdefault(bond["family"], set()).add(tuple(bond["vector"]))
        self.assertEqual(bonds_by_family["2a'"], {(1, -1, 1), (1, 2, 1), (2, 1, -1)})
        self.assertEqual(bonds_by_family["2b'"], {(1, -1, -1), (1, 2, -1), (2, 1, 1)})

    def test_builder_prefers_family_blocks_over_shell_summary_for_input_authority(self):
        payload = self._with_spin_only_family({
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
        })

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
        payload = self._with_spin_only_family({
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
        })

        with self.assertRaisesRegex(ValueError, "unsupported families"):
            build_spin_only_solver_payload(payload)


if __name__ == "__main__":
    unittest.main()
