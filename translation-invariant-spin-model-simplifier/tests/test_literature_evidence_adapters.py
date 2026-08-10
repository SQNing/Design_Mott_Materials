import ast
import dataclasses
import math
import sys
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import validation.literature_evidence_adapters as adapters
from validation.literature_evidence_adapters import (
    ADAPTER_ELIGIBILITY,
    SOURCE_PARSE_ONLY_REASONS,
    AdapterContractError,
    AdapterDefinition,
    ConvergenceContract,
    CounterfactualDomain,
    EligibilityDecision,
    FrozenJsonObject,
    ParameterSource,
    ProblemSizePolicy,
    ResourceLimits,
    RuntimeRequirements,
    ValueSchema,
    canonical_json_bytes,
    canonical_sha256,
    freeze_json,
    thaw_json,
    _build_adapter_eligibility,
)


EXPECTED_ELIGIBILITY = (
    (
        "xxx_spin_half_chain_bethe_ground_state",
        ("energy_per_site",),
        "eligible",
        "xxx_bethe_energy",
        "xxx_bethe_integral_oracle",
        None,
    ),
    (
        "one_dimensional_classical_ising_correlation_length",
        ("formula", "correlation_length_beta_1_j_1"),
        "source_parse_only",
        None,
        None,
        "mixed_selector_contains_source_only_field",
    ),
    (
        "two_dimensional_square_ising_onsager_tc",
        ("tc_over_j",),
        "eligible",
        "square_ising_self_dual_tc",
        "square_ising_duality_residual_oracle",
        None,
    ),
    (
        "two_dimensional_square_ising_spontaneous_magnetization",
        ("formula", "magnetization_beta_0_6_j_1"),
        "source_parse_only",
        None,
        None,
        "mixed_selector_contains_source_only_field",
    ),
    (
        "square_potts_exact_critical_point",
        ("critical_beta_j", "continuous_for_q_le_4"),
        "source_parse_only",
        None,
        None,
        "mixed_selector_contains_source_only_field",
    ),
    (
        "triangular_ising_antiferromagnet_residual_entropy",
        ("residual_entropy_per_spin",),
        "eligible",
        "triangular_ising_af_entropy_quadrature",
        "triangular_ising_af_entropy_series_oracle",
        None,
    ),
    (
        "xy_spin_half_chain_anisotropic_critical_line",
        ("ising_critical_field", "anisotropy_transition_gamma"),
        "eligible",
        "xy_chain_bdg_boundaries",
        "xy_chain_dense_bdg_oracle",
        None,
    ),
    (
        "diamond_j1_j2_spiral_surface_reference",
        ("spiral_surface_for_j2_over_j1_gt",),
        "eligible",
        "diamond_spiral_threshold_fourier",
        "diamond_real_space_threshold_oracle",
        None,
    ),
    (
        "spin_ice_tetrahedron_nn_ice_rule",
        (
            "two_in_two_out_energy",
            "three_in_one_out_energy",
            "all_in_all_out_energy",
            "two_in_two_out_degeneracy",
        ),
        "eligible",
        "spin_ice_tetrahedron_enumeration",
        "spin_ice_tetrahedron_matrix_oracle",
        None,
    ),
    (
        "square_j1_j3_classical_lifshitz_reference",
        ("spiral_condition",),
        "source_parse_only",
        None,
        None,
        "source_only_symbolic_or_categorical_field",
    ),
    (
        "two_leg_ladder_strong_rung_exact_limit",
        ("energy_per_rung", "gap_to_triplet"),
        "eligible",
        "spin_ladder_rung_dense_ed",
        "spin_ladder_analytic_rung_oracle",
        None,
    ),
    (
        "square_ashkin_teller_exact_critical_line",
        ("has_exact_critical_line",),
        "source_parse_only",
        None,
        None,
        "status_or_candidate_only",
    ),
    (
        "pyrochlore_dipolar_spin_ice_pauling_entropy",
        ("pauling_entropy_per_spin",),
        "eligible",
        "pauling_entropy_combinatorics",
        "pauling_cluster_count_oracle",
        None,
    ),
    (
        "two_dimensional_xy_bkt_universal_jump",
        ("formula", "helicity_modulus_at_t_1"),
        "source_parse_only",
        None,
        None,
        "mixed_selector_contains_source_only_field",
    ),
    (
        "uimin_lai_sutherland_spin1_su3_point",
        ("theta_radians", "su3_symmetric"),
        "eligible",
        "uls_two_site_su3_matrix",
        "uls_permutation_commutator_oracle",
        None,
    ),
    (
        "bilinear_biquadratic_spin1_chain_aklt_angle",
        ("aklt_tan_theta", "theta_radians"),
        "eligible",
        "aklt_projector_angle",
        "aklt_two_spin_spectrum_oracle",
        None,
    ),
    (
        "square_compass_model_directional_exchange_degeneracy",
        ("has_line_flip_symmetries",),
        "eligible",
        "compass_line_symmetry_matrix",
        "compass_spin_flip_oracle",
        None,
    ),
    (
        "kitaev_honeycomb_abelian_nonabelian_field_gap_reference",
        ("field_opens_non_abelian_gap",),
        "eligible",
        "kitaev_field_majorana_mass",
        "kitaev_two_band_chern_oracle",
        None,
    ),
    (
        "square_toric_code_exact_topological_degeneracy",
        ("torus_ground_state_degeneracy",),
        "eligible",
        "toric_code_stabilizer_rank",
        "toric_code_logical_loop_oracle",
        None,
    ),
    (
        "triangular_nn_classical_120_reference",
        ("order", "q_reciprocal"),
        "source_parse_only",
        None,
        None,
        "status_or_candidate_only",
    ),
    (
        "aklt_spin1_chain_projector_ground_state",
        ("two_site_projector_eigenvalues", "vbs_ground_energy"),
        "eligible",
        "aklt_two_site_projector_ed",
        "aklt_clebsch_gordan_oracle",
        None,
    ),
    (
        "blume_capel_spin1_zero_temperature_level_crossing",
        ("square_lattice_d_over_j_crossing",),
        "eligible",
        "blume_capel_level_crossing",
        "blume_capel_configuration_oracle",
        None,
    ),
    (
        "checkerboard_heisenberg_afm_planar_pyrochlore_reference",
        ("zero_total_spin_per_crossed_plaquette",),
        "eligible",
        "checkerboard_plaquette_enumeration",
        "checkerboard_total_spin_oracle",
        None,
    ),
    (
        "cubic_ising_critical_temperature_reference",
        ("tc_over_j",),
        "source_parse_only",
        None,
        None,
        "target_equivalent_input",
    ),
    (
        "fcc_j1_j2_heisenberg_type_order_reference",
        ("common_orders",),
        "source_parse_only",
        None,
        None,
        "status_or_candidate_only",
    ),
    (
        "honeycomb_ising_ferromagnet_exact_tc",
        ("tc_over_j",),
        "eligible",
        "honeycomb_ising_star_triangle_tc",
        "honeycomb_ising_critical_polynomial_oracle",
        None,
    ),
    (
        "honeycomb_j1_j2_spiral_ring_reference",
        ("ring_condition",),
        "source_parse_only",
        None,
        None,
        "source_only_symbolic_or_categorical_field",
    ),
    (
        "kagome_ising_antiferromagnet_residual_entropy_reference",
        ("macroscopic_ground_state_degeneracy",),
        "eligible",
        "kagome_ising_af_entropy_quadrature",
        "kagome_ising_af_transfer_count_oracle",
        None,
    ),
    (
        "kagome_ising_ferromagnet_exact_tc",
        ("tc_over_j",),
        "eligible",
        "kagome_ising_star_triangle_tc",
        "kagome_ising_critical_polynomial_oracle",
        None,
    ),
    (
        "majundar_ghosh_chain_exact_dimer_point",
        ("energy_per_site", "degenerate_dimer_coverings"),
        "eligible",
        "majumdar_ghosh_dimer_ed",
        "majumdar_ghosh_projector_oracle",
        None,
    ),
    (
        "one_dimensional_classical_ising_no_finite_t_transition",
        ("finite_temperature_transition", "tc_over_j"),
        "eligible",
        "ising_chain_transfer_matrix",
        "ising_chain_partition_analytic_oracle",
        None,
    ),
    (
        "pyrochlore_heisenberg_afm_coulomb_phase_reference",
        ("zero_total_spin_per_tetrahedron", "pinch_points"),
        "eligible",
        "pyrochlore_coulomb_fourier",
        "pyrochlore_real_space_constraint_oracle",
        None,
    ),
    (
        "shastry_sutherland_exact_dimer_product",
        ("energy_per_dimer", "energy_per_spin"),
        "eligible",
        "shastry_sutherland_dimer_ed",
        "shastry_sutherland_bond_oracle",
        None,
    ),
    (
        "simple_cubic_j1_j2_collinear_reference",
        ("neel_to_collinear_boundary_j2_over_j1",),
        "eligible",
        "simple_cubic_j1_j2_fourier",
        "simple_cubic_real_space_energy_oracle",
        None,
    ),
    (
        "single_ion_spin1_anisotropy_levels",
        ("levels", "degeneracies"),
        "eligible",
        "spin1_single_ion_dense_ed",
        "spin1_m_quantum_number_oracle",
        None,
    ),
    (
        "square_fully_frustrated_ising_residual_entropy_reference",
        ("macroscopic_ground_state_degeneracy",),
        "eligible",
        "fully_frustrated_ising_entropy_series",
        "fully_frustrated_ising_transfer_oracle",
        None,
    ),
    (
        "takhtajan_babujian_spin1_critical_point",
        ("theta_radians", "is_integrable"),
        "source_parse_only",
        None,
        None,
        "mixed_selector_contains_source_only_field",
    ),
    (
        "transverse_field_ising_chain_critical_point",
        ("critical_field_over_exchange",),
        "eligible",
        "tfim_bdg_critical_point",
        "tfim_duality_gap_oracle",
        None,
    ),
    (
        "transverse_field_ising_chain_gap",
        ("gap_formula", "gap_formula_at_g_0_6"),
        "source_parse_only",
        None,
        None,
        "mixed_selector_contains_source_only_field",
    ),
    (
        "triangular_ising_ferromagnet_exact_tc",
        ("tc_over_j",),
        "eligible",
        "triangular_ising_star_triangle_tc",
        "triangular_ising_critical_polynomial_oracle",
        None,
    ),
    (
        "xx_spin_half_chain_free_fermion_energy",
        ("energy_per_site",),
        "eligible",
        "xx_chain_fermion_integral",
        "xx_chain_dense_ed_extrapolation_oracle",
        None,
    ),
    (
        "xxz_spin_half_chain_phase_boundaries",
        (
            "ferromagnetic_boundary_delta",
            "neel_boundary_delta",
            "gapless_interval",
        ),
        "source_parse_only",
        None,
        None,
        "backend_unavailable_for_registered_limit",
    ),
)


EXPECTED_ELIGIBLE_BY_ADAPTER = {
    adapter_id: (selector_fields, oracle_id)
    for (
        _benchmark_name,
        selector_fields,
        disposition,
        adapter_id,
        oracle_id,
        _reason,
    ) in EXPECTED_ELIGIBILITY
    if disposition == "eligible"
}

EXPECTED_BACKENDS = {
    "analytic": frozenset(
        {
            "xxx_bethe_energy",
            "square_ising_self_dual_tc",
            "pauling_entropy_combinatorics",
            "aklt_projector_angle",
            "honeycomb_ising_star_triangle_tc",
            "kagome_ising_star_triangle_tc",
            "ising_chain_transfer_matrix",
            "triangular_ising_star_triangle_tc",
        }
    ),
    "enumeration": frozenset(
        {
            "spin_ice_tetrahedron_enumeration",
            "toric_code_stabilizer_rank",
            "blume_capel_level_crossing",
            "checkerboard_plaquette_enumeration",
        }
    ),
    "dense_ed": frozenset(
        {
            "spin_ladder_rung_dense_ed",
            "uls_two_site_su3_matrix",
            "compass_line_symmetry_matrix",
            "aklt_two_site_projector_ed",
            "majumdar_ghosh_dimer_ed",
            "shastry_sutherland_dimer_ed",
            "spin1_single_ion_dense_ed",
        }
    ),
    "glt_fourier": frozenset(
        {
            "xy_chain_bdg_boundaries",
            "diamond_spiral_threshold_fourier",
            "kitaev_field_majorana_mass",
            "pyrochlore_coulomb_fourier",
            "simple_cubic_j1_j2_fourier",
            "tfim_bdg_critical_point",
        }
    ),
    "iterative_numeric": frozenset(
        {
            "triangular_ising_af_entropy_quadrature",
            "kagome_ising_af_entropy_quadrature",
            "fully_frustrated_ising_entropy_series",
            "xx_chain_fermion_integral",
        }
    ),
}

FIXED_LOCAL = frozenset(
    {
        "spin_ice_tetrahedron_enumeration",
        "spin_ladder_rung_dense_ed",
        "uls_two_site_su3_matrix",
        "aklt_two_site_projector_ed",
        "blume_capel_level_crossing",
        "checkerboard_plaquette_enumeration",
        "spin1_single_ion_dense_ed",
    }
)

SCALABLE = frozenset(
    {
        "compass_line_symmetry_matrix",
        "toric_code_stabilizer_rank",
        "majumdar_ghosh_dimer_ed",
        "shastry_sutherland_dimer_ed",
    }
)

EXPECTED_SIZE_DATA = {
    "spin_ice_tetrahedron_enumeration": {"spin_count": 4, "tetrahedra": 1},
    "spin_ladder_rung_dense_ed": {"spin_count": 2, "rungs": 1},
    "uls_two_site_su3_matrix": {"spin_count": 2, "spin_quantum_number": 1},
    "aklt_two_site_projector_ed": {
        "spin_count": 2,
        "spin_quantum_number": 1,
    },
    "blume_capel_level_crossing": {
        "unit_cell_sites": 1,
        "coordination_number": 4,
    },
    "checkerboard_plaquette_enumeration": {
        "spin_count": 4,
        "crossed_plaquettes": 1,
    },
    "spin1_single_ion_dense_ed": {
        "spin_count": 1,
        "spin_quantum_number": 1,
    },
    "compass_line_symmetry_matrix": {
        "lattice_shapes": ((2, 2), (2, 3)),
        "boundary_conditions": "open",
    },
    "toric_code_stabilizer_rank": {
        "lattice_shapes": ((2, 2), (3, 3)),
        "boundary_conditions": "periodic",
    },
    "majumdar_ghosh_dimer_ed": {
        "periodic_chain_lengths": (8, 10),
        "boundary_conditions": "periodic",
    },
    "shastry_sutherland_dimer_ed": {
        "orthogonal_dimer_counts": (2, 4),
        "spin_counts": (4, 8),
        "boundary_conditions": "open_linked_cells",
    },
}

EXPECTED_OUTPUT_CONTRACTS = {
    "xxx_bethe_energy": {
        "energy_per_site": (
            "number",
            "J",
            "raw_bethe_energy_expression",
            "direct_exact_value",
        ),
    },
    "square_ising_self_dual_tc": {
        "tc_over_j": (
            "number",
            "dimensionless",
            "raw_positive_duality_root",
            "bounded_numeric_value",
        ),
    },
    "triangular_ising_af_entropy_quadrature": {
        "residual_entropy_per_spin": (
            "number",
            "k_B",
            "raw_wannier_entropy_bounds",
            "bounded_numeric_value",
        ),
    },
    "xy_chain_bdg_boundaries": {
        "ising_critical_field": (
            "number",
            "J",
            "raw_field_gap_closing",
            "bounded_numeric_value",
        ),
        "anisotropy_transition_gamma": (
            "number",
            "dimensionless",
            "raw_anisotropy_gap_closing",
            "bounded_numeric_value",
        ),
    },
    "diamond_spiral_threshold_fourier": {
        "spiral_surface_for_j2_over_j1_gt": (
            "number",
            "dimensionless",
            "raw_kernel_minimum_threshold",
            "bounded_numeric_value",
        ),
    },
    "spin_ice_tetrahedron_enumeration": {
        "two_in_two_out_energy": (
            "number",
            "J",
            "raw_two_in_two_out_sector_energy",
            "direct_exact_value",
        ),
        "three_in_one_out_energy": (
            "number",
            "J",
            "raw_three_in_one_out_sector_energy",
            "direct_exact_value",
        ),
        "all_in_all_out_energy": (
            "number",
            "J",
            "raw_all_in_all_out_sector_energy",
            "direct_exact_value",
        ),
        "two_in_two_out_degeneracy": (
            "integer",
            "states",
            "raw_two_in_two_out_sector_count",
            "direct_exact_value",
        ),
    },
    "spin_ladder_rung_dense_ed": {
        "energy_per_rung": (
            "number",
            "J",
            "raw_rung_singlet_eigenvalue",
            "direct_exact_value",
        ),
        "gap_to_triplet": (
            "number",
            "J",
            "raw_rung_spectrum_gap",
            "direct_exact_value",
        ),
    },
    "pauling_entropy_combinatorics": {
        "pauling_entropy_per_spin": (
            "number",
            "k_B",
            "raw_shared_spin_entropy_expression",
            "direct_exact_value",
        ),
    },
    "uls_two_site_su3_matrix": {
        "theta_radians": (
            "number",
            "radians",
            "raw_bilinear_biquadratic_angle",
            "direct_exact_value",
        ),
        "su3_symmetric": (
            "boolean",
            "dimensionless",
            "raw_permutation_commutator_norms",
            "all_residuals_within_bound_boolean",
        ),
    },
    "aklt_projector_angle": {
        "aklt_tan_theta": (
            "number",
            "dimensionless",
            "raw_projector_coefficient_ratio",
            "direct_exact_value",
        ),
        "theta_radians": (
            "number",
            "radians",
            "raw_projector_coefficient_angle",
            "direct_exact_value",
        ),
    },
    "compass_line_symmetry_matrix": {
        "has_line_flip_symmetries": (
            "boolean",
            "dimensionless",
            "raw_line_flip_commutator_norms",
            "all_residuals_within_bound_boolean",
        ),
    },
    "kitaev_field_majorana_mass": {
        "field_opens_non_abelian_gap": (
            "boolean",
            "dimensionless",
            "raw_mass_gap_and_parity",
            "positive_gap_and_odd_parity_boolean",
        ),
    },
    "toric_code_stabilizer_rank": {
        "torus_ground_state_degeneracy": (
            "integer",
            "states",
            "raw_stabilizer_matrix_rank",
            "rank_derived_integer",
        ),
    },
    "aklt_two_site_projector_ed": {
        "two_site_projector_eigenvalues": (
            "list_number",
            "dimensionless",
            "raw_projector_sector_eigenvalues",
            "grouped_exact_sequence",
        ),
        "vbs_ground_energy": (
            "number",
            "J",
            "raw_local_vbs_energy",
            "direct_exact_value",
        ),
    },
    "blume_capel_level_crossing": {
        "square_lattice_d_over_j_crossing": (
            "number",
            "dimensionless",
            "raw_uniform_level_crossing_ratio",
            "direct_exact_value",
        ),
    },
    "checkerboard_plaquette_enumeration": {
        "zero_total_spin_per_crossed_plaquette": (
            "boolean",
            "dimensionless",
            "raw_plaquette_spin_sum_norms",
            "all_residuals_within_bound_boolean",
        ),
    },
    "honeycomb_ising_star_triangle_tc": {
        "tc_over_j": (
            "number",
            "dimensionless",
            "raw_positive_star_triangle_root",
            "bounded_numeric_value",
        ),
    },
    "kagome_ising_af_entropy_quadrature": {
        "macroscopic_ground_state_degeneracy": (
            "boolean",
            "dimensionless",
            "raw_entropy_lower_bounds",
            "positive_lower_bound_boolean",
        ),
    },
    "kagome_ising_star_triangle_tc": {
        "tc_over_j": (
            "number",
            "dimensionless",
            "raw_ferromagnetic_star_triangle_root",
            "bounded_numeric_value",
        ),
    },
    "majumdar_ghosh_dimer_ed": {
        "energy_per_site": (
            "number",
            "J",
            "raw_chain_energy_density_sequence",
            "direct_exact_value",
        ),
        "degenerate_dimer_coverings": (
            "integer",
            "states",
            "raw_translated_ground_space_rank",
            "rank_derived_integer",
        ),
    },
    "ising_chain_transfer_matrix": {
        "finite_temperature_transition": (
            "boolean",
            "dimensionless",
            "raw_transfer_eigenvalue_separation",
            "no_finite_crossing_boolean",
        ),
        "tc_over_j": (
            "number",
            "dimensionless",
            "raw_zero_temperature_limit",
            "no_finite_crossing_zero_limit",
        ),
    },
    "pyrochlore_coulomb_fourier": {
        "zero_total_spin_per_tetrahedron": (
            "boolean",
            "dimensionless",
            "raw_tetrahedron_spin_sum_norms",
            "all_residuals_within_bound_boolean",
        ),
        "pinch_points": (
            "boolean",
            "dimensionless",
            "raw_directional_polarization_limits",
            "directional_limits_differ_boolean",
        ),
    },
    "shastry_sutherland_dimer_ed": {
        "energy_per_dimer": (
            "number",
            "J",
            "raw_singlet_product_energy_per_dimer",
            "direct_exact_value",
        ),
        "energy_per_spin": (
            "number",
            "J",
            "raw_singlet_product_energy_per_spin",
            "direct_exact_value",
        ),
    },
    "simple_cubic_j1_j2_fourier": {
        "neel_to_collinear_boundary_j2_over_j1": (
            "number",
            "dimensionless",
            "raw_branch_crossing_ratio",
            "bounded_numeric_value",
        ),
    },
    "spin1_single_ion_dense_ed": {
        "levels": (
            "list_number",
            "J",
            "raw_single_ion_eigenvalues",
            "grouped_exact_sequence",
        ),
        "degeneracies": (
            "list_integer",
            "states",
            "raw_single_ion_level_multiplicities",
            "grouped_exact_sequence",
        ),
    },
    "fully_frustrated_ising_entropy_series": {
        "macroscopic_ground_state_degeneracy": (
            "boolean",
            "dimensionless",
            "raw_entropy_series_lower_bounds",
            "positive_lower_bound_boolean",
        ),
    },
    "tfim_bdg_critical_point": {
        "critical_field_over_exchange": (
            "number",
            "dimensionless",
            "raw_thermodynamic_gap_closing_ratio",
            "bounded_numeric_value",
        ),
    },
    "triangular_ising_star_triangle_tc": {
        "tc_over_j": (
            "number",
            "dimensionless",
            "raw_positive_critical_equation_root",
            "bounded_numeric_value",
        ),
    },
    "xx_chain_fermion_integral": {
        "energy_per_site": (
            "number",
            "J",
            "raw_occupied_dispersion_integral_bounds",
            "bounded_numeric_value",
        ),
    },
}

EXPECTED_NONNEGATIVE_OUTPUT_FIELDS = frozenset(
    {
        ("square_ising_self_dual_tc", "tc_over_j"),
        (
            "triangular_ising_af_entropy_quadrature",
            "residual_entropy_per_spin",
        ),
        ("xy_chain_bdg_boundaries", "ising_critical_field"),
        ("xy_chain_bdg_boundaries", "anisotropy_transition_gamma"),
        (
            "diamond_spiral_threshold_fourier",
            "spiral_surface_for_j2_over_j1_gt",
        ),
        (
            "spin_ice_tetrahedron_enumeration",
            "two_in_two_out_degeneracy",
        ),
        ("spin_ladder_rung_dense_ed", "gap_to_triplet"),
        ("pauling_entropy_combinatorics", "pauling_entropy_per_spin"),
        ("uls_two_site_su3_matrix", "theta_radians"),
        ("aklt_projector_angle", "aklt_tan_theta"),
        ("aklt_projector_angle", "theta_radians"),
        ("toric_code_stabilizer_rank", "torus_ground_state_degeneracy"),
        ("aklt_two_site_projector_ed", "two_site_projector_eigenvalues"),
        ("aklt_two_site_projector_ed", "vbs_ground_energy"),
        (
            "blume_capel_level_crossing",
            "square_lattice_d_over_j_crossing",
        ),
        ("honeycomb_ising_star_triangle_tc", "tc_over_j"),
        ("kagome_ising_star_triangle_tc", "tc_over_j"),
        ("majumdar_ghosh_dimer_ed", "degenerate_dimer_coverings"),
        ("ising_chain_transfer_matrix", "tc_over_j"),
        (
            "simple_cubic_j1_j2_fourier",
            "neel_to_collinear_boundary_j2_over_j1",
        ),
        ("spin1_single_ion_dense_ed", "degeneracies"),
        ("tfim_bdg_critical_point", "critical_field_over_exchange"),
        ("triangular_ising_star_triangle_tc", "tc_over_j"),
    }
)
EXPECTED_LIST_OUTPUT_LENGTHS = {
    ("aklt_two_site_projector_ed", "two_site_projector_eigenvalues"): 3,
    ("spin1_single_ion_dense_ed", "levels"): 3,
    ("spin1_single_ion_dense_ed", "degeneracies"): 2,
}

EXPECTED_SCIENTIFIC_INPUT_NAMES = {
    "xxx_bethe_energy": {"exchange"},
    "square_ising_self_dual_tc": {"exchange"},
    "triangular_ising_af_entropy_quadrature": {"exchange"},
    "xy_chain_bdg_boundaries": {"exchange"},
    "diamond_spiral_threshold_fourier": {"first_neighbor_exchange"},
    "spin_ice_tetrahedron_enumeration": {"exchange"},
    "spin_ladder_rung_dense_ed": {"rung_exchange"},
    "pauling_entropy_combinatorics": {"spins_per_tetrahedron"},
    "uls_two_site_su3_matrix": {"energy_scale"},
    "aklt_projector_angle": {"projector_scale"},
    "compass_line_symmetry_matrix": {
        "horizontal_exchange",
        "vertical_exchange",
    },
    "kitaev_field_majorana_mass": {
        "kitaev_exchange",
        "field_x",
        "field_y",
        "field_z",
    },
    "toric_code_stabilizer_rank": {"stabilizer_scale"},
    "aklt_two_site_projector_ed": {"projector_scale"},
    "blume_capel_level_crossing": {"exchange"},
    "checkerboard_plaquette_enumeration": {"exchange"},
    "honeycomb_ising_star_triangle_tc": {"exchange"},
    "kagome_ising_af_entropy_quadrature": {"exchange"},
    "kagome_ising_star_triangle_tc": {"exchange"},
    "majumdar_ghosh_dimer_ed": {"nearest_exchange"},
    "ising_chain_transfer_matrix": {"exchange", "inverse_temperature"},
    "pyrochlore_coulomb_fourier": {
        "exchange",
        "approach_direction_a",
        "approach_direction_b",
    },
    "shastry_sutherland_dimer_ed": {
        "intradimer_exchange",
        "interdimer_exchange",
    },
    "simple_cubic_j1_j2_fourier": {"first_neighbor_exchange"},
    "spin1_single_ion_dense_ed": {"single_ion_anisotropy"},
    "fully_frustrated_ising_entropy_series": {"bond_magnitude"},
    "tfim_bdg_critical_point": {"exchange"},
    "triangular_ising_star_triangle_tc": {"exchange"},
    "xx_chain_fermion_integral": {"exchange"},
}

EXPECTED_CONTROL_NAMES = {
    "xxx_bethe_energy": set(),
    "square_ising_self_dual_tc": {
        "root_residual_threshold",
        "maximum_refinement_iterations",
    },
    "triangular_ising_af_entropy_quadrature": {
        "quadrature_absolute_threshold",
        "quadrature_max_subintervals",
    },
    "xy_chain_bdg_boundaries": {
        "momentum_refinement_grid",
        "eigensolver_residual_threshold",
    },
    "diamond_spiral_threshold_fourier": {
        "momentum_refinement_grid",
        "kernel_residual_bound",
    },
    "spin_ice_tetrahedron_enumeration": set(),
    "spin_ladder_rung_dense_ed": set(),
    "pauling_entropy_combinatorics": set(),
    "uls_two_site_su3_matrix": set(),
    "aklt_projector_angle": set(),
    "compass_line_symmetry_matrix": set(),
    "kitaev_field_majorana_mass": {
        "momentum_refinement_grid",
        "gap_residual_bound",
    },
    "toric_code_stabilizer_rank": set(),
    "aklt_two_site_projector_ed": set(),
    "blume_capel_level_crossing": set(),
    "checkerboard_plaquette_enumeration": set(),
    "honeycomb_ising_star_triangle_tc": {
        "root_residual_threshold",
        "maximum_refinement_iterations",
    },
    "kagome_ising_af_entropy_quadrature": {
        "quadrature_absolute_threshold",
        "quadrature_max_subintervals",
    },
    "kagome_ising_star_triangle_tc": {
        "root_residual_threshold",
        "maximum_refinement_iterations",
    },
    "majumdar_ghosh_dimer_ed": set(),
    "ising_chain_transfer_matrix": set(),
    "pyrochlore_coulomb_fourier": {
        "momentum_refinement_grid",
        "constraint_residual_bound",
    },
    "shastry_sutherland_dimer_ed": set(),
    "simple_cubic_j1_j2_fourier": {
        "momentum_refinement_grid",
        "branch_residual_bound",
    },
    "spin1_single_ion_dense_ed": set(),
    "fully_frustrated_ising_entropy_series": {
        "series_refinement_terms",
        "truncation_cutoff",
    },
    "tfim_bdg_critical_point": {
        "momentum_refinement_grid",
        "gap_residual_bound",
    },
    "triangular_ising_star_triangle_tc": {
        "root_residual_threshold",
        "maximum_refinement_iterations",
    },
    "xx_chain_fermion_integral": {
        "momentum_refinement_grid",
        "quadrature_absolute_threshold",
    },
}


MIGRATION_CANDIDATE_SOURCES = frozenset(
    {
        "blume_capel_spin1_zero_temperature_level_crossing",
        "checkerboard_heisenberg_afm_planar_pyrochlore_reference",
        "cubic_ising_critical_temperature_reference",
        "fcc_j1_j2_heisenberg_type_order_reference",
        "honeycomb_ising_ferromagnet_exact_tc",
        "honeycomb_j1_j2_spiral_ring_reference",
        "kagome_ising_antiferromagnet_residual_entropy_reference",
        "kagome_ising_ferromagnet_exact_tc",
        "majundar_ghosh_chain_exact_dimer_point",
        "one_dimensional_classical_ising_no_finite_t_transition",
        "pyrochlore_heisenberg_afm_coulomb_phase_reference",
        "shastry_sutherland_exact_dimer_product",
        "simple_cubic_j1_j2_collinear_reference",
        "single_ion_spin1_anisotropy_levels",
        "square_fully_frustrated_ising_residual_entropy_reference",
        "takhtajan_babujian_spin1_critical_point",
        "transverse_field_ising_chain_critical_point",
        "transverse_field_ising_chain_gap",
        "triangular_ising_ferromagnet_exact_tc",
        "xx_spin_half_chain_free_fermion_energy",
        "xxz_spin_half_chain_phase_boundaries",
    }
)


def _legacy_local_recompute_candidate_names():
    runtime_source = (
        PROJECT_ROOT
        / "scripts"
        / "validation"
        / "literature_runtime_evidence.py"
    )
    tree = ast.parse(
        runtime_source.read_text(encoding="utf-8"),
        filename=str(runtime_source),
    )
    collectors = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "collect_runtime_evidence"
    ]
    assert len(collectors) == 1
    specs_assignments = [
        node
        for node in collectors[0].body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "specs"
            for target in node.targets
        )
    ]
    assert len(specs_assignments) == 1
    specs_literal = specs_assignments[0].value
    assert isinstance(specs_literal, ast.Tuple)

    candidate_names = []
    for spec in specs_literal.elts:
        assert isinstance(spec, ast.Dict)
        literal_fields = {
            key.value: value
            for key, value in zip(spec.keys, spec.values)
            if isinstance(key, ast.Constant) and type(key.value) is str
        }
        mode = literal_fields.get("mode")
        if not (
            isinstance(mode, ast.Constant) and mode.value == "local_recompute"
        ):
            continue
        benchmark_name = literal_fields.get("benchmark_name")
        assert isinstance(benchmark_name, ast.Constant)
        assert type(benchmark_name.value) is str
        candidate_names.append(benchmark_name.value)

    assert len(candidate_names) == 21
    assert len(set(candidate_names)) == 21
    return frozenset(candidate_names)


def test_eligibility_catalog_matches_all_42_normative_rows_field_for_field():
    actual = tuple(
        (
            benchmark_name,
            decision.selector_fields,
            decision.disposition,
            decision.adapter_id,
            decision.oracle_id,
            decision.reason,
        )
        for benchmark_name, decision in ADAPTER_ELIGIBILITY.items()
    )

    assert actual == EXPECTED_ELIGIBILITY
    assert tuple(
        field.name for field in dataclasses.fields(EligibilityDecision)
    ) == (
        "selector_fields",
        "disposition",
        "adapter_id",
        "oracle_id",
        "reason",
    )
    assert ADAPTER_ELIGIBILITY[
        "two_leg_ladder_strong_rung_exact_limit"
    ].selector_fields == ("energy_per_rung", "gap_to_triplet")
    triangular = ADAPTER_ELIGIBILITY["triangular_nn_classical_120_reference"]
    assert (triangular.disposition, triangular.reason) == (
        "source_parse_only",
        "status_or_candidate_only",
    )
    cubic = ADAPTER_ELIGIBILITY["cubic_ising_critical_temperature_reference"]
    assert (cubic.disposition, cubic.reason) == (
        "source_parse_only",
        "target_equivalent_input",
    )


def test_eligibility_catalog_has_exact_29_eligible_and_13_source_parse_rows():
    assert len(ADAPTER_ELIGIBILITY) == 42
    assert sum(
        decision.disposition == "eligible"
        for decision in ADAPTER_ELIGIBILITY.values()
    ) == 29
    assert sum(
        decision.disposition == "source_parse_only"
        for decision in ADAPTER_ELIGIBILITY.values()
    ) == 13
    assert SOURCE_PARSE_ONLY_REASONS == frozenset(
        {
            "status_or_candidate_only",
            "mixed_selector_contains_source_only_field",
            "source_only_symbolic_or_categorical_field",
            "target_equivalent_input",
            "observable_identity_mismatch",
            "no_independent_oracle",
            "no_honest_convergence_evidence",
            "backend_unavailable_for_registered_limit",
        }
    )


def test_source_parse_rows_cannot_resolve_an_adapter():
    for decision in ADAPTER_ELIGIBILITY.values():
        if decision.disposition == "source_parse_only":
            assert decision.adapter_id is None
            assert decision.oracle_id is None


def test_candidate_sources_union_matches_normative_catalog():
    legacy_candidates = _legacy_local_recompute_candidate_names()

    assert len(legacy_candidates) == 21
    assert len(MIGRATION_CANDIDATE_SOURCES) == 21
    assert legacy_candidates.isdisjoint(MIGRATION_CANDIDATE_SOURCES)
    assert legacy_candidates | MIGRATION_CANDIDATE_SOURCES == set(
        ADAPTER_ELIGIBILITY
    )


def test_eligibility_catalog_is_immutable():
    benchmark_name = "xxx_spin_half_chain_bethe_ground_state"
    existing = ADAPTER_ELIGIBILITY[benchmark_name]

    with pytest.raises(TypeError):
        ADAPTER_ELIGIBILITY[benchmark_name] = existing
    with pytest.raises(dataclasses.FrozenInstanceError):
        existing.disposition = "source_parse_only"


def test_eligibility_builder_rejects_a_duplicate_benchmark_id():
    duplicated_row = EXPECTED_ELIGIBILITY[0]

    with pytest.raises(AdapterContractError, match="duplicate.*benchmark"):
        _build_adapter_eligibility((duplicated_row, duplicated_row))


VALID_UNIQUE_EXTRA_ELIGIBILITY_ROW = (
    "unique_extra_eligibility_reference",
    ("status",),
    "eligible",
    "unique_extra_adapter",
    "unique_extra_oracle",
    None,
)


@pytest.mark.parametrize(
    ("rows", "diagnostic"),
    (
        pytest.param(
            (list(EXPECTED_ELIGIBILITY[0]), *EXPECTED_ELIGIBILITY[1:]),
            "exact six-field tuple",
            id="row_is_list",
        ),
        pytest.param(
            (EXPECTED_ELIGIBILITY[0][:-1], *EXPECTED_ELIGIBILITY[1:]),
            "exact six-field tuple",
            id="wrong_row_arity",
        ),
        pytest.param(
            (
                (
                    EXPECTED_ELIGIBILITY[0][0],
                    list(EXPECTED_ELIGIBILITY[0][1]),
                    *EXPECTED_ELIGIBILITY[0][2:],
                ),
                *EXPECTED_ELIGIBILITY[1:],
            ),
            "selector_fields",
            id="selector_fields_is_list",
        ),
        pytest.param(
            (
                (
                    EXPECTED_ELIGIBILITY[0][0],
                    EXPECTED_ELIGIBILITY[0][1],
                    "candidate",
                    *EXPECTED_ELIGIBILITY[0][3:],
                ),
                *EXPECTED_ELIGIBILITY[1:],
            ),
            "disposition",
            id="invalid_disposition",
        ),
        pytest.param(
            EXPECTED_ELIGIBILITY[:-1],
            "exactly 42 rows",
            id="only_41_rows",
        ),
        pytest.param(
            (*EXPECTED_ELIGIBILITY, VALID_UNIQUE_EXTRA_ELIGIBILITY_ROW),
            "exactly 42 rows",
            id="43_unique_rows",
        ),
        pytest.param(
            (
                (
                    EXPECTED_ELIGIBILITY[0][0],
                    EXPECTED_ELIGIBILITY[0][1],
                    "source_parse_only",
                    None,
                    None,
                    "no_independent_oracle",
                ),
                *EXPECTED_ELIGIBILITY[1:],
            ),
            "exactly 29 eligible and 13 source_parse_only rows",
            id="wrong_29_13_split",
        ),
    ),
)
def test_eligibility_builder_rejects_malformed_or_miscounted_catalogs(
    rows, diagnostic
):
    with pytest.raises(AdapterContractError, match=diagnostic):
        _build_adapter_eligibility(rows)


def test_eligibility_builder_returns_exact_immutable_contract_types():
    catalog = _build_adapter_eligibility(EXPECTED_ELIGIBILITY)

    assert type(catalog) is MappingProxyType
    assert len(catalog) == 42
    assert all(
        type(decision) is EligibilityDecision for decision in catalog.values()
    )


def test_eligibility_builder_isolated_mapping_survives_caller_list_mutation():
    caller_rows = list(EXPECTED_ELIGIBILITY)
    catalog = _build_adapter_eligibility(caller_rows)

    caller_rows.clear()
    caller_rows.append(VALID_UNIQUE_EXTRA_ELIGIBILITY_ROW)

    actual = tuple(
        (
            benchmark_name,
            decision.selector_fields,
            decision.disposition,
            decision.adapter_id,
            decision.oracle_id,
            decision.reason,
        )
        for benchmark_name, decision in catalog.items()
    )
    assert len(catalog) == 42
    assert actual == EXPECTED_ELIGIBILITY


def _number_schema(*, lower=0.0, upper=None, units="dimensionless"):
    return ValueSchema(
        kind="number",
        required=True,
        lower=lower,
        upper=upper,
        item_schema=None,
        properties=(),
        units=units,
    )


def _object_schema(properties):
    return ValueSchema(
        kind="object",
        required=True,
        lower=None,
        upper=None,
        item_schema=None,
        properties=properties,
        units="",
    )


def _adapter_values(observable_identity, fixed_sizes, valid_rules):
    scientific_inputs = _object_schema(
        (("exchange", _number_schema(lower=0.0, units="J")),)
    )
    numerical_controls = _object_schema(())
    output_schema = adapters.OutputSchema(
        fields=(
            (
                "energy_per_site",
                adapters.OutputFieldBinding(
                    value_schema=_number_schema(units="J"),
                    raw_field="raw_bethe_energy_expression",
                    proof_kind="direct_exact_value",
                ),
            ),
        )
    )
    return {
        "adapter_id": "xxx_bethe_energy",
        "entry_symbol": (
            "validation.literature_evidence_adapters:adapter_xxx_bethe_energy"
        ),
        "observable_identity": observable_identity,
        "scientific_input_schema": scientific_inputs,
        "numerical_control_schema": numerical_controls,
        "parameter_sources": (
            ParameterSource(
                parameter_name="exchange",
                kind="canonical_model_parameter",
                details={"canonical_path": ["hamiltonian", "exchange"]},
            ),
        ),
        "output_schema": output_schema,
        "backend_kind": "analytic",
        "problem_size_policy": ProblemSizePolicy(
            kind="fixed_local",
            fixed_sizes=fixed_sizes,
            allowed_sizes={},
        ),
        "runtime_requirements": RuntimeRequirements(
            interpreter="python3",
            packages=(),
            native_libraries=(),
            backend_resources=(),
        ),
        "convergence_contract": ConvergenceContract(
            kind="exact",
            requirements={"uncertainty": 0.0},
        ),
        "counterfactual_domain": CounterfactualDomain(
            valid_rules=valid_rules,
            invalid_rules={"exchange": {"values": [0.0, -1.0]}},
        ),
        "oracle_id": "xxx_bethe_energy_series_oracle",
        "resource_limits": ResourceLimits(
            cpu_seconds=10,
            wall_seconds=20.0,
            address_space_bytes=256_000_000,
            output_bytes=64_000,
            file_descriptors=16,
            process_count=1,
        ),
    }


def _observable_identity():
    return {
        "subject": "ground-state energy",
        "system_or_material": "spin-half XXX chain",
        "hamiltonian": {"terms": ["exchange"]},
        "parameter_regime": {"exchange": [1.0]},
        "size_or_limit": {"kind": "thermodynamic_limit"},
        "observable_definition": {"field": "energy_per_site"},
        "units": {"energy_per_site": "J"},
        "conditions": {"temperature": [0.0]},
    }


class _CustomItemsMapping(Mapping):
    def __init__(self, visible, yielded_items):
        self._visible = visible
        self._yielded_items = yielded_items

    def __getitem__(self, key):
        return self._visible[key]

    def __iter__(self):
        return iter(self._visible)

    def __len__(self):
        return len(self._visible)

    def keys(self):
        return self._visible.keys()

    def items(self):
        return iter(self._yielded_items)


class _BrokenItemsMapping(Mapping):
    def __getitem__(self, key):
        raise KeyError(key)

    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0

    def items(self):
        raise RuntimeError("broken items traversal")


class _PartiallyMutatingItemsMapping(Mapping):
    def __init__(self):
        self._backing = {"first": 1}

    def __getitem__(self, key):
        return self._backing[key]

    def __iter__(self):
        return iter(self._backing)

    def __len__(self):
        return len(self._backing)

    def items(self):
        yield "first", 1
        self._backing["injected"] = 2
        raise RuntimeError("mapping mutated during traversal")


class _CallerBackedTuple(tuple):
    def __new__(cls, backing):
        instance = tuple.__new__(cls, ())
        instance._backing = backing
        return instance

    def __iter__(self):
        return iter(self._backing)

    def __len__(self):
        return len(self._backing)

    def __getitem__(self, index):
        return self._backing[index]


class BadRepr:
    def __repr__(self):
        raise RuntimeError("repr must not run")

    def __hash__(self):
        raise RuntimeError("hash must not run")


class _BrokenFrozenItems:
    def __iter__(self):
        raise RuntimeError("broken frozen traversal")


def _list_cycle():
    value = []
    value.append(value)
    return value


def _mapping_cycle():
    value = {}
    value["self"] = value
    return value


def _frozen_object_with_scalar_depth(scalar_depth):
    value = 0
    for _ in range(scalar_depth):
        value = {"nested": value}
    frozen = freeze_json(value)
    assert type(frozen) is FrozenJsonObject
    return frozen


def test_freeze_json_rejects_non_string_keys_unknown_objects_and_nonfinite_numbers():
    class Unknown:
        pass

    invalid_values = (
        {1: "non-string key"},
        {"nested": [{"value": Unknown()}]},
        {"nested": [{"value": object()}]},
        {"bytes": b"not JSON"},
        {"set": {1, 2}},
        {"callable": lambda: None},
        {"number": math.nan},
        {"number": math.inf},
        {"number": -math.inf},
    )

    for value in invalid_values:
        with pytest.raises(AdapterContractError):
            freeze_json(value)


def test_freeze_json_rejects_callable_containers_and_frozen_subclasses():
    class CallableMapping(dict):
        def __call__(self):
            return None

    class CallableList(list):
        def __call__(self):
            return None

    class MutableBackedFrozenJsonObject(FrozenJsonObject):
        def __init__(self, backing):
            super().__init__(backing)
            object.__setattr__(self, "_backing", backing)

        def __getitem__(self, key):
            return self._backing[key]

        def __iter__(self):
            return iter(self._backing)

        def __len__(self):
            return len(self._backing)

    accepted_callable_types = []
    for value in (CallableMapping(x=1), CallableList([1, 2])):
        try:
            freeze_json(value)
        except AdapterContractError:
            continue
        accepted_callable_types.append(type(value).__name__)
    assert accepted_callable_types == []

    backing = {"x": [1]}
    untrusted = MutableBackedFrozenJsonObject(backing)
    with pytest.raises(AdapterContractError):
        freeze_json(untrusted)
    with pytest.raises(AdapterContractError):
        thaw_json(untrusted)
    backing["x"].append(2)
    with pytest.raises(AdapterContractError):
        canonical_sha256(untrusted)

    exact_frozen = freeze_json({"x": [1]})
    assert type(exact_frozen) is FrozenJsonObject
    assert freeze_json(exact_frozen) is exact_frozen


def test_freeze_json_rejects_duplicate_mapping_items():
    duplicate_mapping = _CustomItemsMapping(
        {"x": 1},
        (("x", 1), ("x", 2)),
    )

    with pytest.raises(AdapterContractError, match="duplicate"):
        freeze_json(duplicate_mapping)


@pytest.mark.parametrize(
    "mapping",
    (_BrokenItemsMapping(), _PartiallyMutatingItemsMapping()),
    ids=("broken_items", "mutation_then_exception"),
)
@pytest.mark.parametrize(
    "operation", (freeze_json, canonical_json_bytes), ids=("freeze", "canonical")
)
def test_malformed_mapping_traversal_is_normalized(mapping, operation):
    with pytest.raises(AdapterContractError):
        operation(mapping)


@pytest.mark.parametrize(
    "cycle_factory", (_list_cycle, _mapping_cycle), ids=("list", "mapping")
)
@pytest.mark.parametrize(
    "operation", (freeze_json, canonical_json_bytes), ids=("freeze", "canonical")
)
def test_recursive_json_containers_are_rejected(cycle_factory, operation):
    with pytest.raises(AdapterContractError, match="cycle"):
        operation(cycle_factory())


@pytest.mark.parametrize(
    "operation", (freeze_json, canonical_json_bytes), ids=("freeze", "canonical")
)
def test_excessive_json_nesting_is_rejected(operation):
    value = 0
    for _ in range(256):
        value = [value]

    with pytest.raises(AdapterContractError, match="nesting"):
        operation(value)


@pytest.mark.parametrize("outer_kind", ("mapping", "sequence"))
def test_freeze_json_rejects_frozen_depth_128_embedded_one_level(outer_kind):
    frozen = _frozen_object_with_scalar_depth(128)
    outer = {"embedded": frozen} if outer_kind == "mapping" else [frozen]

    with pytest.raises(AdapterContractError, match="nesting"):
        freeze_json(outer)


@pytest.mark.parametrize("outer_kind", ("mapping", "sequence"))
def test_freeze_json_accepts_frozen_depth_127_embedded_one_level(outer_kind):
    frozen = _frozen_object_with_scalar_depth(127)
    outer = {"embedded": frozen} if outer_kind == "mapping" else [frozen]

    accepted = freeze_json(outer)
    embedded = accepted["embedded"] if outer_kind == "mapping" else accepted[0]
    encoded = canonical_json_bytes(accepted)
    digest = canonical_sha256(accepted)

    assert embedded is frozen
    assert encoded == canonical_json_bytes(accepted)
    assert digest == canonical_sha256(accepted)
    assert accepted == accepted
    assert hash(accepted) == hash(accepted)


def test_freeze_json_accepts_shared_legal_frozen_aliases_without_false_cycle():
    shared = _frozen_object_with_scalar_depth(127)

    accepted = freeze_json({"left": shared, "right": shared})
    digest = canonical_sha256(accepted)

    assert accepted["left"] is accepted["right"] is shared
    assert accepted == accepted
    assert hash(accepted) == hash(accepted)
    assert canonical_sha256(accepted) == digest


def test_freeze_json_at_root_remains_idempotent_at_depth_boundary():
    frozen = _frozen_object_with_scalar_depth(128)

    assert freeze_json(frozen) is frozen


def test_freeze_json_rejects_mutable_storage_in_exact_frozen_object():
    frozen = FrozenJsonObject({"value": 1})
    mutable_items = [("value", 1)]
    object.__setattr__(frozen, "_items", mutable_items)

    with pytest.raises(AdapterContractError, match="immutable"):
        freeze_json(frozen)


def test_excessive_frozen_json_nesting_is_rejected_on_direct_thaw():
    value = 0
    for _ in range(256):
        value = (value,)

    with pytest.raises(AdapterContractError, match="nesting"):
        thaw_json(value)


def test_thaw_json_normalizes_unexpected_frozen_traversal_failures():
    malformed = FrozenJsonObject({"value": 1})
    object.__setattr__(malformed, "_items", _BrokenFrozenItems())

    with pytest.raises(AdapterContractError, match="traversal"):
        thaw_json(malformed)


def test_shared_noncyclic_json_aliases_are_copied_and_accepted():
    shared = {"values": [1, 2]}

    frozen = freeze_json({"left": shared, "right": shared})

    assert frozen["left"] == frozen["right"]
    assert frozen["left"] is not frozen["right"]
    assert thaw_json(frozen) == {
        "left": {"values": [1, 2]},
        "right": {"values": [1, 2]},
    }


def test_frozen_json_equality_and_hash_use_canonical_types():
    frozen_integer = freeze_json({"x": 1})
    equal_integer = freeze_json({"x": 1})
    frozen_float = freeze_json({"x": 1.0})
    frozen_boolean = freeze_json({"x": True})

    assert frozen_integer == equal_integer == {"x": 1}
    assert {"x": 1} == frozen_integer
    assert hash(frozen_integer) == hash(equal_integer)
    assert frozen_integer != frozen_float
    assert frozen_integer != frozen_boolean
    assert frozen_float != frozen_boolean

    frozen_set = {frozen_integer, equal_integer, frozen_float, frozen_boolean}
    assert len(frozen_set) == 3
    lookup = {
        frozen_integer: "integer",
        frozen_float: "float",
        frozen_boolean: "boolean",
    }
    assert lookup[equal_integer] == "integer"
    assert lookup[freeze_json({"x": 1.0})] == "float"
    assert lookup[freeze_json({"x": True})] == "boolean"

    class MalformedMapping(dict):
        def items(self):
            raise RuntimeError("malformed mapping")

    assert frozen_integer != MalformedMapping(x=1)
    assert frozen_integer != object()


def test_json_accepts_1024_bit_integer_boundaries():
    boundary = 2**1024 - 1
    value = {"negative": -boundary, "positive": boundary}

    frozen = freeze_json(value, "payload")
    equal_frozen = freeze_json(value, "payload")
    encoded = canonical_json_bytes(frozen)
    digest = canonical_sha256(frozen)

    assert thaw_json(frozen, "payload") == value
    assert encoded == canonical_json_bytes(value)
    assert digest == canonical_sha256(value)
    assert len(digest) == 64
    assert frozen == frozen == equal_frozen
    assert hash(frozen) == hash(frozen) == hash(equal_frozen)


@pytest.mark.parametrize(
    "value",
    (
        pytest.param(2**1024, id="positive"),
        pytest.param(-(2**1024), id="negative"),
    ),
)
@pytest.mark.parametrize(
    "operation",
    (freeze_json, thaw_json, canonical_json_bytes, canonical_sha256),
    ids=("freeze", "thaw", "canonical_bytes", "canonical_sha256"),
)
def test_json_rejects_integers_beyond_1024_bits(value, operation):
    with pytest.raises(AdapterContractError, match="value.*1024"):
        operation(value)


def test_freeze_json_recursively_prevents_mutation():
    caller_owned = {
        "model": {
            "couplings": [1.0, {"next_nearest": [0.25, 0.5]}],
            "labels": ["α", "β"],
        },
        "enabled": True,
    }
    expected = {
        "enabled": True,
        "model": {
            "couplings": [1.0, {"next_nearest": [0.25, 0.5]}],
            "labels": ["α", "β"],
        },
    }

    frozen = freeze_json(caller_owned)
    digest_before = canonical_sha256(frozen)
    hash_before = hash(frozen)

    caller_owned["model"]["couplings"][1]["next_nearest"].append(0.75)
    caller_owned["model"]["labels"][0] = "changed"
    caller_owned["new"] = "field"

    assert thaw_json(frozen) == expected
    assert canonical_sha256(frozen) == digest_before
    assert hash(frozen) == hash_before == hash(freeze_json(expected))
    assert isinstance(frozen["model"]["couplings"], tuple)
    with pytest.raises(TypeError):
        frozen["new"] = "field"
    with pytest.raises(TypeError):
        frozen["model"]["couplings"][1]["new"] = 1
    with pytest.raises(AttributeError):
        frozen["model"]["labels"].append("γ")


def test_canonical_json_is_sorted_compact_utf8_and_rejects_nan():
    value = {"z": "自旋", "a": [{"β": 2, "a": 1}], "space": "kept value"}

    encoded = canonical_json_bytes(value)

    assert encoded == (
        '{"a":[{"a":1,"β":2}],"space":"kept value","z":"自旋"}'.encode(
            "utf-8"
        )
    )
    assert canonical_sha256(value) == canonical_sha256(freeze_json(value))
    with pytest.raises(AdapterContractError):
        canonical_json_bytes({"nested": [1.0, math.nan]})


SURROGATE_JSON_VALUES = (
    pytest.param({"value": "\ud800"}, id="surrogate_string_value"),
    pytest.param({"\ud800": "value"}, id="surrogate_mapping_key"),
)


@pytest.mark.parametrize("value", SURROGATE_JSON_VALUES)
def test_freeze_json_rejects_non_utf8_unicode_strings(value):
    with pytest.raises(AdapterContractError, match="UTF-8"):
        freeze_json(value)


@pytest.mark.parametrize("value", SURROGATE_JSON_VALUES)
@pytest.mark.parametrize(
    "operation", (canonical_json_bytes, canonical_sha256), ids=("bytes", "sha256")
)
def test_canonical_json_normalizes_non_utf8_unicode_failures(value, operation):
    with pytest.raises(AdapterContractError, match="UTF-8"):
        operation(value)


def test_accepted_frozen_json_remains_reflexive_and_hashable():
    frozen = freeze_json({"label": "自旋", "nested": ["λ", {"spin": 1}]})
    digest = canonical_sha256(frozen)

    assert frozen == frozen
    assert hash(frozen) == hash(frozen)
    assert {frozen} == {freeze_json({"label": "自旋", "nested": ["λ", {"spin": 1}]})}
    assert canonical_sha256(frozen) == digest


def test_thaw_json_rejects_non_utf8_unicode_strings():
    with pytest.raises(AdapterContractError, match="UTF-8"):
        thaw_json("\ud800")


def test_value_schema_units_reject_non_utf8_unicode_strings():
    with pytest.raises(AdapterContractError, match="UTF-8"):
        _number_schema(units="\ud800")


@pytest.mark.parametrize(
    "field_name",
    ("interpreter", "packages", "native_libraries", "backend_resources"),
)
def test_runtime_requirement_strings_reject_non_utf8_unicode(field_name):
    values = {
        "interpreter": "python3",
        "packages": (),
        "native_libraries": (),
        "backend_resources": (),
    }
    values[field_name] = "\ud800" if field_name == "interpreter" else ("\ud800",)

    with pytest.raises(AdapterContractError, match="UTF-8"):
        RuntimeRequirements(**values)


@pytest.mark.parametrize(
    "contract_type",
    (
        ValueSchema,
        ParameterSource,
        CounterfactualDomain,
        ConvergenceContract,
        ProblemSizePolicy,
        RuntimeRequirements,
        ResourceLimits,
        AdapterDefinition,
        EligibilityDecision,
    ),
    ids=lambda contract_type: contract_type.__name__,
)
def test_closed_contract_records_are_runtime_sealed(contract_type):
    with pytest.raises(TypeError, match="sealed|subclass"):
        type(f"Unsafe{contract_type.__name__}", (contract_type,), {})


def test_adapter_rejects_validation_bypassing_schema_subclass():
    try:
        bypass_type = type(
            "BypassingValueSchema",
            (ValueSchema,),
            {"__post_init__": lambda self: None},
        )
    except TypeError:
        return
    bypass = bypass_type(
        kind="object",
        required="not-boolean",
        lower=math.nan,
        upper=None,
        item_schema=None,
        properties=(("exchange", _number_schema()),),
        units=None,
    )
    values = _adapter_values(
        _observable_identity(),
        {"spin_count": [2]},
        {"exchange": {"kind": "finite_interval", "bounds": [0.1, 3.0]}},
    )
    values["scientific_input_schema"] = bypass

    with pytest.raises(AdapterContractError, match="scientific_input_schema"):
        AdapterDefinition(**values)


@pytest.mark.parametrize(
    "field_name", ("packages", "native_libraries", "backend_resources")
)
def test_runtime_requirements_reject_caller_backed_tuple_subclasses(field_name):
    values = {
        "interpreter": "python3",
        "packages": (),
        "native_libraries": (),
        "backend_resources": (),
    }
    values[field_name] = _CallerBackedTuple(["mutable_requirement"])

    with pytest.raises(AdapterContractError, match=field_name):
        RuntimeRequirements(**values)


def test_adapter_rejects_caller_backed_parameter_source_tuple_subclass():
    values = _adapter_values(
        _observable_identity(),
        {"spin_count": [2]},
        {"exchange": {"kind": "finite_interval", "bounds": [0.1, 3.0]}},
    )
    values["parameter_sources"] = _CallerBackedTuple(
        list(values["parameter_sources"])
    )

    with pytest.raises(AdapterContractError, match="parameter_sources"):
        AdapterDefinition(**values)


def test_adapter_observable_identity_uses_one_exact_frozen_snapshot():
    visible = _observable_identity()
    inconsistent = _CustomItemsMapping(
        visible,
        (*visible.items(), ("target", -math.log(2.0))),
    )
    values = _adapter_values(
        inconsistent,
        {"spin_count": [2]},
        {"exchange": {"kind": "finite_interval", "bounds": [0.1, 3.0]}},
    )

    with pytest.raises(AdapterContractError, match="observable_identity|target"):
        AdapterDefinition(**values)


def test_adapter_definition_rejects_missing_unknown_and_mutable_fields():
    observable_identity = {
        "subject": "ground-state energy",
        "system_or_material": "spin-half XXX chain",
        "hamiltonian": {"terms": ["exchange"]},
        "parameter_regime": {"exchange": [1.0]},
        "size_or_limit": {"kind": "thermodynamic_limit"},
        "observable_definition": {"field": "energy_per_site"},
        "units": {"energy_per_site": "J"},
        "conditions": {"temperature": [0.0]},
    }
    fixed_sizes = {"spin_count": [2]}
    valid_rules = {
        "exchange": {"kind": "finite_interval", "bounds": [0.1, 3.0]}
    }
    values = _adapter_values(observable_identity, fixed_sizes, valid_rules)

    definition = AdapterDefinition(**values)
    identity_digest = canonical_sha256(definition.observable_identity)
    size_digest = canonical_sha256(definition.problem_size_policy.fixed_sizes)

    observable_identity["hamiltonian"]["terms"].append("target-dependent term")
    fixed_sizes["spin_count"].append(4)
    valid_rules["exchange"]["bounds"][0] = -100.0

    assert canonical_sha256(definition.observable_identity) == identity_digest
    assert canonical_sha256(definition.problem_size_policy.fixed_sizes) == size_digest
    assert thaw_json(definition.problem_size_policy.fixed_sizes) == {"spin_count": [2]}
    assert thaw_json(definition.counterfactual_domain.valid_rules) == {
        "exchange": {"bounds": [0.1, 3.0], "kind": "finite_interval"}
    }
    assert tuple(field.name for field in dataclasses.fields(AdapterDefinition)) == (
        "adapter_id",
        "entry_symbol",
        "observable_identity",
        "scientific_input_schema",
        "numerical_control_schema",
        "parameter_sources",
        "output_schema",
        "backend_kind",
        "problem_size_policy",
        "runtime_requirements",
        "convergence_contract",
        "counterfactual_domain",
        "oracle_id",
        "resource_limits",
    )

    missing = dict(values)
    missing.pop("oracle_id")
    with pytest.raises(AdapterContractError, match="missing.*oracle_id"):
        AdapterDefinition(**missing)

    with pytest.raises(AdapterContractError, match="unknown|unexpected"):
        AdapterDefinition(**values, expected_result=-math.log(2.0))

    mutable_sources = dict(values)
    mutable_sources["parameter_sources"] = list(values["parameter_sources"])
    with pytest.raises(AdapterContractError, match="parameter_sources"):
        AdapterDefinition(**mutable_sources)

    with pytest.raises(dataclasses.FrozenInstanceError):
        definition.adapter_id = "changed"

    bad_identity = dict(values)
    bad_identity["observable_identity"] = {
        **thaw_json(definition.observable_identity),
        "target": -math.log(2.0),
    }
    with pytest.raises(AdapterContractError, match="observable_identity"):
        AdapterDefinition(**bad_identity)

    for backend_kind in ("", "python", "sparse_ed"):
        with pytest.raises(AdapterContractError, match="backend_kind"):
            AdapterDefinition(**{**values, "backend_kind": backend_kind})

    for invalid_contract in (
        lambda: ParameterSource("exchange", "registry_value", {}),
        lambda: ProblemSizePolicy("dynamic", {}, {}),
        lambda: ConvergenceContract("trust_me", {}),
        lambda: ConvergenceContract([], {}),
    ):
        with pytest.raises(AdapterContractError):
            invalid_contract()

    eligible = EligibilityDecision(
        selector_fields=("energy_per_site",),
        disposition="eligible",
        adapter_id="xxx_bethe_energy",
        oracle_id="xxx_bethe_energy_series_oracle",
        reason=None,
    )
    assert eligible.reason is None
    with pytest.raises(AdapterContractError):
        EligibilityDecision(("energy_per_site",), "eligible", None, None, None)
    with pytest.raises(AdapterContractError):
        EligibilityDecision(
            ("energy_per_site",),
            "source_parse_only",
            "xxx_bethe_energy",
            "xxx_bethe_energy_series_oracle",
            "no_independent_oracle",
        )
    with pytest.raises(AdapterContractError):
        EligibilityDecision(
            ("energy_per_site",),
            "source_parse_only",
            None,
            None,
            "arbitrary_reason",
        )
    source_only = EligibilityDecision(
        ("tc_over_j",),
        "source_parse_only",
        None,
        None,
        "target_equivalent_input",
    )
    assert source_only.adapter_id is source_only.oracle_id is None


@pytest.mark.parametrize(
    "selector_fields",
    (
        pytest.param((), id="empty"),
        pytest.param(["energy_per_site"], id="list"),
        pytest.param(
            _CallerBackedTuple(["energy_per_site"]), id="tuple_subclass"
        ),
        pytest.param(
            ("energy_per_site", "energy_per_site"), id="duplicate"
        ),
        pytest.param(("EnergyPerSite",), id="not_lower_snake_case"),
        pytest.param(("\ud800",), id="non_utf8"),
    ),
)
def test_eligibility_selector_fields_are_exact_nonempty_unique_identifiers(
    selector_fields,
):
    with pytest.raises(AdapterContractError, match="selector_fields"):
        EligibilityDecision(
            selector_fields,
            "eligible",
            "xxx_bethe_energy",
            "xxx_bethe_integral_oracle",
            None,
        )


@pytest.mark.parametrize(
    ("field_name", "diagnostic"),
    (
        ("parameter_source_kind", "kind"),
        ("convergence_kind", "kind"),
        ("problem_size_kind", "kind"),
        ("backend_kind", "backend_kind"),
        ("eligibility_disposition", "disposition"),
        ("eligibility_reason", "reason"),
    ),
)
def test_enum_contracts_do_not_hash_or_repr_untrusted_values(
    field_name, diagnostic
):
    untrusted = BadRepr()

    if field_name == "parameter_source_kind":
        operation = lambda: ParameterSource("exchange", untrusted, {})
    elif field_name == "convergence_kind":
        operation = lambda: ConvergenceContract(untrusted, {})
    elif field_name == "problem_size_kind":
        operation = lambda: ProblemSizePolicy(untrusted, {}, {})
    elif field_name == "backend_kind":
        values = _adapter_values(
            _observable_identity(),
            {"spin_count": [2]},
            {"exchange": {"kind": "finite_interval", "bounds": [0.1, 3.0]}},
        )
        values["backend_kind"] = untrusted
        operation = lambda: AdapterDefinition(**values)
    elif field_name == "eligibility_disposition":
        operation = lambda: EligibilityDecision(
            ("energy_per_site",), untrusted, None, None, None
        )
    else:
        operation = lambda: EligibilityDecision(
            ("energy_per_site",),
            "source_parse_only",
            None,
            None,
            untrusted,
        )

    with pytest.raises(AdapterContractError, match=diagnostic):
        operation()


def test_schema_rejects_bool_where_numeric_is_required():
    for field_name in ("lower", "upper"):
        values = {
            "kind": "number",
            "required": True,
            "lower": 0.0,
            "upper": 1.0,
            "item_schema": None,
            "properties": (),
            "units": "J",
        }
        values[field_name] = True
        with pytest.raises(AdapterContractError, match=field_name):
            ValueSchema(**values)

    with pytest.raises(AdapterContractError, match="cpu_seconds"):
        ResourceLimits(
            cpu_seconds=True,
            wall_seconds=20,
            address_space_bytes=256_000_000,
            output_bytes=64_000,
            file_descriptors=16,
            process_count=1,
        )

    with pytest.raises(AdapterContractError, match="lower"):
        ValueSchema(
            kind="integer",
            required=True,
            lower=math.inf,
            upper=None,
            item_schema=None,
            properties=(),
            units="sites",
        )

    with pytest.raises(AdapterContractError, match="units"):
        ValueSchema(
            kind="number",
            required=True,
            lower=None,
            upper=None,
            item_schema=None,
            properties=(),
            units=None,
        )


def test_value_schema_accepts_1024_bit_integer_bounds():
    boundary = 2**1024 - 1

    schema = ValueSchema(
        kind="number",
        required=True,
        lower=-boundary,
        upper=boundary,
        item_schema=None,
        properties=(),
        units="J",
    )

    assert schema.lower == -boundary
    assert schema.upper == boundary


def test_resource_limits_accept_1024_bit_integer_boundaries():
    boundary = 2**1024 - 1

    limits = ResourceLimits(
        cpu_seconds=boundary,
        wall_seconds=boundary,
        address_space_bytes=boundary,
        output_bytes=boundary,
        file_descriptors=boundary,
        process_count=boundary,
    )

    assert all(
        getattr(limits, field_name) == boundary
        for field_name in (
            "cpu_seconds",
            "wall_seconds",
            "address_space_bytes",
            "output_bytes",
            "file_descriptors",
            "process_count",
        )
    )


@pytest.mark.parametrize("field_name", ("lower", "upper"))
@pytest.mark.parametrize(
    "value",
    (
        pytest.param(2**1024, id="positive"),
        pytest.param(-(2**1024), id="negative"),
    ),
)
def test_value_schema_rejects_integers_beyond_1024_bits(field_name, value):
    values = {
        "kind": "number",
        "required": True,
        "lower": None,
        "upper": None,
        "item_schema": None,
        "properties": (),
        "units": "J",
    }
    values[field_name] = value

    with pytest.raises(AdapterContractError, match=f"{field_name}.*1024"):
        ValueSchema(**values)


@pytest.mark.parametrize(
    "field_name",
    (
        "cpu_seconds",
        "wall_seconds",
        "address_space_bytes",
        "output_bytes",
        "file_descriptors",
        "process_count",
    ),
)
@pytest.mark.parametrize(
    "value",
    (
        pytest.param(2**1024, id="positive"),
        pytest.param(-(2**1024), id="negative"),
    ),
)
def test_resource_limits_reject_integers_beyond_1024_bits(field_name, value):
    values = {
        "cpu_seconds": 10,
        "wall_seconds": 20,
        "address_space_bytes": 256_000_000,
        "output_bytes": 64_000,
        "file_descriptors": 16,
        "process_count": 1,
    }
    values[field_name] = value

    with pytest.raises(AdapterContractError, match=f"{field_name}.*1024"):
        ResourceLimits(**values)


@pytest.mark.parametrize("contract_kind", ("value_schema", "resource_limits"))
@pytest.mark.parametrize(
    "value",
    (
        pytest.param(10**10000, id="positive"),
        pytest.param(-(10**10000), id="negative"),
    ),
)
def test_numeric_contracts_reject_extreme_integers_without_overflow(
    contract_kind, value
):
    with pytest.raises(AdapterContractError, match="1024"):
        if contract_kind == "value_schema":
            ValueSchema(
                kind="number",
                required=True,
                lower=value,
                upper=None,
                item_schema=None,
                properties=(),
                units="J",
            )
        else:
            ResourceLimits(
                cpu_seconds=value,
                wall_seconds=20,
                address_space_bytes=256_000_000,
                output_bytes=64_000,
                file_descriptors=16,
                process_count=1,
            )


@pytest.mark.parametrize(
    ("field_name", "diagnostic"),
    (
        ("cpu_seconds", "cpu_seconds must be positive"),
        ("wall_seconds", "wall_seconds must be positive"),
        ("address_space_bytes", "address_space_bytes must be a positive integer"),
        ("output_bytes", "output_bytes must be a positive integer"),
        ("file_descriptors", "file_descriptors must be a positive integer"),
        ("process_count", "process_count must be a positive integer"),
    ),
)
def test_resource_limits_preserve_within_bound_negative_errors(
    field_name, diagnostic
):
    values = {
        "cpu_seconds": 10,
        "wall_seconds": 20,
        "address_space_bytes": 256_000_000,
        "output_bytes": 64_000,
        "file_descriptors": 16,
        "process_count": 1,
    }
    values[field_name] = -(2**1024 - 1)

    with pytest.raises(AdapterContractError, match=diagnostic):
        ResourceLimits(**values)


@pytest.mark.parametrize("field_name", ("cpu_seconds", "wall_seconds"))
@pytest.mark.parametrize("value", (True, math.nan, math.inf, -math.inf))
def test_resource_limits_reject_bool_and_nonfinite_float_times(field_name, value):
    values = {
        "cpu_seconds": 10,
        "wall_seconds": 20,
        "address_space_bytes": 256_000_000,
        "output_bytes": 64_000,
        "file_descriptors": 16,
        "process_count": 1,
    }
    values[field_name] = value

    with pytest.raises(AdapterContractError, match=field_name):
        ResourceLimits(**values)


def _schema_signature(schema):
    if schema.kind == "list":
        return f"list_{schema.item_schema.kind}"
    return schema.kind


def _fresh_adapter_values():
    return _adapter_values(
        _observable_identity(),
        {"spin_count": 2},
        {"exchange": {"kind": "positive_finite"}},
    )


def test_adapter_definitions_cover_exact_eligible_ids_and_link_field_for_field(
):
    definitions = adapters.ADAPTER_DEFINITIONS

    assert type(definitions) is MappingProxyType
    assert set(definitions) == set(EXPECTED_ELIGIBLE_BY_ADAPTER)
    assert len(definitions) == 29
    assert all(
        type(item) is AdapterDefinition for item in definitions.values()
    )
    for adapter_id, definition in definitions.items():
        selector_fields, oracle_id = EXPECTED_ELIGIBLE_BY_ADAPTER[adapter_id]
        assert definition.adapter_id == adapter_id
        assert definition.entry_symbol == (
            "validation.literature_evidence_adapters:adapter_" + adapter_id
        )
        assert definition.oracle_id == oracle_id
        assert tuple(name for name, _binding in definition.output_schema) == (
            selector_fields
        )
        assert adapters.get_adapter_definition(adapter_id) is definition

    source_parse_ids = {
        adapter_id
        for (
            _benchmark_name,
            _selector_fields,
            disposition,
            adapter_id,
            _oracle_id,
            _reason,
        ) in EXPECTED_ELIGIBILITY
        if disposition == "source_parse_only"
    }
    assert source_parse_ids == {None}

    for invalid_id in (1, "UnknownAdapter", "not_an_adapter"):
        with pytest.raises(AdapterContractError, match="adapter_id|unknown"):
            adapters.get_adapter_definition(invalid_id)


def test_adapter_definition_backend_map_is_exact_and_independent():
    actual = {
        backend: frozenset(
            adapter_id
            for adapter_id, definition in adapters.ADAPTER_DEFINITIONS.items()
            if definition.backend_kind == backend
        )
        for backend in EXPECTED_BACKENDS
    }

    assert actual == EXPECTED_BACKENDS
    assert tuple(len(actual[name]) for name in EXPECTED_BACKENDS) == (
        8,
        4,
        7,
        6,
        4,
    )


def test_adapter_definition_size_policy_assignments_and_data_are_exact():
    definitions = adapters.ADAPTER_DEFINITIONS
    not_applicable = set(EXPECTED_ELIGIBLE_BY_ADAPTER) - FIXED_LOCAL - SCALABLE

    assert len(FIXED_LOCAL) == 7
    assert len(SCALABLE) == 4
    assert len(not_applicable) == 18
    assert set(EXPECTED_SIZE_DATA) == FIXED_LOCAL | SCALABLE

    actual_fixed = {
        adapter_id
        for adapter_id, definition in definitions.items()
        if definition.problem_size_policy.kind == "fixed_local"
    }
    actual_scalable = {
        adapter_id
        for adapter_id, definition in definitions.items()
        if definition.problem_size_policy.kind == "scalable_same_observable"
    }
    actual_not_applicable = {
        adapter_id
        for adapter_id, definition in definitions.items()
        if definition.problem_size_policy.kind == "not_applicable"
    }
    assert (actual_fixed, actual_scalable, actual_not_applicable) == (
        set(FIXED_LOCAL),
        set(SCALABLE),
        not_applicable,
    )

    for adapter_id, definition in definitions.items():
        policy = definition.problem_size_policy
        if adapter_id in FIXED_LOCAL:
            assert policy.fixed_sizes == freeze_json(
                EXPECTED_SIZE_DATA[adapter_id]
            )
            assert not policy.allowed_sizes
        elif adapter_id in SCALABLE:
            assert not policy.fixed_sizes
            assert policy.allowed_sizes == freeze_json(
                EXPECTED_SIZE_DATA[adapter_id]
            )
        else:
            assert not policy.fixed_sizes
            assert not policy.allowed_sizes


def test_adapter_definition_observable_identity_is_complete_and_nonempty():
    exact_keys = {
        "subject",
        "system_or_material",
        "hamiltonian",
        "parameter_regime",
        "size_or_limit",
        "observable_definition",
        "units",
        "conditions",
    }

    identities = []
    for definition in adapters.ADAPTER_DEFINITIONS.values():
        identity = definition.observable_identity
        assert set(identity) == exact_keys
        assert all(
            value not in (None, "", (), False)
            for value in identity.values()
        )
        identities.append(canonical_sha256(identity))
    assert len(set(identities)) == 29


def test_output_schema_records_are_exact_sealed_and_match_every_selector():
    assert adapters.OUTPUT_PROOF_KINDS == frozenset(
        {
            "direct_exact_value",
            "bounded_numeric_value",
            "grouped_exact_sequence",
            "rank_derived_integer",
            "all_residuals_within_bound_boolean",
            "positive_lower_bound_boolean",
            "positive_gap_and_odd_parity_boolean",
            "directional_limits_differ_boolean",
            "no_finite_crossing_boolean",
            "no_finite_crossing_zero_limit",
        }
    )
    assert tuple(
        field.name for field in dataclasses.fields(adapters.OutputFieldBinding)
    ) == ("value_schema", "raw_field", "proof_kind")
    assert tuple(
        field.name for field in dataclasses.fields(adapters.OutputSchema)
    ) == ("fields",)
    for contract_type in (adapters.OutputFieldBinding, adapters.OutputSchema):
        with pytest.raises(TypeError, match="sealed|subclass"):
            type(f"Unsafe{contract_type.__name__}", (contract_type,), {})

    all_raw_fields = []
    for adapter_id, definition in adapters.ADAPTER_DEFINITIONS.items():
        output_schema = definition.output_schema
        assert type(output_schema) is adapters.OutputSchema
        expected_fields = EXPECTED_OUTPUT_CONTRACTS[adapter_id]
        assert tuple(name for name, _binding in output_schema) == tuple(
            expected_fields
        )
        assert output_schema.selector_fields == tuple(expected_fields)
        assert tuple(output_schema.items()) == output_schema.fields

        detached_lookup = output_schema.as_mapping()
        assert type(detached_lookup) is MappingProxyType
        assert tuple(detached_lookup) == tuple(expected_fields)
        for selector_field, binding in output_schema:
            (
                expected_kind,
                expected_units,
                raw_field,
                proof_kind,
            ) = expected_fields[selector_field]
            assert type(binding) is adapters.OutputFieldBinding
            assert type(binding.value_schema) is ValueSchema
            assert binding.value_schema.required is True
            assert _schema_signature(binding.value_schema) == expected_kind
            assert binding.value_schema.units == expected_units
            bounded_schema = (
                binding.value_schema.item_schema
                if binding.value_schema.kind == "list"
                else binding.value_schema
            )
            expected_lower = (
                0
                if (adapter_id, selector_field)
                in EXPECTED_NONNEGATIVE_OUTPUT_FIELDS
                else None
            )
            assert bounded_schema.lower == expected_lower
            assert bounded_schema.upper is None
            if binding.value_schema.kind == "list":
                exact_length = EXPECTED_LIST_OUTPUT_LENGTHS[
                    (adapter_id, selector_field)
                ]
                assert binding.value_schema.lower == exact_length
                assert binding.value_schema.upper == exact_length
            assert (binding.raw_field, binding.proof_kind) == (
                raw_field,
                proof_kind,
            )
            assert output_schema[selector_field] is binding
            all_raw_fields.append(binding.raw_field)
            if binding.value_schema.kind == "boolean":
                assert binding.proof_kind not in {
                    "direct_exact_value",
                    "bounded_numeric_value",
                }
                assert not binding.raw_field.endswith(("status", "boolean"))

    assert set(EXPECTED_OUTPUT_CONTRACTS) == set(EXPECTED_ELIGIBLE_BY_ADAPTER)
    assert len(all_raw_fields) == len(set(all_raw_fields))


def test_list_value_schema_uses_nonnegative_integer_item_count_bounds():
    item_schema = _number_schema(units="J")
    exact_three = ValueSchema(
        kind="list",
        required=True,
        lower=3,
        upper=3,
        item_schema=item_schema,
        properties=(),
        units="J",
    )

    assert (exact_three.lower, exact_three.upper) == (3, 3)
    for lower, upper in ((True, 3), (1.5, 3), (-1, 3), (4, 3)):
        with pytest.raises(
            AdapterContractError,
            match="lower|upper|item.count",
        ):
            ValueSchema(
                kind="list",
                required=True,
                lower=lower,
                upper=upper,
                item_schema=item_schema,
                properties=(),
                units="J",
            )


def test_output_schema_rejects_duplicates_subclasses_and_caller_aliases():
    binding = adapters.OutputFieldBinding(
        value_schema=_number_schema(units="J"),
        raw_field="raw_energy_expression",
        proof_kind="direct_exact_value",
    )
    caller_fields = (("energy_per_site", binding),)
    schema = adapters.OutputSchema(fields=caller_fields)

    assert schema.fields == caller_fields
    with pytest.raises(AdapterContractError, match="duplicate"):
        adapters.OutputSchema(
            fields=(
                ("energy_per_site", binding),
                ("energy_per_site", binding),
            )
        )
    with pytest.raises(AdapterContractError, match="fields"):
        adapters.OutputSchema(fields=list(caller_fields))
    with pytest.raises(AdapterContractError, match="proof_kind"):
        adapters.OutputFieldBinding(
            value_schema=_number_schema(units="J"),
            raw_field="raw_energy_expression",
            proof_kind="trusted_status_literal",
        )
    with pytest.raises(KeyError):
        schema["unknown_field"]


@pytest.mark.parametrize(
    ("field_name", "tampered_value"),
    (
        ("proof_kind", "made_up_proof"),
        ("raw_field", "RawField"),
        ("value_schema", _object_schema(())),
    ),
)
def test_adapter_definition_revalidates_tampered_output_bindings(
    field_name, tampered_value
):
    binding = adapters.OutputFieldBinding(
        _number_schema(units="J"),
        "raw_bethe_energy_expression",
        "direct_exact_value",
    )
    output_schema = adapters.OutputSchema(
        fields=(("energy_per_site", binding),)
    )
    object.__setattr__(binding, field_name, tampered_value)
    values = _fresh_adapter_values()
    values["output_schema"] = output_schema

    with pytest.raises(
        AdapterContractError,
        match="output_schema|proof_kind|raw_field|value_schema",
    ):
        AdapterDefinition(**values)


@pytest.mark.parametrize("tampered_fields", ([], "duplicate", "wrong_binding"))
def test_adapter_definition_revalidates_tampered_output_schema_fields(
    tampered_fields
):
    binding = adapters.OutputFieldBinding(
        _number_schema(units="J"),
        "raw_bethe_energy_expression",
        "direct_exact_value",
    )
    output_schema = adapters.OutputSchema(
        fields=(("energy_per_site", binding),)
    )
    if tampered_fields == "duplicate":
        tampered_fields = (
            ("energy_per_site", binding),
            ("energy_per_site", binding),
        )
    elif tampered_fields == "wrong_binding":
        tampered_fields = (("energy_per_site", object()),)
    object.__setattr__(output_schema, "fields", tampered_fields)
    values = _fresh_adapter_values()
    values["output_schema"] = output_schema

    with pytest.raises(
        AdapterContractError,
        match="output_schema|fields|binding",
    ):
        AdapterDefinition(**values)


def test_adapter_definition_snapshots_output_schema_and_binding_aliases():
    binding = adapters.OutputFieldBinding(
        _number_schema(units="J"),
        "raw_bethe_energy_expression",
        "direct_exact_value",
    )
    output_schema = adapters.OutputSchema(
        fields=(("energy_per_site", binding),)
    )
    values = _fresh_adapter_values()
    values["output_schema"] = output_schema

    definition = AdapterDefinition(**values)
    object.__setattr__(binding, "proof_kind", "made_up_proof")
    object.__setattr__(output_schema, "fields", ())

    stored_binding = definition.output_schema["energy_per_site"]
    assert stored_binding.proof_kind == "direct_exact_value"
    assert definition.output_schema.selector_fields == ("energy_per_site",)


def _nested_list_schema(depth):
    schema = _number_schema(units="J")
    for _ in range(depth):
        schema = ValueSchema(
            kind="list",
            required=True,
            lower=1,
            upper=1,
            item_schema=schema,
            properties=(),
            units="J",
        )
    return schema


@pytest.mark.parametrize("cycle_kind", ("item_schema", "properties"))
def test_output_schema_snapshot_rejects_value_schema_cycles(cycle_kind):
    if cycle_kind == "item_schema":
        schema = _nested_list_schema(1)
        object.__setattr__(schema, "item_schema", schema)
        snapshot = lambda: adapters.OutputFieldBinding(
            schema,
            "raw_cyclic_value",
            "direct_exact_value",
        )
    else:
        schema = _object_schema((("child", _number_schema(units="J")),))
        object.__setattr__(schema, "properties", (("child", schema),))
        snapshot = lambda: adapters._snapshot_value_schema(
            schema,
            "value_schema",
        )

    with pytest.raises(AdapterContractError, match="cycle|nesting|recursion"):
        snapshot()


def test_output_schema_snapshot_enforces_128_level_nesting_boundary():
    accepted = adapters._snapshot_value_schema(
        _nested_list_schema(128), "value_schema"
    )

    assert type(accepted) is ValueSchema
    with pytest.raises(AdapterContractError, match="nesting|128"):
        adapters._snapshot_value_schema(
            _nested_list_schema(129),
            "value_schema",
        )


def test_output_schema_snapshot_allows_shared_noncyclic_subschemas():
    shared = _number_schema(units="J")
    schema = _object_schema((('left', shared), ('right', shared)))

    snapshot = adapters._snapshot_value_schema(schema, "value_schema")

    assert tuple(name for name, _child in snapshot.properties) == (
        "left",
        "right",
    )


def _schema_context_values(context, schema):
    values = _fresh_adapter_values()
    values[context] = schema
    return values


def _schema_context_property_name(context):
    if context == "scientific_input_schema":
        return "exchange"
    return "root_residual_threshold"


def _schema_context_at_depth(context, depth):
    property_name = _schema_context_property_name(context)
    return _object_schema(
        ((property_name, _nested_list_schema(depth - 1)),)
    )


@pytest.mark.parametrize(
    "context",
    ("scientific_input_schema", "numerical_control_schema"),
)
@pytest.mark.parametrize("cycle_kind", ("item_schema", "properties"))
def test_adapter_definition_schema_contexts_reject_cycles(
    context,
    cycle_kind,
):
    property_name = _schema_context_property_name(context)
    if cycle_kind == "item_schema":
        child = _nested_list_schema(1)
        object.__setattr__(child, "item_schema", child)
        schema = _object_schema(((property_name, child),))
    else:
        schema = _object_schema(((property_name, _number_schema()),))
        object.__setattr__(schema, "properties", ((property_name, schema),))

    values = _schema_context_values(context, schema)
    with pytest.raises(
        AdapterContractError,
        match="cycle|nesting|recursion",
    ):
        AdapterDefinition(**values)


@pytest.mark.parametrize(
    "context",
    ("scientific_input_schema", "numerical_control_schema"),
)
def test_adapter_definition_schema_contexts_enforce_128_level_boundary(
    context,
):
    accepted_schema = _schema_context_at_depth(context, 128)
    accepted_values = _schema_context_values(context, accepted_schema)

    accepted = AdapterDefinition(**accepted_values)

    assert type(getattr(accepted, context)) is ValueSchema
    rejected_schema = _schema_context_at_depth(context, 129)
    rejected_values = _schema_context_values(context, rejected_schema)
    with pytest.raises(AdapterContractError, match="nesting|128"):
        AdapterDefinition(**rejected_values)


@pytest.mark.parametrize(
    "context",
    ("scientific_input_schema", "numerical_control_schema"),
)
def test_adapter_definition_schema_contexts_allow_shared_acyclic_children(
    context,
):
    shared = _number_schema(units="J")
    nested = _object_schema((("left", shared), ("right", shared)))
    property_name = _schema_context_property_name(context)
    schema = _object_schema(((property_name, nested),))
    values = _schema_context_values(context, schema)

    definition = AdapterDefinition(**values)

    stored_nested = getattr(definition, context).properties[0][1]
    assert tuple(name for name, _child in stored_nested.properties) == (
        "left",
        "right",
    )


def test_adapter_definition_rejects_numerical_control_scientific_provenance():
    values = _fresh_adapter_values()
    values["parameter_sources"] = (
        ParameterSource(
            parameter_name="exchange",
            kind="numerical_control",
            details={"physical_role": "exchange scale"},
        ),
    )

    with pytest.raises(
        AdapterContractError,
        match="parameter_sources|provenance|numerical.control|scientific",
    ):
        AdapterDefinition(**values)


def test_adapter_definition_rejects_scientific_control_property_overlap():
    values = _fresh_adapter_values()
    values["numerical_control_schema"] = _object_schema(
        (("exchange", _number_schema(units="J")),)
    )

    with pytest.raises(
        AdapterContractError,
        match="scientific.*control|control.*scientific|overlap|disjoint",
    ):
        AdapterDefinition(**values)


def test_adapter_definition_revalidates_tampered_parameter_source_kind():
    values = _fresh_adapter_values()
    parameter_source = values["parameter_sources"][0]
    object.__setattr__(parameter_source, "kind", "numerical_control")

    with pytest.raises(
        AdapterContractError,
        match="parameter_sources|provenance|numerical.control|scientific",
    ):
        AdapterDefinition(**values)


def test_adapter_definition_provenance_is_complete_exact_and_disjoint():
    allowed_source_kinds = {
        "canonical_model_parameter",
        "source_model_parameter",
        "universal_probe",
        "numerical_control",
    }

    for definition in adapters.ADAPTER_DEFINITIONS.values():
        scientific = definition.scientific_input_schema
        controls = definition.numerical_control_schema
        assert type(scientific) is ValueSchema and scientific.kind == "object"
        assert type(controls) is ValueSchema and controls.kind == "object"
        scientific_names = tuple(
            name for name, _schema in scientific.properties
        )
        control_names = tuple(name for name, _schema in controls.properties)
        source_names = tuple(
            source.parameter_name for source in definition.parameter_sources
        )
        assert scientific_names
        assert set(scientific_names) == EXPECTED_SCIENTIFIC_INPUT_NAMES[
            definition.adapter_id
        ]
        assert set(control_names) == EXPECTED_CONTROL_NAMES[
            definition.adapter_id
        ]
        assert len(source_names) == len(set(source_names))
        assert set(source_names) == set(scientific_names)
        assert set(scientific_names).isdisjoint(control_names)
        assert all(
            type(source) is ParameterSource
            and source.kind in allowed_source_kinds - {"numerical_control"}
            and bool(source.details)
            for source in definition.parameter_sources
        )


def test_adapter_definition_domains_convergence_runtime_and_resources_are_closed(  # noqa: E501
):
    convergence_kinds = {
        "exact",
        "residual_bound",
        "finite_size",
        "quadrature",
        "iterative",
    }

    for definition in adapters.ADAPTER_DEFINITIONS.values():
        scientific_names = {
            name
            for name, _schema in definition.scientific_input_schema.properties
        }
        domain = definition.counterfactual_domain
        assert bool(domain.valid_rules)
        assert bool(domain.invalid_rules)
        assert scientific_names <= set(domain.valid_rules)
        assert scientific_names <= set(domain.invalid_rules)
        assert "physical_size_rule" in domain.valid_rules
        assert "physical_size_rule" in domain.invalid_rules

        convergence = definition.convergence_contract
        assert convergence.kind in convergence_kinds
        assert bool(convergence.requirements)

        runtime = definition.runtime_requirements
        assert runtime.interpreter == "python3"
        assert type(runtime.packages) is tuple
        assert type(runtime.native_libraries) is tuple
        assert type(runtime.backend_resources) is tuple
        assert len(runtime.packages) == len(set(runtime.packages))

        limits = definition.resource_limits
        assert 0 < limits.cpu_seconds <= 120
        assert 0 < limits.wall_seconds <= 120
        assert 0 < limits.address_space_bytes <= 2 * 1024**3
        assert 0 < limits.output_bytes <= 1024**2
        assert 0 < limits.file_descriptors <= 64
        assert limits.process_count == 1


def test_adapter_definition_builder_rejects_duplicates_and_caller_aliases():
    definitions = tuple(adapters.ADAPTER_DEFINITIONS.values())
    duplicated = definitions[0]

    with pytest.raises(AdapterContractError, match="duplicate.*adapter"):
        adapters._build_adapter_definitions((duplicated, duplicated))

    caller_definitions = [
        AdapterDefinition(**_definition_values_from(definition))
        for definition in definitions
    ]
    rebuilt = adapters._build_adapter_definitions(caller_definitions)
    first_adapter_id = caller_definitions[0].adapter_id
    first_oracle_id = caller_definitions[0].oracle_id
    object.__setattr__(caller_definitions[0], "oracle_id", "made_up_oracle")
    object.__setattr__(
        caller_definitions[0].output_schema.fields[0][1],
        "proof_kind",
        "made_up_proof",
    )
    caller_definitions.clear()

    assert type(rebuilt) is MappingProxyType
    assert tuple(rebuilt) == tuple(adapters.ADAPTER_DEFINITIONS)
    assert len({item.oracle_id for item in rebuilt.values()}) == 29
    assert rebuilt[first_adapter_id].oracle_id == first_oracle_id
    assert (
        rebuilt[first_adapter_id].output_schema.fields[0][1].proof_kind
        in adapters.OUTPUT_PROOF_KINDS
    )
    with pytest.raises(TypeError):
        rebuilt[definitions[0].adapter_id] = definitions[0]


def _definition_values_from(definition):
    return {
        field.name: getattr(definition, field.name)
        for field in dataclasses.fields(AdapterDefinition)
    }


def _detached_value_schema(schema):
    return ValueSchema(
        kind=schema.kind,
        required=schema.required,
        lower=schema.lower,
        upper=schema.upper,
        item_schema=(
            None
            if schema.item_schema is None
            else _detached_value_schema(schema.item_schema)
        ),
        properties=tuple(
            (name, _detached_value_schema(child))
            for name, child in schema.properties
        ),
        units=schema.units,
    )


def _detached_adapter_definition(definition):
    policy = definition.problem_size_policy
    runtime = definition.runtime_requirements
    convergence = definition.convergence_contract
    domain = definition.counterfactual_domain
    limits = definition.resource_limits
    return AdapterDefinition(
        adapter_id=definition.adapter_id,
        entry_symbol=definition.entry_symbol,
        observable_identity=freeze_json(
            thaw_json(definition.observable_identity)
        ),
        scientific_input_schema=_detached_value_schema(
            definition.scientific_input_schema
        ),
        numerical_control_schema=_detached_value_schema(
            definition.numerical_control_schema
        ),
        parameter_sources=tuple(
            ParameterSource(
                source.parameter_name,
                source.kind,
                thaw_json(source.details),
            )
            for source in definition.parameter_sources
        ),
        output_schema=definition.output_schema,
        backend_kind=definition.backend_kind,
        problem_size_policy=ProblemSizePolicy(
            policy.kind,
            thaw_json(policy.fixed_sizes),
            thaw_json(policy.allowed_sizes),
        ),
        runtime_requirements=RuntimeRequirements(
            runtime.interpreter,
            tuple(runtime.packages),
            tuple(runtime.native_libraries),
            tuple(runtime.backend_resources),
        ),
        convergence_contract=ConvergenceContract(
            convergence.kind,
            thaw_json(convergence.requirements),
        ),
        counterfactual_domain=CounterfactualDomain(
            thaw_json(domain.valid_rules),
            thaw_json(domain.invalid_rules),
        ),
        oracle_id=definition.oracle_id,
        resource_limits=ResourceLimits(
            limits.cpu_seconds,
            limits.wall_seconds,
            limits.address_space_bytes,
            limits.output_bytes,
            limits.file_descriptors,
            limits.process_count,
        ),
    )


def _alias_probe_pair(layer, alias_field):
    if layer == "direct":
        source_values = _fresh_adapter_values()
        source_values["observable_identity"] = freeze_json(
            source_values["observable_identity"]
        )
        source_values["numerical_control_schema"] = _object_schema(
            (
                (
                    "root_residual_threshold",
                    _number_schema(units="dimensionless"),
                ),
            )
        )
        stored = AdapterDefinition(**source_values)
        return source_values, stored

    target_adapter_id = {
        "numerical_control_schema": "square_ising_self_dual_tc",
        "problem_size_policy": "spin_ice_tetrahedron_enumeration",
    }.get(alias_field, "xxx_bethe_energy")
    callers = [
        _detached_adapter_definition(definition)
        for definition in adapters.ADAPTER_DEFINITIONS.values()
    ]
    catalog = adapters._build_adapter_definitions(callers)
    caller = next(
        definition
        for definition in callers
        if definition.adapter_id == target_adapter_id
    )
    return _definition_values_from(caller), catalog[target_adapter_id]


@pytest.mark.parametrize("layer", ("direct", "catalog"))
@pytest.mark.parametrize(
    "alias_field",
    (
        "observable_identity",
        "scientific_input_schema",
        "numerical_control_schema",
        "parameter_source",
        "parameter_source_details",
        "problem_size_policy",
        "runtime_requirements",
        "convergence_contract",
        "counterfactual_domain",
        "resource_limits",
    ),
)
def test_adapter_metadata_snapshots_isolate_all_caller_aliases(
    layer,
    alias_field,
):
    source_values, stored = _alias_probe_pair(layer, alias_field)

    if alias_field == "observable_identity":
        caller_record = source_values[alias_field]
        caller_nested = caller_record["hamiltonian"]
        stored_nested = stored.observable_identity["hamiltonian"]
        digest = canonical_sha256(stored.observable_identity)
        object.__setattr__(caller_nested, "_items", ())
        assert canonical_sha256(stored.observable_identity) == digest
        assert stored.observable_identity is not caller_record
        assert stored_nested is not caller_nested
    elif alias_field in {
        "scientific_input_schema",
        "numerical_control_schema",
    }:
        caller_record = source_values[alias_field]
        caller_child = caller_record.properties[0][1]
        stored_record = getattr(stored, alias_field)
        stored_child = stored_record.properties[0][1]
        units = stored_child.units
        object.__setattr__(caller_child, "units", "caller_mutation")
        assert stored_child.units == units
        assert stored_record is not caller_record
        assert stored_child is not caller_child
    elif alias_field == "parameter_source":
        caller_record = source_values["parameter_sources"][0]
        stored_record = stored.parameter_sources[0]
        kind = stored_record.kind
        object.__setattr__(caller_record, "kind", "numerical_control")
        assert stored_record.kind == kind
        assert stored_record is not caller_record
    elif alias_field == "parameter_source_details":
        caller_source = source_values["parameter_sources"][0]
        caller_record = caller_source.details
        stored_source = stored.parameter_sources[0]
        digest = canonical_sha256(stored_source.details)
        object.__setattr__(caller_record, "_items", ())
        assert canonical_sha256(stored_source.details) == digest
        assert stored_source is not caller_source
        assert stored_source.details is not caller_record
    elif alias_field == "problem_size_policy":
        caller_record = source_values[alias_field]
        stored_record = stored.problem_size_policy
        digest = canonical_sha256(stored_record.fixed_sizes)
        kind = stored_record.kind
        object.__setattr__(caller_record, "kind", "not_applicable")
        object.__setattr__(caller_record.fixed_sizes, "_items", ())
        assert stored_record.kind == kind
        assert canonical_sha256(stored_record.fixed_sizes) == digest
        assert stored_record is not caller_record
    elif alias_field == "runtime_requirements":
        caller_record = source_values[alias_field]
        stored_record = stored.runtime_requirements
        packages = stored_record.packages
        object.__setattr__(caller_record, "packages", ("caller_mutation",))
        assert stored_record.packages == packages
        assert stored_record is not caller_record
    elif alias_field == "convergence_contract":
        caller_record = source_values[alias_field]
        stored_record = stored.convergence_contract
        digest = canonical_sha256(stored_record.requirements)
        kind = stored_record.kind
        object.__setattr__(caller_record, "kind", "iterative")
        object.__setattr__(caller_record.requirements, "_items", ())
        assert stored_record.kind == kind
        assert canonical_sha256(stored_record.requirements) == digest
        assert stored_record is not caller_record
    elif alias_field == "counterfactual_domain":
        caller_record = source_values[alias_field]
        stored_record = stored.counterfactual_domain
        digest = canonical_sha256(stored_record.valid_rules)
        object.__setattr__(caller_record.valid_rules, "_items", ())
        assert canonical_sha256(stored_record.valid_rules) == digest
        assert stored_record is not caller_record
    else:
        caller_record = source_values[alias_field]
        stored_record = stored.resource_limits
        cpu_seconds = stored_record.cpu_seconds
        object.__setattr__(caller_record, "cpu_seconds", 999)
        assert stored_record.cpu_seconds == cpu_seconds
        assert stored_record is not caller_record


def test_adapter_definition_builder_rejects_type_cardinality_and_linkage_drift(
):
    definitions = tuple(adapters.ADAPTER_DEFINITIONS.values())

    with pytest.raises(AdapterContractError, match="AdapterDefinition"):
        adapters._build_adapter_definitions((object(), *definitions[1:]))
    with pytest.raises(AdapterContractError, match="exactly 29"):
        adapters._build_adapter_definitions(definitions[:-1])

    first = definitions[0]
    wrong_id = AdapterDefinition(
        **{
            **_definition_values_from(first),
            "adapter_id": "unique_extra_adapter",
            "entry_symbol": (
                "validation.literature_evidence_adapters:"
                "adapter_unique_extra_adapter"
            ),
        }
    )
    with pytest.raises(
        AdapterContractError,
        match="eligible.*adapter|key set",
    ):
        adapters._build_adapter_definitions((wrong_id, *definitions[1:]))

    wrong_oracle = AdapterDefinition(
        **{
            **_definition_values_from(first),
            "oracle_id": "independent_but_unlinked_oracle",
        }
    )
    with pytest.raises(AdapterContractError, match="oracle"):
        adapters._build_adapter_definitions((wrong_oracle, *definitions[1:]))

    wrong_output = AdapterDefinition(
        **{
            **_definition_values_from(first),
            "output_schema": adapters.OutputSchema(
                fields=(
                    (
                        "unlinked_selector",
                        adapters.OutputFieldBinding(
                            _number_schema(units="J"),
                            "raw_unlinked_calculation",
                            "direct_exact_value",
                        ),
                    ),
                )
            ),
        }
    )
    with pytest.raises(AdapterContractError, match="selector"):
        adapters._build_adapter_definitions((wrong_output, *definitions[1:]))

    fixed_definition = adapters.ADAPTER_DEFINITIONS[
        "spin_ice_tetrahedron_enumeration"
    ]
    wrong_size_data = AdapterDefinition(
        **{
            **_definition_values_from(fixed_definition),
            "problem_size_policy": ProblemSizePolicy(
                "fixed_local", {"spin_count": 6, "tetrahedra": 1}, {}
            ),
        }
    )
    replaced = tuple(
        wrong_size_data
        if item.adapter_id == wrong_size_data.adapter_id
        else item
        for item in definitions
    )
    with pytest.raises(AdapterContractError, match="size data"):
        adapters._build_adapter_definitions(replaced)


def test_adapter_definition_rejects_entry_symbol_mismatch_without_resolving_it(
):
    values = _fresh_adapter_values()
    values["entry_symbol"] = (
        "validation.literature_evidence_adapters:adapter_unlinked_symbol"
    )

    with pytest.raises(AdapterContractError, match="entry_symbol.*exact"):
        AdapterDefinition(**values)


FORBIDDEN_METADATA_CASES = (
    pytest.param(
        "observable_identity",
        "expected",
        id="observable_nested_plain_token",
    ),
    pytest.param(
        "observable_identity",
        "taggedExpectedValue",
        id="observable_nested_camel_alias",
    ),
    pytest.param(
        "scientific_input_schema",
        "answer_value",
        id="scientific_property",
    ),
    pytest.param(
        "parameter_source_details",
        "approved-verdict",
        id="provenance_nested_punctuation_alias",
    ),
    pytest.param("fixed_sizes", "RegistryTag", id="size_data_camel_alias"),
    pytest.param(
        "convergence",
        "comparison.tag",
        id="convergence_punctuation",
    ),
    pytest.param("counterfactual", "sourceOperand", id="domain_camel_pair"),
    pytest.param(
        "counterfactual",
        "sourceoperand",
        id="domain_lowercase_glued_pair",
    ),
    pytest.param("runtime", "solver-report-addon", id="runtime_punctuation"),
    pytest.param("runtime", "sealedEvidenceTag", id="evidence_camel_alias"),
    pytest.param(
        "counterfactual",
        "numeric-tolerance-tag",
        id="tolerance_punctuation_alias",
    ),
    pytest.param(
        "output_selector",
        "expected_value",
        id="selector_identifier",
    ),
    pytest.param("raw_field", "raw_target_value", id="raw_identifier"),
    pytest.param("proof_kind", "answer-proof", id="proof_binding"),
    pytest.param("output_units", "result/unit", id="schema_units"),
)


@pytest.mark.parametrize(
    ("location", "forbidden_value"),
    FORBIDDEN_METADATA_CASES,
)
def test_adapter_definition_rejects_forbidden_vocabulary_at_arbitrary_nesting(
    location, forbidden_value
):
    values = _fresh_adapter_values()
    if location == "observable_identity":
        identity = _observable_identity()
        identity["conditions"] = {"nested": [{forbidden_value: "forbidden"}]}
        values["observable_identity"] = identity
    elif location == "scientific_input_schema":
        values["scientific_input_schema"] = _object_schema(
            ((forbidden_value, _number_schema(units="J")),)
        )
        values["parameter_sources"] = (
            ParameterSource(
                forbidden_value,
                "canonical_model_parameter",
                {"canonical_path": ["hamiltonian", "exchange"]},
            ),
        )
    elif location == "parameter_source_details":
        values["parameter_sources"] = (
            ParameterSource(
                "exchange",
                "canonical_model_parameter",
                {"canonical_path": ["hamiltonian", {forbidden_value: "tag"}]},
            ),
        )
    elif location == "fixed_sizes":
        values["problem_size_policy"] = ProblemSizePolicy(
            "fixed_local",
            {"spin_count": 2, "nested": {forbidden_value: 1}},
            {},
        )
    elif location == "convergence":
        values["convergence_contract"] = ConvergenceContract(
            "exact", {"derivation": {forbidden_value: "present"}}
        )
    elif location == "counterfactual":
        values["counterfactual_domain"] = CounterfactualDomain(
            {"exchange": {"kind": forbidden_value}},
            {"exchange": {"kind": "nonpositive"}},
        )
    elif location == "runtime":
        values["runtime_requirements"] = RuntimeRequirements(
            "python3", (forbidden_value,), (), ()
        )
    else:
        selector = "energy_per_site"
        raw_field = "raw_bethe_energy_expression"
        proof_kind = "direct_exact_value"
        units = "J"
        if location == "output_selector":
            selector = forbidden_value
        elif location == "raw_field":
            raw_field = forbidden_value
        elif location == "proof_kind":
            proof_kind = forbidden_value
        elif location == "output_units":
            units = forbidden_value
        if location in {"output_selector", "raw_field", "proof_kind"}:
            with pytest.raises(AdapterContractError, match="forbidden"):
                adapters.OutputSchema(
                    fields=(
                        (
                            selector,
                            adapters.OutputFieldBinding(
                                _number_schema(units=units),
                                raw_field,
                                proof_kind,
                            ),
                        ),
                    )
                )
            return
        values["output_schema"] = adapters.OutputSchema(
            fields=(
                (
                    selector,
                    adapters.OutputFieldBinding(
                        _number_schema(units=units), raw_field, proof_kind
                    ),
                ),
            )
        )

    with pytest.raises(AdapterContractError, match="forbidden"):
        AdapterDefinition(**values)


def test_forbidden_vocabulary_does_not_confuse_residual_with_result():
    values = _fresh_adapter_values()
    values["convergence_contract"] = ConvergenceContract(
        "residual_bound", {"residual_norm": "derived_from_lower_level_data"}
    )

    definition = AdapterDefinition(**values)

    assert definition.convergence_contract.kind == "residual_bound"


def test_forbidden_vocabulary_diagnostics_do_not_repr_or_hash_custom_objects():
    values = _fresh_adapter_values()
    identity = _observable_identity()
    identity["conditions"] = {"nested": [BadRepr()]}
    values["observable_identity"] = identity

    with pytest.raises(AdapterContractError, match="observable_identity|JSON"):
        AdapterDefinition(**values)


NUMERICAL_CONTROL_ONLY_NAMES = (
    "quadrature_absolute_threshold",
    "eigensolver_residual_threshold",
    "truncation_cutoff",
    "momentum_refinement_grid",
    "series_refinement_terms",
    "maximum_refinement_iterations",
    "root_residual_threshold",
    "quadrature_max_subintervals",
    "kernel_residual_bound",
    "gap_residual_bound",
    "constraint_residual_bound",
    "branch_residual_bound",
)


def test_numerical_control_only_names_are_accepted_in_control_schema():
    values = _fresh_adapter_values()
    values["numerical_control_schema"] = _object_schema(
        tuple(
            (name, _number_schema())
            for name in NUMERICAL_CONTROL_ONLY_NAMES
        )
    )
    values["convergence_contract"] = ConvergenceContract(
        "iterative",
        {"successive_estimates": "form_a_convergent_sequence"},
    )

    definition = AdapterDefinition(**values)

    assert tuple(
        name
        for name, _schema in definition.numerical_control_schema.properties
    ) == tuple(sorted(NUMERICAL_CONTROL_ONLY_NAMES))


def test_physical_threshold_terms_are_not_misclassified_as_numerical_controls(
):
    values = _fresh_adapter_values()
    identity = _observable_identity()
    identity["conditions"] = {"spiral_threshold": "calculated_boundary"}
    values["observable_identity"] = identity
    values["output_schema"] = adapters.OutputSchema(
        fields=(
            (
                "energy_per_site",
                adapters.OutputFieldBinding(
                    _number_schema(units="J"),
                    "raw_kernel_minimum_threshold",
                    "bounded_numeric_value",
                ),
            ),
        )
    )

    definition = AdapterDefinition(**values)

    assert (
        definition.output_schema["energy_per_site"].raw_field
        == "raw_kernel_minimum_threshold"
    )


@pytest.mark.parametrize(
    "location",
    (
        "scientific_input_schema",
        "observable_identity",
        "output_selector",
        "raw_field",
        "provenance_parameter",
        "counterfactual_domain",
        "convergence_contract",
        "runtime_requirements",
    ),
)
@pytest.mark.parametrize("control_name", NUMERICAL_CONTROL_ONLY_NAMES)
def test_numerical_control_only_names_are_rejected_outside_control_schema(
    location, control_name
):
    values = _fresh_adapter_values()
    if location == "scientific_input_schema":
        values["scientific_input_schema"] = _object_schema(
            ((control_name, _number_schema()),)
        )
        values["parameter_sources"] = (
            ParameterSource(
                control_name,
                "canonical_model_parameter",
                {"canonical_path": ["hamiltonian", "exchange"]},
            ),
        )
    elif location == "observable_identity":
        identity = _observable_identity()
        identity["conditions"] = {control_name: 1e-10}
        values["observable_identity"] = identity
    elif location == "provenance_parameter":
        values["parameter_sources"] = (
            ParameterSource(
                control_name,
                "canonical_model_parameter",
                {"canonical_path": ["hamiltonian", "exchange"]},
            ),
        )
    elif location == "counterfactual_domain":
        values["counterfactual_domain"] = CounterfactualDomain(
            {
                "exchange": {"kind": "positive_finite"},
                control_name: {"kind": "positive"},
            },
            {"exchange": {"kind": "nonpositive"}},
        )
    elif location == "convergence_contract":
        values["convergence_contract"] = ConvergenceContract(
            "iterative", {control_name: 1e-10}
        )
    elif location == "runtime_requirements":
        values["runtime_requirements"] = RuntimeRequirements(
            "python3", (control_name,), (), ()
        )
    else:
        selector = (
            control_name
            if location == "output_selector"
            else "energy_per_site"
        )
        raw_field = (
            control_name
            if location == "raw_field"
            else "raw_energy_value"
        )
        if location in {"output_selector", "raw_field"}:
            with pytest.raises(
                AdapterContractError,
                match="numerical.control",
            ):
                adapters.OutputSchema(
                    fields=(
                        (
                            selector,
                            adapters.OutputFieldBinding(
                                _number_schema(units="J"),
                                raw_field,
                                "direct_exact_value",
                            ),
                        ),
                    )
                )
            return
        values["output_schema"] = adapters.OutputSchema(
            fields=(
                (
                    selector,
                    adapters.OutputFieldBinding(
                        _number_schema(units="J"),
                        raw_field,
                        "direct_exact_value",
                    ),
                ),
            )
        )

    with pytest.raises(AdapterContractError, match="numerical.control"):
        AdapterDefinition(**values)
