import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from lswt.build_lswt_payload import build_lswt_payload


class BuildLswtPayloadTests(unittest.TestCase):
    def assertDirectionAlmostEqual(self, actual, expected, places=7):
        self.assertEqual(len(actual), len(expected))
        for actual_value, expected_value in zip(actual, expected):
            self.assertAlmostEqual(actual_value, expected_value, places=places)

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

    def test_builder_emits_lowered_spin_only_onsite_terms(self):
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
            "onsite_terms": [
                {
                    "kind": "quadratic_spin_cartesian",
                    "site_scope": {"kind": "site", "site": 0},
                    "operator_basis": {
                        "family": "spin_cartesian",
                        "components": ["Sx", "Sy", "Sz"],
                    },
                    "frame": {
                        "kind": "global_cartesian",
                        "axes": ["x", "y", "z"],
                    },
                    "payload": {
                        "matrix": [
                            [0.0, 0.0, 0.0],
                            [0.0, 0.0, 0.0],
                            [0.0, 0.0, -2.165],
                        ]
                    },
                }
            ],
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
        self.assertEqual(
            result["payload"]["onsite_terms"],
            [
                {
                    "site": 0,
                    "matrix": [
                        [0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0],
                        [0.0, 0.0, -2.165],
                    ],
                }
            ],
        )

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

    def test_builder_expands_rotating_frame_supercell_reference_frames_for_q_quarter_texture(self):
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
                            "direction": [1.0, 0.0, 0.0],
                        }
                    ],
                    "ordering": {
                        "kind": "commensurate",
                        "q_vector": [0.25, 0.0, 0.0],
                    },
                },
            },
            "rotating_frame_transform": {
                "status": "explicit",
                "kind": "site_phase_rotation",
                "source_frame_kind": "single_q_rotating_frame",
                "source_order_kind": "single_q_spiral",
                "wavevector": [0.25, 0.0, 0.0],
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
        self.assertEqual(payload["supercell_shape"], [4, 1, 1])
        frames = payload["supercell_reference_frames"]
        self.assertEqual(len(frames), 4)
        self.assertDirectionAlmostEqual(frames[0]["direction"], [1.0, 0.0, 0.0])
        self.assertDirectionAlmostEqual(frames[1]["direction"], [0.0, 1.0, 0.0])
        self.assertDirectionAlmostEqual(frames[2]["direction"], [-1.0, 0.0, 0.0])
        self.assertDirectionAlmostEqual(frames[3]["direction"], [0.0, -1.0, 0.0])

    def test_builder_prefers_single_q_reference_contract_over_expanded_supercell_when_q_is_explicitly_resolved(self):
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
                            "direction": [1.0, 0.0, 0.0],
                        }
                    ],
                    "ordering": {
                        "kind": "commensurate",
                        "q_vector": [0.25, 0.0, 0.0],
                    },
                },
            },
            "rotating_frame_realization": {
                "status": "explicit",
                "kind": "single_q_site_phase_rotation",
                "source_transform_kind": "site_phase_rotation",
                "source_order_kind": "single_q_spiral",
                "wavevector": [0.25, 0.0, 0.0],
                "wavevector_units": "reciprocal_lattice_units",
                "phase_rule": "Q_dot_r_plus_phi_s",
                "rotation_axis": [0.0, 0.0, 1.0],
                "site_phase_offsets": {"0": 0.0},
                "phase_coordinate_semantics": "fractional_direct_positions_with_two_pi_factor",
                "supercell_shape": [4, 1, 1],
                "supercell_site_phases": [
                    {"cell": [0, 0, 0], "site": 0, "phase": 0.0},
                    {"cell": [1, 0, 0], "site": 0, "phase": 1.5707963267948966},
                    {"cell": [2, 0, 0], "site": 0, "phase": 3.141592653589793},
                    {"cell": [3, 0, 0], "site": 0, "phase": 4.71238898038469},
                ],
            },
        }

        result = build_lswt_payload(model)

        self.assertEqual(result["status"], "ok")
        payload = result["payload"]
        self.assertEqual(payload["supercell_shape"], [4, 1, 1])
        self.assertNotIn("supercell_reference_frames", payload)
        self.assertEqual(
            payload["single_q_reference_state"],
            {
                "kind": "single_q_spiral",
                "q_vector": [0.25, 0.0, 0.0],
                "rotation_axis": [0.0, 0.0, 1.0],
                "site_phase_offsets": {"0": 0.0},
                "reference_frames": [
                    {"site": 0, "spin_length": 1.0, "direction": [1.0, 0.0, 0.0]}
                ],
            },
        )

    def test_builder_falls_back_to_expanded_supercell_when_only_discrete_phase_table_is_available(self):
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
                            "direction": [1.0, 0.0, 0.0],
                        }
                    ],
                    "ordering": {
                        "kind": "commensurate",
                        "q_vector": [0.25, 0.0, 0.0],
                    },
                },
            },
            "rotating_frame_realization": {
                "status": "explicit",
                "kind": "single_q_site_phase_rotation",
                "source_transform_kind": "site_phase_rotation",
                "source_order_kind": "single_q_spiral",
                "wavevector": [0.25, 0.0, 0.0],
                "wavevector_units": "reciprocal_lattice_units",
                "phase_rule": "Q_dot_r_plus_phi_s",
                "rotation_axis": [0.0, 0.0, 1.0],
                "phase_coordinate_semantics": "fractional_direct_positions_with_two_pi_factor",
                "supercell_shape": [4, 1, 1],
                "supercell_site_phases": [
                    {"cell": [0, 0, 0], "site": 0, "phase": 0.0},
                    {"cell": [1, 0, 0], "site": 0, "phase": 1.5707963267948966},
                    {"cell": [2, 0, 0], "site": 0, "phase": 3.141592653589793},
                    {"cell": [3, 0, 0], "site": 0, "phase": 4.71238898038469},
                ],
            },
        }

        result = build_lswt_payload(model)

        self.assertEqual(result["status"], "ok")
        payload = result["payload"]
        self.assertNotIn("single_q_reference_state", payload)
        self.assertEqual(payload["supercell_shape"], [4, 1, 1])
        frames = payload["supercell_reference_frames"]
        self.assertEqual(len(frames), 4)
        self.assertDirectionAlmostEqual(frames[0]["direction"], [1.0, 0.0, 0.0])
        self.assertDirectionAlmostEqual(frames[1]["direction"], [0.0, 1.0, 0.0])
        self.assertDirectionAlmostEqual(frames[2]["direction"], [-1.0, 0.0, 0.0])
        self.assertDirectionAlmostEqual(frames[3]["direction"], [0.0, -1.0, 0.0])

    def test_builder_expands_triangular_120_degree_rotating_frame_reference_frames(self):
        model = {
            "lattice": {
                "kind": "triangular",
                "dimension": 2,
                "lattice_vectors": [
                    [1.0, 0.0, 0.0],
                    [0.5, 0.8660254037844386, 0.0],
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
                    },
                    {
                        "source": 0,
                        "target": 0,
                        "vector": [0.0, 1.0, 0.0],
                        "matrix": [
                            [1.0, 0.0, 0.0],
                            [0.0, 1.0, 0.0],
                            [0.0, 0.0, 1.0],
                        ],
                    },
                    {
                        "source": 0,
                        "target": 0,
                        "vector": [1.0, -1.0, 0.0],
                        "matrix": [
                            [1.0, 0.0, 0.0],
                            [0.0, 1.0, 0.0],
                            [0.0, 0.0, 1.0],
                        ],
                    },
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
                            "direction": [1.0, 0.0, 0.0],
                        }
                    ],
                    "ordering": {
                        "kind": "commensurate",
                        "q_vector": [1.0 / 3.0, 2.0 / 3.0, 0.0],
                    },
                    "supercell_shape": [3, 3, 1],
                },
            },
            "rotating_frame_transform": {
                "status": "explicit",
                "kind": "site_phase_rotation",
                "source_frame_kind": "single_q_rotating_frame",
                "source_order_kind": "single_q_spiral",
                "wavevector": [1.0 / 3.0, 2.0 / 3.0, 0.0],
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
        self.assertEqual(payload["supercell_shape"], [3, 3, 1])
        frames = payload["supercell_reference_frames"]
        self.assertEqual(len(frames), 9)
        frame_map = {(tuple(frame["cell"]), frame["site"]): frame["direction"] for frame in frames}
        self.assertDirectionAlmostEqual(frame_map[((0, 0, 0), 0)], [1.0, 0.0, 0.0])
        self.assertDirectionAlmostEqual(frame_map[((1, 0, 0), 0)], [-0.5, 0.8660254037844386, 0.0])
        self.assertDirectionAlmostEqual(frame_map[((0, 1, 0), 0)], [-0.5, -0.8660254037844386, 0.0])
        self.assertDirectionAlmostEqual(frame_map[((1, 1, 0), 0)], [1.0, 0.0, 0.0])

    def test_builder_rejects_incomplete_rotating_frame_supercell_phase_coverage(self):
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
                            "direction": [1.0, 0.0, 0.0],
                        }
                    ],
                    "supercell_shape": [4, 1, 1],
                    "ordering": {
                        "kind": "commensurate",
                        "q_vector": [0.25, 0.0, 0.0],
                    },
                },
            },
            "rotating_frame_realization": {
                "status": "explicit",
                "kind": "single_q_site_phase_rotation",
                "source_transform_kind": "site_phase_rotation",
                "source_order_kind": "single_q_spiral",
                "wavevector": [0.25, 0.0, 0.0],
                "wavevector_units": "reciprocal_lattice_units",
                "phase_rule": "Q_dot_r_plus_phi_s",
                "rotation_axis": "c",
                "phase_coordinate_semantics": "fractional_direct_positions_with_two_pi_factor",
                "supercell_shape": [4, 1, 1],
                "supercell_site_phases": [
                    {"cell": [0, 0, 0], "site": 0, "phase": 0.0},
                    {"cell": [1, 0, 0], "site": 0, "phase": 1.5707963267948966},
                    {"cell": [2, 0, 0], "site": 0, "phase": 3.141592653589793},
                ],
            },
        }

        result = build_lswt_payload(model)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "unsupported-lswt-ordering")
        self.assertIn("phase", result["error"]["message"])
        self.assertIn("coverage", result["error"]["message"])

    def test_builder_keeps_phase1_sign_flip_fallback_without_rotating_frame_metadata(self):
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

    def test_builder_keeps_collinear_sign_flip_when_rotating_frame_wrapper_only_relabels_fei2_like_state(self):
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
            "rotating_frame_realization": {
                "status": "explicit",
                "kind": "single_q_site_phase_rotation",
                "source_transform_kind": "site_phase_rotation",
                "source_order_kind": "single_q_spiral",
                "wavevector": [0.5, 0.0, 0.0],
                "wavevector_units": "reciprocal_lattice_units",
                "phase_rule": "Q_dot_r_plus_phi_s",
                "rotation_axis": "c",
                "phase_coordinate_semantics": "fractional_direct_positions_with_two_pi_factor",
                "supercell_shape": [2, 1, 1],
                "supercell_site_phases": [
                    {"cell": [0, 0, 0], "site": 0, "phase": 0.0},
                    {"cell": [1, 0, 0], "site": 0, "phase": 3.141592653589793},
                ],
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

    def test_builder_consumes_nested_variational_phase_fit_realization_for_single_q_contract(self):
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
                            "direction": [1.0, 0.0, 0.0],
                        }
                    ],
                    "ordering": {
                        "kind": "commensurate",
                        "q_vector": [0.25, 0.0, 0.0],
                    },
                },
            },
            "variational_result": {
                "phase_fit": {
                    "realization": {
                        "status": "explicit",
                        "kind": "single_q_site_phase_rotation",
                        "source_transform_kind": "site_phase_rotation",
                        "source_order_kind": "single_q_spiral",
                        "wavevector": [0.25, 0.0, 0.0],
                        "wavevector_units": "reciprocal_lattice_units",
                        "phase_rule": "Q_dot_r_plus_phi_s",
                        "rotation_axis": [0.0, 0.0, 1.0],
                        "site_phase_offsets": {"0": 0.0},
                        "phase_coordinate_semantics": "fractional_direct_positions_with_two_pi_factor",
                        "supercell_shape": [4, 1, 1],
                        "supercell_site_phases": [
                            {"cell": [0, 0, 0], "site": 0, "phase": 0.0},
                            {"cell": [1, 0, 0], "site": 0, "phase": 1.5707963267948966},
                            {"cell": [2, 0, 0], "site": 0, "phase": 3.141592653589793},
                            {"cell": [3, 0, 0], "site": 0, "phase": 4.71238898038469},
                        ],
                    }
                }
            },
        }

        result = build_lswt_payload(model)

        self.assertEqual(result["status"], "ok")
        payload = result["payload"]
        self.assertIn("single_q_reference_state", payload)
        self.assertNotIn("supercell_reference_frames", payload)
        self.assertEqual(payload["single_q_reference_state"]["q_vector"], [0.25, 0.0, 0.0])

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

    def test_builder_derives_quantum_spin_from_local_dim_instead_of_classical_spin_length(self):
        model = {
            "local_dim": 3,
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
                        "kind": "commensurate",
                        "q_vector": [0.5, 0.0, 0.0],
                    },
                },
            },
        }

        result = build_lswt_payload(model)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["payload"]["moments"][0]["spin"], 1.0)
        self.assertEqual(result["payload"]["reference_frames"][0]["spin_length"], 0.5)

    def test_builder_promotes_spin_half_local_dim_when_spin_only_onsite_term_requires_spin_one(self):
        model = {
            "local_dim": 2,
            "onsite_terms": [
                {
                    "kind": "quadratic_spin_cartesian",
                    "site_scope": {"kind": "site", "site": 0},
                    "operator_basis": {
                        "family": "spin_cartesian",
                        "components": ["Sx", "Sy", "Sz"],
                    },
                    "frame": {
                        "kind": "global_cartesian",
                        "axes": ["x", "y", "z"],
                    },
                    "payload": {
                        "matrix": [
                            [0.0, 0.0, 0.0],
                            [0.0, 0.0, 0.0],
                            [0.0, 0.0, -2.165],
                        ]
                    },
                }
            ],
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
                        "kind": "commensurate",
                        "q_vector": [0.5, 0.0, 0.0],
                    },
                },
            },
        }

        result = build_lswt_payload(model)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["payload"]["moments"][0]["spin"], 1.0)


if __name__ == "__main__":
    unittest.main()
