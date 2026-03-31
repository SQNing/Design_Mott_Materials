import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from linear_spin_wave_driver import exact_diagonalization_branch, run_linear_spin_wave


class LinearSpinWaveDriverTests(unittest.TestCase):
    def test_run_linear_spin_wave_short_circuits_unsupported_scope_before_runtime_checks(self):
        model = {
            "simplified_model": {"three_body_terms": [{"sites": [0, 1, 2], "coefficient": 1.0}]},
            "classical_state": {
                "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}],
                "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                "provenance": {"method": "variational", "converged": True},
            },
        }
        result = run_linear_spin_wave(model)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "unsupported-model-scope")

    @patch("linear_spin_wave_driver.detect_julia", return_value=None)
    def test_run_linear_spin_wave_reports_missing_julia_runtime(self, _mock_detect_julia):
        model = {
            "lattice": {"kind": "chain", "dimension": 1, "unit_cell": [0], "sublattices": 1},
            "simplified_model": {
                "template": "heisenberg",
                "bonds": [{"source": 0, "target": 0, "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]}],
            },
            "classical_state": {
                "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}],
                "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                "provenance": {"method": "variational", "converged": True},
            },
        }
        result = run_linear_spin_wave(model)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "missing-julia-runtime")

    @patch("linear_spin_wave_driver.check_sunny_available", return_value=(False, "Sunny not installed"))
    @patch("linear_spin_wave_driver.detect_julia", return_value="julia")
    def test_run_linear_spin_wave_reports_missing_sunny_package(self, _mock_detect_julia, _mock_check_sunny):
        model = {
            "lattice": {"kind": "chain", "dimension": 1, "unit_cell": [0], "sublattices": 1},
            "simplified_model": {
                "template": "heisenberg",
                "bonds": [{"source": 0, "target": 0, "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]}],
            },
            "classical_state": {
                "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}],
                "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                "provenance": {"method": "variational", "converged": True},
            },
        }
        result = run_linear_spin_wave(model)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "missing-sunny-package")

    @patch("linear_spin_wave_driver.run_backend")
    @patch("linear_spin_wave_driver.check_sunny_available", return_value=(True, None))
    @patch("linear_spin_wave_driver.detect_julia", return_value="julia")
    def test_run_linear_spin_wave_returns_backend_result_on_success(
        self, _mock_detect_julia, _mock_check_sunny, mock_run_backend
    ):
        mock_run_backend.return_value = {
            "status": "ok",
            "backend": {"name": "Sunny.jl"},
            "linear_spin_wave": {"dispersion": [{"q": [0.0, 0.0, 0.0], "omega": 0.0}]},
        }
        model = {
            "lattice": {"kind": "chain", "dimension": 1, "unit_cell": [0], "sublattices": 1},
            "simplified_model": {
                "template": "heisenberg",
                "bonds": [{"source": 0, "target": 0, "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]}],
            },
            "classical_state": {
                "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}],
                "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                "provenance": {"method": "variational", "converged": True},
            },
        }
        result = run_linear_spin_wave(model)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["backend"]["name"], "Sunny.jl")
        self.assertEqual(result["linear_spin_wave"]["dispersion"][0]["omega"], 0.0)
        self.assertIn("path", result)
        self.assertIn("labels", result["path"])

    def test_exact_diagonalization_branch_solves_spin_half_dimer(self):
        model = {"local_dim": 2, "cluster_size": 2, "exchange": 1.0}
        summary = exact_diagonalization_branch(model)
        self.assertTrue(summary["supported"])
        self.assertAlmostEqual(summary["ground_state_energy"], -0.75, places=6)


if __name__ == "__main__":
    unittest.main()
