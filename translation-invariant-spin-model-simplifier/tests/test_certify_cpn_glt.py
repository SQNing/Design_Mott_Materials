import io
import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical.certified_glt.certify_cpn_glt import (
    _recommend_next_action,
    _recommend_next_actions,
    certify_cpn_generalized_lt,
)
from classical.certified_glt.progress import ProgressReporter


def _complex(value):
    return {"real": float(value.real), "imag": float(value.imag)}


def _serialized_tensor(local_dimension, entries):
    tensor = []
    for a in range(local_dimension):
        block_a = []
        for b in range(local_dimension):
            block_b = []
            for c in range(local_dimension):
                row = []
                for d in range(local_dimension):
                    row.append(_complex(entries.get((a, b, c, d), 0.0 + 0.0j)))
                block_b.append(row)
            block_a.append(block_b)
        tensor.append(block_a)
    return tensor


def _minimal_cpn_model():
    return {
        "model_version": 2,
        "model_type": "sun_gswt_classical",
        "classical_manifold": "CP^(N-1)",
        "basis_order": "orbital_major_spin_minor",
        "pair_basis_order": "site_i_major_site_j_minor",
        "local_dimension": 2,
        "orbital_count": 1,
        "local_basis_labels": ["up", "down"],
        "positions": [[0.0, 0.0, 0.0]],
        "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "bond_count": 1,
        "bond_tensors": [
            {
                "R": [1, 0, 0],
                "distance": 1.0,
                "matrix_shape": [4, 4],
                "tensor_shape": [2, 2, 2, 2],
                "tensor": _serialized_tensor(
                    2,
                    {
                        (0, 0, 0, 0): -1.0,
                    },
                ),
            }
        ],
    }


class CertifyCpnGltTests(unittest.TestCase):
    def test_next_best_action_targets_dominant_uniform_axis(self):
        action = _recommend_next_action(
            {
                "dominant_axis": "log_p1",
                "dominant_blocking_reason": "uniform_weight_uncertainty",
                "dominant_channel": "uniform",
            },
            {
                "box": {
                    "names": ["q0", "log_p1"],
                    "lower": [0.0, -0.2],
                    "upper": [1.0, 0.3],
                    "depth": 3,
                }
            },
            {
                "q_vector": [0.125, 0.0, 0.0],
                "p_weights": [0.6, 0.4],
            },
            {
                "box_budget": 12,
                "tolerance": 1.0e-3,
                "shell_tolerance": 5.0e-2,
                "supercell_cutoff": 4,
                "weight_bound": 1.0,
            },
        )
        self.assertEqual(action["kind"], "refine_log_p_axis")
        self.assertEqual(action["target_axis"], "log_p1")
        self.assertEqual(action["blocking_reason"], "uniform_weight_uncertainty")
        self.assertEqual(action["seed_q_vector"], [0.125, 0.0, 0.0])
        self.assertEqual(action["suggested_knobs"]["axis_refinement_factor"], 2)
        self.assertEqual(action["suggested_knobs"]["box_budget_multiplier"], 2.0)
        self.assertEqual(action["suggested_run_config"]["box_budget"], 24)
        self.assertEqual(action["suggested_run_config"]["focus_axis"], "log_p1")
        self.assertIn("certify_cpn_generalized_lt(", action["suggested_python_call"])
        self.assertIn("'box_budget': 24", action["suggested_python_call"])

    def test_next_best_actions_returns_ranked_candidates(self):
        actions = _recommend_next_actions(
            {
                "dominant_axis": "q1",
                "dominant_blocking_reason": "nonzero_q_dispersion_uncertainty",
                "dominant_channel": "nonzero_q",
                "queue_reorders_triggered": 2,
            },
            {
                "box": {
                    "names": ["q0", "q1"],
                    "lower": [0.0, 0.2],
                    "upper": [1.0, 0.4],
                    "depth": 2,
                }
            },
            {
                "q_vector": [0.1, 0.3, 0.0],
                "p_weights": [1.0],
            },
            {
                "box_budget": 10,
                "tolerance": 1.0e-3,
                "shell_tolerance": 5.0e-2,
                "supercell_cutoff": 3,
                "weight_bound": 1.0,
            },
        )
        self.assertGreaterEqual(len(actions), 2)
        self.assertEqual(actions[0]["kind"], "refine_q_axis")
        self.assertEqual(actions[0]["priority_rank"], 1)
        self.assertEqual(actions[1]["priority_rank"], 2)
        self.assertEqual(actions[0]["target_axis"], "q1")
        self.assertEqual(actions[0]["suggested_knobs"]["preferred_resolution"], "nonzero_q")
        self.assertIn("box_budget_multiplier", actions[1]["suggested_knobs"])
        self.assertEqual(actions[0]["suggested_run_config"]["box_budget"], 20)
        self.assertEqual(actions[0]["suggested_run_config"]["preferred_resolution"], "nonzero_q")
        self.assertIn("'focus_axis': 'q1'", actions[0]["suggested_python_call"])

    def test_top_level_certifier_returns_all_certificate_sections(self):
        stream = io.StringIO()
        reporter = ProgressReporter(stream=stream)
        result = certify_cpn_generalized_lt(
            _minimal_cpn_model(),
            reporter=reporter,
            box_budget=4,
            tolerance=1.0e-2,
            shell_tolerance=5.0e-2,
            supercell_cutoff=2,
        )
        self.assertIn("relaxed_global_bound", result)
        self.assertIn("lowest_shell_certificate", result)
        self.assertIn("commensurate_lift_certificate", result)
        self.assertIn("projector_exactness_certificate", result)
        self.assertIn("promotion_summary", result)
        self.assertIn("heuristic_seed", result)
        self.assertIn("search_summary", result)
        self.assertIn("next_best_action", result)
        self.assertIn("next_best_actions", result)
        self.assertIn("refinement", result["heuristic_seed"])
        self.assertIn("processed=", stream.getvalue())

    def test_top_level_certifier_reports_final_promotion_when_projector_certificate_is_certified(self):
        result = certify_cpn_generalized_lt(
            _minimal_cpn_model(),
            box_budget=4,
            tolerance=1.0e-2,
            shell_tolerance=5.0e-2,
            supercell_cutoff=2,
        )
        self.assertEqual(result["promotion_summary"]["solver_role"], "final")
        self.assertIn(
            result["promotion_summary"]["promotion_reason"],
            {"certified_projector_solution", "certified_commensurate_lift"},
        )

    def test_top_level_certifier_remains_structured_when_lifting_is_inconclusive(self):
        result = certify_cpn_generalized_lt(
            _minimal_cpn_model(),
            box_budget=2,
            tolerance=1.0e-1,
            shell_tolerance=1.0e-1,
            supercell_cutoff=1,
        )
        self.assertIn(result["commensurate_lift_certificate"]["status"], {"commensurate_certified", "incommensurate_supported", "inconclusive"})
        self.assertIn(result["relaxed_global_bound"]["status"], {"certified", "inconclusive"})
        self.assertIn("search_summary", result)

    def test_top_level_certifier_reports_search_summary_consistently(self):
        result = certify_cpn_generalized_lt(
            _minimal_cpn_model(),
            box_budget=6,
            tolerance=1.0e-2,
            shell_tolerance=5.0e-2,
            supercell_cutoff=2,
        )
        summary = result["search_summary"]
        statistics = result["relaxed_global_bound"]["statistics"]

        self.assertEqual(summary["processed_boxes"], statistics["processed_boxes"])
        self.assertEqual(summary["split_boxes"], statistics["split_boxes"])
        self.assertEqual(sum(summary["axis_split_counts"].values()), statistics["split_boxes"])
        self.assertEqual(
            summary["evaluated_boxes"],
            sum(summary["branch_kind_counts"].values()),
        )
        self.assertIsInstance(summary["axis_split_counts"], dict)
        self.assertIsInstance(summary["axis_gap_reduction_totals"], dict)
        self.assertIsInstance(summary["channel_gap_reduction_totals"], dict)
        self.assertIsInstance(summary["priority_pressure_by_axis"], dict)
        self.assertIsInstance(summary["priority_pressure_by_channel"], dict)
        self.assertGreaterEqual(summary["queue_reorders_triggered"], 0)
        self.assertIn(
            summary["dominant_gap_channel"],
            {"uniform", "nonzero_q", "generic", None},
        )
        self.assertIn(
            summary["dominant_queue_pressure_channel"],
            {"uniform", "nonzero_q", "generic", None},
        )
        if statistics["split_boxes"] > 0:
            self.assertIsNotNone(summary["dominant_split_axis"])
            self.assertIn(summary["dominant_split_axis"], summary["axis_split_counts"])

    def test_top_level_certifier_search_summary_tracks_branch_mix(self):
        result = certify_cpn_generalized_lt(
            _minimal_cpn_model(),
            box_budget=4,
            tolerance=1.0e-1,
            shell_tolerance=1.0e-1,
            supercell_cutoff=1,
        )
        summary = result["search_summary"]
        self.assertIsInstance(summary["branch_kind_counts"], dict)
        self.assertGreaterEqual(sum(summary["branch_kind_counts"].values()), 1)
        self.assertIn(
            summary["dominant_branch_kind"],
            {"uniform", "nonzero-q", "mixed", None},
        )

    def test_top_level_certifier_carries_shell_pressure_into_lift_certificate(self):
        result = certify_cpn_generalized_lt(
            _minimal_cpn_model(),
            box_budget=4,
            tolerance=1.0e-1,
            shell_tolerance=1.0e-1,
            supercell_cutoff=1,
        )
        shell_summary = result["lowest_shell_certificate"]["unresolved_pressure_summary"]
        lift_summary = result["commensurate_lift_certificate"]["shell_pressure_summary"]
        self.assertEqual(
            lift_summary.get("dominant_channel"),
            shell_summary.get("dominant_channel"),
        )
        self.assertEqual(
            lift_summary.get("queue_reorders_triggered"),
            shell_summary.get("queue_reorders_triggered"),
        )
        self.assertEqual(
            lift_summary.get("dominant_blocking_reason"),
            shell_summary.get("dominant_blocking_reason"),
        )

    def test_top_level_certifier_surfaces_next_best_action_in_shell_and_lift_context(self):
        result = certify_cpn_generalized_lt(
            _minimal_cpn_model(),
            box_budget=4,
            tolerance=1.0e-1,
            shell_tolerance=1.0e-1,
            supercell_cutoff=1,
        )
        action = result["next_best_action"]
        shell_action = result["lowest_shell_certificate"]["unresolved_pressure_summary"]["next_best_action"]
        lift_action = result["commensurate_lift_certificate"]["shell_pressure_summary"]["next_best_action"]
        self.assertEqual(shell_action["kind"], action["kind"])
        self.assertEqual(lift_action["kind"], action["kind"])
        self.assertEqual(result["next_best_actions"][0]["kind"], action["kind"])
        self.assertEqual(
            result["lowest_shell_certificate"]["unresolved_pressure_summary"]["next_best_actions"][0]["kind"],
            action["kind"],
        )
        self.assertEqual(
            result["commensurate_lift_certificate"]["shell_pressure_summary"]["next_best_actions"][0]["kind"],
            action["kind"],
        )
        self.assertIn("suggested_knobs", action)
        self.assertIn("box_budget_multiplier", action["suggested_knobs"])
        self.assertIn("suggested_run_config", action)
        self.assertIn("box_budget", action["suggested_run_config"])
        self.assertIn("suggested_python_call", action)
        self.assertIn("certify_cpn_generalized_lt(", action["suggested_python_call"])
        self.assertIn(
            action["kind"],
            {
                "certificate_already_tight",
                "refine_log_p_axis",
                "refine_q_axis",
                "increase_branch_resolution",
                "inspect_generic_uncertainty",
            },
        )


if __name__ == "__main__":
    unittest.main()
