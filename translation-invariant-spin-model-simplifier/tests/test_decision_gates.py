import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from decision_gates import (
    classical_stage_decision,
    exact_diagonalization_stage_decision,
    linear_spin_wave_stage_decision,
    thermodynamics_stage_decision,
)


class DecisionGatesTests(unittest.TestCase):
    def test_classical_stage_requests_method_when_not_yet_confirmed(self):
        model = {"lattice": {"sublattices": 1}, "simplified_model": {"template": "heisenberg"}}
        decision = classical_stage_decision(model)
        self.assertEqual(decision["status"], "needs_input")
        self.assertEqual(decision["question"]["id"], "classical_method")
        self.assertEqual(decision["recommended"], "luttinger-tisza")

    def test_classical_stage_can_auto_select_recommended_method_after_timeout(self):
        model = {"lattice": {"sublattices": 1}, "simplified_model": {"template": "heisenberg"}}
        decision = classical_stage_decision(model, timed_out=True)
        self.assertEqual(decision["status"], "ok")
        self.assertEqual(decision["method"], "luttinger-tisza")
        self.assertTrue(decision["auto_selected"])

    def test_thermodynamics_stage_requests_confirmation_when_unspecified(self):
        decision = thermodynamics_stage_decision()
        self.assertEqual(decision["status"], "needs_input")
        self.assertEqual(decision["question"]["id"], "run_thermodynamics")

    def test_linear_spin_wave_stage_requests_enable_confirmation_first(self):
        decision = linear_spin_wave_stage_decision({"lattice": {"kind": "chain"}})
        self.assertEqual(decision["status"], "needs_input")
        self.assertEqual(decision["question"]["id"], "run_lswt")

    def test_linear_spin_wave_stage_requests_q_path_mode_when_enabled_without_path(self):
        decision = linear_spin_wave_stage_decision({"lattice": {"kind": "chain"}}, run_lswt=True)
        self.assertEqual(decision["status"], "needs_input")
        self.assertEqual(decision["question"]["id"], "lswt_q_path_mode")
        self.assertEqual(decision["recommended"], "auto")

    def test_linear_spin_wave_stage_accepts_existing_q_path_without_extra_question(self):
        decision = linear_spin_wave_stage_decision(
            {"lattice": {"kind": "chain"}, "q_path": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]]},
            run_lswt=True,
        )
        self.assertEqual(decision["status"], "ok")
        self.assertEqual(decision["q_path_mode"], "user-specified")

    def test_exact_diagonalization_stage_skips_when_cluster_scope_absent(self):
        decision = exact_diagonalization_stage_decision({"lattice": {"kind": "chain"}})
        self.assertEqual(decision["status"], "ok")
        self.assertFalse(decision["enabled"])

    def test_exact_diagonalization_stage_requests_confirmation_when_cluster_scope_present(self):
        decision = exact_diagonalization_stage_decision({"local_dim": 2, "cluster_size": 2})
        self.assertEqual(decision["status"], "needs_input")
        self.assertEqual(decision["question"]["id"], "run_exact_diagonalization")


if __name__ == "__main__":
    unittest.main()
