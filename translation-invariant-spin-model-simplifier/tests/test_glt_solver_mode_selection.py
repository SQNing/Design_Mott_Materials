import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from cli.solve_pseudospin_orbital_pipeline import _solve_direct_pseudospin_glt, solve_from_parsed_payload
from cli.solve_cpn_payload_pipeline import main as solve_cpn_payload_main


class GltSolverModeSelectionTests(unittest.TestCase):
    def setUp(self):
        self.classical_model = {"local_dimension": 2, "bond_tensors": [], "classical_manifold": "CP^(N-1)"}

    def test_fast_mode_uses_direct_solver_without_certification(self):
        with patch(
            "cli.solve_pseudospin_orbital_pipeline.solve_cpn_generalized_lt_ground_state",
            return_value={"solver_role": "diagnostic-only", "energy": 3.0},
        ) as solve_mock, patch(
            "cli.solve_pseudospin_orbital_pipeline.certify_cpn_generalized_lt",
            return_value={"promotion_summary": {"solver_role": "final"}},
        ) as certify_mock:
            result = _solve_direct_pseudospin_glt(
                self.classical_model,
                classical_method="cpn-generalized-lt",
                seed=7,
                glt_certification_mode="off",
                glt_solver_mode="fast",
            )

        self.assertEqual(result["solver_role"], "diagnostic-only")
        solve_mock.assert_called_once()
        certify_mock.assert_not_called()

    def test_certified_mode_uses_certification_path(self):
        with patch(
            "cli.solve_pseudospin_orbital_pipeline.solve_cpn_generalized_lt_ground_state",
            return_value={"solver_role": "diagnostic-only", "energy": 3.0},
        ) as solve_mock, patch(
            "cli.solve_pseudospin_orbital_pipeline.certify_cpn_generalized_lt",
            return_value={
                "promotion_summary": {"solver_role": "final", "promotion_reason": "certified"},
                "heuristic_seed": {"raw_result": {"energy": 1.5, "solver_role": "final"}},
            },
        ) as certify_mock:
            result = _solve_direct_pseudospin_glt(
                self.classical_model,
                classical_method="cpn-generalized-lt",
                seed=11,
                glt_certification_mode="off",
                glt_solver_mode="certified",
            )

        self.assertEqual(result["solver_role"], "final")
        self.assertEqual(result["promotion_reason"], "certified")
        solve_mock.assert_not_called()
        certify_mock.assert_called_once()

    def test_auto_certification_skips_certifier_when_fast_result_is_final(self):
        with patch(
            "cli.solve_pseudospin_orbital_pipeline.solve_cpn_generalized_lt_ground_state",
            return_value={"solver_role": "final", "energy": 1.0},
        ) as solve_mock, patch(
            "cli.solve_pseudospin_orbital_pipeline.certify_cpn_generalized_lt",
            return_value={"promotion_summary": {"solver_role": "final"}},
        ) as certify_mock:
            result = _solve_direct_pseudospin_glt(
                self.classical_model,
                classical_method="cpn-generalized-lt",
                seed=13,
                glt_certification_mode="auto",
                glt_solver_mode="fast",
            )

        self.assertEqual(result["solver_role"], "final")
        solve_mock.assert_called_once()
        certify_mock.assert_not_called()

    def test_auto_certification_certifies_when_fast_result_is_diagnostic(self):
        fast_result = {"solver_role": "diagnostic-only", "energy": 3.0}
        with patch(
            "cli.solve_pseudospin_orbital_pipeline.solve_cpn_generalized_lt_ground_state",
            return_value=fast_result,
        ) as solve_mock, patch(
            "cli.solve_pseudospin_orbital_pipeline.certify_cpn_generalized_lt",
            return_value={
                "promotion_summary": {"solver_role": "final", "promotion_reason": "certified"},
                "heuristic_seed": {"raw_result": {"energy": 2.0, "solver_role": "diagnostic-only"}},
            },
        ) as certify_mock:
            result = _solve_direct_pseudospin_glt(
                self.classical_model,
                classical_method="cpn-generalized-lt",
                seed=17,
                glt_certification_mode="auto",
                glt_solver_mode="fast",
            )

        self.assertEqual(result["solver_role"], "final")
        self.assertEqual(result["promotion_reason"], "certified")
        solve_mock.assert_called_once()
        certify_mock.assert_called_once()
        self.assertIs(certify_mock.call_args.kwargs["heuristic_result"], fast_result)

    def test_solve_from_parsed_payload_forwards_glt_solver_mode(self):
        parsed_payload = {
            "classical_bond_label": "cpn",
            "bond_tensors": [],
            "classical_manifold": "CP^(N-1)",
            "local_dimension": 2,
            "local_sites": [],
            "magnetic_site_count": 1,
        }

        with patch(
            "cli.solve_pseudospin_orbital_pipeline.build_sun_gswt_classical_payload",
            return_value=self.classical_model,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.simplify_pseudospin_orbital_payload",
            return_value=parsed_payload,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.group_pseudospin_orbital_terms",
            return_value={"distance_shells": []},
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.write_pseudospin_orbital_reports",
            return_value={"reports": []},
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline._solve_direct_pseudospin_glt",
            return_value={"solver_role": "diagnostic-only", "energy": 3.0},
        ) as direct_mock, patch(
            "cli.solve_pseudospin_orbital_pipeline._build_pseudospin_classical_state_result",
            return_value={"role": "diagnostic-only"},
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline._solver_phase_summary",
            return_value="phase summary",
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.write_results_bundle",
            return_value={"bundle": "ok"},
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline._write_solver_stage_markdown",
            return_value=Path("phase.md"),
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline._build_result_payload",
            return_value={"status": "ok"},
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline._run_selected_gswt",
            return_value={"status": "ok"},
        ):
            solve_from_parsed_payload(
                parsed_payload,
                output_dir=Path("/tmp/glt-mode-test"),
                docs_dir=Path("/tmp/glt-mode-docs"),
                compile_pdf=False,
                classical_method="cpn-generalized-lt",
                glt_certification_mode="off",
                glt_solver_mode="certified",
                run_gswt=False,
            )

        self.assertEqual(direct_mock.call_args.kwargs["glt_solver_mode"], "certified")

    def test_auto_promoted_glt_final_builds_gswt_payload(self):
        parsed_payload = {
            "classical_bond_label": "cpn",
            "model_bond_label": "cpn_pair_model",
            "bond_tensors": [],
            "classical_manifold": "CP^(N-1)",
            "inferred": {"local_dimension": 2},
            "local_dimension": 2,
            "local_sites": [],
            "magnetic_site_count": 1,
            "basis_order": ["0", "1"],
            "pair_basis_order": ["0", "1"],
        }
        final_classical_state = {
            "schema_version": 1,
            "state_kind": "local_rays",
            "manifold": "CP^(N-1)",
            "basis_order": ["0", "1"],
            "pair_basis_order": ["0", "1"],
            "supercell_shape": [1, 1, 1],
            "local_rays": [
                {
                    "cell": [0, 0, 0],
                    "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}],
                }
            ],
            "ordering": {"kind": "uniform", "supercell_shape": [1, 1, 1]},
        }
        glt_final = {
            "method": "cpn-generalized-lt",
            "solver_role": "final",
            "promotion_reason": "exact_projector_solution",
            "energy": -1.0,
            "classical_state": final_classical_state,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "out"
            docs_dir = Path(tmpdir) / "docs"
            with patch(
                "cli.solve_pseudospin_orbital_pipeline.build_sun_gswt_classical_payload",
                return_value=self.classical_model,
            ), patch(
                "cli.solve_pseudospin_orbital_pipeline.simplify_pseudospin_orbital_payload",
                return_value={"effective_model": {}, "simplification": {}, "canonical_model": {}},
            ), patch(
                "cli.solve_pseudospin_orbital_pipeline.group_pseudospin_orbital_terms",
                return_value={"distance_shells": []},
            ), patch(
                "cli.solve_pseudospin_orbital_pipeline.write_pseudospin_orbital_reports",
                return_value={"reports": []},
            ), patch(
                "cli.solve_pseudospin_orbital_pipeline._solve_direct_pseudospin_glt",
                return_value=glt_final,
            ), patch(
                "cli.solve_pseudospin_orbital_pipeline._maybe_apply_cpn_magnetic_supercell_refinement",
                side_effect=lambda model, result, **_kwargs: (model, result),
            ), patch(
                "cli.solve_pseudospin_orbital_pipeline._build_selected_gswt_payload",
                return_value={"payload_kind": "sun_gswt"},
            ) as gswt_payload_mock, patch(
                "cli.solve_pseudospin_orbital_pipeline._run_selected_gswt",
                return_value={"status": "ok"},
            ), patch(
                "cli.solve_pseudospin_orbital_pipeline.write_results_bundle",
                return_value={"bundle": "ok"},
            ), patch(
                "cli.solve_pseudospin_orbital_pipeline._write_solver_stage_markdown",
                return_value=docs_dir / "phase.md",
            ), patch(
                "cli.solve_pseudospin_orbital_pipeline._solver_phase_summary",
                return_value="phase summary",
            ):
                manifest = solve_from_parsed_payload(
                    parsed_payload,
                    output_dir=output_dir,
                    docs_dir=docs_dir,
                    compile_pdf=False,
                    classical_method="auto",
                    glt_certification_mode="off",
                    glt_solver_mode="fast",
                    run_gswt=True,
                )

        gswt_payload_mock.assert_called_once()
        self.assertIsNotNone(manifest["artifacts"]["gswt_payload"])
        self.assertEqual(manifest["solver"]["gswt"], {"status": "ok"})

    def test_cpn_payload_cli_forwards_glt_solver_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            payload_path = Path(tmpdir) / "payload.json"
            output_dir = Path(tmpdir) / "out"
            docs_dir = Path(tmpdir) / "docs"
            payload_path.write_text(json.dumps({"classical_bond_label": "cpn"}), encoding="utf-8")

            argv = [
                "solve_cpn_payload_pipeline.py",
                "--parsed-payload",
                str(payload_path),
                "--output-dir",
                str(output_dir),
                "--docs-dir",
                str(docs_dir),
                "--classical-method",
                "cpn-generalized-lt",
                "--glt-certification-mode",
                "off",
                "--glt-solver-mode",
                "certified",
                "--no-pdf",
                "--no-gswt",
            ]

            with patch("sys.argv", argv), patch(
                "cli.solve_cpn_payload_pipeline.solve_from_parsed_payload",
                return_value={"status": "ok"},
            ) as solve_mock:
                exit_code = solve_cpn_payload_main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(solve_mock.call_args.kwargs["glt_solver_mode"], "certified")
        self.assertEqual(solve_mock.call_args.kwargs["glt_certification_mode"], "off")


if __name__ == "__main__":
    unittest.main()
