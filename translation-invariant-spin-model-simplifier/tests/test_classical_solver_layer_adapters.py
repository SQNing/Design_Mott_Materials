import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical import classical_solver_driver
from cli import solve_pseudospin_orbital_pipeline


def _spin_only_payload(method, *, sublattices=1):
    return {
        "classical": {"method": method},
        "local_dim": 2,
        "lattice": {"sublattices": sublattices, "dimension": 1},
        "bonds": [
            {
                "source": 0,
                "target": 0,
                "vector": [0.0, 0.0, 0.0],
                "matrix": [
                    [1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.0, 0.0, 1.0],
                ],
            }
        ],
    }


class ClassicalSolverLayerAdapterTests(unittest.TestCase):
    def test_spin_only_routing_rejects_unsupported_method_names(self):
        payload = _spin_only_payload("made-up-method")

        with patch.object(
            classical_solver_driver,
            "solve_variational",
            return_value={"method": "variational", "energy": -1.25, "spins": [[0.0, 0.0, 1.0]]},
        ):
            with self.assertRaisesRegex(ValueError, "unsupported classical solver method"):
                classical_solver_driver.run_classical_solver(payload, starts=1, seed=0)

    def test_spin_only_variational_result_includes_normalized_classical_state_result(self):
        payload = _spin_only_payload("variational")

        with patch.object(
            classical_solver_driver,
            "solve_variational",
            return_value={"method": "variational", "energy": -1.25, "spins": [[0.0, 0.0, 1.0]]},
        ):
            result = classical_solver_driver.run_classical_solver(payload, starts=1, seed=0)

        self.assertIn("classical_state_result", result)
        self.assertIn("variational_result", result)
        self.assertIn("classical_state", result)

        standardized = result["classical_state_result"]
        self.assertEqual(standardized["status"], "ok")
        self.assertEqual(standardized["role"], "final")
        self.assertEqual(standardized["solver_family"], "spin_only_explicit")
        self.assertEqual(standardized["method"], "spin-only-variational")
        self.assertEqual(standardized["energy"], -1.25)
        self.assertEqual(standardized["classical_state"], result["classical_state"])
        self.assertEqual(standardized["ordering"], result["classical_state"]["ordering"])
        self.assertEqual(standardized["downstream_compatibility"]["lswt"]["status"], "ready")
        self.assertEqual(standardized["downstream_compatibility"]["gswt"]["status"], "blocked")

    def test_spin_only_luttinger_tisza_result_normalizes_ordering_energy_and_compatibility(self):
        payload = _spin_only_payload("luttinger-tisza")
        recovered_state = {
            "site_frames": [
                {
                    "site": 0,
                    "spin_length": 0.5,
                    "direction": [1.0, 0.0, 0.0],
                }
            ],
            "ordering": {
                "kind": "single-q",
                "q_vector": [0.5, 0.0, 0.0],
                "supercell_shape": [2, 1, 1],
            },
            "constraint_recovery": {"strong_constraint_residual": 0.0},
        }

        with (
            patch.object(
                classical_solver_driver,
                "find_lt_ground_state",
                return_value={
                    "q": [0.5, 0.0, 0.0],
                    "lowest_eigenvalue": -2.0,
                    "eigenvector": [{"real": 1.0, "imag": 0.0}],
                },
            ),
            patch.object(
                classical_solver_driver,
                "recover_classical_state_from_lt",
                return_value=recovered_state,
            ),
            patch.object(
                classical_solver_driver,
                "solve_variational",
                return_value={"method": "variational", "energy": -1.0, "spins": [[0.0, 0.0, 1.0]]},
            ),
        ):
            result = classical_solver_driver.run_classical_solver(payload, starts=1, seed=0)

        standardized = result["classical_state_result"]
        self.assertEqual(standardized["role"], "final")
        self.assertEqual(standardized["solver_family"], "spin_only_explicit")
        self.assertEqual(standardized["method"], "spin-only-luttinger-tisza")
        self.assertEqual(standardized["ordering"], recovered_state["ordering"])
        self.assertEqual(standardized["energy"], -2.0)
        self.assertEqual(standardized["supercell_shape"], [2, 1, 1])
        self.assertEqual(standardized["downstream_compatibility"]["lswt"]["status"], "ready")
        self.assertEqual(standardized["downstream_compatibility"]["gswt"]["status"], "blocked")
        self.assertEqual(standardized["downstream_compatibility"]["thermodynamics"]["status"], "review")
        self.assertIn("lt_result", result)

    def test_spin_only_generalized_lt_result_uses_generalized_method_mapping(self):
        payload = _spin_only_payload("generalized-lt", sublattices=2)
        lt_recovered_state = {
            "site_frames": [
                {
                    "site": 0,
                    "spin_length": 0.5,
                    "direction": [1.0, 0.0, 0.0],
                }
            ],
            "ordering": {
                "kind": "single-q",
                "q_vector": [0.25, 0.25, 0.0],
                "supercell_shape": [2, 2, 1],
            },
            "constraint_recovery": {
                "status": "requires_variational_polish",
                "strong_constraint_residual": 0.25,
                "max_site_norm_residual": 0.5,
            },
        }
        generalized_recovered_state = {
            "site_frames": [
                {
                    "site": 0,
                    "spin_length": 0.5,
                    "direction": [0.0, 1.0, 0.0],
                }
            ],
            "ordering": {
                "kind": "single-q",
                "q_vector": [0.25, 0.25, 0.0],
                "supercell_shape": [2, 2, 1],
            },
            "constraint_recovery": {
                "status": "completed_from_shell",
                "strong_constraint_residual": 0.0,
                "max_site_norm_residual": 0.0,
            },
        }

        def _recover_side_effect(_payload, q, amplitudes, spin_length=0.5, source="lt"):
            if source == "generalized-lt":
                return copy.deepcopy(generalized_recovered_state)
            return copy.deepcopy(lt_recovered_state)

        with (
            patch.object(
                classical_solver_driver,
                "find_lt_ground_state",
                return_value={
                    "q": [0.25, 0.25, 0.0],
                    "lowest_eigenvalue": -2.2,
                    "eigenvector": [{"real": 1.0, "imag": 0.0}],
                },
            ),
            patch.object(
                classical_solver_driver,
                "find_generalized_lt_ground_state",
                return_value={
                    "q": [0.25, 0.25, 0.0],
                    "tightened_lower_bound": -1.6,
                    "eigenspace": [[{"real": 1.0, "imag": 0.0}]],
                },
            ),
            patch.object(
                classical_solver_driver,
                "recover_classical_state_from_lt",
                side_effect=_recover_side_effect,
            ),
            patch.object(
                classical_solver_driver,
                "solve_variational",
                return_value={"method": "variational", "energy": -1.0, "spins": [[0.0, 0.0, 1.0]]},
            ),
        ):
            result = classical_solver_driver.run_classical_solver(payload, starts=1, seed=0)

        standardized = result["classical_state_result"]
        self.assertEqual(standardized["solver_family"], "spin_only_explicit")
        self.assertEqual(standardized["method"], "spin-only-generalized-lt")
        self.assertEqual(standardized["ordering"], generalized_recovered_state["ordering"])
        self.assertEqual(standardized["energy"], -1.6)
        self.assertIn("generalized_lt_result", result)

    def test_generalized_lt_request_prefers_exact_lt_when_lt_is_already_final(self):
        payload = _spin_only_payload("generalized-lt", sublattices=2)
        exact_lt_state = {
            "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [1.0, 0.0, 0.0]}],
            "ordering": {"kind": "single-q", "q_vector": [0.0, 0.0, 0.0], "supercell_shape": [1, 1, 1]},
            "constraint_recovery": {
                "status": "exact_relaxed_hit",
                "strong_constraint_residual": 0.0,
                "max_site_norm_residual": 0.0,
            },
        }
        inexact_glt_state = {
            "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 1.0, 0.0]}],
            "ordering": {"kind": "single-q", "q_vector": [0.25, 0.0, 0.0], "supercell_shape": [2, 1, 1]},
            "constraint_recovery": {
                "status": "requires_variational_polish",
                "strong_constraint_residual": 0.2,
                "max_site_norm_residual": 0.4,
            },
        }

        def _recover_side_effect(_payload, q, amplitudes, spin_length=0.5, source="lt"):
            if source == "generalized-lt":
                return copy.deepcopy(inexact_glt_state)
            return copy.deepcopy(exact_lt_state)

        with (
            patch.object(
                classical_solver_driver,
                "find_lt_ground_state",
                return_value={
                    "q": [0.0, 0.0, 0.0],
                    "lowest_eigenvalue": -1.8,
                    "eigenvector": [{"real": 1.0, "imag": 0.0}],
                },
            ),
            patch.object(
                classical_solver_driver,
                "find_generalized_lt_ground_state",
                return_value={
                    "q": [0.25, 0.0, 0.0],
                    "tightened_lower_bound": -1.5,
                    "eigenspace": [[{"real": 1.0, "imag": 0.0}]],
                },
            ),
            patch.object(
                classical_solver_driver,
                "recover_classical_state_from_lt",
                side_effect=_recover_side_effect,
            ),
            patch.object(
                classical_solver_driver,
                "solve_variational",
                return_value={"method": "variational", "energy": -1.0, "spins": [[0.0, 0.0, 1.0]]},
            ),
        ):
            result = classical_solver_driver.run_classical_solver(payload, starts=1, seed=0)

        self.assertEqual(result["classical"]["chosen_method"], "luttinger-tisza")
        self.assertEqual(result["classical_state_result"]["method"], "spin-only-luttinger-tisza")
        self.assertEqual(result["classical_state_result"]["energy"], -1.8)

    def test_generalized_lt_request_falls_back_to_variational_when_neither_lt_nor_glt_completes(self):
        payload = _spin_only_payload("generalized-lt", sublattices=2)
        incomplete_state = {
            "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [1.0, 0.0, 0.0]}],
            "ordering": {"kind": "single-q", "q_vector": [0.0, 0.0, 0.0], "supercell_shape": [1, 1, 1]},
            "constraint_recovery": {
                "status": "requires_variational_polish",
                "strong_constraint_residual": 0.2,
                "max_site_norm_residual": 0.4,
            },
        }

        with (
            patch.object(
                classical_solver_driver,
                "find_lt_ground_state",
                return_value={
                    "q": [0.0, 0.0, 0.0],
                    "lowest_eigenvalue": -1.8,
                    "eigenvector": [{"real": 1.0, "imag": 0.0}],
                },
            ),
            patch.object(
                classical_solver_driver,
                "find_generalized_lt_ground_state",
                return_value={
                    "q": [0.25, 0.0, 0.0],
                    "tightened_lower_bound": -1.6,
                    "eigenspace": [[{"real": 1.0, "imag": 0.0}]],
                },
            ),
            patch.object(
                classical_solver_driver,
                "recover_classical_state_from_lt",
                return_value=copy.deepcopy(incomplete_state),
            ),
            patch.object(
                classical_solver_driver,
                "solve_variational",
                return_value={"method": "variational", "energy": -1.0, "spins": [[0.0, 0.0, 1.0]]},
            ),
        ):
            result = classical_solver_driver.run_classical_solver(payload, starts=1, seed=0)

        self.assertEqual(result["classical"]["chosen_method"], "variational")
        self.assertEqual(result["classical_state_result"]["method"], "spin-only-variational")
        self.assertEqual(result["classical_state_result"]["energy"], -1.0)

    def test_pseudospin_local_ray_minimize_adapter_emits_final_classical_state_result(self):
        solver_result = {
            "method": "cpn-local-ray-minimize",
            "energy": -3.5,
            "supercell_shape": [2, 1, 1],
            "classical_state": {
                "state_kind": "local_rays",
                "manifold": "CP^(N-1)",
                "supercell_shape": [2, 1, 1],
                "local_rays": [
                    {
                        "cell": [0, 0, 0],
                        "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}],
                    }
                ],
                "ordering": {
                    "kind": "single-q",
                    "q_vector": [0.5, 0.0, 0.0],
                    "supercell_shape": [2, 1, 1],
                },
            },
        }

        standardized = solve_pseudospin_orbital_pipeline._build_pseudospin_classical_state_result(
            solver_result,
            classical_method="cpn-local-ray-minimize",
            default_supercell_shape=[2, 1, 1],
        )

        self.assertEqual(standardized["role"], "final")
        self.assertEqual(standardized["solver_family"], "retained_local_multiplet")
        self.assertEqual(standardized["method"], "pseudospin-cpn-local-ray-minimize")
        self.assertEqual(standardized["energy"], -3.5)
        self.assertEqual(standardized["downstream_compatibility"]["gswt"]["status"], "ready")
        self.assertEqual(standardized["downstream_compatibility"]["thermodynamics"]["status"], "ready")

    def test_pseudospin_sunny_cpn_minimize_adapter_emits_final_classical_state_result(self):
        solver_result = {
            "method": "sunny-cpn-minimize",
            "energy": -4.25,
            "supercell_shape": [1, 1, 1],
            "local_rays": [
                {
                    "cell": [0, 0, 0],
                    "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}],
                }
            ],
        }

        standardized = solve_pseudospin_orbital_pipeline._build_pseudospin_classical_state_result(
            solver_result,
            classical_method="sunny-cpn-minimize",
            default_supercell_shape=[1, 1, 1],
        )

        self.assertEqual(standardized["role"], "final")
        self.assertEqual(standardized["solver_family"], "retained_local_multiplet")
        self.assertEqual(standardized["method"], "pseudospin-sunny-cpn-minimize")
        self.assertEqual(standardized["energy"], -4.25)
        self.assertEqual(standardized["downstream_compatibility"]["gswt"]["status"], "ready")
        self.assertEqual(standardized["downstream_compatibility"]["thermodynamics"]["status"], "ready")

    def test_pseudospin_routing_exposes_specialized_ansatz_metadata(self):
        resolver = getattr(solve_pseudospin_orbital_pipeline, "_resolve_pseudospin_classical_method_metadata", None)
        self.assertIsNotNone(resolver)

        metadata = resolver("sun-gswt-single-q")

        self.assertEqual(metadata["solver_family"], "specialized_classical_ansatz")
        self.assertEqual(metadata["role"], "specialized")
        self.assertEqual(metadata["standardized_method"], "pseudospin-sun-gswt-single-q")

    def test_pseudospin_glt_adapter_emits_diagnostic_blocked_classical_state_result(self):
        solver_result = {
            "method": "cpn-generalized-lt",
            "lower_bound": -5.0,
            "recommended_followup": "sunny-cpn-minimize",
            "seed_candidate": {
                "kind": "commensurate-projector-seed",
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

        standardized = solve_pseudospin_orbital_pipeline._build_pseudospin_classical_state_result(
            solver_result,
            classical_method="cpn-generalized-lt",
            default_supercell_shape=[1, 1, 1],
        )

        self.assertEqual(standardized["role"], "diagnostic")
        self.assertEqual(standardized["solver_family"], "diagnostic_seed_only")
        self.assertEqual(standardized["method"], "pseudospin-cpn-generalized-lt")
        self.assertEqual(standardized["lower_bound"], -5.0)
        self.assertEqual(standardized["recommended_followup"], "sunny-cpn-minimize")
        self.assertIn("seed_candidate", standardized)
        self.assertEqual(standardized["downstream_compatibility"]["lswt"]["status"], "blocked")
        self.assertEqual(standardized["downstream_compatibility"]["gswt"]["status"], "blocked")
        self.assertEqual(standardized["downstream_compatibility"]["thermodynamics"]["status"], "blocked")

    def test_pseudospin_result_payload_carries_classical_state_result(self):
        solver_result = {
            "method": "cpn-local-ray-minimize",
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
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "solver_family": "retained_local_multiplet",
                "method": "pseudospin-cpn-local-ray-minimize",
            },
        }

        payload = solve_pseudospin_orbital_pipeline._build_result_payload(
            {"inferred": {"local_dimension": 2}, "hamiltonian": {}, "structure": {}, "bond_blocks": []},
            {"simplification": {}, "canonical_model": {}, "effective_model": {}},
            solver_result,
            classical_method="cpn-local-ray-minimize",
            default_supercell_shape=[1, 1, 1],
        )

        self.assertEqual(payload["classical_state_result"]["solver_family"], "retained_local_multiplet")
        self.assertEqual(payload["classical_state_result"]["classical_state"]["manifold"], "CP^(N-1)")
        self.assertNotIn("classical", payload)
        self.assertNotIn("classical_state", payload)

    def test_pseudospin_result_payload_accepts_bare_standardized_contract_as_solver_result(self):
        solver_result = {
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
                "custom_annotation": {"source": "bare-contract"},
                "local_rays": [
                    {
                        "cell": [0, 0, 0],
                        "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}],
                    }
                ],
            },
        }

        payload = solve_pseudospin_orbital_pipeline._build_result_payload(
            {"inferred": {"local_dimension": 2}, "hamiltonian": {}, "structure": {}, "bond_blocks": []},
            {"simplification": {}, "canonical_model": {}, "effective_model": {}},
            solver_result,
            classical_method="cpn-local-ray-minimize",
            default_supercell_shape=[1, 1, 1],
        )

        self.assertEqual(payload["classical_state_result"]["role"], "final")
        self.assertEqual(payload["classical_state_result"]["classical_state"]["supercell_shape"], [1, 1, 1])
        self.assertEqual(payload["classical_state_result"]["classical_state"]["custom_annotation"]["source"], "bare-contract")
        self.assertNotIn("classical", payload)
        self.assertNotIn("classical_state", payload)

    def test_pseudospin_result_payload_does_not_share_standardized_contract_references_with_solver_result(self):
        solver_result = {
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
                "custom_annotation": {"source": "bare-contract"},
                "local_rays": [
                    {
                        "cell": [0, 0, 0],
                        "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}],
                    }
                ],
            },
        }
        original = copy.deepcopy(solver_result)

        payload = solve_pseudospin_orbital_pipeline._build_result_payload(
            {"inferred": {"local_dimension": 2}, "hamiltonian": {}, "structure": {}, "bond_blocks": []},
            {"simplification": {}, "canonical_model": {}, "effective_model": {}},
            solver_result,
            classical_method="cpn-local-ray-minimize",
            default_supercell_shape=[1, 1, 1],
        )

        payload["classical_state_result"]["method"] = "mutated"
        payload["classical_state_result"]["classical_state"]["custom_annotation"]["source"] = "changed"

        self.assertEqual(solver_result, original)

    def test_pseudospin_result_payload_accepts_wrapped_standardized_contract_without_legacy_mirrors_by_default(self):
        solver_result = {
            "classical_state_result": {
                "status": "ok",
                "role": "final",
                "solver_family": "retained_local_multiplet",
                "method": "pseudospin-compatibility-only",
                "downstream_compatibility": {
                    "lswt": {"status": "blocked", "reason": "requires-spin-frame-site-frames"},
                    "gswt": {"status": "blocked", "reason": "requires-local-ray-cpn-state"},
                    "thermodynamics": {"status": "blocked", "reason": "requires-local-ray-cpn-state"},
                },
                "classical_state": {
                    "site_frames": [
                        {
                            "site": 0,
                            "spin_length": 0.5,
                            "direction": [0.0, 0.0, 1.0],
                        }
                    ],
                    "compatibility_label": "wrapped-contract",
                },
            }
        }

        payload = solve_pseudospin_orbital_pipeline._build_result_payload(
            {"inferred": {"local_dimension": 2}, "hamiltonian": {}, "structure": {}, "bond_blocks": []},
            {"simplification": {}, "canonical_model": {}, "effective_model": {}},
            solver_result,
            classical_method="compatibility-only",
            default_supercell_shape=[1, 1, 1],
        )

        self.assertEqual(payload["classical_state_result"]["method"], "pseudospin-compatibility-only")
        self.assertEqual(payload["classical_state_result"]["classical_state"]["compatibility_label"], "wrapped-contract")
        self.assertEqual(len(payload["classical_state_result"]["classical_state"]["site_frames"]), 1)
        self.assertNotIn("classical", payload)
        self.assertNotIn("classical_state", payload)

    def test_pseudospin_result_payload_can_explicitly_export_legacy_mirrors(self):
        solver_result = {
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

        payload = solve_pseudospin_orbital_pipeline._build_result_payload(
            {"inferred": {"local_dimension": 2}, "hamiltonian": {}, "structure": {}, "bond_blocks": []},
            {"simplification": {}, "canonical_model": {}, "effective_model": {}},
            solver_result,
            classical_method="cpn-local-ray-minimize",
            default_supercell_shape=[1, 1, 1],
            compatibility_export_mode="legacy",
        )

        self.assertEqual(payload["classical"]["classical_state_result"]["method"], "pseudospin-cpn-local-ray-minimize")
        self.assertEqual(payload["classical_state"]["manifold"], "CP^(N-1)")

    def test_resolved_bundle_classical_state_preserves_non_cpn_compatibility_state(self):
        solver_result = {
            "status": "ok",
            "role": "final",
            "solver_family": "retained_local_multiplet",
            "method": "pseudospin-compatibility-only",
            "downstream_compatibility": {
                "lswt": {"status": "blocked", "reason": "requires-spin-frame-site-frames"},
                "gswt": {"status": "blocked", "reason": "requires-local-ray-cpn-state"},
                "thermodynamics": {"status": "blocked", "reason": "requires-local-ray-cpn-state"},
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

        resolved = solve_pseudospin_orbital_pipeline._resolved_bundle_classical_state(
            solver_result,
            default_supercell_shape=[1, 1, 1],
        )

        self.assertEqual(resolved, solver_result["classical_state"])

    def test_pseudospin_thermodynamics_gate_accepts_ready_standardized_result(self):
        classical_state_result = {
            "status": "ok",
            "role": "final",
            "method": "pseudospin-sunny-cpn-minimize",
            "downstream_compatibility": {
                "lswt": {"status": "blocked", "reason": "requires-spin-frame-site-frames"},
                "gswt": {"status": "ready"},
                "thermodynamics": {"status": "ready"},
            },
        }

        result = solve_pseudospin_orbital_pipeline._validate_pseudospin_thermodynamics_request(
            classical_state_result,
            classical_method="sunny-cpn-minimize",
        )

        self.assertIsNone(result)

    def test_pseudospin_thermodynamics_gate_prefers_shared_route_over_legacy_method_name(self):
        classical_state_result = {
            "status": "ok",
            "role": "final",
            "method": "pseudospin-restricted-product-state",
            "solver_family": "retained_local_multiplet",
            "downstream_compatibility": {
                "lswt": {"status": "blocked", "reason": "requires-spin-frame-site-frames"},
                "gswt": {"status": "ready"},
                "thermodynamics": {"status": "review", "reason": "requires-caller-confirmed-support"},
            },
        }

        result = solve_pseudospin_orbital_pipeline._validate_pseudospin_thermodynamics_request(
            classical_state_result,
            classical_method="restricted-product-state",
        )

        self.assertIsNone(result)

    def test_pseudospin_thermodynamics_gate_rejects_diagnostic_standardized_result(self):
        classical_state_result = {
            "status": "ok",
            "role": "diagnostic",
            "method": "pseudospin-cpn-generalized-lt",
            "downstream_compatibility": {
                "lswt": {"status": "blocked", "reason": "diagnostic-seed-method"},
                "gswt": {"status": "blocked", "reason": "diagnostic-seed-method"},
                "thermodynamics": {"status": "blocked", "reason": "diagnostic-seed-method"},
            },
        }

        with self.assertRaisesRegex(ValueError, "diagnostic-only"):
            solve_pseudospin_orbital_pipeline._validate_pseudospin_thermodynamics_request(
                classical_state_result,
                classical_method="cpn-generalized-lt",
            )

    def test_pseudospin_thermodynamics_gate_rejects_restricted_product_state_without_cpn_contract(self):
        with self.assertRaisesRegex(ValueError, "requires a CP\\^\\(N-1\\) classical state"):
            solve_pseudospin_orbital_pipeline._validate_pseudospin_thermodynamics_request(
                None,
                classical_method="restricted-product-state",
            )


if __name__ == "__main__":
    unittest.main()
