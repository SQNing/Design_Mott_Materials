import math
import sys
import unittest
from pathlib import Path

import numpy as np

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from lswt.single_q_z_harmonic_adapter import (
    build_single_q_z_harmonic_payload,
    reconstruct_z_from_harmonics,
)


def _serialize_complex(value):
    return {"real": float(np.real(value)), "imag": float(np.imag(value))}


def _serialize_vector(vector):
    return [_serialize_complex(value) for value in vector]


def _serialize_matrix(matrix):
    return [[_serialize_complex(value) for value in row] for row in matrix]


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


class SingleQZHarmonicAdapterTests(unittest.TestCase):
    def test_build_payload_extracts_truncated_z_harmonics_from_single_q_unitary_ray_state(self):
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
            "bond_tensors": [
                {
                    "R": [1, 0, 0],
                    "pair_matrix": _negative_permutation_pair_matrix(2),
                    "tensor_shape": [2, 2, 2, 2],
                }
            ],
        }
        solver_result = {
            "method": "sun-gswt-classical-single-q",
            "ansatz": "single-q-unitary-ray",
            "q_vector": [0.2, 0.0, 0.0],
            "reference_ray": _serialize_vector(np.array([1.0, 1.0], dtype=complex) / math.sqrt(2.0)),
            "generator_matrix": _serialize_matrix(np.array([[0.0, 0.0], [0.0, 1.0]], dtype=complex)),
            "classical_state": {
                "schema_version": 1,
                "state_kind": "local_rays",
                "manifold": "CP^(N-1)",
                "supercell_shape": [5, 1, 1],
                "local_rays": [
                    {"cell": [0, 0, 0], "vector": _serialize_vector(np.array([1.0, 1.0], dtype=complex) / math.sqrt(2.0))}
                ],
                "ordering": {
                    "ansatz": "single-q-unitary-ray",
                    "q_vector": [0.2, 0.0, 0.0],
                },
            },
        }

        payload = build_single_q_z_harmonic_payload(
            model,
            classical_state=solver_result,
            z_harmonic_cutoff=1,
            phase_grid_size=32,
            sideband_cutoff=2,
        )

        self.assertEqual(payload["payload_kind"], "python_glswt_single_q_z_harmonic")
        self.assertEqual(payload["q_vector"], [0.2, 0.0, 0.0])
        self.assertEqual(payload["z_harmonic_cutoff"], 1)
        self.assertEqual(payload["phase_grid_size"], 32)
        self.assertEqual(payload["sideband_cutoff"], 2)
        self.assertEqual(payload["source_classical_ansatz"], "single-q-unitary-ray")
        self.assertEqual(len(payload["z_harmonics"]), 3)
        self.assertLess(payload["harmonic_diagnostics"]["max_reconstruction_error"], 1e-8)
        self.assertLess(payload["harmonic_diagnostics"]["max_norm_error"], 1e-8)

    def test_build_payload_accepts_nested_classical_bundle_shape_for_single_q_wrapper(self):
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
            "bond_tensors": [
                {
                    "R": [1, 0, 0],
                    "pair_matrix": _negative_permutation_pair_matrix(2),
                    "tensor_shape": [2, 2, 2, 2],
                }
            ],
        }
        canonical_state = {
            "schema_version": 1,
            "state_kind": "local_rays",
            "manifold": "CP^(N-1)",
            "supercell_shape": [5, 1, 1],
            "local_rays": [
                {"cell": [0, 0, 0], "vector": _serialize_vector(np.array([1.0, 1.0], dtype=complex) / math.sqrt(2.0))}
            ],
            "ordering": {
                "ansatz": "single-q-unitary-ray",
                "q_vector": [0.2, 0.0, 0.0],
            },
        }
        bundle_payload = {
            "classical": {
                "classical_state": {
                    "method": "sun-gswt-classical-single-q",
                    "ansatz": "single-q-unitary-ray",
                    "q_vector": [0.2, 0.0, 0.0],
                    "reference_ray": _serialize_vector(np.array([1.0, 1.0], dtype=complex) / math.sqrt(2.0)),
                    "generator_matrix": _serialize_matrix(np.array([[0.0, 0.0], [0.0, 1.0]], dtype=complex)),
                    "classical_state": {
                        **canonical_state,
                        "supercell_shape": [7, 1, 1],
                    },
                },
                "classical_state_result": {
                    "status": "ok",
                    "role": "final",
                    "downstream_compatibility": {"gswt": {"status": "ready"}},
                    "classical_state": canonical_state,
                },
            }
        }

        payload = build_single_q_z_harmonic_payload(
            model,
            classical_state=bundle_payload,
            z_harmonic_cutoff=1,
            phase_grid_size=32,
            sideband_cutoff=2,
        )

        self.assertEqual(payload["payload_kind"], "python_glswt_single_q_z_harmonic")
        self.assertEqual(payload["q_vector"], [0.2, 0.0, 0.0])
        self.assertEqual(payload["source_classical_ansatz"], "single-q-unitary-ray")
        self.assertLess(payload["harmonic_diagnostics"]["max_reconstruction_error"], 1e-8)

    def test_reconstruct_z_from_harmonics_matches_exact_single_q_sample(self):
        z_harmonics = {
            -1: np.array([0.0, 0.0], dtype=complex),
            0: np.array([1.0 / math.sqrt(2.0), 0.0], dtype=complex),
            1: np.array([0.0, 1.0 / math.sqrt(2.0)], dtype=complex),
        }

        reconstructed = reconstruct_z_from_harmonics(z_harmonics, phase=0.37 * 2.0 * math.pi)
        expected = np.array(
            [1.0, np.exp(1.0j * 0.37 * 2.0 * math.pi)],
            dtype=complex,
        ) / math.sqrt(2.0)

        self.assertTrue(np.allclose(reconstructed, expected, atol=1e-10))


if __name__ == "__main__":
    unittest.main()
