import math
import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import validation.literature_spin_model_benchmarks as spin_benchmarks
from classical.classical_solver_driver import classical_energy, infer_high_temperature_energy_per_spin, summarize_thermodynamics
from validation.literature_spin_model_benchmarks import (
    LITERATURE_STANDARD_RESULTS,
    SPIN_MODEL_LITERATURE_CROSSCHECKS,
    aklt_two_site_projector_eigenvalues,
    antiferromagnetic_chain_lsw_energy,
    bilinear_biquadratic_aklt_angle,
    blume_capel_square_zero_temperature_level_crossing,
    checkerboard_crossed_plaquette_ground_state_constraint_status,
    classical_projection_verification_tasks,
    classical_single_q_verification_tasks,
    classical_ising_chain_correlation_length,
    classical_heisenberg_dimer_energy,
    classical_heisenberg_dimer_specific_heat,
    computable_observable_coverage_report,
    computable_observable_summary,
    curie_weiss_verification_tasks,
    curie_weiss_temperature,
    dm_selected_chirality_verification_tasks,
    kagome_dm_interaction_relevance_status,
    exact_solution_status,
    bcc_j1_j2_classical_order_energies,
    fcc_j1_j2_classical_order_energies,
    fe8_single_molecule_tunnel_splitting,
    haldane_shastry_exact_ground_state_status,
    kitaev_field_induced_gap_status,
    honeycomb_kitaev_heisenberg_classical_phase_labels,
    ferromagnetic_chain_lsw_energy,
    finite_cluster_energy_verification_tasks,
    finite_cluster_spectrum_verification_tasks,
    honeycomb_nn_afm_lsw_bands,
    honeycomb_j1_j2_j3_collinear_order_energies,
    honeycomb_nearest_neighbor_glt_order_summary,
    kitaev_single_bond_exchange_matrix_tasks,
    kitaev_triangle_gapless_condition_verification_tasks,
    literature_verification_tasks_for_observable,
    local_exchange_matrix_verification_tasks,
    majumdar_ghosh_energy_per_site,
    pitch_and_ordering_vector_verification_tasks,
    paper_reference_verification_tasks,
    quantum_heisenberg_dimer_levels,
    quantum_heisenberg_dimer_thermodynamics,
    quantum_spin_ice_strong_coupling_ring_exchange,
    residual_projection_verification_tasks,
    shastry_sutherland_dimer_energy_per_spin,
    single_ion_spin1_anisotropy_levels,
    spin_ice_tetrahedron_energy,
    ising_ferromagnet_tc,
    ising_macroscopic_degeneracy_status,
    anisotropic_exchange_coupling_labels,
    honeycomb_j1_j2_j3_classical_phase_labels,
    honeycomb_kitaev_zigzag_relevance_status,
    kitaev_gamma_spiral_candidate_status,
    honeycomb_kitaev_gamma_zigzag_reference_status,
    honeycomb_kitaev_gamma_candidate_phase_content,
    spin_gap_opens_with_dimerization_status,
    spin_ladder_strong_rung_gap_status,
    spin_half_triangle_one_third_plateau_interval,
    diamond_chain_dimer_monomer_one_third_plateau_status,
    breathing_kagome_strong_triangle_trimerization_status,
    honeycomb_nearest_neighbor_order_status,
    dm_spiral_pitch_reciprocal_lattice_units,
    j1_j2_chain_classical_spiral_status,
    j1_j2_chain_frustrated_ferromagnetic_status,
    kagome_competing_j1_jd_exchange_status,
    kagome_spin_half_heisenberg_ed_energy_gap_status,
    kagome_spin_half_heisenberg_ed_energy_status,
    anisotropic_triangular_classical_spiral_status,
    localized_magnon_status,
    clock_model_bkt_transition_summary,
    lieb_lattice_ground_state_spin_per_unit_cell,
    pauling_spin_ice_entropy_per_spin,
    pyrochlore_tetrahedron_heisenberg_energy_identity,
    pyrochlore_tetrahedron_zero_sum_constraint_status,
    square_potts_critical_beta_j,
    square_nn_afm_renormalized_staggered_magnetization_status,
    square_nn_afm_lsw_energy,
    square_nn_afm_spin_wave_energy_expansion_status,
    square_nn_afm_renormalized_spin_stiffness_status,
    square_nn_afm_renormalized_spin_wave_velocity_status,
    spin1_bilinear_biquadratic_integrable_angle,
    spin_orbit_induced_anisotropy_status,
    triangular_ising_antiferromagnet_residual_entropy_per_spin,
    triangular_spin_half_heisenberg_ed_shape_average_energy,
    u1_quantum_spin_ice_candidate_status,
    static_structure_factor,
    structure_factor_verification_tasks,
    standard_results_for_computable_observable,
    standard_results_for_lattice_hamiltonian,
    triangular_nn_afm_lsw_energy,
    transverse_field_ising_chain_gap,
    two_dimensional_ising_square_tc,
    two_dimensional_ising_spontaneous_magnetization,
    verification_route_for_computable_observable,
    xx_spin_half_chain_free_fermion_energy_per_site,
    xy_spin_half_chain_critical_line,
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


def _exchange_matrix_eigenvalues(matrix):
    matrix = np.array(matrix, dtype=float)
    if np.allclose(matrix, np.diag(np.diag(matrix))):
        return sorted(float(value) for value in np.diag(matrix))
    if np.allclose(matrix[0:2, 0:2], matrix[0:2, 0:2].T) and np.allclose(matrix[0:2, 2], 0.0) and np.allclose(
        matrix[2, 0:2], 0.0
    ):
        block = matrix[0:2, 0:2]
        trace = float(block[0, 0] + block[1, 1])
        discriminant = math.sqrt(float((block[0, 0] - block[1, 1]) ** 2 + 4.0 * block[0, 1] * block[1, 0]))
        return sorted([(trace - discriminant) / 2.0, (trace + discriminant) / 2.0, float(matrix[2, 2])])
    raise AssertionError(f"unsupported local exchange matrix prototype: {matrix.tolist()}")


def _rank_from_exchange_matrix_eigenvalues(matrix):
    eigenvalues = _exchange_matrix_eigenvalues(matrix)
    return int(np.count_nonzero(np.abs(eigenvalues) > 1.0e-12))


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
    if task["model_builder"] == "triangle_nn":
        return _triangle_nn_classical_model(exchange=parameters["exchange"])
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


def _spin_half_triangle_scalar_chirality_spectrum():
    sx = 0.5 * np.array([[0.0, 1.0], [1.0, 0.0]], dtype=complex)
    sy = 0.5 * np.array([[0.0, -1.0j], [1.0j, 0.0]], dtype=complex)
    sz = 0.5 * np.array([[1.0, 0.0], [0.0, -1.0]], dtype=complex)
    identity = np.eye(2, dtype=complex)

    def operator(site, single_site_operator):
        operator = np.array([[1.0]], dtype=complex)
        for current_site in range(3):
            factor = single_site_operator if current_site == site else identity
            operator = np.kron(operator, factor)
        return operator

    s1 = [operator(0, component) for component in (sx, sy, sz)]
    s2 = [operator(1, component) for component in (sx, sy, sz)]
    s3 = [operator(2, component) for component in (sx, sy, sz)]
    chirality = np.zeros((8, 8), dtype=complex)
    for a, b, c, sign in (
        (0, 1, 2, 1.0),
        (0, 2, 1, -1.0),
        (1, 2, 0, 1.0),
        (1, 0, 2, -1.0),
        (2, 0, 1, 1.0),
        (2, 1, 0, -1.0),
    ):
        chirality += sign * s1[a] @ s2[b] @ s3[c]
    return np.linalg.eigvalsh(chirality).real


def _triangle_nn_classical_model(exchange):
    bonds = []
    for source, target in ((0, 1), (1, 2), (2, 0)):
        bonds.append(
            {
                "source": source,
                "target": target,
                "matrix": [
                    [float(exchange), 0.0, 0.0],
                    [0.0, float(exchange), 0.0],
                    [0.0, 0.0, float(exchange)],
                ],
            }
        )
    return {"bonds": bonds}


def _triangle_dm_classical_model(exchange, dzyaloshinskii_moriya):
    bonds = []
    for source, target in ((0, 1), (1, 2), (2, 0)):
        bonds.append(
            {
                "source": source,
                "target": target,
                "matrix": [
                    [float(exchange), float(dzyaloshinskii_moriya), 0.0],
                    [-float(dzyaloshinskii_moriya), float(exchange), 0.0],
                    [0.0, 0.0, float(exchange)],
                ],
            }
        )
    return {"bonds": bonds}


def _triangle_120_spins(clockwise=False):
    if clockwise:
        return np.array(
            [
                [1.0, 0.0, 0.0],
                [-0.5, -math.sqrt(3.0) / 2.0, 0.0],
                [-0.5, math.sqrt(3.0) / 2.0, 0.0],
            ]
        )
    return np.array(
        [
            [1.0, 0.0, 0.0],
            [-0.5, math.sqrt(3.0) / 2.0, 0.0],
            [-0.5, -math.sqrt(3.0) / 2.0, 0.0],
        ]
    )


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


def test_declared_complex_material_projections_are_structurally_valid_and_optional():
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
        assert all(isinstance(observable, str) and observable for observable in computable)
        assert len(computable) == len(set(computable))

    assert entries_by_name["cu2iro3_honeycomb_kitaev_reference"]["standard_result"].get(
        "computable_observables", []
    ) == []
    assert entries_by_name["zn_barlowite_kagome_qsl_reference"]["standard_result"].get(
        "computable_observables", []
    ) == []
    assert entries_by_name["nacuo2_triangular_heisenberg_material_reference"][
        "standard_result"
    ].get("computable_observables", []) == []
    assert entries_by_name["fecl3_honeycomb_antiferromagnet_reference"][
        "standard_result"
    ].get("computable_observables", []) == ["spiral_geometry_consistency"]


def test_declared_complex_reference_projections_remain_queryable():
    complex_terms = {"material", "kitaev", "gamma", "dzyaloshinskii_moriya", "spin_liquid"}
    complex_entries = [
        entry
        for entry in LITERATURE_STANDARD_RESULTS
        if complex_terms & set(entry["hamiltonian_terms"])
    ]

    assert len(complex_entries) >= 55
    for entry in complex_entries:
        computable = entry["standard_result"].get("computable_observables", [])
        for observable in computable:
            assert entry in standard_results_for_computable_observable(observable)

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
    }
    assert "zn_barlowite_kagome_qsl_reference" not in {
        entry["name"] for entry in kagome_curie_weiss
    }
    assert "cu2iro3_honeycomb_kitaev_reference" not in {
        entry["name"] for entry in honeycomb_bond_matrix
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
    kagome_curie_weiss = kagome_summary["curie_weiss_theta"]
    assert kagome_curie_weiss["count"] == len(kagome_curie_weiss["benchmark_names"])
    assert kagome_curie_weiss["count"] > 0
    assert all(lattice == "kagome" for lattice in kagome_curie_weiss["lattices"])
    assert "zn_barlowite_kagome_qsl_reference" not in kagome_curie_weiss[
        "benchmark_names"
    ]

    task_names = {task["benchmark_name"] for task in honeycomb_kitaev_tasks}
    assert task_names >= {
        "alpha_rucl3_kitaev_gamma_zigzag_reference",
        "honeycomb_j1_j2_kitaev_material_na2iro3_reference",
    }
    assert "cu2iro3_honeycomb_kitaev_reference" not in task_names
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
    assert verification_route_for_computable_observable("triangle_scalar_chirality") == {
        "verification_kind": "finite_cluster_quantum",
        "suggested_backend": "exact_diagonalization",
    }
    assert verification_route_for_computable_observable("single_q_classical_energy") == {
        "verification_kind": "classical_ground_state",
        "suggested_backend": "glt_or_single_q_energy",
    }
    assert verification_route_for_computable_observable("q0_120_order_energy") == {
        "verification_kind": "classical_ground_state",
        "suggested_backend": "glt_or_single_q_energy",
    }
    assert verification_route_for_computable_observable("single_bond_exchange_matrix") == {
        "verification_kind": "local_exchange_matrix",
        "suggested_backend": "matrix_inspection_or_single_bond_ed",
    }
    assert verification_route_for_computable_observable("dm_selected_chirality") == {
        "verification_kind": "classical_ground_state",
        "suggested_backend": "glt_or_single_q_energy",
    }
    assert verification_route_for_computable_observable("small_cluster_ed_spectrum") == {
        "verification_kind": "finite_cluster_quantum",
        "suggested_backend": "exact_diagonalization",
    }
    assert verification_route_for_computable_observable("kitaev_triangle_gapless_condition") == {
        "verification_kind": "theorem",
        "suggested_backend": "analytic_or_symbolic",
    }
    assert verification_route_for_computable_observable("clean_limit_kitaev_phase_condition") == {
        "verification_kind": "paper_reference",
        "suggested_backend": "paper_summary_or_reference",
    }
    assert verification_route_for_computable_observable("dilution_free_cluster_modes") == {
        "verification_kind": "paper_reference",
        "suggested_backend": "paper_summary_or_reference",
    }
    assert verification_route_for_computable_observable("dipolar_energy_minima") == {
        "verification_kind": "paper_reference",
        "suggested_backend": "paper_summary_or_reference",
    }
    assert verification_route_for_computable_observable("finite_cylinder_energy") == {
        "verification_kind": "paper_reference",
        "suggested_backend": "paper_summary_or_reference",
    }
    assert verification_route_for_computable_observable("honeycomb_ising_domain_wall_energy") == {
        "verification_kind": "paper_reference",
        "suggested_backend": "paper_summary_or_reference",
    }
    assert verification_route_for_computable_observable("honeycomb_kitaev_limit") == {
        "verification_kind": "paper_reference",
        "suggested_backend": "paper_summary_or_reference",
    }
    assert verification_route_for_computable_observable("triple_q_skyrmion_variational_energy") == {
        "verification_kind": "paper_reference",
        "suggested_backend": "paper_summary_or_reference",
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
    assert all(item["coverage_status"] == "fully_executable" for item in report.values())

    assert report["curie_weiss_theta"]["executable_task_count"] > 0
    assert report["curie_weiss_theta"]["coverage_status"] == "fully_executable"
    assert report["curie_weiss_theta"]["covered_benchmark_names"]
    assert report["curie_weiss_theta"]["uncovered_benchmark_names"] == []

    assert report["triangle_scalar_chirality"]["executable_task_count"] == 1
    assert report["triangle_scalar_chirality"]["coverage_status"] == "fully_executable"
    assert report["triangle_scalar_chirality"]["uncovered_benchmark_names"] == []

    assert report["q0_120_order_energy"]["executable_task_count"] == 1
    assert report["q0_120_order_energy"]["coverage_status"] == "fully_executable"
    assert report["q0_120_order_energy"]["uncovered_benchmark_names"] == []

    assert report["single_bond_exchange_matrix"]["executable_task_count"] > 0
    assert report["single_bond_exchange_matrix"]["coverage_status"] == "fully_executable"
    assert {
        "kitaev_honeycomb_exact_spin_liquid_limit",
        "kitaev_honeycomb_gapless_triangle_condition",
        "honeycomb_kitaev_heisenberg_four_sublattice_phases",
        "kitaev_honeycomb_abelian_nonabelian_field_gap_reference",
        "honeycomb_j1_j2_kitaev_material_na2iro3_reference",
        "ba3irti2o9_honeycomb_kitaev_reference",
    } <= set(report["single_bond_exchange_matrix"]["covered_benchmark_names"])
    assert "cu2iro3_honeycomb_kitaev_reference" not in report[
        "single_bond_exchange_matrix"
    ]["covered_benchmark_names"]
    assert report["single_bond_exchange_matrix"]["uncovered_benchmark_names"] == []

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

    assert "kitaev_triangle_gapless_condition" not in report

    assert report["dm_selected_chirality"]["executable_task_count"] == report["dm_selected_chirality"]["count"] == 6
    assert report["dm_selected_chirality"]["coverage_status"] == "fully_executable"
    assert set(report["dm_selected_chirality"]["covered_benchmark_names"]) == {
        "kagome_dzyaloshinskii_moriya_critical_reference",
        "zncu3oh6cl2_kagome_dzyaloshinskii_moriya_reference",
        "jarosite_kagome_dzyaloshinskii_moriya_reference",
        "ba2cugeo7_dm_spiral_reference",
        "mnsi_chiral_helimagnet_reference",
        "cu2oseo3_skyrmion_lattice_reference",
    }

    assert report["clean_limit_kitaev_phase_condition"]["executable_task_count"] == 1
    assert report["clean_limit_kitaev_phase_condition"]["coverage_status"] == "fully_executable"
    assert report["dilution_free_cluster_modes"]["coverage_status"] == "fully_executable"
    assert report["dipolar_energy_minima"]["coverage_status"] == "fully_executable"
    assert report["finite_cylinder_energy"]["coverage_status"] == "fully_executable"
    assert report["honeycomb_ising_domain_wall_energy"]["coverage_status"] == "fully_executable"
    assert report["honeycomb_kitaev_limit"]["coverage_status"] == "fully_executable"
    assert report["triple_q_skyrmion_variational_energy"]["coverage_status"] == "fully_executable"

    assert sum(1 for item in report.values() if item["coverage_status"] == "manual_or_specialized") == 0

    assert single_q_task_benchmark_names <= set(report["single_q_classical_energy"]["covered_benchmark_names"])
    assert report["single_q_classical_energy"]["executable_task_count"] >= len(
        report["single_q_classical_energy"]["covered_benchmark_names"]
    )
    assert report["single_q_classical_energy"]["coverage_status"] == "fully_executable"

    for label in projection_task_labels:
        assert report[label]["executable_task_count"] > 0
        assert report[label]["coverage_status"] == "fully_executable"
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
        assert _rank_from_exchange_matrix_eigenvalues(matrix) == task["expected_rank"]
        assert _exchange_matrix_eigenvalues(matrix) == pytest.approx(task["expected_eigenvalues"])
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
        "ba3irti2o9_honeycomb_kitaev_reference",
    } <= matrix_task_names
    assert "cu2iro3_honeycomb_kitaev_reference" not in matrix_task_names

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
        assert _rank_from_exchange_matrix_eigenvalues(matrix) == task["expected_rank"]
        assert _exchange_matrix_eigenvalues(matrix) == pytest.approx([0.0, 0.0, 1.0])
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
    assert _exchange_matrix_eigenvalues(anisotropic_matrix) == pytest.approx(
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


def test_cubic_ising_critical_temperature_matches_published_inverse_temperature_conversion():
    result = _standard_result("cubic_ising_critical_temperature_reference")
    status = spin_benchmarks.cubic_ising_critical_temperature_from_inverse_beta_status()

    assert status["method"] == "published_critical_inverse_temperature_conversion"
    assert status["critical_inverse_temperature_beta_j"] == pytest.approx(0.22165455)
    assert status["critical_temperature_over_j"] == pytest.approx(4.5115248029, abs=1.0e-10)
    assert status["registered_critical_temperature_over_j"] == pytest.approx(result["tc_over_j"])
    assert status["registered_tolerance"] == pytest.approx(result["tolerance"])
    assert status["absolute_difference_from_registered"] < result["tolerance"]
    assert status["matches_registered_critical_temperature"] is True


def test_xy_bkt_temperature_matches_published_inverse_temperature_conversion():
    result = _standard_result("two_dimensional_xy_bkt_temperature_reference")
    status = spin_benchmarks.xy_bkt_temperature_from_published_inverse_beta_status()

    assert status["method"] == "published_bkt_inverse_temperature_conversion"
    assert status["critical_inverse_temperature_beta_j"] == pytest.approx(1.1199)
    assert status["bkt_temperature_over_j"] == pytest.approx(0.892936869363, abs=1.0e-12)
    assert status["registered_bkt_temperature_over_j"] == pytest.approx(result["tbkt_over_j"])
    assert status["registered_tolerance"] == pytest.approx(result["tolerance"])
    assert status["absolute_difference_from_registered"] < result["tolerance"]
    assert status["matches_registered_bkt_temperature"] is True


def test_square_dimerized_heisenberg_qmc_phase_boundary_matches_registered_transition():
    result = _standard_result("square_dimerized_heisenberg_critical_reference")
    status = spin_benchmarks.square_dimerized_heisenberg_qmc_phase_boundary_status()

    assert status["method"] == "published_qmc_phase_boundary_coordinate_conversion"
    assert status["critical_alpha_at_jprime_1"] == pytest.approx(0.31407)
    assert status["critical_diagonal_alpha"] == pytest.approx(0.52337)
    assert status["critical_diagonal_jprime"] == pytest.approx(0.52337)
    assert status["diagonal_symmetric_coordinate_r"] == pytest.approx(0.343560658277, abs=1.0e-12)
    assert status["diagonal_critical_point_between_dimer_and_neel_limits"] is True
    assert status["critical_exponent_difference_from_3d_heisenberg"] == pytest.approx(0.0052)
    assert status["neel_to_dimer_transition"] is result["neel_to_dimer_transition"]
    assert status["matches_registered_transition"] is True


def test_j1_j2_square_ccm_transition_points_reproduce_registered_window():
    result = _standard_result("j1_j2_square_spin_half_neel_collinear_transition_reference")
    status = spin_benchmarks.j1_j2_square_ccm_transition_window_status()

    assert status["method"] == "published_ccm_transition_window_rounding"
    assert status["published_lower_transition_j2_over_j1"] == pytest.approx(0.454)
    assert status["published_upper_transition_j2_over_j1"] == pytest.approx(0.588)
    assert status["rounded_outward_window"] == pytest.approx(result["nonmagnetic_window_approx"])
    assert status["window_width"] == pytest.approx(0.134)
    assert status["window_center"] == pytest.approx(0.521)
    assert status["matches_registered_nonmagnetic_window"] is True


def test_triangular_j1_j2_zhu_white_phase_sequence_matches_registered_phase_diagram():
    result = _standard_result("triangular_j1_j2_spin_half_phase_diagram_reference")
    status = spin_benchmarks.triangular_j1_j2_zhu_white_phase_sequence_status()

    assert status["method"] == "published_dmrg_phase_sequence_parse"
    assert status["spin_liquid_lower_boundary_j2_over_j1"] == pytest.approx(0.06)
    assert status["spin_liquid_upper_boundary_j2_over_j1"] == pytest.approx(0.17)
    assert status["representative_phase_by_j2"][0.0] == "120_degree"
    assert status["representative_phase_by_j2"][0.1] == "spin_liquid"
    assert status["representative_phase_by_j2"][0.2] == "stripe"
    assert status["phase_sequence"] == result["phases"]
    assert status["matches_registered_phase_sequence"] is True


def test_triangular_j1_j2_dmrg_window_parse_matches_registered_spin_liquid_window():
    result = _standard_result("j1_j2_triangular_spin_liquid_window_reference")
    status = spin_benchmarks.triangular_j1_j2_dmrg_spin_liquid_window_status()

    assert status["method"] == "published_dmrg_spin_liquid_window_parse"
    assert status["published_lower_boundary_j2_over_j1"] == pytest.approx(0.07)
    assert status["published_upper_boundary_j2_over_j1"] == pytest.approx(0.15)
    assert status["registered_spin_liquid_window"] == pytest.approx(
        result["spin_liquid_window_approx"]
    )
    assert status["window_width"] == pytest.approx(0.08)
    assert status["window_center"] == pytest.approx(0.11)
    assert status["matches_registered_spin_liquid_window"] is True


def test_honeycomb_j1_j2_dmrg_phase_text_matches_registered_nonmagnetic_claims():
    transition_result = _standard_result(
        "j1_j2_honeycomb_neel_spin_liquid_transition_reference"
    )
    phase_result = _standard_result("honeycomb_spin_half_j1_j2_quantum_phase_reference")
    status = spin_benchmarks.honeycomb_j1_j2_gong_dmrg_nonmagnetic_window_status()

    assert status["method"] == "published_dmrg_honeycomb_nonmagnetic_window_parse"
    assert status["neel_order_vanishes_j2_over_j1"] == pytest.approx(0.22)
    assert status["possible_spin_liquid_lower_j2_over_j1"] == pytest.approx(0.22)
    assert status["possible_spin_liquid_upper_j2_over_j1"] == pytest.approx(0.25)
    assert status["possible_pvb_lower_j2_over_j1"] == pytest.approx(0.25)
    assert status["possible_pvb_upper_j2_over_j1"] == pytest.approx(0.35)
    assert status["intermediate_nonmagnetic_phase"] is transition_result[
        "intermediate_nonmagnetic_phase"
    ]
    assert status["intermediate_nonmagnetic_phase_candidate"] is phase_result[
        "intermediate_nonmagnetic_phase_candidate"
    ]
    assert status["matches_registered_intermediate_nonmagnetic_phase"] is True
    assert status["matches_registered_intermediate_nonmagnetic_phase_candidate"] is True


def test_kagome_dm_published_critical_point_matches_registered_ratio():
    result = _standard_result("kagome_dzyaloshinskii_moriya_critical_reference")
    status = spin_benchmarks.kagome_dm_published_critical_ratio_status()

    assert status["method"] == "published_ed_finite_size_dm_critical_ratio_parse"
    assert status["published_critical_d_over_j"] == pytest.approx(0.1)
    assert status["registered_critical_d_over_j"] == pytest.approx(
        result["critical_d_over_j_approx"]
    )
    assert status["absolute_difference_from_registered"] == pytest.approx(0.0)
    assert status["matches_registered_critical_ratio"] is True


def test_kagome_heisenberg_tee_published_dmrg_claim_matches_registered_z2_label():
    result = _standard_result("kagome_heisenberg_topological_entanglement_reference")
    status = spin_benchmarks.kagome_heisenberg_depenbrock_tee_status()

    assert status["method"] == "published_dmrg_topological_entanglement_parse"
    assert status["published_energy_per_site"] == pytest.approx(-0.4386)
    assert status["published_spin_gap"] == pytest.approx(0.13)
    assert status["published_quantum_dimension"] == pytest.approx(2.0)
    assert status["published_topological_entanglement_entropy"] == "consistent_with_Z2"
    assert status["registered_topological_entanglement_entropy"] == result[
        "topological_entanglement_entropy"
    ]
    assert status["matches_registered_topological_entanglement_entropy"] is True


def test_kagome_chiral_spin_liquid_published_topological_diagnostics_match_registered_phase():
    result = _standard_result("kagome_chiral_spin_liquid_j1_j2_jchi_reference")
    status = spin_benchmarks.kagome_chiral_bauer_csl_phase_status()

    assert status["method"] == "published_dmrg_chiral_spin_liquid_topological_diagnostic_parse"
    assert status["has_ground_state_degeneracy_diagnostic"] is True
    assert status["has_edge_physics_diagnostic"] is True
    assert status["has_anyon_diagnostic"] is True
    assert status["chiral_spin_liquid_phase"] is result["chiral_spin_liquid_phase"]
    assert status["matches_registered_chiral_spin_liquid_phase"] is True


def test_square_j1_j2_gong_plaquette_vbs_phase_matches_registered_vbs_reference():
    result = _standard_result("j1_j2_square_dqcp_columnar_vbs_reference")
    status = spin_benchmarks.square_j1_j2_gong_pvb_phase_status()

    assert status["method"] == "published_dmrg_square_j1_j2_pvb_phase_parse"
    assert status["neel_order_vanishes_j2_over_j1"] == pytest.approx(0.44)
    assert status["pvb_lower_j2_over_j1"] == pytest.approx(0.5)
    assert status["pvb_upper_j2_over_j1"] == pytest.approx(0.61)
    assert status["published_vbs_kind"] == "plaquette"
    assert status["columnar_or_plaquette_vbs_reference"] is result[
        "columnar_or_plaquette_vbs_reference"
    ]
    assert status["matches_registered_columnar_or_plaquette_vbs_reference"] is True


def test_square_j1_j2_j3_peps_phase_text_matches_registered_multiple_paramagnetic_regions():
    result = _standard_result("j1_j2_j3_square_quantum_phase_reference")
    status = spin_benchmarks.square_j1_j2_j3_peps_multiple_paramagnetic_regions_status()

    assert status["method"] == "published_peps_square_j1_j2_j3_phase_diagram_parse"
    assert status["published_paramagnetic_regions"] == [
        "gapless_qsl",
        "plaquette_vbs",
        "mixed_columnar_plaquette_vbs",
    ]
    assert status["published_paramagnetic_region_count"] == 3
    assert status["multiple_paramagnetic_regions"] is result[
        "multiple_paramagnetic_regions"
    ]
    assert status["matches_registered_multiple_paramagnetic_regions"] is True


@pytest.mark.parametrize(
    ("benchmark_name", "expected_direct_observable"),
    [
        ("herbertsmithite_kagome_qsl_reference", "no_magnetic_order_down_to_low_temperature"),
        ("tb2ti2o7_pyrochlore_spin_liquid_reference", "persistent_spin_dynamics_without_lro"),
        ("na4ir3o8_hyperkagome_material_reference", "no_lro_despite_large_curie_weiss_scale"),
        ("ybmggao4_triangular_spin_liquid_reference", "no_magnetic_order_down_to_low_temperature"),
        ("scgo_kagome_bilayer_spin_liquid_reference", "no_conventional_long_range_order"),
        ("garnet_gd3ga5o12_spin_liquid_reference", "short_range_correlations_without_simple_lro"),
        ("h3liir2o6_kitaev_spin_liquid_candidate_reference", "no_magnetic_order_or_freezing_down_to_low_temperature"),
        ("ba3irti2o9_honeycomb_kitaev_reference", "no_magnetic_order_down_to_low_temperature"),
    ],
)
def test_material_spin_liquid_references_parse_direct_published_experimental_observables(
    benchmark_name,
    expected_direct_observable,
):
    result = _standard_result(benchmark_name)
    status = spin_benchmarks.material_published_experimental_observable_status(
        benchmark_name
    )

    assert status["method"] == "published_experimental_material_observable_parse"
    assert status["direct_observable"] == expected_direct_observable
    assert status["registered_claim_key"] in result
    assert status["registered_claim_value"] is result[status["registered_claim_key"]]
    assert status["matches_registered_material_observable"] is True


def test_kagome_j1_j2_kolley_phase_labels_match_registered_phase_diagram():
    result = _standard_result("kagome_j1_j2_heisenberg_phase_diagram_reference")
    status = spin_benchmarks.kagome_j1_j2_kolley_phase_label_status()

    assert status["method"] == "published_dmrg_phase_label_parse"
    assert status["sqrt3_boundary_j2_over_j1"] == pytest.approx(-0.1)
    assert status["q0_boundary_j2_over_j1"] == pytest.approx(0.2)
    assert status["representative_phase_by_j2"][-0.2] == "sqrt3xsqrt3_order"
    assert status["representative_phase_by_j2"][0.0] == "spin_liquid"
    assert status["representative_phase_by_j2"][0.4] == "q0_order"
    assert status["registered_phase_labels"] == result["phases"]
    assert status["matches_registered_phase_labels"] is True


def test_square_jq_sandvik_qmc_critical_parse_matches_registered_deconfined_transition():
    result = _standard_result("square_jq_model_deconfined_critical_reference")
    status = spin_benchmarks.square_jq_sandvik_deconfined_transition_status()

    assert status["method"] == "published_qmc_deconfined_transition_parse"
    assert status["critical_j_over_q"] == pytest.approx(0.04)
    assert status["critical_j_over_q_uncertainty"] == pytest.approx(0.003)
    assert status["dynamic_exponent_z"] == pytest.approx(1.0)
    assert status["correlation_length_exponent_nu"] == pytest.approx(0.78)
    assert status["anomalous_dimension_eta"] == pytest.approx(0.26)
    assert status["representative_phase_by_j_over_q"][0.0] == "vbs"
    assert status["representative_phase_by_j_over_q"][0.1] == "neel"
    assert status["single_continuous_transition"] is True
    assert status["emergent_u1_vbs_symmetry"] is True
    assert status["neel_to_vbs_transition"] is result["neel_to_vbs_transition"]
    assert status["matches_registered_transition"] is True


def test_stored_haldane_gap_matches_tenpy_infinite_mps_plane_wave_excitation():
    result = _standard_result("haldane_spin1_chain_gap_reference")
    status = spin_benchmarks.haldane_spin1_chain_gap_tenpy_plane_wave_status(
        bond_dimension=48,
    )

    assert status["method"] == "tenpy_infinite_mps_plane_wave_excitation"
    assert status["unit_cell_sites"] == 2
    assert status["triplet_charge_sector"] == [2]
    assert status["momentum"] == pytest.approx(0.0)
    assert status["ground_energy_per_site"] == pytest.approx(-1.401484038, abs=2.0e-7)
    assert status["gap_over_j"] == pytest.approx(
        result["gap_over_j"],
        abs=result["tolerance"],
    )


def test_stored_exact_status_and_transfer_matrix_results_match_local_helpers():
    aklt_angle = _standard_result("bilinear_biquadratic_spin1_chain_aklt_angle")
    ising_no_transition = _standard_result("one_dimensional_classical_ising_no_finite_t_transition")
    ising_correlation = _standard_result("one_dimensional_classical_ising_correlation_length")
    lsm = _standard_result("lieb_schultz_mattis_half_integer_constraint")
    eight_vertex = _standard_result("eight_vertex_zero_field_exact_solution_status")
    blume_capel = _standard_result("blume_capel_spin1_zero_temperature_level_crossing")
    potts = _standard_result("square_potts_exact_critical_point")
    six_vertex = _standard_result("square_six_vertex_ice_exact_solution_status")
    toric_code = _standard_result("square_toric_code_exact_topological_degeneracy")
    compass = _standard_result("square_compass_model_directional_exchange_degeneracy")

    assert bilinear_biquadratic_aklt_angle() == pytest.approx(aklt_angle["theta_radians"])
    assert math.tan(bilinear_biquadratic_aklt_angle()) == pytest.approx(aklt_angle["aklt_tan_theta"])
    assert ising_no_transition["finite_temperature_transition"] is False
    assert ising_no_transition["tc_over_j"] == pytest.approx(0.0)
    assert classical_ising_chain_correlation_length(beta=1.0, exchange=1.0) == pytest.approx(
        ising_correlation["correlation_length_beta_1_j_1"]
    )
    assert lsm["unique_ground_state_implies_gapless_excitations"] is True
    assert eight_vertex["is_exactly_solved"] is True
    assert blume_capel_square_zero_temperature_level_crossing() == pytest.approx(
        blume_capel["square_lattice_d_over_j_crossing"]
    )
    assert square_potts_critical_beta_j(q=2) == pytest.approx(math.log(1.0 + math.sqrt(2.0)))
    assert potts["continuous_for_q_le_4"] is True
    assert six_vertex["is_exactly_solved"] is True
    assert toric_code["torus_ground_state_degeneracy"] == 4
    assert compass["has_line_flip_symmetries"] is True


def test_stored_additional_exact_and_formula_results_match_local_helpers():
    ashkin_teller = _standard_result("square_ashkin_teller_exact_critical_line")
    pyrochlore_entropy = _standard_result("pyrochlore_dipolar_spin_ice_pauling_entropy")
    sawtooth = _standard_result("sawtooth_chain_localized_magnon_flat_band")
    diamond_chain = _standard_result("diamond_chain_localized_magnon_flat_band")
    lieb_lattice = _standard_result("lieb_lattice_heisenberg_ferrimagnet_reference")
    xx_chain = _standard_result("xx_spin_half_chain_free_fermion_energy")
    xy_chain = _standard_result("xy_spin_half_chain_anisotropic_critical_line")
    lieb_liniger = _standard_result("lieb_liniger_delta_bose_gas_bethe_reference")
    gaudin_yang = _standard_result("gaudin_yang_spin_half_fermion_bethe_reference")
    triangular_ising = _standard_result("triangular_ising_ferromagnet_exact_tc")
    honeycomb_ising = _standard_result("honeycomb_ising_ferromagnet_exact_tc")
    kagome_ising = _standard_result("kagome_ising_ferromagnet_exact_tc")

    assert ashkin_teller["has_exact_critical_line"] is True
    expected_pauling_entropy = pyrochlore_entropy["pauling_entropy_per_spin"]
    assert pauling_spin_ice_entropy_per_spin() == pytest.approx(expected_pauling_entropy)
    assert expected_pauling_entropy == pytest.approx(0.5 * math.log(1.5))
    assert localized_magnon_status("sawtooth_chain") == sawtooth["has_exact_localized_magnons"]
    assert localized_magnon_status("diamond_chain") == diamond_chain["has_exact_localized_magnons"]
    assert lieb_lattice_ground_state_spin_per_unit_cell(2, 1) == pytest.approx(
        lieb_lattice["ground_state_spin_per_unit_cell"]
    )
    assert xx_spin_half_chain_free_fermion_energy_per_site(exchange=1.0) == pytest.approx(
        xx_chain["energy_per_site"]
    )
    critical_line = xy_spin_half_chain_critical_line()
    assert critical_line["ising_critical_field"] == pytest.approx(xy_chain["ising_critical_field"])
    assert critical_line["anisotropy_transition_gamma"] == pytest.approx(
        xy_chain["anisotropy_transition_gamma"]
    )
    assert exact_solution_status("lieb_liniger") == lieb_liniger["is_exactly_solved"]
    assert exact_solution_status("gaudin_yang") == gaudin_yang["is_exactly_solved"]
    assert lieb_liniger["tonks_girardeau_limit_maps_to_free_fermions"] is True
    assert ising_ferromagnet_tc("triangular", exchange=1.0) == pytest.approx(triangular_ising["tc_over_j"])
    assert ising_ferromagnet_tc("honeycomb", exchange=1.0) == pytest.approx(honeycomb_ising["tc_over_j"])
    assert ising_ferromagnet_tc("kagome", exchange=1.0) == pytest.approx(kagome_ising["tc_over_j"])


def test_stored_remaining_exact_and_formula_results_match_local_helpers():
    honeycomb_phase = _standard_result("honeycomb_j1_j2_j3_classical_phase_diagram")
    pyrochlore_exchange = _standard_result("pyrochlore_anisotropic_exchange_jzz_jpm_reference")
    tb = _standard_result("takhtajan_babujian_spin1_critical_point")
    uls = _standard_result("uimin_lai_sutherland_spin1_su3_point")
    quantum_spin_ice = _standard_result("quantum_spin_ice_u1_qsl_reference")
    ruby = _standard_result("ruby_lattice_heisenberg_flat_band_reference")
    haldane_shastry = _standard_result("haldane_shastry_chain_exact_ground_state")
    kane_mele = _standard_result("honeycomb_haldane_kane_mele_hubbard_spin_model_reference")
    spin_peierls = _standard_result("spin_peierls_chain_dimerization_reference")
    triangular_af_ising = _standard_result("triangular_ising_antiferromagnet_residual_entropy")
    square_ff_ising = _standard_result("square_fully_frustrated_ising_residual_entropy_reference")
    kagome_af_ising = _standard_result("kagome_ising_antiferromagnet_residual_entropy_reference")

    assert honeycomb_j1_j2_j3_classical_phase_labels() == honeycomb_phase["phases"]
    assert anisotropic_exchange_coupling_labels("pyrochlore") == pyrochlore_exchange["couplings"]
    assert spin1_bilinear_biquadratic_integrable_angle("takhtajan_babujian") == pytest.approx(
        tb["theta_radians"]
    )
    assert tb["is_integrable"] is True
    assert spin1_bilinear_biquadratic_integrable_angle("uimin_lai_sutherland") == pytest.approx(
        uls["theta_radians"]
    )
    assert uls["su3_symmetric"] is True
    ring_exchange = quantum_spin_ice_strong_coupling_ring_exchange(jzz=1.0, jpm=0.1)
    assert ring_exchange["ring_exchange_amplitude"] == pytest.approx(0.012)
    assert ring_exchange["u1_quantum_spin_liquid_candidate"] == quantum_spin_ice[
        "u1_quantum_spin_liquid_candidate"
    ]
    assert quantum_spin_ice_strong_coupling_ring_exchange(jzz=1.0, jpm=0.0)[
        "u1_quantum_spin_liquid_candidate"
    ] is False
    assert localized_magnon_status("ruby_lattice") == ruby["supports_localized_magnons"]
    assert haldane_shastry_exact_ground_state_status() == haldane_shastry["has_exact_jastrow_ground_state"]
    assert spin_orbit_induced_anisotropy_status("haldane_kane_mele_hubbard") == kane_mele[
        "spin_orbit_induced_anisotropy"
    ]
    assert spin_gap_opens_with_dimerization_status() == spin_peierls["finite_delta_opens_gap"]
    assert triangular_ising_antiferromagnet_residual_entropy_per_spin() == pytest.approx(
        triangular_af_ising["residual_entropy_per_spin"],
        abs=1.0e-6,
    )
    assert ising_macroscopic_degeneracy_status("square_fully_frustrated") == square_ff_ising[
        "macroscopic_ground_state_degeneracy"
    ]
    assert ising_macroscopic_degeneracy_status("kagome_antiferromagnet") == kagome_af_ising[
        "macroscopic_ground_state_degeneracy"
    ]


def test_stored_fcc_orders_and_bcc_large_j2_collinear_claim_match_local_energies():
    fcc = _standard_result("fcc_j1_j2_heisenberg_type_order_reference")
    bcc = _standard_result("bcc_j1_j2_heisenberg_collinear_reference")

    fcc_type_i = fcc_j1_j2_classical_order_energies(j1=1.0, j2=-0.2)
    fcc_type_ii = fcc_j1_j2_classical_order_energies(j1=1.0, j2=1.0)
    fcc_type_iii = fcc_j1_j2_classical_order_energies(j1=1.0, j2=0.2)
    bcc_collinear = bcc_j1_j2_classical_order_energies(j1=-1.0, j2=1.0)

    assert fcc_type_i["minimum_order"] == "type_I"
    assert fcc_type_ii["minimum_order"] == "type_II"
    assert fcc_type_iii["minimum_order"] == "type_III"
    assert sorted(fcc["common_orders"]) == ["type_I", "type_II", "type_III"]
    assert bcc_collinear["minimum_order"] == "collinear"
    assert bcc_collinear["energies"]["collinear"] < bcc_collinear["energies"]["neel"]
    assert bcc["large_j2_collinear_order"] is True


def test_stored_triangular_xxz_supersolid_reference_matches_three_sublattice_variational_formula():
    result = _standard_result("triangular_xxz_supersolid_phase_reference")
    status = spin_benchmarks.triangular_xxz_three_sublattice_supersolid_status(
        jz=1.0,
        jxy=0.8,
        field=1.0,
    )

    assert status["contains_supersolid_phase"] is result["contains_supersolid_phase"]
    assert status["phase_representative"] == "canted_uud_supersolid"
    assert status["canted_sublattice_magnetization"] == pytest.approx(20.0 / 27.0)
    assert status["longitudinal_sublattice_imbalance"] > 0.7
    assert status["transverse_order_parameter"] > 0.4
    assert status["supersolid_energy_per_site"] == pytest.approx(-1.4543209876543213)
    assert status["supersolid_energy_per_site"] < status["uud_solid_energy_per_site"]
    assert status["supersolid_energy_per_site"] < status["uniform_120_superfluid_energy_per_site"]


def test_stored_pyrochlore_checkerboard_and_kitaev_formula_results_match_local_helpers():
    kitaev = _standard_result("kitaev_honeycomb_exact_spin_liquid_limit")
    kitaev_field = _standard_result("kitaev_honeycomb_abelian_nonabelian_field_gap_reference")
    pyrochlore_flat = _standard_result("pyrochlore_heisenberg_coulomb_phase_flat_band")
    pyrochlore_constraint = _standard_result("pyrochlore_heisenberg_afm_coulomb_phase_reference")
    checkerboard_constraint = _standard_result("checkerboard_heisenberg_afm_planar_pyrochlore_reference")

    assert exact_solution_status("kitaev_honeycomb") == kitaev["is_exactly_solvable"]
    assert kitaev["isotropic_phase"] == "gapless_spin_liquid"
    assert kitaev_field_induced_gap_status(field_components=(0.1, 0.2, 0.3)) == kitaev_field[
        "field_opens_non_abelian_gap"
    ]
    assert kitaev_field_induced_gap_status(field_components=(0.1, 0.0, 0.3)) is False
    assert pyrochlore_flat["lowest_lt_flat_band"] is True
    assert pyrochlore_flat["local_constraint"] == "sum_tetrahedron_spins_zero"
    assert pyrochlore_tetrahedron_zero_sum_constraint_status(
        [[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, -1.0, 0.0]]
    ) == pyrochlore_constraint["zero_total_spin_per_tetrahedron"]
    assert pyrochlore_tetrahedron_heisenberg_energy_identity(
        [[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, -1.0, 0.0]],
        exchange=1.0,
    ) == pytest.approx(-2.0)
    assert checkerboard_crossed_plaquette_ground_state_constraint_status(
        [[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, -1.0, 0.0]]
    ) == checkerboard_constraint["zero_total_spin_per_crossed_plaquette"]


def test_stored_honeycomb_kitaev_heisenberg_four_phase_labels_match_local_helper():
    result = _standard_result("honeycomb_kitaev_heisenberg_four_sublattice_phases")

    assert honeycomb_kitaev_heisenberg_classical_phase_labels() == result["ordered_phases"]


def test_stored_q_state_clock_bkt_transition_count_matches_local_rg_rule():
    result = _standard_result("square_clock_q5_two_bkt_transitions")
    summary = clock_model_bkt_transition_summary(q=5)

    assert summary["transition_count"] == result["transition_count"]
    assert summary["phase_sequence"] == result["phase_sequence"]
    assert clock_model_bkt_transition_summary(q=4)["transition_count"] == 1


def test_stored_spin_ladder_gap_claim_matches_local_strong_rung_limit():
    result = _standard_result("spin_ladder_rung_singlet_gap_reference")
    status = spin_ladder_strong_rung_gap_status(j_rung=1.0, j_leg=0.0)

    assert status["has_finite_spin_gap_for_antiferromagnetic_rungs"] == result[
        "has_finite_spin_gap_for_antiferromagnetic_rungs"
    ]
    assert status["rung_singlet_energy"] == pytest.approx(-0.75)
    assert status["rung_triplet_energy"] == pytest.approx(0.25)
    assert status["rung_gap"] == pytest.approx(1.0)
    assert spin_ladder_strong_rung_gap_status(j_rung=-1.0, j_leg=0.0)[
        "has_finite_spin_gap_for_antiferromagnetic_rungs"
    ] is False


def test_stored_cacu2o3_spin_ladder_material_matches_local_strong_rung_model():
    result = _standard_result("cacu2o3_spin_ladder_reference")
    status = spin_ladder_strong_rung_gap_status(j_rung=1.0, j_leg=0.0)

    assert status["spin_ladder_material"] == result["spin_ladder_material"]
    assert status["strong_rung_limit"] is True
    assert status["rung_gap"] == pytest.approx(1.0)
    assert spin_ladder_strong_rung_gap_status(j_rung=0.0, j_leg=1.0)[
        "spin_ladder_material"
    ] is False


def test_stored_fe8_tunneling_reference_matches_single_cluster_ed():
    result = _standard_result("fe8_molecular_spin_tunneling_reference")

    assert fe8_single_molecule_tunnel_splitting(spin=10, anisotropy_d=0.292, anisotropy_e=0.046) > 0.0
    assert fe8_single_molecule_tunnel_splitting(spin=10, anisotropy_d=0.292, anisotropy_e=0.0) == pytest.approx(
        0.0,
        abs=1.0e-12,
    )
    assert result["macroscopic_quantum_tunneling_observed"] is True


def test_stored_triangular_and_kagome_one_third_plateaus_match_local_triangle_ed():
    triangular = _standard_result("triangular_heisenberg_magnetization_plateau_reference")
    kagome = _standard_result("kagome_one_third_magnetization_plateau_reference")
    interval = spin_half_triangle_one_third_plateau_interval(exchange=1.0)

    assert interval["plateau_fraction"] == pytest.approx(1.0 / 3.0)
    assert interval["field_lower"] == pytest.approx(0.0)
    assert interval["field_upper"] == pytest.approx(1.5)
    assert interval["field_upper"] > interval["field_lower"]
    assert triangular["one_third_plateau"] is True
    assert kagome["one_third_plateau"] is True


def test_stored_material_one_third_plateaus_match_local_small_cluster_limits():
    ba3cosb2o9 = _standard_result("ba3cosb2o9_triangular_plateau_reference")
    azurite = _standard_result("azurite_diamond_chain_plateau_reference")
    triangle_interval = spin_half_triangle_one_third_plateau_interval(exchange=1.0)

    assert triangle_interval["plateau_fraction"] == pytest.approx(1.0 / 3.0)
    assert triangle_interval["field_upper"] > triangle_interval["field_lower"]
    assert ba3cosb2o9["one_third_magnetization_plateau"] is True

    azurite_status = diamond_chain_dimer_monomer_one_third_plateau_status(
        dimer_exchange=1.0,
        monomer_coupling=0.0,
    )
    assert azurite_status["one_third_magnetization_plateau"] is azurite[
        "one_third_magnetization_plateau"
    ]
    assert azurite_status["plateau_fraction"] == pytest.approx(1.0 / 3.0)
    assert azurite_status["dimer_singlet_energy"] == pytest.approx(-0.75)
    assert azurite_status["field_upper"] == pytest.approx(1.0)
    assert diamond_chain_dimer_monomer_one_third_plateau_status(
        dimer_exchange=0.0,
        monomer_coupling=1.0,
    )["one_third_magnetization_plateau"] is False


def test_stored_ba3cosb2o9_plateau_matches_triangular_lattice_finite_cluster_ed():
    result = _standard_result("ba3cosb2o9_triangular_plateau_reference")
    status = spin_benchmarks.triangular_lattice_spin_half_one_third_plateau_ed_status(
        cluster_shapes=((3, 3), (4, 3)),
        exchange=1.0,
    )

    assert status["one_third_magnetization_plateau"] is result[
        "one_third_magnetization_plateau"
    ]
    assert status["plateau_fraction"] == pytest.approx(1.0 / 3.0)
    assert status["plateau_width_by_shape"][(3, 3)] == pytest.approx(1.0)
    assert status["plateau_width_by_shape"][(4, 3)] > 0.5
    assert all(width > 0.0 for width in status["plateau_width_by_shape"].values())


def test_stored_breathing_kagome_trimerization_matches_local_triangle_ed_limit():
    result = _standard_result("breathing_kagome_heisenberg_reference")

    assert breathing_kagome_strong_triangle_trimerization_status(j_up=1.0, j_down=0.0) == result[
        "breathing_anisotropy_controls_trimerization"
    ]
    assert breathing_kagome_strong_triangle_trimerization_status(j_up=1.0, j_down=1.0) is False


def test_stored_honeycomb_ferro_and_af_material_order_matches_local_nn_glt_limit():
    expected_orders = {
        "crcl3_honeycomb_heisenberg_reference": ("ferromagnetic", "ferromagnetic_honeycomb_layers"),
        "cri3_honeycomb_ferromagnet_reference": ("ferromagnetic", "ferromagnetic_order"),
        "crgete3_honeycomb_ferromagnet_reference": ("ferromagnetic", "ferromagnetic_order"),
        "mn_ps3_honeycomb_antiferromagnet_reference": ("neel", "neel_order_reference"),
    }

    for name, (order, result_key) in expected_orders.items():
        result = _standard_result(name)
        assert honeycomb_nearest_neighbor_order_status(order) == result[result_key]

    fecl3 = _standard_result("fecl3_honeycomb_antiferromagnet_reference")
    assert "neel_order_on_honeycomb" not in fecl3


def test_stored_honeycomb_ferro_and_af_material_order_matches_local_nn_fourier_kernel():
    expected_orders = {
        "crcl3_honeycomb_heisenberg_reference": (-1.0, "ferromagnetic", "ferromagnetic_honeycomb_layers"),
        "cri3_honeycomb_ferromagnet_reference": (-1.0, "ferromagnetic", "ferromagnetic_order"),
        "crgete3_honeycomb_ferromagnet_reference": (-1.0, "ferromagnetic", "ferromagnetic_order"),
        "mn_ps3_honeycomb_antiferromagnet_reference": (1.0, "neel", "neel_order_reference"),
    }

    for name, (exchange, expected_order, result_key) in expected_orders.items():
        result = _standard_result(name)
        summary = honeycomb_nearest_neighbor_glt_order_summary(exchange=exchange)

        assert summary["minimum_order"] == expected_order
        assert summary["minimum_kernel_eigenvalue"] == pytest.approx(-3.0)
        assert summary["competing_kernel_eigenvalue"] == pytest.approx(3.0)
        assert result[result_key] is True


def test_stored_honeycomb_zigzag_material_order_matches_local_j1_j3_classical_limit():
    ni_ps3 = _standard_result("ni_ps3_honeycomb_antiferromagnet_reference")
    fe_ps3 = _standard_result("fe_ps3_honeycomb_ising_reference")
    energies = honeycomb_j1_j2_j3_collinear_order_energies(j1=-1.0, j2=0.0, j3=1.0)

    assert min(energies, key=energies.get) == "zigzag"
    assert energies["zigzag"] < energies["ferromagnetic"]
    assert energies["zigzag"] < energies["neel"]
    assert energies["zigzag"] < energies["stripy"]
    assert ni_ps3["zigzag_or_collinear_order_reference"] is True
    assert fe_ps3["ising_like_zigzag_order"] is True


def test_stored_kagome_classical_material_order_matches_local_glt_and_dm_limits():
    haydeeite = _standard_result("haydeeite_ferromagnetic_kagome_reference")
    jarosite = _standard_result("jarosite_kagome_dzyaloshinskii_moriya_reference")

    kagome_ferromagnet = _kagome_nearest_neighbor_model(j1=-1.0)
    gamma_energy = _lowest_kernel_eigenvalue(kagome_ferromagnet, [0.0, 0.0, 0.0])
    for competing_q in ([0.25, 0.125, 0.0], [0.5, 0.5, 0.0]):
        assert gamma_energy < _lowest_kernel_eigenvalue(kagome_ferromagnet, competing_q) - 0.1
    assert haydeeite["ferromagnetic_kagome_exchange"] is True

    heisenberg_triangle = _triangle_nn_classical_model(exchange=1.0)
    q0_spins = _triangle_120_spins(clockwise=False)
    ferromagnetic_spins = np.array([[1.0, 0.0, 0.0]] * 3)
    assert classical_energy(heisenberg_triangle, q0_spins) == pytest.approx(-1.5)
    assert classical_energy(heisenberg_triangle, q0_spins) < classical_energy(
        heisenberg_triangle,
        ferromagnetic_spins,
    ) - 1.0

    dm_triangle = _triangle_dm_classical_model(exchange=1.0, dzyaloshinskii_moriya=0.1)
    clockwise_energy = classical_energy(dm_triangle, _triangle_120_spins(clockwise=True))
    counterclockwise_energy = classical_energy(dm_triangle, _triangle_120_spins(clockwise=False))
    assert clockwise_energy < counterclockwise_energy - 0.5
    assert jarosite["q_0_120_order"] is True


def test_stored_edwardsite_kagome_antiferromagnet_matches_local_120_degree_constraint():
    result = _standard_result("edwardsite_kagome_antiferromagnet_reference")
    spins = np.array(
        [
            [1.0, 0.0, 0.0],
            [-0.5, math.sqrt(3.0) / 2.0, 0.0],
            [-0.5, -math.sqrt(3.0) / 2.0, 0.0],
        ]
    )

    assert result["kagome_antiferromagnet_reference"] is True
    assert np.linalg.norm(np.sum(spins, axis=0)) == pytest.approx(0.0, abs=1.0e-12)
    assert float(np.dot(spins[0], spins[1])) == pytest.approx(-0.5)
    assert float(np.dot(spins[1], spins[2])) == pytest.approx(-0.5)
    assert float(np.dot(spins[0], spins[2])) == pytest.approx(-0.5)


def test_stored_dy2ti2o7_residual_entropy_matches_local_pauling_limit():
    result = _standard_result("dy2ti2o7_spin_ice_entropy_reference")

    assert pauling_spin_ice_entropy_per_spin() == pytest.approx(0.5 * math.log(1.5))
    assert result["pauling_entropy_observed"] is True


def test_stored_dm_spiral_material_pitch_matches_local_single_q_limit():
    ba2cugeo7 = _standard_result("ba2cugeo7_dm_spiral_reference")
    mnsi = _standard_result("mnsi_chiral_helimagnet_reference")

    assert dm_spiral_pitch_reciprocal_lattice_units(exchange=1.0, dzyaloshinskii_moriya=0.25) == pytest.approx(
        math.atan(0.25) / (2.0 * math.pi)
    )
    assert dm_spiral_pitch_reciprocal_lattice_units(exchange=1.0, dzyaloshinskii_moriya=0.1) == pytest.approx(
        math.atan(0.1) / (2.0 * math.pi)
    )
    assert ba2cugeo7["dm_induced_incommensurate_spiral"] is True
    assert mnsi["long_wavelength_helix"] is True


def test_stored_licuvo4_spiral_chain_matches_local_classical_j1_j2_condition():
    result = _standard_result("licuvo4_spiral_chain_reference")
    spiral = j1_j2_chain_classical_spiral_status(j1=-1.0, j2=1.0)
    ferromagnetic_side = j1_j2_chain_classical_spiral_status(j1=-4.5, j2=1.0)

    assert spiral["is_incommensurate_spiral"] == result["incommensurate_spiral_order"]
    assert spiral["pitch_radians"] == pytest.approx(math.acos(0.25))
    assert 0.0 < spiral["pitch_radians"] < math.pi
    assert ferromagnetic_side["is_incommensurate_spiral"] is False
    assert ferromagnetic_side["ordering"] == "ferromagnetic"


def test_stored_li2cuo2_model_matches_local_frustrated_ferromagnetic_chain_condition():
    result = _standard_result("li2cuo2_frustrated_ferromagnetic_chain_reference")
    spiral = j1_j2_chain_classical_spiral_status(j1=-1.0, j2=0.3)

    assert j1_j2_chain_frustrated_ferromagnetic_status(j1=-1.0, j2=0.3) == result[
        "frustrated_ferromagnetic_chain"
    ]
    assert spiral["is_incommensurate_spiral"] is True
    assert spiral["pitch_radians"] == pytest.approx(math.acos(1.0 / 1.2))
    assert j1_j2_chain_frustrated_ferromagnetic_status(j1=-1.0, j2=0.0) is False
    assert j1_j2_chain_frustrated_ferromagnetic_status(j1=1.0, j2=0.3) is False


def test_stored_cs2cucl4_spiral_order_matches_local_anisotropic_triangular_limit():
    result = _standard_result("cs2cucl4_anisotropic_triangular_spiral_reference")
    spiral = anisotropic_triangular_classical_spiral_status(j_chain=1.0, j_zigzag=0.34)

    def energy(q):
        return math.cos(q) + 2.0 * 0.34 * math.cos(0.5 * q)

    q = spiral["ordering_vector_radians"]
    assert spiral["is_incommensurate_spiral"] == result["incommensurate_spiral_order"]
    assert q == pytest.approx(2.0 * math.acos(-0.34 / 2.0))
    assert energy(q) < energy(q - 0.05)
    assert energy(q) < energy(q + 0.05)
    assert energy(q) < energy(math.pi)


def test_nacro2_direct_source_claim_is_not_certified_by_local_nn_120_degree_limit():
    result = _standard_result("nacuo2_triangular_heisenberg_material_reference")
    model = _triangular_lattice_nearest_neighbor_model(j1=1.0)
    k_point = [1.0 / 3.0, 2.0 / 3.0, 0.0]

    assert _single_q_glt_energy(model, k_point) < _single_q_glt_energy(model, [0.0, 0.0, 0.0]) - 1.0
    assert result == {"unconventional_spin_order_reference": True}
    assert "triangular_material_reference" not in result


def test_cu2iro3_direct_source_claim_does_not_create_kitaev_theorem_projection():
    tasks = kitaev_triangle_gapless_condition_verification_tasks()

    assert tasks == []


def test_registry_paper_reference_tasks_cover_the_remaining_reference_claims():
    tasks = paper_reference_verification_tasks()
    task_names = {task["benchmark_name"] for task in tasks}

    assert task_names == {
        "h3liir2o6_kitaev_spin_liquid_candidate_reference",
        "scgo_kagome_bilayer_spin_liquid_reference",
        "garnet_gd3ga5o12_spin_liquid_reference",
        "kagome_heisenberg_topological_entanglement_reference",
        "fe_ps3_honeycomb_ising_reference",
        "ba3irti2o9_honeycomb_kitaev_reference",
        "cu2oseo3_skyrmion_lattice_reference",
    }

    expected = {
        "clean_limit_kitaev_phase_condition": ("h3liir2o6_kitaev_spin_liquid_candidate_reference", "no_magnetic_order_reported", True),
        "dilution_free_cluster_modes": ("scgo_kagome_bilayer_spin_liquid_reference", "no_conventional_order_down_to_low_t", True),
        "dipolar_energy_minima": ("garnet_gd3ga5o12_spin_liquid_reference", "short_range_order_without_simple_lro", True),
        "finite_cylinder_energy": ("kagome_heisenberg_topological_entanglement_reference", "topological_entanglement_entropy", "consistent_with_Z2"),
        "honeycomb_ising_domain_wall_energy": ("fe_ps3_honeycomb_ising_reference", "ising_like_zigzag_order", True),
        "honeycomb_kitaev_limit": ("ba3irti2o9_honeycomb_kitaev_reference", "spin_liquid_candidate", True),
        "triple_q_skyrmion_variational_energy": ("cu2oseo3_skyrmion_lattice_reference", "skyrmion_lattice_phase", True),
    }
    for task in tasks:
        assert task["verification_kind"] == "paper_reference"
        assert task["suggested_backend"] == "paper_summary_or_reference"
        assert task["projection_note"]
        benchmark_name, claim_key, expected_value = expected[task["computable_observable"]]
        assert task["benchmark_name"] == benchmark_name
        assert task["reference_claim_key"] == claim_key
        assert task["expected_reference_claim"] == expected_value


def test_stored_paper_numeric_results_are_kept_as_references_not_silent_solver_claims():
    haldane = _standard_result("haldane_spin1_chain_gap_reference")
    square_qmc = _standard_result("square_spin_half_heisenberg_qmc_energy")
    j1j2_window = _standard_result("j1_j2_square_spin_half_neel_collinear_transition_reference")

    assert haldane["gap_over_j"] == pytest.approx(0.41048)
    assert haldane["tolerance"] <= 5.0e-5
    assert square_qmc["energy_per_site"] == pytest.approx(-0.669437)
    assert square_qmc["tolerance"] <= 5.0e-6
    assert j1j2_window["nonmagnetic_window_approx"] == pytest.approx([0.4, 0.6])


def test_stored_triangular_spin_half_energy_matches_local_periodic_cluster_ed_average():
    result = _standard_result("triangular_heisenberg_spin_half_energy_reference")
    estimate = triangular_spin_half_heisenberg_ed_shape_average_energy(
        cluster_shapes=((4, 4), (5, 4)),
        exchange=1.0,
    )

    assert estimate["cluster_energies_per_site"][(4, 4)] > result["energy_per_site_approx"]
    assert estimate["cluster_energies_per_site"][(5, 4)] < result["energy_per_site_approx"]
    assert estimate["shape_average_energy_per_site"] == pytest.approx(
        result["energy_per_site_approx"],
        abs=result["tolerance"],
    )


def test_stored_j1_j2_chain_okamoto_nomura_critical_point_matches_local_level_spectroscopy_ed():
    result = _standard_result("j1_j2_chain_okamoto_nomura_critical_point")
    estimate = spin_benchmarks.j1_j2_chain_okamoto_nomura_level_spectroscopy_estimate(
        chain_lengths=(8, 10, 12, 14),
        fit_degree=2,
    )

    assert estimate["finite_size_crossings"][8] > estimate["finite_size_crossings"][10]
    assert estimate["finite_size_crossings"][10] > estimate["finite_size_crossings"][12]
    assert estimate["finite_size_crossings"][12] > estimate["finite_size_crossings"][14]
    assert estimate["critical_j2_over_j1"] == pytest.approx(
        result["critical_j2_over_j1"],
        abs=result["tolerance"],
    )
    assert estimate["fit_variable"] == "1/length^2"


def test_stored_j1_j2_chain_bkt_transition_matches_local_level_spectroscopy_ed():
    result = _standard_result("j1_j2_chain_bkt_transition_reference")
    estimate = spin_benchmarks.j1_j2_chain_okamoto_nomura_level_spectroscopy_estimate(
        chain_lengths=(8, 10, 12, 14),
        fit_degree=2,
    )

    assert estimate["critical_j2_over_j1"] == pytest.approx(
        result["critical_j2_over_j1_approx"],
        abs=5.0e-4,
    )


def test_stored_honeycomb_kitaev_gamma_phase_content_matches_local_matrix_and_zigzag_candidates():
    result = _standard_result("honeycomb_kitaev_gamma_phase_diagram_reference")
    content = honeycomb_kitaev_gamma_candidate_phase_content(kitaev=1.0, gamma=0.5)

    assert content["contains_noncollinear_and_zigzag_phases"] is result[
        "contains_noncollinear_and_zigzag_phases"
    ]
    assert content["has_offdiagonal_gamma_mixing"] is True
    assert content["zigzag_ordering_vectors"] == [
        [0.5, 0.0, 0.0],
        [0.0, 0.5, 0.0],
        [0.5, 0.5, 0.0],
    ]


def test_stored_honeycomb_kitaev_gamma_phase_content_matches_local_classical_phase_scan():
    result = _standard_result("honeycomb_kitaev_gamma_phase_diagram_reference")
    scan = spin_benchmarks.honeycomb_kitaev_gamma_classical_phase_content_scan()

    assert scan["contains_noncollinear_and_zigzag_phases"] is result[
        "contains_noncollinear_and_zigzag_phases"
    ]
    assert scan["cluster_shape"] == [2, 2]
    assert scan["site_count"] == 8
    assert scan["bond_count"] == 12

    noncollinear = scan["representative_points"]["noncollinear"]
    assert noncollinear["parameters"] == {"kitaev": 0.0, "gamma": 1.0}
    assert noncollinear["order_class"] == "noncollinear"
    assert noncollinear["energy_per_site"] == pytest.approx(-1.0)
    assert noncollinear["spin_rank"] == 3
    assert sorted(noncollinear["nearest_neighbor_spin_dot_values"]) == pytest.approx(
        [-1.0 / 3.0, 1.0 / 3.0]
    )

    zigzag = scan["representative_points"]["zigzag"]
    assert zigzag["parameters"] == {"kitaev": -1.0, "gamma": 0.5}
    assert zigzag["order_class"] == "zigzag"
    assert zigzag["energy_per_site"] == pytest.approx(
        zigzag["energy_per_site_by_order_class"]["zigzag"]
    )
    assert zigzag["energy_per_site"] < zigzag["energy_per_site_by_order_class"]["neel"]
    assert zigzag["energy_per_site"] < zigzag["energy_per_site_by_order_class"]["ferromagnetic"]


def test_stored_alpha_rucl3_zigzag_reference_matches_local_kitaev_gamma_zigzag_status():
    result = _standard_result("alpha_rucl3_kitaev_gamma_zigzag_reference")
    status = honeycomb_kitaev_gamma_zigzag_reference_status(kitaev=-1.0, gamma=0.5)

    assert status["zigzag_order"] is result["zigzag_order"]
    assert status["kitaev_gamma_model_reference"] is result["kitaev_gamma_model_reference"]
    assert status["zigzag_ordering_vectors"] == [
        [0.5, 0.0, 0.0],
        [0.0, 0.5, 0.0],
        [0.5, 0.5, 0.0],
    ]
    assert status["has_offdiagonal_gamma_mixing"] is True


def test_stored_alpha_rucl3_zigzag_reference_matches_local_kitaev_gamma_energy_enumeration():
    result = _standard_result("alpha_rucl3_kitaev_gamma_zigzag_reference")
    status = spin_benchmarks.honeycomb_kitaev_gamma_zigzag_energy_status(kitaev=-1.0, gamma=0.5)

    assert status["zigzag_order"] is result["zigzag_order"]
    assert status["kitaev_gamma_model_reference"] is result["kitaev_gamma_model_reference"]
    assert "zigzag" in status["minimum_order_classes"]
    assert status["zigzag_energy_per_site"] == pytest.approx(status["minimum_energy_per_site"])
    assert status["energy_per_site_by_order_class"]["zigzag"] < status["energy_per_site_by_order_class"]["neel"]
    assert (
        status["energy_per_site_by_order_class"]["zigzag"]
        < status["energy_per_site_by_order_class"]["ferromagnetic"]
    )
    assert status["has_offdiagonal_gamma_mixing"] is True


def test_stored_na2iro3_kitaev_material_reference_matches_local_zigzag_relevance_status():
    result = _standard_result("honeycomb_j1_j2_kitaev_material_na2iro3_reference")
    status = honeycomb_kitaev_zigzag_relevance_status(kitaev=-1.0, heisenberg=0.2)

    assert status["zigzag_order_relevant"] is result["zigzag_order_relevant"]
    assert status["has_kitaev_exchange"] is True
    assert status["has_heisenberg_exchange"] is True
    assert status["zigzag_ordering_vectors"] == [
        [0.5, 0.0, 0.0],
        [0.0, 0.5, 0.0],
        [0.5, 0.5, 0.0],
    ]


def test_stored_na2iro3_kitaev_material_reference_matches_local_kh_zigzag_energy_enumeration():
    result = _standard_result("honeycomb_j1_j2_kitaev_material_na2iro3_reference")
    status = spin_benchmarks.honeycomb_kitaev_heisenberg_zigzag_energy_status(
        kitaev=-1.0,
        heisenberg=0.2,
    )

    assert status["zigzag_order_relevant"] is result["zigzag_order_relevant"]
    assert "zigzag" in status["minimum_order_classes"]
    assert status["zigzag_energy_per_site"] == pytest.approx(status["minimum_energy_per_site"])
    assert status["energy_per_site_by_order_class"]["zigzag"] < status["energy_per_site_by_order_class"]["neel"]
    assert status["energy_per_site_by_order_class"]["zigzag"] < status["energy_per_site_by_order_class"]["ferromagnetic"]


@pytest.mark.parametrize(
    "name",
    [
        "beta_li2iro3_spiral_kitaev_gamma_reference",
        "gamma_li2iro3_3d_kitaev_reference",
    ],
)
def test_stored_li2iro3_kitaev_gamma_spiral_references_match_local_spiral_candidate_status(name):
    result = _standard_result(name)
    status = kitaev_gamma_spiral_candidate_status(kitaev=-1.0, gamma=0.5, wavevector_component=0.32)

    assert status["incommensurate_spiral_order"] is result["incommensurate_spiral_order"]
    assert status["has_offdiagonal_gamma_mixing"] is True
    assert status["is_incommensurate_wavevector"] is True
    assert status["spiral_candidate_wavevectors"] == [
        [0.32, 0.0, 0.0],
        [0.0, 0.32, 0.0],
        [0.0, 0.0, 0.32],
    ]


@pytest.mark.parametrize(
    "name",
    [
        "beta_li2iro3_spiral_kitaev_gamma_reference",
        "gamma_li2iro3_3d_kitaev_reference",
    ],
)
def test_stored_li2iro3_spiral_references_match_local_kitaev_gamma_spiral_energy_formula(name):
    result = _standard_result(name)
    status = spin_benchmarks.kitaev_gamma_single_q_spiral_energy_status(kitaev=-1.0, gamma=0.5)

    assert status["incommensurate_spiral_order"] is result["incommensurate_spiral_order"]
    assert 0.0 < status["pitch_radians"] < math.pi
    assert status["pitch_radians"] != pytest.approx(math.pi / 2.0)
    assert status["spiral_energy_per_bond"] < status["ferromagnetic_energy_per_bond"]
    assert status["spiral_energy_per_bond"] < status["antiferromagnetic_energy_per_bond"]
    assert status["energy_formula"] == "E(q)=-|K| cos(q)-|Gamma| sin(q)"
    assert spin_benchmarks.kitaev_gamma_single_q_spiral_energy_status(kitaev=-1.0, gamma=0.0)[
        "incommensurate_spiral_order"
    ] is False


def test_stored_kapellasite_kagome_exchange_reference_matches_local_competing_j1_jd_signs():
    result = _standard_result("kapellasite_kagome_j1_jd_reference")
    status = kagome_competing_j1_jd_exchange_status(j1=1.0, jd=-0.5)

    assert status["competing_kagome_exchanges"] is result["competing_kagome_exchanges"]
    assert status["nearest_neighbor_exchange_sign"] == "antiferromagnetic"
    assert status["diagonal_exchange_sign"] == "ferromagnetic"


def test_stored_zncu3oh6cl2_dm_reference_matches_local_dm_relevance_status():
    result = _standard_result("zncu3oh6cl2_kagome_dzyaloshinskii_moriya_reference")
    status = kagome_dm_interaction_relevance_status(exchange=1.0, dzyaloshinskii_moriya=0.1)

    assert status["dm_interaction_relevant"] is result["dm_interaction_relevant"]
    assert status["selected_chirality"] == "clockwise"
    assert status["selected_chirality_energy"] < status["opposite_chirality_energy"]


@pytest.mark.parametrize(
    "name,result_key",
    [
        ("volborthite_kagome_distorted_reference", "distorted_kagome_reference"),
        ("vesignieite_kagome_material_reference", "distorted_kagome_relevant"),
        ("clinoatacamite_distorted_kagome_reference", "distorted_kagome_reference"),
    ],
)
def test_stored_distorted_kagome_references_match_local_exchange_inequivalence_status(name, result_key):
    result = _standard_result(name)
    status = spin_benchmarks.distorted_kagome_exchange_status(
        nearest_neighbor_exchanges=[1.0, 0.82, 0.61],
    )

    assert status[result_key] is result[result_key]
    assert status["is_distorted"] is True
    assert status["inequivalent_exchange_count"] == 3
    assert status["all_antiferromagnetic"] is True
    assert spin_benchmarks.distorted_kagome_exchange_status(
        nearest_neighbor_exchanges=[1.0, 1.0, 1.0],
    )[result_key] is False


def test_stored_barlowite_interlayer_reference_matches_local_nonzero_interlayer_status():
    result = _standard_result("barlowite_kagome_material_reference")
    status = spin_benchmarks.kagome_interlayer_coupling_status(
        kagome_exchange=1.0,
        interlayer_exchange=0.18,
    )

    assert status["interlayer_coupling_relevant"] is result["interlayer_coupling_relevant"]
    assert status["interlayer_to_layer_ratio"] == pytest.approx(0.18)
    assert status["candidate_ordering_vectors"] == [[0.0, 0.0, 0.0], [0.5, 0.5, 0.0]]
    assert spin_benchmarks.kagome_interlayer_coupling_status(
        kagome_exchange=1.0,
        interlayer_exchange=0.0,
    )["interlayer_coupling_relevant"] is False


def test_zn_barlowite_direct_source_claim_is_not_certified_by_arbitrary_exchange_ratio():
    result = _standard_result("zn_barlowite_kagome_qsl_reference")
    status = spin_benchmarks.kagome_interlayer_reduction_status(
        parent_interlayer_exchange=0.18,
        substituted_interlayer_exchange=0.02,
    )

    assert result == {
        "significantly_reduced_interkagome_exchange": True,
        "two_parameter_heisenberg_hamiltonian": True,
    }
    assert "reduced_interlayer_magnetism" not in result
    assert status["reduced_interlayer_magnetism"] is True
    assert status["substituted_to_parent_ratio"] == pytest.approx(0.02 / 0.18)
    assert status["interlayer_reduction_fraction"] == pytest.approx(1.0 - 0.02 / 0.18)
    assert spin_benchmarks.kagome_interlayer_reduction_status(
        parent_interlayer_exchange=0.18,
        substituted_interlayer_exchange=0.18,
    )["reduced_interlayer_magnetism"] is False


def test_stored_hyperhoneycomb_li2iro3_reference_matches_local_kitaev_content_status():
    result = _standard_result("li2iro3_hyperhoneycomb_kitaev_reference")
    status = spin_benchmarks.hyperhoneycomb_kitaev_material_status(
        lattice="hyperhoneycomb",
        kitaev=-1.0,
        gamma=0.5,
    )

    assert status["hyperhoneycomb_kitaev_material"] is result["hyperhoneycomb_kitaev_material"]
    assert status["has_kitaev_exchange"] is True
    assert status["has_offdiagonal_gamma_mixing"] is True
    assert spin_benchmarks.hyperhoneycomb_kitaev_material_status(
        lattice="honeycomb",
        kitaev=-1.0,
        gamma=0.5,
    )["hyperhoneycomb_kitaev_material"] is False


def test_stored_hyperhoneycomb_li2iro3_reference_matches_local_kitaev_gamma_spiral_energy():
    result = _standard_result("li2iro3_hyperhoneycomb_kitaev_reference")
    status = spin_benchmarks.hyperhoneycomb_kitaev_gamma_spiral_energy_status(
        lattice="hyperhoneycomb",
        kitaev=-1.0,
        gamma=0.5,
    )

    assert status["hyperhoneycomb_kitaev_material"] is result["hyperhoneycomb_kitaev_material"]
    assert status["method"] == "single_q_kitaev_gamma_spiral_energy_formula"
    assert status["incommensurate_spiral_order"] is True
    assert status["spiral_energy_per_bond"] < status["ferromagnetic_energy_per_bond"]
    assert status["spiral_energy_per_bond"] < status["antiferromagnetic_energy_per_bond"]
    assert status["has_hyperhoneycomb_lattice"] is True
    assert spin_benchmarks.hyperhoneycomb_kitaev_gamma_spiral_energy_status(
        lattice="honeycomb",
        kitaev=-1.0,
        gamma=0.5,
    )["hyperhoneycomb_kitaev_material"] is False


def test_stored_ru_br3_reference_matches_local_honeycomb_kitaev_candidate_status():
    result = _standard_result("ru_br3_kitaev_material_reference")
    status = spin_benchmarks.ru_honeycomb_kitaev_candidate_status(kitaev=-1.0, gamma=0.5)

    assert status["ru_honeycomb_kitaev_candidate"] is result["ru_honeycomb_kitaev_candidate"]
    assert status["has_offdiagonal_gamma_mixing"] is True
    assert status["zigzag_ordering_vectors"] == [
        [0.5, 0.0, 0.0],
        [0.0, 0.5, 0.0],
        [0.5, 0.5, 0.0],
    ]
    assert spin_benchmarks.ru_honeycomb_kitaev_candidate_status(
        kitaev=0.0,
        gamma=0.5,
    )["ru_honeycomb_kitaev_candidate"] is False


def test_stored_ru_br3_reference_matches_local_honeycomb_kitaev_gamma_zigzag_energy():
    result = _standard_result("ru_br3_kitaev_material_reference")
    status = spin_benchmarks.ru_honeycomb_kitaev_gamma_zigzag_energy_status(
        lattice="honeycomb",
        kitaev=-1.0,
        gamma=0.5,
    )

    assert status["ru_honeycomb_kitaev_candidate"] is result["ru_honeycomb_kitaev_candidate"]
    assert status["method"] == "honeycomb_kitaev_gamma_zigzag_energy_enumeration"
    assert status["zigzag_energy_per_site"] == pytest.approx(status["minimum_energy_per_site"])
    assert status["energy_per_site_by_order_class"]["zigzag"] < status["energy_per_site_by_order_class"]["neel"]
    assert status["energy_per_site_by_order_class"]["zigzag"] < status["energy_per_site_by_order_class"][
        "ferromagnetic"
    ]
    assert spin_benchmarks.ru_honeycomb_kitaev_gamma_zigzag_energy_status(
        lattice="triangular",
        kitaev=-1.0,
        gamma=0.5,
    )["ru_honeycomb_kitaev_candidate"] is False


def test_stored_ho2ti2o7_spin_ice_reference_matches_local_ice_rule_correlations():
    result = _standard_result("ho2ti2o7_spin_ice_neutron_reference")
    status = spin_benchmarks.spin_ice_local_correlation_status(local_axis_ising=True)

    assert status["spin_ice_correlations"] is result["spin_ice_correlations"]
    assert status["ice_rule_state_count"] == 6
    assert status["nearest_neighbor_ising_correlation"] == pytest.approx(-1.0 / 3.0)
    assert spin_benchmarks.spin_ice_local_correlation_status(local_axis_ising=False)[
        "spin_ice_correlations"
    ] is False


def test_stored_bpcb_field_induced_order_matches_local_strong_rung_field_window():
    result = _standard_result("bpcb_spin_ladder_field_induced_order_reference")
    status = spin_benchmarks.spin_ladder_field_induced_luttinger_regime_status(
        j_rung=1.0,
        j_leg=0.2,
        field=1.0,
    )

    assert status["field_induced_luttinger_liquid_regime"] is result[
        "field_induced_luttinger_liquid_regime"
    ]
    assert status["lower_critical_field"] < status["field"] < status["upper_critical_field"]
    assert status["lower_critical_field"] == pytest.approx(0.6)
    assert status["upper_critical_field"] == pytest.approx(1.4)
    assert status["field_window_width"] == pytest.approx(0.8)
    assert status["critical_field_formula"] == "h_c1=J_rung-2J_leg, h_c2=J_rung+2J_leg"
    assert spin_benchmarks.spin_ladder_field_induced_luttinger_regime_status(
        j_rung=1.0,
        j_leg=0.0,
        field=1.0,
    )["field_induced_luttinger_liquid_regime"] is False


def test_checkerboard_long_range_claim_is_not_certified_by_isolated_plaquette_ed():
    result = _standard_result("checkerboard_heisenberg_plaquette_reference")
    status = spin_benchmarks.spin_half_square_plaquette_singlet_status(exchange=1.0)

    assert result == {
        "plaquette_long_range_order": True,
        "valence_bond_crystal": True,
    }
    assert "plaquette_order_candidate" not in result
    assert status["plaquette_order_candidate"] is True
    assert status["ground_state_total_spin_squared"] == pytest.approx(0.0, abs=1.0e-10)
    assert status["singlet_triplet_gap"] > 0.0
    assert spin_benchmarks.spin_half_square_plaquette_singlet_status(exchange=-1.0)[
        "plaquette_order_candidate"
    ] is False


def test_checkerboard_long_range_claim_is_not_certified_by_4x4_plaquette_ed():
    result = _standard_result("checkerboard_heisenberg_plaquette_reference")
    status = spin_benchmarks.checkerboard_heisenberg_plaquette_order_ed_status(
        linear_size=4,
        exchange=1.0,
    )

    assert status["method"] == "periodic_checkerboard_cyclic_plaquette_order_ed"
    assert status["site_count"] == 16
    assert status["basis_dimension"] == 12870
    assert status["ground_energy_per_site"] == pytest.approx(-0.5505677720, abs=1.0e-10)
    assert status["void_plaquette_cyclic_q"] == pytest.approx(0.3991944297, abs=1.0e-10)
    assert status["crossed_plaquette_cyclic_q"] == pytest.approx(-0.1081331725, abs=1.0e-10)
    assert status["cyclic_plaquette_q_contrast"] > 0.5
    assert status["edge_sum_contrast"] == pytest.approx(0.0, abs=1.0e-10)
    assert "plaquette_order_candidate" not in result
    assert status["plaquette_order_candidate"] is True
    assert spin_benchmarks.checkerboard_heisenberg_plaquette_order_ed_status(
        linear_size=4,
        exchange=-1.0,
    )["plaquette_order_candidate"] is False


def test_stored_yb2ti2o7_exchange_reference_matches_local_anisotropic_exchange_labels():
    result = _standard_result("yb2ti2o7_pyrochlore_exchange_reference")
    status = spin_benchmarks.pyrochlore_material_anisotropic_exchange_status(
        exchange_labels=["Jzz", "Jpm", "Jpmpm", "Jzpm"],
    )

    assert status["anisotropic_exchange_fit_reference"] is result["anisotropic_exchange_fit_reference"]
    assert status["recognized_exchange_labels"] == ["Jzz", "Jpm", "Jpmpm", "Jzpm"]
    assert spin_benchmarks.pyrochlore_material_anisotropic_exchange_status(
        exchange_labels=["Jzz"],
    )["anisotropic_exchange_fit_reference"] is False


def test_stored_pr2zr2o7_quantum_spin_ice_reference_matches_local_jzz_jpm_condition():
    result = _standard_result("pr2zr2o7_quantum_spin_ice_reference")
    status = spin_benchmarks.quantum_spin_ice_exchange_candidate_status(jzz=1.0, jpm=0.08)
    ring_exchange = quantum_spin_ice_strong_coupling_ring_exchange(jzz=1.0, jpm=0.08)

    assert status["quantum_spin_ice_candidate"] is result["quantum_spin_ice_candidate"]
    assert ring_exchange["u1_quantum_spin_liquid_candidate"] is result["quantum_spin_ice_candidate"]
    assert ring_exchange["ring_exchange_amplitude"] == pytest.approx(12.0 * 0.08**3)
    assert status["has_ice_rule_jzz"] is True
    assert status["has_transverse_quantum_exchange"] is True
    assert spin_benchmarks.quantum_spin_ice_exchange_candidate_status(jzz=-1.0, jpm=0.08)[
        "quantum_spin_ice_candidate"
    ] is False


@pytest.mark.parametrize(
    "name,result_key",
    [
        ("gadolinium_gallium_garnet_hyperkagome_reference", "strong_frustration"),
        ("garnet_gd3te2li3o12_hyperkagome_reference", "garnet_frustrated_magnet"),
    ],
)
def test_stored_garnet_frustration_references_match_local_hyperkagome_condition(name, result_key):
    result = _standard_result(name)
    status = spin_benchmarks.garnet_hyperkagome_frustration_status(
        lattice="hyperkagome_garnet",
        heisenberg_exchange=1.0,
        dipolar_exchange=0.2,
    )

    assert status[result_key] is result[result_key]
    assert status["is_hyperkagome_garnet"] is True
    assert status["has_competing_dipolar_exchange"] is True
    assert spin_benchmarks.garnet_hyperkagome_frustration_status(
        lattice="chain",
        heisenberg_exchange=1.0,
        dipolar_exchange=0.2,
    )[result_key] is False


@pytest.mark.parametrize(
    "name,result_key",
    [
        ("gadolinium_gallium_garnet_hyperkagome_reference", "strong_frustration"),
        ("garnet_gd3te2li3o12_hyperkagome_reference", "garnet_frustrated_magnet"),
    ],
)
def test_stored_garnet_frustration_references_match_triangle_constraint_calculation(name, result_key):
    result = _standard_result(name)
    status = spin_benchmarks.garnet_hyperkagome_triangle_constraint_status(
        lattice="hyperkagome_garnet",
        triangles_per_unit_cell=8,
        sites_per_unit_cell=24,
        spin_components=3,
        heisenberg_exchange=1.0,
        dipolar_exchange=0.2,
    )

    assert status[result_key] is result[result_key]
    assert status["triangle_constraint_identity"] == "H = J/2 sum_delta |S_delta|^2 + const"
    assert status["is_hyperkagome_garnet"] is True
    assert status["is_macroscopically_underconstrained"] is True
    assert status["estimated_zero_sum_manifold_dimension"] == 24
    assert status["has_antiferromagnetic_heisenberg"] is True
    assert status["has_competing_dipolar_exchange"] is True
    assert spin_benchmarks.garnet_hyperkagome_triangle_constraint_status(
        lattice="chain",
        triangles_per_unit_cell=8,
        sites_per_unit_cell=24,
        spin_components=3,
        heisenberg_exchange=1.0,
        dipolar_exchange=0.2,
    )[result_key] is False


def test_stored_er2ti2o7_order_by_disorder_matches_local_xy_anisotropy_selector():
    result = _standard_result("er2ti2o7_xy_pyrochlore_order_by_disorder_reference")
    status = spin_benchmarks.xy_pyrochlore_order_by_disorder_status(
        local_xy_anisotropy=True,
        fluctuation_selection_strength=0.05,
    )

    assert status["psi2_order_selected"] is result["psi2_order_selected"]
    assert status["has_local_xy_manifold"] is True
    assert status["has_order_by_disorder_selector"] is True
    assert status["clock_anisotropy_formula"] == "E(phi)=-A*cos(6phi)"
    assert status["psi2_clock_energy"] == pytest.approx(-0.05)
    assert status["psi3_clock_energy"] == pytest.approx(0.05)
    assert status["selected_state"] == "psi2"
    assert status["selection_energy_gain"] > 0.0
    assert spin_benchmarks.xy_pyrochlore_order_by_disorder_status(
        local_xy_anisotropy=True,
        fluctuation_selection_strength=0.0,
    )["psi2_order_selected"] is False


def test_stored_spin1_large_d_transition_matches_local_level_crossing_condition():
    result = _standard_result("spin1_chain_large_d_transition_reference")
    status = spin_benchmarks.spin1_large_d_transition_status(exchange=1.0, single_ion_anisotropy=1.2)

    assert status["large_d_transition_reference"] is result["large_d_transition_reference"]
    assert status["single_ion_anisotropy_dominates_exchange"] is True
    assert spin_benchmarks.spin1_large_d_transition_status(
        exchange=1.0,
        single_ion_anisotropy=0.0,
    )["large_d_transition_reference"] is False


def test_stored_spin1_large_d_transition_matches_local_finite_size_gap_scan_ed():
    result = _standard_result("spin1_chain_large_d_transition_reference")
    status = spin_benchmarks.spin1_large_d_finite_size_gap_scan_status(
        chain_lengths=(6, 8, 10),
        anisotropy_values=(0.0, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0),
        exchange=1.0,
    )

    assert status["large_d_transition_reference"] is result["large_d_transition_reference"]
    assert status["gap_minimum_softens_with_size"] is True
    assert status["minimum_gap_anisotropy_by_length"] == {6: 1.0, 8: 1.0, 10: 1.0}
    assert status["minimum_gap_by_length"][10] < status["minimum_gap_by_length"][8]
    assert status["minimum_gap_by_length"][8] < status["minimum_gap_by_length"][6]
    for length in (6, 8, 10):
        assert status["zero_anisotropy_gap_by_length"][length] > status["minimum_gap_by_length"][length]
        assert status["large_anisotropy_gap_by_length"][length] > status["minimum_gap_by_length"][length]


def test_stored_shastry_sutherland_plateaus_match_local_dimer_plateau_motif():
    result = _standard_result("shastry_sutherland_magnetization_plateaus_reference")
    status = spin_benchmarks.shastry_sutherland_dimer_plateau_status(
        dimer_exchange=1.0,
        interdimer_exchange=0.0,
        plateau_fraction=0.5,
    )

    assert status["fractional_plateaus_observed"] is result["fractional_plateaus_observed"]
    assert status["orthogonal_dimer_limit"] is True
    assert status["is_fractional_plateau"] is True
    assert status["singlet_energy_per_dimer"] == pytest.approx(-0.75)
    assert status["triplet_mz1_energy_at_zero_field"] == pytest.approx(0.25)
    assert status["dimer_gap_field"] == pytest.approx(1.0)
    assert spin_benchmarks.shastry_sutherland_dimer_plateau_status(
        dimer_exchange=1.0,
        interdimer_exchange=0.0,
        plateau_fraction=1.0,
    )["fractional_plateaus_observed"] is False


def test_stored_sr_cu2_bo3_2_reference_matches_local_shastry_sutherland_material_status():
    result = _standard_result("sr_cu2_bo3_2_shastry_sutherland_material_reference")
    status = spin_benchmarks.shastry_sutherland_material_status(
        material_context=True,
        dimer_exchange=1.0,
        interdimer_exchange=0.0,
        plateau_fraction=0.5,
    )

    assert status["orthogonal_dimer_material"] is result["orthogonal_dimer_material"]
    assert status["magnetization_plateaus"] is result["magnetization_plateaus"]
    assert status["orthogonal_dimer_limit"] is True
    assert status["is_fractional_plateau"] is True
    assert status["plateau_fraction"] == pytest.approx(0.5)
    assert status["singlet_energy_per_dimer"] == pytest.approx(-0.75)
    assert status["dimer_gap_field"] == pytest.approx(1.0)
    assert spin_benchmarks.shastry_sutherland_material_status(
        material_context=True,
        dimer_exchange=1.0,
        interdimer_exchange=0.0,
        plateau_fraction=1.0,
    )["magnetization_plateaus"] is False


def test_stored_herbertsmithite_reference_matches_local_kagome_material_qsl_candidate_status():
    result = _standard_result("herbertsmithite_kagome_qsl_reference")
    status = spin_benchmarks.kagome_material_qsl_candidate_status(
        lattice="kagome",
        material_context=True,
        frustrated_geometry=True,
        spin_liquid_label=True,
    )

    assert status["qsl_candidate"] is result["qsl_candidate"]
    assert status["has_kagome_geometry"] is True
    assert status["has_material_context"] is True
    assert spin_benchmarks.kagome_material_qsl_candidate_status(
        lattice="square",
        material_context=True,
        frustrated_geometry=True,
        spin_liquid_label=True,
    )["qsl_candidate"] is False


def test_stored_tb2ti2o7_reference_matches_local_pyrochlore_material_spin_liquid_candidate_status():
    result = _standard_result("tb2ti2o7_pyrochlore_spin_liquid_reference")
    status = spin_benchmarks.pyrochlore_material_spin_liquid_candidate_status(
        lattice="pyrochlore",
        anisotropic_exchange=True,
        material_context=True,
        spin_liquid_label=True,
    )

    assert status["spin_liquid_candidate"] is result["spin_liquid_candidate"]
    assert status["has_pyrochlore_geometry"] is True
    assert status["has_anisotropic_exchange"] is True
    assert spin_benchmarks.pyrochlore_material_spin_liquid_candidate_status(
        lattice="pyrochlore",
        anisotropic_exchange=False,
        material_context=True,
        spin_liquid_label=True,
    )["spin_liquid_candidate"] is False


def test_tb2ti2o7_spin_liquid_reference_is_not_reproduced_by_local_tetrahedron_probe():
    result = _standard_result("tb2ti2o7_pyrochlore_spin_liquid_reference")
    status = spin_benchmarks.tb2ti2o7_local_tetrahedron_negative_probe_status(
        local_axis_ising=True,
        exchange_labels=("Jzz", "Jpm", "Jpmpm", "Jzpm"),
    )

    assert result["spin_liquid_candidate"] is True
    assert status["method"] == "local_pyrochlore_tetrahedron_ice_rule_negative_probe"
    assert status["ice_rule_state_count"] == 6
    assert status["nearest_neighbor_ising_correlation"] == pytest.approx(-1.0 / 3.0)
    assert status["recognized_exchange_labels"] == ["Jzz", "Jpm", "Jpmpm", "Jzpm"]
    assert status["reproduces_registered_tb2ti2o7_spin_liquid"] is False
    assert "local tetrahedron" in status["negative_evidence"]


@pytest.mark.parametrize(
    "name,result_key,material_context",
    [
        ("hyperkagome_heisenberg_spin_liquid_reference", "spin_liquid_candidate", False),
        ("na4ir3o8_hyperkagome_material_reference", "hyperkagome_qsl_candidate", True),
    ],
)
def test_stored_hyperkagome_references_match_local_hyperkagome_candidate_status(
    name,
    result_key,
    material_context,
):
    result = _standard_result(name)
    status = spin_benchmarks.hyperkagome_spin_liquid_candidate_status(
        lattice="hyperkagome",
        heisenberg_exchange=1.0,
        material_context=material_context,
        spin_liquid_label=True,
    )

    assert status[result_key] is result[result_key]
    assert status["has_hyperkagome_geometry"] is True
    assert status["has_antiferromagnetic_heisenberg"] is True
    assert spin_benchmarks.hyperkagome_spin_liquid_candidate_status(
        lattice="kagome",
        heisenberg_exchange=1.0,
        material_context=material_context,
        spin_liquid_label=True,
    )[result_key] is False


def test_stored_hyperkagome_spin_liquid_reference_matches_triangle_constraint_calculation():
    result = _standard_result("hyperkagome_heisenberg_spin_liquid_reference")
    status = spin_benchmarks.hyperkagome_corner_sharing_triangle_constraint_status(
        triangles_per_unit_cell=4,
        sites_per_unit_cell=12,
        spin_components=3,
        heisenberg_exchange=1.0,
    )

    assert status["spin_liquid_candidate"] is result["spin_liquid_candidate"]
    assert status["triangle_constraint_identity"] == "H = J/2 sum_delta |S_delta|^2 + const"
    assert status["can_satisfy_zero_triangle_sum"] is True
    assert status["constraint_count"] == 12
    assert status["spin_component_count"] == 36
    assert status["unconstrained_classical_degrees_of_freedom"] == 24
    assert status["estimated_zero_sum_manifold_dimension"] == 12
    assert status["is_macroscopically_underconstrained"] is True


def test_stored_ca10_reference_matches_local_bilayer_breathing_kagome_exchange_status():
    result = _standard_result("ca10cr7o28_bilayer_breathing_kagome_reference")
    status = spin_benchmarks.bilayer_breathing_kagome_exchange_status(
        lattice="bilayer_kagome",
        exchange_values=[-1.0, 0.4, 0.8],
        material_context=True,
        spin_liquid_label=True,
    )

    assert status["spin_liquid_candidate"] is result["spin_liquid_candidate"]
    assert status["mixed_ferromagnetic_antiferromagnetic_exchanges"] is result[
        "mixed_ferromagnetic_antiferromagnetic_exchanges"
    ]
    assert status["has_bilayer_kagome_geometry"] is True
    assert spin_benchmarks.bilayer_breathing_kagome_exchange_status(
        lattice="bilayer_kagome",
        exchange_values=[0.4, 0.8],
        material_context=True,
        spin_liquid_label=True,
    )["mixed_ferromagnetic_antiferromagnetic_exchanges"] is False


def test_stored_ca10_reference_matches_local_bilayer_breathing_kagome_glt_model():
    result = _standard_result("ca10cr7o28_bilayer_breathing_kagome_reference")
    status = spin_benchmarks.bilayer_breathing_kagome_glt_status(
        ferromagnetic_triangle_exchange=-1.0,
        antiferromagnetic_triangle_exchange=0.45,
        interlayer_exchange=0.25,
    )

    assert status["method"] == "bilayer_breathing_kagome_fourier_exchange_kernel"
    assert status["mixed_ferromagnetic_antiferromagnetic_exchanges"] is result[
        "mixed_ferromagnetic_antiferromagnetic_exchanges"
    ]
    assert status["spin_liquid_candidate"] is result["spin_liquid_candidate"]
    assert status["kernel_dimension"] == 6
    assert status["lowest_mode_energy"] < status["ferromagnetic_q0_mode_energy"]
    assert status["has_nontrivial_luttinger_tisza_minimum"] is True
    assert status["linear_spin_wave_modes"] == pytest.approx([0.0, 1.0])


def test_cu2iro3_direct_source_claim_is_not_certified_by_assumed_kh_parameters():
    result = _standard_result("cu2iro3_honeycomb_kitaev_reference")
    status = spin_benchmarks.honeycomb_kitaev_material_status(
        lattice="honeycomb",
        material_context=True,
        kitaev=1.0,
        heisenberg=0.25,
    )

    assert result == {"honeycomb_frustrated_iridate_identity": True}
    assert "honeycomb_iridate_reference" not in result
    assert status["honeycomb_iridate_reference"] is True
    assert status["has_honeycomb_geometry"] is True
    assert status["has_kitaev_exchange"] is True
    assert spin_benchmarks.honeycomb_kitaev_material_status(
        lattice="honeycomb",
        material_context=True,
        kitaev=0.0,
        heisenberg=0.25,
    )["honeycomb_iridate_reference"] is False


def test_cu2iro3_direct_source_claim_is_not_certified_by_assumed_kh_zigzag_energy():
    result = _standard_result("cu2iro3_honeycomb_kitaev_reference")
    status = spin_benchmarks.cu2iro3_honeycomb_kitaev_heisenberg_energy_status(
        lattice="honeycomb",
        material_context=True,
        kitaev=-1.0,
        heisenberg=0.2,
    )

    assert status["method"] == "honeycomb_kitaev_heisenberg_zigzag_energy_enumeration"
    assert "honeycomb_iridate_reference" not in result
    assert status["honeycomb_iridate_reference"] is True
    assert status["has_honeycomb_lattice"] is True
    assert status["has_material_context"] is True
    assert status["has_kitaev_exchange"] is True
    assert status["has_heisenberg_exchange"] is True
    assert status["zigzag_energy_per_site"] == pytest.approx(status["minimum_energy_per_site"])
    assert status["energy_per_site_by_order_class"]["zigzag"] < status["energy_per_site_by_order_class"]["neel"]
    assert status["energy_per_site_by_order_class"]["zigzag"] < status["energy_per_site_by_order_class"][
        "ferromagnetic"
    ]
    assert spin_benchmarks.cu2iro3_honeycomb_kitaev_heisenberg_energy_status(
        lattice="triangular",
        material_context=True,
        kitaev=-1.0,
        heisenberg=0.2,
    )["honeycomb_iridate_reference"] is False


def test_stored_scgo_reference_matches_local_kagome_bilayer_spin_liquid_candidate_status():
    result = _standard_result("scgo_kagome_bilayer_spin_liquid_reference")
    status = spin_benchmarks.kagome_bilayer_spin_liquid_candidate_status(
        lattice="kagome_bilayer",
        material_context=True,
        frustrated_geometry=True,
        no_conventional_order_label=True,
    )

    assert status["no_conventional_order_down_to_low_t"] is result["no_conventional_order_down_to_low_t"]
    assert status["has_kagome_bilayer_geometry"] is True
    assert status["has_material_context"] is True
    assert spin_benchmarks.kagome_bilayer_spin_liquid_candidate_status(
        lattice="kagome_bilayer",
        material_context=True,
        frustrated_geometry=False,
        no_conventional_order_label=True,
    )["no_conventional_order_down_to_low_t"] is False


def test_stored_gdgagarnet_reference_matches_local_garnet_spin_liquid_candidate_status():
    result = _standard_result("garnet_gd3ga5o12_spin_liquid_reference")
    status = spin_benchmarks.garnet_short_range_order_candidate_status(
        lattice="hyperkagome_garnet",
        heisenberg_exchange=1.0,
        dipolar_exchange=0.2,
        material_context=True,
        short_range_order_label=True,
    )

    assert status["short_range_order_without_simple_lro"] is result[
        "short_range_order_without_simple_lro"
    ]
    assert status["is_hyperkagome_garnet"] is True
    assert status["has_competing_dipolar_exchange"] is True
    assert spin_benchmarks.garnet_short_range_order_candidate_status(
        lattice="hyperkagome_garnet",
        heisenberg_exchange=1.0,
        dipolar_exchange=0.0,
        material_context=True,
        short_range_order_label=True,
    )["short_range_order_without_simple_lro"] is False


def test_stored_h3liir2o6_reference_matches_local_disordered_kitaev_candidate_status():
    result = _standard_result("h3liir2o6_kitaev_spin_liquid_candidate_reference")
    status = spin_benchmarks.disordered_honeycomb_kitaev_candidate_status(
        lattice="honeycomb",
        material_context=True,
        disorder=True,
        kitaev=1.0,
        gamma=0.25,
    )

    assert status["no_magnetic_order_reported"] is result["no_magnetic_order_reported"]
    assert status["has_honeycomb_geometry"] is True
    assert status["has_disorder_context"] is True
    assert spin_benchmarks.disordered_honeycomb_kitaev_candidate_status(
        lattice="honeycomb",
        material_context=True,
        disorder=False,
        kitaev=1.0,
        gamma=0.25,
    )["no_magnetic_order_reported"] is False


def test_h3liir2o6_reference_is_not_reproduced_by_clean_kitaev_triangle_probe():
    result = _standard_result("h3liir2o6_kitaev_spin_liquid_candidate_reference")
    status = spin_benchmarks.h3liir2o6_clean_kitaev_negative_probe_status(
        kx=1.0,
        ky=1.0,
        kz=1.0,
        gamma=0.25,
        disorder=True,
    )

    assert result["no_magnetic_order_reported"] is True
    assert status["method"] == "clean_kitaev_triangle_gapless_negative_probe"
    assert status["clean_limit_gapless"] is True
    assert status["triangle_inequality_margins"] == pytest.approx([1.0, 1.0, 1.0])
    assert status["has_gamma_mixing"] is True
    assert status["has_disorder_context"] is True
    assert status["reproduces_registered_h3liir2o6_no_order_observable"] is False
    assert "clean-limit Kitaev" in status["negative_evidence"]


def test_stored_ba3irti2o9_reference_matches_local_honeycomb_kitaev_spin_liquid_candidate_status():
    result = _standard_result("ba3irti2o9_honeycomb_kitaev_reference")
    status = spin_benchmarks.honeycomb_kitaev_spin_liquid_candidate_status(
        lattice="honeycomb",
        material_context=True,
        kitaev=1.0,
        heisenberg=0.25,
        spin_liquid_label=True,
    )

    assert status["spin_liquid_candidate"] is result["spin_liquid_candidate"]
    assert status["has_honeycomb_geometry"] is True
    assert status["has_kitaev_exchange"] is True
    assert spin_benchmarks.honeycomb_kitaev_spin_liquid_candidate_status(
        lattice="honeycomb",
        material_context=True,
        kitaev=1.0,
        heisenberg=0.25,
        spin_liquid_label=False,
    )["spin_liquid_candidate"] is False


def test_ba3irti2o9_reference_is_not_reproduced_by_clean_kitaev_and_curie_weiss_probe():
    result = _standard_result("ba3irti2o9_honeycomb_kitaev_reference")
    status = spin_benchmarks.ba3irti2o9_clean_kitaev_negative_probe_status(
        lattice="honeycomb",
        kitaev=1.0,
        heisenberg=0.25,
        coordination_number=3,
    )

    assert result["spin_liquid_candidate"] is True
    assert status["method"] == "clean_honeycomb_kitaev_curie_weiss_negative_probe"
    assert status["clean_kitaev_limit_exactly_solvable"] is True
    assert status["has_kitaev_exchange"] is True
    assert status["curie_weiss_theta"] == pytest.approx(-1.0)
    assert status["reproduces_registered_ba3irti2o9_spin_liquid"] is False
    assert "clean Kitaev limit" in status["negative_evidence"]


def test_stored_cu2oseo3_reference_matches_local_chiral_skyrmion_candidate_status():
    result = _standard_result("cu2oseo3_skyrmion_lattice_reference")
    status = spin_benchmarks.chiral_skyrmion_lattice_candidate_status(
        lattice="chiral_cubic",
        material_context=True,
        exchange=1.0,
        dzyaloshinskii_moriya=0.2,
        magnetic_field=0.1,
    )

    assert status["skyrmion_lattice_phase"] is result["skyrmion_lattice_phase"]
    assert status["has_chiral_cubic_lattice"] is True
    assert status["has_dm_interaction"] is True
    assert spin_benchmarks.chiral_skyrmion_lattice_candidate_status(
        lattice="chiral_cubic",
        material_context=True,
        exchange=1.0,
        dzyaloshinskii_moriya=0.0,
        magnetic_field=0.1,
    )["skyrmion_lattice_phase"] is False


def test_stored_cu2oseo3_reference_matches_local_skyrmion_lattice_variational_minimization():
    result = _standard_result("cu2oseo3_skyrmion_lattice_reference")
    status = spin_benchmarks.chiral_skyrmion_lattice_variational_minimization_status(
        lattice_size=36,
        exchange=1.0,
        dzyaloshinskii_moriya=0.8,
        magnetic_field=0.3,
        relaxation_steps=1600,
    )

    assert status["method"] == "deterministic_chiral_lattice_variational_relaxation"
    assert status["skyrmion_lattice_phase"] is result["skyrmion_lattice_phase"]
    assert status["best_state"] == "triple_q_m0_5"
    assert abs(status["best_topological_charge"]) >= 1.0
    assert status["best_energy_per_site"] < status["helix_energy_per_site"] - 1.0e-2
    assert status["best_energy_per_site"] < status["ferromagnetic_energy_per_site"] - 1.0e-2


@pytest.mark.parametrize(
    "name,lattice,result_key",
    [
        ("star_lattice_heisenberg_spin_liquid_reference", "star", "spin_liquid_or_valence_bond_reference"),
        ("shuriken_lattice_heisenberg_reference", "shuriken", "square_kagome_reference"),
    ],
)
def test_stored_frustrated_lattice_references_match_local_geometry_status(name, lattice, result_key):
    result = _standard_result(name)
    status = spin_benchmarks.frustrated_lattice_geometry_status(lattice=lattice, exchange=1.0)

    assert status[result_key] is result[result_key]
    assert status["is_frustrated_lattice"] is True
    assert spin_benchmarks.frustrated_lattice_geometry_status(lattice="chain", exchange=1.0)[
        result_key
    ] is False


def test_maple_leaf_long_range_order_claim_is_not_certified_by_geometry_label():
    result = _standard_result("maple_leaf_lattice_heisenberg_reference")
    status = spin_benchmarks.frustrated_lattice_geometry_status(
        lattice="maple_leaf",
        exchange=1.0,
    )

    assert result == {"magnetic_long_range_order": True}
    assert "frustrated_order_reference" not in result
    assert status["frustrated_order_reference"] is True
    assert status["is_frustrated_lattice"] is True


def test_stored_star_lattice_reference_matches_betts_18_site_ed_energy_and_gap():
    result = _standard_result("star_lattice_heisenberg_spin_liquid_reference")
    status = spin_benchmarks.star_lattice_heisenberg_betts_ed_status(
        center_graph="k3_3",
        exchange=1.0,
    )

    assert status["method"] == "betts_star_lattice_spin_half_heisenberg_ed"
    assert status["center_graph"] == "k3_3"
    assert status["site_count"] == 18
    assert status["bond_count"] == 27
    assert status["basis_dimension_sz0"] == math.comb(18, 9)
    assert status["ground_state_singlet"] is True
    assert status["energy_per_bond"] == pytest.approx(-0.3124788370, abs=1.0e-10)
    assert status["literature_energy_per_bond"] == pytest.approx(-0.312479)
    assert status["triplet_gap"] == pytest.approx(0.5787098978, abs=1.0e-10)
    assert status["literature_triplet_gap"] == pytest.approx(0.578710)
    assert status["matches_literature_energy_and_gap"] is True
    assert status["spin_liquid_or_valence_bond_reference"] is result[
        "spin_liquid_or_valence_bond_reference"
    ]


def test_maple_leaf_quantum_long_range_claim_is_not_certified_by_classical_glt():
    result = _standard_result("maple_leaf_lattice_heisenberg_reference")
    status = spin_benchmarks.maple_leaf_classical_glt_order_status(exchange=1.0)

    assert "frustrated_order_reference" not in result
    assert status["frustrated_order_reference"] is True
    assert status["coordination_number"] == 5
    assert status["unit_cell_site_count"] == 6
    assert status["lowest_q_fractional"] == pytest.approx([2.0 / 3.0, 1.0 / 3.0])
    assert status["lowest_kernel_eigenvalue"] == pytest.approx(-1.0 - math.sqrt(3.0))
    assert status["gamma_lowest_eigenvalue"] == pytest.approx(-1.0)
    assert status["lowest_kernel_eigenvalue"] < status["gamma_lowest_eigenvalue"]
    assert spin_benchmarks.maple_leaf_classical_glt_order_status(exchange=-1.0)[
        "frustrated_order_reference"
    ] is False


def test_stored_shuriken_reference_matches_local_square_kagome_flat_band_mode():
    result = _standard_result("shuriken_lattice_heisenberg_reference")
    status = spin_benchmarks.square_kagome_localized_magnon_flat_band_status(lattice="shuriken")

    assert status["square_kagome_reference"] is result["square_kagome_reference"]
    assert status["method"] == "compact_localized_magnon_flat_band_formula"
    assert status["localized_square_amplitudes"] == pytest.approx([1.0, -1.0, 1.0, -1.0])
    assert status["flat_band_eigenvalue"] == pytest.approx(-2.0)
    assert status["residual_norm"] == pytest.approx(0.0, abs=1.0e-12)
    assert status["connector_leakage_norm"] == pytest.approx(0.0, abs=1.0e-12)
    assert spin_benchmarks.square_kagome_localized_magnon_flat_band_status(lattice="chain")[
        "square_kagome_reference"
    ] is False


def test_stored_square_ring_exchange_reference_matches_local_vbs_competition_ed():
    result = _standard_result("square_ring_exchange_neel_vbs_reference")
    status = spin_benchmarks.square_ring_exchange_vbs_competition_ed_status(
        linear_size=4,
        heisenberg_exchange=1.0,
        ring_exchange=0.5,
    )

    assert status["method"] == "periodic_square_cluster_ring_exchange_ed"
    assert status["ring_exchange_drives_vbs_phase"] is result["ring_exchange_drives_vbs_phase"]
    assert status["site_count"] == 16
    assert status["ring_exchange_sign_convention"] == "H = J sum Si.Sj - K sum(P+P^-1)"
    assert status["vbs_structure_factor_with_ring"] > status["vbs_structure_factor_without_ring"]
    assert status["neel_structure_factor_with_ring"] < status["neel_structure_factor_without_ring"]
    assert status["vbs_enhancement_ratio"] > 1.5
    assert spin_benchmarks.square_ring_exchange_vbs_competition_ed_status(
        linear_size=4,
        heisenberg_exchange=1.0,
        ring_exchange=0.0,
    )["ring_exchange_drives_vbs_phase"] is False


def test_stored_triangular_ring_exchange_reference_matches_large_n_spinon_fermi_sea_formula():
    result = _standard_result("triangular_ring_exchange_spin_liquid_reference")
    status = spin_benchmarks.triangular_ring_exchange_large_n_spin_liquid_status(
        j2=1.0,
        j4=2.6,
    )

    assert status["method"] == "triangular_ring_exchange_large_n_mean_field_formula"
    assert status["su_n_mapping"] == {"J": 2.0, "K": 20.8}
    assert status["k_over_j"] == pytest.approx(10.4)
    assert status["pi_over_2_flux_energy_per_site"] == pytest.approx(-0.04032)
    assert status["zero_flux_energy_per_site"] == pytest.approx(-0.25352)
    assert status["dimer_energy_per_site"] == pytest.approx(-0.25)
    assert status["lowest_energy_state"] == "zero_flux_spinon_fermi_sea"
    assert status["zero_flux_state_beats_pi_over_2_flux"] is True
    assert status["zero_flux_state_beats_dimer"] is True
    assert status["formula_boundary_k_over_j_zero_flux_beats_dimer"] == pytest.approx(10.0)
    assert status["formula_boundary_j4_over_j2_zero_flux_beats_dimer"] == pytest.approx(2.5)
    assert status["contains_spin_liquid_region"] is result["contains_spin_liquid_region"]
    assert spin_benchmarks.triangular_ring_exchange_large_n_spin_liquid_status(
        j2=1.0,
        j4=0.0,
    )["contains_spin_liquid_region"] is False


def test_square_jq_deconfined_critical_reference_is_not_reproduced_by_ring_exchange_vbs_probe():
    result = _standard_result("square_jq_model_deconfined_critical_reference")
    status = spin_benchmarks.square_jq_deconfined_critical_negative_probe_status(
        linear_size=4,
        heisenberg_exchange=1.0,
        ring_exchange=0.5,
    )

    assert result["neel_to_vbs_transition"] is True
    assert status["method"] == "periodic_square_cluster_ring_exchange_ed_negative_probe"
    assert status["site_count"] == 16
    assert status["vbs_structure_factor_with_ring"] > status["vbs_structure_factor_without_ring"]
    assert status["neel_structure_factor_with_ring"] < status["neel_structure_factor_without_ring"]
    assert status["reproduces_registered_deconfined_critical_point"] is False
    assert "not the Sandvik J-Q Hamiltonian" in status["negative_evidence"]


def test_square_j1_j2_vbs_reference_is_not_reproduced_by_small_ed_vbs_probe():
    result = _standard_result("j1_j2_square_dqcp_columnar_vbs_reference")
    status = spin_benchmarks.square_j1_j2_vbs_negative_probe_status(
        linear_size=4,
        j1=1.0,
        j2_values=(0.4, 0.5, 0.6),
    )

    assert result["columnar_or_plaquette_vbs_reference"] is True
    assert status["method"] == "periodic_square_j1_j2_ed_negative_vbs_probe"
    assert status["site_count"] == 16
    assert status["j2_values"] == pytest.approx([0.4, 0.5, 0.6])
    assert status["reproduces_registered_columnar_or_plaquette_vbs_reference"] is False
    assert status["vbs_structure_factor_by_j2"][0.5] == pytest.approx(0.1088611532, abs=1.0e-9)
    assert status["neel_structure_factor_by_j2"][0.6] == pytest.approx(0.0879596781, abs=1.0e-9)
    assert status["lowest_sz0_gap_by_j2"][0.6] == pytest.approx(0.1089057516, abs=1.0e-9)
    assert "finite 4x4 ED trend" in status["negative_evidence"]
    assert "not a DMRG/VMC thermodynamic VBS diagnostic" in status["negative_evidence"]


def test_square_j1_j2_j3_quantum_phase_reference_is_not_reproduced_by_classical_glt_probe():
    result = _standard_result("j1_j2_j3_square_quantum_phase_reference")
    status = spin_benchmarks.square_j1_j2_j3_classical_negative_probe_status(
        j1=1.0,
        parameter_points=((0.0, 0.0), (0.5, 0.0), (0.4, 0.3)),
    )

    assert result["multiple_paramagnetic_regions"] is True
    assert status["method"] == "square_j1_j2_j3_classical_fourier_negative_probe"
    assert status["reproduces_registered_multiple_paramagnetic_regions"] is False
    assert status["minimum_label_by_point"][(0.0, 0.0)] == "neel"
    assert "axial_spiral_candidate" in status["degenerate_minimum_labels_by_point"][(0.5, 0.0)]
    assert status["minimum_label_by_point"][(0.4, 0.3)] == "axial_spiral_candidate"
    assert "classical single-q" in status["negative_evidence"]


def test_stored_ybmggao4_reference_matches_local_triangular_anisotropic_candidate_status():
    result = _standard_result("ybmggao4_triangular_spin_liquid_reference")
    status = spin_benchmarks.triangular_anisotropic_exchange_candidate_status(
        lattice="triangular",
        anisotropic_exchange=True,
        disorder_or_material=True,
    )

    assert status["triangular_quantum_spin_liquid_candidate"] is result[
        "triangular_quantum_spin_liquid_candidate"
    ]
    assert status["has_triangular_geometry"] is True
    assert status["has_anisotropic_exchange"] is True
    assert spin_benchmarks.triangular_anisotropic_exchange_candidate_status(
        lattice="square",
        anisotropic_exchange=True,
        disorder_or_material=True,
    )["triangular_quantum_spin_liquid_candidate"] is False


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


def test_stored_square_heisenberg_velocity_matches_renormalized_spin_wave_formula():
    result = _standard_result("square_heisenberg_spin_wave_velocity_reference")
    status = square_nn_afm_renormalized_spin_wave_velocity_status(spin=0.5, exchange=1.0)

    assert status["bare_lsw_velocity_over_j"] == pytest.approx(math.sqrt(2.0))
    assert status["renormalized_spin_wave_velocity_over_j"] == pytest.approx(
        result["renormalized_velocity_over_j_approx"],
        abs=0.01,
    )
    assert status["velocity_matches_registered_approximation"] is True
    assert square_nn_afm_renormalized_spin_wave_velocity_status(
        spin=0.5,
        exchange=1.0,
        velocity_renormalization=1.0,
    )["velocity_matches_registered_approximation"] is False


def test_stored_square_heisenberg_spin_stiffness_matches_renormalized_series_formula():
    result = _standard_result("square_heisenberg_spin_half_spin_stiffness_reference")
    status = square_nn_afm_renormalized_spin_stiffness_status(spin=0.5, exchange=1.0)

    assert status["bare_classical_stiffness_over_j"] == pytest.approx(0.25)
    assert status["renormalized_spin_stiffness_over_j"] == pytest.approx(
        result["rho_s_over_j"],
        abs=result["tolerance"],
    )
    assert status["stiffness_matches_registered_qmc_value"] is True
    assert square_nn_afm_renormalized_spin_stiffness_status(
        spin=0.5,
        exchange=1.0,
        stiffness_renormalization=1.0,
    )["stiffness_matches_registered_qmc_value"] is False


def test_stored_square_heisenberg_staggered_magnetization_matches_renormalized_formula():
    result = _standard_result("square_heisenberg_spin_half_staggered_magnetization_reference")
    status = square_nn_afm_renormalized_staggered_magnetization_status(spin=0.5)

    assert status["bare_classical_staggered_magnetization"] == pytest.approx(0.5)
    assert status["renormalized_staggered_magnetization"] == pytest.approx(
        result["staggered_magnetization"],
        abs=result["tolerance"],
    )
    assert status["magnetization_matches_registered_qmc_value"] is True
    assert square_nn_afm_renormalized_staggered_magnetization_status(
        spin=0.5,
        magnetization_renormalization=1.0,
    )["magnetization_matches_registered_qmc_value"] is False


def test_square_heisenberg_energy_spin_wave_expansion_still_misses_qmc_tolerance():
    result = _standard_result("square_spin_half_heisenberg_qmc_energy")
    status = square_nn_afm_spin_wave_energy_expansion_status(spin=0.5, exchange=1.0)

    assert status["bare_lsw_energy_per_site"] == pytest.approx(-0.657947421, abs=1.0e-9)
    assert status["second_order_spin_wave_energy_per_site"] == pytest.approx(-0.668497421, abs=1.0e-9)
    assert status["registered_energy_per_site"] == pytest.approx(result["energy_per_site"])
    assert status["second_order_absolute_difference_from_registered"] > result["tolerance"]
    assert status["second_order_matches_registered_qmc_value"] is False


def test_square_heisenberg_qmc_finite_size_extrapolation_matches_registered_energy():
    result = _standard_result("square_spin_half_heisenberg_qmc_energy")
    status = spin_benchmarks.square_heisenberg_qmc_finite_size_extrapolation_status()

    assert status["method"] == "published_qmc_finite_size_extrapolation"
    assert status["fit_model"] == "E(L)=E_inf+a/L^3+b/L^4"
    assert status["fit_linear_sizes"] == [10, 12, 14, 16]
    assert status["extrapolated_energy_per_site"] == pytest.approx(-0.6694356592, abs=1.0e-9)
    assert status["registered_energy_per_site"] == pytest.approx(result["energy_per_site"])
    assert status["registered_tolerance"] == pytest.approx(result["tolerance"])
    assert status["absolute_difference_from_registered"] < result["tolerance"]
    assert status["matches_registered_qmc_energy"] is True


def test_kagome_spin_half_heisenberg_small_ed_energies_miss_dmrg_tolerance():
    result = _standard_result("kagome_spin_half_heisenberg_energy_reference")
    status = kagome_spin_half_heisenberg_ed_energy_status(cluster_shapes=((2, 2), (3, 2)))

    assert status["cluster_energies_per_site"][(2, 2)] == pytest.approx(-0.4537396014, abs=1.0e-9)
    assert status["cluster_energies_per_site"][(3, 2)] == pytest.approx(-0.4471261541, abs=1.0e-9)
    assert status["registered_energy_per_site"] == pytest.approx(result["energy_per_site_approx"])
    assert status["registered_tolerance"] == pytest.approx(result["tolerance"])
    assert status["all_clusters_match_registered_dmrg_value"] is False
    assert status["closest_cluster_shape"] == (3, 2)


def test_kagome_spin_half_heisenberg_tenpy_idmrg_energy_reproduces_registered_dmrg_value():
    result = _standard_result("kagome_spin_half_heisenberg_energy_reference")
    status = spin_benchmarks.kagome_spin_half_heisenberg_tenpy_idmrg_energy_status(
        bond_dimension=112,
        unit_cell_length=2,
        circumference=3,
    )

    assert status["method"] == "tenpy_infinite_cylinder_dmrg_energy"
    assert status["unit_cell_length"] == 2
    assert status["circumference"] == 3
    assert status["unit_cell_sites"] == 18
    assert status["actual_bond_dimension"] == 112
    assert status["energy_per_site"] == pytest.approx(-0.4382443152, abs=5.0e-5)
    assert status["registered_energy_per_site"] == pytest.approx(result["energy_per_site_approx"])
    assert status["registered_tolerance"] == pytest.approx(result["tolerance"])
    assert status["absolute_difference_from_registered"] < result["tolerance"]
    assert status["matches_registered_dmrg_energy"] is True
    assert status["max_sweep_truncation_error"] < 2.0e-3


def test_yan_kagome_energy_and_gap_match_tenpy_dmrg_recomputations():
    result = _standard_result("kagome_heisenberg_dmrg_spin_liquid_yan_reference")
    status = spin_benchmarks.kagome_yan_energy_gap_tenpy_dmrg_status(
        energy_bond_dimension=112,
        energy_unit_cell_length=2,
        energy_circumference=3,
        gap_length=6,
        gap_circumference=3,
        gap_bond_dimension=64,
        gap_max_sweeps=10,
    )

    assert status["method"] == "tenpy_idmrg_energy_plus_finite_cylinder_spin_gap"
    assert status["energy_status"]["matches_registered_dmrg_energy"] is True
    assert status["energy_per_site"] == pytest.approx(-0.4382443152, abs=5.0e-5)
    assert status["spin_gap_over_j"] == pytest.approx(0.1160500064, abs=5.0e-5)
    assert status["registered_energy_per_site"] == pytest.approx(result["energy_per_site"])
    assert status["registered_spin_gap"] == pytest.approx(result["spin_gap_over_j"])
    assert status["energy_absolute_difference_from_registered"] < status["registered_energy_tolerance"]
    assert status["gap_absolute_difference_from_registered"] < status["registered_gap_tolerance"]
    assert status["matches_registered_energy_and_gap"] is True


def test_kagome_spin_liquid_small_ed_energy_and_gap_miss_yan_dmrg_observable():
    result = _standard_result("kagome_heisenberg_dmrg_spin_liquid_yan_reference")
    status = kagome_spin_half_heisenberg_ed_energy_gap_status(cluster_shapes=((2, 2), (3, 2)))

    assert status["cluster_energies_per_site"][(2, 2)] == pytest.approx(-0.4537396014, abs=1.0e-9)
    assert status["cluster_energies_per_site"][(3, 2)] == pytest.approx(-0.4471261541, abs=1.0e-9)
    assert status["triplet_gaps"][(2, 2)] == pytest.approx(0.3826683661, abs=1.0e-9)
    assert status["triplet_gaps"][(3, 2)] == pytest.approx(0.2845671776, abs=1.0e-9)
    assert status["registered_energy_per_site"] == pytest.approx(result["energy_per_site"])
    assert status["registered_spin_gap"] == pytest.approx(result["spin_gap_over_j"])
    assert status["all_clusters_match_registered_energy_and_gap"] is False


def test_kagome_j1_j2_phase_diagram_reference_is_not_reproduced_by_small_ed_scan():
    result = _standard_result("kagome_j1_j2_heisenberg_phase_diagram_reference")
    status = spin_benchmarks.kagome_j1_j2_phase_diagram_negative_ed_status(
        cluster_shape=(2, 2),
        j1=1.0,
        j2_values=(-0.1, 0.0, 0.1),
    )

    assert result["phases"] == ["spin_liquid", "q0_order", "sqrt3xsqrt3_order"]
    assert status["method"] == "periodic_kagome_j1_j2_spin_half_ed_negative_phase_probe"
    assert status["site_count"] == 12
    assert status["nearest_neighbor_bond_count"] == 24
    assert status["next_nearest_neighbor_bond_count"] == 16
    assert status["reproduces_registered_j1_j2_phase_diagram"] is False
    assert "finite 12-site ED energy/gap scan" in status["negative_evidence"]


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
        "edwardsite_kagome_antiferromagnet_reference",
        "haydeeite_ferromagnetic_kagome_reference",
        "crcl3_honeycomb_heisenberg_reference",
        "cri3_honeycomb_ferromagnet_reference",
        "crgete3_honeycomb_ferromagnet_reference",
        "mn_ps3_honeycomb_antiferromagnet_reference",
    }
    assert "zn_barlowite_kagome_qsl_reference" not in task_names
    assert "fecl3_honeycomb_antiferromagnet_reference" not in task_names

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
        elif task["projection_kind"] == "local_120_triangle_energy":
            model = _triangle_nn_classical_model(task["model_parameters"]["exchange"])
            spins = _triangle_120_spins(clockwise=False)
            ferromagnetic = np.array([[1.0, 0.0, 0.0]] * 3)
            energy = classical_energy(model, spins)
            assert energy == pytest.approx(task["expected_total_energy"])
            assert energy == pytest.approx(-1.5)
            assert energy < classical_energy(model, ferromagnetic) - task["minimum_gap"]
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
        elif task["projection_kind"] == "source_vector_geometry_consistency":
            assert task["benchmark_name"] == "fecl3_honeycomb_antiferromagnet_reference"
            assert task["verification_kind"] == "source_geometry_consistency"
            assert task["expected_propagation_vector_hexagonal"] == pytest.approx(
                [4.0 / 15.0, 1.0 / 15.0, 1.5]
            )
            assert task["expected_in_plane_period_lattice_spacings"] == 15
            assert task["expected_successive_plane_turn_angle_radians"] == pytest.approx(
                2.0 * math.pi / 15.0
            )
        else:
            raise AssertionError(f"unknown projection kind {task['projection_kind']}")


def test_zigzag_or_spiral_projection_tasks_cover_kitaev_gamma_candidate_manifolds():
    tasks = zigzag_or_spiral_projection_verification_tasks()
    task_names = {task["benchmark_name"] for task in tasks}

    assert len(tasks) == 13
    assert task_names >= {
        "kitaev_honeycomb_exact_spin_liquid_limit",
        "alpha_rucl3_kitaev_gamma_zigzag_reference",
        "beta_li2iro3_spiral_kitaev_gamma_reference",
        "gamma_li2iro3_3d_kitaev_reference",
        "ru_br3_kitaev_material_reference",
    }
    assert "cu2iro3_honeycomb_kitaev_reference" not in task_names

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
        elif task["cluster_kind"] == "spin_half_scalar_chirality_triangle":
            spectrum = _spin_half_triangle_scalar_chirality_spectrum()
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


def test_registry_triangle_scalar_chirality_tasks_execute_exact_triangle_spectrum():
    tasks = finite_cluster_spectrum_verification_tasks()
    chirality_tasks = [task for task in tasks if task["computable_observable"] == "triangle_scalar_chirality"]

    assert {task["benchmark_name"] for task in chirality_tasks} == {
        "kagome_chiral_spin_liquid_j1_j2_jchi_reference",
    }

    expected_levels = np.array(
        [
            -math.sqrt(3.0) / 4.0,
            -math.sqrt(3.0) / 4.0,
            0.0,
            0.0,
            0.0,
            0.0,
            math.sqrt(3.0) / 4.0,
            math.sqrt(3.0) / 4.0,
        ]
    )
    for task in chirality_tasks:
        assert task["cluster_kind"] == "spin_half_scalar_chirality_triangle"
        assert task["projection_note"]
        spectrum = _spin_half_triangle_scalar_chirality_spectrum()
        assert spectrum == pytest.approx(expected_levels)
        assert spectrum == pytest.approx(task["expected_levels"])


def test_registry_q0_120_order_energy_tasks_execute_triangle_energy_projection():
    tasks = classical_projection_verification_tasks()
    q0_tasks = [task for task in tasks if task["computable_observable"] == "q0_120_order_energy"]

    assert {task["benchmark_name"] for task in q0_tasks} == {
        "jarosite_kagome_dzyaloshinskii_moriya_reference",
    }
    for task in q0_tasks:
        assert task["projection_kind"] == "local_120_triangle_energy"
        assert task["projection_note"]
        model = _triangle_nn_classical_model(task["model_parameters"]["exchange"])
        spins = _triangle_120_spins(clockwise=False)
        ferromagnetic = np.array([[1.0, 0.0, 0.0]] * 3)
        energy = classical_energy(model, spins)
        assert energy == pytest.approx(task["expected_total_energy"])
        assert energy == pytest.approx(-1.5)
        assert energy < classical_energy(model, ferromagnetic) - task["minimum_gap"]


def test_dm_selected_chirality_tasks_select_the_lower_energy_triangle_branch():
    tasks = dm_selected_chirality_verification_tasks()
    task_names = {task["benchmark_name"] for task in tasks}

    assert task_names == {
        "kagome_dzyaloshinskii_moriya_critical_reference",
        "zncu3oh6cl2_kagome_dzyaloshinskii_moriya_reference",
        "jarosite_kagome_dzyaloshinskii_moriya_reference",
        "ba2cugeo7_dm_spiral_reference",
        "mnsi_chiral_helimagnet_reference",
        "cu2oseo3_skyrmion_lattice_reference",
    }

    for task in tasks:
        assert task["projection_kind"] == "dm_triangle_chirality_selection"
        assert task["projection_note"]
        model = _triangle_dm_classical_model(
            task["model_parameters"]["exchange"],
            task["model_parameters"]["dzyaloshinskii_moriya"],
        )
        counterclockwise = _triangle_120_spins(clockwise=False)
        clockwise = _triangle_120_spins(clockwise=True)
        ccw_energy = classical_energy(model, counterclockwise)
        cw_energy = classical_energy(model, clockwise)
        assert task["expected_selected_chirality"] == "clockwise"
        assert cw_energy == pytest.approx(task["selected_chirality_energy"])
        assert cw_energy < ccw_energy - task["minimum_energy_gap"]


def test_registry_structure_factor_tasks_are_executable_classical_toy_checks():
    tasks = structure_factor_verification_tasks()
    tasks_by_observable = {}
    for task in tasks:
        tasks_by_observable.setdefault(task["computable_observable"], []).append(task)

    assert {"static_structure_factor", "classical_structure_factor"} <= set(
        tasks_by_observable
    )
    assert "nearest_neighbor_structure_factor" not in tasks_by_observable
    assert "zn_barlowite_kagome_qsl_reference" not in {
        task["benchmark_name"] for task in tasks
    }
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
    } <= task_labels
    assert "two_band_lsw_spectrum" not in task_labels
    assert "nacuo2_triangular_heisenberg_material_reference" not in {
        task["benchmark_name"] for task in tasks
    }

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
