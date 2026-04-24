import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from cli import solve_pseudospin_orbital_pipeline  # noqa: E402


def _parsed_payload():
    return {
        "inferred": {"local_dimension": 2},
        "hamiltonian": {"comment": "toy-pseudospin-model"},
        "structure": {
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "positions": [[0.0, 0.0, 0.0]],
            "coordinate_mode": "fractional",
            "species": ["X"],
            "counts": [1],
        },
        "bond_blocks": [],
        "basis_order": "orbital_major_spin_minor",
        "pair_basis_order": "site_i_major_site_j_minor",
        "local_basis_labels": ["up", "down"],
        "retained_local_space": {},
    }


def _parsed_payload_with_cpn_family():
    payload = _parsed_payload()
    payload["classical_family"] = "cpn"
    return payload


def _simplified_payload():
    return {
        "simplification": {"candidates": []},
        "canonical_model": {},
        "effective_model": {},
    }


def _report_manifest():
    return {
        "reports": {
            "human_friendly": {"pdf_status": "skipped"},
            "full_coefficients": {"pdf_status": "skipped"},
        }
    }


def _final_local_ray_state():
    return {
        "state_kind": "local_rays",
        "manifold": "CP^(N-1)",
        "supercell_shape": [1, 1, 1],
        "local_rays": [
            {
                "cell": [0, 0, 0],
                "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}],
            }
        ],
        "ordering": {
            "kind": "uniform",
            "q_vector": [0.0, 0.0, 0.0],
            "supercell_shape": [1, 1, 1],
        },
    }


def _certified_final_result():
    return {
        "heuristic_seed": {
            "raw_result": {
                "method": "cpn-generalized-lt",
                "energy": -2.5,
                "starts": 1,
                "seed": 0,
                "classical_state": _final_local_ray_state(),
            }
        },
        "promotion_summary": {
            "solver_role": "final",
            "promotion_reason": "certified_commensurate_lift",
        },
        "relaxed_global_bound": {
            "status": "certified",
            "lower_bound": -2.5,
            "upper_bound": -2.5,
            "gap": 0.0,
            "statistics": {},
            "best_box": {},
        },
        "lowest_shell_certificate": {"status": "certified"},
        "commensurate_lift_certificate": {"status": "commensurate_certified"},
        "projector_exactness_certificate": {"status": "not-certified"},
        "search_summary": {},
        "next_best_action": {},
        "next_best_actions": [],
    }


class SolvePseudospinOrbitalPipelineTests(unittest.TestCase):
    def test_solve_from_parsed_payload_accepts_non_many_body_cpn_payload(self):
        parsed_payload = _parsed_payload_with_cpn_family()
        simplified_payload = _simplified_payload()
        report_manifest = _report_manifest()
        final_glt_result = {
            "method": "cpn-generalized-lt",
            "solver_role": "final",
            "promotion_reason": "exact_projector_solution",
            "energy": -2.25,
            "starts": 1,
            "seed": 0,
            "classical_state": _final_local_ray_state(),
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "out"
            docs_dir = Path(tmpdir) / "docs"
            output_dir.mkdir(parents=True, exist_ok=True)
            docs_dir.mkdir(parents=True, exist_ok=True)

            with patch.object(
                solve_pseudospin_orbital_pipeline,
                "simplify_pseudospin_orbital_payload",
                return_value=simplified_payload,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "group_pseudospin_orbital_terms",
                return_value={"distance_shells": [], "bonds": []},
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "write_pseudospin_orbital_reports",
                return_value=report_manifest,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "solve_cpn_generalized_lt_ground_state",
                return_value=final_glt_result,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "write_results_bundle",
                return_value={"status": "ok"},
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "_write_solver_stage_markdown",
                return_value=docs_dir / "phase-note.md",
            ):
                manifest = solve_pseudospin_orbital_pipeline.solve_from_parsed_payload(
                    parsed_payload,
                    output_dir=output_dir,
                    docs_dir=docs_dir,
                    compile_pdf=False,
                    classical_method="cpn-generalized-lt",
                    run_gswt=False,
                )

        self.assertEqual(manifest["status"], "ok")
        self.assertEqual(manifest["solver"]["classical_state_result"]["role"], "final")
        self.assertEqual(manifest["solver"]["classical_state_result"]["solver_family"], "retained_local_multiplet")

    def test_pseudospin_pipeline_fails_when_parsed_payload_has_no_explicit_family(self):
        parsed_payload = _parsed_payload()
        simplified_payload = _simplified_payload()
        report_manifest = _report_manifest()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "out"
            docs_dir = Path(tmpdir) / "docs"
            output_dir.mkdir(parents=True, exist_ok=True)
            docs_dir.mkdir(parents=True, exist_ok=True)

            with patch.object(
                solve_pseudospin_orbital_pipeline,
                "build_pseudospin_orbital_payload",
                return_value=parsed_payload,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "simplify_pseudospin_orbital_payload",
                return_value=simplified_payload,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "group_pseudospin_orbital_terms",
                return_value={"distance_shells": [], "bonds": []},
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "write_pseudospin_orbital_reports",
                return_value=report_manifest,
            ):
                with self.assertRaisesRegex(ValueError, "missing-classical-family"):
                    solve_pseudospin_orbital_pipeline.solve_from_files(
                        poscar_path=Path(tmpdir) / "POSCAR",
                        hr_path=Path(tmpdir) / "hr.dat",
                        output_dir=output_dir,
                        docs_dir=docs_dir,
                        compile_pdf=False,
                        classical_method="cpn-generalized-lt",
                        run_gswt=False,
                    )

    def test_pseudospin_pipeline_rejects_spin_only_family_request(self):
        parsed_payload = _parsed_payload_with_cpn_family()
        simplified_payload = _simplified_payload()
        report_manifest = _report_manifest()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "out"
            docs_dir = Path(tmpdir) / "docs"
            output_dir.mkdir(parents=True, exist_ok=True)
            docs_dir.mkdir(parents=True, exist_ok=True)

            with patch.object(
                solve_pseudospin_orbital_pipeline,
                "build_pseudospin_orbital_payload",
                return_value=parsed_payload,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "simplify_pseudospin_orbital_payload",
                return_value=simplified_payload,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "group_pseudospin_orbital_terms",
                return_value={"distance_shells": [], "bonds": []},
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "write_pseudospin_orbital_reports",
                return_value=report_manifest,
            ):
                with self.assertRaisesRegex(ValueError, "conflicting-classical-family|incompatible-classical-family"):
                    solve_pseudospin_orbital_pipeline.solve_from_files(
                        poscar_path=Path(tmpdir) / "POSCAR",
                        hr_path=Path(tmpdir) / "hr.dat",
                        output_dir=output_dir,
                        docs_dir=docs_dir,
                        compile_pdf=False,
                        classical_method="cpn-generalized-lt",
                        classical_family="spin-only",
                        run_gswt=False,
                    )

    def test_direct_glt_required_certification_uses_certifier_and_returns_final_solver_result(self):
        parsed_payload = _parsed_payload_with_cpn_family()
        simplified_payload = _simplified_payload()
        report_manifest = _report_manifest()
        classical_model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "out"
            docs_dir = Path(tmpdir) / "docs"
            output_dir.mkdir(parents=True, exist_ok=True)
            docs_dir.mkdir(parents=True, exist_ok=True)

            with patch.object(
                solve_pseudospin_orbital_pipeline,
                "build_pseudospin_orbital_payload",
                return_value=parsed_payload,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "simplify_pseudospin_orbital_payload",
                return_value=simplified_payload,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "group_pseudospin_orbital_terms",
                return_value={"distance_shells": [], "bonds": []},
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "write_pseudospin_orbital_reports",
                return_value=report_manifest,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "build_sun_gswt_classical_payload",
                return_value=classical_model,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "certify_cpn_generalized_lt",
                return_value=_certified_final_result(),
            ) as certify_mock, patch.object(
                solve_pseudospin_orbital_pipeline,
                "solve_cpn_generalized_lt_ground_state",
            ) as heuristic_mock, patch.object(
                solve_pseudospin_orbital_pipeline,
                "write_results_bundle",
                return_value={"status": "ok"},
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "_write_solver_stage_markdown",
                return_value=docs_dir / "phase-note.md",
            ):
                manifest = solve_pseudospin_orbital_pipeline.solve_from_files(
                    poscar_path=Path(tmpdir) / "POSCAR",
                    hr_path=Path(tmpdir) / "hr.dat",
                    output_dir=output_dir,
                    docs_dir=docs_dir,
                    compile_pdf=False,
                    classical_method="cpn-generalized-lt",
                    glt_certification_mode="required",
                    run_gswt=False,
                )

        certify_mock.assert_called_once()
        heuristic_mock.assert_not_called()
        self.assertEqual(manifest["solver"]["promotion_reason"], "certified_commensurate_lift")
        self.assertEqual(manifest["solver"]["classical_state_result"]["role"], "final")
        self.assertEqual(
            manifest["solver"]["classical_state_result"]["downstream_compatibility"]["gswt"]["status"],
            "ready",
        )

    def test_direct_glt_auto_certification_escalates_after_diagnostic_heuristic_result(self):
        parsed_payload = _parsed_payload_with_cpn_family()
        simplified_payload = _simplified_payload()
        report_manifest = _report_manifest()
        classical_model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
        }
        diagnostic_heuristic = {
            "method": "cpn-generalized-lt",
            "solver_role": "diagnostic-only",
            "energy": -1.75,
            "lower_bound": -1.75,
            "starts": 1,
            "seed": 0,
            "seed_candidate": {
                "kind": "commensurate-projector-seed",
                "classical_state": _final_local_ray_state(),
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "out"
            docs_dir = Path(tmpdir) / "docs"
            output_dir.mkdir(parents=True, exist_ok=True)
            docs_dir.mkdir(parents=True, exist_ok=True)

            with patch.object(
                solve_pseudospin_orbital_pipeline,
                "build_pseudospin_orbital_payload",
                return_value=parsed_payload,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "simplify_pseudospin_orbital_payload",
                return_value=simplified_payload,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "group_pseudospin_orbital_terms",
                return_value={"distance_shells": [], "bonds": []},
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "write_pseudospin_orbital_reports",
                return_value=report_manifest,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "build_sun_gswt_classical_payload",
                return_value=classical_model,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "solve_cpn_generalized_lt_ground_state",
                return_value=diagnostic_heuristic,
            ) as heuristic_mock, patch.object(
                solve_pseudospin_orbital_pipeline,
                "certify_cpn_generalized_lt",
                return_value=_certified_final_result(),
            ) as certify_mock, patch.object(
                solve_pseudospin_orbital_pipeline,
                "write_results_bundle",
                return_value={"status": "ok"},
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "_write_solver_stage_markdown",
                return_value=docs_dir / "phase-note.md",
            ):
                manifest = solve_pseudospin_orbital_pipeline.solve_from_files(
                    poscar_path=Path(tmpdir) / "POSCAR",
                    hr_path=Path(tmpdir) / "hr.dat",
                    output_dir=output_dir,
                    docs_dir=docs_dir,
                    compile_pdf=False,
                    classical_method="cpn-generalized-lt",
                    glt_certification_mode="auto",
                    run_gswt=False,
                )

        heuristic_mock.assert_called_once()
        certify_mock.assert_called_once()
        self.assertEqual(manifest["solver"]["promotion_reason"], "certified_commensurate_lift")
        self.assertEqual(manifest["solver"]["classical_state_result"]["role"], "final")

    def test_direct_glt_required_certification_builds_gswt_payload_after_final_promotion(self):
        parsed_payload = _parsed_payload_with_cpn_family()
        simplified_payload = _simplified_payload()
        report_manifest = _report_manifest()
        classical_model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
        }
        gswt_payload = {"payload_kind": "python_glswt_local_rays"}
        gswt_result = {"status": "ok", "backend": {"name": "python-glswt"}}

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "out"
            docs_dir = Path(tmpdir) / "docs"
            output_dir.mkdir(parents=True, exist_ok=True)
            docs_dir.mkdir(parents=True, exist_ok=True)

            with patch.object(
                solve_pseudospin_orbital_pipeline,
                "build_pseudospin_orbital_payload",
                return_value=parsed_payload,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "simplify_pseudospin_orbital_payload",
                return_value=simplified_payload,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "group_pseudospin_orbital_terms",
                return_value={"distance_shells": [], "bonds": []},
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "write_pseudospin_orbital_reports",
                return_value=report_manifest,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "build_sun_gswt_classical_payload",
                return_value=classical_model,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "certify_cpn_generalized_lt",
                return_value=_certified_final_result(),
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "_build_selected_gswt_payload",
                return_value=gswt_payload,
            ) as build_gswt_mock, patch.object(
                solve_pseudospin_orbital_pipeline,
                "_run_selected_gswt",
                return_value=gswt_result,
            ) as run_gswt_mock, patch.object(
                solve_pseudospin_orbital_pipeline,
                "write_results_bundle",
                return_value={"status": "ok"},
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "_write_solver_stage_markdown",
                return_value=docs_dir / "phase-note.md",
            ):
                manifest = solve_pseudospin_orbital_pipeline.solve_from_files(
                    poscar_path=Path(tmpdir) / "POSCAR",
                    hr_path=Path(tmpdir) / "hr.dat",
                    output_dir=output_dir,
                    docs_dir=docs_dir,
                    compile_pdf=False,
                    classical_method="cpn-generalized-lt",
                    glt_certification_mode="required",
                    run_gswt=True,
                    gswt_backend="python",
                )

        build_gswt_mock.assert_called_once()
        run_gswt_mock.assert_called_once_with(gswt_payload, gswt_backend="python")
        self.assertEqual(manifest["solver"]["gswt"]["status"], "ok")

    def test_pseudospin_auto_stops_at_promoted_glt_result(self):
        parsed_payload = _parsed_payload_with_cpn_family()
        simplified_payload = _simplified_payload()
        report_manifest = _report_manifest()
        classical_model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
        }
        final_glt_result = {
            "method": "cpn-generalized-lt",
            "solver_role": "final",
            "promotion_reason": "exact_projector_solution",
            "energy": -2.25,
            "starts": 1,
            "seed": 0,
            "classical_state": _final_local_ray_state(),
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "out"
            docs_dir = Path(tmpdir) / "docs"
            output_dir.mkdir(parents=True, exist_ok=True)
            docs_dir.mkdir(parents=True, exist_ok=True)

            with patch.object(
                solve_pseudospin_orbital_pipeline,
                "build_pseudospin_orbital_payload",
                return_value=parsed_payload,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "simplify_pseudospin_orbital_payload",
                return_value=simplified_payload,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "group_pseudospin_orbital_terms",
                return_value={"distance_shells": [], "bonds": []},
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "write_pseudospin_orbital_reports",
                return_value=report_manifest,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "build_sun_gswt_classical_payload",
                return_value=classical_model,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "solve_cpn_generalized_lt_ground_state",
                return_value=final_glt_result,
            ) as glt_mock, patch.object(
                solve_pseudospin_orbital_pipeline,
                "solve_cpn_local_ray_ground_state",
            ) as local_ray_mock, patch.object(
                solve_pseudospin_orbital_pipeline,
                "write_results_bundle",
                return_value={"status": "ok"},
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "_write_solver_stage_markdown",
                return_value=docs_dir / "phase-note.md",
            ):
                manifest = solve_pseudospin_orbital_pipeline.solve_from_files(
                    poscar_path=Path(tmpdir) / "POSCAR",
                    hr_path=Path(tmpdir) / "hr.dat",
                    output_dir=output_dir,
                    docs_dir=docs_dir,
                    compile_pdf=False,
                    classical_method="auto",
                    run_gswt=False,
                )

        glt_mock.assert_called_once()
        local_ray_mock.assert_not_called()
        self.assertEqual(manifest["solver"]["promotion_reason"], "exact_projector_solution")
        self.assertEqual(manifest["solver"]["classical_state_result"]["method"], "pseudospin-cpn-generalized-lt")

    def test_pseudospin_auto_falls_back_to_local_ray_when_glt_stays_diagnostic(self):
        parsed_payload = _parsed_payload_with_cpn_family()
        simplified_payload = _simplified_payload()
        report_manifest = _report_manifest()
        classical_model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
        }
        diagnostic_glt_result = {
            "method": "cpn-generalized-lt",
            "solver_role": "diagnostic-only",
            "energy": -1.25,
            "lower_bound": -1.25,
            "starts": 1,
            "seed": 0,
            "seed_candidate": {
                "kind": "commensurate-projector-seed",
                "classical_state": _final_local_ray_state(),
            },
        }
        local_ray_result = {
            "method": "cpn-local-ray-minimize",
            "energy": -2.75,
            "starts": 16,
            "seed": 0,
            "supercell_shape": [1, 1, 1],
            "local_rays": list(_final_local_ray_state()["local_rays"]),
            "classical_state": _final_local_ray_state(),
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "out"
            docs_dir = Path(tmpdir) / "docs"
            output_dir.mkdir(parents=True, exist_ok=True)
            docs_dir.mkdir(parents=True, exist_ok=True)

            with patch.object(
                solve_pseudospin_orbital_pipeline,
                "build_pseudospin_orbital_payload",
                return_value=parsed_payload,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "simplify_pseudospin_orbital_payload",
                return_value=simplified_payload,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "group_pseudospin_orbital_terms",
                return_value={"distance_shells": [], "bonds": []},
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "write_pseudospin_orbital_reports",
                return_value=report_manifest,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "build_sun_gswt_classical_payload",
                return_value=classical_model,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "solve_cpn_generalized_lt_ground_state",
                return_value=diagnostic_glt_result,
            ) as glt_mock, patch.object(
                solve_pseudospin_orbital_pipeline,
                "_extract_cpn_glt_preconditioner",
                return_value=(
                    {"shape": [1, 1, 1], "local_rays": list(_final_local_ray_state()["local_rays"])},
                    {"method": "cpn-generalized-lt", "used": True, "source": "seed_candidate"},
                ),
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "solve_cpn_local_ray_ground_state",
                return_value=local_ray_result,
            ) as local_ray_mock, patch.object(
                solve_pseudospin_orbital_pipeline,
                "write_results_bundle",
                return_value={"status": "ok"},
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "_write_solver_stage_markdown",
                return_value=docs_dir / "phase-note.md",
            ):
                manifest = solve_pseudospin_orbital_pipeline.solve_from_files(
                    poscar_path=Path(tmpdir) / "POSCAR",
                    hr_path=Path(tmpdir) / "hr.dat",
                    output_dir=output_dir,
                    docs_dir=docs_dir,
                    compile_pdf=False,
                    classical_method="auto",
                    run_gswt=False,
                )

        glt_mock.assert_called_once()
        local_ray_mock.assert_called_once()
        self.assertEqual(manifest["solver"]["method"], "cpn-local-ray-minimize")
        self.assertEqual(
            manifest["solver"]["classical_state_result"]["method"],
            "pseudospin-cpn-local-ray-minimize",
        )

    def test_solver_phase_summary_describes_direct_glt_as_conditionally_final(self):
        summary = solve_pseudospin_orbital_pipeline._solver_phase_summary(
            {
                **_parsed_payload(),
                "inferred": {"local_dimension": 4, "multiplet_dimension": 4},
            },
            _simplified_payload(),
            {"bonds": [], "distance_shells": []},
            {"bond_count": 0, "classical_manifold": "CP^(N-1)", "local_dimension": 4},
            {
                "method": "cpn-generalized-lt",
                "solver_role": "final",
                "promotion_reason": "exact_projector_solution",
                "energy": -2.0,
                "starts": 1,
                "seed": 0,
                "gswt": {"status": "ok", "payload_kind": "python_glswt_local_rays", "backend": {"name": "python"}},
                "projector_diagnostics": {"grid_shape": [3, 3, 1]},
                "stationarity": {"residual_definition": "projected-gradient"},
            },
            _report_manifest(),
            "cpn-generalized-lt",
        )

        self.assertIn("conditionally final", summary)
        self.assertNotIn("the current branch is diagnostic-only", summary)
        self.assertNotIn("does not auto-run GSWT or thermodynamics", summary)

    def test_solver_phase_summary_keeps_diagnostic_glt_limitations_explicit(self):
        summary = solve_pseudospin_orbital_pipeline._solver_phase_summary(
            {
                **_parsed_payload(),
                "inferred": {"local_dimension": 4, "multiplet_dimension": 4},
            },
            _simplified_payload(),
            {"bonds": [], "distance_shells": []},
            {"bond_count": 0, "classical_manifold": "CP^(N-1)", "local_dimension": 4},
            {
                "method": "cpn-generalized-lt",
                "solver_role": "diagnostic-only",
                "energy": -1.5,
                "starts": 1,
                "seed": 0,
                "projector_diagnostics": {"grid_shape": [3, 3, 1]},
                "stationarity": {"residual_definition": "projected-gradient"},
            },
            _report_manifest(),
            "cpn-generalized-lt",
        )

        self.assertIn("conditionally final", summary)
        self.assertIn("diagnostic when promotion checks fail", summary)

    def test_cli_main_preserves_none_local_space_mode_when_flag_is_omitted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "out"
            docs_dir = Path(tmpdir) / "docs"
            argv = [
                "solve_pseudospin_orbital_pipeline.py",
                "--poscar",
                str(Path(tmpdir) / "POSCAR"),
                "--hr",
                str(Path(tmpdir) / "hr.dat"),
                "--output-dir",
                str(output_dir),
                "--docs-dir",
                str(docs_dir),
                "--no-pdf",
            ]

            with patch.object(sys, "argv", argv), patch.object(
                solve_pseudospin_orbital_pipeline,
                "solve_from_files",
                return_value={"status": "ok"},
            ) as solve_mock:
                exit_code = solve_pseudospin_orbital_pipeline.main()

        self.assertEqual(exit_code, 0)
        self.assertIsNone(solve_mock.call_args.kwargs["local_space_mode"])


if __name__ == "__main__":
    unittest.main()
