import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical.sunny_sun_classical_driver import run_sunny_sun_classical


def _serialize_complex(value):
    return {"real": float(value.real), "imag": float(value.imag)}


def _classical_payload():
    return {
        "backend": "Sunny.jl",
        "payload_kind": "sunny_sun_classical",
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
        "supercell_shape": [2, 1, 1],
        "starts": 3,
        "seed": 7,
    }


class RunSunnySunClassicalDriverTests(unittest.TestCase):
    def test_driver_invokes_julia_backend_and_parses_json(self):
        payload = _classical_payload()

        def fake_run(command, check, capture_output, text):
            self.assertEqual(command[0], "julia")
            self.assertTrue(command[1].endswith("run_sunny_sun_classical.jl"))
            payload_path = Path(command[2])
            backend_payload = json.loads(payload_path.read_text(encoding="utf-8"))
            self.assertEqual(backend_payload["payload_kind"], "sunny_sun_classical")
            self.assertEqual(backend_payload["supercell_shape"], [2, 1, 1])
            self.assertEqual(backend_payload["model"]["classical_manifold"], "CP^(N-1)")

            class Completed:
                stdout = json.dumps(
                    {
                        "status": "ok",
                        "backend": {"name": "Sunny.jl", "mode": "SUN", "solver": "minimize_energy!"},
                        "payload_kind": "sunny_sun_classical",
                        "method": "sunny-cpn-minimize",
                        "energy": -0.5,
                        "supercell_shape": [2, 1, 1],
                        "local_rays": [
                            {"cell": [0, 0, 0], "vector": [_serialize_complex(1.0), _serialize_complex(0.0)]},
                            {"cell": [1, 0, 0], "vector": [_serialize_complex(0.0), _serialize_complex(1.0)]},
                        ],
                        "starts": 3,
                        "seed": 7,
                    }
                )

            return Completed()

        with patch("classical.sunny_sun_classical_driver.subprocess.run", side_effect=fake_run):
            result = run_sunny_sun_classical(payload)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["backend"]["solver"], "minimize_energy!")
        self.assertEqual(result["method"], "sunny-cpn-minimize")
        self.assertEqual(result["supercell_shape"], [2, 1, 1])

    def test_driver_surfaces_payload_validation_errors(self):
        result = run_sunny_sun_classical({})

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "missing-classical-payload")

    def test_driver_reports_missing_julia_command(self):
        payload = _classical_payload()

        with patch("classical.sunny_sun_classical_driver.subprocess.run", side_effect=FileNotFoundError("julia")):
            result = run_sunny_sun_classical(payload)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "missing-julia-command")

    def test_driver_reports_backend_process_failure(self):
        payload = _classical_payload()
        error = subprocess.CalledProcessError(
            returncode=1,
            cmd=["julia", "run_sunny_sun_classical.jl"],
            stderr="classical backend exploded",
        )

        with patch("classical.sunny_sun_classical_driver.subprocess.run", side_effect=error):
            result = run_sunny_sun_classical(payload)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "backend-process-failed")
        self.assertEqual(result["error"]["message"], "classical backend exploded")

    def test_driver_reports_invalid_backend_json(self):
        payload = _classical_payload()

        class Completed:
            stdout = "not-json"

        with patch("classical.sunny_sun_classical_driver.subprocess.run", return_value=Completed()):
            result = run_sunny_sun_classical(payload)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "invalid-backend-json")


if __name__ == "__main__":
    unittest.main()
