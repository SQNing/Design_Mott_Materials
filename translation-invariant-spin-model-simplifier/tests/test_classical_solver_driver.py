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

    def test_lswt_builder_consumes_supercell_variational_output(self):
        result = run_classical_solver(
            self._one_site_antiferromagnetic_chain(),
            starts=4,
            seed=3,
        )

        lswt_payload = build_lswt_payload(result)

        self.assertEqual(lswt_payload["status"], "ok")
        payload = lswt_payload["payload"]
        self.assertEqual(payload["supercell_shape"], [2, 1, 1])
        self.assertEqual(len(payload["supercell_reference_frames"]), 2)
        first = payload["supercell_reference_frames"][0]["direction"]
        second = payload["supercell_reference_frames"][1]["direction"]
        for first_value, second_value in zip(first, second):
            self.assertAlmostEqual(first_value, -second_value, places=6)

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

        self.assertEqual(result["variational_result"]["ansatz_stationarity"]["optimizer_method"], "trust-constr")
        self.assertEqual(
            result["variational_result"]["ansatz_stationarity"]["optimization_mode"],
            "direct-q-and-cartesian-harmonic-coefficients",
        )
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
        self.assertIn("optimized_cosine_coefficients", result["variational_result"]["ansatz_stationarity"])
        self.assertIn("optimized_sine_coefficients", result["variational_result"]["ansatz_stationarity"])

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
