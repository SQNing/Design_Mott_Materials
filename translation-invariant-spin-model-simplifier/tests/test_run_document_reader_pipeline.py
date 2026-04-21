import json
import subprocess
import sys
import tempfile
import unittest
from base64 import b64encode
from pathlib import Path
from unittest.mock import patch


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from cli.run_document_reader_pipeline import run_document_reader_pipeline


class RunDocumentReaderPipelineTests(unittest.TestCase):
    FEI2_FIXTURE_PATH = SKILL_ROOT / "tests" / "data" / "fei2_document_input.tex"
    PROSE_ONLY_EFFECTIVE_FIXTURE = r"""
\documentclass[11pt]{article}
\begin{document}
\section*{Effective Hamiltonian}
The effective Hamiltonian contains anisotropic spin interactions discussed in the main text.
\end{document}
"""

    @classmethod
    def setUpClass(cls):
        cls.fei2_fixture = cls.FEI2_FIXTURE_PATH.read_text(encoding="utf-8")

    @staticmethod
    def _mock_agent_command():
        payload = {
            "source_document": {"source_kind": "agent_normalized_document", "source_path": "paper.tex"},
            "model_candidates": [{"name": "effective", "role": "main"}],
            "candidate_models": {
                "effective": {
                    "operator_expression": "Jmock * Sz@0 Sz@1",
                }
            },
            "parameter_registry": {"Jmock": -1.25},
        }
        payload_json = json.dumps(payload)
        return f"printf '%s\\n' '{payload_json}'"

    @staticmethod
    def _mock_fei2_agent_command():
        payload = {
            "source_document": {"source_kind": "agent_normalized_document", "source_path": "fei2_document_input.tex"},
            "model_candidates": [
                {"name": "effective", "role": "main"},
                {"name": "matrix_form", "role": "equivalent_form"},
            ],
            "candidate_models": {
                "effective": {
                    "local_bond_candidates": [
                        {
                            "family": "1",
                            "expression": "J_1^{zz} * Sz@0 Sz@1",
                            "evidence_refs": ["eq_eff_1"],
                        }
                    ]
                },
                "matrix_form": {
                    "matrix_form": True,
                    "local_bond_candidates": [
                        {
                            "family": "1",
                            "expression": "J_1^{xx} * Sx@0 Sx@1 + J_1^{yy} * Sy@0 Sy@1 + J_1^{yz} * Sy@0 Sz@1 + J_1^{yz} * Sz@0 Sy@1 + J_1^{zz} * Sz@0 Sz@1",
                            "evidence_refs": ["eq_mat_1"],
                        }
                    ],
                },
            },
            "parameter_registry": {
                "D": {
                    "value": 2.165,
                    "units": "meV",
                    "evidence_refs": ["eq_param_d"],
                },
                "J_1^{zz}": {
                    "value": -0.236,
                    "units": "meV",
                    "evidence_refs": ["eq_eff_1", "eq_mat_1"],
                },
                "J_1^{xx}": {
                    "value": -0.397,
                    "units": "meV",
                    "evidence_refs": ["eq_mat_1"],
                },
                "J_1^{yy}": {
                    "value": -0.075,
                    "units": "meV",
                    "evidence_refs": ["eq_mat_1"],
                },
                "J_1^{yz}": {
                    "value": -0.261,
                    "units": "meV",
                    "evidence_refs": ["eq_mat_1"],
                },
            },
            "evidence_items": [
                {"id": "eq_eff_1", "kind": "equation", "text": "H contains H_{ij}^{(1)} for first neighbors"},
                {"id": "eq_mat_1", "kind": "equation", "text": "\\mathcal J_{ij}^{(1)} = ..."},
                {"id": "eq_param_d", "kind": "equation", "text": "D = 2.165 \\pm 0.101 meV"},
            ],
        }
        encoded = b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
        return (
            f"{sys.executable} -c "
            "\"import base64; "
            f"print(base64.b64decode('{encoded}').decode())\""
        )

    def test_document_reader_pipeline_stops_at_document_orchestration_when_agent_normalization_is_needed(self):
        orchestration_result = {
            "status": "needs_agent_normalization",
            "interaction": {"status": "needs_input", "id": "agent_document_normalization"},
            "agent_normalization_request": {"target_schema": "agent_normalized_document"},
            "normalized_model": {
                "local_term": {"representation": {"kind": "natural_language", "value": "freeform"}},
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "cli.run_document_reader_pipeline.run_agent_document_normalization_orchestrator",
                return_value=orchestration_result,
            ) as orchestrator:
                result = run_document_reader_pipeline(
                    self.PROSE_ONLY_EFFECTIVE_FIXTURE,
                    source_path="tests/data/prose_only_effective.tex",
                    selected_model_candidate="effective",
                    output_dir=tmpdir,
                )

        self.assertEqual(result["status"], "needs_agent_normalization")
        self.assertEqual(result["stage"], "document_orchestration")
        self.assertEqual(result["document_orchestration_status"], "needs_agent_normalization")
        self.assertEqual(
            result["agent_normalization_request"]["target_schema"],
            "agent_normalized_document",
        )
        orchestrator.assert_called_once()

    def test_document_reader_pipeline_stops_at_document_orchestration_when_agent_review_remains(self):
        orchestration_result = {
            "status": "needs_review",
            "normalized_model": {
                "local_term": {"representation": {"kind": "operator", "value": "J_1^{xx} * Sx@0 Sx@1"}},
            },
            "agent_review": {
                "status": "needs_review",
                "reason": "max_agent_rounds_exhausted",
                "review_category": "semantic_conflict",
                "remaining_finding_ids": ["selected_model_candidate_conflict"],
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "cli.run_document_reader_pipeline.run_agent_document_normalization_orchestrator",
                return_value=orchestration_result,
            ) as orchestrator:
                result = run_document_reader_pipeline(
                    self.PROSE_ONLY_EFFECTIVE_FIXTURE,
                    source_path="tests/data/prose_only_effective.tex",
                    selected_model_candidate="effective",
                    output_dir=tmpdir,
                )

        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["stage"], "document_orchestration")
        self.assertEqual(result["document_orchestration_status"], "needs_review")
        self.assertEqual(result["agent_review"]["reason"], "max_agent_rounds_exhausted")
        self.assertEqual(result["agent_review"]["review_category"], "semantic_conflict")
        orchestrator.assert_called_once()

    def test_document_reader_pipeline_reaches_complete_when_orchestration_and_simplification_succeed(self):
        landed_model = {
            "local_hilbert": {"dimension": 2},
            "local_term": {
                "support": [0, 1],
                "representation": {
                    "kind": "operator",
                    "value": "Jxy * Sx@0 Sx@1 + Jxy * Sy@0 Sy@1 + Jz * Sz@0 Sz@1",
                },
            },
            "parameters": {"Jxy": -0.161, "Jz": -0.236},
            "lattice_description": {"kind": "unspecified", "value": ""},
            "user_required_symmetries": [],
            "allowed_breaking": [],
            "coordinate_convention": {},
            "rotating_frame_transform": {},
            "unsupported_features": [],
        }
        orchestration_result = {
            "status": "ok",
            "normalized_model": landed_model,
        }
        simplification_result = {
            "status": "ok",
            "stage": "complete",
            "normalized_model": landed_model,
            "effective_model": {"main": [{"type": "xxz_exchange"}]},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "cli.run_document_reader_pipeline.run_agent_document_normalization_orchestrator",
                return_value=orchestration_result,
            ) as orchestrator:
                with patch(
                    "cli.run_document_reader_pipeline.run_simplification_from_normalized_model",
                    return_value=simplification_result,
                ) as continuation:
                    result = run_document_reader_pipeline(
                        self.PROSE_ONLY_EFFECTIVE_FIXTURE,
                        source_path="tests/data/prose_only_effective.tex",
                        selected_model_candidate="effective",
                        output_dir=tmpdir,
                    )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["stage"], "complete")
        self.assertEqual(result["document_orchestration_status"], "ok")
        self.assertEqual(result["simplification_status"], "ok")
        self.assertEqual(result["normalized_model"], landed_model)
        self.assertTrue(result["effective_model"]["main"])
        orchestrator.assert_called_once()
        continuation.assert_called_once_with(landed_model)

    def test_document_reader_pipeline_writes_unified_artifacts(self):
        landed_model = {
            "local_hilbert": {"dimension": 2},
            "local_term": {
                "support": [0, 1],
                "representation": {
                    "kind": "operator",
                    "value": "Jxy * Sx@0 Sx@1 + Jxy * Sy@0 Sy@1 + Jz * Sz@0 Sz@1",
                },
            },
            "parameters": {"Jxy": -0.161, "Jz": -0.236},
            "lattice_description": {"kind": "unspecified", "value": ""},
            "user_required_symmetries": [],
            "allowed_breaking": [],
            "coordinate_convention": {},
            "rotating_frame_transform": {},
            "unsupported_features": [],
        }
        orchestration_result = {
            "status": "ok",
            "normalized_model": landed_model,
        }
        simplification_result = {
            "status": "ok",
            "stage": "complete",
            "normalized_model": landed_model,
            "effective_model": {"main": [{"type": "xxz_exchange"}]},
            "simplification": {"candidates": [{"name": "faithful-readable"}]},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "cli.run_document_reader_pipeline.run_agent_document_normalization_orchestrator",
                return_value=orchestration_result,
            ):
                with patch(
                    "cli.run_document_reader_pipeline.run_simplification_from_normalized_model",
                    return_value=simplification_result,
                ):
                    with patch(
                        "cli.run_document_reader_pipeline.render_simplified_model_report",
                        return_value="# Simplified Model Report\n",
                    ):
                        run_document_reader_pipeline(
                            self.PROSE_ONLY_EFFECTIVE_FIXTURE,
                            source_path="tests/data/prose_only_effective.tex",
                            selected_model_candidate="effective",
                            output_dir=tmpdir,
                        )

            output_dir = Path(tmpdir)
            self.assertTrue((output_dir / "document_orchestration" / "final_result.json").exists())
            self.assertTrue((output_dir / "simplification" / "pipeline_result.json").exists())
            self.assertTrue((output_dir / "simplification" / "effective_model.json").exists())
            self.assertTrue((output_dir / "simplification" / "simplification_candidates.json").exists())
            self.assertTrue((output_dir / "simplification" / "report.md").exists())
            self.assertTrue((output_dir / "final_pipeline_result.json").exists())

    def test_document_reader_pipeline_cli_prints_complete_payload_for_mock_agent_command(self):
        script_path = SKILL_ROOT / "scripts" / "cli" / "run_document_reader_pipeline.py"

        with tempfile.TemporaryDirectory() as tmpdir:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(script_path),
                    "--freeform",
                    self.PROSE_ONLY_EFFECTIVE_FIXTURE,
                    "--source-path",
                    "tests/data/prose_only_effective.tex",
                    "--selected-model-candidate",
                    "effective",
                    "--output-dir",
                    tmpdir,
                    "--agent-command",
                    self._mock_agent_command(),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "needs_review")
            self.assertEqual(payload["stage"], "document_orchestration")
            self.assertEqual(payload["agent_review"]["reason"], "max_agent_rounds_exhausted")
            self.assertEqual(
                payload["normalized_model"]["local_term"]["representation"]["kind"],
                "operator",
            )
            self.assertTrue((Path(tmpdir) / "final_pipeline_result.json").exists())

    def test_document_reader_pipeline_can_complete_real_fei2_fixture_with_agent_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_document_reader_pipeline(
                self.fei2_fixture,
                source_path=str(self.FEI2_FIXTURE_PATH),
                selected_model_candidate="effective",
                selected_local_bond_family="1",
                selected_coordinate_convention="global_crystallographic",
                output_dir=tmpdir,
                agent_command=self._mock_fei2_agent_command(),
            )

            output_dir = Path(tmpdir)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["stage"], "complete")
            self.assertEqual(
                result["normalized_model"]["local_term"]["representation"]["value"],
                "J_1^{zz} * Sz@0 Sz@1",
            )
            self.assertAlmostEqual(result["normalized_model"]["parameters"]["J_1^{zz}"], -0.236)
            self.assertTrue((output_dir / "document_orchestration" / "agent_normalized_document.json").exists())
            self.assertTrue((output_dir / "simplification" / "pipeline_result.json").exists())

    def test_document_reader_pipeline_can_emit_bridge_and_solver_artifacts_when_opted_in(self):
        landed_model = {
            "selected_model_candidate": "effective",
            "selected_local_bond_family": "2a'",
            "selected_coordinate_convention": "global_crystallographic",
            "local_hilbert": {"dimension": 3},
            "lattice": {
                "kind": "trigonal",
                "dimension": 3,
                "cell_parameters": {
                    "a": 4.05012,
                    "b": 4.05012,
                    "c": 6.75214,
                    "alpha": 90.0,
                    "beta": 90.0,
                    "gamma": 120.0,
                },
                "positions": [[0.0, 0.0, 0.0]],
                "family_shell_map": {"2a'": {"shell_index": 6, "distance": 9.736622}},
            },
            "local_term": {
                "support": [0, 1],
                "representation": {"kind": "operator", "value": "J_2ap^{zz} * Sz@0 Sz@1"},
            },
            "parameters": {"J_2ap^{zz}": 0.073, "J_2ap^{pm}": 0.068},
            "unsupported_features": [],
        }
        orchestration_result = {"status": "ok", "normalized_model": landed_model}
        simplification_result = {
            "status": "ok",
            "stage": "complete",
            "normalized_model": landed_model,
            "effective_model": {
                "main": [
                    {
                        "type": "xxz_exchange",
                        "family": "2a'",
                        "coefficient_xy": 0.068,
                        "coefficient_z": 0.073,
                    }
                ]
            },
        }
        bridge_result = {
            "status": "ok",
            "payload": {
                "lattice": landed_model["lattice"],
                "normalized_model": landed_model,
                "bonds": [
                    {
                        "source": 0,
                        "target": 0,
                        "vector": [1, -1, 1],
                        "distance": 9.736622,
                        "matrix": [
                            [0.068, 0.0, 0.0],
                            [0.0, 0.068, 0.0],
                            [0.0, 0.0, 0.073],
                        ],
                        "family": "2a'",
                    }
                ],
                "classical": {"method": "auto"},
                "bridge_metadata": {
                    "bridge_kind": "document_reader_spin_only_minimal",
                    "selected_family": "2a'",
                    "block_type": "xxz_exchange",
                    "shell_index": 6,
                },
            },
        }
        solver_result = {
            "classical": {"chosen_method": "luttinger-tisza"},
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "method": "spin-only-luttinger-tisza",
                "ordering": {"q_vector": [0.0, 0.0, 0.5]},
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "cli.run_document_reader_pipeline.run_agent_document_normalization_orchestrator",
                return_value=orchestration_result,
            ):
                with patch(
                    "cli.run_document_reader_pipeline.run_simplification_from_normalized_model",
                    return_value=simplification_result,
                ):
                    with patch(
                        "cli.run_document_reader_pipeline.build_spin_only_solver_payload",
                        return_value=bridge_result,
                    ):
                        with patch(
                            "cli.run_document_reader_pipeline.run_classical_solver",
                            return_value=solver_result,
                        ):
                            result = run_document_reader_pipeline(
                                self.fei2_fixture,
                                source_path=str(self.FEI2_FIXTURE_PATH),
                                selected_model_candidate="effective",
                                selected_local_bond_family="2a'",
                                selected_coordinate_convention="global_crystallographic",
                                output_dir=tmpdir,
                                agent_command=self._mock_fei2_agent_command(),
                                emit_spin_only_solver_payload=True,
                                run_spin_only_classical_solver=True,
                            )

            output_dir = Path(tmpdir)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["bridge_status"], "ok")
            self.assertEqual(
                result["bridge_payload"]["bridge_metadata"]["selected_family"],
                "2a'",
            )
            self.assertEqual(
                result["classical_solver"]["classical_state_result"]["ordering"]["q_vector"],
                [0.0, 0.0, 0.5],
            )
            self.assertTrue((output_dir / "classical" / "solver_payload.json").exists())
            self.assertTrue((output_dir / "classical" / "solver_result.json").exists())

    def test_document_reader_pipeline_writes_downstream_artifacts_when_v2b_is_enabled(self):
        landed_model = {
            "selected_model_candidate": "effective",
            "selected_local_bond_family": "2a'",
            "selected_coordinate_convention": "global_crystallographic",
            "local_hilbert": {"dimension": 3},
            "lattice": {
                "kind": "trigonal",
                "dimension": 3,
                "cell_parameters": {
                    "a": 4.05012,
                    "b": 4.05012,
                    "c": 6.75214,
                    "alpha": 90.0,
                    "beta": 90.0,
                    "gamma": 120.0,
                },
                "positions": [[0.0, 0.0, 0.0]],
                "family_shell_map": {"2a'": {"shell_index": 6, "distance": 9.736622}},
            },
            "unsupported_features": [],
        }
        orchestration_result = {"status": "ok", "normalized_model": landed_model}
        simplification_result = {
            "status": "ok",
            "stage": "complete",
            "normalized_model": landed_model,
            "effective_model": {
                "main": [
                    {
                        "type": "xxz_exchange",
                        "family": "2a'",
                        "coefficient_xy": 0.068,
                        "coefficient_z": 0.073,
                    }
                ]
            },
        }
        bridge_result = {
            "status": "ok",
            "payload": {
                "lattice": landed_model["lattice"],
                "normalized_model": landed_model,
                "bonds": [
                    {
                        "source": 0,
                        "target": 0,
                        "vector": [1, -1, 1],
                        "distance": 9.736622,
                        "matrix": [
                            [0.068, 0.0, 0.0],
                            [0.0, 0.068, 0.0],
                            [0.0, 0.0, 0.073],
                        ],
                        "family": "2a'",
                    }
                ],
                "classical": {"method": "auto"},
                "bridge_metadata": {"bridge_kind": "document_reader_spin_only_shell_expanded"},
            },
        }
        solver_result = {
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "method": "spin-only-luttinger-tisza",
                "ordering": {"q_vector": [0.0, 0.0, 0.5]},
            }
        }
        downstream_result = {
            "downstream_status": "partial",
            "downstream_routes": {
                "lswt": {"status": "ready"},
                "gswt": {"status": "blocked"},
                "thermodynamics": {"status": "review"},
            },
            "downstream_results": {"lswt": {"status": "ok"}},
            "downstream_summary": {
                "lswt": {"execution_decision": "executed"},
                "gswt": {"execution_decision": "blocked_route"},
                "thermodynamics": {"execution_decision": "skipped_review"},
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "cli.run_document_reader_pipeline.run_agent_document_normalization_orchestrator",
                return_value=orchestration_result,
            ):
                with patch(
                    "cli.run_document_reader_pipeline.run_simplification_from_normalized_model",
                    return_value=simplification_result,
                ):
                    with patch(
                        "cli.run_document_reader_pipeline.build_spin_only_solver_payload",
                        return_value=bridge_result,
                    ):
                        with patch(
                            "cli.run_document_reader_pipeline.run_classical_solver",
                            return_value=solver_result,
                        ):
                            with patch(
                                "cli.run_document_reader_pipeline.orchestrate_document_reader_downstream",
                                return_value=downstream_result,
                                create=True,
                            ):
                                result = run_document_reader_pipeline(
                                    self.fei2_fixture,
                                    source_path=str(self.FEI2_FIXTURE_PATH),
                                    selected_model_candidate="effective",
                                    selected_local_bond_family="2a'",
                                    selected_coordinate_convention="global_crystallographic",
                                    output_dir=tmpdir,
                                    agent_command=self._mock_fei2_agent_command(),
                                    emit_spin_only_solver_payload=True,
                                    run_spin_only_classical_solver=True,
                                    run_downstream_stages=True,
                                )

            output_dir = Path(tmpdir)
            self.assertEqual(result["downstream_status"], "partial")
            self.assertTrue((output_dir / "classical" / "downstream_routes.json").exists())
            self.assertTrue((output_dir / "classical" / "downstream_results.json").exists())
            self.assertTrue((output_dir / "classical" / "downstream_summary.json").exists())

    def test_document_reader_pipeline_preserves_classical_success_when_downstream_stage_errors(self):
        landed_model = {
            "selected_model_candidate": "effective",
            "selected_local_bond_family": "2a'",
            "selected_coordinate_convention": "global_crystallographic",
            "local_hilbert": {"dimension": 3},
            "lattice": {
                "kind": "trigonal",
                "dimension": 3,
                "cell_parameters": {
                    "a": 4.05012,
                    "b": 4.05012,
                    "c": 6.75214,
                    "alpha": 90.0,
                    "beta": 90.0,
                    "gamma": 120.0,
                },
                "positions": [[0.0, 0.0, 0.0]],
                "family_shell_map": {"2a'": {"shell_index": 6, "distance": 9.736622}},
            },
            "unsupported_features": [],
        }
        orchestration_result = {"status": "ok", "normalized_model": landed_model}
        simplification_result = {
            "status": "ok",
            "stage": "complete",
            "normalized_model": landed_model,
            "effective_model": {
                "main": [
                    {
                        "type": "xxz_exchange",
                        "family": "2a'",
                        "coefficient_xy": 0.068,
                        "coefficient_z": 0.073,
                    }
                ]
            },
        }
        bridge_result = {
            "status": "ok",
            "payload": {
                "lattice": landed_model["lattice"],
                "normalized_model": landed_model,
                "bonds": [],
                "classical": {"method": "auto"},
                "bridge_metadata": {"bridge_kind": "document_reader_spin_only_shell_expanded"},
            },
        }
        solver_result = {
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "method": "spin-only-luttinger-tisza",
                "ordering": {"q_vector": [0.0, 0.0, 0.5]},
            }
        }
        downstream_result = {
            "downstream_status": "error",
            "downstream_routes": {"lswt": {"status": "ready"}},
            "downstream_results": {"lswt": {"status": "error", "message": "boom"}},
            "downstream_summary": {"lswt": {"execution_decision": "error"}},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "cli.run_document_reader_pipeline.run_agent_document_normalization_orchestrator",
                return_value=orchestration_result,
            ):
                with patch(
                    "cli.run_document_reader_pipeline.run_simplification_from_normalized_model",
                    return_value=simplification_result,
                ):
                    with patch(
                        "cli.run_document_reader_pipeline.build_spin_only_solver_payload",
                        return_value=bridge_result,
                    ):
                        with patch(
                            "cli.run_document_reader_pipeline.run_classical_solver",
                            return_value=solver_result,
                        ):
                            with patch(
                                "cli.run_document_reader_pipeline.orchestrate_document_reader_downstream",
                                return_value=downstream_result,
                                create=True,
                            ):
                                result = run_document_reader_pipeline(
                                    self.fei2_fixture,
                                    source_path=str(self.FEI2_FIXTURE_PATH),
                                    selected_model_candidate="effective",
                                    selected_local_bond_family="2a'",
                                    selected_coordinate_convention="global_crystallographic",
                                    output_dir=tmpdir,
                                    agent_command=self._mock_fei2_agent_command(),
                                    emit_spin_only_solver_payload=True,
                                    run_spin_only_classical_solver=True,
                                    run_downstream_stages=True,
                                )

        self.assertEqual(result["classical_solver"]["classical_state_result"]["status"], "ok")
        self.assertEqual(result["downstream_results"]["lswt"]["status"], "error")

    def test_document_reader_pipeline_records_route_only_downstream_outcomes(self):
        landed_model = {
            "selected_model_candidate": "effective",
            "selected_local_bond_family": "2a'",
            "selected_coordinate_convention": "global_crystallographic",
            "local_hilbert": {"dimension": 3},
            "lattice": {
                "kind": "trigonal",
                "dimension": 3,
                "cell_parameters": {
                    "a": 4.05012,
                    "b": 4.05012,
                    "c": 6.75214,
                    "alpha": 90.0,
                    "beta": 90.0,
                    "gamma": 120.0,
                },
                "positions": [[0.0, 0.0, 0.0]],
                "family_shell_map": {"2a'": {"shell_index": 6, "distance": 9.736622}},
            },
            "unsupported_features": [],
        }
        orchestration_result = {"status": "ok", "normalized_model": landed_model}
        simplification_result = {
            "status": "ok",
            "stage": "complete",
            "normalized_model": landed_model,
            "effective_model": {
                "main": [
                    {
                        "type": "xxz_exchange",
                        "family": "2a'",
                        "coefficient_xy": 0.068,
                        "coefficient_z": 0.073,
                    }
                ]
            },
        }
        bridge_result = {
            "status": "ok",
            "payload": {
                "lattice": landed_model["lattice"],
                "normalized_model": landed_model,
                "bonds": [],
                "classical": {"method": "auto"},
                "bridge_metadata": {"bridge_kind": "document_reader_spin_only_shell_expanded"},
            },
        }
        solver_result = {
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "method": "spin-only-luttinger-tisza",
                "ordering": {"q_vector": [0.0, 0.0, 0.5]},
            }
        }
        downstream_result = {
            "downstream_status": "blocked",
            "downstream_routes": {
                "lswt": {"status": "blocked"},
                "gswt": {"status": "blocked"},
                "thermodynamics": {"status": "review"},
            },
            "downstream_results": {},
            "downstream_summary": {
                "lswt": {"execution_decision": "blocked_route"},
                "gswt": {"execution_decision": "blocked_route"},
                "thermodynamics": {"execution_decision": "skipped_review"},
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "cli.run_document_reader_pipeline.run_agent_document_normalization_orchestrator",
                return_value=orchestration_result,
            ):
                with patch(
                    "cli.run_document_reader_pipeline.run_simplification_from_normalized_model",
                    return_value=simplification_result,
                ):
                    with patch(
                        "cli.run_document_reader_pipeline.build_spin_only_solver_payload",
                        return_value=bridge_result,
                    ):
                        with patch(
                            "cli.run_document_reader_pipeline.run_classical_solver",
                            return_value=solver_result,
                        ):
                            with patch(
                                "cli.run_document_reader_pipeline.orchestrate_document_reader_downstream",
                                return_value=downstream_result,
                                create=True,
                            ):
                                result = run_document_reader_pipeline(
                                    self.fei2_fixture,
                                    source_path=str(self.FEI2_FIXTURE_PATH),
                                    selected_model_candidate="effective",
                                    selected_local_bond_family="2a'",
                                    selected_coordinate_convention="global_crystallographic",
                                    output_dir=tmpdir,
                                    agent_command=self._mock_fei2_agent_command(),
                                    emit_spin_only_solver_payload=True,
                                    run_spin_only_classical_solver=True,
                                    run_downstream_stages=True,
                                )

        self.assertEqual(result["downstream_routes"]["gswt"]["status"], "blocked")
        self.assertEqual(result["downstream_routes"]["thermodynamics"]["status"], "review")
        self.assertEqual(result["downstream_results"], {})


if __name__ == "__main__":
    unittest.main()
