import json
import io
import subprocess
import sys
import threading
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
    def test_driver_streams_backend_progress_to_stderr(self):
        payload = _classical_payload()

        class FakeProcess:
            def __init__(self):
                self.stdout = io.StringIO(
                    json.dumps(
                        {
                            "status": "ok",
                            "backend": {"name": "Sunny.jl", "mode": "SUN", "solver": "minimize_energy!"},
                            "payload_kind": "sunny_sun_classical",
                            "method": "sunny-cpn-minimize",
                            "energy": -0.5,
                            "supercell_shape": [2, 1, 1],
                            "local_rays": [
                                {"cell": [0, 0, 0], "vector": [_serialize_complex(1.0), _serialize_complex(0.0)]},
                            ],
                            "starts": 3,
                            "seed": 7,
                        }
                    )
                )
                self.stderr = io.StringIO("[sunny-classical] start 1/3\n[sunny-classical] best energy = -0.5\n")
                self.returncode = 0

            def wait(self):
                return self.returncode

        def fake_popen(command, stdout, stderr, text):
            self.assertEqual(command[0], "julia")
            self.assertTrue(command[1].endswith("run_sunny_sun_classical.jl"))
            self.assertTrue(text)
            return FakeProcess()

        with patch("classical.sunny_sun_classical_driver.subprocess.Popen", side_effect=fake_popen):
            with patch("sys.stderr", new_callable=io.StringIO) as fake_stderr:
                result = run_sunny_sun_classical(payload, stream_progress=True)

        self.assertEqual(result["status"], "ok")
        self.assertIn("[sunny-classical] start 1/3", fake_stderr.getvalue())
        self.assertIn("[sunny-classical] best energy = -0.5", fake_stderr.getvalue())

    def test_driver_drains_stdout_while_streaming_stderr_progress(self):
        payload = _classical_payload()

        class CoordinatedStdout:
            def __init__(self, read_started):
                self._read_started = read_started

            def read(self):
                self._read_started.set()
                return json.dumps(
                    {
                        "status": "ok",
                        "backend": {"name": "Sunny.jl", "mode": "SUN", "solver": "minimize_energy!"},
                        "payload_kind": "sunny_sun_classical",
                        "method": "sunny-cpn-minimize",
                        "energy": -0.5,
                        "supercell_shape": [2, 1, 1],
                        "local_rays": [
                            {"cell": [0, 0, 0], "vector": [_serialize_complex(1.0), _serialize_complex(0.0)]},
                        ],
                        "starts": 3,
                        "seed": 7,
                    }
                )

        class CoordinatedStderr:
            def __init__(self, read_started):
                self._read_started = read_started
                self._line_index = 0

            def __iter__(self):
                return self

            def __next__(self):
                if self._line_index == 0:
                    self._line_index += 1
                    return "[sunny-classical] start 1/3\n"
                if not self._read_started.wait(timeout=0.1):
                    raise AssertionError("stdout must be drained concurrently with stderr progress")
                raise StopIteration

        class FakeProcess:
            def __init__(self):
                read_started = threading.Event()
                self.stdout = CoordinatedStdout(read_started)
                self.stderr = CoordinatedStderr(read_started)
                self.returncode = 0

            def wait(self):
                return self.returncode

        def fake_popen(command, stdout, stderr, text):
            self.assertEqual(command[0], "julia")
            self.assertTrue(command[1].endswith("run_sunny_sun_classical.jl"))
            self.assertTrue(text)
            return FakeProcess()

        with patch("classical.sunny_sun_classical_driver.subprocess.Popen", side_effect=fake_popen):
            result = run_sunny_sun_classical(payload, stream_progress=True)

        self.assertEqual(result["status"], "ok")

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

    def test_driver_rejects_non_cpn_classical_model_before_backend_runs(self):
        payload = _classical_payload()
        payload["model"]["classical_manifold"] = "spin-S2"

        with patch("classical.sunny_sun_classical_driver.subprocess.run", side_effect=AssertionError("backend should not run")):
            result = run_sunny_sun_classical(payload)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "invalid-classical-payload")
        self.assertIn("CP^(N-1)", result["error"]["message"])
        self.assertIn("pseudospin-orbital", result["error"]["message"])

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

    def test_driver_rejects_explicitly_inconsistent_basis_order_before_backend_runs(self):
        payload = _classical_payload()
        payload["model"]["basis_order"] = "spin_major_orbital_minor"

        with patch("classical.sunny_sun_classical_driver.subprocess.run", side_effect=AssertionError("backend should not run")):
            result = run_sunny_sun_classical(payload)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "invalid-classical-convention")
        self.assertIn("basis_order", result["error"]["message"])

    def test_driver_aggregates_reverse_pairs_before_calling_julia_backend(self):
        payload = _classical_payload()
        payload["model"]["positions"] = [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]]
        payload["model"]["bond_tensors"] = [
            {
                "source": 0,
                "target": 1,
                "R": [1, 0, 0],
                "pair_matrix": [
                    [_serialize_complex(1.0), _serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(0.0)],
                    [_serialize_complex(0.0), _serialize_complex(2.0), _serialize_complex(0.0), _serialize_complex(0.0)],
                    [_serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(3.0), _serialize_complex(0.0)],
                    [_serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(4.0)],
                ],
                "tensor_shape": [2, 2, 2, 2],
            },
            {
                "source": 1,
                "target": 0,
                "R": [-1, 0, 0],
                "pair_matrix": [
                    [_serialize_complex(10.0), _serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(0.0)],
                    [_serialize_complex(0.0), _serialize_complex(20.0), _serialize_complex(0.0), _serialize_complex(0.0)],
                    [_serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(30.0), _serialize_complex(0.0)],
                    [_serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(40.0)],
                ],
                "tensor_shape": [2, 2, 2, 2],
            },
        ]

        def fake_run(command, check, capture_output, text):
            backend_payload = json.loads(Path(command[2]).read_text(encoding="utf-8"))
            bond_tensors = backend_payload["model"]["bond_tensors"]
            self.assertEqual(len(bond_tensors), 1)
            diagonal = [bond_tensors[0]["pair_matrix"][index][index]["real"] for index in range(4)]
            self.assertEqual(diagonal, [11.0, 32.0, 23.0, 44.0])

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
                        ],
                        "starts": 3,
                        "seed": 7,
                    }
                )

            return Completed()

        with patch("classical.sunny_sun_classical_driver.subprocess.run", side_effect=fake_run):
            result = run_sunny_sun_classical(payload)

        self.assertEqual(result["status"], "ok")


if __name__ == "__main__":
    unittest.main()
