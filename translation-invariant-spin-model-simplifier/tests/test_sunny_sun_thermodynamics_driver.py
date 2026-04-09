import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical.sunny_sun_thermodynamics_driver import run_sunny_sun_thermodynamics


def _serialize_complex(value):
    return {"real": float(value.real), "imag": float(value.imag)}


def _thermodynamics_payload(backend_method):
    return {
        "backend": "Sunny.jl",
        "payload_kind": "sunny_sun_thermodynamics",
        "backend_method": backend_method,
        "model": {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "orbital_count": 1,
            "pair_basis_order": "site_i_major_site_j_minor",
            "local_basis_labels": ["up", "down"],
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "positions": [[0.0, 0.0, 0.0]],
            "bond_tensors": [
                {
                    "R": [1, 0, 0],
                    "pair_matrix": [
                        [_serialize_complex(1.0), _serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(0.0)],
                        [_serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(1.0), _serialize_complex(0.0)],
                        [_serialize_complex(0.0), _serialize_complex(1.0), _serialize_complex(0.0), _serialize_complex(0.0)],
                        [_serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(1.0)],
                    ],
                    "tensor_shape": [2, 2, 2, 2],
                }
            ],
        },
        "initial_state": {
            "shape": [1, 1, 1],
            "local_rays": [
                {"cell": [0, 0, 0], "vector": [_serialize_complex(1.0), _serialize_complex(0.0)]},
            ],
        },
        "supercell_shape": [1, 1, 1],
        "temperatures": [0.2, 0.4],
        "seed": 5,
        "sweeps": 8,
        "burn_in": 4,
        "measurement_interval": 1,
        "proposal": "delta",
        "proposal_scale": 0.2,
        "pt_temperatures": [0.2, 0.4, 0.8],
        "pt_exchange_interval": 2,
        "wl_bounds": [-2.0, 0.0],
        "wl_bin_size": 0.05,
        "wl_windows": 2,
        "wl_overlap": 0.25,
        "wl_ln_f": 1.0,
        "wl_sweeps": 10,
    }


def _successful_backend_stdout(backend_method):
    payload = {
        "status": "ok",
        "backend": {"name": "Sunny.jl", "mode": "SUN", "sampler": backend_method},
        "payload_kind": "sunny_sun_thermodynamics",
        "thermodynamics_result": {
            "method": backend_method,
            "backend": {"name": "Sunny.jl", "mode": "SUN", "sampler": backend_method},
            "grid": [
                {
                    "temperature": 0.2,
                    "energy": -0.1,
                    "magnetization": 0.3,
                    "specific_heat": 0.4,
                    "susceptibility": 0.5,
                }
            ],
            "observables": {
                "energy": [-0.1],
                "magnetization": [0.3],
                "specific_heat": [0.4],
                "susceptibility": [0.5],
            },
            "uncertainties": {
                "energy": [0.01],
                "magnetization": [0.02],
                "specific_heat": [0.03],
                "susceptibility": [0.04],
            },
            "sampling": {"seed": 5},
            "reference": {"normalization": "per_spin"},
        },
    }
    if backend_method == "sunny-wang-landau":
        payload["dos_result"] = {
            "energy_bins": [-1.0, -0.9],
            "log_density_of_states": [0.0, 0.1],
        }
    return json.dumps(payload)


class RunSunnySunThermodynamicsDriverTests(unittest.TestCase):
    def test_driver_supports_local_sampler_backend(self):
        payload = _thermodynamics_payload("sunny-local-sampler")

        def fake_run(command, check, capture_output, text):
            self.assertEqual(command[0], "julia")
            self.assertTrue(command[1].endswith("run_sunny_sun_thermodynamics.jl"))
            payload_path = Path(command[2])
            backend_payload = json.loads(payload_path.read_text(encoding="utf-8"))
            self.assertEqual(backend_payload["backend_method"], "sunny-local-sampler")

            class Completed:
                stdout = _successful_backend_stdout("sunny-local-sampler")

            return Completed()

        with patch("classical.sunny_sun_thermodynamics_driver.subprocess.run", side_effect=fake_run):
            result = run_sunny_sun_thermodynamics(payload)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["backend"]["sampler"], "sunny-local-sampler")
        self.assertIn("thermodynamics_result", result)

    def test_driver_supports_parallel_tempering_backend(self):
        payload = _thermodynamics_payload("sunny-parallel-tempering")

        class Completed:
            stdout = _successful_backend_stdout("sunny-parallel-tempering")

        with patch("classical.sunny_sun_thermodynamics_driver.subprocess.run", return_value=Completed()):
            result = run_sunny_sun_thermodynamics(payload)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["backend"]["sampler"], "sunny-parallel-tempering")
        self.assertEqual(result["thermodynamics_result"]["method"], "sunny-parallel-tempering")

    def test_driver_supports_wang_landau_backend(self):
        payload = _thermodynamics_payload("sunny-wang-landau")

        class Completed:
            stdout = _successful_backend_stdout("sunny-wang-landau")

        with patch("classical.sunny_sun_thermodynamics_driver.subprocess.run", return_value=Completed()):
            result = run_sunny_sun_thermodynamics(payload)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["backend"]["sampler"], "sunny-wang-landau")
        self.assertIn("dos_result", result)

    def test_driver_reports_missing_payload(self):
        result = run_sunny_sun_thermodynamics({})

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "missing-thermodynamics-payload")

    def test_driver_reports_missing_julia_command(self):
        payload = _thermodynamics_payload("sunny-local-sampler")

        with patch("classical.sunny_sun_thermodynamics_driver.subprocess.run", side_effect=FileNotFoundError("julia")):
            result = run_sunny_sun_thermodynamics(payload)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "missing-julia-command")

    def test_driver_reports_backend_process_failure(self):
        payload = _thermodynamics_payload("sunny-local-sampler")
        error = subprocess.CalledProcessError(
            returncode=1,
            cmd=["julia", "run_sunny_sun_thermodynamics.jl"],
            stderr="thermodynamics backend exploded",
        )

        with patch("classical.sunny_sun_thermodynamics_driver.subprocess.run", side_effect=error):
            result = run_sunny_sun_thermodynamics(payload)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "backend-process-failed")
        self.assertEqual(result["error"]["message"], "thermodynamics backend exploded")

    def test_driver_reports_invalid_backend_json(self):
        payload = _thermodynamics_payload("sunny-local-sampler")

        class Completed:
            stdout = "not-json"

        with patch("classical.sunny_sun_thermodynamics_driver.subprocess.run", return_value=Completed()):
            result = run_sunny_sun_thermodynamics(payload)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "invalid-backend-json")

    def test_driver_rejects_explicitly_inconsistent_basis_order_before_backend_runs(self):
        payload = _thermodynamics_payload("sunny-local-sampler")
        payload["model"]["basis_order"] = "spin_major_orbital_minor"

        with patch(
            "classical.sunny_sun_thermodynamics_driver.subprocess.run",
            side_effect=AssertionError("backend should not run"),
        ):
            result = run_sunny_sun_thermodynamics(payload)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "invalid-thermodynamics-convention")
        self.assertIn("basis_order", result["error"]["message"])


if __name__ == "__main__":
    unittest.main()
