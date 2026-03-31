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


if __name__ == "__main__":
    unittest.main()
