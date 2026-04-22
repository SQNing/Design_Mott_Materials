import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from lswt.build_lswt_payload import build_lswt_payload


class BuildLswtPayloadTests(unittest.TestCase):
    def test_builder_infers_commensurate_supercell_and_expands_supercell_reference_frames(self):
        model = {
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "lattice_vectors": [
                    [1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.0, 0.0, 1.0],
                ],
                "positions": [[0.0, 0.0, 0.0]],
            },
            "simplified_model": {
                "template": "generic",
                "bonds": [
                    {
                        "source": 0,
                        "target": 0,
                        "vector": [1.0, 0.0, 0.0],
                        "matrix": [
                            [1.0, 0.0, 0.0],
                            [0.0, 1.0, 0.0],
                            [0.0, 0.0, 1.0],
                        ],
                    }
                ],
            },
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "classical_state": {
                    "site_frames": [
                        {
                            "site": 0,
                            "spin_length": 1.0,
                            "direction": [0.0, 0.0, 1.0],
                        }
                    ],
                    "ordering": {
                        "kind": "commensurate",
                        "q_vector": [0.5, 0.0, 0.0],
                    },
                },
            },
        }

        result = build_lswt_payload(model)

        self.assertEqual(result["status"], "ok")
        payload = result["payload"]
        self.assertEqual(payload["supercell_shape"], [2, 1, 1])
        self.assertEqual(
            payload["supercell_reference_frames"],
            [
                {"cell": [0, 0, 0], "site": 0, "spin_length": 1.0, "direction": [0.0, 0.0, 1.0]},
                {"cell": [1, 0, 0], "site": 0, "spin_length": 1.0, "direction": [0.0, 0.0, -1.0]},
            ],
        )

    def test_builder_prefers_explicit_supercell_shape_when_expanding_reference_frames(self):
        model = {
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "lattice_vectors": [
                    [1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.0, 0.0, 1.0],
                ],
                "positions": [[0.0, 0.0, 0.0]],
            },
            "simplified_model": {
                "template": "generic",
                "bonds": [
                    {
                        "source": 0,
                        "target": 0,
                        "vector": [1.0, 0.0, 0.0],
                        "matrix": [
                            [1.0, 0.0, 0.0],
                            [0.0, 1.0, 0.0],
                            [0.0, 0.0, 1.0],
                        ],
                    }
                ],
            },
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "classical_state": {
                    "site_frames": [
                        {
                            "site": 0,
                            "spin_length": 1.0,
                            "direction": [0.0, 0.0, 1.0],
                        }
                    ],
                    "supercell_shape": [4, 1, 1],
                    "ordering": {
                        "kind": "commensurate",
                        "q_vector": [0.5, 0.0, 0.0],
                    },
                },
            },
        }

        result = build_lswt_payload(model)

        self.assertEqual(result["status"], "ok")
        payload = result["payload"]
        self.assertEqual(payload["supercell_shape"], [4, 1, 1])
        self.assertEqual(len(payload["supercell_reference_frames"]), 4)
        self.assertEqual(payload["supercell_reference_frames"][0]["direction"], [0.0, 0.0, 1.0])
        self.assertEqual(payload["supercell_reference_frames"][1]["direction"], [0.0, 0.0, -1.0])
        self.assertEqual(payload["supercell_reference_frames"][2]["direction"], [0.0, 0.0, 1.0])
        self.assertEqual(payload["supercell_reference_frames"][3]["direction"], [0.0, 0.0, -1.0])

    def test_builder_rejects_commensurate_noncollinear_phase_pattern_in_phase1(self):
        model = {
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "lattice_vectors": [
                    [1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.0, 0.0, 1.0],
                ],
                "positions": [[0.0, 0.0, 0.0]],
            },
            "simplified_model": {
                "template": "generic",
                "bonds": [
                    {
                        "source": 0,
                        "target": 0,
                        "vector": [1.0, 0.0, 0.0],
                        "matrix": [
                            [1.0, 0.0, 0.0],
                            [0.0, 1.0, 0.0],
                            [0.0, 0.0, 1.0],
                        ],
                    }
                ],
            },
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "classical_state": {
                    "site_frames": [
                        {
                            "site": 0,
                            "spin_length": 1.0,
                            "direction": [0.0, 0.0, 1.0],
                        }
                    ],
                    "ordering": {
                        "kind": "commensurate",
                        "q_vector": [0.25, 0.0, 0.0],
                    },
                },
            },
        }

        result = build_lswt_payload(model)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "unsupported-lswt-ordering")
        self.assertIn("0/pi", result["error"]["message"])
        self.assertIn("commensurate", result["error"]["message"])

    def test_builder_accepts_spin_frame_classical_state_result(self):
        model = {
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "lattice_vectors": [
                    [1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.0, 0.0, 1.0],
                ],
                "positions": [[0.0, 0.0, 0.0]],
            },
            "simplified_model": {
                "template": "generic",
                "bonds": [
                    {
                        "source": 0,
                        "target": 0,
                        "vector": [1.0, 0.0, 0.0],
                        "matrix": [
                            [1.0, 0.0, 0.0],
                            [0.0, 1.0, 0.0],
                            [0.0, 0.0, 1.0],
                        ],
                    }
                ],
            },
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "classical_state": {
                    "site_frames": [
                        {
                            "site": 0,
                            "spin_length": 0.5,
                            "direction": [0.0, 0.0, 1.0],
                        }
                    ],
                    "ordering": {
                        "ansatz": "single-q-spiral",
                        "q_vector": [0.5, 0.0, 0.0],
                        "supercell_shape": [2, 1, 1],
                    },
                },
            },
            "rotating_frame_transform": {
                "status": "explicit",
                "kind": "site_phase_rotation",
                "source_frame_kind": "single_q_rotating_frame",
                "source_order_kind": "single_q_spiral",
                "wavevector": [0.5, 0.0, 0.0],
                "wavevector_units": "reciprocal_lattice_units",
                "phase_rule": "Q_dot_r_plus_phi_s",
                "phase_origin": "Q_dot_r",
                "sublattice_phase_offsets": {},
                "rotation_axis": "c",
            },
        }

        result = build_lswt_payload(model)

        self.assertEqual(result["status"], "ok")
        payload = result["payload"]
        self.assertEqual(payload["reference_frames"][0]["site"], 0)
        self.assertEqual(payload["ordering"]["q_vector"], [0.5, 0.0, 0.0])

    def test_builder_preserves_single_q_rotating_frame_transform_metadata(self):
        model = {
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "lattice_vectors": [
                    [1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.0, 0.0, 1.0],
                ],
                "positions": [[0.0, 0.0, 0.0]],
            },
            "simplified_model": {
                "template": "generic",
                "bonds": [
                    {
                        "source": 0,
                        "target": 0,
                        "vector": [1.0, 0.0, 0.0],
                        "matrix": [
                            [1.0, 0.0, 0.0],
                            [0.0, 1.0, 0.0],
                            [0.0, 0.0, 1.0],
                        ],
                    }
                ],
            },
            "classical_state": {
                "site_frames": [
                    {
                        "site": 0,
                        "spin_length": 0.5,
                        "direction": [0.0, 0.0, 1.0],
                    }
                ],
                "ordering": {
                    "ansatz": "single-q-spiral",
                    "q_vector": [0.5, 0.0, 0.0],
                    "supercell_shape": [2, 1, 1],
                },
            },
            "rotating_frame_transform": {
                "status": "explicit",
                "kind": "site_phase_rotation",
                "source_frame_kind": "single_q_rotating_frame",
                "source_order_kind": "single_q_spiral",
                "wavevector": [0.5, 0.0, 0.0],
                "wavevector_units": "reciprocal_lattice_units",
                "phase_rule": "Q_dot_r_plus_phi_s",
                "phase_origin": "Q_dot_r",
                "sublattice_phase_offsets": {},
                "rotation_axis": "c",
            },
        }

        result = build_lswt_payload(model)

        self.assertEqual(result["status"], "ok")
        payload = result["payload"]
        self.assertEqual(payload["rotating_frame_transform"]["kind"], "site_phase_rotation")
        self.assertEqual(payload["rotating_frame_transform"]["wavevector"], [0.5, 0.0, 0.0])
        self.assertEqual(payload["rotating_frame_transform"]["wavevector_units"], "reciprocal_lattice_units")
        self.assertEqual(payload["rotating_frame_transform"]["rotation_axis"], "c")
        self.assertEqual(payload["rotating_frame_realization"]["kind"], "single_q_site_phase_rotation")
        self.assertEqual(
            payload["rotating_frame_realization"]["phase_coordinate_semantics"],
            "fractional_direct_positions_with_two_pi_factor",
        )
        self.assertEqual(payload["quadratic_phase_dressing"]["kind"], "site_phase_gauge_rules")
        self.assertEqual(payload["quadratic_phase_dressing"]["channel_phase_rules"]["normal"], "target_minus_source")
        self.assertEqual(payload["quadratic_phase_dressing"]["channel_phase_rules"]["pair"], "minus_source_minus_target")
        self.assertEqual(payload["quadratic_phase_dressing"]["site_phase_count"], 2)
        self.assertEqual(
            payload["rotating_frame_realization"]["supercell_site_phases"],
            [
                {"cell": [0, 0, 0], "site": 0, "phase": 0.0},
                {"cell": [1, 0, 0], "site": 0, "phase": 3.141592653589793},
            ],
        )

    def test_builder_prefers_nested_standardized_contract_over_conflicting_legacy_state(self):
        model = {
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "lattice_vectors": [
                    [1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.0, 0.0, 1.0],
                ],
                "positions": [[0.0, 0.0, 0.0]],
            },
            "simplified_model": {
                "template": "generic",
                "bonds": [
                    {
                        "source": 0,
                        "target": 0,
                        "vector": [1.0, 0.0, 0.0],
                        "matrix": [
                            [1.0, 0.0, 0.0],
                            [0.0, 1.0, 0.0],
                            [0.0, 0.0, 1.0],
                        ],
                    }
                ],
            },
            "classical_state": {
                "site_frames": [
                    {
                        "site": 0,
                        "spin_length": 0.5,
                        "direction": [1.0, 0.0, 0.0],
                    }
                ],
                "ordering": {
                    "ansatz": "legacy-conflict",
                    "q_vector": [0.5, 0.0, 0.0],
                    "supercell_shape": [7, 1, 1],
                },
            },
            "classical": {
                "classical_state_result": {
                    "status": "ok",
                    "role": "final",
                    "classical_state": {
                        "site_frames": [
                            {
                        "site": 0,
                        "spin_length": 0.5,
                        "direction": [0.0, 0.0, 1.0],
                    }
                ],
                "ordering": {
                    "ansatz": "single-q-spiral",
                    "q_vector": [0.5, 0.0, 0.0],
                    "supercell_shape": [2, 1, 1],
                },
                    },
                }
            },
        }

        result = build_lswt_payload(model)

        self.assertEqual(result["status"], "ok")
        payload = result["payload"]
        self.assertEqual(payload["reference_frames"][0]["direction"], [0.0, 0.0, 1.0])
        self.assertEqual(payload["ordering"]["q_vector"], [0.5, 0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
