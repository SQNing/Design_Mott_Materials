import math
import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from classical.classical_solver_driver import infer_high_temperature_energy_per_spin, summarize_thermodynamics
from validation.literature_spin_model_benchmarks import (
    LITERATURE_STANDARD_RESULTS,
    SPIN_MODEL_LITERATURE_CROSSCHECKS,
    aklt_two_site_projector_eigenvalues,
    antiferromagnetic_chain_lsw_energy,
    classical_projection_verification_tasks,
    classical_single_q_verification_tasks,
    classical_heisenberg_dimer_energy,
    classical_heisenberg_dimer_specific_heat,
    computable_observable_coverage_report,
    computable_observable_summary,
    curie_weiss_verification_tasks,
    curie_weiss_temperature,
    ferromagnetic_chain_lsw_energy,
    finite_cluster_energy_verification_tasks,
    finite_cluster_spectrum_verification_tasks,
    honeycomb_nn_afm_lsw_bands,
    kitaev_single_bond_exchange_matrix_tasks,
    literature_verification_tasks_for_observable,
    local_exchange_matrix_verification_tasks,
    majumdar_ghosh_energy_per_site,
    pitch_and_ordering_vector_verification_tasks,
    quantum_heisenberg_dimer_levels,
    quantum_heisenberg_dimer_thermodynamics,
    residual_projection_verification_tasks,
    shastry_sutherland_dimer_energy_per_spin,
    single_ion_spin1_anisotropy_levels,
    spin_ice_tetrahedron_energy,
    square_nn_afm_lsw_energy,
    static_structure_factor,
    structure_factor_verification_tasks,
    standard_results_for_computable_observable,
    standard_results_for_lattice_hamiltonian,
    triangular_nn_afm_lsw_energy,
    transverse_field_ising_chain_gap,
    two_dimensional_ising_square_tc,
    two_dimensional_ising_spontaneous_magnetization,
    verification_route_for_computable_observable,
    xy_bkt_universal_helicity_jump,
    xxx_spin_half_chain_bethe_energy_per_site,
    xxz_spin_half_chain_phase_label,
    zigzag_or_spiral_projection_verification_tasks,
)

from test_cpn_glt_continuous_search_failures import (
    LITERATURE_BENCHMARK_MODELS,
    _diamond_j1_j2_model,
    _honeycomb_j1_j2_model,
    _kagome_nearest_neighbor_model,
    _lowest_kernel_eigenvalue,
    _pyrochlore_nearest_neighbor_model,
    _single_q_glt_energy,
    _square_lattice_j1_j2_model,
    _triangular_lattice_nearest_neighbor_model,
)


def _assert_crosscheck_registry_is_well_formed():
    names = [entry["name"] for entry in SPIN_MODEL_LITERATURE_CROSSCHECKS]
    assert len(names) >= 20
    assert len(names) == len(set(names))
    assert {"classical_ground_state", "spin_wave_dispersion", "thermodynamics"} <= {
        entry["observable"] for entry in SPIN_MODEL_LITERATURE_CROSSCHECKS
    }
    for entry in SPIN_MODEL_LITERATURE_CROSSCHECKS:
        assert entry["source"]
        assert entry["source_url"].startswith("http")
        assert entry["expected"]
        assert entry["checked_by"].startswith("test_")

def _spin_model_bonds_for_infinite_temperature_energy():
    return {
        "bonds": [
            {"source": 0, "target": 0, "matrix": [[0.2, 0.0, 0.0], [0.0, -0.1, 0.0], [0.0, 0.0, 0.5]]},
            {"source": 0, "target": 1, "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]},
        ]
    }


def _model_for_classical_single_q_task(task):
    parameters = task["model_parameters"]
    if task["model_builder"] == "triangular_nn":
        return _triangular_lattice_nearest_neighbor_model(j1=parameters["j1"])
    if task["model_builder"] == "square_j1_j3":
        from test_cpn_glt_continuous_search_failures import _square_lattice_j1_j3_model

        return _square_lattice_j1_j3_model(j1=parameters["j1"], j3=parameters["j3"])
    if task["model_builder"] == "simple_cubic_j1_j2":
        from test_cpn_glt_continuous_search_failures import _simple_cubic_j1_j2_model

        return _simple_cubic_j1_j2_model(j1=parameters["j1"], j2=parameters["j2"])
    if task["model_builder"] == "honeycomb_j1_j2":
        return _honeycomb_j1_j2_model(j1=parameters["j1"], j2=parameters["j2"])
    if task["model_builder"] == "diamond_j1_j2":
        return _diamond_j1_j2_model(j1=parameters["j1"], j2=parameters["j2"])
    raise AssertionError(f"unknown model builder {task['model_builder']}")


def _model_for_classical_projection_task(task):
    parameters = task["model_parameters"]
    if task["model_builder"] == "kagome_nn":
        return _kagome_nearest_neighbor_model(j1=parameters["j1"])
    if task["model_builder"] == "honeycomb_nn":
        return _honeycomb_j1_j2_model(j1=parameters["j1"], j2=0.0)
    raise AssertionError(f"unknown model builder {task['model_builder']}")


def _spin_half_operator(site_count, site, single_site_operator):
    operator = np.array([[1.0]], dtype=complex)
    identity = np.eye(2, dtype=complex)
    for current_site in range(site_count):
        factor = single_site_operator if current_site == site else identity
        operator = np.kron(operator, factor)
    return operator


def _heisenberg_spin_half_cluster_spectrum(site_count, bonds, exchange):
    sx = 0.5 * np.array([[0.0, 1.0], [1.0, 0.0]], dtype=complex)
    sy = 0.5 * np.array([[0.0, -1.0j], [1.0j, 0.0]], dtype=complex)
    sz = 0.5 * np.array([[1.0, 0.0], [0.0, -1.0]], dtype=complex)
    operators = [
        [_spin_half_operator(site_count, site, component) for component in (sx, sy, sz)]
        for site in range(site_count)
    ]
    hamiltonian = np.zeros((2**site_count, 2**site_count), dtype=complex)
    for source, target in bonds:
        for component in range(3):
            hamiltonian += float(exchange) * operators[source][component] @ operators[target][component]
    return np.linalg.eigvalsh(hamiltonian).real


def test_spin_model_literature_crosscheck_registry_tracks_twenty_models_and_three_observables():
    _assert_crosscheck_registry_is_well_formed()
    combined = LITERATURE_BENCHMARK_MODELS + SPIN_MODEL_LITERATURE_CROSSCHECKS
    assert len(combined) >= 40


def test_literature_standard_results_store_is_structured_and_traceable():
    names = [entry["name"] for entry in LITERATURE_STANDARD_RESULTS]
    comparison_kinds = {entry["comparison_kind"] for entry in LITERATURE_STANDARD_RESULTS}
    backend_needs = {entry["backend_needed"] for entry in LITERATURE_STANDARD_RESULTS}

    assert len(LITERATURE_STANDARD_RESULTS) >= 150
    assert len(names) == len(set(names))
    assert {"exact_solution", "paper_numeric", "paper_formula", "exact_enumeration"} <= comparison_kinds
    assert {"analytic", "ed_or_analytic", "dmrg_or_large_ed", "kitaev_majorana"} <= backend_needs
    for entry in LITERATURE_STANDARD_RESULTS:
        assert entry["model"]
        assert entry["lattice"]
        assert entry["hamiltonian"]
        assert isinstance(entry["hamiltonian_terms"], list)
        assert entry["hamiltonian_terms"]
        assert isinstance(entry["parameters"], dict)
        assert entry["observable"]
        assert entry["source"]
        assert entry["source_url"].startswith(("http://", "https://"))
        assert entry["citation_locator"]
        assert isinstance(entry["standard_result"], dict)
        assert entry["standard_result"]


def test_literature_standard_results_include_benchmark_models_from_recent_survey():
    expected_names = {
        "majundar_ghosh_chain_exact_dimer_point",
        "aklt_spin1_chain_projector_ground_state",
        "xxx_spin_half_chain_bethe_ground_state",
        "xxz_spin_half_chain_phase_boundaries",
        "shastry_sutherland_exact_dimer_product",
        "spin_ice_tetrahedron_nn_ice_rule",
        "single_ion_spin1_anisotropy_levels",
        "kitaev_honeycomb_exact_spin_liquid_limit",
        "haldane_spin1_chain_gap_reference",
        "square_spin_half_heisenberg_qmc_energy",
        "j1_j2_square_spin_half_neel_collinear_transition_reference",
        "bilinear_biquadratic_spin1_chain_aklt_angle",
        "transverse_field_ising_chain_critical_point",
        "transverse_field_ising_chain_gap",
        "two_dimensional_square_ising_onsager_tc",
        "two_dimensional_square_ising_spontaneous_magnetization",
        "two_dimensional_xy_bkt_temperature_reference",
        "two_dimensional_xy_bkt_universal_jump",
        "one_dimensional_classical_ising_no_finite_t_transition",
        "one_dimensional_classical_ising_correlation_length",
        "lieb_schultz_mattis_half_integer_constraint",
        "kitaev_honeycomb_gapless_triangle_condition",
        "eight_vertex_zero_field_exact_solution_status",
        "blume_capel_spin1_zero_temperature_level_crossing",
        "square_potts_exact_critical_point",
        "square_clock_q5_two_bkt_transitions",
        "square_ashkin_teller_exact_critical_line",
        "square_six_vertex_ice_exact_solution_status",
        "square_toric_code_exact_topological_degeneracy",
        "square_compass_model_directional_exchange_degeneracy",
        "triangular_j1_j2_spin_half_phase_diagram_reference",
        "triangular_xxz_supersolid_phase_reference",
        "triangular_ring_exchange_spin_liquid_reference",
        "honeycomb_j1_j2_j3_classical_phase_diagram",
        "honeycomb_kitaev_heisenberg_four_sublattice_phases",
        "honeycomb_kitaev_gamma_phase_diagram_reference",
        "kagome_spin_half_heisenberg_energy_reference",
        "kagome_j1_j2_heisenberg_phase_diagram_reference",
        "kagome_dzyaloshinskii_moriya_critical_reference",
        "pyrochlore_heisenberg_coulomb_phase_flat_band",
        "pyrochlore_dipolar_spin_ice_pauling_entropy",
        "pyrochlore_anisotropic_exchange_jzz_jpm_reference",
        "diamond_j1_j2_spiral_surface_reference",
        "fcc_j1_j2_heisenberg_type_order_reference",
        "bcc_j1_j2_heisenberg_collinear_reference",
        "sawtooth_chain_localized_magnon_flat_band",
        "diamond_chain_localized_magnon_flat_band",
        "spin_ladder_rung_singlet_gap_reference",
        "hyperkagome_heisenberg_spin_liquid_reference",
        "haldane_shastry_chain_exact_ground_state",
        "sr_cu2_bo3_2_shastry_sutherland_material_reference",
        "alpha_rucl3_kitaev_gamma_zigzag_reference",
        "nacuo2_triangular_heisenberg_material_reference",
        "cs2cucl4_anisotropic_triangular_spiral_reference",
        "herbertsmithite_kagome_qsl_reference",
        "volborthite_kagome_distorted_reference",
        "kapellasite_kagome_j1_jd_reference",
        "dy2ti2o7_spin_ice_entropy_reference",
        "ho2ti2o7_spin_ice_neutron_reference",
        "yb2ti2o7_pyrochlore_exchange_reference",
        "tb2ti2o7_pyrochlore_spin_liquid_reference",
        "pr2zr2o7_quantum_spin_ice_reference",
        "na4ir3o8_hyperkagome_material_reference",
        "li2iro3_hyperhoneycomb_kitaev_reference",
        "beta_li2iro3_spiral_kitaev_gamma_reference",
        "square_jq_model_deconfined_critical_reference",
        "j1_j2_square_dqcp_columnar_vbs_reference",
        "kagome_one_third_magnetization_plateau_reference",
        "shastry_sutherland_magnetization_plateaus_reference",
        "triangular_heisenberg_spin_half_energy_reference",
        "triangular_heisenberg_magnetization_plateau_reference",
        "honeycomb_haldane_kane_mele_hubbard_spin_model_reference",
        "square_dimerized_heisenberg_critical_reference",
        "two_leg_ladder_strong_rung_exact_limit",
        "spin1_chain_large_d_transition_reference",
        "xx_spin_half_chain_free_fermion_energy",
        "xy_spin_half_chain_anisotropic_critical_line",
        "j1_j2_chain_okamoto_nomura_critical_point",
        "spin_peierls_chain_dimerization_reference",
        "lieb_liniger_delta_bose_gas_bethe_reference",
        "gaudin_yang_spin_half_fermion_bethe_reference",
        "square_heisenberg_spin_half_staggered_magnetization_reference",
        "square_heisenberg_spin_half_spin_stiffness_reference",
        "cubic_ising_critical_temperature_reference",
        "triangular_ising_ferromagnet_exact_tc",
        "honeycomb_ising_ferromagnet_exact_tc",
        "kagome_ising_ferromagnet_exact_tc",
        "triangular_ising_antiferromagnet_residual_entropy",
        "square_fully_frustrated_ising_residual_entropy_reference",
        "kagome_ising_antiferromagnet_residual_entropy_reference",
        "pyrochlore_heisenberg_afm_coulomb_phase_reference",
        "checkerboard_heisenberg_afm_planar_pyrochlore_reference",
        "j1_j2_honeycomb_neel_spin_liquid_transition_reference",
        "j1_j2_triangular_spin_liquid_window_reference",
        "square_ring_exchange_neel_vbs_reference",
        "honeycomb_j1_j2_kitaev_material_na2iro3_reference",
        "li2cuo2_frustrated_ferromagnetic_chain_reference",
        "licuvo4_spiral_chain_reference",
        "azurite_diamond_chain_plateau_reference",
        "cacu2o3_spin_ladder_reference",
        "bpcb_spin_ladder_field_induced_order_reference",
        "ba3cosb2o9_triangular_plateau_reference",
        "ybmggao4_triangular_spin_liquid_reference",
        "zncu3oh6cl2_kagome_dzyaloshinskii_moriya_reference",
        "fe8_molecular_spin_tunneling_reference",
        "kagome_heisenberg_dmrg_spin_liquid_yan_reference",
        "kagome_heisenberg_topological_entanglement_reference",
        "kagome_chiral_spin_liquid_j1_j2_jchi_reference",
        "ca10cr7o28_bilayer_breathing_kagome_reference",
        "scgo_kagome_bilayer_spin_liquid_reference",
        "barlowite_kagome_material_reference",
        "zn_barlowite_kagome_qsl_reference",
        "vesignieite_kagome_material_reference",
        "haydeeite_ferromagnetic_kagome_reference",
        "clinoatacamite_distorted_kagome_reference",
        "edwardsite_kagome_antiferromagnet_reference",
        "jarosite_kagome_dzyaloshinskii_moriya_reference",
        "gadolinium_gallium_garnet_hyperkagome_reference",
        "garnet_gd3ga5o12_spin_liquid_reference",
        "garnet_gd3te2li3o12_hyperkagome_reference",
        "gamma_li2iro3_3d_kitaev_reference",
        "h3liir2o6_kitaev_spin_liquid_candidate_reference",
        "cu2iro3_honeycomb_kitaev_reference",
        "ba3irti2o9_honeycomb_kitaev_reference",
        "ru_br3_kitaev_material_reference",
        "crcl3_honeycomb_heisenberg_reference",
        "cri3_honeycomb_ferromagnet_reference",
        "crgete3_honeycomb_ferromagnet_reference",
        "fecl3_honeycomb_antiferromagnet_reference",
        "ni_ps3_honeycomb_antiferromagnet_reference",
        "mn_ps3_honeycomb_antiferromagnet_reference",
        "fe_ps3_honeycomb_ising_reference",
        "ba2cugeo7_dm_spiral_reference",
        "mnsi_chiral_helimagnet_reference",
        "cu2oseo3_skyrmion_lattice_reference",
    }
    assert expected_names <= {entry["name"] for entry in LITERATURE_STANDARD_RESULTS}


def test_complex_material_references_record_computable_observable_projections():
    complex_reference_names = {
        "kagome_heisenberg_dmrg_spin_liquid_yan_reference",
        "kagome_heisenberg_topological_entanglement_reference",
        "kagome_chiral_spin_liquid_j1_j2_jchi_reference",
        "ca10cr7o28_bilayer_breathing_kagome_reference",
        "scgo_kagome_bilayer_spin_liquid_reference",
        "barlowite_kagome_material_reference",
        "zn_barlowite_kagome_qsl_reference",
        "vesignieite_kagome_material_reference",
        "haydeeite_ferromagnetic_kagome_reference",
        "clinoatacamite_distorted_kagome_reference",
        "edwardsite_kagome_antiferromagnet_reference",
        "jarosite_kagome_dzyaloshinskii_moriya_reference",
        "gadolinium_gallium_garnet_hyperkagome_reference",
        "garnet_gd3ga5o12_spin_liquid_reference",
        "garnet_gd3te2li3o12_hyperkagome_reference",
        "gamma_li2iro3_3d_kitaev_reference",
        "h3liir2o6_kitaev_spin_liquid_candidate_reference",
        "cu2iro3_honeycomb_kitaev_reference",
        "ba3irti2o9_honeycomb_kitaev_reference",
        "ru_br3_kitaev_material_reference",
        "crcl3_honeycomb_heisenberg_reference",
        "cri3_honeycomb_ferromagnet_reference",
        "crgete3_honeycomb_ferromagnet_reference",
        "fecl3_honeycomb_antiferromagnet_reference",
        "ni_ps3_honeycomb_antiferromagnet_reference",
        "mn_ps3_honeycomb_antiferromagnet_reference",
        "fe_ps3_honeycomb_ising_reference",
        "ba2cugeo7_dm_spiral_reference",
        "mnsi_chiral_helimagnet_reference",
        "cu2oseo3_skyrmion_lattice_reference",
    }
    entries_by_name = {entry["name"]: entry for entry in LITERATURE_STANDARD_RESULTS}

    for name in complex_reference_names:
        computable = entries_by_name[name]["standard_result"].get("computable_observables", [])
        assert isinstance(computable, list)
        assert len(computable) >= 2
        assert all(isinstance(observable, str) and observable for observable in computable)


def test_all_complex_references_have_queryable_computable_observable_projections():
    complex_terms = {"material", "kitaev", "gamma", "dzyaloshinskii_moriya", "spin_liquid"}
    complex_entries = [
        entry
        for entry in LITERATURE_STANDARD_RESULTS
        if complex_terms & set(entry["hamiltonian_terms"])
    ]

    assert len(complex_entries) >= 55
    for entry in complex_entries:
        computable = entry["standard_result"].get("computable_observables", [])
        assert len(computable) >= 2, entry["name"]

    honeycomb_bond_matrix = standard_results_for_computable_observable(
        "single_bond_exchange_matrix",
        lattice="honeycomb",
        required_terms=["kitaev"],
    )
    kagome_curie_weiss = standard_results_for_computable_observable(
        "curie_weiss_theta",
        lattice="kagome",
        required_terms=["material"],
    )
    dm_single_q = standard_results_for_computable_observable(
        "single_q_classical_energy",
        required_terms=["dzyaloshinskii_moriya"],
    )

    assert {entry["name"] for entry in honeycomb_bond_matrix} >= {
        "alpha_rucl3_kitaev_gamma_zigzag_reference",
        "honeycomb_j1_j2_kitaev_material_na2iro3_reference",
    }
    assert {entry["name"] for entry in kagome_curie_weiss} >= {
        "herbertsmithite_kagome_qsl_reference",
        "barlowite_kagome_material_reference",
        "zn_barlowite_kagome_qsl_reference",
    }
    assert {entry["name"] for entry in dm_single_q} >= {
        "kagome_dzyaloshinskii_moriya_critical_reference",
        "ba2cugeo7_dm_spiral_reference",
        "mnsi_chiral_helimagnet_reference",
    }


def test_computable_observable_summary_and_verification_tasks_are_actionable():
    summary = computable_observable_summary(required_terms=["material"])
    kagome_summary = computable_observable_summary(
        lattice="kagome",
        required_terms=["material"],
    )
    honeycomb_kitaev_tasks = literature_verification_tasks_for_observable(
        "single_bond_exchange_matrix",
        lattice="honeycomb",
        required_terms=["kitaev"],
    )

    assert summary["curie_weiss_theta"]["count"] >= 25
    assert {"kagome", "honeycomb", "pyrochlore"} <= set(summary["curie_weiss_theta"]["lattices"])
    assert kagome_summary["curie_weiss_theta"]["count"] >= 10
    assert all(lattice == "kagome" for lattice in kagome_summary["curie_weiss_theta"]["lattices"])

    task_names = {task["benchmark_name"] for task in honeycomb_kitaev_tasks}
    assert task_names >= {
        "alpha_rucl3_kitaev_gamma_zigzag_reference",
        "honeycomb_j1_j2_kitaev_material_na2iro3_reference",
    }
    for task in honeycomb_kitaev_tasks:
        assert task["computable_observable"] == "single_bond_exchange_matrix"
        assert task["lattice"] == "honeycomb"
        assert "kitaev" in task["hamiltonian_terms"]
        assert task["verification_kind"] == "local_exchange_matrix"
        assert task["suggested_backend"] == "matrix_inspection_or_single_bond_ed"
        assert task["backend_needed"]
        assert task["source_url"].startswith("http")


def test_computable_observable_routes_to_suggested_verification_backend():
    assert verification_route_for_computable_observable("curie_weiss_theta") == {
        "verification_kind": "thermodynamic_moment_sum_rule",
        "suggested_backend": "high_temperature_series_or_bond_sum",
    }
    assert verification_route_for_computable_observable("single_q_classical_energy") == {
        "verification_kind": "classical_ground_state",
        "suggested_backend": "glt_or_single_q_energy",
    }
    assert verification_route_for_computable_observable("single_bond_exchange_matrix") == {
        "verification_kind": "local_exchange_matrix",
        "suggested_backend": "matrix_inspection_or_single_bond_ed",
    }
    assert verification_route_for_computable_observable("small_cluster_ed_spectrum") == {
        "verification_kind": "finite_cluster_quantum",
        "suggested_backend": "exact_diagonalization",
    }
    assert verification_route_for_computable_observable("kitaev_triangle_gapless_condition") == {
        "verification_kind": "manual_or_specialized",
        "suggested_backend": "model_specific",
    }
    assert verification_route_for_computable_observable("classical_structure_factor") == {
        "verification_kind": "correlation_function",
        "suggested_backend": "structure_factor",
    }


def test_computable_observable_coverage_report_accounts_for_all_registry_labels():
    report = computable_observable_coverage_report()
    expected_labels = {
        observable
        for entry in LITERATURE_STANDARD_RESULTS
        for observable in entry["standard_result"].get("computable_observables", [])
    }

    assert set(report) == expected_labels

    finite_cluster_labels = {
        task["computable_observable"]
        for task in finite_cluster_spectrum_verification_tasks()
    }
    projection_task_labels = {
        task["computable_observable"]
        for task in classical_projection_verification_tasks()
    }
    single_q_task_benchmark_names = {
        task["benchmark_name"]
        for task in classical_single_q_verification_tasks()
    }
    assert report["curie_weiss_theta"]["executable_task_count"] > 0
    assert report["curie_weiss_theta"]["coverage_status"] == "partially_executable"
    assert report["curie_weiss_theta"]["covered_benchmark_names"]
    assert report["curie_weiss_theta"]["uncovered_benchmark_names"]
    assert set(report["curie_weiss_theta"]["covered_benchmark_names"]).isdisjoint(
        report["curie_weiss_theta"]["uncovered_benchmark_names"]
    )

    assert report["single_bond_exchange_matrix"]["executable_task_count"] > 0
    assert report["single_bond_exchange_matrix"]["coverage_status"] == "partially_executable"
    assert {
        "kitaev_honeycomb_exact_spin_liquid_limit",
        "kitaev_honeycomb_gapless_triangle_condition",
        "honeycomb_kitaev_heisenberg_four_sublattice_phases",
        "kitaev_honeycomb_abelian_nonabelian_field_gap_reference",
        "honeycomb_j1_j2_kitaev_material_na2iro3_reference",
        "cu2iro3_honeycomb_kitaev_reference",
        "ba3irti2o9_honeycomb_kitaev_reference",
    } <= set(report["single_bond_exchange_matrix"]["covered_benchmark_names"])
    assert report["single_bond_exchange_matrix"]["uncovered_benchmark_names"]

    assert report["single_bond_exchange_eigenvalues"]["executable_task_count"] == 6
    assert report["single_bond_exchange_eigenvalues"]["coverage_status"] == "fully_executable"
    assert set(report["single_bond_exchange_eigenvalues"]["covered_benchmark_names"]) == {
        "h3liir2o6_kitaev_spin_liquid_candidate_reference",
        "ru_br3_kitaev_material_reference",
    }
    assert report["single_bond_exchange_eigenvalues"]["uncovered_benchmark_names"] == []

    assert report["single_bond_anisotropic_exchange_matrix"]["executable_task_count"] == 1
    assert report["single_bond_anisotropic_exchange_matrix"]["coverage_status"] == "fully_executable"
    assert report["single_bond_anisotropic_exchange_matrix"]["covered_benchmark_names"] == [
        "gamma_li2iro3_3d_kitaev_reference"
    ]
    assert report["single_bond_anisotropic_exchange_matrix"]["uncovered_benchmark_names"] == []

    assert single_q_task_benchmark_names <= set(report["single_q_classical_energy"]["covered_benchmark_names"])
    assert report["single_q_classical_energy"]["executable_task_count"] >= len(
        report["single_q_classical_energy"]["covered_benchmark_names"]
    )
    assert report["single_q_classical_energy"]["coverage_status"] in {
        "partially_executable",
        "fully_executable",
    }

    for label in projection_task_labels:
        assert report[label]["executable_task_count"] > 0
        assert report[label]["coverage_status"] in {
            "partially_executable",
            "fully_executable",
        }
        assert report[label]["covered_benchmark_names"]

    for task in pitch_and_ordering_vector_verification_tasks():
        label = task["computable_observable"]
        assert report[label]["executable_task_count"] > 0
        assert task["benchmark_name"] in report[label]["covered_benchmark_names"]

    assert report["classical_zigzag_or_spiral_energy"]["coverage_status"] == "fully_executable"
    assert report["classical_zigzag_or_spiral_energy"]["executable_task_count"] == report[
        "classical_zigzag_or_spiral_energy"
    ]["count"]

    for task in residual_projection_verification_tasks():
        label = task["computable_observable"]
        assert report[label]["executable_task_count"] > 0
        assert task["benchmark_name"] in report[label]["covered_benchmark_names"]

    for label in finite_cluster_labels:
        assert report[label]["executable_task_count"] == 1
        assert report[label]["coverage_status"] == "fully_executable"
        assert report[label]["covered_benchmark_names"] == report[label]["benchmark_names"]
        assert report[label]["uncovered_benchmark_names"] == []

    for label, details in report.items():
        route = verification_route_for_computable_observable(label)
        assert details["verification_kind"]
        assert details["suggested_backend"]
        assert details["verification_kind"] == route["verification_kind"]
        assert details["suggested_backend"] == route["suggested_backend"]
        assert details["benchmark_names"]
        assert details["count"] == len(details["benchmark_names"])
        assert set(details["covered_benchmark_names"]) <= set(details["benchmark_names"])
        assert set(details["uncovered_benchmark_names"]) <= set(details["benchmark_names"])
        assert set(details["covered_benchmark_names"]).isdisjoint(details["uncovered_benchmark_names"])
        assert set(details["covered_benchmark_names"]) | set(details["uncovered_benchmark_names"]) == set(
            details["benchmark_names"]
        )
        if details["coverage_status"] == "manual_or_specialized":
            assert route["verification_kind"] == "manual_or_specialized"


def test_kitaev_single_bond_exchange_matrix_tasks_are_executable_local_checks():
    tasks = kitaev_single_bond_exchange_matrix_tasks(
        lattice="honeycomb",
        required_terms=["kitaev"],
    )
    task_labels = {(task["benchmark_name"], task["bond_label"]) for task in tasks}

    assert len(tasks) == 6
    assert task_labels >= {
        ("kitaev_honeycomb_exact_spin_liquid_limit", "x"),
        ("kitaev_honeycomb_exact_spin_liquid_limit", "y"),
        ("kitaev_honeycomb_exact_spin_liquid_limit", "z"),
        ("kitaev_honeycomb_gapless_triangle_condition", "x"),
        ("kitaev_honeycomb_gapless_triangle_condition", "y"),
        ("kitaev_honeycomb_gapless_triangle_condition", "z"),
    }
    axis_for_label = {"x": 0, "y": 1, "z": 2}
    for task in tasks:
        matrix = np.array(task["exchange_matrix"], dtype=float)
        axis = axis_for_label[task["bond_label"]]
        assert task["verification_kind"] == "local_exchange_matrix"
        assert task["suggested_backend"] == "matrix_inspection_or_single_bond_ed"
        assert matrix.shape == (3, 3)
        assert np.linalg.matrix_rank(matrix) == task["expected_rank"]
        assert np.linalg.eigvalsh(matrix) == pytest.approx(task["expected_eigenvalues"])
        assert matrix[axis, axis] == pytest.approx(1.0)
        assert np.count_nonzero(matrix) == 1


def test_local_exchange_matrix_tasks_cover_material_eigenvalue_and_anisotropic_labels():
    tasks = local_exchange_matrix_verification_tasks()
    tasks_by_observable = {}
    for task in tasks:
        tasks_by_observable.setdefault(task["computable_observable"], []).append(task)

    matrix_task_names = {
        task["benchmark_name"]
        for task in tasks_by_observable["single_bond_exchange_matrix"]
    }
    assert {
        "kitaev_honeycomb_exact_spin_liquid_limit",
        "kitaev_honeycomb_gapless_triangle_condition",
        "honeycomb_kitaev_heisenberg_four_sublattice_phases",
        "kitaev_honeycomb_abelian_nonabelian_field_gap_reference",
        "honeycomb_j1_j2_kitaev_material_na2iro3_reference",
        "cu2iro3_honeycomb_kitaev_reference",
        "ba3irti2o9_honeycomb_kitaev_reference",
    } <= matrix_task_names

    eigenvalue_tasks = tasks_by_observable["single_bond_exchange_eigenvalues"]
    eigenvalue_task_labels = {
        (task["benchmark_name"], task["bond_label"])
        for task in eigenvalue_tasks
    }
    assert eigenvalue_task_labels == {
        ("h3liir2o6_kitaev_spin_liquid_candidate_reference", "x"),
        ("h3liir2o6_kitaev_spin_liquid_candidate_reference", "y"),
        ("h3liir2o6_kitaev_spin_liquid_candidate_reference", "z"),
        ("ru_br3_kitaev_material_reference", "x"),
        ("ru_br3_kitaev_material_reference", "y"),
        ("ru_br3_kitaev_material_reference", "z"),
    }

    axis_for_label = {"x": 0, "y": 1, "z": 2}
    for task in eigenvalue_tasks:
        matrix = np.array(task["exchange_matrix"], dtype=float)
        axis = axis_for_label[task["bond_label"]]
        assert task["verification_kind"] == "local_exchange_matrix"
        assert matrix.shape == (3, 3)
        assert np.linalg.matrix_rank(matrix) == task["expected_rank"]
        assert np.linalg.eigvalsh(matrix) == pytest.approx([0.0, 0.0, 1.0])
        assert task["expected_eigenvalues"] == [0.0, 0.0, 1.0]
        assert matrix[axis, axis] == pytest.approx(1.0)
        assert np.count_nonzero(matrix) == 1

    anisotropic_tasks = tasks_by_observable["single_bond_anisotropic_exchange_matrix"]
    assert len(anisotropic_tasks) == 1
    anisotropic_task = anisotropic_tasks[0]
    assert anisotropic_task["benchmark_name"] == "gamma_li2iro3_3d_kitaev_reference"
    assert anisotropic_task["bond_label"] == "z"
    assert anisotropic_task["model_parameters"] == {"kitaev": 1.0, "gamma": 0.5}

    anisotropic_matrix = np.array(anisotropic_task["exchange_matrix"], dtype=float)
    assert anisotropic_matrix == pytest.approx(
        np.array([[0.0, 0.5, 0.0], [0.5, 0.0, 0.0], [0.0, 0.0, 1.0]])
    )
    assert np.linalg.eigvalsh(anisotropic_matrix) == pytest.approx(
        anisotropic_task["expected_eigenvalues"]
    )
    assert anisotropic_task["expected_eigenvalues"] == [-0.5, 0.5, 1.0]


def test_literature_standard_results_can_be_found_by_lattice_and_hamiltonian_terms():
    square_j1j2 = standard_results_for_lattice_hamiltonian(
        lattice="square",
        required_terms=["heisenberg", "j1", "j2"],
    )
    honeycomb_kitaev = standard_results_for_lattice_hamiltonian(
        lattice="honeycomb",
        required_terms=["kitaev", "bond_dependent"],
    )
    chain_tfim = standard_results_for_lattice_hamiltonian(
        lattice="chain",
        required_terms=["ising", "transverse_field"],
    )
    pyrochlore_ising = standard_results_for_lattice_hamiltonian(
        lattice="pyrochlore_tetrahedron",
        required_terms=["ising", "local_axis"],
    )
    kagome_dm = standard_results_for_lattice_hamiltonian(
        lattice="kagome",
        required_terms=["heisenberg", "dzyaloshinskii_moriya"],
    )
    triangular_j1j2 = standard_results_for_lattice_hamiltonian(
        lattice="triangular",
        required_terms=["heisenberg", "j1", "j2"],
    )
    square_potts = standard_results_for_lattice_hamiltonian(
        lattice="square",
        required_terms=["potts", "classical"],
    )
    pyrochlore_exchange = standard_results_for_lattice_hamiltonian(
        lattice="pyrochlore",
        required_terms=["anisotropic_exchange", "jzz"],
    )
    material_kitaev = standard_results_for_lattice_hamiltonian(
        lattice="honeycomb",
        required_terms=["kitaev", "gamma", "material"],
    )
    shastry_material = standard_results_for_lattice_hamiltonian(
        lattice="shastry_sutherland",
        required_terms=["heisenberg", "material"],
    )

    assert {entry["name"] for entry in square_j1j2} >= {
        "j1_j2_square_spin_half_neel_collinear_transition_reference"
    }
    assert {entry["name"] for entry in honeycomb_kitaev} >= {
        "kitaev_honeycomb_exact_spin_liquid_limit",
        "kitaev_honeycomb_gapless_triangle_condition",
    }
    assert {entry["name"] for entry in chain_tfim} >= {
        "transverse_field_ising_chain_critical_point",
        "transverse_field_ising_chain_gap",
    }
    assert {entry["name"] for entry in pyrochlore_ising} >= {"spin_ice_tetrahedron_nn_ice_rule"}
    assert {entry["name"] for entry in kagome_dm} >= {"kagome_dzyaloshinskii_moriya_critical_reference"}
    assert {entry["name"] for entry in triangular_j1j2} >= {
        "triangular_j1_j2_spin_half_phase_diagram_reference"
    }
    assert {entry["name"] for entry in square_potts} >= {"square_potts_exact_critical_point"}
    assert {entry["name"] for entry in pyrochlore_exchange} >= {
        "pyrochlore_anisotropic_exchange_jzz_jpm_reference"
    }
    assert {entry["name"] for entry in material_kitaev} >= {"alpha_rucl3_kitaev_gamma_zigzag_reference"}
    assert {entry["name"] for entry in shastry_material} >= {
        "sr_cu2_bo3_2_shastry_sutherland_material_reference"
    }


def _standard_result(name):
    return next(entry for entry in LITERATURE_STANDARD_RESULTS if entry["name"] == name)["standard_result"]


def test_stored_exact_chain_and_dimer_standard_results_match_local_formula_helpers():
    assert _standard_result("majundar_ghosh_chain_exact_dimer_point")["energy_per_site"] == pytest.approx(
        majumdar_ghosh_energy_per_site(j1=1.0)
    )
    assert _standard_result("shastry_sutherland_exact_dimer_product")["energy_per_spin"] == pytest.approx(
        shastry_sutherland_dimer_energy_per_spin(dimer_exchange=1.0)
    )
    assert _standard_result("xxx_spin_half_chain_bethe_ground_state")["energy_per_site"] == pytest.approx(
        xxx_spin_half_chain_bethe_energy_per_site(exchange=1.0)
    )
    assert _standard_result("aklt_spin1_chain_projector_ground_state")[
        "two_site_projector_eigenvalues"
    ] == pytest.approx(aklt_two_site_projector_eigenvalues())


def test_stored_xxz_spin_ice_and_single_ion_standard_results_match_local_helpers():
    xxz_result = _standard_result("xxz_spin_half_chain_phase_boundaries")
    spin_ice_result = _standard_result("spin_ice_tetrahedron_nn_ice_rule")
    single_ion_result = _standard_result("single_ion_spin1_anisotropy_levels")

    assert xxz_spin_half_chain_phase_label(-1.1) == "ferromagnetic"
    assert xxz_spin_half_chain_phase_label(0.0) == "gapless"
    assert xxz_spin_half_chain_phase_label(1.1) == "neel"
    assert xxz_result["gapless_interval"] == pytest.approx([-1.0, 1.0])
    assert spin_ice_tetrahedron_energy(2, jeff=1.0) == pytest.approx(spin_ice_result["two_in_two_out_energy"])
    assert spin_ice_tetrahedron_energy(3, jeff=1.0) == pytest.approx(spin_ice_result["three_in_one_out_energy"])
    assert spin_ice_tetrahedron_energy(4, jeff=1.0) == pytest.approx(spin_ice_result["all_in_all_out_energy"])
    assert single_ion_spin1_anisotropy_levels(anisotropy=1.0) == pytest.approx(single_ion_result["levels"])


def test_stored_ising_xy_and_kitaev_standard_results_match_local_helpers():
    tfim_critical = _standard_result("transverse_field_ising_chain_critical_point")
    tfim_gap = _standard_result("transverse_field_ising_chain_gap")
    onsager = _standard_result("two_dimensional_square_ising_onsager_tc")
    ising_m = _standard_result("two_dimensional_square_ising_spontaneous_magnetization")
    xy_jump = _standard_result("two_dimensional_xy_bkt_universal_jump")
    kitaev_condition = _standard_result("kitaev_honeycomb_gapless_triangle_condition")

    assert tfim_critical["critical_field_over_exchange"] == pytest.approx(1.0)
    assert transverse_field_ising_chain_gap(0.6, exchange=1.0) == pytest.approx(tfim_gap["gap_formula_at_g_0_6"])
    assert transverse_field_ising_chain_gap(1.0, exchange=1.0) == pytest.approx(0.0)
    assert two_dimensional_ising_square_tc(exchange=1.0) == pytest.approx(onsager["tc_over_j"])
    assert two_dimensional_ising_spontaneous_magnetization(beta=0.6, exchange=1.0) == pytest.approx(
        ising_m["magnetization_beta_0_6_j_1"]
    )
    assert xy_bkt_universal_helicity_jump(temperature=1.0) == pytest.approx(
        xy_jump["helicity_modulus_at_t_1"]
    )
    assert kitaev_condition["gapless_condition"] == "triangle_inequalities"
    assert kitaev_condition["isotropic_kitaev_point_gapless"] is True


def test_stored_paper_numeric_results_are_kept_as_references_not_silent_solver_claims():
    haldane = _standard_result("haldane_spin1_chain_gap_reference")
    square_qmc = _standard_result("square_spin_half_heisenberg_qmc_energy")
    j1j2_window = _standard_result("j1_j2_square_spin_half_neel_collinear_transition_reference")

    assert haldane["gap_over_j"] == pytest.approx(0.41048)
    assert haldane["tolerance"] <= 5.0e-5
    assert square_qmc["energy_per_site"] == pytest.approx(-0.669437)
    assert square_qmc["tolerance"] <= 5.0e-6
    assert j1j2_window["nonmagnetic_window_approx"] == pytest.approx([0.4, 0.6])


def test_square_nn_afm_ground_state_neel_and_lsw_dispersion_match_literature():
    model = _square_lattice_j1_j2_model(j1=1.0, j2=0.0)
    neel = [0.5, 0.5, 0.0]

    assert _single_q_glt_energy(model, neel) < _single_q_glt_energy(model, [0.0, 0.0, 0.0]) - 1.0
    assert square_nn_afm_lsw_energy(0.0, 0.0) == pytest.approx(0.0)
    assert square_nn_afm_lsw_energy(math.pi, math.pi) == pytest.approx(0.0, abs=1.0e-12)
    assert square_nn_afm_lsw_energy(math.pi, 0.0) == pytest.approx(4.0)
    assert square_nn_afm_lsw_energy(math.pi / 2.0, math.pi / 2.0) == pytest.approx(4.0)


@pytest.mark.parametrize("spin,expected_zone_boundary", [(1.0, 4.0), (1.5, 6.0), (2.0, 8.0)])
def test_square_nn_afm_lsw_dispersion_scales_with_spin_s_for_s_greater_than_half(
    spin, expected_zone_boundary
):
    assert square_nn_afm_lsw_energy(math.pi, 0.0, spin=spin) == pytest.approx(expected_zone_boundary)
    assert square_nn_afm_lsw_energy(math.pi / 2.0, math.pi / 2.0, spin=spin) == pytest.approx(
        expected_zone_boundary
    )


def test_triangular_nn_afm_ground_state_and_lsw_soft_modes_match_literature():
    model = _triangular_lattice_nearest_neighbor_model(j1=1.0)
    k_point = [1.0 / 3.0, 2.0 / 3.0, 0.0]

    assert _single_q_glt_energy(model, k_point) < _single_q_glt_energy(model, [0.0, 0.0, 0.0]) - 1.0
    assert triangular_nn_afm_lsw_energy(0.0, 0.0) == pytest.approx(0.0)
    assert triangular_nn_afm_lsw_energy(4.0 * math.pi / 3.0, 0.0) == pytest.approx(0.0, abs=1.0e-12)
    assert triangular_nn_afm_lsw_energy(math.pi, math.pi / math.sqrt(3.0)) == pytest.approx(2.0)


@pytest.mark.parametrize("spin,expected_m_point", [(1.0, 2.0), (1.5, 3.0), (2.0, 4.0)])
def test_triangular_nn_afm_lsw_dispersion_scales_with_spin_s_for_s_greater_than_half(
    spin, expected_m_point
):
    assert triangular_nn_afm_lsw_energy(
        math.pi,
        math.pi / math.sqrt(3.0),
        spin=spin,
    ) == pytest.approx(expected_m_point)


def test_honeycomb_nn_afm_ground_state_and_lsw_dispersion_match_literature():
    model = _honeycomb_j1_j2_model(j1=1.0, j2=0.0)
    gamma = [0.0, 0.0, 0.0]

    assert _single_q_glt_energy(model, gamma) == pytest.approx(-1.5, abs=1.0e-12)
    assert honeycomb_nn_afm_lsw_bands(0.0, 0.0) == pytest.approx([0.0, 3.0 * math.sqrt(2.0)])
    assert honeycomb_nn_afm_lsw_bands(4.0 * math.pi / (3.0 * math.sqrt(3.0)), 0.0) == pytest.approx([3.0, 3.0])


@pytest.mark.parametrize(
    "spin,expected_gamma_upper,expected_k",
    [(1.0, 3.0 * math.sqrt(2.0), 3.0), (1.5, 4.5 * math.sqrt(2.0), 4.5), (2.0, 6.0 * math.sqrt(2.0), 6.0)],
)
def test_honeycomb_nn_afm_lsw_bands_scale_with_spin_s_for_s_greater_than_half(
    spin, expected_gamma_upper, expected_k
):
    assert honeycomb_nn_afm_lsw_bands(0.0, 0.0, spin=spin) == pytest.approx([0.0, expected_gamma_upper])
    assert honeycomb_nn_afm_lsw_bands(
        4.0 * math.pi / (3.0 * math.sqrt(3.0)),
        0.0,
        spin=spin,
    ) == pytest.approx([expected_k, expected_k])


def test_kagome_and_pyrochlore_literature_flat_bands_are_kernel_flat():
    for model, points in [
        (
            _kagome_nearest_neighbor_model(j1=1.0),
            [[0.0, 0.0, 0.0], [0.25, 0.125, 0.0], [0.5, 0.5, 0.0]],
        ),
        (
            _pyrochlore_nearest_neighbor_model(j1=1.0),
            [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25], [1.0 / 3.0, 0.2, 0.1]],
        ),
    ]:
        eigenvalues = [_lowest_kernel_eigenvalue(model, point) for point in points]
        assert eigenvalues == pytest.approx([-1.0, -1.0, -1.0], abs=1.0e-12)


def test_diamond_j1_j2_spiral_surface_remains_degenerate_at_multiple_literature_points():
    model = _diamond_j1_j2_model(j1=1.0, j2=0.25)
    q_points = [[1.0 / 3.0, 1.0 / 3.0, 0.0], [0.25, 0.75, 0.0], [0.5, 0.0, 0.0]]
    energies = [_lowest_kernel_eigenvalue(model, q) for q in q_points]

    assert max(energies) - min(energies) < 1.0e-12
    assert energies[0] < _lowest_kernel_eigenvalue(model, [0.0, 0.0, 0.0]) - 1.0e-1


def test_ferromagnetic_chain_lsw_dispersion_matches_textbook_formula():
    assert ferromagnetic_chain_lsw_energy(0.0) == pytest.approx(0.0)
    assert ferromagnetic_chain_lsw_energy(math.pi / 2.0) == pytest.approx(2.0)
    assert ferromagnetic_chain_lsw_energy(math.pi) == pytest.approx(4.0)


def test_antiferromagnetic_chain_lsw_dispersion_matches_textbook_formula():
    assert antiferromagnetic_chain_lsw_energy(0.0) == pytest.approx(0.0)
    assert antiferromagnetic_chain_lsw_energy(math.pi / 2.0) == pytest.approx(2.0)
    assert antiferromagnetic_chain_lsw_energy(math.pi) == pytest.approx(0.0, abs=1.0e-12)


def test_square_j1_j2_stripe_kernel_has_expected_degenerate_ordering_vectors():
    model = _square_lattice_j1_j2_model(j1=1.0, j2=0.8)
    stripe_x = _single_q_glt_energy(model, [0.5, 0.0, 0.0])
    stripe_y = _single_q_glt_energy(model, [0.0, 0.5, 0.0])

    assert stripe_x == pytest.approx(stripe_y, abs=1.0e-12)
    assert stripe_x < _single_q_glt_energy(model, [0.5, 0.5, 0.0]) - 1.0e-1


@pytest.mark.parametrize(
    "coordination,exchange,expected",
    [
        (4, 1.0, -4.0 / 3.0),
        (6, 1.0, -2.0),
        (3, 1.0, -1.0),
        (2, -1.0, 2.0 / 3.0),
    ],
)
def test_curie_weiss_temperatures_match_coordination_number_formula(coordination, exchange, expected):
    assert curie_weiss_temperature(coordination, exchange) == pytest.approx(expected)


def test_registry_curie_weiss_tasks_are_executable_moment_sum_rules():
    tasks = curie_weiss_verification_tasks(required_terms=["heisenberg"])
    square_tasks = curie_weiss_verification_tasks(
        lattice="square",
        required_terms=["heisenberg"],
    )

    assert len(tasks) >= 10
    assert {task["benchmark_name"] for task in square_tasks} >= {
        "square_spin_half_heisenberg_qmc_energy",
        "square_heisenberg_spin_half_staggered_magnetization_reference",
        "square_heisenberg_spin_half_spin_stiffness_reference",
    }
    for task in tasks:
        assert task["verification_kind"] == "thermodynamic_moment_sum_rule"
        assert task["suggested_backend"] == "high_temperature_series_or_bond_sum"
        assert curie_weiss_temperature(task["coordination_number"], task["exchange"]) == pytest.approx(
            task["expected_theta"]
        )


def test_registry_classical_single_q_tasks_are_executable_glt_checks():
    tasks = classical_single_q_verification_tasks(required_terms=["heisenberg"])
    task_names = {task["benchmark_name"] for task in tasks}

    assert task_names >= {
        "triangular_nn_classical_120_reference",
        "square_j1_j3_classical_lifshitz_reference",
        "simple_cubic_j1_j2_collinear_reference",
        "honeycomb_j1_j2_spiral_ring_reference",
        "diamond_j1_j2_spiral_surface_reference",
    }

    for task in tasks:
        model = _model_for_classical_single_q_task(task)
        expected_energy = _single_q_glt_energy(model, task["expected_q"])
        assert task["verification_kind"] == "classical_ground_state"
        assert task["suggested_backend"] == "glt_or_single_q_energy"
        for symmetry_q in task["symmetry_related_q"]:
            assert expected_energy == pytest.approx(_single_q_glt_energy(model, symmetry_q), abs=1.0e-9)
        for competing_q in task["higher_energy_competing_q"]:
            assert expected_energy < _single_q_glt_energy(model, competing_q) - task["minimum_gap"]


def test_registry_classical_projection_tasks_are_executable_glt_or_local_checks():
    tasks = classical_projection_verification_tasks()
    task_names = {task["benchmark_name"] for task in tasks}

    assert task_names >= {
        "kagome_heisenberg_dmrg_spin_liquid_yan_reference",
        "herbertsmithite_kagome_qsl_reference",
        "barlowite_kagome_material_reference",
        "zn_barlowite_kagome_qsl_reference",
        "edwardsite_kagome_antiferromagnet_reference",
        "haydeeite_ferromagnetic_kagome_reference",
        "crcl3_honeycomb_heisenberg_reference",
        "cri3_honeycomb_ferromagnet_reference",
        "crgete3_honeycomb_ferromagnet_reference",
        "fecl3_honeycomb_antiferromagnet_reference",
        "mn_ps3_honeycomb_antiferromagnet_reference",
    }

    for task in tasks:
        assert task["verification_kind"] == "classical_ground_state"
        assert task["suggested_backend"] == "glt_or_single_q_energy"
        assert task["projection_note"]
        if task["projection_kind"] == "flat_lowest_kernel_band":
            model = _model_for_classical_projection_task(task)
            eigenvalues = [_lowest_kernel_eigenvalue(model, q) for q in task["sample_q"]]
            assert eigenvalues == pytest.approx(
                [task["expected_lowest_kernel_eigenvalue"]] * len(task["sample_q"]),
                abs=1.0e-12,
            )
        elif task["projection_kind"] == "gamma_lowest_kernel_minimum":
            model = _model_for_classical_projection_task(task)
            expected_energy = _lowest_kernel_eigenvalue(model, task["expected_q"])
            for competing_q in task["higher_energy_competing_q"]:
                assert expected_energy < _lowest_kernel_eigenvalue(model, competing_q) - task["minimum_gap"]
        elif task["projection_kind"] == "local_120_triangle_constraint":
            spins = np.array(
                [
                    [1.0, 0.0, 0.0],
                    [-0.5, math.sqrt(3.0) / 2.0, 0.0],
                    [-0.5, -math.sqrt(3.0) / 2.0, 0.0],
                ]
            )
            pair_dots = [
                float(np.dot(spins[0], spins[1])),
                float(np.dot(spins[0], spins[2])),
                float(np.dot(spins[1], spins[2])),
            ]
            assert pair_dots == pytest.approx([task["expected_pair_dot"]] * 3)
            assert np.linalg.norm(np.sum(spins, axis=0)) == pytest.approx(
                task["expected_triangle_vector_sum_norm"],
                abs=1.0e-12,
            )
        else:
            raise AssertionError(f"unknown projection kind {task['projection_kind']}")


def test_pitch_and_ordering_vector_tasks_are_executable_projection_checks():
    tasks = pitch_and_ordering_vector_verification_tasks()
    task_names = {task["benchmark_name"] for task in tasks}

    assert task_names >= {
        "ba2cugeo7_dm_spiral_reference",
        "mnsi_chiral_helimagnet_reference",
        "cu2oseo3_skyrmion_lattice_reference",
        "fe_ps3_honeycomb_ising_reference",
        "ru_br3_kitaev_material_reference",
        "ni_ps3_honeycomb_antiferromagnet_reference",
    }

    for task in tasks:
        assert task["projection_note"]
        if task["projection_kind"] == "dm_spiral_pitch":
            parameters = task["model_parameters"]
            expected_pitch = math.atan(
                parameters["dzyaloshinskii_moriya"] / parameters["exchange"]
            ) / (2.0 * math.pi)
            assert task["expected_pitch_reciprocal_lattice_units"] == pytest.approx(expected_pitch)
        elif task["projection_kind"] == "dm_helix_energy":
            parameters = task["model_parameters"]
            expected_energy = -math.sqrt(
                parameters["exchange"] ** 2 + parameters["dzyaloshinskii_moriya"] ** 2
            )
            assert task["expected_energy_per_bond"] == pytest.approx(expected_energy)
            assert task["expected_energy_per_bond"] < task["ferromagnetic_energy_per_bond"]
        elif task["projection_kind"] == "honeycomb_zigzag_m_points":
            ordering_vectors = np.array(task["expected_ordering_vectors"], dtype=float)
            assert ordering_vectors.shape == (3, 3)
            assert np.all(ordering_vectors >= 0.0)
            assert np.all(ordering_vectors <= 0.5)
            assert {tuple(vector) for vector in ordering_vectors} == {
                (0.5, 0.0, 0.0),
                (0.0, 0.5, 0.0),
                (0.5, 0.5, 0.0),
            }
        else:
            raise AssertionError(f"unknown projection kind {task['projection_kind']}")


def test_zigzag_or_spiral_projection_tasks_cover_kitaev_gamma_candidate_manifolds():
    tasks = zigzag_or_spiral_projection_verification_tasks()
    task_names = {task["benchmark_name"] for task in tasks}

    assert len(tasks) == 14
    assert task_names >= {
        "kitaev_honeycomb_exact_spin_liquid_limit",
        "alpha_rucl3_kitaev_gamma_zigzag_reference",
        "beta_li2iro3_spiral_kitaev_gamma_reference",
        "gamma_li2iro3_3d_kitaev_reference",
        "ru_br3_kitaev_material_reference",
    }

    for task in tasks:
        ordering_vectors = np.array(task["expected_ordering_vectors"], dtype=float)
        assert task["verification_kind"] == "classical_ground_state"
        assert task["suggested_backend"] == "glt_or_single_q_energy"
        assert task["projection_note"]
        assert ordering_vectors.shape == (3, 3)
        assert np.all(ordering_vectors >= 0.0)
        assert np.all(ordering_vectors <= 0.5)
        if task["projection_kind"] == "honeycomb_zigzag_m_points":
            assert {tuple(vector) for vector in ordering_vectors} == {
                (0.5, 0.0, 0.0),
                (0.0, 0.5, 0.0),
                (0.5, 0.5, 0.0),
            }
        elif task["projection_kind"] == "spiral_candidate_wavevectors":
            assert np.count_nonzero(ordering_vectors) == 3
            assert np.allclose(np.sum(ordering_vectors, axis=1), 0.32)
        else:
            raise AssertionError(f"unknown projection kind {task['projection_kind']}")


def test_registry_finite_cluster_spectrum_tasks_are_executable_quantum_checks():
    tasks = finite_cluster_spectrum_verification_tasks()
    task_names = {task["benchmark_name"] for task in tasks}

    assert task_names >= {
        "single_ion_spin1_anisotropy_levels",
        "aklt_spin1_chain_projector_ground_state",
        "shastry_sutherland_exact_dimer_product",
        "two_leg_ladder_strong_rung_exact_limit",
    }
    for task in tasks:
        assert task["verification_kind"] == "finite_cluster_quantum"
        assert task["suggested_backend"] == "exact_diagonalization"
        if task["cluster_kind"] == "single_ion_sz2":
            levels = single_ion_spin1_anisotropy_levels(task["cluster_parameters"]["anisotropy"])
            assert levels == pytest.approx(task["expected_levels"])
        elif task["cluster_kind"] == "aklt_two_site_projector":
            assert aklt_two_site_projector_eigenvalues() == pytest.approx(task["expected_projector_eigenvalues"])
        elif task["cluster_kind"] == "heisenberg_dimer":
            levels = quantum_heisenberg_dimer_levels(
                task["cluster_parameters"]["spin"],
                exchange=task["cluster_parameters"]["exchange"],
            )
            energies = [level["energy"] for level in levels]
            degeneracies = [level["degeneracy"] for level in levels]
            assert min(energies) == pytest.approx(task["expected_ground_energy"])
            assert sorted(degeneracies) == task["expected_degeneracies"]
            assert sorted(energies)[1] - sorted(energies)[0] == pytest.approx(task["expected_gap"])
        elif task["cluster_kind"] == "spin_half_heisenberg_triangle":
            spectrum = _heisenberg_spin_half_cluster_spectrum(
                task["site_count"],
                task["bonds"],
                task["cluster_parameters"]["exchange"],
            )
            assert spectrum == pytest.approx(task["expected_levels"])
            assert task["projection_note"]
        else:
            raise AssertionError(f"unknown cluster kind {task['cluster_kind']}")


def test_registry_finite_cluster_energy_tasks_execute_kagome_triangle_ed_projection():
    tasks = finite_cluster_energy_verification_tasks()
    task_names = {task["benchmark_name"] for task in tasks}

    assert task_names >= {"kagome_heisenberg_dmrg_spin_liquid_yan_reference"}
    for task in tasks:
        assert task["verification_kind"] == "finite_cluster_quantum"
        assert task["suggested_backend"] == "exact_diagonalization"
        assert task["cluster_kind"] == "spin_half_heisenberg_triangle"
        assert task["projection_note"]
        spectrum = _heisenberg_spin_half_cluster_spectrum(
            task["site_count"],
            task["bonds"],
            task["cluster_parameters"]["exchange"],
        )
        assert spectrum[0] == pytest.approx(task["expected_ground_energy"])
        assert spectrum[0] / task["site_count"] == pytest.approx(task["expected_ground_energy_per_site"])
        assert np.sum(np.isclose(spectrum, task["expected_ground_energy"], atol=1.0e-10)) == task[
            "expected_ground_state_degeneracy"
        ]


def test_registry_small_cluster_ed_spectrum_tasks_execute_local_chiral_triangle_projection():
    tasks = finite_cluster_spectrum_verification_tasks()
    chiral_tasks = [
        task
        for task in tasks
        if task["computable_observable"] == "small_cluster_ed_spectrum"
    ]

    assert {task["benchmark_name"] for task in chiral_tasks} == {
        "kagome_chiral_spin_liquid_j1_j2_jchi_reference"
    }
    for task in chiral_tasks:
        assert task["cluster_kind"] == "spin_half_heisenberg_triangle"
        spectrum = _heisenberg_spin_half_cluster_spectrum(
            task["site_count"],
            task["bonds"],
            task["cluster_parameters"]["exchange"],
        )
        assert spectrum == pytest.approx(task["expected_levels"])
        assert task["projection_note"]


def test_registry_structure_factor_tasks_are_executable_classical_toy_checks():
    tasks = structure_factor_verification_tasks()
    tasks_by_observable = {}
    for task in tasks:
        tasks_by_observable.setdefault(task["computable_observable"], []).append(task)

    assert {"static_structure_factor", "nearest_neighbor_structure_factor", "classical_structure_factor"} <= set(
        tasks_by_observable
    )
    assert "structure_factor_peak_absence" in tasks_by_observable
    for task in tasks:
        positions = np.array(task["positions"], dtype=float)
        spins = np.array(task["spins"], dtype=float)
        assert task["verification_kind"] == "correlation_function"
        assert task["suggested_backend"] == "structure_factor"
        assert task["projection_note"]
        evaluated = {
            tuple(sample["q"]): static_structure_factor(positions, spins, sample["q"])
            for sample in task["sample_points"]
        }
        for sample in task["sample_points"]:
            assert evaluated[tuple(sample["q"])] == pytest.approx(sample["expected_value"])
        if task["structure_factor_kind"] == "peak_absence":
            assert evaluated[tuple(task["absent_peak_q"])] <= task["maximum_absent_peak_value"]
        elif task["structure_factor_kind"] in {"ferromagnetic_peak", "antiferromagnetic_peak"}:
            peak = evaluated[tuple(task["expected_peak_q"])]
            for competing_q in task["lower_intensity_q"]:
                assert peak > evaluated[tuple(competing_q)] + task["minimum_intensity_gap"]
        else:
            raise AssertionError(f"unknown structure factor kind {task['structure_factor_kind']}")


def test_residual_projection_tasks_make_all_remaining_routed_labels_executable():
    tasks = residual_projection_verification_tasks()
    task_labels = {task["computable_observable"] for task in tasks}

    assert {
        "dipolar_luttinger_tisza_minima",
        "distorted_kagome_classical_minima",
        "classical_ground_state_manifold",
        "interlayer_ordering_vector",
        "classical_spiral_wavevector",
        "linear_spin_wave_modes",
        "spin_wave_gap",
        "single_ion_or_exchange_anisotropy_gap",
        "singlet_gap",
        "two_band_lsw_spectrum",
    } <= task_labels

    for task in tasks:
        assert task["projection_note"]
        if task["projection_kind"] == "sampled_luttinger_tisza_minima":
            candidate_q = np.array(task["candidate_q"], dtype=float)
            assert candidate_q.ndim == 2
            assert candidate_q.shape[1] == 3
            assert isinstance(task["expected_degenerate_minima"], bool)
        elif task["projection_kind"] == "manifold_dimension_lower_bound":
            assert task["expected_minimum_zero_modes"] >= 1
        elif task["projection_kind"] == "ordering_vector_set":
            vectors = np.array(task["expected_ordering_vectors"], dtype=float)
            assert vectors.ndim == 2
            assert vectors.shape[1] == 3
            assert np.all(vectors >= 0.0)
            assert np.all(vectors <= 0.5)
        elif task["projection_kind"] == "local_two_mode_spectrum":
            levels = np.array(task["expected_levels"], dtype=float)
            assert len(levels) == 2
            assert np.all(np.diff(levels) > 0.0)
        elif task["projection_kind"] == "local_gap":
            assert task["expected_gap"] == pytest.approx(task["anisotropy"])
            assert task["expected_gap"] > 0.0
        else:
            raise AssertionError(f"unknown projection kind {task['projection_kind']}")


def test_classical_heisenberg_dimer_thermodynamics_matches_exact_partition_function():
    beta = 1.7
    exchange = 0.8
    assert classical_heisenberg_dimer_energy(beta, exchange) == pytest.approx(-0.32459712057373025)
    assert classical_heisenberg_dimer_specific_heat(beta, exchange) == pytest.approx(0.44146987997037024)


@pytest.mark.parametrize(
    "spin,expected_levels",
    [
        (1.0, [(-2.0, 1), (-1.0, 3), (1.0, 5)]),
        (1.5, [(-3.75, 1), (-2.75, 3), (-0.75, 5), (2.25, 7)]),
        (2.0, [(-6.0, 1), (-5.0, 3), (-3.0, 5), (0.0, 7), (4.0, 9)]),
    ],
)
def test_quantum_heisenberg_dimer_levels_match_total_spin_multiplets_for_s_greater_than_half(
    spin, expected_levels
):
    levels = quantum_heisenberg_dimer_levels(spin, exchange=1.0)
    assert [(level["energy"], level["degeneracy"]) for level in levels] == pytest.approx(expected_levels)
    assert sum(level["degeneracy"] for level in levels) == int((2.0 * spin + 1.0) ** 2)


@pytest.mark.parametrize(
    "spin,beta,expected_energy,expected_specific_heat",
    [
        (1.0, 0.7, -0.9276075023197201, 0.5422587187446302),
        (1.5, 0.7, -2.5163212303165934, 0.9011936353741602),
        (2.0, 0.7, -4.743944912136997, 0.9947653833167956),
    ],
)
def test_quantum_heisenberg_dimer_thermodynamics_matches_exact_s_greater_than_half_sum(
    spin, beta, expected_energy, expected_specific_heat
):
    result = quantum_heisenberg_dimer_thermodynamics(spin, beta=beta, exchange=1.0)
    assert result["energy"] == pytest.approx(expected_energy)
    assert result["specific_heat"] == pytest.approx(expected_specific_heat)
    assert result["partition_function"] > 0.0


def test_thermodynamic_integration_uses_sorted_beta_grid_and_trapezoid_rule():
    temperatures = [1.0, 2.0]
    energy_samples = [[-2.0, -2.0], [-1.0, -1.0]]
    magnetization_samples = [[0.25, 0.25], [0.5, 0.5]]

    result = summarize_thermodynamics(
        temperatures,
        energy_samples,
        magnetization_samples,
        n_spins=2,
        high_temperature_entropy=math.log(4.0 * math.pi),
        energy_infinite_temperature=0.0,
    )

    grid_by_temp = {entry["temperature"]: entry for entry in result["grid"]}
    assert grid_by_temp[2.0]["free_energy"] == pytest.approx(-math.log(4.0 * math.pi) / 0.5 - 0.5)
    assert grid_by_temp[1.0]["free_energy"] == pytest.approx(-math.log(4.0 * math.pi) - 1.0)
    assert grid_by_temp[1.0]["entropy"] == pytest.approx(-1.0 + math.log(4.0 * math.pi))


def test_high_temperature_energy_uses_only_onsite_trace_average():
    model = _spin_model_bonds_for_infinite_temperature_energy()
    assert infer_high_temperature_energy_per_spin(model) == pytest.approx((0.2 - 0.1 + 0.5) / 3.0 / 2.0)
