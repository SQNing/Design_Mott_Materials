import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from linear_spin_wave_driver import run_linear_spin_wave


class LinearSpinWaveDriverTests(unittest.TestCase):
    def test_run_linear_spin_wave_builds_lswt_payload_and_invokes_sunny_backend(self):
        model = {
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "sublattices": 1,
                "positions": [[0.0, 0.0, 0.0]],
            },
            "simplified_model": {
                "template": "heisenberg",
                "bonds": [
                    {
                        "source": 0,
                        "target": 0,
                        "vector": [1, 0, 0],
                        "matrix": [
                            [1.0, 0.0, 0.0],
                            [0.0, 1.0, 0.0],
                            [0.0, 0.0, 1.0],
                        ],
                    }
                ],
            },
            "classical": {
                "chosen_method": "luttinger-tisza",
                "classical_state": {
                    "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}],
                    "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                },
            },
            "q_path": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
            "q_samples": 4,
        }

        def fake_run(command, check, capture_output, text):
            self.assertEqual(command[0], "julia")
            self.assertTrue(command[1].endswith("run_sunny_lswt.jl"))
            payload_path = Path(command[2])
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["reference_frames"]), 1)
            self.assertEqual(payload["ordering"]["q_vector"], [0.0, 0.0, 0.0])

            class Completed:
                stdout = json.dumps(
                    {
                        "status": "ok",
                        "backend": {"name": "Sunny.jl"},
                        "linear_spin_wave": {
                            "dispersion": [{"q": [0.0, 0.0, 0.0], "omega": 0.0, "bands": [0.0]}]
                        },
                    }
                )

            return Completed()

        with patch("linear_spin_wave_driver.subprocess.run", side_effect=fake_run):
            result = run_linear_spin_wave(model)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["backend"]["name"], "Sunny.jl")
        self.assertEqual(result["path"]["labels"], ["G", "X"])
        self.assertEqual(result["linear_spin_wave"]["dispersion"][0]["q"], [0.0, 0.0, 0.0])

    def test_run_linear_spin_wave_surfaces_lswt_payload_validation_errors(self):
        model = {
            "lattice": {"kind": "chain", "dimension": 1, "sublattices": 1},
            "simplified_model": {
                "template": "heisenberg",
                "bonds": [
                    {
                        "source": 0,
                        "target": 0,
                        "vector": [1, 0, 0],
                        "matrix": [
                            [1.0, 0.0, 0.0],
                            [0.0, 1.0, 0.0],
                            [0.0, 0.0, 1.0],
                        ],
                    }
                ],
            },
        }

        result = run_linear_spin_wave(model)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "invalid-classical-reference-state")

    def test_run_linear_spin_wave_reports_missing_julia_command(self):
        model = {
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "sublattices": 1,
                "positions": [[0.0, 0.0, 0.0]],
            },
            "simplified_model": {
                "template": "heisenberg",
                "bonds": [
                    {
                        "source": 0,
                        "target": 0,
                        "vector": [1, 0, 0],
                        "matrix": [
                            [1.0, 0.0, 0.0],
                            [0.0, 1.0, 0.0],
                            [0.0, 0.0, 1.0],
                        ],
                    }
                ],
            },
            "classical": {
                "chosen_method": "luttinger-tisza",
                "classical_state": {
                    "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}],
                    "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                },
            },
        }

        with patch("linear_spin_wave_driver.subprocess.run", side_effect=FileNotFoundError("julia")):
            result = run_linear_spin_wave(model)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "missing-julia-command")

    def test_run_linear_spin_wave_reports_backend_process_failure(self):
        model = {
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "sublattices": 1,
                "positions": [[0.0, 0.0, 0.0]],
            },
            "simplified_model": {
                "template": "heisenberg",
                "bonds": [
                    {
                        "source": 0,
                        "target": 0,
                        "vector": [1, 0, 0],
                        "matrix": [
                            [1.0, 0.0, 0.0],
                            [0.0, 1.0, 0.0],
                            [0.0, 0.0, 1.0],
                        ],
                    }
                ],
            },
            "classical": {
                "chosen_method": "luttinger-tisza",
                "classical_state": {
                    "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}],
                    "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                },
            },
        }

        error = subprocess.CalledProcessError(
            returncode=1,
            cmd=["julia", "run_sunny_lswt.jl"],
            stderr="backend exploded",
        )
        with patch("linear_spin_wave_driver.subprocess.run", side_effect=error):
            result = run_linear_spin_wave(model)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "backend-process-failed")
        self.assertEqual(result["error"]["message"], "backend exploded")

    def test_run_linear_spin_wave_reports_invalid_backend_json(self):
        model = {
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "sublattices": 1,
                "positions": [[0.0, 0.0, 0.0]],
            },
            "simplified_model": {
                "template": "heisenberg",
                "bonds": [
                    {
                        "source": 0,
                        "target": 0,
                        "vector": [1, 0, 0],
                        "matrix": [
                            [1.0, 0.0, 0.0],
                            [0.0, 1.0, 0.0],
                            [0.0, 0.0, 1.0],
                        ],
                    }
                ],
            },
            "classical": {
                "chosen_method": "luttinger-tisza",
                "classical_state": {
                    "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}],
                    "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                },
            },
        }

        class Completed:
            stdout = "not-json"

        with patch("linear_spin_wave_driver.subprocess.run", return_value=Completed()):
            result = run_linear_spin_wave(model)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "invalid-backend-json")

    def test_run_linear_spin_wave_preserves_valid_backend_error_payload(self):
        model = {
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "sublattices": 1,
                "positions": [[0.0, 0.0, 0.0]],
            },
            "simplified_model": {
                "template": "heisenberg",
                "bonds": [
                    {
                        "source": 0,
                        "target": 0,
                        "vector": [1, 0, 0],
                        "matrix": [
                            [1.0, 0.0, 0.0],
                            [0.0, 1.0, 0.0],
                            [0.0, 0.0, 1.0],
                        ],
                    }
                ],
            },
            "classical": {
                "chosen_method": "luttinger-tisza",
                "classical_state": {
                    "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}],
                    "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                },
            },
            "q_path": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
            "q_samples": 4,
        }

        class Completed:
            stdout = json.dumps(
                {
                    "status": "error",
                    "backend": {"name": "Sunny.jl"},
                    "linear_spin_wave": {},
                    "error": {"code": "missing-sunny-package", "message": "Sunny.jl is unavailable"},
                }
            )

        with patch("linear_spin_wave_driver.subprocess.run", return_value=Completed()):
            result = run_linear_spin_wave(model)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "missing-sunny-package")
        self.assertEqual(result["path"]["labels"], ["G", "X"])


if __name__ == "__main__":
    unittest.main()
