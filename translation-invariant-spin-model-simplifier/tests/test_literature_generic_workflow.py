import ast
import csv
import importlib
import inspect
import math
import os
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

import pytest


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = SKILL_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


PRODUCT_DIRECTORIES = (
    "cli",
    "input",
    "simplify",
    "common",
    "classical",
    "lswt",
    "output",
)
FORBIDDEN_PRODUCT_DEPENDENCIES = {
    "validation.literature_evidence_adapters",
    "validation.literature_evidence_adapter_oracles",
    "validation.literature_evidence_isolation",
}


def _imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return tuple(imported)


def test_product_modules_do_not_depend_on_literature_catalogs():
    violations = []
    for directory_name in PRODUCT_DIRECTORIES:
        directory = SCRIPTS_ROOT / directory_name
        for path in directory.rglob("*.py"):
            for module_name in _imported_modules(path):
                if any(
                    module_name == forbidden
                    or module_name.startswith(forbidden + ".")
                    for forbidden in FORBIDDEN_PRODUCT_DEPENDENCIES
                ):
                    violations.append(
                        (str(path.relative_to(SKILL_ROOT)), module_name)
                    )

    assert violations == []


def test_literature_case_contract_keeps_claim_out_of_model_input():
    workflow = importlib.import_module("validation.literature_generic_workflow")

    case = workflow.LiteratureModelCase(
        case_id="onsager_square_ising_tc",
        source_id="Onsager_1944",
        claim_id="critical_temperature",
        input_route="operator",
        model_input={
            "text": "-J*Sz@0 Sz@1 on square-lattice nearest-neighbor bonds",
            "selected_classical_bond_label": "spin-only",
        },
        analysis_request={"task": "critical_temperature"},
    )
    claim = workflow.LiteratureClaim(
        claim_id="critical_temperature",
        observable="critical_temperature",
        value=2.269185314213022,
        uncertainty=0.0,
        units="J/k_B",
        source_location="Phys. Rev. 65, 117 (1944)",
    )

    assert tuple(field.name for field in fields(case)) == (
        "case_id",
        "source_id",
        "claim_id",
        "input_route",
        "model_input",
        "analysis_request",
    )
    assert "value" not in case.model_input
    assert "uncertainty" not in case.model_input
    assert claim.value == pytest.approx(2.269185314213022)
    with pytest.raises(TypeError):
        case.model_input["value"] = claim.value


def test_generic_text_workflow_import_does_not_require_spglib(tmp_path):
    (tmp_path / "spglib.py").write_text(
        "raise ImportError('spglib is intentionally unavailable')\n",
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(tmp_path), str(SCRIPTS_ROOT))
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "from cli.simplify_text_input import run_text_simplification_pipeline",
        ],
        cwd=str(SKILL_ROOT),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def test_canonical_lattice_term_contract_runs_through_generic_simplification():
    from cli.simplify_text_input import run_simplification_from_normalized_model
    from input.normalize_input import normalize_input

    normalized = normalize_input(
        {
            "representation": "operator",
            "support": [0, 1],
            "expression": "J1*Sz@0 Sz@1",
            "parameters": {"J1": 1.0},
            "classical_bond_label": "spin-only",
            "selected_local_bond_bond_label": "1",
        }
    )

    result = run_simplification_from_normalized_model(normalized)

    assert normalized["schema_version"] == "lattice-term-contract/v1"
    assert result["status"] == "ok"
    assert result["stage"] == "complete"
    assert result["canonical_model"]
    assert result["readable_model"]
    assert result["effective_model"]
    assert "fidelity" in result
    assert "unsupported_features" in result


def test_generic_simplification_prefers_declared_J_parameter_over_imaginary_alias():
    from cli.simplify_text_input import run_simplification_from_normalized_model
    from input.normalize_input import normalize_input

    for expression, expected_coefficient in (
        ("J*Sz@0 Sz@1", 2.5),
        ("-J*Sz@0 Sz@1", -2.5),
    ):
        normalized = normalize_input(
            {
                "representation": "operator",
                "support": [0, 1],
                "expression": expression,
                "parameters": {"J": 2.5},
                "classical_bond_label": "spin-only",
                "selected_local_bond_bond_label": "1",
            }
        )

        result = run_simplification_from_normalized_model(normalized)

        assert result["status"] == "ok"
        assert len(result["canonical_model"]["two_body"]) == 1
        assert result["canonical_model"]["two_body"][0][
            "coefficient"
        ] == expected_coefficient


def test_literature_case_runs_answer_free_model_through_generic_workflow():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    model_input = {
        "representation": "operator",
        "support": [0, 1],
        "expression": "J1*Sz@0 Sz@1",
        "parameters": {"J1": 1.0},
        "classical_bond_label": "spin-only",
        "selected_local_bond_bond_label": "1",
    }
    first = workflow.LiteratureModelCase(
        case_id="ising_chain_transfer_matrix_model",
        source_id="Baxter_1982",
        claim_id="zero_temperature_limit",
        input_route="structured",
        model_input=model_input,
        analysis_request={"task": "simplification"},
    )
    renamed = workflow.LiteratureModelCase(
        case_id="renamed_case_without_literature_identity",
        source_id="unregistered_source",
        claim_id="different_claim_link",
        input_route="structured",
        model_input=model_input,
        analysis_request={"task": "simplification"},
    )

    first_result = workflow.run_literature_case(first)
    renamed_result = workflow.run_literature_case(renamed)

    assert tuple(inspect.signature(workflow.run_literature_case).parameters) == (
        "case",
    )
    assert first_result["normalization_status"] == "completed"
    assert first_result["simplification_status"] == "completed"
    assert first_result["analysis_status"] == "not_requested"
    assert first_result["product_result"]["status"] == "ok"
    assert first_result["product_result"]["canonical_model"]
    assert first_result["product_result"]["effective_model"]
    for field_name in (
        "canonical_model",
        "readable_model",
        "effective_model",
        "fidelity",
    ):
        assert (
            first_result["product_result"][field_name]
            == renamed_result["product_result"][field_name]
        )


def test_unsupported_literature_input_route_is_reported_without_an_answer():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    case = workflow.LiteratureModelCase(
        case_id="generic_many_body_hr_probe",
        source_id="unregistered_source",
        claim_id="unused_claim",
        input_route="many_body_hr",
        model_input={"path": "answer-free-placeholder.hr"},
        analysis_request={"task": "band_structure"},
    )

    result = workflow.run_literature_case(case)

    assert result == {
        "case_id": "generic_many_body_hr_probe",
        "source_id": "unregistered_source",
        "claim_id": "unused_claim",
        "normalization_status": "unsupported",
        "simplification_status": "not_run",
        "analysis_status": "not_run",
        "blocker": "unsupported input route: many_body_hr",
        "product_result": None,
    }


def test_spin1_literature_case_uses_generic_local_spectrum_backend():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    case = workflow.LiteratureModelCase(
        case_id="single_ion_spin1_anisotropy_levels",
        source_id="generic_spin1_reference",
        claim_id="single_ion_levels",
        input_route="matrix",
        model_input={
            "representation": "matrix",
            "support": [0],
            "matrix": [[1, 0, 0], [0, 0, 0], [0, 0, 1]],
            "local_dim": 3,
            "classical_bond_label": "spin-only",
        },
        analysis_request={"task": "local_spectrum"},
    )

    result = workflow.run_literature_case(case)

    assert result["normalization_status"] == "completed"
    assert result["simplification_status"] == "completed"
    assert result["analysis_status"] == "completed"
    assert result["analysis_result"]["task"] == "local_spectrum"
    assert result["analysis_result"]["eigenvalues"] == pytest.approx(
        [0.0, 1.0, 1.0]
    )


def test_literature_claim_comparison_runs_only_after_product_analysis():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    claim = workflow.LiteratureClaim(
        claim_id="single_ion_levels",
        observable="eigenvalues",
        value=[0.0, 1.0, 1.0],
        uncertainty=1.0e-12,
        units="D",
        source_location="single-ion spectrum table",
    )

    matched = workflow.compare_literature_claim(
        {
            "observable": "eigenvalues",
            "value": [0.0, 1.0, 1.0],
            "units": "D",
        },
        claim,
    )
    mismatched = workflow.compare_literature_claim(
        {
            "observable": "eigenvalues",
            "value": [0.0, 0.5, 1.0],
            "units": "D",
        },
        claim,
    )

    assert matched["status"] == "matched"
    assert matched["maximum_absolute_difference"] == pytest.approx(0.0)
    assert mismatched["status"] == "mismatched"
    assert mismatched["maximum_absolute_difference"] == pytest.approx(0.5)


def test_eligible_inventory_reports_layered_generic_workflow_statuses():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    cases = (
        workflow.LiteratureModelCase(
            case_id="one_dimensional_classical_ising_no_finite_t_transition",
            source_id="Baxter_1982",
            claim_id="zero_temperature_limit",
            input_route="structured",
            model_input={
                "representation": "operator",
                "support": [0, 1],
                "expression": "J1*Sz@0 Sz@1",
                "parameters": {"J1": 1.0},
                "classical_bond_label": "spin-only",
                "selected_local_bond_bond_label": "1",
            },
            analysis_request={"task": "simplification"},
        ),
        workflow.LiteratureModelCase(
            case_id="single_ion_spin1_anisotropy_levels",
            source_id="generic_spin1_reference",
            claim_id="single_ion_levels",
            input_route="matrix",
            model_input={
                "representation": "matrix",
                "support": [0],
                "matrix": [[1, 0, 0], [0, 0, 0], [0, 0, 1]],
                "local_dim": 3,
                "classical_bond_label": "spin-only",
            },
            analysis_request={"task": "local_spectrum"},
        ),
    )

    rows = workflow.build_eligible_workflow_inventory(cases)

    assert len(rows) == 29
    by_id = {row["model_id"]: row for row in rows}
    assert by_id[
        "one_dimensional_classical_ising_no_finite_t_transition"
    ]["simplification_status"] == "completed"
    assert by_id["single_ion_spin1_anisotropy_levels"][
        "analysis_status"
    ] == "completed"
    assert sum(row["migration_status"] == "migrated" for row in rows) == 2
    assert sum(
        row["migration_status"] == "not_migrated" for row in rows
    ) == 27
    required_layers = {
        "backend_status",
        "computation_status",
        "convergence_status",
        "oracle_status",
    }
    assert all(required_layers <= set(row) for row in rows)
    assert by_id["single_ion_spin1_anisotropy_levels"]["backend_status"] == (
        "available"
    )
    assert by_id["single_ion_spin1_anisotropy_levels"][
        "computation_status"
    ] == "completed"
    assert by_id["single_ion_spin1_anisotropy_levels"][
        "convergence_status"
    ] == "not_applicable"
    assert by_id["single_ion_spin1_anisotropy_levels"]["oracle_status"] == (
        "not_connected"
    )


def test_initial_migrated_case_registry_contains_answer_free_inputs_only():
    workflow = importlib.import_module("validation.literature_generic_workflow")

    cases = workflow.initial_generic_literature_cases()

    assert {case.case_id for case in cases} == {
        "one_dimensional_classical_ising_no_finite_t_transition",
        "single_ion_spin1_anisotropy_levels",
        "xxx_spin_half_chain_bethe_ground_state",
        "two_dimensional_square_ising_onsager_tc",
        "xy_spin_half_chain_anisotropic_critical_line",
        "triangular_ising_ferromagnet_exact_tc",
        "honeycomb_ising_ferromagnet_exact_tc",
        "kagome_ising_ferromagnet_exact_tc",
        "spin_ice_tetrahedron_nn_ice_rule",
        "blume_capel_spin1_zero_temperature_level_crossing",
        "triangular_ising_antiferromagnet_residual_entropy",
        "kagome_ising_antiferromagnet_residual_entropy_reference",
        "two_leg_ladder_strong_rung_exact_limit",
        "aklt_spin1_chain_projector_ground_state",
        "shastry_sutherland_exact_dimer_product",
        "checkerboard_heisenberg_afm_planar_pyrochlore_reference",
        "majundar_ghosh_chain_exact_dimer_point",
        "square_compass_model_directional_exchange_degeneracy",
        "transverse_field_ising_chain_critical_point",
        "xx_spin_half_chain_free_fermion_energy",
        "bilinear_biquadratic_spin1_chain_aklt_angle",
        "uimin_lai_sutherland_spin1_su3_point",
        "pyrochlore_dipolar_spin_ice_pauling_entropy",
        "pyrochlore_heisenberg_afm_coulomb_phase_reference",
        "simple_cubic_j1_j2_collinear_reference",
        "diamond_j1_j2_spiral_surface_reference",
        "kitaev_honeycomb_abelian_nonabelian_field_gap_reference",
        "square_toric_code_exact_topological_degeneracy",
        "square_fully_frustrated_ising_residual_entropy_reference",
    }
    assert {case.source_id for case in cases} == {
        "Ising_1925",
        "Blume_1966",
        "Bethe_1931",
        "Onsager_1944",
        "Barouch_McCoy_1971",
        "Husimi_Syozi_1950",
        "Kano_Naya_1953",
        "Harris_et_al_1997",
        "Wannier_1950",
        "Dagotto_Rice_1996",
        "Affleck_Kennedy_Lieb_Tasaki_1987",
        "Shastry_Sutherland_1981",
        "Fouet_et_al_arXiv_cond-mat_0108070",
        "Caspers_Emmett_Magnus_1984",
        "Nussinov_van_den_Brink_2015",
        "Dziarmaga_2005",
        "Lieb_Schultz_Mattis_1961",
        "Uimin_Lai_Sutherland",
        "Bramwell_Gingras_2001",
        "Moessner_Chalker_1998",
        "Pinettes_Diep_1998",
        "Bergman_Alicea_Gull_Trebst_Balents_2007",
        "Kitaev_2006",
        "Kitaev_2003",
        "Villain_1977",
    }
    for case in cases:
        assert "expected_value" not in case.model_input
        assert "literature_value" not in case.model_input
        assert "oracle_result" not in case.model_input


def test_new_operator_cases_reach_only_the_available_generic_workflow_layers():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    cases = {
        case.case_id: case
        for case in workflow.initial_generic_literature_cases()
    }

    expected_coefficients = {
        "xxx_spin_half_chain_bethe_ground_state": {
            "Sx@0 Sx@1": 1.0,
            "Sy@0 Sy@1": 1.0,
            "Sz@0 Sz@1": 1.0,
        },
        "two_dimensional_square_ising_onsager_tc": {
            "Sz@0 Sz@1": -4.0,
        },
        "xy_spin_half_chain_anisotropic_critical_line": {
            "Sx@0 Sx@1": -1.5,
            "Sy@0 Sy@1": -0.5,
        },
    }
    for case_id, expected in expected_coefficients.items():
        result = workflow.run_literature_case(cases[case_id])
        assert result["normalization_status"] == "completed"
        assert result["simplification_status"] == "completed"
        expected_analysis_status = (
            "completed"
            if case_id in {
                "two_dimensional_square_ising_onsager_tc",
                "xy_spin_half_chain_anisotropic_critical_line",
                "xxx_spin_half_chain_bethe_ground_state",
            }
            else "unsupported"
        )
        assert result["analysis_status"] == expected_analysis_status
        assert result["normalized_model"]["lattice_structure"][
            "basis_sites"
        ]
        assert result["normalized_model"]["lattice_structure"][
            "bond_orbits"
        ]
        assert {
            term["canonical_label"]: term["coefficient"]
            for term in result["product_result"]["canonical_model"][
                "two_body"
            ]
        } == expected

    xxx_result = workflow.run_literature_case(
        cases["xxx_spin_half_chain_bethe_ground_state"]
    )
    assert xxx_result["analysis_result"]["task"] == (
        "xxx_chain_bethe_integral"
    )
    assert xxx_result["analysis_result"]["value"] == pytest.approx(
        0.25 - math.log(2.0), abs=1.0e-10
    )

    xy_result = workflow.run_literature_case(
        cases["xy_spin_half_chain_anisotropic_critical_line"]
    )
    assert len(xy_result["product_result"]["canonical_model"][
        "onsite_terms"
    ]) == 1
    assert xy_result["analysis_result"]["task"] == (
        "xy_chain_free_fermion_boundaries"
    )
    assert xy_result["analysis_result"]["value"] == pytest.approx(
        {
            "ising_critical_field": 1.0,
            "anisotropy_transition_gamma": 0.0,
        }
    )

    square_case = cases["two_dimensional_square_ising_onsager_tc"]
    square_result = workflow.run_literature_case(square_case)
    assert "2.269" not in square_case.analysis_request["equation"]
    assert len(
        square_result["normalized_model"]["lattice_structure"][
            "bond_orbits"
        ][0]["members"]
    ) == 2
    assert square_result["analysis_result"]["observable"] == (
        "critical_temperature"
    )
    assert square_result["analysis_result"]["value"] == pytest.approx(
        2.269185314213022, abs=1.0e-10
    )


def test_every_initial_case_includes_lattice_geometry_in_the_model_input():
    workflow = importlib.import_module("validation.literature_generic_workflow")

    for case in workflow.initial_generic_literature_cases():
        assert case.model_input["lattice"]["positions"]


def test_completed_generic_results_are_compared_with_separate_initial_claims():
    workflow = importlib.import_module("validation.literature_generic_workflow")

    rows = workflow.build_eligible_workflow_inventory(
        workflow.initial_generic_literature_cases(),
        claims=workflow.initial_literature_claims(),
    )

    by_id = {row["model_id"]: row for row in rows}
    assert by_id["two_dimensional_square_ising_onsager_tc"][
        "literature_match_status"
    ] == "matched"
    assert by_id["single_ion_spin1_anisotropy_levels"][
        "literature_match_status"
    ] == "matched"
    assert by_id[
        "one_dimensional_classical_ising_no_finite_t_transition"
    ]["literature_match_status"] == "matched"
    assert by_id["xxx_spin_half_chain_bethe_ground_state"][
        "literature_match_status"
    ] == "matched"


def test_one_dimensional_ising_uses_the_generic_transfer_matrix_backend():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    case = next(
        case
        for case in workflow.initial_generic_literature_cases()
        if case.case_id
        == "one_dimensional_classical_ising_no_finite_t_transition"
    )

    result = workflow.run_literature_case(case)

    assert result["analysis_status"] == "completed"
    assert result["analysis_result"]["task"] == (
        "one_dimensional_transfer_matrix"
    )
    assert result["analysis_result"]["proof_kind"] == (
        "positive_finite_transfer_matrix"
    )
    assert result["analysis_result"]["value"] == 0.0


def test_exact_ising_lattices_share_the_generic_scalar_root_backend():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    cases = {
        case.case_id: case
        for case in workflow.initial_generic_literature_cases()
    }
    expected = {
        "triangular_ising_ferromagnet_exact_tc": (
            4.0 / math.log(3.0),
            3,
        ),
        "honeycomb_ising_ferromagnet_exact_tc": (
            2.0 / math.log(2.0 + math.sqrt(3.0)),
            3,
        ),
        "kagome_ising_ferromagnet_exact_tc": (
            4.0 / math.log(3.0 + 2.0 * math.sqrt(3.0)),
            6,
        ),
    }

    for case_id, (expected_value, expected_bond_count) in expected.items():
        case = cases[case_id]
        result = workflow.run_literature_case(case)
        assert case.analysis_request["task"] == "scalar_root"
        assert str(expected_value) not in case.analysis_request["equation"]
        assert result["analysis_status"] == "completed"
        assert result["analysis_result"]["value"] == pytest.approx(
            expected_value, abs=1.0e-10
        )
        orbit = result["normalized_model"]["lattice_structure"][
            "bond_orbits"
        ][0]
        assert len(orbit["members"]) == expected_bond_count


def test_spin_ice_tetrahedron_uses_generic_classical_configuration_enumeration():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    case = next(
        case
        for case in workflow.initial_generic_literature_cases()
        if case.case_id == "spin_ice_tetrahedron_nn_ice_rule"
    )

    result = workflow.run_literature_case(case)

    assert result["analysis_status"] == "completed"
    assert result["analysis_result"]["task"] == (
        "classical_sz_enumeration"
    )
    assert result["analysis_result"]["configuration_count"] == 16
    assert result["analysis_result"]["value"] == [
        {"energy": -2.0, "degeneracy": 6},
        {"energy": 0.0, "degeneracy": 8},
        {"energy": 6.0, "degeneracy": 2},
    ]


def test_blume_capel_crossing_uses_spin1_model_and_generic_root_solver():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    case = next(
        case
        for case in workflow.initial_generic_literature_cases()
        if case.case_id
        == "blume_capel_spin1_zero_temperature_level_crossing"
    )

    result = workflow.run_literature_case(case)

    assert result["normalized_model"]["local_hilbert"]["basis_registry"][
        "basis:spin_s_1"
    ]["dimension"] == 3
    assert len(result["product_result"]["canonical_model"][
        "onsite_terms"
    ]) == 1
    assert result["analysis_status"] == "completed"
    assert result["analysis_result"]["task"] == "scalar_root"
    assert result["analysis_result"]["value"] == pytest.approx(2.0)


def test_frustrated_ising_cases_compute_finite_clusters_without_claiming_limit():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    cases = {
        case.case_id: case
        for case in workflow.initial_generic_literature_cases()
    }

    for case_id in (
        "triangular_ising_antiferromagnet_residual_entropy",
        "kagome_ising_antiferromagnet_residual_entropy_reference",
    ):
        result = workflow.run_literature_case(cases[case_id])

        assert result["normalization_status"] == "completed"
        assert result["simplification_status"] == "completed"
        assert result["analysis_status"] == "inconclusive"
        assert result["analysis_result"]["task"] == (
            "periodic_classical_sz_enumeration"
        )
        assert len(result["analysis_result"]["finite_size_estimates"]) >= 3
        assert all(
            row["ground_state_degeneracy"] > 1
            for row in result["analysis_result"]["finite_size_estimates"]
        )
        assert "thermodynamic-limit" in result["analysis_result"][
            "blocker"
        ]


def test_strong_rung_ladder_gap_comes_from_generic_local_spectrum():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    case = next(
        case
        for case in workflow.initial_generic_literature_cases()
        if case.case_id == "two_leg_ladder_strong_rung_exact_limit"
    )

    result = workflow.run_literature_case(case)

    assert case.model_input["parameters"] == {"J_rung": 1.0}
    assert result["analysis_status"] == "completed"
    assert result["analysis_result"]["task"] == "local_spectrum"
    assert result["analysis_result"]["ground_state_energy"] == pytest.approx(
        -0.75
    )
    assert result["analysis_result"]["ground_state_degeneracy"] == 1
    assert result["analysis_result"]["spectral_gap"] == pytest.approx(1.0)
    assert result["analysis_result"]["value"] == pytest.approx(1.0)


def test_aklt_two_site_projector_uses_generic_matrix_spectrum():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    case = next(
        case
        for case in workflow.initial_generic_literature_cases()
        if case.case_id == "aklt_spin1_chain_projector_ground_state"
    )

    result = workflow.run_literature_case(case)

    assert case.input_route == "matrix"
    assert "expected" not in case.model_input
    assert result["analysis_status"] == "completed"
    assert result["analysis_result"]["matrix_dimension"] == 9
    assert result["analysis_result"]["ground_state_degeneracy"] == 4
    assert result["analysis_result"]["spectral_gap"] == pytest.approx(1.0)
    assert result["analysis_result"]["eigenvalues"] == pytest.approx(
        [0.0] * 4 + [1.0] * 5,
        abs=1.0e-12,
    )


def test_shastry_sutherland_dimer_energy_uses_generic_local_spectrum():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    case = next(
        case
        for case in workflow.initial_generic_literature_cases()
        if case.case_id == "shastry_sutherland_exact_dimer_product"
    )

    result = workflow.run_literature_case(case)

    assert result["analysis_status"] == "completed"
    assert result["analysis_result"]["task"] == "local_spectrum"
    assert result["analysis_result"]["observable"] == (
        "ground_state_energy"
    )
    assert result["analysis_result"]["value"] == pytest.approx(-0.75)
    assert result["analysis_result"]["spectral_gap"] == pytest.approx(1.0)


def test_checkerboard_crossed_plaquette_zero_spin_is_derived_by_ed():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    case = next(
        case
        for case in workflow.initial_generic_literature_cases()
        if case.case_id
        == "checkerboard_heisenberg_afm_planar_pyrochlore_reference"
    )

    result = workflow.run_literature_case(case)

    assert result["analysis_status"] == "completed"
    assert result["analysis_result"]["task"] == "finite_cluster_ed"
    assert result["analysis_result"]["site_count"] == 4
    assert result["analysis_result"]["bond_count"] == 6
    assert result["analysis_result"]["ground_state_energy"] == pytest.approx(
        -1.5
    )
    assert result["analysis_result"]["ground_state_degeneracy"] == 2
    assert result["analysis_result"]["value"] is True
    assert result["analysis_result"][
        "ground_space_total_spin_squared"
    ] == pytest.approx([0.0, 0.0], abs=1.0e-10)


def test_majumdar_ghosh_uses_multiorbit_periodic_cluster_ed():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    case = next(
        case
        for case in workflow.initial_generic_literature_cases()
        if case.case_id == "majundar_ghosh_chain_exact_dimer_point"
    )

    result = workflow.run_literature_case(case)

    assert result["analysis_status"] == "completed"
    assert result["analysis_result"]["task"] == "finite_cluster_ed"
    assert result["analysis_result"]["site_count"] == 4
    assert result["analysis_result"]["bond_count"] == 8
    assert result["analysis_result"]["ground_state_degeneracy"] == 2
    assert result["analysis_result"]["value"][
        "energy_per_site"
    ] == pytest.approx(-0.375)
    assert result["analysis_result"]["value"][
        "ground_state_degeneracy"
    ] == 2


def test_square_compass_line_flips_are_checked_as_ed_commutators():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    case = next(
        case
        for case in workflow.initial_generic_literature_cases()
        if case.case_id
        == "square_compass_model_directional_exchange_degeneracy"
    )

    result = workflow.run_literature_case(case)

    assert result["analysis_status"] == "completed"
    assert result["analysis_result"]["task"] == "finite_cluster_ed"
    assert result["analysis_result"]["site_count"] == 4
    assert result["analysis_result"]["value"] is True
    assert result["analysis_result"]["maximum_commutator_norm"] <= 1.0e-10
    assert len(result["analysis_result"]["commutator_norms"]) == 4


def test_tfim_critical_field_is_derived_from_canonical_couplings():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    case = next(
        case
        for case in workflow.initial_generic_literature_cases()
        if case.case_id == "transverse_field_ising_chain_critical_point"
    )

    result = workflow.run_literature_case(case)

    assert result["analysis_status"] == "completed"
    assert result["analysis_result"]["task"] == "ising_chain_free_fermion"
    assert result["analysis_result"]["exchange"] == pytest.approx(1.0)
    assert result["analysis_result"]["field"] == pytest.approx(0.6)
    assert result["analysis_result"]["current_gap"] == pytest.approx(0.8)
    assert result["analysis_result"]["critical_gap_residual"] == pytest.approx(
        0.0
    )
    assert result["analysis_result"]["value"] == pytest.approx(1.0)


def test_xx_chain_energy_is_derived_by_refined_free_fermion_integration():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    case = next(
        case
        for case in workflow.initial_generic_literature_cases()
        if case.case_id == "xx_spin_half_chain_free_fermion_energy"
    )

    assert "energy_per_site" not in case.model_input
    result = workflow.run_literature_case(case)

    assert result["analysis_status"] == "completed"
    assert result["analysis_result"]["task"] == "xx_chain_free_fermion"
    assert result["analysis_result"]["exchange"] == pytest.approx(1.0)
    assert len(result["analysis_result"]["grid_estimates"]) >= 2
    assert result["analysis_result"]["refinement_difference"] < 1.0e-8
    assert result["analysis_result"]["value"] == pytest.approx(
        -1.0 / math.pi, abs=1.0e-8
    )
    inventory = workflow.build_eligible_workflow_inventory(
        workflow.initial_generic_literature_cases(),
        claims=workflow.initial_literature_claims(),
    )
    row = next(
        row
        for row in inventory
        if row["model_id"] == "xx_spin_half_chain_free_fermion_energy"
    )
    assert row["literature_match_status"] == "matched"


@pytest.mark.parametrize(
    "case_id, expected_ratio, expected_theta, expected_su3",
    [
        (
            "bilinear_biquadratic_spin1_chain_aklt_angle",
            1.0 / 3.0,
            math.atan(1.0 / 3.0),
            False,
        ),
        (
            "uimin_lai_sutherland_spin1_su3_point",
            1.0,
            math.pi / 4.0,
            True,
        ),
    ],
)
def test_spin_one_special_points_are_derived_from_local_bond_matrices(
    case_id, expected_ratio, expected_theta, expected_su3
):
    workflow = importlib.import_module("validation.literature_generic_workflow")
    case = next(
        case
        for case in workflow.initial_generic_literature_cases()
        if case.case_id == case_id
    )

    result = workflow.run_literature_case(case)

    assert result["analysis_status"] == "completed"
    analysis = result["analysis_result"]
    assert analysis["task"] == (
        "spin_one_bilinear_biquadratic_decomposition"
    )
    assert analysis["bilinear_biquadratic_ratio"] == pytest.approx(
        expected_ratio
    )
    assert analysis["theta_radians"] == pytest.approx(expected_theta)
    assert analysis["su3_symmetric"] is expected_su3
    assert analysis["reconstruction_residual"] < 1.0e-12
    row = next(
        row
        for row in workflow.build_eligible_workflow_inventory(
            workflow.initial_generic_literature_cases(),
            claims=workflow.initial_literature_claims(),
        )
        if row["model_id"] == case_id
    )
    assert row["literature_match_status"] == "matched"


def test_pyrochlore_pauling_entropy_comes_from_tetrahedron_enumeration():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    case = next(
        case
        for case in workflow.initial_generic_literature_cases()
        if case.case_id == "pyrochlore_dipolar_spin_ice_pauling_entropy"
    )

    result = workflow.run_literature_case(case)

    assert result["analysis_status"] == "completed"
    analysis = result["analysis_result"]
    assert analysis["task"] == "local_constraint_entropy_estimate"
    assert analysis["configuration_count"] == 16
    assert analysis["allowed_configuration_count"] == 6
    assert analysis["value"] == pytest.approx(0.5 * math.log(1.5))
    row = next(
        row
        for row in workflow.build_eligible_workflow_inventory(
            workflow.initial_generic_literature_cases(),
            claims=workflow.initial_literature_claims(),
        )
        if row["model_id"] == case.case_id
    )
    assert row["literature_match_status"] == "matched"


def test_pyrochlore_coulomb_constraint_comes_from_fourier_flat_bands():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    case = next(
        case
        for case in workflow.initial_generic_literature_cases()
        if case.case_id == "pyrochlore_heisenberg_afm_coulomb_phase_reference"
    )

    result = workflow.run_literature_case(case)

    assert result["analysis_status"] == "completed"
    analysis = result["analysis_result"]
    assert analysis["task"] == "fourier_exchange_spectrum"
    assert analysis["value"] == {
        "zero_total_spin_per_tetrahedron": True,
        "pinch_points": True,
    }
    assert analysis["flat_band_width"] < 1.0e-10
    row = next(
        row
        for row in workflow.build_eligible_workflow_inventory(
            workflow.initial_generic_literature_cases(),
            claims=workflow.initial_literature_claims(),
        )
        if row["model_id"] == case.case_id
    )
    assert row["literature_match_status"] == "matched"


def test_simple_cubic_j1_j2_boundary_is_derived_from_fourier_orbits():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    case = next(
        case
        for case in workflow.initial_generic_literature_cases()
        if case.case_id == "simple_cubic_j1_j2_collinear_reference"
    )

    result = workflow.run_literature_case(case)

    assert result["analysis_status"] == "completed"
    analysis = result["analysis_result"]
    assert analysis["task"] == "bravais_fourier_competing_order_boundary"
    assert analysis["value"] == pytest.approx(0.25)
    assert analysis["energy_crossing_residual"] < 1.0e-12
    row = next(
        row
        for row in workflow.build_eligible_workflow_inventory(
            workflow.initial_generic_literature_cases(),
            claims=workflow.initial_literature_claims(),
        )
        if row["model_id"] == case.case_id
    )
    assert row["literature_match_status"] == "matched"


def test_diamond_spiral_onset_is_derived_from_fourier_curvature():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    case = next(
        case
        for case in workflow.initial_generic_literature_cases()
        if case.case_id == "diamond_j1_j2_spiral_surface_reference"
    )

    result = workflow.run_literature_case(case)

    assert result["analysis_status"] == "completed"
    analysis = result["analysis_result"]
    assert analysis["task"] == "fourier_curvature_instability_boundary"
    assert analysis["value"] == pytest.approx(0.125, abs=1.0e-6)
    assert analysis["curvature_residual"] < 1.0e-8
    row = next(
        row
        for row in workflow.build_eligible_workflow_inventory(
            workflow.initial_generic_literature_cases(),
            claims=workflow.initial_literature_claims(),
        )
        if row["model_id"] == case.case_id
    )
    assert row["literature_match_status"] == "matched"


def test_kitaev_field_gap_is_derived_from_majorana_mass():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    case = next(
        case
        for case in workflow.initial_generic_literature_cases()
        if case.case_id
        == "kitaev_honeycomb_abelian_nonabelian_field_gap_reference"
    )

    result = workflow.run_literature_case(case)

    assert result["analysis_status"] == "completed"
    analysis = result["analysis_result"]
    assert analysis["task"] == "kitaev_majorana_field_gap"
    assert analysis["value"] is True
    assert analysis["majorana_gap"] > 0.0
    assert analysis["dirac_residual"] < 1.0e-12
    row = next(
        row
        for row in workflow.build_eligible_workflow_inventory(
            workflow.initial_generic_literature_cases(),
            claims=workflow.initial_literature_claims(),
        )
        if row["model_id"] == case.case_id
    )
    assert row["literature_match_status"] == "matched"


def test_toric_code_degeneracy_is_derived_from_stabilizer_rank():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    case = next(
        case
        for case in workflow.initial_generic_literature_cases()
        if case.case_id == "square_toric_code_exact_topological_degeneracy"
    )

    result = workflow.run_literature_case(case)

    assert result["analysis_status"] == "completed"
    analysis = result["analysis_result"]
    assert analysis["task"] == "pauli_stabilizer_rank"
    assert analysis["generator_count"] == 8
    assert analysis["stabilizer_rank"] == 6
    assert analysis["logical_qubit_count"] == 2
    assert analysis["value"] == 4
    row = next(
        row
        for row in workflow.build_eligible_workflow_inventory(
            workflow.initial_generic_literature_cases(),
            claims=workflow.initial_literature_claims(),
        )
        if row["model_id"] == case.case_id
    )
    assert row["literature_match_status"] == "matched"


def test_fully_frustrated_ising_entropy_comes_from_strip_transfer_matrix():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    case = next(
        case
        for case in workflow.initial_generic_literature_cases()
        if case.case_id
        == "square_fully_frustrated_ising_residual_entropy_reference"
    )

    result = workflow.run_literature_case(case)

    assert result["analysis_status"] == "completed"
    analysis = result["analysis_result"]
    assert analysis["task"] == "ising_strip_transfer_entropy"
    assert analysis["value"] is True
    assert analysis["residual_entropy_per_spin"] == pytest.approx(
        0.2915609, abs=2.0e-5
    )
    assert analysis["fit_stability_difference"] < 2.0e-5
    row = next(
        row
        for row in workflow.build_eligible_workflow_inventory(
            workflow.initial_generic_literature_cases(),
            claims=workflow.initial_literature_claims(),
        )
        if row["model_id"] == case.case_id
    )
    assert row["literature_match_status"] == "matched"


def test_layered_inventory_report_uses_current_generic_workflow_results(
    tmp_path,
):
    workflow = importlib.import_module("validation.literature_generic_workflow")
    csv_path = tmp_path / "coverage.csv"
    markdown_path = tmp_path / "coverage.md"

    summary = workflow.write_eligible_workflow_report(
        csv_path,
        markdown_path,
        cases=workflow.initial_generic_literature_cases(),
        claims=workflow.initial_literature_claims(),
    )

    assert summary == {
        "eligible_models": 29,
        "migrated_models": 29,
        "not_migrated_models": 0,
        "normalized_models": 29,
        "simplified_models": 29,
        "analyzed_models": 27,
        "convergence_satisfied_models": 15,
        "convergence_not_applicable_models": 12,
        "inconclusive_models": 2,
        "oracle_verified_models": 0,
        "literature_matched_models": 27,
    }
    csv_text = csv_path.read_text(encoding="utf-8")
    markdown_text = markdown_path.read_text(encoding="utf-8")
    assert "single_ion_spin1_anisotropy_levels" in csv_text
    assert "Eligible models | 29" in markdown_text
    assert "Migrated to generic workflow | 29" in markdown_text
    assert "Matched to literature after computation | 27" in markdown_text
    assert "Independent oracle verified | 0" in markdown_text
    assert "| Literature match |" in markdown_text


def test_registered_inventory_covers_every_claim_and_canonical_source():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    inventory = importlib.import_module("validation.literature_evidence_inventory")
    benchmarks = importlib.import_module(
        "validation.literature_spin_model_benchmarks"
    )

    rows = workflow.build_registered_workflow_inventory(
        cases=workflow.initial_generic_literature_cases(),
        claims=workflow.initial_literature_claims(),
    )

    assert len(rows) == 155
    assert len({row["benchmark_name"] for row in rows}) == 155
    assert len({row["canonical_source_identity"] for row in rows}) == 137
    assert {
        row["canonical_source_identity"] for row in rows
    } == {
        inventory.canonical_source_identity(entry["source_url"])
        for entry in benchmarks.LITERATURE_STANDARD_RESULTS
    }
    assert sum(row["migration_status"] == "migrated" for row in rows) == 29
    assert sum(row["migration_status"] == "not_landed" for row in rows) == 126
    assert sum(row["normalization_status"] == "completed" for row in rows) == 29
    assert sum(row["simplification_status"] == "completed" for row in rows) == 29
    assert sum(row["analysis_status"] == "completed" for row in rows) == 27
    assert sum(row["analysis_status"] == "inconclusive" for row in rows) == 2
    assert sum(row["convergence_status"] == "not_demonstrated" for row in rows) == 2
    assert sum(row["literature_match_status"] == "matched" for row in rows) == 27
    assert sum(row["literature_match_status"] == "inconclusive" for row in rows) == 2
    assert {row["oracle_status"] for row in rows} == {"not_connected"}
    assert all("standard_result" not in row for row in rows)
    assert all("paper_value" not in row for row in rows)


def test_registered_inventory_does_not_read_registry_answers():
    workflow = importlib.import_module("validation.literature_generic_workflow")
    benchmarks = importlib.import_module(
        "validation.literature_spin_model_benchmarks"
    )

    class ForbiddenAnswer:
        def __getattribute__(self, name):
            raise AssertionError("registry answer was read")

        def __iter__(self):
            raise AssertionError("registry answer was iterated")

    registry = tuple(
        {
            **entry,
            "standard_result": ForbiddenAnswer(),
        }
        for entry in benchmarks.LITERATURE_STANDARD_RESULTS
    )

    rows = workflow.build_registered_workflow_inventory(
        registry_entries=registry,
        cases=(),
        claims=(),
    )

    assert len(rows) == 155
    assert all(row["migration_status"] == "not_landed" for row in rows)
    assert all(row["analysis_status"] == "not_run" for row in rows)


def test_registered_inventory_report_exposes_layers_and_backend_gaps(tmp_path):
    workflow = importlib.import_module("validation.literature_generic_workflow")
    csv_path = tmp_path / "registered-coverage.csv"
    markdown_path = tmp_path / "registered-coverage.md"

    summary = workflow.write_registered_workflow_report(
        csv_path,
        markdown_path,
        cases=workflow.initial_generic_literature_cases(),
        claims=workflow.initial_literature_claims(),
    )

    assert summary == {
        "registered_claims": 155,
        "canonical_sources": 137,
        "registered_models": 138,
        "answer_free_models_landed": 29,
        "answer_free_models_not_landed": 126,
        "claims_extracted_for_comparison": 27,
        "normalized": 29,
        "simplified": 29,
        "computed": 27,
        "convergence_satisfied": 15,
        "convergence_not_applicable": 12,
        "inconclusive": 2,
        "oracle_verified": 0,
        "literature_matched": 27,
        "unsupported": 0,
        "needs_review": 126,
    }
    csv_lines = csv_path.read_text(encoding="utf-8").splitlines()
    markdown_text = markdown_path.read_text(encoding="utf-8")
    assert len(csv_lines) == 156
    assert "Registered claims | 155" in markdown_text
    assert "Canonical literature sources | 137" in markdown_text
    assert "Distinct registered models | 138" in markdown_text
    assert "Independent oracle verified | 0" in markdown_text
    assert "| anisotropic_exchange | 11 |" in markdown_text
    assert "| ed_or_dmrg | 10 |" in markdown_text
    assert "Paper-side target values are never computation inputs" in markdown_text


def test_checked_in_workflow_reports_match_fresh_generic_runs(tmp_path):
    workflow = importlib.import_module("validation.literature_generic_workflow")
    cases = workflow.initial_generic_literature_cases()
    claims = workflow.initial_literature_claims()
    generated_eligible_csv = tmp_path / "eligible.csv"
    generated_eligible_md = tmp_path / "eligible.md"
    generated_registered_csv = tmp_path / "registered.csv"
    generated_registered_md = tmp_path / "registered.md"

    workflow.write_eligible_workflow_report(
        generated_eligible_csv,
        generated_eligible_md,
        cases=cases,
        claims=claims,
    )
    workflow.write_registered_workflow_report(
        generated_registered_csv,
        generated_registered_md,
        cases=cases,
        claims=claims,
    )

    expected_pairs = (
        (
            SKILL_ROOT / "reports/literature_generic_workflow_coverage.csv",
            generated_eligible_csv,
        ),
        (
            SKILL_ROOT / "reports/literature_generic_workflow_coverage.md",
            generated_eligible_md,
        ),
        (
            SKILL_ROOT
            / "reports/literature_generic_workflow_registered_inventory.csv",
            generated_registered_csv,
        ),
        (
            SKILL_ROOT
            / "reports/literature_generic_workflow_registered_inventory.md",
            generated_registered_md,
        ),
    )
    for checked_in, generated in expected_pairs:
        if checked_in.suffix == ".csv":
            with checked_in.open(encoding="utf-8", newline="") as handle:
                checked_in_rows = list(csv.DictReader(handle))
            with generated.open(encoding="utf-8", newline="") as handle:
                generated_rows = list(csv.DictReader(handle))
            assert checked_in_rows == generated_rows
        else:
            assert checked_in.read_bytes() == generated.read_bytes()
