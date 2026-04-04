import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class RunSunnyLswtContractTests(unittest.TestCase):
    def test_runner_script_exists(self):
        runner = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "run_sunny_lswt.jl"
        )
        self.assertTrue(runner.exists())

    @unittest.skipUnless(shutil.which("julia"), "Julia runtime is not available in this environment")
    def test_runner_emits_structured_json_even_when_backend_cannot_run(self):
        runner = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "run_sunny_lswt.jl"
        )
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json") as handle:
            json.dump({"backend": "Sunny.jl", "bonds": [], "reference_frames": []}, handle)
            handle.flush()
            completed = subprocess.run(
                ["julia", str(runner), handle.name],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertIn("status", payload)
        self.assertIn("backend", payload)
        self.assertIn("linear_spin_wave", payload)

    @unittest.skipUnless(shutil.which("julia"), "Julia runtime is not available in this environment")
    def test_runner_solves_simple_ferromagnetic_heisenberg_example(self):
        runner = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "run_sunny_lswt.jl"
        )
        payload = {
            "backend": "Sunny.jl",
            "lattice_vectors": [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
            ],
            "positions": [[0.0, 0.0, 0.0]],
            "bonds": [
                {
                    "source": 0,
                    "target": 0,
                    "vector": [1, 0, 0],
                    "exchange_matrix": [
                        [-1.0, 0.0, 0.0],
                        [0.0, -1.0, 0.0],
                        [0.0, 0.0, -1.0],
                    ],
                }
            ],
            "reference_frames": [
                {"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]},
            ],
            "moments": [
                {"site": 0, "spin": 0.5, "g": 2.0},
            ],
            "q_path": [[0.0, 0.0, 0.0], [3.141592653589793, 0.0, 0.0]],
        }
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json") as handle:
            json.dump(payload, handle)
            handle.flush()
            completed = subprocess.run(
                ["julia", str(runner), handle.name],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["backend"]["name"], "Sunny.jl")
        self.assertGreaterEqual(len(result["linear_spin_wave"]["dispersion"]), 1)


if __name__ == "__main__":
    unittest.main()
