import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical.classical_solver_driver import (
    _build_variational_classical_state,
    _recover_lt_classical_state,
    _single_q_cosine_constraints_and_jacobian,
    _single_q_cosine_value_and_gradient,
    classical_energy,
    run_classical_solver,
)
from classical.compare_spin_only_classical_methods import compare_spin_only_classical_methods
from classical.lt_fourier_exchange import fourier_exchange_matrix
from lswt.build_lswt_payload import build_lswt_payload


class ClassicalSolverDriverTests(unittest.TestCase):
    @staticmethod
    def _one_site_antiferromagnetic_chain():
        return {
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "positions": [[0.0, 0.0, 0.0]],
                "lattice_vectors": [
                    [1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.0, 0.0, 1.0],
                ],
                "magnetic_site_count": 1,
                "magnetic_sites": [[0.0, 0.0, 0.0]],
            },
            "positions": [[0.0, 0.0, 0.0]],
            "bonds": [
                {
                    "source": 0,
                    "target": 0,
                    "vector": [1.0, 0.0, 0.0],
                    "matrix": [
                        [1.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0],
                        [0.0, 0.0, 1.0],
                    ],
                }
            ],
            "classical": {
                "method": "variational",
                "variational": {
                    "max_linear_size": 2,
                    "convergence_repeats": 1,
                    "max_sweeps": 200,
                    "sweep_tolerance": 1.0e-10,
                    "energy_tolerance": 1.0e-8,
                },
            },
        }

    @staticmethod
    def _one_site_chain_with_easy_axis_onsite():
        model = ClassicalSolverDriverTests._one_site_antiferromagnetic_chain()
        model["onsite_terms"] = [
            {
                "kind": "quadratic_spin_cartesian",
                "site_scope": {"kind": "site", "site": 0},
                "operator_basis": {
                    "family": "spin_cartesian",
                    "components": ["Sx", "Sy", "Sz"],
                },
                "frame": {
                    "kind": "global_cartesian",
                    "axes": ["x", "y", "z"],
                },
                "payload": {
                    "matrix": [
                        [0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0],
                        [0.0, 0.0, -2.165],
                    ]
                },
            }
        ]
        return model

    @staticmethod
    def _one_site_zero_chain_with_lt_quarter_seed():
        return {
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "positions": [[0.0, 0.0, 0.0]],
                "lattice_vectors": [
                    [1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.0, 0.0, 1.0],
                ],
                "magnetic_site_count": 1,
                "magnetic_sites": [[0.0, 0.0, 0.0]],
                "sublattices": 1,
            },
            "positions": [[0.0, 0.0, 0.0]],
            "bonds": [
                {
                    "source": 0,
                    "target": 0,
                    "vector": [1.0, 0.0, 0.0],
                    "matrix": [
                        [0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0],
                    ],
                }
            ],
            "lt_result": {
                "q": [0.25, 0.0, 0.0],
                "eigenvector": [
                    {"real": 1.0, "imag": 0.0},
                    {"real": 0.0, "imag": 1.0},
                    {"real": 0.0, "imag": 0.0},
                ],
                "eigenspace": [
                    [
                        {"real": 1.0, "imag": 0.0},
                        {"real": 0.0, "imag": 1.0},
                        {"real": 0.0, "imag": 0.0},
                    ]
                ],
            },
            "classical": {
                "method": "variational",
                "variational": {
                    "max_linear_size": 2,
                    "convergence_repeats": 1,
                    "max_sweeps": 10,
                    "sweep_tolerance": 1.0e-10,
                    "energy_tolerance": 1.0e-8,
                    "lt_seed_enabled": True,
                },
            },
        }

    @staticmethod
    def _one_site_antiferromagnetic_chain_with_lt_quarter_seed():
        model = ClassicalSolverDriverTests._one_site_antiferromagnetic_chain()
        model["lt_result"] = {
            "q": [0.25, 0.0, 0.0],
            "eigenvector": [
                {"real": 1.0, "imag": 0.0},
                {"real": 0.0, "imag": 1.0},
                {"real": 0.0, "imag": 0.0},
            ],
            "eigenspace": [
                [
                    {"real": 1.0, "imag": 0.0},
                    {"real": 0.0, "imag": 1.0},
                    {"real": 0.0, "imag": 0.0},
                ]
            ],
        }
        model["classical"]["variational"]["mode"] = "lt-single-q-cosine"
        model["classical"]["variational"]["maxiter"] = 200
        return model

    @staticmethod
    def _one_site_antiferromagnetic_chain_with_lt_quarter_seed_harmonic():
        model = ClassicalSolverDriverTests._one_site_antiferromagnetic_chain_with_lt_quarter_seed()
        model["classical"]["variational"]["mode"] = "lt-single-q-harmonic"
        return model

    def test_classical_energy_includes_onsite_quadratic_term(self):
        spins = np.array([[0.0, 0.0, 1.0]])

        bond_only_energy = classical_energy(
            self._one_site_antiferromagnetic_chain(),
            spins,
        )
        onsite_energy = classical_energy(
            self._one_site_chain_with_easy_axis_onsite(),
            spins,
        )

        self.assertAlmostEqual(onsite_energy - bond_only_energy, -2.165, places=6)

    def test_lt_fourier_exchange_includes_onsite_local_block(self):
        bond_only = fourier_exchange_matrix(
            self._one_site_antiferromagnetic_chain(),
            [0.0, 0.0, 0.0],
        )
        with_onsite = fourier_exchange_matrix(
            self._one_site_chain_with_easy_axis_onsite(),
            [0.0, 0.0, 0.0],
        )

        self.assertAlmostEqual(
            float(np.real(with_onsite[2, 2] - bond_only[2, 2])),
            -2.165,
            places=6,
        )

    def test_auto_variational_searches_supercell_and_returns_single_q_contract(self):
        result = run_classical_solver(
            self._one_site_antiferromagnetic_chain(),
            starts=4,
            seed=3,
        )

        self.assertEqual(result["classical"]["chosen_method"], "variational")
        self.assertLess(result["classical_state_result"]["energy"], -0.9)
        self.assertEqual(result["classical_state_result"]["supercell_shape"], [2, 1, 1])
        self.assertAlmostEqual(
            result["classical_state_result"]["ordering"]["q_vector"][0],
            0.5,
            places=6,
        )
        self.assertIn("rotating_frame_realization", result)
        self.assertEqual(
            result["rotating_frame_realization"]["supercell_shape"],
            [2, 1, 1],
        )
        self.assertEqual(
            result["rotating_frame_realization"]["kind"],
            "single_q_site_phase_rotation",
        )
        self.assertEqual(
            result["variational_result"]["diagnostics_summary"]["single_q_fit_status"],
            "single-q-compatible",
        )
        self.assertEqual(
            result["variational_result"]["search_settings"]["max_linear_size"],
            2,
        )
        self.assertEqual(
            result["variational_result"]["convergence"]["stopped_reason"],
            "max_linear_size_reached",
        )
        self.assertEqual(
            result["variational_result"]["diagnostics_summary"]["search_limit_hit"],
            True,
        )

    def test_lswt_builder_exports_single_q_reference_state_from_supercell_variational_output(self):
        result = run_classical_solver(
            self._one_site_antiferromagnetic_chain(),
            starts=4,
            seed=3,
        )

        lswt_payload = build_lswt_payload(result)

        self.assertEqual(lswt_payload["status"], "ok")
        payload = lswt_payload["payload"]
        self.assertEqual(payload["supercell_shape"], [2, 1, 1])
        self.assertNotIn("supercell_reference_frames", payload)
        self.assertEqual(payload["single_q_reference_state"]["kind"], "single_q_spiral")
        self.assertEqual(payload["single_q_reference_state"]["q_vector"], [0.5, 0.0, 0.0])
        self.assertEqual(payload["single_q_reference_state"]["rotation_axis"], [0.0, -0.0, 1.0])
        self.assertEqual(payload["single_q_reference_state"]["site_phase_offsets"], {"0": 0.0})
        self.assertEqual(len(payload["single_q_reference_state"]["reference_frames"]), 1)
        self.assertEqual(
            payload["single_q_reference_state"]["reference_frames"][0]["direction"],
            [1.0, -0.0, -0.0],
        )

    def test_auto_prefers_lt_for_single_sublattice_generic_bilinear_model(self):
        model = self._one_site_antiferromagnetic_chain()
        model["classical"]["method"] = "auto"

        result = run_classical_solver(
            model,
            starts=4,
            seed=3,
        )

        self.assertEqual(result["recommended_method"], "luttinger-tisza")
        self.assertEqual(result["classical"]["chosen_method"], "luttinger-tisza")
        self.assertEqual(result["classical"]["auto_resolution"]["reason"], "lt-completion-succeeded")
        self.assertIn("luttinger-tisza", result["classical"]["auto_resolution"]["evaluated_methods"])
        self.assertNotIn("variational", result["classical"]["auto_resolution"]["evaluated_methods"])
        self.assertLess(result["classical_state_result"]["energy"], -1.9)

    def test_method_comparison_helper_summarizes_spin_only_methods(self):
        model = self._one_site_antiferromagnetic_chain()

        comparison = compare_spin_only_classical_methods(model, starts=4, seed=3)

        self.assertEqual(sorted(comparison["methods"]), ["auto", "generalized-lt", "luttinger-tisza", "variational"])
        self.assertEqual(comparison["comparison"]["best_energy_method"], "luttinger-tisza")
        self.assertEqual(comparison["results"]["auto"]["chosen_method"], "luttinger-tisza")
        self.assertEqual(comparison["results"]["variational"]["ordering"]["q_vector"], [0.5, 0.0, 0.0])
        self.assertEqual(comparison["results"]["auto"]["lswt_route"]["status"], "ready")

    def test_variational_reports_lt_seed_usage_for_single_q_supercell_search(self):
        model = self._one_site_antiferromagnetic_chain()

        result = run_classical_solver(
            model,
            starts=1,
            seed=0,
        )

        self.assertEqual(result["classical"]["chosen_method"], "variational")
        self.assertEqual(result["variational_result"]["search_settings"]["lt_seed_enabled"], True)
        self.assertEqual(result["variational_result"]["initialization"]["lt_seed_status"], "applied")
        self.assertEqual(
            result["variational_result"]["initialization"]["lt_seed_commensurate_shape"],
            [2, 1, 1],
        )
        self.assertEqual(
            result["variational_result"]["diagnostics_summary"]["lt_seed_status"],
            "applied",
        )
        self.assertEqual(
            result["variational_result"]["diagnostics_summary"]["lt_seed_q_vector"],
            [0.5, 0.0, 0.0],
        )

    def test_explicit_lt_skips_variational_when_constraint_completion_is_exact(self):
        model = self._one_site_antiferromagnetic_chain()
        model["classical"]["method"] = "luttinger-tisza"

        result = run_classical_solver(
            model,
            starts=4,
            seed=3,
        )

        self.assertEqual(result["classical"]["chosen_method"], "luttinger-tisza")
        self.assertEqual(result["classical"]["auto_resolution"]["reason"], "lt-completion-succeeded")
        self.assertEqual(result["classical"]["auto_resolution"]["lt_residual"], 0.0)
        self.assertNotIn("variational_result", result)
        self.assertEqual(result["classical_state_result"]["ordering"]["q_vector"], [0.5, 0.0, 0.0])

    def test_explicit_lt_falls_back_to_seeded_variational_when_lt_is_not_exact(self):
        model = self._one_site_antiferromagnetic_chain()
        model["classical"]["method"] = "luttinger-tisza"

        with patch("classical.classical_solver_driver._constraint_completion_succeeds", return_value=False):
            result = run_classical_solver(
                model,
                starts=1,
                seed=0,
            )

        self.assertEqual(result["classical"]["chosen_method"], "variational")
        self.assertEqual(result["classical"]["auto_resolution"]["reason"], "lt-needs-variational-polish")
        self.assertEqual(result["variational_result"]["initialization"]["lt_seed_status"], "applied")
        self.assertEqual(result["variational_result"]["diagnostics_summary"]["lt_seed_q_vector"], [0.5, 0.0, 0.0])

    def test_lt_recovery_can_use_minimum_shell_payload(self):
        payload = self._one_site_antiferromagnetic_chain()
        payload["lattice"]["positions"] = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
        payload["lattice"]["sublattices"] = 2
        payload["lt_result"] = {
            "minimum_shell": {
                "sectors": [
                    {
                        "q": [0.0, 0.0, 0.0],
                        "eigenspace": [
                            [
                                {"real": 1.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                            ]
                        ],
                    },
                    {
                        "q": [0.5, 0.0, 0.0],
                        "eigenspace": [
                            [
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                                {"real": 1.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                            ]
                        ],
                    },
                ]
            },
            "q": [0.0, 0.0, 0.0],
            "eigenvector": [
                {"real": 1.0, "imag": 0.0},
                {"real": 0.0, "imag": 0.0},
                {"real": 0.0, "imag": 0.0},
                {"real": 0.0, "imag": 0.0},
                {"real": 0.0, "imag": 0.0},
                {"real": 0.0, "imag": 0.0},
            ],
        }

        classical_state = _recover_lt_classical_state(payload, "luttinger-tisza")

        self.assertIsNotNone(classical_state)
        self.assertEqual(classical_state["constraint_recovery"]["status"], "completed_from_shell")
        self.assertLess(classical_state["constraint_recovery"]["max_site_norm_residual"], 1.0e-8)

    def test_variational_starts_from_lt_commensurate_shape_for_single_q_seed(self):
        result = run_classical_solver(
            self._one_site_zero_chain_with_lt_quarter_seed(),
            starts=1,
            seed=0,
        )

        history = result["variational_result"]["convergence"]["history"]
        self.assertEqual(history[0]["shape"], [4, 1, 1])
        self.assertEqual(
            result["variational_result"]["initialization"]["lt_seed_commensurate_shape"],
            [4, 1, 1],
        )

    def test_variational_reports_lt_single_q_cosine_seed_source(self):
        result = run_classical_solver(
            self._one_site_zero_chain_with_lt_quarter_seed(),
            starts=1,
            seed=0,
        )

        self.assertEqual(
            result["variational_result"]["initialization"]["lt_seed_source"],
            "lt-single-q-cosine-ansatz",
        )

    def test_lt_single_q_cosine_variational_uses_explicit_norm_constraints(self):
        result = run_classical_solver(
            self._one_site_antiferromagnetic_chain_with_lt_quarter_seed(),
            starts=4,
            seed=2,
        )

        self.assertEqual(result["classical"]["chosen_method"], "variational")
        self.assertEqual(result["variational_result"]["ansatz"], "lt-single-q-cosine")
        self.assertEqual(result["variational_result"]["search_settings"]["mode"], "lt-single-q-cosine")
        self.assertEqual(result["variational_result"]["supercell_shape"], [4, 1, 1])
        self.assertEqual(result["variational_result"]["ansatz_stationarity"]["optimizer_method"], "trust-constr")
        self.assertLess(
            result["variational_result"]["ansatz_stationarity"]["optimizer_constraint_violation"],
            1.0e-8,
        )
        self.assertLess(
            result["variational_result"]["ansatz_stationarity"]["raw_norm_diagnostics"]["max_abs_norm_minus_1"],
            1.0e-8,
        )
        self.assertEqual(
            result["variational_result"]["initialization"]["lt_seed_q_vector"],
            [0.25, 0.0, 0.0],
        )

    def test_lt_single_q_harmonic_variational_routes_and_reports_contract(self):
        result = run_classical_solver(
            self._one_site_antiferromagnetic_chain_with_lt_quarter_seed_harmonic(),
            starts=1,
            seed=0,
        )

        self.assertEqual(result["classical"]["chosen_method"], "variational")
        self.assertEqual(result["variational_result"]["ansatz"], "lt-single-q-harmonic")
        self.assertEqual(result["variational_result"]["search_settings"]["mode"], "lt-single-q-harmonic")
        self.assertEqual(result["variational_result"]["supercell_shape"], [4, 1, 1])
        self.assertEqual(result["variational_result"]["ordering"]["ansatz"], "lt-single-q-harmonic")

    def test_lt_single_q_harmonic_variational_uses_explicit_norm_constraints(self):
        result = run_classical_solver(
            self._one_site_antiferromagnetic_chain_with_lt_quarter_seed_harmonic(),
            starts=4,
            seed=2,
        )

        self.assertEqual(result["variational_result"]["ansatz_stationarity"]["optimizer_method"], "minimize-spiral-manifold-cg")
        self.assertEqual(
            result["variational_result"]["ansatz_stationarity"]["optimization_mode"],
            "lt-seeded-minimize-spiral-manifold-cg-and-q-relaxation",
        )
        self.assertLess(
            result["variational_result"]["ansatz_stationarity"]["raw_norm_diagnostics"]["max_abs_norm_minus_1"],
            1.0e-8,
        )
        self.assertEqual(
            result["variational_result"]["initialization"]["lt_seed_q_vector"],
            [0.25, 0.0, 0.0],
        )
        self.assertLessEqual(
            result["variational_result"]["energy"],
            result["variational_result"]["ansatz_stationarity"]["initial_objective"] + 1.0e-10,
        )
        self.assertIn("spin_gradient_norm", result["variational_result"]["ansatz_stationarity"])
        self.assertIn("q_gradient_norm", result["variational_result"]["ansatz_stationarity"])
        self.assertIn("gradient_tolerance_scale", result["variational_result"]["ansatz_stationarity"])
        self.assertIn("effective_spin_gradient_tolerance", result["variational_result"]["ansatz_stationarity"])
        self.assertIn("effective_q_gradient_tolerance", result["variational_result"]["ansatz_stationarity"])
        self.assertIn("restart_count", result["variational_result"]["ansatz_stationarity"])
        self.assertIn("line_search_restart_count", result["variational_result"]["ansatz_stationarity"])
        self.assertIn("final_beta", result["variational_result"]["ansatz_stationarity"])
        self.assertIn("beta_clamped_count", result["variational_result"]["ansatz_stationarity"])
        self.assertIn("optimized_cosine_coefficients", result["variational_result"]["ansatz_stationarity"])
        self.assertIn("optimized_sine_coefficients", result["variational_result"]["ansatz_stationarity"])

    def test_lt_single_q_harmonic_variational_reports_start_diagnostics(self):
        result = run_classical_solver(
            self._one_site_antiferromagnetic_chain_with_lt_quarter_seed_harmonic(),
            starts=4,
            seed=2,
        )

        stationarity = result["variational_result"]["ansatz_stationarity"]
        candidate_summaries = stationarity["candidate_start_summaries"]
        self.assertEqual(len(candidate_summaries), 4)
        self.assertEqual(
            [item["start_source"] for item in candidate_summaries],
            [
                "lt-harmonic-seed",
                "lt-aligned-feasible",
                "planar-feasible",
                "uniform-feasible",
            ],
        )
        self.assertEqual(
            [item["start_index"] for item in candidate_summaries],
            [0, 1, 2, 3],
        )
        self.assertIn(stationarity["best_start_source"], [item["start_source"] for item in candidate_summaries])
        self.assertGreaterEqual(stationarity["best_start_index"], 0)

    def test_lt_single_q_harmonic_variational_reports_lt_randomized_start_sources(self):
        result = run_classical_solver(
            self._one_site_antiferromagnetic_chain_with_lt_quarter_seed_harmonic(),
            starts=6,
            seed=0,
        )

        candidate_summaries = result["variational_result"]["ansatz_stationarity"]["candidate_start_summaries"]
        self.assertEqual(
            [item["start_source"] for item in candidate_summaries],
            [
                "lt-harmonic-seed",
                "lt-aligned-feasible",
                "planar-feasible",
                "uniform-feasible",
                "lt-randomized-planar-0",
                "lt-randomized-planar-1",
            ],
        )

    def test_lt_single_q_harmonic_variational_reports_guided_q_start_sources(self):
        model = self._one_site_antiferromagnetic_chain_with_lt_quarter_seed_harmonic()
        model["classical"]["variational"]["guided_q_vectors"] = [
            [0.5, 0.25, 0.0],
            [0.75, 0.0, 0.0],
        ]

        result = run_classical_solver(
            model,
            starts=8,
            seed=0,
        )

        candidate_summaries = result["variational_result"]["ansatz_stationarity"]["candidate_start_summaries"]
        self.assertEqual(
            [item["start_source"] for item in candidate_summaries],
            [
                "lt-harmonic-seed",
                "lt-aligned-feasible",
                "planar-feasible",
                "uniform-feasible",
                "guided-lt-aligned-q-0",
                "guided-planar-q-0",
                "guided-lt-aligned-q-1",
                "guided-planar-q-1",
            ],
        )

    def test_single_q_harmonic_beta_clamp_helper_applies_ceiling(self):
        from classical.classical_solver_driver import _single_q_harmonic_clamp_beta

        beta, was_clamped = _single_q_harmonic_clamp_beta(18.5, 5.0)

        self.assertEqual(beta, 5.0)
        self.assertTrue(was_clamped)

    def test_single_q_harmonic_pair_retraction_returns_orthonormal_columns(self):
        from classical.classical_solver_driver import _single_q_harmonic_retract_pair

        pair = np.array(
            [
                [1.2, 0.1],
                [0.3, 0.9],
                [0.0, 0.4],
            ],
            dtype=float,
        )

        retracted = _single_q_harmonic_retract_pair(pair)

        np.testing.assert_allclose(retracted.T @ retracted, np.eye(2), atol=1.0e-8)

    def test_single_q_harmonic_pair_tangent_projection_satisfies_stiefel_condition(self):
        from classical.classical_solver_driver import (
            _single_q_harmonic_project_pair_tangent,
            _single_q_harmonic_retract_pair,
        )

        pair = _single_q_harmonic_retract_pair(
            np.array(
                [
                    [1.2, 0.1],
                    [0.3, 0.9],
                    [0.0, 0.4],
                ],
                dtype=float,
            )
        )
        gradient = np.array(
            [
                [0.2, -0.1],
                [-0.4, 0.3],
                [0.7, 0.5],
            ],
            dtype=float,
        )

        projected = _single_q_harmonic_project_pair_tangent(pair, gradient)

        np.testing.assert_allclose(
            pair.T @ projected + projected.T @ pair,
            np.zeros((2, 2), dtype=float),
            atol=1.0e-8,
        )

    def test_single_q_harmonic_retract_vector_wraps_q_periodically(self):
        from classical.classical_solver_driver import (
            _single_q_harmonic_retract_vector,
            _single_q_harmonic_vector,
            _split_single_q_harmonic_vector,
        )

        model = self._one_site_antiferromagnetic_chain()
        vector = _single_q_harmonic_vector(
            model,
            np.array([0.6], dtype=float),
            np.array([[1.0, 0.0, 0.0]], dtype=float),
            np.array([[0.0, 1.0, 0.0]], dtype=float),
        )

        retracted = _single_q_harmonic_retract_vector(
            model,
            vector,
            site_count=1,
            q_bounds=[(-0.5, 0.5)],
        )
        wrapped_q, _cosine, _sine = _split_single_q_harmonic_vector(
            model,
            retracted,
            site_count=1,
        )

        self.assertAlmostEqual(wrapped_q[0], -0.4, places=6)

    def test_single_q_harmonic_jitter_vector_changes_spin_plane_but_preserves_constraints(self):
        from classical.classical_solver_driver import (
            _single_q_harmonic_jitter_vector,
            _single_q_harmonic_vector,
            _split_single_q_harmonic_vector,
        )

        model = self._one_site_antiferromagnetic_chain()
        vector = _single_q_harmonic_vector(
            model,
            np.array([0.25], dtype=float),
            np.array([[1.0, 0.0, 0.0]], dtype=float),
            np.array([[0.0, 1.0, 0.0]], dtype=float),
        )

        jittered = _single_q_harmonic_jitter_vector(
            model,
            vector,
            site_count=1,
            q_bounds=[(-0.5, 0.5)],
            rng=np.random.default_rng(0),
            magnitude=1.0e-3,
        )
        _q_vector, cosine, sine = _split_single_q_harmonic_vector(
            model,
            jittered,
            site_count=1,
        )
        pair = np.column_stack([cosine[0], sine[0]])

        self.assertFalse(np.allclose(jittered, vector))
        np.testing.assert_allclose(pair.T @ pair, np.eye(2), atol=1.0e-8)

    def test_single_q_harmonic_characteristic_energy_scale_tracks_coupling_size(self):
        from classical.classical_solver_driver import _single_q_harmonic_characteristic_energy_scale

        weak_model = self._one_site_antiferromagnetic_chain()
        strong_model = self._one_site_antiferromagnetic_chain()
        strong_model["bonds"][0]["matrix"] = [
            [10.0, 0.0, 0.0],
            [0.0, 10.0, 0.0],
            [0.0, 0.0, 10.0],
        ]

        weak_scale = _single_q_harmonic_characteristic_energy_scale(weak_model)
        strong_scale = _single_q_harmonic_characteristic_energy_scale(strong_model)

        self.assertGreaterEqual(weak_scale, 1.0)
        self.assertGreater(strong_scale, weak_scale)

    def test_lt_single_q_harmonic_variational_restarts_after_line_search_failure(self):
        from classical import classical_solver_driver as driver

        model = self._one_site_antiferromagnetic_chain_with_lt_quarter_seed_harmonic()
        model["classical"]["variational"]["maxiter"] = 16
        real_backtracking_step = driver._single_q_harmonic_backtracking_step
        real_projected_gradient = driver._single_q_harmonic_projected_gradient
        call_count = {"count": 0}
        gradient_call_count = {"count": 0}

        def flaky_backtracking_step(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] == 1:
                return np.array(args[1], dtype=float, copy=True), float(kwargs["initial_value"]), 0.0, False, 0
            return real_backtracking_step(*args, **kwargs)

        def forced_nonzero_gradient(*args, **kwargs):
            gradient_call_count["count"] += 1
            if gradient_call_count["count"] == 1:
                vector = np.array(args[1], dtype=float, copy=False)
                gradient = np.ones_like(vector)
                q_count = len(driver._active_q_axes(model))
                return 0.0, np.zeros_like(vector), gradient, float(np.linalg.norm(gradient[q_count:])), float(
                    np.linalg.norm(gradient[:q_count])
                )
            return real_projected_gradient(*args, **kwargs)

        with patch.object(driver, "_single_q_harmonic_projected_gradient", side_effect=forced_nonzero_gradient):
            with patch.object(driver, "_single_q_harmonic_backtracking_step", side_effect=flaky_backtracking_step):
                result = driver.run_classical_solver(model, starts=1, seed=0)

        stationarity = result["variational_result"]["ansatz_stationarity"]
        stopped_reason = result["variational_result"]["convergence"]["stopped_reason"]
        self.assertGreater(call_count["count"], 0)
        self.assertGreaterEqual(stationarity["restart_count"], 1)
        self.assertGreaterEqual(stationarity["line_search_restart_count"], 1)
        self.assertEqual(stationarity["line_search_restart_count"], call_count["count"])
        self.assertNotEqual(stopped_reason, "minimize-line-search-failed")

    def test_single_q_cosine_analytic_gradient_matches_finite_difference(self):
        model = self._one_site_antiferromagnetic_chain()
        amplitudes = np.array([[0.8, 0.6, 0.4]], dtype=float)
        shape = [3, 1, 1]
        vector = np.array([0.27, 0.31, -0.42, 0.23, 0.8, 0.6, 0.4], dtype=float)

        value, gradient = _single_q_cosine_value_and_gradient(
            model,
            vector,
            amplitudes,
            shape,
            fallback_state=None,
        )

        finite_difference = np.zeros_like(vector)
        step = 1.0e-6
        for index in range(vector.size):
            plus = np.array(vector, copy=True)
            minus = np.array(vector, copy=True)
            plus[index] += step
            minus[index] -= step
            value_plus, _ = _single_q_cosine_value_and_gradient(
                model,
                plus,
                amplitudes,
                shape,
                fallback_state=None,
            )
            value_minus, _ = _single_q_cosine_value_and_gradient(
                model,
                minus,
                amplitudes,
                shape,
                fallback_state=None,
            )
            finite_difference[index] = (value_plus - value_minus) / (2.0 * step)

        self.assertTrue(np.isfinite(value))
        np.testing.assert_allclose(gradient, finite_difference, rtol=2.0e-5, atol=2.0e-6)

    def test_single_q_cosine_constraint_jacobian_matches_finite_difference(self):
        model = self._one_site_antiferromagnetic_chain()
        amplitudes = np.array([[0.8, 0.6, 0.4]], dtype=float)
        shape = [3, 1, 1]
        vector = np.array([0.27, 0.31, -0.42, 0.23, 0.8, 0.6, 0.4], dtype=float)

        constraints, jacobian = _single_q_cosine_constraints_and_jacobian(
            model,
            vector,
            amplitudes,
            shape,
        )

        finite_difference = np.zeros_like(jacobian)
        step = 1.0e-6
        for index in range(vector.size):
            plus = np.array(vector, copy=True)
            minus = np.array(vector, copy=True)
            plus[index] += step
            minus[index] -= step
            constraints_plus, _ = _single_q_cosine_constraints_and_jacobian(
                model,
                plus,
                amplitudes,
                shape,
            )
            constraints_minus, _ = _single_q_cosine_constraints_and_jacobian(
                model,
                minus,
                amplitudes,
                shape,
            )
            finite_difference[:, index] = (constraints_plus - constraints_minus) / (2.0 * step)

        self.assertEqual(constraints.shape, (3,))
        np.testing.assert_allclose(jacobian, finite_difference, rtol=2.0e-5, atol=2.0e-6)

    def test_single_q_harmonic_analytic_gradient_matches_finite_difference(self):
        from classical.classical_solver_driver import _single_q_harmonic_value_and_gradient

        model = self._one_site_antiferromagnetic_chain()
        shape = [3, 1, 1]
        vector = np.array([0.27, 0.8, -0.6, 0.4, 0.15, -0.35, 0.25], dtype=float)

        value, gradient = _single_q_harmonic_value_and_gradient(
            model,
            vector,
            shape,
        )

        finite_difference = np.zeros_like(vector)
        step = 1.0e-6
        for index in range(vector.size):
            plus = np.array(vector, copy=True)
            minus = np.array(vector, copy=True)
            plus[index] += step
            minus[index] -= step
            value_plus, _ = _single_q_harmonic_value_and_gradient(
                model,
                plus,
                shape,
            )
            value_minus, _ = _single_q_harmonic_value_and_gradient(
                model,
                minus,
                shape,
            )
            finite_difference[index] = (value_plus - value_minus) / (2.0 * step)

        self.assertTrue(np.isfinite(value))
        np.testing.assert_allclose(gradient, finite_difference, rtol=2.0e-5, atol=2.0e-6)

    def test_single_q_harmonic_constraint_jacobian_matches_finite_difference(self):
        from classical.classical_solver_driver import _single_q_harmonic_constraints_and_jacobian

        model = self._one_site_antiferromagnetic_chain()
        shape = [3, 1, 1]
        vector = np.array([0.27, 0.8, -0.6, 0.4, 0.15, -0.35, 0.25], dtype=float)

        constraints, jacobian = _single_q_harmonic_constraints_and_jacobian(
            model,
            vector,
            shape,
        )

        finite_difference = np.zeros_like(jacobian)
        step = 1.0e-6
        for index in range(vector.size):
            plus = np.array(vector, copy=True)
            minus = np.array(vector, copy=True)
            plus[index] += step
            minus[index] -= step
            constraints_plus, _ = _single_q_harmonic_constraints_and_jacobian(
                model,
                plus,
                shape,
            )
            constraints_minus, _ = _single_q_harmonic_constraints_and_jacobian(
                model,
                minus,
                shape,
            )
            finite_difference[:, index] = (constraints_plus - constraints_minus) / (2.0 * step)

        self.assertEqual(constraints.shape, (3,))
        np.testing.assert_allclose(jacobian, finite_difference, rtol=2.0e-5, atol=2.0e-6)

    def test_single_q_harmonic_lt_aligned_feasible_guess_satisfies_constraints(self):
        from classical.classical_solver_driver import (
            _single_q_harmonic_constraints_and_jacobian,
            _single_q_harmonic_lt_aligned_feasible_guess,
            _split_single_q_harmonic_vector,
        )

        model = self._one_site_antiferromagnetic_chain()
        reduced_q = np.array([0.25], dtype=float)
        cosine_coefficients = np.array([[2.0, 1.0, 0.0]], dtype=float)
        sine_coefficients = np.array([[1.0, 2.0, 0.0]], dtype=float)

        vector = _single_q_harmonic_lt_aligned_feasible_guess(
            model,
            cosine_coefficients,
            sine_coefficients,
            reduced_q,
        )
        _q_vector, feasible_cosine, feasible_sine = _split_single_q_harmonic_vector(
            model,
            vector,
            site_count=1,
        )
        constraints, _jacobian = _single_q_harmonic_constraints_and_jacobian(
            model,
            vector,
            [4, 1, 1],
        )

        self.assertAlmostEqual(float(np.linalg.norm(feasible_cosine[0])), 1.0, places=6)
        self.assertAlmostEqual(float(np.linalg.norm(feasible_sine[0])), 1.0, places=6)
        self.assertAlmostEqual(float(np.dot(feasible_cosine[0], feasible_sine[0])), 0.0, places=6)
        self.assertLess(float(np.max(np.abs(constraints))), 1.0e-8)

    def test_single_q_harmonic_lt_randomized_feasible_guess_satisfies_constraints(self):
        from classical.classical_solver_driver import (
            _single_q_harmonic_constraints_and_jacobian,
            _single_q_harmonic_lt_randomized_feasible_guess,
        )

        model = self._one_site_antiferromagnetic_chain()
        reduced_q = np.array([0.25], dtype=float)
        cosine_coefficients = np.array([[2.0, 1.0, 0.0]], dtype=float)
        sine_coefficients = np.array([[1.0, 2.0, 0.0]], dtype=float)
        rng = np.random.default_rng(0)

        vector = _single_q_harmonic_lt_randomized_feasible_guess(
            model,
            cosine_coefficients,
            sine_coefficients,
            reduced_q,
            rng=rng,
            q_bounds=[(-0.5, 0.5)],
        )
        constraints, _jacobian = _single_q_harmonic_constraints_and_jacobian(
            model,
            vector,
            [4, 1, 1],
        )

        self.assertLess(float(np.max(np.abs(constraints))), 1.0e-8)

    def test_build_variational_classical_state_prefers_explicit_variational_ordering(self):
        payload = self._one_site_antiferromagnetic_chain()
        payload["variational_result"] = {
            "state": [
                {
                    "cell": [0, 0, 0],
                    "site": 0,
                    "direction": [1.0, 0.0, 0.0],
                }
            ],
            "ordering": {
                "kind": "commensurate",
                "q_vector": [0.5, 0.0, 0.0],
                "supercell_shape": [2, 1, 1],
                "ansatz": "lt-single-q-cosine",
            },
            "supercell_shape": [2, 1, 1],
            "magnetic_supercell_shape": [2, 1, 1],
            "phase_fit": {
                "status": "not-single-q-compatible",
                "phase_sample_summary": {
                    "phase_sample_inferred_q_vector": None,
                },
            },
            "convergence": {
                "stopped_reason": "optimizer_converged",
            },
        }

        result = _build_variational_classical_state(payload)

        self.assertIsNotNone(result)
        self.assertEqual(result["ordering"]["q_vector"], [0.5, 0.0, 0.0])
        self.assertEqual(result["ordering"]["ansatz"], "lt-single-q-cosine")

    def test_build_variational_classical_state_preserves_harmonic_ordering(self):
        payload = self._one_site_antiferromagnetic_chain()
        payload["variational_result"] = {
            "state": [
                {
                    "cell": [0, 0, 0],
                    "site": 0,
                    "direction": [1.0, 0.0, 0.0],
                }
            ],
            "ordering": {
                "kind": "commensurate",
                "q_vector": [0.25, 0.0, 0.0],
                "supercell_shape": [4, 1, 1],
                "ansatz": "lt-single-q-harmonic",
            },
            "supercell_shape": [4, 1, 1],
            "magnetic_supercell_shape": [4, 1, 1],
            "phase_fit": {
                "status": "single-q-ansatz",
                "phase_sample_summary": {
                    "phase_sample_inferred_q_vector": [0.25, 0.0, 0.0],
                },
            },
            "convergence": {
                "stopped_reason": "optimizer_converged",
            },
        }

        result = _build_variational_classical_state(payload)

        self.assertIsNotNone(result)
        self.assertEqual(result["ordering"]["q_vector"], [0.25, 0.0, 0.0])
        self.assertEqual(result["ordering"]["ansatz"], "lt-single-q-harmonic")

    def test_build_variational_classical_state_handles_missing_phase_fit_q_vector(self):
        payload = self._one_site_antiferromagnetic_chain()
        payload["variational_result"] = {
            "state": [
                {
                    "cell": [0, 0, 0],
                    "site": 0,
                    "direction": [0.0, 0.0, 1.0],
                }
            ],
            "supercell_shape": [2, 2, 2],
            "magnetic_supercell_shape": [2, 2, 2],
            "phase_fit": {
                "status": "not-single-q-compatible",
                "phase_sample_summary": {
                    "phase_sample_inferred_q_vector": None,
                },
            },
            "convergence": {
                "stopped_reason": "max_linear_size_reached",
            },
        }

        result = _build_variational_classical_state(payload)

        self.assertIsNotNone(result)
        self.assertEqual(result["ordering"]["q_vector"], [0.0, 0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
