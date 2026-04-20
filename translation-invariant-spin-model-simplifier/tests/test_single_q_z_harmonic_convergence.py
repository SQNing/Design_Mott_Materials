import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from lswt.single_q_z_harmonic_convergence import analyze_single_q_z_harmonic_convergence
from lswt.single_q_z_harmonic_convergence_driver import run_single_q_z_harmonic_convergence_driver


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


def _simple_chain_model():
    return {
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
        "q_path": [[0.0, 0.0, 0.0], [0.13, 0.0, 0.0], [0.27, 0.0, 0.0]],
        "path": {"labels": ["G", "Q", "X"], "node_indices": [0, 1, 2]},
    }


def _single_q_helical_state():
    return {
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


def _driver_input_payload():
    return {
        **_simple_chain_model(),
        "classical_state": _single_q_helical_state(),
        "phase_grid_sizes": [16, 32],
        "z_harmonic_cutoffs": [0, 1],
        "sideband_cutoffs": [0, 1],
        "z_harmonic_reference_mode": "input",
    }


def _wrapped_single_q_helical_state():
    state = _single_q_helical_state()
    return {
        **state,
        "classical_state_result": {
            "status": "ok",
            "role": "final",
            "downstream_compatibility": {"gswt": {"status": "ready"}},
            "classical_state": dict(state["classical_state"]),
        },
    }


class SingleQZHarmonicConvergenceTests(unittest.TestCase):
    def test_analysis_returns_three_scan_tables_with_reference_parameters(self):
        result = analyze_single_q_z_harmonic_convergence(
            _simple_chain_model(),
            classical_state=_single_q_helical_state(),
            phase_grid_sizes=[16, 32],
            z_harmonic_cutoffs=[0, 1],
            sideband_cutoffs=[0, 1],
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["analysis_kind"], "single_q_z_harmonic_convergence")
        self.assertEqual(
            result["reference_parameters"],
            {
                "phase_grid_size": 32,
                "z_harmonic_cutoff": 1,
                "sideband_cutoff": 1,
                "z_harmonic_reference_mode": "input",
            },
        )
        self.assertEqual(
            [entry["phase_grid_size"] for entry in result["phase_grid_scan"]],
            [16, 32],
        )
        self.assertEqual(
            [entry["z_harmonic_cutoff"] for entry in result["z_harmonic_cutoff_scan"]],
            [0, 1],
        )
        self.assertEqual(
            [entry["sideband_cutoff"] for entry in result["sideband_cutoff_scan"]],
            [0, 1],
        )
        self.assertEqual(result["z_harmonic_cutoff_scan"][-1]["max_band_delta_vs_reference"], 0.0)
        self.assertGreater(result["z_harmonic_cutoff_scan"][0]["max_band_delta_vs_reference"], 1e-6)
        self.assertEqual(result["phase_grid_scan"][0]["resolved_reference_mode"], "input")
        self.assertIsNotNone(result["reference_metrics"]["omega_min"])

    def test_driver_reads_scan_configuration_from_payload_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            payload_path = Path(tmpdir) / "payload.json"
            payload_path.write_text(json.dumps(_driver_input_payload()), encoding="utf-8")

            result = run_single_q_z_harmonic_convergence_driver(str(payload_path))

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["reference_parameters"]["phase_grid_size"], 32)
        self.assertGreater(result["z_harmonic_cutoff_scan"][0]["max_band_delta_vs_reference"], 1e-6)

    def test_driver_accepts_pipeline_output_directory_and_uses_gswt_payload_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            (output_dir / "classical_model.json").write_text(
                json.dumps(_simple_chain_model()),
                encoding="utf-8",
            )
            (output_dir / "solver_result.json").write_text(
                json.dumps(_single_q_helical_state()),
                encoding="utf-8",
            )
            (output_dir / "gswt_payload.json").write_text(
                json.dumps(
                    {
                        "payload_kind": "python_glswt_single_q_z_harmonic",
                        "phase_grid_size": 24,
                        "z_harmonic_cutoff": 1,
                        "sideband_cutoff": 1,
                        "z_harmonic_reference_mode": "refined-retained-local",
                    }
                ),
                encoding="utf-8",
            )

            result = run_single_q_z_harmonic_convergence_driver(str(output_dir))

        self.assertEqual(result["status"], "ok")
        self.assertEqual(
            result["reference_parameters"],
            {
                "phase_grid_size": 24,
                "z_harmonic_cutoff": 1,
                "sideband_cutoff": 1,
                "z_harmonic_reference_mode": "refined-retained-local",
            },
        )
        self.assertEqual([entry["phase_grid_size"] for entry in result["phase_grid_scan"]], [24])
        self.assertEqual([entry["z_harmonic_cutoff"] for entry in result["z_harmonic_cutoff_scan"]], [1])
        self.assertEqual([entry["sideband_cutoff"] for entry in result["sideband_cutoff_scan"]], [1])

    def test_driver_accepts_pipeline_output_directory_with_nested_standardized_contract(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            (output_dir / "classical_model.json").write_text(
                json.dumps(_simple_chain_model()),
                encoding="utf-8",
            )
            (output_dir / "solver_result.json").write_text(
                json.dumps(_wrapped_single_q_helical_state()),
                encoding="utf-8",
            )
            (output_dir / "gswt_payload.json").write_text(
                json.dumps(
                    {
                        "payload_kind": "python_glswt_single_q_z_harmonic",
                        "phase_grid_size": 20,
                        "z_harmonic_cutoff": 1,
                        "sideband_cutoff": 1,
                        "z_harmonic_reference_mode": "input",
                    }
                ),
                encoding="utf-8",
            )

            result = run_single_q_z_harmonic_convergence_driver(str(output_dir))

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["reference_parameters"]["phase_grid_size"], 20)
        self.assertEqual(result["reference_parameters"]["z_harmonic_reference_mode"], "input")


if __name__ == "__main__":
    unittest.main()
