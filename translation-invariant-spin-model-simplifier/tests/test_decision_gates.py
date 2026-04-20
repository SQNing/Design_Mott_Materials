import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical.decision_gates import (
    linear_spin_wave_stage_decision,
    lswt_stability_precheck,
    thermodynamics_stage_decision,
)


class DecisionGatesTests(unittest.TestCase):
    def test_lswt_stability_precheck_detects_standardized_lt_family_method(self):
        model = {
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "method": "spin-only-generalized-lt",
                "downstream_compatibility": {
                    "lswt": {"status": "ready"},
                },
            }
        }

        result = lswt_stability_precheck(model)

        self.assertEqual(result["status"], "warn")
        self.assertIn("classical_method=spin-only-generalized-lt", result["signals"])

    def test_linear_spin_wave_stage_decision_blocks_when_standardized_contract_blocks_lswt(self):
        model = {
            "classical_state_result": {
                "status": "ok",
                "role": "diagnostic",
                "method": "pseudospin-cpn-generalized-lt",
                "downstream_compatibility": {
                    "lswt": {"status": "blocked", "reason": "requires-spin-frame-site-frames"},
                    "gswt": {"status": "blocked", "reason": "diagnostic-seed-method"},
                    "thermodynamics": {"status": "blocked", "reason": "diagnostic-seed-method"},
                },
            }
        }

        result = linear_spin_wave_stage_decision(model, run_lswt=True)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["enabled"], False)
        self.assertEqual(result["reason"], "requires-spin-frame-site-frames")

    def test_linear_spin_wave_stage_decision_allows_standardized_ready_contract(self):
        model = {
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "method": "spin-only-variational",
                "downstream_compatibility": {
                    "lswt": {"status": "ready"},
                    "gswt": {"status": "blocked", "reason": "requires-local-ray-cpn-state"},
                    "thermodynamics": {"status": "review", "reason": "requires-caller-confirmed-support"},
                },
            },
            "q_path": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
        }

        result = linear_spin_wave_stage_decision(model, run_lswt=True)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["enabled"], True)

    def test_linear_spin_wave_stage_decision_accepts_bare_standardized_contract_mapping(self):
        model = {
            "status": "ok",
            "role": "final",
            "method": "spin-only-variational",
            "downstream_compatibility": {
                "lswt": {"status": "ready"},
                "gswt": {"status": "blocked", "reason": "requires-local-ray-cpn-state"},
                "thermodynamics": {"status": "review", "reason": "requires-caller-confirmed-support"},
            },
            "q_path": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
        }

        result = linear_spin_wave_stage_decision(model, run_lswt=True)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["enabled"], True)

    def test_thermodynamics_stage_decision_reports_review_route_from_standardized_contract(self):
        model = {
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
            }
        }

        result = thermodynamics_stage_decision(model, run_thermodynamics=True)

        self.assertEqual(result["status"], "review")
        self.assertEqual(result["enabled"], True)
        self.assertEqual(result["reason"], "requires-caller-confirmed-support")

    def test_thermodynamics_stage_decision_blocks_when_standardized_contract_blocks_stage(self):
        model = {
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

        result = thermodynamics_stage_decision(model, run_thermodynamics=True)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["enabled"], False)
        self.assertEqual(result["reason"], "diagnostic-seed-method")


if __name__ == "__main__":
    unittest.main()
