import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

try:
    from common import downstream_stage_routing as routing  # noqa: E402
except ImportError:
    routing = None


class DownstreamStageRoutingTests(unittest.TestCase):
    def test_resolve_lswt_route_from_standardized_spin_frame_result(self):
        self.assertIsNotNone(routing)
        payload = {
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
            }
        }

        route = routing.resolve_downstream_stage_route(payload, "lswt")

        self.assertEqual(route["status"], "ready")
        self.assertEqual(route["enabled"], True)
        self.assertEqual(route["method"], "spin-only-variational")
        self.assertEqual(route["solver_family"], "spin_only_explicit")

    def test_resolve_gswt_route_from_standardized_local_ray_result(self):
        self.assertIsNotNone(routing)
        payload = {
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "method": "pseudospin-cpn-local-ray-minimize",
                "solver_family": "retained_local_multiplet",
                "downstream_compatibility": {
                    "lswt": {"status": "blocked", "reason": "requires-spin-frame-site-frames"},
                    "gswt": {"status": "ready", "recommended_backend": "python"},
                    "thermodynamics": {"status": "ready", "recommended_backend": "sunny-local-sampler"},
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
            "gswt_payload": {"payload_kind": "python_glswt_local_rays"},
        }

        route = routing.resolve_downstream_stage_route(payload, "gswt")

        self.assertEqual(route["status"], "ready")
        self.assertEqual(route["enabled"], True)
        self.assertEqual(route["recommended_backend"], "python")
        self.assertEqual(route["method"], "pseudospin-cpn-local-ray-minimize")

    def test_resolve_review_thermodynamics_route_is_enabled(self):
        self.assertIsNotNone(routing)
        payload = {
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
            },
            "bonds": [
                {
                    "source": 0,
                    "target": 0,
                    "vector": [0.0, 0.0, 0.0],
                    "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                }
            ],
            "thermodynamics": {"temperatures": [0.1, 0.2]},
        }

        route = routing.resolve_downstream_stage_route(payload, "thermodynamics")

        self.assertEqual(route["status"], "review")
        self.assertEqual(route["enabled"], True)
        self.assertEqual(route["reason"], "requires-caller-confirmed-support")

    def test_resolve_diagnostic_route_blocks_all_downstream_stages(self):
        self.assertIsNotNone(routing)
        payload = {
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
            }
        }

        route = routing.resolve_downstream_stage_route(payload, "gswt")

        self.assertEqual(route["status"], "blocked")
        self.assertEqual(route["enabled"], False)
        self.assertEqual(route["reason"], "diagnostic-seed-method")
        self.assertEqual(route["role"], "diagnostic")

    def test_resolve_lswt_route_falls_back_to_legacy_spin_frame_semantics(self):
        self.assertIsNotNone(routing)
        payload = {
            "classical_state": {
                "site_frames": [
                    {
                        "site": 0,
                        "spin_length": 0.5,
                        "direction": [0.0, 0.0, 1.0],
                    }
                ]
            }
        }

        route = routing.resolve_downstream_stage_route(payload, "lswt")

        self.assertEqual(route["status"], "ready")
        self.assertEqual(route["enabled"], True)
        self.assertEqual(route["source"], "legacy-fallback")

    def test_unsupported_stage_raises_stable_value_error(self):
        self.assertIsNotNone(routing)

        with self.assertRaisesRegex(ValueError, "unsupported downstream stage"):
            routing.resolve_downstream_stage_route({}, "made-up-stage")


if __name__ == "__main__":
    unittest.main()
