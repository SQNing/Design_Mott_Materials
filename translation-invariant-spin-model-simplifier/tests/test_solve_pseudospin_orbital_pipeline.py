import sys
import tempfile
import unittest
import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "cpn_workflow"

from cli import solve_pseudospin_orbital_pipeline  # noqa: E402
from cli import render_pseudospin_orbital_report  # noqa: E402


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


def _load_cpn_workflow_fixture(name):
    path = FIXTURE_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _skill_text():
    return (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")


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
    def test_solve_from_files_passes_local_level_mapping_to_payload_builder(self):
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
            mapping_path = Path(tmpdir) / "level_mapping.json"
            output_dir.mkdir(parents=True, exist_ok=True)
            docs_dir.mkdir(parents=True, exist_ok=True)
            mapping_path.write_text('{"schema_version": 1, "site_level_mapping": []}', encoding="utf-8")

            with patch.object(
                solve_pseudospin_orbital_pipeline,
                "build_pseudospin_orbital_payload",
                return_value=parsed_payload,
            ) as build_payload_mock, patch.object(
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
                solve_pseudospin_orbital_pipeline.solve_from_files(
                    poscar_path=Path(tmpdir) / "POSCAR",
                    hr_path=Path(tmpdir) / "hr.dat",
                    output_dir=output_dir,
                    docs_dir=docs_dir,
                    compile_pdf=False,
                    classical_method="cpn-generalized-lt",
                    local_level_to_site_mapping_path=mapping_path,
                    run_gswt=False,
                )

        self.assertEqual(
            build_payload_mock.call_args.kwargs["local_level_to_site_mapping_path"],
            mapping_path,
        )

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
                result_payload = json.loads(Path(manifest["artifacts"]["result_payload"]).read_text(encoding="utf-8"))

        self.assertEqual(manifest["status"], "ok")
        self.assertEqual(manifest["solver"]["classical_state_result"]["role"], "final")
        self.assertEqual(manifest["solver"]["classical_state_result"]["solver_family"], "retained_local_multiplet")
        self.assertEqual(result_payload["projection"]["status"], "cpn_pair_model")

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

    def test_sun_gswt_cpn_pipeline_builds_gswt_from_accepted_refined_branch_and_exports_contract(self):
        parsed_payload = _parsed_payload_with_cpn_family()
        simplified_payload = _simplified_payload()
        report_manifest = _report_manifest()
        classical_model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
        }
        initial_solver_result = {
            "method": "sun-gswt-cpn",
            "energy": -2.0,
            "starts": 2,
            "seed": 0,
            "supercell_shape": [4, 4, 4],
            "local_rays": list(_final_local_ray_state()["local_rays"]),
            "classical_state": _final_local_ray_state(),
            "projector_diagnostics": {
                "dominant_ordering_q": [0.25, 0.75, 0.25],
                "top_components": [{"q": [0.25, 0.75, 0.25], "weight": 0.14}],
            },
            "stationarity": {"max_residual_norm": 1e-8},
        }
        reshaped_model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "positions": [[0.0, 0.0, 0.0]] * 4,
        }
        refined_state = {
            "state_kind": "local_rays",
            "manifold": "CP^(N-1)",
            "supercell_shape": [4, 4, 1],
            "local_rays": [
                {
                    "cell": [0, 0, 0],
                    "site": 0,
                    "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}],
                }
            ],
            "ordering": {
                "kind": "commensurate-supercell",
                "q_vector": [0.75, 0.25, 0.75],
                "supercell_shape": [4, 4, 1],
            },
        }
        magnetic_refinement = {
            "accepted": True,
            "trigger_q": [0.75, 0.25, 0.75],
            "candidate_matrix": [[0, 3, -1], [1, -3, 0], [0, 4, 0]],
            "energy_before_per_site": -2.0,
            "energy_after_python_per_site": -2.2,
            "energy_gain_per_site": 0.2,
            "candidates": [
                {
                    "accepted": True,
                    "trigger_q": [0.75, 0.25, 0.75],
                    "candidate_matrix": [[0, 3, -1], [1, -3, 0], [0, 4, 0]],
                }
            ],
        }
        refinement_result = {
            "status": "candidate",
            "candidate": {
                "status": "ok",
                "selected_q": [0.75, 0.25, 0.75],
                "matrix": [[0, 3, -1], [1, -3, 0], [0, 4, 0]],
                "determinant": 4,
            },
            "reshaped_model": reshaped_model,
            "refined_python_result": {
                "method": "sun-gswt-classical-variational",
                "energy": -8.8,
                "starts": 2,
                "seed": 0,
                "supercell_shape": [4, 4, 1],
                "local_rays": list(refined_state["local_rays"]),
                "classical_state": refined_state,
                "projector_diagnostics": {
                    "dominant_ordering_q": [0.75, 0.25, 0.75],
                    "top_components": [{"q": [0.75, 0.25, 0.75], "weight": 0.2}],
                },
                "stationarity": {"max_residual_norm": 1e-10},
            },
            "decision": {
                "accepted": True,
                "reason": "energy-improved",
                "selected_backend": "python",
                "energy_before_per_site": -2.0,
                "energy_after_python_per_site": -2.2,
                "energy_gain_per_site": 0.2,
                "selected_classical_state": refined_state,
            },
            "magnetic_supercell_refinement": magnetic_refinement,
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
                "solve_sun_gswt_classical_ground_state",
                return_value=initial_solver_result,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "run_cpn_magnetic_supercell_refinement",
                return_value=refinement_result,
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
                    classical_method="sun-gswt-cpn",
                    run_gswt=True,
                    gswt_backend="python",
                    starts=2,
                    seed=0,
                )

        build_gswt_mock.assert_called_once()
        called_model, called_solver_result = build_gswt_mock.call_args.args[:2]
        self.assertEqual(called_model, reshaped_model)
        self.assertEqual(called_solver_result["selected_classical_branch"], "magnetic-supercell-refined")
        self.assertTrue(called_solver_result["magnetic_supercell_refinement"]["accepted"])
        run_gswt_mock.assert_called_once_with(gswt_payload, gswt_backend="python")
        self.assertEqual(manifest["solver"]["classical_state_result"]["role"], "final")
        self.assertEqual(
            manifest["solver"]["classical_state_result"]["selected_classical_branch"],
            "magnetic-supercell-refined",
        )
        self.assertTrue(
            manifest["solver"]["classical_state_result"]["diagnostics"]["magnetic_supercell_refinement"]["accepted"]
        )

    def test_maybe_apply_refinement_uses_sunny_selected_state_when_sunny_backend_wins(self):
        classical_model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "positions": [[0.0, 0.0, 0.0]],
        }
        initial_state = _final_local_ray_state()
        solver_result = {
            "method": "sun-gswt-cpn",
            "energy": -2.0,
            "starts": 2,
            "seed": 0,
            "supercell_shape": [1, 1, 1],
            "local_rays": list(initial_state["local_rays"]),
            "classical_state": initial_state,
            "projector_diagnostics": {"dominant_ordering_q": [0.25, 0.75, 0.25], "top_components": []},
            "stationarity": {"max_residual_norm": 1e-8},
        }
        python_state = {
            **_final_local_ray_state(),
            "supercell_shape": [4, 4, 1],
            "ordering": {
                "kind": "commensurate-supercell",
                "q_vector": [0.75, 0.25, 0.75],
                "supercell_shape": [4, 4, 1],
            },
        }
        sunny_state = {
            **_final_local_ray_state(),
            "supercell_shape": [4, 4, 1],
            "ordering": {
                "kind": "commensurate-supercell",
                "q_vector": [0.25, 0.0, 0.25],
                "supercell_shape": [4, 4, 1],
            },
        }
        reshaped_model = {
            **classical_model,
            "positions": [[0.0, 0.0, 0.0]] * 4,
        }
        refinement_result = {
            "decision": {
                "accepted": True,
                "reason": "energy-improved",
                "selected_backend": "sunny",
                "selected_classical_state": sunny_state,
                "energy_before_per_site": -2.0,
                "energy_after_python_per_site": -2.2,
                "energy_after_sunny_per_site": -2.3,
                "energy_gain_per_site": 0.3,
            },
            "refined_python_result": {
                "method": "sun-gswt-cpn",
                "energy": -8.8,
                "starts": 2,
                "seed": 0,
                "supercell_shape": [4, 4, 1],
                "local_rays": list(python_state["local_rays"]),
                "classical_state": python_state,
            },
            "reshaped_model": reshaped_model,
            "magnetic_supercell_refinement": {
                "accepted": True,
                "acceptance_backend": "sunny",
                "selected_backend": "sunny",
                "trigger_q": [0.25, 0.0, 0.25],
                "candidate_matrix": [[0, 1, 0], [1, 0, -1], [0, 0, 4]],
                "energy_before_per_site": -2.0,
                "energy_after_python_per_site": -2.2,
                "energy_after_sunny_per_site": -2.3,
                "energy_gain_per_site": 0.3,
                "candidates": [],
            },
        }

        with patch.object(
            solve_pseudospin_orbital_pipeline,
            "run_cpn_magnetic_supercell_refinement",
            return_value=refinement_result,
        ):
            selected_model, selected_result = solve_pseudospin_orbital_pipeline._maybe_apply_cpn_magnetic_supercell_refinement(
                classical_model,
                solver_result,
                starts=2,
                seed=0,
                max_candidate_components=4,
                max_denominator=16,
            )

        self.assertEqual(selected_model, reshaped_model)
        self.assertEqual(selected_result["selected_classical_branch"], "magnetic-supercell-refined")
        self.assertEqual(selected_result["magnetic_supercell_refinement"]["acceptance_backend"], "sunny")
        self.assertEqual(
            selected_result["classical_state"]["ordering"]["q_vector"],
            [0.25, 0.0, 0.25],
        )

    def test_sun_gswt_cpn_pipeline_passes_requested_supercell_shape_to_classical_solver(self):
        parsed_payload = _parsed_payload_with_cpn_family()
        simplified_payload = _simplified_payload()
        report_manifest = _report_manifest()
        classical_model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
        }
        solver_result = {
            "method": "sun-gswt-cpn",
            "energy": -2.0,
            "starts": 2,
            "seed": 0,
            "supercell_shape": [4, 4, 4],
            "local_rays": list(_final_local_ray_state()["local_rays"]),
            "classical_state": _final_local_ray_state(),
            "projector_diagnostics": {"dominant_ordering_q": [0.25, 0.75, 0.25], "top_components": []},
            "stationarity": {"max_residual_norm": 1e-8},
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
                "solve_sun_gswt_classical_ground_state",
                return_value=solver_result,
            ) as solve_mock, patch.object(
                solve_pseudospin_orbital_pipeline,
                "_maybe_apply_cpn_magnetic_supercell_refinement",
                side_effect=lambda model, result, *, starts, seed, max_candidate_components, max_denominator, verify_with_sunny=False: (model, result),
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "write_results_bundle",
                return_value={"status": "ok"},
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "_write_solver_stage_markdown",
                return_value=docs_dir / "phase-note.md",
            ):
                solve_pseudospin_orbital_pipeline.solve_from_files(
                    poscar_path=Path(tmpdir) / "POSCAR",
                    hr_path=Path(tmpdir) / "hr.dat",
                    output_dir=output_dir,
                    docs_dir=docs_dir,
                    compile_pdf=False,
                    classical_method="sun-gswt-cpn",
                    supercell_shape=(4, 4, 4),
                    run_gswt=False,
                    starts=2,
                    seed=0,
                )

        solve_mock.assert_called_once_with(
            classical_model,
            supercell_shape=(4, 4, 4),
            starts=2,
            seed=0,
        )

    def test_sun_gswt_cpn_pipeline_auto_promotes_default_unit_supercell_when_larger_periodic_branch_wins(self):
        parsed_payload = _parsed_payload_with_cpn_family()
        simplified_payload = _simplified_payload()
        report_manifest = _report_manifest()
        classical_model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "positions": [[0.0, 0.0, 0.0]],
        }
        initial_result = {
            "method": "sun-gswt-cpn",
            "energy": -1.565,
            "starts": 2,
            "seed": 0,
            "supercell_shape": [1, 1, 1],
            "local_rays": list(_final_local_ray_state()["local_rays"]),
            "classical_state": _final_local_ray_state(),
            "projector_diagnostics": {"dominant_ordering_q": [0.0, 0.0, 0.0], "top_components": []},
            "stationarity": {"max_residual_norm": 1e-8},
        }
        promoted_seed_result = {
            "method": "sun-gswt-cpn",
            "energy": -2.782712359221584,
            "starts": 2,
            "seed": 0,
            "supercell_shape": [4, 4, 4],
            "local_rays": list(_final_local_ray_state()["local_rays"]),
            "classical_state": {
                **_final_local_ray_state(),
                "supercell_shape": [4, 4, 4],
            },
            "projector_diagnostics": {
                "dominant_ordering_q": [0.25, 0.75, 0.25],
                "top_components": [{"q": [0.25, 0.75, 0.25], "weight": 0.14}],
            },
            "stationarity": {"max_residual_norm": 1e-8},
        }
        refined_solver_result = {
            "method": "sun-gswt-classical-variational",
            "energy": -11.66537089338383,
            "starts": 2,
            "seed": 0,
            "supercell_shape": [4, 4, 1],
            "local_rays": list(_final_local_ray_state()["local_rays"]),
            "classical_state": {
                **_final_local_ray_state(),
                "supercell_shape": [4, 4, 1],
                "ordering": {
                    "kind": "commensurate-supercell",
                    "q_vector": [0.75, 0.25, 0.75],
                    "supercell_shape": [4, 4, 1],
                },
            },
            "projector_diagnostics": {
                "dominant_ordering_q": [0.75, 0.25, 0.75],
                "top_components": [{"q": [0.75, 0.25, 0.75], "weight": 0.2}],
            },
            "stationarity": {"max_residual_norm": 1e-10},
            "selected_classical_branch": "magnetic-supercell-refined",
            "magnetic_supercell_refinement": {
                "accepted": True,
                "trigger_q": [0.75, 0.25, 0.75],
                "candidate_matrix": [[0, 3, -1], [1, -3, 0], [0, 4, 0]],
                "energy_before_per_site": -2.782712359221584,
                "energy_after_python_per_site": -2.9163427233459576,
                "energy_gain_per_site": 0.13363036412437346,
                "candidates": [
                    {
                        "accepted": True,
                        "trigger_q": [0.75, 0.25, 0.75],
                        "candidate_matrix": [[0, 3, -1], [1, -3, 0], [0, 4, 0]],
                    }
                ],
            },
        }
        reshaped_model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "positions": [[0.0, 0.0, 0.0]] * 4,
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
                "solve_sun_gswt_classical_ground_state",
                side_effect=[initial_result, promoted_seed_result],
            ) as solve_mock, patch.object(
                solve_pseudospin_orbital_pipeline,
                "_maybe_apply_cpn_magnetic_supercell_refinement",
                # First branch keeps the seed state, second branch returns the accepted refined branch.
                side_effect=[
                    (
                        classical_model,
                        {
                            **initial_result,
                            "magnetic_supercell_refinement": {
                                "accepted": False,
                                "candidate_count": 0,
                                "energy_before_per_site": -1.565,
                            },
                        },
                    ),
                    (reshaped_model, refined_solver_result),
                ],
            ), patch.object(
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
                    classical_method="sun-gswt-cpn",
                    supercell_shape=(1, 1, 1),
                    run_gswt=False,
                    starts=2,
                    seed=0,
                )

        self.assertEqual(solve_mock.call_count, 2)
        self.assertEqual(solve_mock.call_args_list[0].kwargs["supercell_shape"], (1, 1, 1))
        self.assertEqual(solve_mock.call_args_list[1].kwargs["supercell_shape"], (4, 4, 4))
        self.assertEqual(
            manifest["solver"]["classical_state_result"]["selected_classical_branch"],
            "magnetic-supercell-refined",
        )
        self.assertEqual(
            manifest["solver"]["classical_state_result"]["diagnostics"]["magnetic_supercell_refinement"]["accepted"],
            True,
        )

    def test_sun_gswt_cpn_pipeline_can_disable_default_unit_supercell_promotion(self):
        parsed_payload = _parsed_payload_with_cpn_family()
        simplified_payload = _simplified_payload()
        report_manifest = _report_manifest()
        classical_model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "positions": [[0.0, 0.0, 0.0]],
        }
        initial_result = {
            "method": "sun-gswt-cpn",
            "energy": -1.565,
            "starts": 2,
            "seed": 0,
            "supercell_shape": [1, 1, 1],
            "local_rays": list(_final_local_ray_state()["local_rays"]),
            "classical_state": _final_local_ray_state(),
            "projector_diagnostics": {"dominant_ordering_q": [0.0, 0.0, 0.0], "top_components": []},
            "stationarity": {"max_residual_norm": 1e-8},
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
                "solve_sun_gswt_classical_ground_state",
                return_value=initial_result,
            ) as solve_mock, patch.object(
                solve_pseudospin_orbital_pipeline,
                "_maybe_apply_cpn_magnetic_supercell_refinement",
                side_effect=lambda model, result, *, starts, seed, max_candidate_components, max_denominator, verify_with_sunny=False: (model, result),
            ), patch.object(
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
                    classical_method="sun-gswt-cpn",
                    supercell_shape=(1, 1, 1),
                    supercell_promotion_policy="none",
                    run_gswt=False,
                    starts=2,
                    seed=0,
                )

        solve_mock.assert_called_once()
        self.assertEqual(
            manifest["solver"]["supercell_promotion"]["policy"],
            "none",
        )
        self.assertEqual(
            manifest["solver"]["supercell_promotion"]["attempted"],
            False,
        )

    def test_sun_gswt_cpn_pipeline_uses_configured_promotion_shape(self):
        parsed_payload = _parsed_payload_with_cpn_family()
        simplified_payload = _simplified_payload()
        report_manifest = _report_manifest()
        classical_model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "positions": [[0.0, 0.0, 0.0]],
        }
        initial_result = {
            "method": "sun-gswt-cpn",
            "energy": -1.5,
            "starts": 2,
            "seed": 0,
            "supercell_shape": [1, 1, 1],
            "local_rays": list(_final_local_ray_state()["local_rays"]),
            "classical_state": _final_local_ray_state(),
            "projector_diagnostics": {"dominant_ordering_q": [0.0, 0.0, 0.0], "top_components": []},
            "stationarity": {"max_residual_norm": 1e-8},
        }
        promoted_result = {
            **initial_result,
            "energy": -1.7,
            "supercell_shape": [3, 3, 1],
            "classical_state": {
                **_final_local_ray_state(),
                "supercell_shape": [3, 3, 1],
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
                "solve_sun_gswt_classical_ground_state",
                side_effect=[initial_result, promoted_result],
            ) as solve_mock, patch.object(
                solve_pseudospin_orbital_pipeline,
                "_maybe_apply_cpn_magnetic_supercell_refinement",
                side_effect=lambda model, result, *, starts, seed, max_candidate_components, max_denominator, verify_with_sunny=False: (model, result),
            ), patch.object(
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
                    classical_method="sun-gswt-cpn",
                    supercell_shape=(1, 1, 1),
                    supercell_promotion_shape=(3, 3, 1),
                    run_gswt=False,
                    starts=2,
                    seed=0,
                )

        self.assertEqual(solve_mock.call_count, 2)
        self.assertEqual(solve_mock.call_args_list[1].kwargs["supercell_shape"], (3, 3, 1))
        self.assertEqual(
            manifest["solver"]["supercell_promotion"]["promoted_supercell_shape"],
            [3, 3, 1],
        )

    def test_cpn_pipeline_forwards_configured_refinement_candidate_budget(self):
        parsed_payload = _parsed_payload_with_cpn_family()
        simplified_payload = _simplified_payload()
        report_manifest = _report_manifest()
        classical_model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "positions": [[0.0, 0.0, 0.0]],
        }
        solver_result = {
            "method": "sun-gswt-cpn",
            "energy": -2.0,
            "starts": 2,
            "seed": 0,
            "supercell_shape": [4, 4, 4],
            "local_rays": list(_final_local_ray_state()["local_rays"]),
            "classical_state": {
                **_final_local_ray_state(),
                "supercell_shape": [4, 4, 4],
            },
            "projector_diagnostics": {"dominant_ordering_q": [0.25, 0.75, 0.25], "top_components": []},
            "stationarity": {"max_residual_norm": 1e-8},
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
                "solve_sun_gswt_classical_ground_state",
                return_value=solver_result,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "_maybe_apply_cpn_magnetic_supercell_refinement",
                side_effect=lambda model, result, *, starts, seed, max_candidate_components, max_denominator, verify_with_sunny=False: (
                    model,
                    {
                        **result,
                        "candidate_budget_seen": int(max_candidate_components),
                    },
                ),
            ) as refinement_mock, patch.object(
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
                    classical_method="sun-gswt-cpn",
                    supercell_shape=(4, 4, 4),
                    magnetic_supercell_max_candidate_components=7,
                    run_gswt=False,
                    starts=2,
                    seed=0,
                )

        self.assertEqual(
            refinement_mock.call_args.kwargs["max_candidate_components"],
            7,
        )
        self.assertEqual(manifest["solver"]["candidate_budget_seen"], 7)

    def test_local_ray_pipeline_forwards_configured_refinement_max_denominator(self):
        parsed_payload = _parsed_payload_with_cpn_family()
        simplified_payload = _simplified_payload()
        report_manifest = _report_manifest()
        classical_model = {
            "model_type": "sun_gswt_classical",
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
        }
        local_ray_result = {
            "method": "cpn-local-ray-minimize",
            "energy": -2.75,
            "starts": 4,
            "seed": 0,
            "supercell_shape": [1, 1, 1],
            "local_rays": list(_final_local_ray_state()["local_rays"]),
            "classical_state": _final_local_ray_state(),
            "projector_diagnostics": {"dominant_ordering_q": [0.25, 0.0, 0.25], "top_components": []},
            "stationarity": {"max_residual_norm": 1e-8},
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
                side_effect=RuntimeError("skip-preconditioner"),
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "solve_cpn_local_ray_ground_state",
                return_value=local_ray_result,
            ), patch.object(
                solve_pseudospin_orbital_pipeline,
                "_maybe_apply_cpn_magnetic_supercell_refinement",
                side_effect=lambda model, result, *, starts, seed, max_candidate_components, max_denominator, verify_with_sunny=False: (
                    model,
                    {
                        **result,
                        "max_denominator_seen": int(max_denominator),
                    },
                ),
            ) as refinement_mock, patch.object(
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
                    classical_method="cpn-local-ray-minimize",
                    magnetic_supercell_max_denominator=21,
                    run_gswt=False,
                    starts=4,
                    seed=0,
                )

        self.assertEqual(refinement_mock.call_args.kwargs["max_denominator"], 21)
        self.assertEqual(manifest["solver"]["max_denominator_seen"], 21)

    def test_cpn_workflow_regression_fixtures(self):
        for fixture_name in [
            "uniform_smoke",
            "commensurate_refine",
            "diagnostic_glt_fallback",
        ]:
            fixture = _load_cpn_workflow_fixture(fixture_name)
            parsed_payload = _parsed_payload_with_cpn_family()
            simplified_payload = _simplified_payload()
            report_manifest = _report_manifest()
            classical_model = {
                "model_type": "sun_gswt_classical",
                "classical_manifold": "CP^(N-1)",
                "local_dimension": 2,
                "positions": [[0.0, 0.0, 0.0]],
            }

            with self.subTest(fixture=fixture_name), tempfile.TemporaryDirectory() as tmpdir:
                output_dir = Path(tmpdir) / "out"
                docs_dir = Path(tmpdir) / "docs"
                output_dir.mkdir(parents=True, exist_ok=True)
                docs_dir.mkdir(parents=True, exist_ok=True)

                common_patches = [
                    patch.object(
                        solve_pseudospin_orbital_pipeline,
                        "build_pseudospin_orbital_payload",
                        return_value=parsed_payload,
                    ),
                    patch.object(
                        solve_pseudospin_orbital_pipeline,
                        "simplify_pseudospin_orbital_payload",
                        return_value=simplified_payload,
                    ),
                    patch.object(
                        solve_pseudospin_orbital_pipeline,
                        "group_pseudospin_orbital_terms",
                        return_value={"distance_shells": [], "bonds": []},
                    ),
                    patch.object(
                        solve_pseudospin_orbital_pipeline,
                        "write_pseudospin_orbital_reports",
                        return_value=report_manifest,
                    ),
                    patch.object(
                        solve_pseudospin_orbital_pipeline,
                        "write_results_bundle",
                        return_value={"status": "ok"},
                    ),
                    patch.object(
                        solve_pseudospin_orbital_pipeline,
                        "_write_solver_stage_markdown",
                        return_value=docs_dir / "phase-note.md",
                    ),
                ]

                if fixture["scenario"] == "uniform_smoke":
                    solver_result = {
                        "method": "sun-gswt-cpn",
                        "energy": -1.5,
                        "starts": 2,
                        "seed": 0,
                        "supercell_shape": [1, 1, 1],
                        "local_rays": list(_final_local_ray_state()["local_rays"]),
                        "classical_state": _final_local_ray_state(),
                        "projector_diagnostics": {"dominant_ordering_q": [0.0, 0.0, 0.0], "top_components": []},
                        "stationarity": {"max_residual_norm": 1e-8},
                    }
                    scenario_patches = [
                        patch.object(
                            solve_pseudospin_orbital_pipeline,
                            "build_sun_gswt_classical_payload",
                            return_value=classical_model,
                        ),
                        patch.object(
                            solve_pseudospin_orbital_pipeline,
                            "solve_sun_gswt_classical_ground_state",
                            return_value=solver_result,
                        ),
                        patch.object(
                            solve_pseudospin_orbital_pipeline,
                            "_maybe_apply_cpn_magnetic_supercell_refinement",
                            return_value=(
                                classical_model,
                                {
                                    **solver_result,
                                    "magnetic_supercell_refinement": {
                                        "accepted": False,
                                        "candidate_count": 0,
                                        "energy_before_per_site": -1.5,
                                    },
                                },
                            ),
                        ),
                    ]
                elif fixture["scenario"] == "commensurate_refine":
                    initial_result = {
                        "method": "sun-gswt-cpn",
                        "energy": -1.565,
                        "starts": 2,
                        "seed": 0,
                        "supercell_shape": [1, 1, 1],
                        "local_rays": list(_final_local_ray_state()["local_rays"]),
                        "classical_state": _final_local_ray_state(),
                        "projector_diagnostics": {"dominant_ordering_q": [0.25, 0.75, 0.25], "top_components": []},
                        "stationarity": {"max_residual_norm": 1e-8},
                    }
                    reshaped_model = {
                        **classical_model,
                        "positions": [[0.0, 0.0, 0.0]] * 4,
                    }
                    refined_result = {
                        "method": "sun-gswt-cpn",
                        "energy": -12.073997998161994,
                        "starts": 2,
                        "seed": 0,
                        "supercell_shape": [4, 4, 1],
                        "local_rays": list(_final_local_ray_state()["local_rays"]),
                        "classical_state": {
                            **_final_local_ray_state(),
                            "supercell_shape": [4, 4, 1],
                            "ordering": {
                                "kind": "commensurate-supercell",
                                "q_vector": [0.0, 0.25, 0.0],
                                "supercell_shape": [4, 4, 1],
                            },
                        },
                        "selected_classical_branch": "magnetic-supercell-refined",
                        "magnetic_supercell_refinement": {
                            "accepted": True,
                            "acceptance_backend": "sunny",
                            "trigger_q": [0.0, 0.25, 0.0],
                            "candidate_matrix": [[0, 0, 1], [1, 0, 0], [0, 4, 0]],
                            "energy_before_per_site": -1.565,
                            "energy_after_python_per_site": -2.8971224739951573,
                            "energy_after_sunny_per_site": -3.0184994995404986,
                            "energy_gain_per_site": 1.4534994995404985,
                            "candidates": [],
                        },
                    }
                    scenario_patches = [
                        patch.object(
                            solve_pseudospin_orbital_pipeline,
                            "build_sun_gswt_classical_payload",
                            return_value=classical_model,
                        ),
                        patch.object(
                            solve_pseudospin_orbital_pipeline,
                            "solve_sun_gswt_classical_ground_state",
                            return_value=initial_result,
                        ),
                        patch.object(
                            solve_pseudospin_orbital_pipeline,
                            "_maybe_apply_cpn_magnetic_supercell_refinement",
                            return_value=(reshaped_model, refined_result),
                        ),
                    ]
                else:
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
                    scenario_patches = [
                        patch.object(
                            solve_pseudospin_orbital_pipeline,
                            "build_sun_gswt_classical_payload",
                            return_value=classical_model,
                        ),
                        patch.object(
                            solve_pseudospin_orbital_pipeline,
                            "solve_cpn_generalized_lt_ground_state",
                            return_value=diagnostic_glt_result,
                        ),
                        patch.object(
                            solve_pseudospin_orbital_pipeline,
                            "_extract_cpn_glt_preconditioner",
                            return_value=(
                                {"shape": [1, 1, 1], "local_rays": list(_final_local_ray_state()["local_rays"])},
                                {"method": "cpn-generalized-lt", "used": True, "source": "seed_candidate"},
                            ),
                        ),
                        patch.object(
                            solve_pseudospin_orbital_pipeline,
                            "solve_cpn_local_ray_ground_state",
                            return_value=local_ray_result,
                        ),
                        patch.object(
                            solve_pseudospin_orbital_pipeline,
                            "_maybe_apply_cpn_magnetic_supercell_refinement",
                            return_value=(classical_model, local_ray_result),
                        ),
                    ]

                with ExitStack() as stack:
                    for patcher in common_patches + scenario_patches:
                        stack.enter_context(patcher)
                    manifest = solve_pseudospin_orbital_pipeline.solve_from_files(
                        poscar_path=Path(tmpdir) / "POSCAR",
                        hr_path=Path(tmpdir) / "hr.dat",
                        output_dir=output_dir,
                        docs_dir=docs_dir,
                        compile_pdf=False,
                        classical_method=str(fixture["classical_method"]),
                        run_gswt=False,
                    )

                classical_state_result = manifest["solver"]["classical_state_result"]
                self.assertEqual(
                    classical_state_result.get("selected_classical_branch"),
                    fixture["expected"]["selected_classical_branch"],
                )
                self.assertEqual(
                    classical_state_result.get("method"),
                    fixture["expected"]["classical_state_method"],
                )

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
        self.assertIn("legacy many_body_hr adapter", summary)
        self.assertIn("canonical bond terms", summary)
        self.assertNotIn("VR_hr.dat", summary)
        self.assertNotIn("bond blocks", summary)
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

    def test_skill_mentions_conditional_finality_for_cpn_glt(self):
        skill_text = _skill_text()

        self.assertIn("conditionally final", skill_text)
        self.assertIn("diagnostic-only", skill_text)

    def test_report_phase_summary_uses_canonical_cpn_language(self):
        summary = render_pseudospin_orbital_report._phase_summary(
            {
                **_parsed_payload(),
                "model_family": "cpn_pair_model",
                "inferred": {"local_dimension": 4, "multiplet_dimension": 4},
                "bond_terms": [
                    {
                        "source": 0,
                        "target": 0,
                        "translation": [1, 0, 0],
                        "matrix_shape": [16, 16],
                        "pair_matrix": [],
                    }
                ],
            },
            _simplified_payload(),
            {"bonds": [], "distance_shells": []},
        )

        self.assertIn("canonical cpn_pair_model", summary)
        self.assertIn("legacy many_body_hr adapter", summary)
        self.assertIn("canonical bond terms", summary)
        self.assertNotIn("wannier-style hr.dat", summary)
        self.assertNotIn("bond blocks", summary)

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
