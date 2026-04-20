import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from lswt.build_sun_gswt_payload import build_sun_gswt_payload


def _serialize_complex(value):
    return {"real": float(value.real), "imag": float(value.imag)}


def _permutation_tensor(local_dimension):
    tensor = []
    for a in range(local_dimension):
        block_b = []
        for b in range(local_dimension):
            block_c = []
            for c in range(local_dimension):
                block_d = []
                for d in range(local_dimension):
                    block_d.append(_serialize_complex(1.0 if (a == d and b == c) else 0.0))
                block_c.append(block_d)
            block_b.append(block_c)
        tensor.append(block_b)
    return tensor


class BuildSunGswtPayloadTests(unittest.TestCase):
    def test_build_payload_exports_local_rays_and_pair_couplings(self):
        model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "orbital_count": 1,
            "local_basis_labels": ["up", "down"],
            "pair_basis_order": "site_i_major_site_j_minor",
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "positions": [[0.0, 0.0, 0.0]],
            "bond_tensors": [
                {
                    "R": [1, 0, 0],
                    "tensor_shape": [2, 2, 2, 2],
                    "pair_matrix": [
                        [_serialize_complex(1.0), _serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(0.0)],
                        [_serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(1.0), _serialize_complex(0.0)],
                        [_serialize_complex(0.0), _serialize_complex(1.0), _serialize_complex(0.0), _serialize_complex(0.0)],
                        [_serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(1.0)],
                    ],
                    "tensor": _permutation_tensor(2),
                }
            ],
        }
        classical_state = {
            "manifold": "CP^(N-1)",
            "supercell_shape": [2, 1, 1],
            "local_rays": [
                {"cell": [0, 0, 0], "vector": [_serialize_complex(1.0), _serialize_complex(0.0)]},
                {"cell": [1, 0, 0], "vector": [_serialize_complex(0.0), _serialize_complex(1.0)]},
            ],
        }

        payload = build_sun_gswt_payload(model, classical_state=classical_state)

        self.assertEqual(payload["payload_version"], 2)
        self.assertEqual(payload["backend"], "Sunny.jl")
        self.assertEqual(payload["mode"], "SUN")
        self.assertEqual(payload["local_dimension"], 2)
        self.assertEqual(payload["local_basis_labels"], ["up", "down"])
        self.assertEqual(len(payload["pair_couplings"]), 1)
        self.assertEqual(len(payload["initial_local_rays"]), 2)
        self.assertEqual(payload["classical_reference"]["state_kind"], "local_rays")
        self.assertEqual(payload["classical_reference"]["manifold"], "CP^(N-1)")
        self.assertEqual(payload["classical_reference"]["frame_construction"], "first-column-is-reference-ray")
        self.assertEqual(payload["backend_requirements"]["sunny_sun_gswt"]["periodic_supercell_required"], True)
        self.assertEqual(
            payload["backend_requirements"]["sunny_sun_gswt"]["single_crystallographic_site_per_cell_required"],
            True,
        )
        self.assertEqual(payload["capabilities"]["spin_wave"], "prototype")
        self.assertEqual(payload["path"]["labels"], ["G", "X"])
        self.assertEqual(payload["q_path"][0], [0.0, 0.0, 0.0])

    def test_build_payload_marks_incommensurate_single_q_ordering(self):
        model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "orbital_count": 1,
            "local_basis_labels": ["up", "down"],
            "pair_basis_order": "site_i_major_site_j_minor",
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "positions": [[0.0, 0.0, 0.0]],
            "rotating_frame_transform": {
                "status": "explicit",
                "kind": "site_phase_rotation",
                "source_frame_kind": "single_q_rotating_frame",
                "source_order_kind": "single_q_helical",
                "wavevector": [0.2, 0.0, 0.0],
                "wavevector_units": "reciprocal_lattice_units",
                "phase_rule": "Q_dot_r_plus_phi_s",
                "phase_origin": "Q_dot_r",
                "sublattice_phase_offsets": {},
                "rotation_axis": "z",
            },
            "bond_tensors": [
                {
                    "R": [1, 0, 0],
                    "tensor_shape": [2, 2, 2, 2],
                    "pair_matrix": [
                        [_serialize_complex(1.0), _serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(0.0)],
                        [_serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(1.0), _serialize_complex(0.0)],
                        [_serialize_complex(0.0), _serialize_complex(1.0), _serialize_complex(0.0), _serialize_complex(0.0)],
                        [_serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(1.0)],
                    ],
                    "tensor": _permutation_tensor(2),
                }
            ],
        }
        classical_state = {
            "ansatz": "single-q-unitary-ray",
            "q_vector": [0.2, 0.0, 0.0],
            "supercell_shape": [3, 1, 1],
            "local_rays": [
                {"cell": [0, 0, 0], "vector": [_serialize_complex(1.0), _serialize_complex(0.0)]},
            ],
        }

        payload = build_sun_gswt_payload(model, classical_state=classical_state)

        self.assertEqual(payload["ordering"]["ansatz"], "single-q-unitary-ray")
        self.assertEqual(payload["ordering"]["q_vector"], [0.2, 0.0, 0.0])
        self.assertEqual(payload["ordering"]["supercell_shape"], [3, 1, 1])
        self.assertEqual(payload["ordering"]["compatibility_with_supercell"]["kind"], "incommensurate")
        self.assertEqual(payload["rotating_frame_transform"]["kind"], "site_phase_rotation")
        self.assertEqual(payload["rotating_frame_transform"]["source_order_kind"], "single_q_helical")
        self.assertEqual(payload["rotating_frame_transform"]["wavevector_units"], "reciprocal_lattice_units")
        self.assertEqual(payload["rotating_frame_realization"]["kind"], "single_q_site_phase_rotation")
        self.assertEqual(payload["quadratic_phase_dressing"]["kind"], "site_phase_gauge_rules")
        self.assertEqual(payload["quadratic_phase_dressing"]["channel_phase_rules"]["normal"], "target_minus_source")
        self.assertEqual(payload["quadratic_phase_dressing"]["channel_phase_rules"]["pair"], "minus_source_minus_target")
        self.assertEqual(payload["quadratic_phase_dressing"]["site_phase_count"], 3)
        self.assertEqual(len(payload["rotating_frame_realization"]["supercell_site_phases"]), 3)
        self.assertAlmostEqual(payload["rotating_frame_realization"]["supercell_site_phases"][1]["phase"], 0.4 * 3.141592653589793)

    def test_build_payload_accepts_nested_canonical_classical_state_object(self):
        model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "orbital_count": 1,
            "local_basis_labels": ["up", "down"],
            "pair_basis_order": "site_i_major_site_j_minor",
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "positions": [[0.0, 0.0, 0.0]],
            "bond_tensors": [
                {
                    "R": [1, 0, 0],
                    "tensor_shape": [2, 2, 2, 2],
                    "pair_matrix": [
                        [_serialize_complex(1.0), _serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(0.0)],
                        [_serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(1.0), _serialize_complex(0.0)],
                        [_serialize_complex(0.0), _serialize_complex(1.0), _serialize_complex(0.0), _serialize_complex(0.0)],
                        [_serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(1.0)],
                    ],
                    "tensor": _permutation_tensor(2),
                }
            ],
        }
        classical_result = {
            "method": "sun-gswt-classical-single-q",
            "classical_state": {
                "schema_version": 1,
                "state_kind": "local_rays",
                "manifold": "CP^(N-1)",
                "supercell_shape": [2, 1, 1],
                "local_rays": [
                    {"cell": [0, 0, 0], "vector": [_serialize_complex(1.0), _serialize_complex(0.0)]},
                    {"cell": [1, 0, 0], "vector": [_serialize_complex(0.0), _serialize_complex(1.0)]},
                ],
                "ordering": {
                    "ansatz": "single-q-unitary-ray",
                    "q_vector": [0.5, 0.0, 0.0],
                    "supercell_shape": [2, 1, 1],
                },
            },
        }

        payload = build_sun_gswt_payload(model, classical_state=classical_result)

        self.assertEqual(payload["supercell_shape"], [2, 1, 1])
        self.assertEqual(len(payload["initial_local_rays"]), 2)
        self.assertEqual(payload["ordering"]["ansatz"], "single-q-unitary-ray")
        self.assertEqual(payload["ordering"]["q_vector"], [0.5, 0.0, 0.0])
        self.assertEqual(payload["ordering"]["compatibility_with_supercell"]["kind"], "commensurate")

    def test_build_payload_accepts_classical_state_result_wrapper(self):
        model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "orbital_count": 1,
            "local_basis_labels": ["up", "down"],
            "pair_basis_order": "site_i_major_site_j_minor",
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "positions": [[0.0, 0.0, 0.0]],
            "bond_tensors": [
                {
                    "R": [1, 0, 0],
                    "tensor_shape": [2, 2, 2, 2],
                    "pair_matrix": [
                        [_serialize_complex(1.0), _serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(0.0)],
                        [_serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(1.0), _serialize_complex(0.0)],
                        [_serialize_complex(0.0), _serialize_complex(1.0), _serialize_complex(0.0), _serialize_complex(0.0)],
                        [_serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(1.0)],
                    ],
                    "tensor": _permutation_tensor(2),
                }
            ],
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "classical_state": {
                    "schema_version": 1,
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "supercell_shape": [2, 1, 1],
                    "local_rays": [
                        {"cell": [0, 0, 0], "vector": [_serialize_complex(1.0), _serialize_complex(0.0)]},
                        {"cell": [1, 0, 0], "vector": [_serialize_complex(0.0), _serialize_complex(1.0)]},
                    ],
                    "ordering": {
                        "ansatz": "single-q-unitary-ray",
                        "q_vector": [0.5, 0.0, 0.0],
                        "supercell_shape": [2, 1, 1],
                    },
                },
            },
        }

        payload = build_sun_gswt_payload(model, classical_state=model)

        self.assertEqual(payload["supercell_shape"], [2, 1, 1])
        self.assertEqual(len(payload["initial_local_rays"]), 2)
        self.assertEqual(payload["ordering"]["q_vector"], [0.5, 0.0, 0.0])

    def test_build_payload_rejects_explicitly_inconsistent_model_convention(self):
        model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "basis_order": "spin_major_orbital_minor",
            "local_dimension": 2,
            "orbital_count": 1,
            "local_basis_labels": ["up", "down"],
            "pair_basis_order": "site_i_major_site_j_minor",
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "positions": [[0.0, 0.0, 0.0]],
            "bond_tensors": [
                {
                    "R": [1, 0, 0],
                    "tensor_shape": [2, 2, 2, 2],
                    "pair_matrix": [
                        [_serialize_complex(1.0), _serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(0.0)],
                        [_serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(1.0), _serialize_complex(0.0)],
                        [_serialize_complex(0.0), _serialize_complex(1.0), _serialize_complex(0.0), _serialize_complex(0.0)],
                        [_serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(1.0)],
                    ],
                    "tensor": _permutation_tensor(2),
                }
            ],
        }

        with self.assertRaises(ValueError):
            build_sun_gswt_payload(model, classical_state=None)

    def test_build_payload_aggregates_reverse_pair_couplings_for_sunny(self):
        model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "orbital_count": 1,
            "local_basis_labels": ["up", "down"],
            "pair_basis_order": "site_i_major_site_j_minor",
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "positions": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
            "bond_tensors": [
                {
                    "source": 0,
                    "target": 1,
                    "R": [1, 0, 0],
                    "tensor_shape": [2, 2, 2, 2],
                    "pair_matrix": [
                        [_serialize_complex(1.0), _serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(0.0)],
                        [_serialize_complex(0.0), _serialize_complex(2.0), _serialize_complex(0.0), _serialize_complex(0.0)],
                        [_serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(3.0), _serialize_complex(0.0)],
                        [_serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(4.0)],
                    ],
                    "tensor": _permutation_tensor(2),
                },
                {
                    "source": 1,
                    "target": 0,
                    "R": [-1, 0, 0],
                    "tensor_shape": [2, 2, 2, 2],
                    "pair_matrix": [
                        [_serialize_complex(10.0), _serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(0.0)],
                        [_serialize_complex(0.0), _serialize_complex(20.0), _serialize_complex(0.0), _serialize_complex(0.0)],
                        [_serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(30.0), _serialize_complex(0.0)],
                        [_serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(40.0)],
                    ],
                    "tensor": _permutation_tensor(2),
                },
            ],
        }
        classical_state = {
            "manifold": "CP^(N-1)",
            "supercell_shape": [1, 1, 1],
            "local_rays": [
                {"cell": [0, 0, 0], "vector": [_serialize_complex(1.0), _serialize_complex(0.0)]},
            ],
        }

        payload = build_sun_gswt_payload(model, classical_state=classical_state)

        self.assertEqual(len(payload["pair_couplings"]), 1)
        diagonal = [payload["pair_couplings"][0]["pair_matrix"][index][index]["real"] for index in range(4)]
        self.assertEqual(diagonal, [11.0, 32.0, 23.0, 44.0])


if __name__ == "__main__":
    unittest.main()
