import math
import sys
import unittest
from pathlib import Path

import numpy as np


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical.lt_fourier_exchange import fourier_exchange_matrix
from classical.lt_solver import find_lt_ground_state


def _spin_model(*, bonds, sublattices=1):
    return {
        "classical": {"method": "luttinger-tisza"},
        "local_dim": 2,
        "lattice": {
            "sublattices": sublattices,
            "dimension": 1,
            "positions": [[0.0, 0.0, 0.0] for _ in range(sublattices)],
        },
        "bonds": list(bonds),
    }


def _bond(*, source, target, vector, matrix):
    return {
        "source": int(source),
        "target": int(target),
        "vector": [float(value) for value in vector],
        "matrix": [[float(value) for value in row] for row in matrix],
    }


class LtFourierExchangeTests(unittest.TestCase):
    def test_isotropic_heisenberg_chain_remains_scalar_identity_in_spin_space(self):
        model = _spin_model(
            bonds=[
                _bond(
                    source=0,
                    target=0,
                    vector=[1.0, 0.0, 0.0],
                    matrix=[
                        [1.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0],
                        [0.0, 0.0, 1.0],
                    ],
                )
            ]
        )

        jq = fourier_exchange_matrix(model, [0.125, 0.0, 0.0])
        expected = math.sqrt(2.0) * np.eye(3, dtype=complex)

        self.assertEqual(jq.shape, (3, 3))
        self.assertTrue(np.allclose(jq, expected, atol=1.0e-9))

    def test_diagonal_anisotropy_builds_component_resolved_kernel(self):
        model = _spin_model(
            bonds=[
                _bond(
                    source=0,
                    target=0,
                    vector=[0.0, 0.0, 0.0],
                    matrix=[
                        [2.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0],
                        [0.0, 0.0, 0.5],
                    ],
                )
            ]
        )

        jq = fourier_exchange_matrix(model, [0.25, 0.0, 0.0])

        self.assertEqual(jq.shape, (3, 3))
        self.assertTrue(
            np.allclose(
                jq,
                np.diag([2.0, 1.0, 0.5]).astype(complex),
                atol=1.0e-9,
            )
        )

    def test_dm_exchange_contributes_antisymmetric_component_to_kernel(self):
        model = _spin_model(
            bonds=[
                _bond(
                    source=0,
                    target=0,
                    vector=[0.25, 0.0, 0.0],
                    matrix=[
                        [0.0, 1.0, 0.0],
                        [-1.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0],
                    ],
                )
            ]
        )

        jq = fourier_exchange_matrix(model, [1.0, 0.0, 0.0])

        self.assertEqual(jq.shape, (3, 3))
        self.assertTrue(np.allclose(jq, jq.conjugate().T, atol=1.0e-9))
        self.assertAlmostEqual(jq[0, 1].real, 0.0, places=9)
        self.assertAlmostEqual(jq[1, 0].real, 0.0, places=9)
        self.assertGreater(abs(jq[0, 1].imag), 1.0e-9)
        self.assertAlmostEqual(jq[0, 1], -jq[1, 0], places=9)

    def test_two_sublattice_full_tensor_kernel_is_hermitian_and_respects_q_inversion(self):
        tensor = np.array(
            [
                [1.0, 2.0, -0.5],
                [0.25, -1.5, 0.75],
                [1.25, -0.4, 0.3],
            ],
            dtype=float,
        )
        model = _spin_model(
            sublattices=2,
            bonds=[
                _bond(
                    source=0,
                    target=1,
                    vector=[1.0, 0.0, 0.0],
                    matrix=tensor,
                )
            ],
        )

        jq = fourier_exchange_matrix(model, [0.125, 0.0, 0.0])
        j_minus_q = fourier_exchange_matrix(model, [-0.125, 0.0, 0.0])

        self.assertEqual(jq.shape, (6, 6))
        self.assertTrue(np.allclose(jq, jq.conjugate().T, atol=1.0e-9))
        self.assertTrue(np.allclose(j_minus_q, jq.conjugate(), atol=1.0e-9))

    def test_lt_solver_reports_component_resolved_mode_size(self):
        model = _spin_model(
            bonds=[
                _bond(
                    source=0,
                    target=0,
                    vector=[0.0, 0.0, 0.0],
                    matrix=[
                        [2.0, 0.0, 0.0],
                        [0.0, -1.0, 0.0],
                        [0.0, 0.0, 0.5],
                    ],
                )
            ]
        )

        result = find_lt_ground_state(model, mesh_shape=(1, 1, 1))

        self.assertEqual(result["matrix_size"], 3)
        self.assertEqual(len(result["eigenvector"]), 3)


if __name__ == "__main__":
    unittest.main()
