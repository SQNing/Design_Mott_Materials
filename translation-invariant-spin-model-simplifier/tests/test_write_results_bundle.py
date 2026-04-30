import sys
import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from cli import write_results_bundle
from common.classical_state_result import build_final_classical_state_result


def _minimal_refined_bundle_payload():
    classical_state = {
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
    payload = {
        "normalized_model": {"local_hilbert": {"dimension": 2}},
        "simplification": {"candidates": [{"name": "toy"}], "recommended": 0},
        "canonical_model": {},
        "effective_model": {"main": [], "low_weight": [], "residual": []},
        "fidelity": {
            "reconstruction_error": 0.0,
            "main_fraction": 1.0,
            "low_weight_fraction": 0.0,
            "residual_fraction": 0.0,
            "risk_notes": [],
        },
        "projection": {"status": "cpn_pair_model"},
        "classical_state_result": {
            "status": "ok",
            "role": "final",
            "solver_family": "retained_local_multiplet",
            "method": "pseudospin-sun-gswt-cpn",
            "selected_classical_branch": "magnetic-supercell-refined",
            "downstream_compatibility": {
                "lswt": {"status": "blocked", "reason": "requires-spin-frame-site-frames"},
                "gswt": {"status": "ready"},
                "thermodynamics": {"status": "ready"},
            },
            "classical_state": classical_state,
            "diagnostics": {
                "magnetic_supercell_refinement": {
                    "accepted": True,
                    "acceptance_backend": "sunny",
                    "trigger_q": [0.75, 0.25, 0.75],
                    "candidate_matrix": [[0, 3, -1], [1, -3, 0], [0, 4, 0]],
                    "energy_before_per_site": -2.782712359221584,
                    "energy_after_python_per_site": -2.9163427233459576,
                    "energy_after_sunny_per_site": -3.0184994995404986,
                    "energy_gain_per_site": 0.13363036412437346,
                    "candidates": [
                        {
                            "accepted": False,
                            "trigger_q": [0.25, 0.75, 0.25],
                            "energy_after_python_per_site": -2.7710803677952422,
                        },
                        {
                            "accepted": True,
                            "trigger_q": [0.75, 0.25, 0.75],
                            "energy_after_python_per_site": -2.9163427233459576,
                        },
                    ],
                }
            },
        },
    }
    return payload


class WriteResultsBundleTests(unittest.TestCase):
    def test_has_classical_state_accepts_standardized_result_wrapper(self):
        payload = {
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "classical_state": {
                    "site_frames": [
                        {
                            "site": 0,
                            "spin_length": 0.5,
                            "direction": [0.0, 0.0, 1.0],
                        }
                    ]
                },
            }
        }

        self.assertEqual(write_results_bundle._has_classical_state(payload), True)

    def test_has_classical_state_stays_contract_first_when_raw_mirror_is_empty(self):
        payload = {
            "classical_state": {},
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "classical_state": {
                    "site_frames": [
                        {
                            "site": 0,
                            "spin_length": 0.5,
                            "direction": [0.0, 0.0, 1.0],
                        }
                    ]
                },
            },
        }

        self.assertEqual(write_results_bundle._has_classical_state(payload), True)

    def test_has_classical_state_preserves_nested_legacy_fallback_when_top_level_mirror_is_empty(self):
        payload = {
            "classical_state": {},
            "classical": {
                "classical_state": {
                    "site_frames": [
                        {
                            "site": 0,
                            "spin_length": 0.5,
                            "direction": [0.0, 0.0, 1.0],
                        }
                    ]
                }
            },
        }

        self.assertEqual(write_results_bundle._has_classical_state(payload), True)

    def test_has_classical_state_preserves_top_level_legacy_state_when_nested_mirror_is_empty(self):
        payload = {
            "classical_state": {
                "site_frames": [
                    {
                        "site": 0,
                        "spin_length": 0.5,
                        "direction": [0.0, 0.0, 1.0],
                    }
                ]
            },
            "classical": {"classical_state": {}},
        }

        self.assertEqual(write_results_bundle._has_classical_state(payload), True)

    def test_can_run_lswt_accepts_standardized_ready_contract(self):
        payload = {
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "classical_state": {
                    "site_frames": [
                        {
                            "site": 0,
                            "spin_length": 0.5,
                            "direction": [0.0, 0.0, 1.0],
                        }
                    ]
                },
                "downstream_compatibility": {
                    "lswt": {"status": "ready"},
                    "gswt": {"status": "blocked", "reason": "requires-local-ray-cpn-state"},
                    "thermodynamics": {"status": "review", "reason": "requires-caller-confirmed-support"},
                },
            }
        }

        self.assertEqual(write_results_bundle._can_run_lswt(payload), True)

    def test_can_run_lswt_preserves_top_level_spin_frame_precedence_for_mixed_legacy_payloads(self):
        payload = {
            "classical_state": {
                "site_frames": [
                    {
                        "site": 0,
                        "spin_length": 0.5,
                        "direction": [0.0, 0.0, 1.0],
                    }
                ]
            },
            "classical": {
                "classical_state": {
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "supercell_shape": [1, 1, 1],
                    "local_rays": [
                        {
                            "cell": [0, 0, 0],
                            "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}],
                        }
                    ],
                }
            },
        }

        self.assertEqual(write_results_bundle._can_run_lswt(payload), True)

    def test_can_run_gswt_rejects_blocked_standardized_contract(self):
        payload = {
            "gswt_payload": {"payload_kind": "python_glswt_local_rays"},
            "classical_state_result": {
                "status": "ok",
                "role": "diagnostic",
                "downstream_compatibility": {
                    "lswt": {"status": "blocked", "reason": "diagnostic-seed-method"},
                    "gswt": {"status": "blocked", "reason": "diagnostic-seed-method"},
                    "thermodynamics": {"status": "blocked", "reason": "diagnostic-seed-method"},
                },
            },
        }

        self.assertEqual(write_results_bundle._can_run_gswt(payload), False)

    def test_can_run_thermodynamics_rejects_blocked_standardized_contract(self):
        payload = {
            "bonds": [
                {
                    "source": 0,
                    "target": 0,
                    "vector": [0.0, 0.0, 0.0],
                    "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                }
            ],
            "thermodynamics": {"temperatures": [0.1, 0.2]},
            "classical_state_result": {
                "status": "ok",
                "role": "diagnostic",
                "downstream_compatibility": {
                    "lswt": {"status": "blocked", "reason": "diagnostic-seed-method"},
                    "gswt": {"status": "blocked", "reason": "diagnostic-seed-method"},
                    "thermodynamics": {"status": "blocked", "reason": "diagnostic-seed-method"},
                },
            },
        }

        self.assertEqual(write_results_bundle._can_run_thermodynamics(payload), False)

    def test_stage_summary_prefers_standardized_classical_metadata(self):
        bundle_payload = {
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "solver_family": "retained_local_multiplet",
                "method": "pseudospin-cpn-local-ray-minimize",
                "downstream_compatibility": {
                    "lswt": {"status": "blocked", "reason": "requires-spin-frame-site-frames"},
                    "gswt": {"status": "ready"},
                    "thermodynamics": {"status": "ready"},
                },
                "classical_state": {
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "supercell_shape": [1, 1, 1],
                    "local_rays": [
                        {
                            "cell": [0, 0, 0],
                            "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}],
                        }
                    ],
                },
            }
        }

        summary = write_results_bundle._stage_summary(
            {},
            bundle_payload,
            run_missing_classical=True,
            run_missing_thermodynamics=True,
            run_missing_gswt=True,
            run_missing_lswt=True,
        )

        self.assertEqual(summary["classical"]["present"], True)
        self.assertEqual(summary["classical"]["method"], "pseudospin-cpn-local-ray-minimize")
        self.assertEqual(summary["classical"]["role"], "final")
        self.assertEqual(summary["classical"]["solver_family"], "retained_local_multiplet")
        self.assertEqual(summary["classical"]["downstream_compatibility"]["gswt"]["status"], "ready")

    def test_stage_summary_accepts_bare_standardized_contract_payload(self):
        classical_state = {
            "site_frames": [
                {
                    "site": 0,
                    "spin_length": 0.5,
                    "direction": [0.0, 0.0, 1.0],
                }
            ]
        }
        bundle_payload = build_final_classical_state_result(classical_state)
        bundle_payload["method"] = "spin-only-variational"
        bundle_payload["solver_family"] = "spin_only_explicit"

        summary = write_results_bundle._stage_summary(
            {},
            bundle_payload,
            run_missing_classical=False,
            run_missing_thermodynamics=False,
            run_missing_gswt=False,
            run_missing_lswt=False,
        )

        self.assertEqual(summary["classical"]["method"], "spin-only-variational")
        self.assertEqual(summary["classical"]["role"], "final")

    def test_stage_summary_preserves_compatibility_method_mirrors_from_original_payload(self):
        classical_state = {
            "site_frames": [
                {
                    "site": 0,
                    "spin_length": 0.5,
                    "direction": [0.0, 0.0, 1.0],
                }
            ]
        }
        original_payload = {
            "classical": {
                "chosen_method": "legacy-method",
                "requested_method": "auto",
            }
        }
        bundle_payload = build_final_classical_state_result(classical_state)
        bundle_payload["method"] = "spin-only-variational"
        bundle_payload["solver_family"] = "spin_only_explicit"

        summary = write_results_bundle._stage_summary(
            original_payload,
            bundle_payload,
            run_missing_classical=False,
            run_missing_thermodynamics=False,
            run_missing_gswt=False,
            run_missing_lswt=False,
        )

        self.assertEqual(summary["classical"]["chosen_method"], "legacy-method")
        self.assertEqual(summary["classical"]["requested_method"], "auto")
        self.assertEqual(summary["classical"]["method"], "spin-only-variational")

    def test_stage_summary_treats_nested_shim_metadata_as_compatibility_only(self):
        bundle_payload = {
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "solver_family": "retained_local_multiplet",
                "method": "pseudospin-cpn-local-ray-minimize",
                "downstream_compatibility": {
                    "lswt": {"status": "blocked", "reason": "requires-spin-frame-site-frames"},
                    "gswt": {"status": "ready"},
                    "thermodynamics": {"status": "ready"},
                },
                "classical_state": {
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "supercell_shape": [1, 1, 1],
                    "local_rays": [
                        {
                            "cell": [0, 0, 0],
                            "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}],
                        }
                    ],
                },
            },
            "classical": {
                "chosen_method": "legacy-method",
                "requested_method": "auto",
                "classical_state_result": {
                    "status": "ok",
                    "role": "diagnostic",
                    "solver_family": "legacy-nested",
                    "method": "nested-legacy-method",
                },
            },
        }

        summary = write_results_bundle._stage_summary(
            {},
            bundle_payload,
            run_missing_classical=False,
            run_missing_thermodynamics=False,
            run_missing_gswt=False,
            run_missing_lswt=False,
        )

        self.assertEqual(summary["classical"]["chosen_method"], "legacy-method")
        self.assertEqual(summary["classical"]["requested_method"], "auto")
        self.assertEqual(summary["classical"]["method"], "pseudospin-cpn-local-ray-minimize")
        self.assertEqual(summary["classical"]["role"], "final")
        self.assertEqual(summary["classical"]["solver_family"], "retained_local_multiplet")

    def test_stage_summary_reports_ready_gswt_for_promoted_pseudospin_glt(self):
        bundle_payload = {
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "solver_family": "retained_local_multiplet",
                "method": "pseudospin-cpn-generalized-lt",
                "downstream_compatibility": {
                    "lswt": {"status": "blocked", "reason": "requires-spin-frame-site-frames"},
                    "gswt": {"status": "ready"},
                    "thermodynamics": {"status": "ready"},
                },
                "classical_state": {
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "supercell_shape": [1, 1, 1],
                    "local_rays": [
                        {
                            "cell": [0, 0, 0],
                            "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}],
                        }
                    ],
                },
            },
        }

        summary = write_results_bundle._stage_summary(
            {},
            bundle_payload,
            run_missing_classical=True,
            run_missing_thermodynamics=True,
            run_missing_gswt=True,
            run_missing_lswt=True,
        )

        self.assertEqual(summary["classical"]["method"], "pseudospin-cpn-generalized-lt")
        self.assertEqual(summary["classical"]["role"], "final")
        self.assertEqual(summary["classical"]["downstream_compatibility"]["gswt"]["status"], "ready")

    def test_stage_summary_exports_selected_refined_branch_and_magnetic_supercell_refinement_summary(self):
        bundle_payload = _minimal_refined_bundle_payload()

        summary = write_results_bundle._stage_summary(
            {},
            bundle_payload,
            run_missing_classical=False,
            run_missing_thermodynamics=False,
            run_missing_gswt=False,
            run_missing_lswt=False,
        )

        self.assertEqual(summary["classical"]["selected_classical_branch"], "magnetic-supercell-refined")
        refinement = summary["classical"]["magnetic_supercell_refinement"]
        self.assertEqual(refinement["accepted"], True)
        self.assertEqual(refinement["acceptance_backend"], "sunny")
        self.assertEqual(refinement["trigger_q"], [0.75, 0.25, 0.75])
        self.assertEqual(refinement["candidate_matrix"], [[0, 3, -1], [1, -3, 0], [0, 4, 0]])
        self.assertEqual(refinement["energy_after_python_per_site"], -2.9163427233459576)
        self.assertEqual(refinement["energy_after_sunny_per_site"], -3.0184994995404986)
        self.assertEqual(refinement["candidate_count"], 2)

    def test_write_results_bundle_renders_magnetic_supercell_refinement_section_in_report(self):
        payload = _minimal_refined_bundle_payload()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            with patch.object(
                write_results_bundle,
                "render_plots",
                return_value={"status": "ok", "plots": {}},
            ):
                manifest = write_results_bundle.write_results_bundle(
                    payload,
                    output_dir=output_dir,
                    run_missing_classical=False,
                    run_missing_thermodynamics=False,
                    run_missing_gswt=False,
                    run_missing_lswt=False,
                )

            bundle_manifest = json.loads((output_dir / "bundle_manifest.json").read_text(encoding="utf-8"))
            report_text = (output_dir / "report.txt").read_text(encoding="utf-8")

        self.assertEqual(manifest["status"], "ok")
        self.assertEqual(
            bundle_manifest["stages"]["classical"]["selected_classical_branch"],
            "magnetic-supercell-refined",
        )
        self.assertIn("Magnetic supercell refinement:", report_text)
        self.assertIn("selected_classical_branch=magnetic-supercell-refined", report_text)
        self.assertIn("accepted=True", report_text)
        self.assertIn("trigger_q=[0.75, 0.25, 0.75]", report_text)
        self.assertIn("candidate_matrix=[[0, 3, -1], [1, -3, 0], [0, 4, 0]]", report_text)
        self.assertIn("energy_before_per_site=-2.7827124", report_text)
        self.assertIn("energy_after_python_per_site=-2.9163427", report_text)
        self.assertIn("energy_after_sunny_per_site=-3.0184995", report_text)

    def test_populate_missing_results_routes_gswt_through_shared_execution(self):
        payload = {
            "gswt_payload": {"payload_kind": "python_glswt_local_rays"},
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "downstream_compatibility": {
                    "lswt": {"status": "blocked", "reason": "requires-spin-frame-site-frames"},
                    "gswt": {"status": "ready", "recommended_backend": "python_glswt"},
                    "thermodynamics": {"status": "blocked", "reason": "missing-thermodynamics-inputs"},
                },
                "classical_state": {
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "supercell_shape": [1, 1, 1],
                    "local_rays": [
                        {
                            "cell": [0, 0, 0],
                            "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}],
                        }
                    ],
                },
            },
        }

        with (
            patch.object(
                write_results_bundle,
                "execute_downstream_stage",
                create=True,
                return_value={"status": "ok", "backend": {"name": "python-glswt"}},
            ) as execute_stage,
            patch.object(write_results_bundle, "run_python_glswt_driver", return_value={"status": "legacy-python"}) as python_runner,
            patch.object(write_results_bundle, "run_sun_gswt", return_value={"status": "legacy-sunny"}) as sunny_runner,
        ):
            result = write_results_bundle._populate_missing_results(
                payload,
                run_missing_classical=False,
                run_missing_thermodynamics=False,
                run_missing_gswt=True,
                run_missing_lswt=False,
            )

        self.assertEqual(result["gswt"]["status"], "ok")
        self.assertEqual(execute_stage.call_args[0][1], "gswt")
        self.assertEqual(python_runner.called, False)
        self.assertEqual(sunny_runner.called, False)

    def test_populate_missing_results_routes_thermodynamics_through_shared_execution(self):
        payload = {
            "bonds": [
                {
                    "source": 0,
                    "target": 0,
                    "vector": [0.0, 0.0, 0.0],
                    "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                }
            ],
            "thermodynamics": {
                "temperatures": [0.1, 0.2],
                "backend_method": "sunny-local-sampler",
            },
            "thermodynamics_payload": {
                "payload_kind": "sunny_sun_thermodynamics",
                "backend_method": "sunny-local-sampler",
            },
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "downstream_compatibility": {
                    "lswt": {"status": "blocked", "reason": "requires-spin-frame-site-frames"},
                    "gswt": {"status": "blocked", "reason": "missing-gswt-payload"},
                    "thermodynamics": {"status": "ready", "recommended_backend": "sunny_thermodynamics"},
                },
                "classical_state": {
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "supercell_shape": [1, 1, 1],
                    "local_rays": [
                        {
                            "cell": [0, 0, 0],
                            "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}],
                        }
                    ],
                },
            },
        }

        with (
            patch.object(
                write_results_bundle,
                "execute_downstream_stage",
                create=True,
                return_value={
                    "status": "ok",
                    "configuration": {"backend_method": "sunny-local-sampler"},
                    "grid": [{"temperature": 0.1}],
                },
            ) as execute_stage,
            patch.object(write_results_bundle, "estimate_thermodynamics", return_value={"status": "legacy-spin-only"}) as estimate,
        ):
            result = write_results_bundle._populate_missing_results(
                payload,
                run_missing_classical=False,
                run_missing_thermodynamics=True,
                run_missing_gswt=False,
                run_missing_lswt=False,
            )

        self.assertEqual(result["thermodynamics_result"]["status"], "ok")
        self.assertEqual(execute_stage.call_args[0][1], "thermodynamics")
        self.assertEqual(estimate.called, False)

    def test_populate_missing_results_routes_lswt_through_shared_execution(self):
        payload = {
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "downstream_compatibility": {
                    "lswt": {"status": "ready", "recommended_backend": "linear_spin_wave"},
                    "gswt": {"status": "blocked", "reason": "requires-local-ray-cpn-state"},
                    "thermodynamics": {"status": "review", "reason": "requires-caller-confirmed-support"},
                },
                "classical_state": {
                    "site_frames": [
                        {
                            "site": 0,
                            "spin_length": 0.5,
                            "direction": [0.0, 0.0, 1.0],
                        }
                    ]
                },
            }
        }

        with (
            patch.object(
                write_results_bundle,
                "execute_downstream_stage",
                create=True,
                return_value={"status": "ok", "backend": {"name": "SpinW"}},
            ) as execute_stage,
            patch.object(write_results_bundle, "run_linear_spin_wave", return_value={"status": "legacy-lswt"}) as lswt_runner,
        ):
            result = write_results_bundle._populate_missing_results(
                payload,
                run_missing_classical=False,
                run_missing_thermodynamics=False,
                run_missing_gswt=False,
                run_missing_lswt=True,
            )

        self.assertEqual(result["lswt"]["status"], "ok")
        self.assertEqual(execute_stage.call_args[0][1], "lswt")
        self.assertEqual(lswt_runner.called, False)

    def test_populate_missing_results_skips_blocked_gswt_and_thermodynamics(self):
        payload = {
            "bonds": [
                {
                    "source": 0,
                    "target": 0,
                    "vector": [0.0, 0.0, 0.0],
                    "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                }
            ],
            "thermodynamics": {"temperatures": [0.1, 0.2]},
            "gswt_payload": {"payload_kind": "python_glswt_local_rays"},
            "classical_state_result": {
                "status": "ok",
                "role": "diagnostic",
                "downstream_compatibility": {
                    "lswt": {"status": "blocked", "reason": "diagnostic-seed-method"},
                    "gswt": {"status": "blocked", "reason": "diagnostic-seed-method"},
                    "thermodynamics": {"status": "blocked", "reason": "diagnostic-seed-method"},
                },
            },
        }

        with (
            patch.object(write_results_bundle, "_run_gswt_stage") as run_gswt_stage,
            patch.object(write_results_bundle, "_run_thermodynamics_stage") as run_thermodynamics_stage,
        ):
            result = write_results_bundle._populate_missing_results(
                payload,
                run_missing_classical=False,
                run_missing_thermodynamics=True,
                run_missing_gswt=True,
                run_missing_lswt=False,
            )

        self.assertEqual(result["classical_state_result"]["role"], "diagnostic")
        self.assertEqual(run_gswt_stage.called, False)
        self.assertEqual(run_thermodynamics_stage.called, False)

    def test_populate_missing_results_allows_promoted_final_cpn_glt_result(self):
        payload = {
            "bonds": [
                {
                    "source": 0,
                    "target": 0,
                    "vector": [0.0, 0.0, 0.0],
                    "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                }
            ],
            "thermodynamics": {"temperatures": [0.1, 0.2]},
            "gswt_payload": {"payload_kind": "python_glswt_local_rays"},
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "solver_family": "retained_local_multiplet",
                "method": "pseudospin-cpn-generalized-lt",
                "downstream_compatibility": {
                    "lswt": {"status": "blocked", "reason": "requires-spin-frame-site-frames"},
                    "gswt": {"status": "ready"},
                    "thermodynamics": {"status": "ready"},
                },
            },
        }

        with (
            patch.object(
                write_results_bundle,
                "_run_gswt_stage",
                side_effect=lambda bundle: {**bundle, "gswt": {"status": "ok"}},
            ) as run_gswt_stage,
            patch.object(
                write_results_bundle,
                "_run_thermodynamics_stage",
                side_effect=lambda bundle: {**bundle, "thermodynamics_result": {"status": "ok"}},
            ) as run_thermodynamics_stage,
        ):
            result = write_results_bundle._populate_missing_results(
                payload,
                run_missing_classical=False,
                run_missing_thermodynamics=True,
                run_missing_gswt=True,
                run_missing_lswt=False,
            )

        self.assertEqual(result["classical_state_result"]["method"], "pseudospin-cpn-generalized-lt")
        self.assertEqual(run_gswt_stage.called, True)
        self.assertEqual(run_thermodynamics_stage.called, True)


if __name__ == "__main__":
    unittest.main()
