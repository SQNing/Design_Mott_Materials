import sys
import unittest
import copy
from pathlib import Path

import numpy as np

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from lswt.build_python_glswt_payload import build_python_glswt_payload


def _serialize_complex(value):
    return {"real": float(value.real), "imag": float(value.imag)}


def _negative_permutation_pair_matrix(local_dimension):
    pair_matrix = []
    for row_left in range(local_dimension):
        for row_right in range(local_dimension):
            row = []
            for col_left in range(local_dimension):
                for col_right in range(local_dimension):
                    value = -1.0 if (row_left == col_right and row_right == col_left) else 0.0
                    row.append(_serialize_complex(value))
            pair_matrix.append(row)
    return pair_matrix


def _serialize_vector(vector):
    return [_serialize_complex(value) for value in vector]


def _serialize_matrix(matrix):
    return [[_serialize_complex(value) for value in row] for row in matrix]


def _single_q_supercell_site_phases(*, q_vector, positions, supercell_shape, site_phase_offsets=None):
    site_phase_offsets = site_phase_offsets or {}
    entries = []
    for cell_x in range(int(supercell_shape[0])):
        for cell_y in range(int(supercell_shape[1])):
            for cell_z in range(int(supercell_shape[2])):
                cell = [cell_x, cell_y, cell_z]
                for site, position in enumerate(positions):
                    phase = 2.0 * np.pi * sum(
                        float(q_vector[axis]) * (float(cell[axis]) + float(position[axis]))
                        for axis in range(3)
                    ) + float(site_phase_offsets.get(site, 0.0))
                    entries.append({"cell": list(cell), "site": int(site), "phase": float(phase)})
    return entries


class BuildPythonGlswtPayloadTests(unittest.TestCase):
    def test_builder_accepts_canonical_local_rays_state(self):
        model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "orbital_count": 1,
            "local_basis_labels": ["up", "down"],
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "positions": [[0.0, 0.0, 0.0]],
            "rotating_frame_transform": {
                "status": "explicit",
                "kind": "site_phase_rotation",
                "source_frame_kind": "single_q_rotating_frame",
                "source_order_kind": "single_q_spiral",
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
                    "pair_matrix": _negative_permutation_pair_matrix(2),
                    "tensor_shape": [2, 2, 2, 2],
                }
            ],
        }
        classical_state = {
            "schema_version": 1,
            "state_kind": "local_rays",
            "manifold": "CP^(N-1)",
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "supercell_shape": [2, 1, 1],
            "local_rays": [
                {"cell": [0, 0, 0], "vector": [_serialize_complex(1.0), _serialize_complex(0.0)]},
                {"cell": [1, 0, 0], "vector": [_serialize_complex(1.0), _serialize_complex(0.0)]},
            ],
        }

        payload = build_python_glswt_payload(model, classical_state=classical_state)

        self.assertEqual(payload["payload_kind"], "python_glswt_local_rays")
        self.assertEqual(payload["backend"], "python")
        self.assertEqual(payload["mode"], "GLSWT")
        self.assertEqual(payload["classical_reference"]["state_kind"], "local_rays")
        self.assertEqual(payload["classical_reference"]["frame_construction"], "first-column-is-reference-ray")
        self.assertEqual(payload["supercell_shape"], [2, 1, 1])
        self.assertEqual(len(payload["initial_local_rays"]), 2)
        self.assertEqual(payload["path"]["labels"], ["G", "X"])
        self.assertEqual(payload["q_path"][0], [0.0, 0.0, 0.0])

    def test_builder_rejects_missing_local_rays(self):
        model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "orbital_count": 1,
            "local_basis_labels": ["up", "down"],
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "positions": [[0.0, 0.0, 0.0]],
            "bond_tensors": [],
        }

        with self.assertRaises(ValueError):
            build_python_glswt_payload(model, classical_state={"supercell_shape": [1, 1, 1]})

    def test_builder_accepts_nested_classical_state(self):
        model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "orbital_count": 1,
            "local_basis_labels": ["up", "down"],
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "positions": [[0.0, 0.0, 0.0]],
            "rotating_frame_transform": {
                "status": "explicit",
                "kind": "site_phase_rotation",
                "source_frame_kind": "single_q_rotating_frame",
                "source_order_kind": "single_q_spiral",
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
                    "pair_matrix": _negative_permutation_pair_matrix(2),
                    "tensor_shape": [2, 2, 2, 2],
                }
            ],
            "classical_state": {
                "schema_version": 1,
                "state_kind": "local_rays",
                "manifold": "CP^(N-1)",
                "basis_order": "orbital_major_spin_minor",
                "pair_basis_order": "site_i_major_site_j_minor",
                "supercell_shape": [1, 1, 1],
                "local_rays": [
                    {"cell": [0, 0, 0], "vector": [_serialize_complex(1.0), _serialize_complex(0.0)]},
                ],
            },
        }

        payload = build_python_glswt_payload(model)

        self.assertEqual(payload["classical_reference"]["state_kind"], "local_rays")
        self.assertEqual(payload["supercell_shape"], [1, 1, 1])

    def test_builder_accepts_classical_state_result_wrapper(self):
        model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "orbital_count": 1,
            "local_basis_labels": ["up", "down"],
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "positions": [[0.0, 0.0, 0.0]],
            "rotating_frame_transform": {
                "status": "explicit",
                "kind": "site_phase_rotation",
                "source_frame_kind": "single_q_rotating_frame",
                "source_order_kind": "single_q_spiral",
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
                    "pair_matrix": _negative_permutation_pair_matrix(2),
                    "tensor_shape": [2, 2, 2, 2],
                }
            ],
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "classical_state": {
                    "schema_version": 1,
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "basis_order": "orbital_major_spin_minor",
                    "pair_basis_order": "site_i_major_site_j_minor",
                    "supercell_shape": [1, 1, 1],
                    "local_rays": [
                        {"cell": [0, 0, 0], "vector": [_serialize_complex(1.0), _serialize_complex(0.0)]},
                    ],
                },
            },
        }

        payload = build_python_glswt_payload(model)

        self.assertEqual(payload["classical_reference"]["state_kind"], "local_rays")
        self.assertEqual(payload["supercell_shape"], [1, 1, 1])

    def test_builder_accepts_bare_standardized_contract_input(self):
        model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "orbital_count": 1,
            "local_basis_labels": ["up", "down"],
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "positions": [[0.0, 0.0, 0.0]],
            "rotating_frame_transform": {
                "status": "explicit",
                "kind": "site_phase_rotation",
                "source_frame_kind": "single_q_rotating_frame",
                "source_order_kind": "single_q_spiral",
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
                    "pair_matrix": _negative_permutation_pair_matrix(2),
                    "tensor_shape": [2, 2, 2, 2],
                }
            ],
        }
        classical_contract = {
            "status": "ok",
            "role": "final",
            "downstream_compatibility": {"gswt": {"status": "ready"}},
            "classical_state": {
                "schema_version": 1,
                "state_kind": "local_rays",
                "manifold": "CP^(N-1)",
                "basis_order": "orbital_major_spin_minor",
                "pair_basis_order": "site_i_major_site_j_minor",
                "supercell_shape": [1, 1, 1],
                "local_rays": [
                    {"cell": [0, 0, 0], "vector": [_serialize_complex(1.0), _serialize_complex(0.0)]},
                ],
            },
        }

        payload = build_python_glswt_payload(model, classical_state=classical_contract)

        self.assertEqual(payload["classical_reference"]["state_kind"], "local_rays")
        self.assertEqual(payload["supercell_shape"], [1, 1, 1])

    def test_builder_emits_native_single_q_z_harmonic_payload_for_single_q_classical_result(self):
        model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "orbital_count": 1,
            "local_basis_labels": ["up", "down"],
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "positions": [[0.0, 0.0, 0.0]],
            "z_harmonic_reference_mode": "refined-retained-local",
            "rotating_frame_transform": {
                "status": "explicit",
                "kind": "site_phase_rotation",
                "source_frame_kind": "single_q_rotating_frame",
                "source_order_kind": "single_q_spiral",
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
                    "pair_matrix": _negative_permutation_pair_matrix(2),
                    "tensor_shape": [2, 2, 2, 2],
                }
            ],
        }
        classical_state = {
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
            "classical_state": {
                "schema_version": 1,
                "state_kind": "local_rays",
                "manifold": "CP^(N-1)",
                "basis_order": "orbital_major_spin_minor",
                "pair_basis_order": "site_i_major_site_j_minor",
                "supercell_shape": [5, 1, 1],
                "local_rays": [
                    {
                        "cell": [0, 0, 0],
                        "vector": _serialize_vector(np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)),
                    }
                ],
                "ordering": {"ansatz": "single-q-unitary-ray", "q_vector": [0.2, 0.0, 0.0]},
            },
        }

        payload = build_python_glswt_payload(model, classical_state=classical_state)

        self.assertEqual(payload["payload_kind"], "python_glswt_single_q_z_harmonic")
        self.assertEqual(payload["q_vector"], [0.2, 0.0, 0.0])
        self.assertEqual(payload["source_classical_ansatz"], "single-q-unitary-ray")
        self.assertEqual(payload["restricted_ansatz_stationarity"]["optimization_mode"], "direct-joint")
        self.assertEqual(payload["z_harmonic_reference_mode"], "refined-retained-local")
        self.assertEqual(payload["rotating_frame_transform"]["kind"], "site_phase_rotation")

    def test_builder_preserves_single_q_wrapper_when_standardized_contract_is_nested(self):
        model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "orbital_count": 1,
            "local_basis_labels": ["up", "down"],
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "positions": [[0.0, 0.0, 0.0]],
            "rotating_frame_transform": {
                "status": "explicit",
                "kind": "site_phase_rotation",
                "source_frame_kind": "single_q_rotating_frame",
                "source_order_kind": "single_q_spiral",
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
                    "pair_matrix": _negative_permutation_pair_matrix(2),
                    "tensor_shape": [2, 2, 2, 2],
                }
            ],
        }
        classical_payload = {
            "schema_version": 1,
            "state_kind": "local_rays",
            "manifold": "CP^(N-1)",
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "supercell_shape": [5, 1, 1],
            "local_rays": [
                {
                    "cell": [0, 0, 0],
                    "vector": _serialize_vector(np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)),
                }
            ],
            "ordering": {"ansatz": "single-q-unitary-ray", "q_vector": [0.2, 0.0, 0.0]},
        }
        wrapped_state = {
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
            "classical_state": dict(classical_payload),
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "downstream_compatibility": {"gswt": {"status": "ready"}},
                "classical_state": dict(classical_payload),
            },
        }

        payload = build_python_glswt_payload(model, classical_state=wrapped_state)

        self.assertEqual(payload["payload_kind"], "python_glswt_single_q_z_harmonic")
        self.assertEqual(payload["source_classical_ansatz"], "single-q-unitary-ray")
        self.assertEqual(payload["q_vector"], [0.2, 0.0, 0.0])
        self.assertEqual(payload["rotating_frame_transform"]["wavevector_units"], "reciprocal_lattice_units")
        self.assertEqual(payload["rotating_frame_transform"]["rotation_axis"], "z")
        self.assertEqual(payload["rotating_frame_realization"]["kind"], "single_q_site_phase_rotation")
        self.assertEqual(payload["quadratic_phase_dressing"]["kind"], "site_phase_gauge_rules")
        self.assertEqual(payload["quadratic_phase_dressing"]["channel_phase_rules"]["normal"], "target_minus_source")
        self.assertEqual(payload["quadratic_phase_dressing"]["channel_phase_rules"]["pair"], "minus_source_minus_target")
        self.assertEqual(payload["quadratic_phase_dressing"]["site_phase_count"], 5)
        self.assertEqual(payload["rotating_frame_realization"]["supercell_site_phases"][0]["cell"], [0, 0, 0])
        self.assertEqual(payload["rotating_frame_realization"]["supercell_site_phases"][1]["cell"], [1, 0, 0])
        self.assertAlmostEqual(payload["rotating_frame_realization"]["supercell_site_phases"][1]["phase"], 0.4 * np.pi)

    def test_builder_accepts_nested_classical_bundle_shape_for_single_q_wrapper(self):
        model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "orbital_count": 1,
            "local_basis_labels": ["up", "down"],
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "positions": [[0.0, 0.0, 0.0]],
            "rotating_frame_transform": {
                "status": "explicit",
                "kind": "site_phase_rotation",
                "source_frame_kind": "single_q_rotating_frame",
                "source_order_kind": "single_q_spiral",
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
                    "pair_matrix": _negative_permutation_pair_matrix(2),
                    "tensor_shape": [2, 2, 2, 2],
                }
            ],
        }
        classical_payload = {
            "schema_version": 1,
            "state_kind": "local_rays",
            "manifold": "CP^(N-1)",
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "supercell_shape": [5, 1, 1],
            "local_rays": [
                {
                    "cell": [0, 0, 0],
                    "vector": _serialize_vector(np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)),
                }
            ],
            "ordering": {"ansatz": "single-q-unitary-ray", "q_vector": [0.2, 0.0, 0.0]},
        }
        bundle_payload = {
            "classical": {
                "classical_state": {
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
                    "classical_state": {
                        **classical_payload,
                        "supercell_shape": [7, 1, 1],
                    },
                },
                "classical_state_result": {
                    "status": "ok",
                    "role": "final",
                    "downstream_compatibility": {"gswt": {"status": "ready"}},
                    "classical_state": dict(classical_payload),
                },
            }
        }

        payload = build_python_glswt_payload(model, classical_state=bundle_payload)

        self.assertEqual(payload["payload_kind"], "python_glswt_single_q_z_harmonic")
        self.assertEqual(payload["source_classical_ansatz"], "single-q-unitary-ray")
        self.assertEqual(payload["q_vector"], [0.2, 0.0, 0.0])
        self.assertEqual(payload["quadratic_phase_dressing"]["site_phase_count"], 5)

    def test_builder_does_not_mutate_single_q_wrapper_input(self):
        model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "orbital_count": 1,
            "local_basis_labels": ["up", "down"],
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "positions": [[0.0, 0.0, 0.0]],
            "rotating_frame_transform": {
                "status": "explicit",
                "kind": "site_phase_rotation",
                "source_frame_kind": "single_q_rotating_frame",
                "source_order_kind": "single_q_spiral",
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
                    "pair_matrix": _negative_permutation_pair_matrix(2),
                    "tensor_shape": [2, 2, 2, 2],
                }
            ],
        }
        classical_payload = {
            "schema_version": 1,
            "state_kind": "local_rays",
            "manifold": "CP^(N-1)",
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "supercell_shape": [5, 1, 1],
            "local_rays": [
                {
                    "cell": [0, 0, 0],
                    "vector": _serialize_vector(np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)),
                }
            ],
            "ordering": {"ansatz": "single-q-unitary-ray", "q_vector": [0.2, 0.0, 0.0]},
        }
        wrapped_state = {
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
            "classical_state": dict(classical_payload),
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "downstream_compatibility": {"gswt": {"status": "ready"}},
                "classical_state": dict(classical_payload),
            },
        }
        original = copy.deepcopy(wrapped_state)

        build_python_glswt_payload(model, classical_state=wrapped_state)

        self.assertEqual(wrapped_state, original)

    def test_builder_preserves_multisite_local_rays_and_pair_coupling_site_indices(self):
        model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "orbital_count": 1,
            "local_basis_labels": ["up", "down"],
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "positions": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
            "bond_tensors": [
                {
                    "source": 0,
                    "target": 1,
                    "R": [0, 0, 0],
                    "pair_matrix": _negative_permutation_pair_matrix(2),
                    "tensor_shape": [2, 2, 2, 2],
                },
                {
                    "source": 1,
                    "target": 0,
                    "R": [0, 0, 0],
                    "pair_matrix": _negative_permutation_pair_matrix(2),
                    "tensor_shape": [2, 2, 2, 2],
                },
            ],
        }
        classical_state = {
            "schema_version": 1,
            "state_kind": "local_rays",
            "manifold": "CP^(N-1)",
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "supercell_shape": [1, 1, 1],
            "local_rays": [
                {"cell": [0, 0, 0], "site": 0, "vector": [_serialize_complex(1.0), _serialize_complex(0.0)]},
                {"cell": [0, 0, 0], "site": 1, "vector": [_serialize_complex(1.0), _serialize_complex(0.0)]},
            ],
        }

        payload = build_python_glswt_payload(model, classical_state=classical_state)

        self.assertEqual(payload["payload_kind"], "python_glswt_local_rays")
        self.assertEqual([entry["site"] for entry in payload["initial_local_rays"]], [0, 1])

    def test_builder_attaches_consistent_rotating_frame_preflight_to_local_rays_payload(self):
        model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "orbital_count": 1,
            "local_basis_labels": ["up", "down"],
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "positions": [[0.0, 0.0, 0.0]],
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
                "rotation_axis": "z",
            },
            "rotating_frame_realization": {
                "status": "explicit",
                "kind": "generic_site_phase_rotation",
                "supercell_shape": [2, 1, 1],
                "supercell_site_phases": _single_q_supercell_site_phases(
                    q_vector=[0.25, 0.0, 0.0],
                    positions=[[0.0, 0.0, 0.0]],
                    supercell_shape=[2, 1, 1],
                ),
            },
            "bond_tensors": [
                {
                    "R": [1, 0, 0],
                    "pair_matrix": _negative_permutation_pair_matrix(2),
                    "tensor_shape": [2, 2, 2, 2],
                }
            ],
        }
        classical_state = {
            "schema_version": 1,
            "state_kind": "local_rays",
            "manifold": "CP^(N-1)",
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "supercell_shape": [2, 1, 1],
            "local_rays": [
                {"cell": [0, 0, 0], "vector": [_serialize_complex(1.0), _serialize_complex(0.0)]},
                {"cell": [1, 0, 0], "vector": [_serialize_complex(1.0), _serialize_complex(0.0)]},
            ],
        }

        payload = build_python_glswt_payload(model, classical_state=classical_state)

        self.assertEqual(payload["payload_kind"], "python_glswt_local_rays")
        self.assertEqual(payload["rotating_frame_metadata_phase_sample_cross_check"]["status"], "consistent")
        self.assertEqual(payload["rotating_frame_metadata_phase_sample_cross_check"]["conflict_sources"], [])
        self.assertEqual(payload["rotating_frame_metadata_phase_sample_cross_check"]["likely_conflicting_path"], "none")

    def test_builder_attaches_single_q_rotating_frame_preflight_conflict(self):
        model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "orbital_count": 1,
            "local_basis_labels": ["up", "down"],
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "positions": [[0.0, 0.0, 0.0]],
            "rotating_frame_transform": {
                "status": "explicit",
                "kind": "site_phase_rotation",
                "source_frame_kind": "single_q_rotating_frame",
                "source_order_kind": "single_q_helical",
                "wavevector": [0.125, 0.0, 0.0],
                "wavevector_units": "reciprocal_lattice_units",
                "phase_rule": "Q_dot_r_plus_phi_s",
                "phase_origin": "Q_dot_r",
                "sublattice_phase_offsets": {},
                "rotation_axis": "z",
            },
            "rotating_frame_realization": {
                "status": "explicit",
                "kind": "generic_site_phase_rotation",
                "supercell_shape": [5, 1, 1],
                "supercell_site_phases": _single_q_supercell_site_phases(
                    q_vector=[0.2, 0.0, 0.0],
                    positions=[[0.0, 0.0, 0.0]],
                    supercell_shape=[5, 1, 1],
                ),
            },
            "bond_tensors": [
                {
                    "R": [1, 0, 0],
                    "pair_matrix": _negative_permutation_pair_matrix(2),
                    "tensor_shape": [2, 2, 2, 2],
                }
            ],
        }
        classical_state = {
            "method": "sun-gswt-classical-single-q",
            "ansatz": "single-q-unitary-ray",
            "q_vector": [0.2, 0.0, 0.0],
            "reference_ray": _serialize_vector(np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)),
            "generator_matrix": _serialize_matrix(np.array([[0.0, 0.0], [0.0, 1.0]], dtype=complex)),
            "classical_state": {
                "schema_version": 1,
                "state_kind": "local_rays",
                "manifold": "CP^(N-1)",
                "basis_order": "orbital_major_spin_minor",
                "pair_basis_order": "site_i_major_site_j_minor",
                "supercell_shape": [5, 1, 1],
                "local_rays": [
                    {
                        "cell": [0, 0, 0],
                        "vector": _serialize_vector(np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)),
                    }
                ],
                "ordering": {"ansatz": "single-q-unitary-ray", "q_vector": [0.2, 0.0, 0.0]},
            },
        }

        payload = build_python_glswt_payload(model, classical_state=classical_state)

        self.assertEqual(payload["payload_kind"], "python_glswt_single_q_z_harmonic")
        self.assertEqual(payload["rotating_frame_metadata_phase_sample_cross_check"]["status"], "conflict")
        self.assertEqual(payload["rotating_frame_metadata_phase_sample_cross_check"]["conflict_sources"], ["wavevector"])
        self.assertEqual(payload["rotating_frame_metadata_phase_sample_cross_check"]["likely_conflicting_path"], "metadata")

    def test_builder_compiles_composite_rotating_frame_realization_into_supercell_site_phases(self):
        model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "orbital_count": 1,
            "local_basis_labels": ["up", "down"],
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "positions": [[0.0, 0.0, 0.0]],
            "rotating_frame_realization": {
                "status": "explicit",
                "kind": "composite_site_phase_rotation",
                "composition_rule": "sum_site_phases",
                "components": [
                    {
                        "wavevector": [0.25, 0.0, 0.0],
                        "wavevector_units": "reciprocal_lattice_units",
                        "phase_rule": "Q_dot_r_plus_phi_s",
                        "rotation_axis": "z",
                        "site_phase_offsets": {},
                        "phase_coordinate_semantics": "fractional_direct_positions_with_two_pi_factor",
                    },
                    {
                        "wavevector": [0.125, 0.0, 0.0],
                        "wavevector_units": "reciprocal_lattice_units",
                        "phase_rule": "Q_dot_r_plus_phi_s",
                        "rotation_axis": "z",
                        "site_phase_offsets": {},
                        "phase_coordinate_semantics": "fractional_direct_positions_with_two_pi_factor",
                    },
                ],
            },
            "bond_tensors": [
                {
                    "R": [1, 0, 0],
                    "pair_matrix": _negative_permutation_pair_matrix(2),
                    "tensor_shape": [2, 2, 2, 2],
                }
            ],
        }
        classical_state = {
            "schema_version": 1,
            "state_kind": "local_rays",
            "manifold": "CP^(N-1)",
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "supercell_shape": [2, 1, 1],
            "local_rays": [
                {"cell": [0, 0, 0], "vector": [_serialize_complex(1.0), _serialize_complex(0.0)]},
                {"cell": [1, 0, 0], "vector": [_serialize_complex(1.0), _serialize_complex(0.0)]},
            ],
        }

        payload = build_python_glswt_payload(model, classical_state=classical_state)

        self.assertEqual(payload["rotating_frame_realization"]["kind"], "composite_site_phase_rotation")
        self.assertEqual(payload["rotating_frame_realization"]["component_count"], 2)
        self.assertEqual(payload["rotating_frame_realization"]["composition_rule"], "sum_site_phases")
        self.assertEqual(payload["rotating_frame_realization"]["supercell_site_phases"][0]["phase"], 0.0)
        self.assertAlmostEqual(payload["rotating_frame_realization"]["supercell_site_phases"][1]["phase"], 0.75 * np.pi)
        self.assertEqual(payload["quadratic_phase_dressing"]["kind"], "site_phase_gauge_rules")
        self.assertEqual(payload["quadratic_phase_dressing"]["source_realization_kind"], "composite_site_phase_rotation")
        self.assertEqual(payload["quadratic_phase_dressing"]["component_count"], 2)

    def test_builder_accepts_nested_single_q_site_ansatz_without_top_level_shared_reference(self):
        model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "orbital_count": 1,
            "local_basis_labels": ["up", "down"],
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "positions": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
            "bond_tensors": [
                {
                    "source": 0,
                    "target": 1,
                    "R": [0, 0, 0],
                    "pair_matrix": _negative_permutation_pair_matrix(2),
                    "tensor_shape": [2, 2, 2, 2],
                },
                {
                    "source": 1,
                    "target": 0,
                    "R": [0, 0, 0],
                    "pair_matrix": _negative_permutation_pair_matrix(2),
                    "tensor_shape": [2, 2, 2, 2],
                },
            ],
        }
        classical_state = {
            "method": "sun-gswt-classical-single-q",
            "ansatz": "single-q-unitary-ray",
            "q_vector": [0.0, 0.0, 0.0],
            "classical_state": {
                "schema_version": 1,
                "state_kind": "local_rays",
                "manifold": "CP^(N-1)",
                "basis_order": "orbital_major_spin_minor",
                "pair_basis_order": "site_i_major_site_j_minor",
                "supercell_shape": [1, 1, 1],
                "local_rays": [
                    {"cell": [0, 0, 0], "site": 0, "vector": [_serialize_complex(1.0), _serialize_complex(0.0)]},
                    {
                        "cell": [0, 0, 0],
                        "site": 1,
                        "vector": _serialize_vector(np.exp(1.0j * np.pi / 3.0) * np.array([1.0, 0.0], dtype=complex)),
                    },
                ],
                "site_ansatz": [
                    {
                        "site": 0,
                        "reference_ray": _serialize_vector(np.array([1.0, 0.0], dtype=complex)),
                        "generator_matrix": _serialize_matrix(np.zeros((2, 2), dtype=complex)),
                    },
                    {
                        "site": 1,
                        "reference_ray": _serialize_vector(
                            np.exp(1.0j * np.pi / 3.0) * np.array([1.0, 0.0], dtype=complex)
                        ),
                        "generator_matrix": _serialize_matrix(np.zeros((2, 2), dtype=complex)),
                    },
                ],
                "ordering": {"ansatz": "single-q-unitary-ray", "q_vector": [0.0, 0.0, 0.0]},
            },
        }

        payload = build_python_glswt_payload(model, classical_state=classical_state)

        self.assertEqual(payload["payload_kind"], "python_glswt_single_q_z_harmonic")
        self.assertEqual(payload["site_count"], 2)
        self.assertEqual(payload["site_reference_mode"], "explicit-site-ansatz")
        self.assertEqual([entry["site"] for entry in payload["source_site_ansatz"]], [0, 1])
        self.assertEqual(sorted({int(item["site"]) for item in payload["z_harmonics"]}), [0, 1])
        site0_h0 = next(item for item in payload["z_harmonics"] if int(item["site"]) == 0 and int(item["harmonic"]) == 0)
        site1_h0 = next(item for item in payload["z_harmonics"] if int(item["site"]) == 1 and int(item["harmonic"]) == 0)
        site0_summary = payload["source_site_ansatz"][0]
        site1_summary = payload["source_site_ansatz"][1]
        site0_harmonic_summary = next(
            item for item in payload["harmonic_diagnostics"]["sites"] if int(item["site"]) == 0
        )
        site1_harmonic_summary = next(
            item for item in payload["harmonic_diagnostics"]["sites"] if int(item["site"]) == 1
        )
        self.assertAlmostEqual(payload["source_site_ansatz"][0]["reference_ray"][0]["real"], 1.0)
        self.assertAlmostEqual(payload["source_site_ansatz"][0]["reference_ray"][0]["imag"], 0.0)
        self.assertAlmostEqual(payload["source_site_ansatz"][1]["reference_ray"][0]["real"], 0.5)
        self.assertAlmostEqual(payload["source_site_ansatz"][1]["reference_ray"][0]["imag"], np.sqrt(3.0) / 2.0)
        self.assertAlmostEqual(site0_summary["reference_ray_norm"], 1.0)
        self.assertAlmostEqual(site1_summary["reference_ray_norm"], 1.0)
        self.assertAlmostEqual(site0_summary["generator_frobenius_norm"], 0.0)
        self.assertAlmostEqual(site1_summary["generator_frobenius_norm"], 0.0)
        self.assertTrue(site0_summary["generator_is_zero"])
        self.assertTrue(site1_summary["generator_is_zero"])
        self.assertAlmostEqual(site0_harmonic_summary["zero_harmonic_weight"], 1.0)
        self.assertAlmostEqual(site1_harmonic_summary["zero_harmonic_weight"], 1.0)
        self.assertAlmostEqual(site0_harmonic_summary["nonzero_harmonic_weight"], 0.0)
        self.assertAlmostEqual(site1_harmonic_summary["nonzero_harmonic_weight"], 0.0)
        self.assertAlmostEqual(site0_h0["vector"][0]["real"], 1.0)
        self.assertAlmostEqual(site0_h0["vector"][0]["imag"], 0.0)
        self.assertAlmostEqual(site1_h0["vector"][0]["real"], 0.5)
        self.assertAlmostEqual(site1_h0["vector"][0]["imag"], np.sqrt(3.0) / 2.0)

    def test_builder_marks_top_level_reference_as_representative_for_multisite_incommensurate_single_q(self):
        model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "orbital_count": 1,
            "local_basis_labels": ["up", "down"],
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "positions": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
            "bond_tensors": [
                {
                    "source": 0,
                    "target": 1,
                    "R": [0, 0, 0],
                    "pair_matrix": _negative_permutation_pair_matrix(2),
                    "tensor_shape": [2, 2, 2, 2],
                },
                {
                    "source": 1,
                    "target": 0,
                    "R": [0, 0, 0],
                    "pair_matrix": _negative_permutation_pair_matrix(2),
                    "tensor_shape": [2, 2, 2, 2],
                },
            ],
        }
        classical_state = {
            "method": "sun-gswt-classical-single-q",
            "ansatz": "single-q-unitary-ray",
            "q_vector": [0.2, 0.0, 0.0],
            "classical_state": {
                "schema_version": 1,
                "state_kind": "local_rays",
                "manifold": "CP^(N-1)",
                "basis_order": "orbital_major_spin_minor",
                "pair_basis_order": "site_i_major_site_j_minor",
                "supercell_shape": [1, 1, 1],
                "local_rays": [
                    {"cell": [0, 0, 0], "site": 0, "vector": _serialize_vector(np.array([1.0, 0.0], dtype=complex))},
                    {
                        "cell": [0, 0, 0],
                        "site": 1,
                        "vector": _serialize_vector(np.array([1.0, 1.0j], dtype=complex) / np.sqrt(2.0)),
                    },
                ],
                "site_ansatz": [
                    {
                        "site": 0,
                        "reference_ray": _serialize_vector(np.array([1.0, 0.0], dtype=complex)),
                        "generator_matrix": _serialize_matrix(np.zeros((2, 2), dtype=complex)),
                    },
                    {
                        "site": 1,
                        "reference_ray": _serialize_vector(np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)),
                        "generator_matrix": _serialize_matrix(np.array([[0.0, 0.0], [0.0, 1.0]], dtype=complex)),
                    },
                ],
                "ordering": {"ansatz": "single-q-unitary-ray", "q_vector": [0.2, 0.0, 0.0]},
            },
        }

        payload = build_python_glswt_payload(model, classical_state=classical_state)

        self.assertEqual(payload["payload_kind"], "python_glswt_single_q_z_harmonic")
        self.assertEqual(payload["site_reference_mode"], "explicit-site-ansatz")
        self.assertEqual(payload["source_reference_scope"], "representative-site-only")
        self.assertEqual(payload["source_reference_site"], 0)
        site0_summary = payload["source_site_ansatz"][0]
        site1_summary = payload["source_site_ansatz"][1]
        site0_harmonic_summary = next(
            item for item in payload["harmonic_diagnostics"]["sites"] if int(item["site"]) == 0
        )
        site1_harmonic_summary = next(
            item for item in payload["harmonic_diagnostics"]["sites"] if int(item["site"]) == 1
        )
        self.assertTrue(site0_summary["generator_is_zero"])
        self.assertFalse(site1_summary["generator_is_zero"])
        self.assertAlmostEqual(site0_harmonic_summary["zero_harmonic_weight"], 1.0)
        self.assertAlmostEqual(site0_harmonic_summary["nonzero_harmonic_weight"], 0.0)
        self.assertAlmostEqual(site1_harmonic_summary["zero_harmonic_weight"], 0.5, places=6)
        self.assertAlmostEqual(site1_harmonic_summary["nonzero_harmonic_weight"], 0.5, places=6)


if __name__ == "__main__":
    unittest.main()
