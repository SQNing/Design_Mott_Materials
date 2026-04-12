import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from output.render_report import render_text


class RenderReportTests(unittest.TestCase):
    def test_render_text_includes_gswt_classical_reference_and_ordering_summary(self):
        payload = {
            "normalized_model": {"local_hilbert": {"dimension": 2}},
            "simplification": {"recommended": 0, "candidates": [{"name": "faithful-readable"}]},
            "canonical_model": {"one_body": [], "two_body": [], "three_body": [], "four_body": [], "higher_body": []},
            "effective_model": {"main": [], "low_weight": [], "residual": []},
            "fidelity": {
                "reconstruction_error": 0.0,
                "main_fraction": 1.0,
                "low_weight_fraction": 0.0,
                "residual_fraction": 0.0,
                "risk_notes": [],
            },
            "projection": {"status": "not-needed"},
            "classical": {"chosen_method": "sunny-cpn-minimize"},
            "gswt": {
                "status": "ok",
                "backend": {"name": "Sunny.jl", "mode": "SUN"},
                "payload_kind": "sun_gswt_prototype",
                "classical_reference": {
                    "schema_version": 1,
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "frame_construction": "first-column-is-reference-ray",
                },
                "ordering": {
                    "ansatz": "single-q-unitary-ray",
                    "q_vector": [0.5, 0.0, 0.0],
                    "supercell_shape": [2, 1, 1],
                    "compatibility_with_supercell": {"kind": "commensurate"},
                },
            },
            "lswt": {"status": "skipped", "error": {"code": "missing", "message": "unavailable"}},
        }

        text = render_text(payload)

        self.assertIn("GSWT backend: Sunny.jl", text)
        self.assertIn("GSWT status: ok", text)
        self.assertIn("GSWT reference state: local_rays", text)
        self.assertIn("manifold=CP^(N-1)", text)
        self.assertIn("frame=first-column-is-reference-ray", text)
        self.assertIn("GSWT ordering: ansatz=single-q-unitary-ray", text)
        self.assertIn("q_vector=[0.5, 0.0, 0.0]", text)
        self.assertIn("compatibility=commensurate", text)

    def test_render_text_includes_gswt_instability_and_dispersion_diagnostics(self):
        payload = {
            "normalized_model": {"local_hilbert": {"dimension": 2}},
            "simplification": {"recommended": 0, "candidates": [{"name": "faithful-readable"}]},
            "canonical_model": {"one_body": [], "two_body": [], "three_body": [], "four_body": [], "higher_body": []},
            "effective_model": {"main": [], "low_weight": [], "residual": []},
            "fidelity": {
                "reconstruction_error": 0.0,
                "main_fraction": 1.0,
                "low_weight_fraction": 0.0,
                "residual_fraction": 0.0,
                "risk_notes": [],
            },
            "projection": {"status": "not-needed"},
            "classical": {"chosen_method": "sunny-cpn-minimize"},
            "gswt": {
                "status": "error",
                "backend": {"name": "Sunny.jl", "mode": "SUN"},
                "payload_kind": "sun_gswt_prototype",
                "diagnostics": {
                    "instability": {
                        "kind": "wavevector-instability",
                        "q_vector": [0.25, -0.125, 0.0],
                        "nearest_q_path_index": 7,
                        "nearest_q_path_kind": "path-segment-sample",
                        "nearest_q_path_distance": 0.031,
                        "nearest_path_segment_label": "G-X",
                        "nearest_high_symmetry_label": "X",
                    },
                    "dispersion": {
                        "omega_min": -0.1,
                        "omega_min_q_vector": [0.5, 0.0, 0.0],
                        "soft_mode_count": 1,
                    },
                },
                "error": {"code": "backend-execution-failed", "message": "Instability at wavevector q = [0.25, -0.125, 0.0]"},
            },
            "lswt": {"status": "skipped", "error": {"code": "missing", "message": "unavailable"}},
        }

        text = render_text(payload)

        self.assertIn("GSWT instability diagnostics:", text)
        self.assertIn("q_vector=[0.25, -0.125, 0.0]", text)
        self.assertIn("nearest_q_path_kind=path-segment-sample", text)
        self.assertIn("nearest_q_path_distance=0.031", text)
        self.assertIn("nearest_path_segment_label=G-X", text)
        self.assertIn("nearest_high_symmetry_label=X", text)
        self.assertIn("GSWT interpretation:", text)
        self.assertIn("harmonic instability near path segment G-X", text)
        self.assertIn("GSWT dispersion diagnostics:", text)
        self.assertIn("omega_min=-0.1", text)
        self.assertIn("soft_mode_count=1", text)

    def test_render_text_includes_thermodynamics_configuration_summary(self):
        payload = {
            "normalized_model": {"local_hilbert": {"dimension": 4}},
            "simplification": {"recommended": 0, "candidates": [{"name": "faithful-readable"}]},
            "canonical_model": {"one_body": [], "two_body": [], "three_body": [], "four_body": [], "higher_body": []},
            "effective_model": {"main": [], "low_weight": [], "residual": []},
            "fidelity": {
                "reconstruction_error": 0.0,
                "main_fraction": 1.0,
                "low_weight_fraction": 0.0,
                "residual_fraction": 0.0,
                "risk_notes": [],
            },
            "projection": {"status": "not-needed"},
            "classical": {"chosen_method": "sunny-cpn-minimize"},
            "thermodynamics": {
                "profile": "smoke",
                "backend_method": "sunny-local-sampler",
                "temperatures": [0.2, 0.4],
                "sweeps": 10,
                "burn_in": 5,
                "measurement_interval": 1,
                "proposal": "delta",
                "proposal_scale": 0.1,
            },
            "thermodynamics_result": {
                "method": "sunny-local-sampler",
                "backend": {"name": "Sunny.jl", "mode": "SUN", "sampler": "sunny-local-sampler"},
                "configuration": {
                    "profile": "smoke",
                    "backend_method": "sunny-local-sampler",
                    "temperatures": [0.2, 0.4],
                    "sweeps": 10,
                    "burn_in": 5,
                    "measurement_interval": 1,
                    "proposal": "delta",
                    "proposal_scale": 0.1,
                },
                "sampling": {"seed": 7},
                "grid": [{"temperature": 0.2, "energy": -0.1}],
            },
            "lswt": {"status": "skipped", "error": {"code": "missing", "message": "unavailable"}},
        }

        text = render_text(payload)

        self.assertIn("Thermodynamics configuration:", text)
        self.assertIn("profile=smoke", text)
        self.assertIn("backend_method=sunny-local-sampler", text)
        self.assertIn("temperatures=[0.2, 0.4]", text)
        self.assertIn("sweeps=10", text)
        self.assertIn("burn_in=5", text)
        self.assertIn("proposal_scale=0.1", text)

    def test_render_text_includes_python_gswt_stationarity_and_bogoliubov_diagnostics(self):
        payload = {
            "normalized_model": {"local_hilbert": {"dimension": 4}},
            "simplification": {"recommended": 0, "candidates": [{"name": "faithful-readable"}]},
            "canonical_model": {"one_body": [], "two_body": [], "three_body": [], "four_body": [], "higher_body": []},
            "effective_model": {"main": [], "low_weight": [], "residual": []},
            "fidelity": {
                "reconstruction_error": 0.0,
                "main_fraction": 1.0,
                "low_weight_fraction": 0.0,
                "residual_fraction": 0.0,
                "risk_notes": [],
            },
            "projection": {"status": "many_body_hr-pseudospin_orbital"},
            "classical": {"chosen_method": "sunny-cpn-minimize"},
            "gswt": {
                "status": "ok",
                "backend": {"name": "python-glswt", "implementation": "local-frame-quadratic-expansion"},
                "payload_kind": "python_glswt_local_rays",
                "classical_reference": {
                    "schema_version": 1,
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "frame_construction": "first-column-is-reference-ray",
                },
                "diagnostics": {
                    "dispersion": {
                        "omega_min": 0.0,
                        "omega_min_q_vector": [0.0, 0.0, 0.0],
                        "soft_mode_count": 0,
                    },
                    "stationarity": {
                        "is_stationary": True,
                        "linear_term_max_norm": 2.5e-10,
                        "linear_term_mean_norm": 1.0e-10,
                    },
                    "bogoliubov": {
                        "mode_count": 6,
                        "max_A_antihermitian_norm": 0.0,
                        "max_B_asymmetry_norm": 0.0,
                        "max_complex_eigenvalue_count": 0,
                    },
                },
            },
            "lswt": {"status": "skipped", "error": {"code": "missing", "message": "unavailable"}},
        }

        text = render_text(payload)

        self.assertIn("GSWT backend: python-glswt", text)
        self.assertIn("GSWT stationarity diagnostics:", text)
        self.assertIn("is_stationary=True", text)
        self.assertIn("linear_term_max_norm=2.5e-10", text)
        self.assertIn("GSWT Bogoliubov diagnostics:", text)
        self.assertIn("mode_count=6", text)
        self.assertIn("max_complex_eigenvalue_count=0", text)

    def test_render_text_includes_single_q_z_harmonic_diagnostics(self):
        payload = {
            "normalized_model": {"local_hilbert": {"dimension": 4}},
            "simplification": {"recommended": 0, "candidates": [{"name": "faithful-readable"}]},
            "canonical_model": {"one_body": [], "two_body": [], "three_body": [], "four_body": [], "higher_body": []},
            "effective_model": {"main": [], "low_weight": [], "residual": []},
            "fidelity": {
                "reconstruction_error": 0.0,
                "main_fraction": 1.0,
                "low_weight_fraction": 0.0,
                "residual_fraction": 0.0,
                "risk_notes": [],
            },
            "projection": {"status": "many_body_hr-pseudospin_orbital"},
            "classical": {"chosen_method": "sun-gswt-single-q"},
            "gswt": {
                "status": "ok",
                "backend": {"name": "python-glswt", "implementation": "single-q-z-harmonic-sideband"},
                "payload_kind": "python_glswt_single_q_z_harmonic",
                "z_harmonic_reference_mode": "refined-retained-local",
                "reference_dispersions": {
                    "input": [
                        {"q": [0.0, 0.0, 0.0], "bands": [0.125, 0.4], "omega": 0.125},
                        {"q": [0.13, 0.0, 0.0], "bands": [0.25, 0.5], "omega": 0.25},
                    ],
                    "refined-retained-local": [
                        {"q": [0.0, 0.0, 0.0], "bands": [0.0625, 0.4], "omega": 0.0625},
                        {"q": [0.13, 0.0, 0.0], "bands": [0.1875, 0.5], "omega": 0.1875},
                    ],
                },
                "ordering": {"ansatz": "single-q-unitary-ray", "q_vector": [0.2, 0.0, 0.0]},
                "diagnostics": {
                    "reference_selection": {
                        "requested_mode": "refined-retained-local",
                        "resolved_mode": "refined-retained-local",
                        "dispersion_recomputed": True,
                        "input_retained_linear_term_max_norm": 2.0e-4,
                        "selected_retained_linear_term_max_norm": 5.0e-5,
                    },
                    "restricted_ansatz_stationarity": {
                        "best_objective": -0.75,
                        "optimizer_success": True,
                        "optimizer_method": "L-BFGS-B",
                        "optimization_mode": "direct-joint",
                    },
                    "harmonic": {
                        "phase_grid_size": 32,
                        "max_reconstruction_error": 1.0e-9,
                        "max_norm_error": 2.0e-9,
                    },
                    "stationarity": {
                        "scope": "full-local-tangent",
                        "sampling_kind": "phase_grid",
                        "phase_grid_size": 32,
                        "is_stationary": False,
                        "linear_term_max_norm": 1.2e-4,
                        "linear_term_mean_norm": 3.0e-5,
                    },
                    "truncated_z_harmonic_stationarity": {
                        "scope": "truncated-z-harmonic-manifold",
                        "projection_kind": "phase-fourier-retained-harmonics",
                        "harmonic_cutoff": 1,
                        "phase_grid_size": 32,
                        "full_dft_harmonic_count": 32,
                        "discarded_harmonic_count": 29,
                        "is_stationary": True,
                        "linear_term_max_norm": 2.0e-8,
                        "linear_term_mean_norm": 1.0e-8,
                        "discarded_linear_term_max_norm": 3.0e-5,
                    },
                    "truncated_z_harmonic_local_refinement": {
                        "status": "improved",
                        "selected_step_size": 0.25,
                        "iteration_count": 3,
                        "step_history": [0.5, 0.25, -0.1],
                        "initial_retained_linear_term_max_norm": 2.0e-4,
                        "refined_retained_linear_term_max_norm": 5.0e-5,
                    },
                    "bogoliubov": {
                        "mode_count": 5,
                        "sideband_count": 5,
                        "sideband_cutoff": 2,
                        "max_A_antihermitian_norm": 0.0,
                        "max_B_asymmetry_norm": 0.0,
                        "max_complex_eigenvalue_count": 0,
                    },
                },
                "z_harmonic_cutoff": 1,
                "phase_grid_size": 32,
                "sideband_cutoff": 2,
            },
            "lswt": {"status": "skipped", "error": {"code": "missing", "message": "unavailable"}},
        }

        text = render_text(payload)

        self.assertIn("GSWT single-q z-harmonic diagnostics:", text)
        self.assertIn("GSWT reference selection:", text)
        self.assertIn("requested_mode=refined-retained-local", text)
        self.assertIn("resolved_mode=refined-retained-local", text)
        self.assertIn("GSWT reference dispersion comparison:", text)
        self.assertIn("input_omega_min=0.125", text)
        self.assertIn("selected_omega_min=0.0625", text)
        self.assertIn("delta_omega_min=-0.0625", text)
        self.assertIn("GSWT restricted-ansatz stationarity diagnostics:", text)
        self.assertIn("optimization_mode=direct-joint", text)
        self.assertIn("z_harmonic_cutoff=1", text)
        self.assertIn("phase_grid_size=32", text)
        self.assertIn("sideband_cutoff=2", text)
        self.assertIn("GSWT truncated z-harmonic stationarity diagnostics:", text)
        self.assertIn("scope=truncated-z-harmonic-manifold", text)
        self.assertIn("discarded_harmonic_count=29", text)
        self.assertIn("discarded_linear_term_max_norm=3e-05", text)
        self.assertIn("GSWT truncated z-harmonic local refinement:", text)
        self.assertIn("selected_step_size=0.25", text)
        self.assertIn("iteration_count=3", text)
        self.assertIn("scope=full-local-tangent", text)
        self.assertIn("sampling_kind=phase_grid", text)

    def test_render_text_includes_single_q_convergence_section(self):
        payload = {
            "normalized_model": {"local_hilbert": {"dimension": 4}},
            "simplification": {"recommended": 0, "candidates": [{"name": "faithful-readable"}]},
            "canonical_model": {"one_body": [], "two_body": [], "three_body": [], "four_body": [], "higher_body": []},
            "effective_model": {"main": [], "low_weight": [], "residual": []},
            "fidelity": {
                "reconstruction_error": 0.0,
                "main_fraction": 1.0,
                "low_weight_fraction": 0.0,
                "residual_fraction": 0.0,
                "risk_notes": [],
            },
            "projection": {"status": "many_body_hr-pseudospin_orbital"},
            "classical": {"chosen_method": "sun-gswt-single-q"},
            "gswt": {
                "status": "ok",
                "backend": {"name": "python-glswt", "implementation": "single-q-z-harmonic-sideband"},
                "payload_kind": "python_glswt_single_q_z_harmonic",
            },
            "single_q_convergence": {
                "status": "ok",
                "analysis_kind": "single_q_z_harmonic_convergence",
                "reference_parameters": {
                    "phase_grid_size": 32,
                    "z_harmonic_cutoff": 1,
                    "sideband_cutoff": 2,
                    "z_harmonic_reference_mode": "input",
                },
                "reference_metrics": {
                    "omega_min": 0.05,
                    "omega_min_q_vector": [0.13, 0.0, 0.0],
                    "retained_linear_term_max_norm": 1.0e-7,
                    "discarded_linear_term_max_norm": 2.0e-5,
                    "full_tangent_linear_term_max_norm": 1.0e-4,
                },
                "phase_grid_scan": [
                    {
                        "phase_grid_size": 16,
                        "omega_min": 0.07,
                        "omega_min_delta_vs_reference": 0.02,
                        "max_band_delta_vs_reference": 0.03,
                        "retained_linear_term_max_norm": 3.0e-7,
                        "full_tangent_linear_term_max_norm": 2.0e-4,
                    }
                ],
                "z_harmonic_cutoff_scan": [
                    {
                        "z_harmonic_cutoff": 0,
                        "omega_min": 0.09,
                        "omega_min_delta_vs_reference": 0.04,
                        "max_band_delta_vs_reference": 0.05,
                        "retained_linear_term_max_norm": 5.0e-6,
                        "full_tangent_linear_term_max_norm": 3.0e-4,
                    }
                ],
                "sideband_cutoff_scan": [
                    {
                        "sideband_cutoff": 1,
                        "omega_min": 0.06,
                        "omega_min_delta_vs_reference": 0.01,
                        "max_band_delta_vs_reference": 0.015,
                        "retained_linear_term_max_norm": 2.0e-7,
                        "full_tangent_linear_term_max_norm": 1.1e-4,
                    }
                ],
            },
            "lswt": {"status": "skipped", "error": {"code": "missing", "message": "unavailable"}},
        }

        text = render_text(payload)

        self.assertIn("Single-Q Z-Harmonic Convergence:", text)
        self.assertIn("reference_phase_grid_size=32", text)
        self.assertIn("reference_omega_min=0.05", text)
        self.assertIn("phase_grid_size=16", text)
        self.assertIn("max_band_delta_vs_reference=0.03", text)
        self.assertIn("z_harmonic_cutoff=0", text)
        self.assertIn("sideband_cutoff=1", text)

    def test_render_text_includes_lswt_failure_interpretation_and_next_steps(self):
        payload = {
            "normalized_model": {"local_hilbert": {"dimension": 2}},
            "simplification": {"recommended": 0, "candidates": [{"name": "faithful-readable"}]},
            "canonical_model": {"one_body": [], "two_body": [], "three_body": [], "four_body": [], "higher_body": []},
            "effective_model": {"main": [], "low_weight": [], "residual": []},
            "fidelity": {
                "reconstruction_error": 0.0,
                "main_fraction": 1.0,
                "low_weight_fraction": 0.0,
                "residual_fraction": 0.0,
                "risk_notes": [],
            },
            "projection": {"status": "not-needed"},
            "classical": {"chosen_method": "luttinger-tisza"},
            "lt_result": {
                "q": [0.5, 0.0, 0.0],
                "lowest_eigenvalue": -2.0,
                "matrix_size": 1,
                "constraint_recovery": {"strong_constraint_residual": 0.0},
            },
            "lswt": {
                "status": "error",
                "backend": {"name": "Sunny.jl"},
                "path": {"labels": ["G", "X"]},
                "error": {
                    "code": "backend-execution-failed",
                    "message": "Instability at wavevector q = [0.0625, 0.0, 0.0]",
                },
            },
        }

        text = render_text(payload)

        self.assertIn("LSWT interpretation:", text)
        self.assertIn("harmonic expansion around the supplied classical reference is unstable", text)
        self.assertIn("LSWT likely cause:", text)
        self.assertIn("classical reference state is not a stable expansion point", text)
        self.assertIn("LSWT suggested next steps:", text)
        self.assertIn("check whether the classical reference state should be revised", text)
        self.assertIn("scan nearby ordering wavevectors", text)

    def test_render_text_includes_symmetry_interpretation_for_weak_anisotropy(self):
        payload = {
            "normalized_model": {"local_hilbert": {"dimension": 2}},
            "simplification": {"recommended": 0, "candidates": [{"name": "faithful-readable"}]},
            "canonical_model": {
                "one_body": [],
                "two_body": [
                    {
                        "canonical_label": "Sx@0 Sx@1",
                        "coefficient": 1.0,
                        "absolute_weight": 1.0,
                        "relative_weight": 1.0,
                        "support": [0, 1],
                        "body_order": 2,
                        "symmetry_annotations": [],
                    },
                    {
                        "canonical_label": "Sy@0 Sy@1",
                        "coefficient": 1.0,
                        "absolute_weight": 1.0,
                        "relative_weight": 1.0,
                        "support": [0, 1],
                        "body_order": 2,
                        "symmetry_annotations": [],
                    },
                    {
                        "canonical_label": "Sz@0 Sz@1",
                        "coefficient": 1.0,
                        "absolute_weight": 1.0,
                        "relative_weight": 1.0,
                        "support": [0, 1],
                        "body_order": 2,
                        "symmetry_annotations": [],
                    },
                    {
                        "canonical_label": "Sx@0 Sz@1",
                        "coefficient": 0.05,
                        "absolute_weight": 0.05,
                        "relative_weight": 0.05,
                        "support": [0, 1],
                        "body_order": 2,
                        "symmetry_annotations": [],
                    },
                ],
                "three_body": [],
                "four_body": [],
                "higher_body": [],
            },
            "effective_model": {
                "main": [{"type": "isotropic_exchange", "coefficient": 1.0}],
                "low_weight": [{"canonical_label": "Sx@0 Sz@1", "coefficient": 0.05}],
                "residual": [],
            },
            "fidelity": {
                "reconstruction_error": 0.0,
                "main_fraction": 0.95,
                "low_weight_fraction": 0.05,
                "residual_fraction": 0.0,
                "risk_notes": [],
            },
            "projection": {"status": "not-needed"},
            "classical": {"chosen_method": "luttinger-tisza"},
            "detected_symmetries": ["translation", "hermiticity"],
            "lswt": {"status": "skipped", "error": {"code": "missing", "message": "unavailable"}},
        }

        text = render_text(payload)

        self.assertIn("Symmetry interpretation:", text)
        self.assertIn("detected=translation, hermiticity", text)
        self.assertIn("ruled_out=su2_spin, u1_spin", text)
        self.assertIn("cross-axis coupling Sx@0 Sz@1 remains in the model", text)


if __name__ == "__main__":
    unittest.main()
