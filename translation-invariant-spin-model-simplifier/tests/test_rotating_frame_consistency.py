import sys
import unittest
from pathlib import Path

import numpy as np

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from common.rotating_frame_consistency import (
    infer_single_q_from_supercell_site_phases,
    local_rays_rotating_frame_metadata_phase_sample_cross_check,
    metadata_phase_sample_cross_check,
)
from common.rotating_frame_realization import resolve_rotating_frame_realization


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


class RotatingFrameConsistencyTests(unittest.TestCase):
    def test_realization_resolves_supercell_shape_from_standardized_classical_state_result(self):
        model = {
            "positions": [[0.0, 0.0, 0.0]],
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
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
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "classical_state": {
                    "supercell_shape": [3, 1, 1],
                    "ordering": {
                        "q_vector": [0.25, 0.0, 0.0],
                        "supercell_shape": [3, 1, 1],
                    },
                },
            },
        }

        realization = resolve_rotating_frame_realization(model)

        self.assertEqual(realization["supercell_shape"], [3, 1, 1])
        self.assertEqual(len(realization["supercell_site_phases"]), 3)
        self.assertAlmostEqual(realization["supercell_site_phases"][1]["phase"], 0.5 * np.pi)

    def test_realization_prefers_standardized_supercell_shape_over_conflicting_legacy_wrapper(self):
        model = {
            "positions": [[0.0, 0.0, 0.0]],
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
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
            "classical_state": {
                "supercell_shape": [7, 1, 1],
                "ordering": {
                    "q_vector": [0.5, 0.0, 0.0],
                    "supercell_shape": [7, 1, 1],
                },
                "classical_state": {
                    "supercell_shape": [9, 1, 1],
                    "ordering": {
                        "q_vector": [0.5, 0.0, 0.0],
                        "supercell_shape": [9, 1, 1],
                    },
                },
            },
            "classical": {
                "classical_state_result": {
                    "status": "ok",
                    "role": "final",
                    "classical_state": {
                        "supercell_shape": [3, 1, 1],
                        "ordering": {
                            "q_vector": [0.25, 0.0, 0.0],
                            "supercell_shape": [3, 1, 1],
                        },
                    },
                }
            },
        }

        realization = resolve_rotating_frame_realization(model)

        self.assertEqual(realization["supercell_shape"], [3, 1, 1])
        self.assertEqual(len(realization["supercell_site_phases"]), 3)

    def test_infer_single_q_from_supercell_site_phases_recovers_q_and_offsets(self):
        payload = {
            "positions": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
            "site_count": 2,
        }
        realization = {
            "supercell_shape": [3, 1, 1],
            "supercell_site_phases": _single_q_supercell_site_phases(
                q_vector=[0.2, 0.0, 0.0],
                positions=payload["positions"],
                supercell_shape=[3, 1, 1],
                site_phase_offsets={0: 0.1, 1: -0.2},
            ),
        }

        summary = infer_single_q_from_supercell_site_phases(payload, realization)

        self.assertEqual(summary["phase_sample_status"], "single-q-compatible")
        self.assertEqual(summary["phase_sample_inferred_q_vector"], [0.2, 0.0, 0.0])
        self.assertEqual(summary["phase_sample_effective_site_phase_offsets"], {"0": 0.1, "1": -0.2})

    def test_metadata_phase_sample_cross_check_reports_wavevector_conflict(self):
        cross_check = metadata_phase_sample_cross_check(
            single_q_q_vector=[0.2, 0.0, 0.0],
            rotating_frame_wavevector=[0.125, 0.0, 0.0],
            realization_status="single-q-compatible",
            effective_site_phase_offsets={"0": 0.1, "1": -0.2},
            source_kind="rotating_frame_transform",
            phase_sample_summary={
                "phase_sample_status": "single-q-compatible",
                "phase_sample_inferred_q_vector": [0.2, 0.0, 0.0],
                "phase_sample_effective_site_phase_offsets": {"0": 0.1, "1": -0.2},
                "phase_sample_max_residual": 0.0,
            },
        )

        self.assertEqual(cross_check["status"], "conflict")
        self.assertEqual(cross_check["conflict_sources"], ["wavevector"])
        self.assertEqual(cross_check["likely_conflicting_path"], "metadata")

    def test_local_rays_cross_check_reports_phase_pattern_conflict(self):
        payload = {
            "positions": [[0.0, 0.0, 0.0]],
            "supercell_shape": [3, 1, 1],
            "rotating_frame_transform": {
                "wavevector": [0.25, 0.0, 0.0],
                "wavevector_units": "reciprocal_lattice_units",
                "sublattice_phase_offsets": {},
            },
            "rotating_frame_realization": {
                "supercell_shape": [3, 1, 1],
                "supercell_site_phases": _single_q_supercell_site_phases(
                    q_vector=[0.25, 0.0, 0.0],
                    positions=[[0.0, 0.0, 0.0]],
                    supercell_shape=[3, 1, 1],
                ),
            },
            "initial_local_rays": [
                {"cell": [0, 0, 0], "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}]},
                {"cell": [1, 0, 0], "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}]},
                {"cell": [2, 0, 0], "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}]},
            ],
        }
        payload["rotating_frame_realization"]["supercell_site_phases"][-1]["phase"] += 0.17

        cross_check = local_rays_rotating_frame_metadata_phase_sample_cross_check(payload)

        self.assertEqual(cross_check["status"], "conflict")
        self.assertEqual(cross_check["conflict_sources"], ["phase_pattern"])
        self.assertEqual(cross_check["likely_conflicting_path"], "phase_samples")


if __name__ == "__main__":
    unittest.main()
