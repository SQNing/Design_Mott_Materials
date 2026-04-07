import math
import sys
import unittest
from pathlib import Path

import numpy as np

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical.lt_constraint_recovery import (
    recover_classical_state_from_lt,
    reconstruct_single_q_real_space_state,
    strong_constraint_residual,
)


class LTConstraintRecoveryTests(unittest.TestCase):
    def test_single_q_spiral_reconstruction_satisfies_unit_length(self):
        positions = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
        q = [0.25, 0.0, 0.0]
        amplitudes = [1.0 + 0.0j, 1.0 + 0.0j]

        spins = reconstruct_single_q_real_space_state(positions, q, amplitudes)

        for spin in spins:
            self.assertAlmostEqual(float(np.linalg.norm(spin)), 1.0, places=6)
        self.assertAlmostEqual(strong_constraint_residual(spins), 0.0, places=6)

    def test_multi_sublattice_amplitudes_can_fail_strong_constraint(self):
        positions = [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]]
        q = [0.0, 0.0, 0.0]
        amplitudes = [1.0 + 0.0j, 0.3 + 0.0j]

        spins = reconstruct_single_q_real_space_state(positions, q, amplitudes)

        self.assertGreater(strong_constraint_residual(spins), 0.0)

    def test_residual_reports_explicit_sitewise_length_error(self):
        spins = [
            np.array([1.0, 0.0, 0.0]),
            np.array([0.5, 0.0, 0.0]),
        ]

        residual = strong_constraint_residual(spins)

        self.assertAlmostEqual(residual, (1.0 - 0.25) ** 2, places=6)

    def test_recover_classical_state_from_lt_returns_site_frames_and_residual(self):
        model = {
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "sublattices": 2,
                "positions": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
            }
        }

        classical_state = recover_classical_state_from_lt(
            model,
            q=[0.25, 0.0, 0.0],
            amplitudes=[1.0 + 0.0j, 1.0 + 0.0j],
            spin_length=0.5,
            source="lt",
        )

        self.assertEqual(len(classical_state["site_frames"]), 2)
        self.assertAlmostEqual(classical_state["site_frames"][0]["spin_length"], 0.5, places=6)
        self.assertAlmostEqual(
            np.linalg.norm(np.array(classical_state["site_frames"][0]["direction"], dtype=float)),
            1.0,
            places=6,
        )
        self.assertEqual(classical_state["ordering"]["kind"], "commensurate")
        self.assertAlmostEqual(classical_state["constraint_recovery"]["strong_constraint_residual"], 0.0, places=6)

    def test_recover_classical_state_marks_generic_q_as_incommensurate(self):
        model = {
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "sublattices": 1,
                "positions": [[0.0, 0.0, 0.0]],
            }
        }

        classical_state = recover_classical_state_from_lt(
            model,
            q=[0.23, 0.0, 0.0],
            amplitudes=[1.0 + 0.0j],
            spin_length=0.5,
            source="generalized-lt",
        )

        self.assertEqual(classical_state["ordering"]["kind"], "incommensurate")


if __name__ == "__main__":
    unittest.main()
