import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from lswt.linear_spin_wave_driver import run_linear_spin_wave


def _lswt_payload():
    return {
        "status": "ok",
        "payload": {
            "payload_kind": "spin_only_lswt",
            "path": {"labels": ["G", "X"], "node_indices": [0, 1]},
        },
    }


class RunLinearSpinWaveDriverTests(unittest.TestCase):
    def test_driver_prefers_environment_julia_override(self):
        payload = {"spin": 1.0}

        def fake_run(command, check, capture_output, text):
            self.assertEqual(command[0], "/tmp/julia-1.12/bin/julia")
            self.assertTrue(command[1].endswith("run_sunny_lswt.jl"))

            class Completed:
                stdout = json.dumps(
                    {
                        "status": "ok",
                        "backend": {"name": "Sunny.jl"},
                        "linear_spin_wave": {"dispersion": []},
                    }
                )

            return Completed()

        with patch("lswt.linear_spin_wave_driver.build_lswt_payload", return_value=_lswt_payload()):
            with patch.dict("os.environ", {"DESIGN_MOTT_JULIA_CMD": "/tmp/julia-1.12/bin/julia"}, clear=False):
                with patch("lswt.linear_spin_wave_driver.subprocess.run", side_effect=fake_run):
                    result = run_linear_spin_wave(payload)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["path"]["labels"], ["G", "X"])

    def test_driver_falls_back_to_plain_julia_without_override(self):
        payload = {"spin": 1.0}

        def fake_run(command, check, capture_output, text):
            self.assertEqual(command[0], "julia")

            class Completed:
                stdout = json.dumps(
                    {
                        "status": "ok",
                        "backend": {"name": "Sunny.jl"},
                        "linear_spin_wave": {"dispersion": []},
                    }
                )

            return Completed()

        with patch("lswt.linear_spin_wave_driver.build_lswt_payload", return_value=_lswt_payload()):
            with patch.dict("os.environ", {}, clear=True):
                with patch("lswt.linear_spin_wave_driver.subprocess.run", side_effect=fake_run):
                    result = run_linear_spin_wave(payload)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["path"]["node_indices"], [0, 1])


if __name__ == "__main__":
    unittest.main()
