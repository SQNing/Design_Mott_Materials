import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical.lt_constraint_recovery import recover_classical_state_from_lt
from classical.lt_tensor_constraint_completion import complete_lt_constraints


def _complex(real, imag=0.0):
    return {"real": float(real), "imag": float(imag)}


def _spin_model(*, sublattices=1):
    return {
        "classical": {"method": "luttinger-tisza"},
        "local_dim": 2,
        "lattice": {
            "sublattices": int(sublattices),
            "dimension": 1,
            "positions": [[float(index), 0.0, 0.0] for index in range(sublattices)],
        },
        "bonds": [],
    }


class LtTensorConstraintCompletionTests(unittest.TestCase):
    def test_exact_relaxed_hit_accepts_component_resolved_single_q_mode(self):
        model = _spin_model(sublattices=1)
        relaxed_solution = {
            "q": [0.0, 0.0, 0.0],
            "eigenspace": [[_complex(0.0), _complex(1.0), _complex(0.0)]],
        }

        result = complete_lt_constraints(relaxed_solution, model)

        self.assertEqual(result["status"], "exact_relaxed_hit")
        self.assertLess(result["max_site_norm_residual"], 1.0e-8)
        self.assertEqual(len(result["site_frames"]), 1)
        self.assertEqual(result["site_frames"][0]["direction"], [0.0, 1.0, 0.0])

    def test_shell_completion_promotes_multi_mode_solution_when_site_norms_can_be_restored(self):
        model = _spin_model(sublattices=2)
        relaxed_solution = {
            "q": [0.0, 0.0, 0.0],
            "eigenspace": [
                [_complex(1.0), _complex(0.0), _complex(0.0), _complex(0.0), _complex(0.0), _complex(0.0)],
                [_complex(0.0), _complex(0.0), _complex(0.0), _complex(1.0), _complex(0.0), _complex(0.0)],
            ],
        }

        result = complete_lt_constraints(relaxed_solution, model)

        self.assertEqual(result["status"], "completed_from_shell")
        self.assertLess(result["max_site_norm_residual"], 1.0e-8)
        self.assertEqual(result["site_norms"], [1.0, 1.0])

    def test_completion_reports_residual_when_shell_cannot_satisfy_strong_constraints(self):
        model = _spin_model(sublattices=2)
        relaxed_solution = {
            "q": [0.0, 0.0, 0.0],
            "eigenspace": [
                [_complex(0.5), _complex(0.0), _complex(0.0), _complex(0.0), _complex(0.0), _complex(0.0)]
            ],
        }

        result = complete_lt_constraints(relaxed_solution, model)

        self.assertEqual(result["status"], "requires_variational_polish")
        self.assertGreater(result["max_site_norm_residual"], 1.0e-3)
        self.assertIn("variational_seed", result)

    def test_lt_constraint_recovery_uses_tensor_completion_for_component_resolved_modes(self):
        model = _spin_model(sublattices=1)
        amplitudes = [_complex(1.0), _complex(0.0), _complex(0.0)]

        result = recover_classical_state_from_lt(
            model,
            q=[0.0, 0.0, 0.0],
            amplitudes=amplitudes,
            spin_length=0.5,
            source="lt",
        )

        self.assertEqual(result["constraint_recovery"]["status"], "exact_relaxed_hit")
        self.assertLess(result["constraint_recovery"]["max_site_norm_residual"], 1.0e-8)
        self.assertEqual(result["site_frames"][0]["direction"], [1.0, 0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
