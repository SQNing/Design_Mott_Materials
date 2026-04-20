import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

try:
    from common import downstream_stage_execution as execution  # noqa: E402
except ImportError:
    execution = None


def _spin_frame_payload():
    return {
        "bonds": [
            {
                "source": 0,
                "target": 0,
                "vector": [0.0, 0.0, 0.0],
                "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            }
        ],
        "thermodynamics": {"temperatures": [0.1, 0.2]},
        "classical_state_result": {
            "status": "ok",
            "role": "final",
            "method": "spin-only-variational",
            "solver_family": "spin_only_explicit",
            "downstream_compatibility": {
                "lswt": {"status": "ready"},
                "gswt": {"status": "blocked", "reason": "requires-local-ray-cpn-state"},
                "thermodynamics": {"status": "review", "reason": "requires-caller-confirmed-support"},
            },
            "classical_state": {
                "site_frames": [
                    {
                        "site": 0,
                        "spin_length": 0.5,
                        "direction": [0.0, 0.0, 1.0],
                    }
                ]
            },
        },
    }


def _local_ray_payload(payload_kind="python_glswt_local_rays"):
    return {
        "gswt_payload": {"payload_kind": payload_kind},
        "thermodynamics_payload": {
            "payload_kind": "sunny_sun_thermodynamics",
            "backend_method": "sunny-local-sampler",
        },
        "classical_state_result": {
            "status": "ok",
            "role": "final",
            "method": "pseudospin-cpn-local-ray-minimize",
            "solver_family": "retained_local_multiplet",
            "downstream_compatibility": {
                "lswt": {"status": "blocked", "reason": "requires-spin-frame-site-frames"},
                "gswt": {"status": "ready"},
                "thermodynamics": {"status": "ready"},
            },
            "classical_state": {
                "state_kind": "local_rays",
                "manifold": "CP^(N-1)",
                "supercell_shape": [1, 1, 1],
                "local_rays": [
                    {
                        "cell": [0, 0, 0],
                        "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}],
                    }
                ],
            },
        },
    }


class DownstreamStageExecutionTests(unittest.TestCase):
    def test_select_gswt_backend_prefers_python_runner_for_python_payload_kind(self):
        self.assertIsNotNone(execution)

        backend = execution.select_downstream_backend(_local_ray_payload(), "gswt")

        self.assertEqual(backend, "python_glswt")

    def test_select_gswt_backend_prefers_sunny_runner_for_sunny_payload_kind(self):
        self.assertIsNotNone(execution)

        backend = execution.select_downstream_backend(_local_ray_payload(payload_kind="sun_gswt_prototype"), "gswt")

        self.assertEqual(backend, "sun_gswt")

    def test_select_lswt_backend_returns_linear_spin_wave(self):
        self.assertIsNotNone(execution)

        backend = execution.select_downstream_backend(_spin_frame_payload(), "lswt")

        self.assertEqual(backend, "linear_spin_wave")

    def test_select_thermodynamics_backend_distinguishes_spin_only_and_sunny_routes(self):
        self.assertIsNotNone(execution)

        spin_only_backend = execution.select_downstream_backend(_spin_frame_payload(), "thermodynamics")
        sunny_backend = execution.select_downstream_backend(_local_ray_payload(), "thermodynamics")

        self.assertEqual(spin_only_backend, "spin_only_thermodynamics")
        self.assertEqual(sunny_backend, "sunny_thermodynamics")

    def test_execute_gswt_stage_dispatches_to_python_runner(self):
        self.assertIsNotNone(execution)

        with (
            patch.object(execution, "run_python_glswt_driver", return_value={"status": "ok", "backend": "python"}) as python_runner,
            patch.object(execution, "run_sun_gswt", return_value={"status": "ok", "backend": "sunny"}) as sunny_runner,
        ):
            result = execution.execute_downstream_stage(_local_ray_payload(), "gswt")

        self.assertEqual(result["backend"], "python")
        self.assertEqual(python_runner.called, True)
        self.assertEqual(sunny_runner.called, False)

    def test_execute_lswt_stage_dispatches_to_linear_spin_wave_runner(self):
        self.assertIsNotNone(execution)

        with patch.object(execution, "run_linear_spin_wave", return_value={"status": "ok", "backend": "lswt"}) as lswt_runner:
            result = execution.execute_downstream_stage(_spin_frame_payload(), "lswt")

        self.assertEqual(result["backend"], "lswt")
        self.assertEqual(lswt_runner.called, True)

    def test_execute_thermodynamics_stage_raises_for_blocked_route(self):
        self.assertIsNotNone(execution)
        payload = {
            "bonds": [
                {
                    "source": 0,
                    "target": 0,
                    "vector": [0.0, 0.0, 0.0],
                    "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                }
            ],
            "thermodynamics": {"temperatures": [0.1, 0.2]},
            "classical_state_result": {
                "status": "ok",
                "role": "diagnostic",
                "method": "pseudospin-cpn-generalized-lt",
                "solver_family": "diagnostic_seed_only",
                "downstream_compatibility": {
                    "lswt": {"status": "blocked", "reason": "diagnostic-seed-method"},
                    "gswt": {"status": "blocked", "reason": "diagnostic-seed-method"},
                    "thermodynamics": {"status": "blocked", "reason": "diagnostic-seed-method"},
                },
            },
        }

        with self.assertRaisesRegex(ValueError, "blocked"):
            execution.execute_downstream_stage(payload, "thermodynamics")


if __name__ == "__main__":
    unittest.main()
