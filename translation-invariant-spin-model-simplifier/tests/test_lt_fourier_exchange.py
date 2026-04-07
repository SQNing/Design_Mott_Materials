import sys
import unittest
from pathlib import Path

import numpy as np

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical.lt_fourier_exchange import fourier_exchange_matrix


class LTFourierExchangeTests(unittest.TestCase):
    def test_single_sublattice_chain_returns_one_by_one_matrix(self):
        model = {
            "bonds": [
                {
                    "source": 0,
                    "target": 0,
                    "vector": [1, 0, 0],
                    "matrix": [
                        [1.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0],
                        [0.0, 0.0, 1.0],
                    ],
                }
            ]
        }

        jq = fourier_exchange_matrix(model, [0.5, 0.0, 0.0])

        self.assertEqual(jq.shape, (1, 1))
        self.assertAlmostEqual(float(jq[0, 0].real), -2.0, places=6)
        self.assertAlmostEqual(float(jq[0, 0].imag), 0.0, places=6)

    def test_multi_sublattice_matrix_has_expected_complex_phase_structure(self):
        model = {
            "bonds": [
                {
                    "source": 0,
                    "target": 1,
                    "vector": [0, 0, 0],
                    "matrix": [
                        [1.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0],
                        [0.0, 0.0, 1.0],
                    ],
                },
                {
                    "source": 0,
                    "target": 1,
                    "vector": [1, 0, 0],
                    "matrix": [
                        [2.0, 0.0, 0.0],
                        [0.0, 2.0, 0.0],
                        [0.0, 0.0, 2.0],
                    ],
                },
            ]
        }

        jq = fourier_exchange_matrix(model, [0.25, 0.0, 0.0])

        self.assertEqual(jq.shape, (2, 2))
        self.assertAlmostEqual(float(jq[0, 1].real), 1.0, places=6)
        self.assertAlmostEqual(float(jq[0, 1].imag), -2.0, places=6)
        self.assertAlmostEqual(float(jq[1, 0].real), 1.0, places=6)
        self.assertAlmostEqual(float(jq[1, 0].imag), 2.0, places=6)

    def test_exchange_matrix_is_hermitian_for_all_q(self):
        model = {
            "bonds": [
                {
                    "source": 0,
                    "target": 1,
                    "vector": [1, 1, 0],
                    "matrix": [
                        [0.7, 0.0, 0.0],
                        [0.0, 0.7, 0.0],
                        [0.0, 0.0, 0.7],
                    ],
                },
                {
                    "source": 1,
                    "target": 2,
                    "vector": [0, 0, 0],
                    "matrix": [
                        [1.3, 0.0, 0.0],
                        [0.0, 1.3, 0.0],
                        [0.0, 0.0, 1.3],
                    ],
                },
            ]
        }

        jq = fourier_exchange_matrix(model, [0.173, 0.271, 0.0])

        self.assertTrue(np.allclose(jq, jq.conj().T))


if __name__ == "__main__":
    unittest.main()
