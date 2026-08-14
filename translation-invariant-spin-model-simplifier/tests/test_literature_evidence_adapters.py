import ast
import dataclasses
import dis
import hmac
import hashlib
import inspect
from itertools import product
import json
import math
import os
import pathlib
import re
import stat
import string
import subprocess
import sys
import tracemalloc
from collections import deque
from collections.abc import Mapping
from pathlib import Path, PurePath, PurePosixPath
from types import MappingProxyType, ModuleType

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


AUTHORITY_CONTEXT_FIELDS = frozenset(
    {
        "schema_version",
        "audit_run_id",
        "benchmark_name",
        "producer_id",
        "producer_code_sha256",
        "canonical_observable_id",
        "observable_identity",
        "canonical_spec_path",
        "canonical_spec_sha256",
        "scientific_inputs",
        "parameter_provenance",
        "numerical_controls",
        "numerical_control_provenance",
        "registry_snapshot_sha256",
        "selector_sha256",
        "forbidden_output_fingerprints",
        "fingerprint_algorithm_version",
        "context_sha256",
    }
)
WORKER_REQUEST_FIELDS = frozenset(
    {
        "schema_version",
        "opaque_run_nonce",
        "adapter_id",
        "scientific_inputs",
        "numerical_controls",
        "capsule_sha256",
    }
)
LOCAL_OBSERVABLE_RESULT_FIELDS = frozenset(
    {
        "schema_version",
        "adapter_id",
        "capsule_sha256",
        "request_sha256",
        "observable_identity",
        "fields",
        "units",
        "uncertainty",
        "raw_convergence_evidence",
        "backend_diagnostics",
        "operation_counts_or_sizes",
        "worker_started_monotonic_ns",
        "worker_finished_monotonic_ns",
    }
)
FAILURE_CONTRACT_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "stage",
        "reason_code",
        "diagnostic",
        "available_hashes",
        "available_attestations",
    }
)

AUTHORITY_ONLY_CANARIES = (
    "authority-benchmark-canary",
    "canonical-observable-canary",
    "canonical/specifications/authority-canary.json",
    "provenance-locator-canary",
    "registry-snapshot-canary",
    "selector-commitment-canary",
)


def _sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _authority_context_payload(*, producer_id="task7_test_authority_v1"):
    """Produce a Task 7 canary context without loading any registry module."""

    payload = {
        "schema_version": "adapter_authority_context_v1",
        "audit_run_id": "authority-audit-run-canary",
        "benchmark_name": AUTHORITY_ONLY_CANARIES[0],
        "producer_id": producer_id,
        "producer_code_sha256": _sha256_text(
            "independent-authority-producer-code-v1"
        ),
        "canonical_observable_id": AUTHORITY_ONLY_CANARIES[1],
        "observable_identity": {
            "subject": "critical temperature from a duality root",
            "system_or_material": "canary square lattice spin model",
            "hamiltonian": {"nearest_neighbor_exchange": "positive"},
            "parameter_regime": {"exchange": "positive_finite"},
            "size_or_limit": {"kind": "thermodynamic_limit"},
            "observable_definition": {"quantity": "temperature_ratio"},
            "units": {"temperature_ratio": "dimensionless"},
            "conditions": {"field": 0.0},
        },
        "canonical_spec_path": AUTHORITY_ONLY_CANARIES[2],
        "canonical_spec_sha256": _sha256_text("canonical-spec-canary"),
        "scientific_inputs": {"exchange": 1.375},
        "parameter_provenance": {
            "exchange": {
                "kind": "canonical_model_parameter",
                "requirement": {
                    "canonical_path": ["hamiltonian", "exchange"],
                    "physical_role": "isotropic ferromagnetic exchange",
                },
                "locator": {
                    "kind": "canonical_spec_path",
                    "path": ["hamiltonian", "exchange"],
                },
                "commitment_sha256": _sha256_text(
                    "parameter-provenance-canary"
                ),
                "target_equivalent": False,
            }
        },
        "numerical_controls": {
            "maximum_refinement_iterations": 64,
            "root_residual_threshold": 1e-12,
        },
        "numerical_control_provenance": {
            "maximum_refinement_iterations": {
                "kind": "numerical_control",
                "locator": "fixed-control-policy-canary-a",
                "commitment_sha256": _sha256_text("control-canary-a"),
                "registry_independent": True,
            },
            "root_residual_threshold": {
                "kind": "numerical_control",
                "locator": "fixed-control-policy-canary-b",
                "commitment_sha256": _sha256_text("control-canary-b"),
                "registry_independent": True,
            },
        },
        "registry_snapshot_sha256": _sha256_text(
            AUTHORITY_ONLY_CANARIES[4]
        ),
        "selector_sha256": _sha256_text(AUTHORITY_ONLY_CANARIES[5]),
        "forbidden_output_fingerprints": tuple(
            sorted(
                {
                    _sha256_text("forbidden-numeric-operand-canary"),
                    _sha256_text("forbidden-categorical-operand-canary"),
                }
            )
        ),
        "fingerprint_algorithm_version": "canonical_json_sha256_v1",
    }
    payload["context_sha256"] = canonical_sha256(payload)
    return payload


def _rehash_authority_payload(payload):
    rehashed = dict(payload)
    rehashed.pop("context_sha256", None)
    rehashed["context_sha256"] = canonical_sha256(rehashed)
    return rehashed


def test_authority_context_requires_exact_closed_fields_and_hash():
    from validation import literature_evidence_isolation as isolation

    payload = _authority_context_payload()
    accepted = isolation.validate_authority_context(
        payload, allow_test_producer=True
    )

    assert type(accepted) is isolation.AdapterAuthorityContext
    assert {
        field.name for field in dataclasses.fields(type(accepted))
    } == AUTHORITY_CONTEXT_FIELDS
    assert accepted.context_sha256 == canonical_sha256(
        {
            key: value
            for key, value in payload.items()
            if key != "context_sha256"
        }
    )

    for bad_payload in (
        {
            key: value
            for key, value in payload.items()
            if key != "selector_sha256"
        },
        {**payload, "authority_extra": "must-fail-closed"},
    ):
        with pytest.raises(AdapterContractError):
            isolation.validate_authority_context(
                bad_payload, allow_test_producer=True
            )


AUTHORITY_MUTATIONS = (
    "producer_id",
    "producer_code_sha256",
    "canonical_spec_sha256",
    "registry_snapshot_sha256",
    "selector_sha256",
    "fingerprint_empty",
    "fingerprint_duplicate",
    "fingerprint_unsorted",
    "fingerprint_algorithm",
    "parameter_provenance",
    "context_sha256",
)


@pytest.mark.parametrize("mutation", AUTHORITY_MUTATIONS)
def test_authority_context_rejects_stale_or_incomplete_commitments(mutation):
    from validation import literature_evidence_isolation as isolation

    payload = _authority_context_payload()
    if mutation == "producer_id":
        payload["producer_id"] = "unknown_authority_producer_v1"
    elif mutation == "fingerprint_empty":
        payload["forbidden_output_fingerprints"] = ()
    elif mutation == "fingerprint_duplicate":
        digest = payload["forbidden_output_fingerprints"][0]
        payload["forbidden_output_fingerprints"] = (digest, digest)
    elif mutation == "fingerprint_unsorted":
        payload["forbidden_output_fingerprints"] = tuple(
            reversed(payload["forbidden_output_fingerprints"])
        )
    elif mutation == "fingerprint_algorithm":
        payload["fingerprint_algorithm_version"] = "unknown_algorithm_v2"
    elif mutation == "parameter_provenance":
        payload["parameter_provenance"] = {
            "exchange": {
                **payload["parameter_provenance"]["exchange"],
                "locator": {
                    "kind": "canonical_spec_path",
                    "path": ["hamiltonian", "mutated_exchange"],
                },
            }
        }
    elif mutation == "context_sha256":
        payload["context_sha256"] = "0" * 64
    else:
        payload[mutation] = "1" * 63

    if mutation != "context_sha256":
        payload = _rehash_authority_payload(payload)

    expected_guard = {
        "producer_id": "producer",
        "producer_code_sha256": "producer_code_sha256|SHA-256",
        "canonical_spec_sha256": "canonical_spec_sha256|SHA-256",
        "registry_snapshot_sha256": "registry_snapshot_sha256|SHA-256",
        "selector_sha256": "selector_sha256|SHA-256",
        "fingerprint_empty": "nonempty",
        "fingerprint_duplicate": "duplicate",
        "fingerprint_unsorted": "ordering",
        "fingerprint_algorithm": "algorithm",
        "parameter_provenance": "locator|path|requirement",
        "context_sha256": "context hash",
    }[mutation]
    with pytest.raises(AdapterContractError, match=expected_guard):
        isolation.validate_authority_context(payload, allow_test_producer=True)


def test_authority_accepts_structurally_valid_unknown_authenticity_hashes():
    from validation import literature_evidence_isolation as isolation

    payload = _authority_context_payload()
    for field_name in (
        "producer_code_sha256",
        "canonical_spec_sha256",
        "registry_snapshot_sha256",
        "selector_sha256",
    ):
        payload[field_name] = _sha256_text(
            f"structurally-valid-unknown-{field_name}"
        )
    payload = _rehash_authority_payload(payload)
    accepted = isolation.validate_authority_context(
        payload, allow_test_producer=True
    )
    assert accepted.context_sha256 == payload["context_sha256"]


def test_production_validation_rejects_test_authority_producer():
    from validation import literature_evidence_isolation as isolation

    payload = _authority_context_payload()

    with pytest.raises(AdapterContractError, match="test.*producer|producer"):
        isolation.validate_authority_context(payload)

    accepted = isolation.validate_authority_context(
        payload, allow_test_producer=True
    )
    production_payload = _rehash_authority_payload(
        {**payload, "producer_id": "task8_canonical_authority_v1"}
    )
    production = isolation.validate_authority_context(production_payload)

    assert accepted.producer_id == "task7_test_authority_v1"
    assert production.producer_id == "task8_canonical_authority_v1"


def test_target_equivalent_parameter_provenance_is_rejected():
    from validation import literature_evidence_isolation as isolation

    payload = _authority_context_payload()
    payload["parameter_provenance"] = {
        "exchange": {
            **payload["parameter_provenance"]["exchange"],
            "target_equivalent": True,
        }
    }
    payload = _rehash_authority_payload(payload)

    with pytest.raises(AdapterContractError, match="target.equivalent"):
        isolation.validate_authority_context(
            payload, allow_test_producer=True
        )


def _valid_worker_request():
    from validation import literature_evidence_isolation as isolation

    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    authority = isolation.validate_authority_context(
        _authority_context_payload(), allow_test_producer=True
    )
    return isolation.make_worker_request(
        definition,
        authority,
        opaque_run_nonce="opaque-worker-run-nonce-7f1d",
        capsule_sha256=_sha256_text("frozen-adapter-capsule-canary"),
        allow_test_producer=True,
    )


def test_worker_request_projection_excludes_authority_canaries():
    request = _valid_worker_request()
    serialized = canonical_json_bytes(request.to_frozen_json())

    from validation import literature_evidence_isolation as isolation

    assert type(request) is isolation.WorkerRequest
    assert {
        field.name for field in dataclasses.fields(type(request))
    } == WORKER_REQUEST_FIELDS
    assert set(request.to_frozen_json()) == WORKER_REQUEST_FIELDS
    assert request.scientific_inputs == {"exchange": 1.375}
    assert request.numerical_controls == {
        "maximum_refinement_iterations": 64,
        "root_residual_threshold": 1e-12,
    }
    for canary in AUTHORITY_ONLY_CANARIES:
        assert canary.encode("utf-8") not in serialized
    for forbidden_token in (
        b"benchmark_name",
        b"canonical_observable_id",
        b"parameter_provenance",
        b"registry_snapshot_sha256",
        b"selector_sha256",
        b"forbidden_output_fingerprints",
        b"target",
        b"verdict",
    ):
        assert forbidden_token not in serialized


def test_worker_request_rejects_extra_metadata_and_tampered_authority_records(
):
    from validation import literature_evidence_isolation as isolation

    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    authority = isolation.validate_authority_context(
        _authority_context_payload(), allow_test_producer=True
    )
    with pytest.raises(AdapterContractError):
        isolation.make_worker_request(
            definition,
            authority,
            opaque_run_nonce="opaque-worker-run-nonce-7f1d",
            capsule_sha256=_sha256_text("frozen-adapter-capsule-canary"),
            allow_test_producer=True,
            target_metadata={"answer": 2.0},
        )

    object.__setattr__(authority, "scientific_inputs", {"exchange": 1.0})
    with pytest.raises(AdapterContractError):
        isolation.make_worker_request(
            definition,
            authority,
            opaque_run_nonce="opaque-worker-run-nonce-7f1d",
            capsule_sha256=_sha256_text("frozen-adapter-capsule-canary"),
            allow_test_producer=True,
        )


def _local_observable_payload():
    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    request = _valid_worker_request()
    return {
        "schema_version": "local_observable_result_v1",
        "adapter_id": definition.adapter_id,
        "capsule_sha256": request.capsule_sha256,
        "request_sha256": canonical_sha256(request.to_frozen_json()),
        "observable_identity": thaw_json(definition.observable_identity),
        "fields": {"tc_over_j": 2.269185314213022},
        "units": {"tc_over_j": "dimensionless"},
        "uncertainty": {"tc_over_j": 2e-13},
        "raw_convergence_evidence": {
            "kind": "residual_bound",
            "controls": {
                "maximum_refinement_iterations": 64,
                "root_residual_threshold": 1e-12,
            },
            "samples": [2.26918531420, 2.269185314213022],
            "residuals": [2e-11, 2e-14],
            "error_bound": 2e-13,
            "certificate": {
                "kind": "residual_envelope",
                "certificate_sha256": _sha256_text(
                    "residual-envelope-canary"
                ),
            },
        },
        "backend_diagnostics": {
            "backend_kind": "analytic",
            "interpreter_implementation": "cpython",
            "interpreter_version": "canary-version",
            "interpreter_binary_sha256": _sha256_text(
                "python-binary-canary"
            ),
            "packages": {
                "scipy": {
                    "version": "canary-version",
                    "binary_sha256": _sha256_text(
                        "scipy-binary-canary"
                    ),
                }
            },
            "native_libraries": {},
            "numerical_backend": {
                "name": "not_applicable",
                "version": None,
                "binary_sha256": None,
                "applicability": "not_applicable",
            },
            "backend_resources": {
                "single_cpu_core": {"applicability": "used"}
            },
        },
        "operation_counts_or_sizes": {
            "operation_counts": {"root_iterations": 12},
            "problem_size": {
                "policy_kind": "not_applicable",
                "values": {},
            },
        },
        "worker_started_monotonic_ns": 10_000,
        "worker_finished_monotonic_ns": 20_000,
    }


def test_local_observable_result_has_exact_local_calculation_fields_only():
    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    payload = _local_observable_payload()
    accepted = adapters.validate_local_observable_result(definition, payload)

    assert type(accepted) is FrozenJsonObject
    assert {
        field.name
        for field in dataclasses.fields(adapters.LocalObservableResult)
    } == LOCAL_OBSERVABLE_RESULT_FIELDS
    assert set(accepted) == LOCAL_OBSERVABLE_RESULT_FIELDS
    assert set(payload) == LOCAL_OBSERVABLE_RESULT_FIELDS
    serialized = canonical_json_bytes(accepted)
    for forbidden_token in (
        b"success",
        b"verdict",
        b"strict_match",
        b"literature",
        b"expected",
        b"comparison",
        b"registry",
    ):
        assert forbidden_token not in serialized.lower()


@pytest.mark.parametrize(
    "mutation",
    (
        "extra_field",
        "missing_field",
        "wrong_units",
        "nonfinite_field",
        "missing_uncertainty",
        "wrong_convergence_kind",
        "timestamp_reversal",
        "success_bundle",
    ),
)
def test_local_observable_result_rejects_closed_contract_violations(mutation):
    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    payload = _local_observable_payload()
    if mutation == "extra_field":
        payload["extra"] = "closed"
    elif mutation == "missing_field":
        payload["fields"] = {}
    elif mutation == "wrong_units":
        payload["units"] = {"tc_over_j": "kelvin"}
    elif mutation == "nonfinite_field":
        payload["fields"] = {"tc_over_j": math.nan}
    elif mutation == "missing_uncertainty":
        payload["uncertainty"] = {}
    elif mutation == "wrong_convergence_kind":
        payload["raw_convergence_evidence"]["kind"] = "exact"
    elif mutation == "timestamp_reversal":
        payload["worker_finished_monotonic_ns"] = 9_999
    else:
        payload["backend_diagnostics"]["success_bundle"] = {
            "strict_match": True
        }

    with pytest.raises(AdapterContractError):
        adapters.validate_local_observable_result(definition, payload)


def test_local_observable_result_requires_zero_exact_uncertainty():
    definition = adapters.ADAPTER_DEFINITIONS["xxx_bethe_energy"]
    payload = _local_observable_payload()
    payload.update(
        {
            "adapter_id": definition.adapter_id,
            "observable_identity": thaw_json(definition.observable_identity),
            "fields": {"energy_per_site": -0.4431471805599453},
            "units": {"energy_per_site": "J"},
            "uncertainty": {"energy_per_site": 1e-15},
            "raw_convergence_evidence": {
                "kind": "exact",
                "samples": [-0.4431471805599453],
                "residuals": [0.0],
            },
        }
    )

    with pytest.raises(AdapterContractError, match="uncertainty|zero"):
        adapters.validate_local_observable_result(definition, payload)


def _failure_payload():
    return {
        "schema_version": "adapter_run_failure_v1",
        "status": "execution_failed",
        "stage": "worker_execution",
        "reason_code": "worker_timeout",
        "diagnostic": "worker exceeded the declared wall-time limit",
        "available_hashes": {
            "capsule_sha256": _sha256_text("failure-capsule-canary")
        },
        "available_attestations": {"namespace_created": True},
    }


def test_failure_contract_is_closed_bounded_and_has_no_success_bundle():
    from validation import literature_evidence_isolation as isolation

    accepted = isolation.validate_failure(_failure_payload())

    assert type(accepted) is isolation.AdapterRunFailure
    assert {
        field.name for field in dataclasses.fields(type(accepted))
    } == FAILURE_CONTRACT_FIELDS
    assert accepted.status == "execution_failed"
    assert not hasattr(accepted, "evidence")
    assert not hasattr(accepted, "success")


@pytest.mark.parametrize(
    "mutation",
    (
        "success_status",
        "unknown_stage",
        "unknown_reason",
        "oversized_diagnostic",
        "success_bundle",
        "unknown_field",
        "nonfinite_attestation",
    ),
)
def test_failure_contract_rejects_success_or_unbounded_payloads(mutation):
    from validation import literature_evidence_isolation as isolation

    payload = _failure_payload()
    if mutation == "success_status":
        payload["status"] = "isolated_recomputation_succeeded"
    elif mutation == "unknown_stage":
        payload["stage"] = "caller_chosen_stage"
    elif mutation == "unknown_reason":
        payload["reason_code"] = "caller_chosen_reason"
    elif mutation == "oversized_diagnostic":
        payload["diagnostic"] = "x" * 2_000
    elif mutation == "success_bundle":
        payload["available_attestations"] = {
            "success_bundle": {"strict_match": True}
        }
    elif mutation == "unknown_field":
        payload["evidence"] = {"strict_match": True}
    else:
        payload["available_attestations"] = {"elapsed": math.inf}

    with pytest.raises(AdapterContractError):
        isolation.validate_failure(payload)


def test_failure_contract_rejects_subclasses_lists_and_pre_tampered_records():
    from validation import literature_evidence_isolation as isolation

    with pytest.raises(TypeError):
        class FailureSubclass(isolation.AdapterRunFailure):
            pass

    payload = _failure_payload()
    payload["available_hashes"] = [("capsule_sha256", "0" * 64)]
    with pytest.raises(AdapterContractError):
        isolation.validate_failure(payload)

    accepted = isolation.validate_failure(_failure_payload())
    object.__setattr__(accepted, "status", "isolated_recomputation_succeeded")
    with pytest.raises(AdapterContractError):
        isolation.validate_failure(accepted)


def test_all_task4_records_are_exact_frozen_sealed_contracts():
    from validation import literature_evidence_isolation as isolation

    record_names_and_fields = {
        "ScientificClosure": {
            "schema_version", "role", "entry_symbol", "nodes",
            "dependency_edges", "emitted_source_sha256", "bundle_sha256",
        },
        "ScientificPolicyCommitment": {
            "schema_version", "role", "definition_id",
            "canonical_definition_bytes", "canonical_definition_sha256",
            "eligibility_row_sha256", "eligibility_catalog_sha256",
            "entry_closure_sha256", "output_or_invariant_proof_bindings",
            "domain_sha256", "size_policy_sha256", "convergence_sha256",
            "static_scan_sha256", "combined_sha256",
        },
        "InfrastructureClosure": {
            "schema_version", "roots", "nodes", "dependency_edges",
            "purpose_bindings", "bundle_sha256",
        },
        "StaticScanReport": {
            "schema_version", "role", "scanner_version", "scanner_sha256",
            "scanned_closure_sha256", "fingerprint_commitment_sha256",
            "checks", "passed", "report_sha256",
        },
        "RuntimeResourceManifest": {
            "schema_version", "resources", "manifest_sha256",
        },
        "RuntimeSnapshot": {
            "schema_version", "manifest", "snapshot_root",
            "directory_identities", "snapshot_sha256",
        },
        "CapabilityPreflightReport": {
            "schema_version", "audit_run_id", "available", "checks",
            "command_identities", "namespace_identifiers", "mount_facts",
            "probe_result_codes", "trace_sha256", "report_sha256",
        },
        "CounterfactualPoint": {
            "schema_version", "domain_version", "adapter_id", "point_id",
            "run_nonce", "kind", "scientific_inputs", "numerical_controls",
            "problem_size", "expected_validation", "scientific_configuration",
            "metamorphic_metadata",
        },
        "ProcessAttestation": {
            "schema_version", "process_role", "point_id",
            "namespace_identifiers", "mount_facts", "environment_facts",
            "resource_limit_facts", "chroot_facts", "attestation_sha256",
        },
        "TracePolicyReport": {
            "schema_version", "trace_sha256", "attempted_accesses",
            "violations", "passed", "report_sha256",
        },
        "PointExecutionEvidence": {
            "schema_version", "point_id", "request_sha256", "result_sha256",
            "trace_policy_report", "process_attestation",
            "backend_diagnostics", "exit_status", "execution_sha256",
        },
        "ConvergenceDecision": {
            "schema_version", "kind", "accepted", "raw_evidence_sha256",
            "reason_code", "decision_sha256",
        },
        "OracleDecision": {
            "schema_version", "oracle_id", "accepted",
            "oracle_execution_evidence_hashes", "residuals", "invariants",
            "reason_code", "decision_sha256",
        },
        "AdapterExecutionEvidence": {
            "schema_version", "status", "authority_context_sha256",
            "validated_inputs_and_provenance", "eligibility_commitments",
            "adapter_policy_commitment", "oracle_policy_commitment",
            "adapter_scientific_closure", "oracle_scientific_closure",
            "infrastructure_closure", "static_scan_reports",
            "runtime_snapshot", "ordering_events",
            "capability_preflight_sha256", "point_executions",
            "convergence_decision", "oracle_decision", "disclosed_seed_hex",
            "bundle_sha256",
        },
        "AdapterRunOutcome": {"status", "evidence", "failure"},
        "EventRecord": {"sequence_number", "event_name", "details"},
    }

    for record_name, expected_fields in record_names_and_fields.items():
        record_type = getattr(isolation, record_name)
        assert dataclasses.is_dataclass(record_type)
        assert dataclasses.fields(record_type)[0]._field_type is not None
        assert {field.name for field in dataclasses.fields(record_type)} == (
            expected_fields
        )
        assert record_type.__dataclass_params__.frozen is True
        with pytest.raises(TypeError):
            type(f"{record_name}Subclass", (record_type,), {})


def test_oracle_contract_is_closed_and_catalog_starts_exactly_empty():
    from validation import literature_evidence_adapter_oracles as oracles

    assert {
        field.name for field in dataclasses.fields(oracles.OracleDefinition)
    } == {
        "oracle_id",
        "entry_symbol",
        "input_schema",
        "result_schema",
        "runtime_requirements",
        "convergence_invariant_contract",
        "resource_limits",
    }
    assert oracles.ORACLE_DEFINITIONS == {}
    assert type(oracles.ORACLE_DEFINITIONS) is MappingProxyType
    with pytest.raises(AdapterContractError):
        oracles.get_oracle_definition("not_populated_until_task13")


def test_scientific_policy_rejects_noncanonical_or_unknown_definition():
    from validation import literature_evidence_isolation as isolation

    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    values = _adapter_policy_values(definition)
    canonical_bytes = values["canonical_definition_bytes"]
    canonical_payload = json.loads(canonical_bytes)
    accepted = isolation.ScientificPolicyCommitment(**values)
    assert accepted.canonical_definition_bytes == canonical_bytes

    noncanonical = json.dumps(
        thaw_json(freeze_json(canonical_payload)), sort_keys=False, indent=2
    ).encode("utf-8")
    bad_noncanonical = dict(values)
    bad_noncanonical["canonical_definition_bytes"] = noncanonical
    bad_noncanonical["canonical_definition_sha256"] = hashlib.sha256(
        noncanonical
    ).hexdigest()
    bad_noncanonical["combined_sha256"] = (
        isolation.scientific_policy_combined_sha256(bad_noncanonical)
    )
    with pytest.raises(AdapterContractError, match="canonical"):
        isolation.ScientificPolicyCommitment(**bad_noncanonical)

    with_unknown = dict(canonical_payload)
    with_unknown["unexpected_policy_field"] = "must-fail-before-emission"
    bad_unknown = dict(values)
    bad_unknown["canonical_definition_bytes"] = canonical_json_bytes(
        with_unknown
    )
    bad_unknown["canonical_definition_sha256"] = hashlib.sha256(
        bad_unknown["canonical_definition_bytes"]
    ).hexdigest()
    bad_unknown["combined_sha256"] = (
        isolation.scientific_policy_combined_sha256(bad_unknown)
    )
    with pytest.raises(
        AdapterContractError, match="unknown|definition fields"
    ):
        isolation.ScientificPolicyCommitment(**bad_unknown)


def test_authority_context_fresh_snapshots_revalidate_tampering():
    from validation import literature_evidence_isolation as isolation

    payload = _authority_context_payload()
    caller_inputs = freeze_json(payload["scientific_inputs"])
    caller_provenance = freeze_json(payload["parameter_provenance"])
    payload["scientific_inputs"] = caller_inputs
    payload["parameter_provenance"] = caller_provenance
    payload = _rehash_authority_payload(payload)

    accepted = isolation.validate_authority_context(
        payload, allow_test_producer=True
    )
    accepted_hash = accepted.context_sha256
    object.__setattr__(caller_inputs, "_items", ())
    object.__setattr__(caller_provenance, "_items", ())

    assert accepted.scientific_inputs == {"exchange": 1.375}
    assert accepted.context_sha256 == accepted_hash
    assert accepted.scientific_inputs is not caller_inputs
    assert accepted.parameter_provenance is not caller_provenance

    object.__setattr__(accepted, "producer_code_sha256", "0" * 64)
    with pytest.raises(AdapterContractError, match="hash"):
        isolation.validate_authority_context(
            accepted, allow_test_producer=True
        )


@pytest.mark.parametrize(
    "invalid_value",
    (
        pytest.param(math.nan, id="nan"),
        pytest.param(math.inf, id="positive_infinity"),
        pytest.param(-math.inf, id="negative_infinity"),
        pytest.param(_list_cycle(), id="cycle"),
    ),
)
def test_authority_context_rejects_nonfinite_or_cyclic_inputs(invalid_value):
    from validation import literature_evidence_isolation as isolation

    payload = _authority_context_payload()
    payload["scientific_inputs"] = {"exchange": invalid_value}
    with pytest.raises(AdapterContractError):
        isolation.validate_authority_context(
            payload, allow_test_producer=True
        )


def test_authority_context_rejects_excessive_depth_and_list_record_fields():
    from validation import literature_evidence_isolation as isolation

    nested = 1.0
    for _ in range(140):
        nested = [nested]
    payload = _authority_context_payload()
    payload["scientific_inputs"] = {"exchange": nested}
    with pytest.raises(AdapterContractError, match="nesting|recursion"):
        isolation.validate_authority_context(
            payload, allow_test_producer=True
        )

    direct_values = _authority_context_payload()
    direct_values["forbidden_output_fingerprints"] = list(
        direct_values["forbidden_output_fingerprints"]
    )
    with pytest.raises(AdapterContractError, match="tuple"):
        isolation.AdapterAuthorityContext(**direct_values)


def test_input_control_validation_rejects_closed_contract_violations():
    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]

    assert adapters.validate_scientific_inputs(
        definition, {"exchange": 1.25}
    ) == {"exchange": 1.25}
    assert adapters.validate_numerical_controls(
        definition,
        {
            "maximum_refinement_iterations": 32,
            "root_residual_threshold": 1e-10,
        },
    ) == {
        "maximum_refinement_iterations": 32,
        "root_residual_threshold": 1e-10,
    }
    for bad_inputs in (
        {},
        {"exchange": 1.25, "unexpected": 2.0},
        {"exchange": True},
        {"exchange": math.nan},
        {"exchange": "target answer"},
    ):
        with pytest.raises(AdapterContractError):
            adapters.validate_scientific_inputs(definition, bad_inputs)
    with pytest.raises(AdapterContractError):
        adapters.validate_numerical_controls(
            definition, {"maximum_refinement_iterations": 32}
        )


def test_worker_request_record_rejects_unknown_missing_and_wrong_hash_fields():
    from validation import literature_evidence_isolation as isolation

    request = _valid_worker_request()
    values = {
        field.name: getattr(request, field.name)
        for field in dataclasses.fields(type(request))
    }
    with pytest.raises(AdapterContractError, match="unknown"):
        isolation.WorkerRequest(**{**values, "benchmark_name": "forbidden"})
    values.pop("opaque_run_nonce")
    with pytest.raises(AdapterContractError, match="missing"):
        isolation.WorkerRequest(**values)
    values = {
        field.name: getattr(request, field.name)
        for field in dataclasses.fields(type(request))
    }
    values["capsule_sha256"] = "not-a-hash"
    with pytest.raises(AdapterContractError, match="SHA-256"):
        isolation.WorkerRequest(**values)


def test_local_result_revalidates_pre_tampered_records_and_hash_shapes():
    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    payload = _local_observable_payload()
    record = adapters.LocalObservableResult(**payload)
    object.__setattr__(record, "fields", freeze_json({}))
    with pytest.raises(AdapterContractError):
        adapters.validate_local_observable_result(definition, record)

    for hash_field in ("capsule_sha256", "request_sha256"):
        bad_payload = _local_observable_payload()
        bad_payload[hash_field] = "f" * 63
        with pytest.raises(AdapterContractError, match="SHA-256"):
            adapters.validate_local_observable_result(
                definition, bad_payload
            )


def test_local_result_and_failure_snapshots_do_not_retain_deep_aliases():
    from validation import literature_evidence_isolation as isolation

    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    local_payload = _local_observable_payload()
    caller_diagnostics = freeze_json(local_payload["backend_diagnostics"])
    local_payload["backend_diagnostics"] = caller_diagnostics
    accepted_local = adapters.validate_local_observable_result(
        definition, local_payload
    )
    local_digest = canonical_sha256(accepted_local)
    object.__setattr__(caller_diagnostics, "_items", ())
    assert canonical_sha256(accepted_local) == local_digest
    assert accepted_local["backend_diagnostics"]

    failure_payload = _failure_payload()
    caller_attestations = freeze_json(
        failure_payload["available_attestations"]
    )
    failure_payload["available_attestations"] = caller_attestations
    accepted_failure = isolation.validate_failure(failure_payload)
    object.__setattr__(caller_attestations, "_items", ())
    assert accepted_failure.available_attestations == {
        "namespace_created": True
    }
    assert accepted_failure.available_attestations is not caller_attestations


@pytest.mark.parametrize(
    "invalid_attestation",
    (
        pytest.param(_mapping_cycle(), id="cycle"),
        pytest.param({"elapsed": math.nan}, id="nan"),
        pytest.param({"elapsed": math.inf}, id="infinity"),
    ),
)
def test_failure_contract_normalizes_recursive_json_rejections(
    invalid_attestation,
):
    from validation import literature_evidence_isolation as isolation

    payload = _failure_payload()
    payload["available_attestations"] = invalid_attestation
    with pytest.raises(AdapterContractError):
        isolation.validate_failure(payload)


@pytest.mark.parametrize(
    "canonical_spec_path",
    (
        "canonical//observable.json",
        "canonical/./observable.json",
        ".",
    ),
)
def test_authority_context_rejects_noncanonical_spec_paths(
    canonical_spec_path,
):
    from validation import literature_evidence_isolation as isolation

    payload = _authority_context_payload()
    payload["canonical_spec_path"] = canonical_spec_path
    payload = _rehash_authority_payload(payload)
    with pytest.raises(AdapterContractError, match="normalized|path"):
        isolation.validate_authority_context(
            payload, allow_test_producer=True
        )


def test_worker_request_requires_separate_explicit_test_producer_opt_in():
    from validation import literature_evidence_isolation as isolation

    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    authority = isolation.validate_authority_context(
        _authority_context_payload(), allow_test_producer=True
    )
    with pytest.raises(AdapterContractError, match="test.*producer|opt.in"):
        isolation.make_worker_request(
            definition,
            authority,
            opaque_run_nonce="opaque-worker-run-nonce-7f1d",
            capsule_sha256=_sha256_text("frozen-adapter-capsule-canary"),
        )

    request = isolation.make_worker_request(
        definition,
        authority,
        opaque_run_nonce="opaque-worker-run-nonce-7f1d",
        capsule_sha256=_sha256_text("frozen-adapter-capsule-canary"),
        allow_test_producer=True,
    )
    assert request.adapter_id == definition.adapter_id


def test_scientific_policy_binds_definition_id_to_canonical_bytes():
    from validation import literature_evidence_isolation as isolation

    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    values = _adapter_policy_values(definition)
    values["definition_id"] = "different_adapter_id"
    values["combined_sha256"] = (
        isolation.scientific_policy_combined_sha256(values)
    )
    with pytest.raises(AdapterContractError, match="definition_id|canonical"):
        isolation.ScientificPolicyCommitment(**values)


def test_oracle_definition_recursively_rejects_expected_answer_metadata():
    from validation import literature_evidence_adapter_oracles as oracles

    input_schema = ValueSchema(
        "object",
        True,
        None,
        None,
        None,
        (("exchange", _number_schema(units="J")),),
        "",
    )
    result_schema = ValueSchema(
        "object",
        True,
        None,
        None,
        None,
        (("residual_norm", _number_schema()),),
        "",
    )
    with pytest.raises(AdapterContractError, match="forbidden"):
        oracles.OracleDefinition(
            oracle_id="canary_oracle",
            entry_symbol=(
                "validation.literature_evidence_adapter_oracles:"
                "oracle_canary_oracle"
            ),
            input_schema=input_schema,
            result_schema=result_schema,
            runtime_requirements=RuntimeRequirements(
                "python3", (), (), ()
            ),
            convergence_invariant_contract={
                "expected_answer": "forbidden-canary"
            },
            resource_limits=ResourceLimits(
                1, 2, 64_000_000, 16_000, 16, 1
            ),
        )


def _policy_value_schema_payload(schema):
    return {
        "kind": schema.kind,
        "required": schema.required,
        "lower": schema.lower,
        "upper": schema.upper,
        "item_schema": (
            None
            if schema.item_schema is None
            else _policy_value_schema_payload(schema.item_schema)
        ),
        "properties": {
            name: _policy_value_schema_payload(child)
            for name, child in schema.properties
        },
        "units": schema.units,
    }


def _policy_runtime_payload(runtime):
    return {
        "interpreter": runtime.interpreter,
        "packages": list(runtime.packages),
        "native_libraries": list(runtime.native_libraries),
        "backend_resources": list(runtime.backend_resources),
    }


def _policy_limits_payload(limits):
    return {
        "cpu_seconds": limits.cpu_seconds,
        "wall_seconds": limits.wall_seconds,
        "address_space_bytes": limits.address_space_bytes,
        "output_bytes": limits.output_bytes,
        "file_descriptors": limits.file_descriptors,
        "process_count": limits.process_count,
    }


def _policy_output_payload(output_schema):
    return {
        "fields": {
            name: {
                "value_schema": _policy_value_schema_payload(
                    binding.value_schema
                ),
                "raw_field": binding.raw_field,
                "proof_kind": binding.proof_kind,
            }
            for name, binding in output_schema
        }
    }


def _canonical_adapter_definition_payload(definition):
    return {
        "adapter_id": definition.adapter_id,
        "entry_symbol": definition.entry_symbol,
        "observable_identity": thaw_json(definition.observable_identity),
        "scientific_input_schema": _policy_value_schema_payload(
            definition.scientific_input_schema
        ),
        "numerical_control_schema": _policy_value_schema_payload(
            definition.numerical_control_schema
        ),
        "parameter_sources": [
            {
                "parameter_name": source.parameter_name,
                "kind": source.kind,
                "details": thaw_json(source.details),
            }
            for source in definition.parameter_sources
        ],
        "output_schema": _policy_output_payload(definition.output_schema),
        "backend_kind": definition.backend_kind,
        "problem_size_policy": {
            "kind": definition.problem_size_policy.kind,
            "fixed_sizes": thaw_json(
                definition.problem_size_policy.fixed_sizes
            ),
            "allowed_sizes": thaw_json(
                definition.problem_size_policy.allowed_sizes
            ),
        },
        "runtime_requirements": _policy_runtime_payload(
            definition.runtime_requirements
        ),
        "convergence_contract": {
            "kind": definition.convergence_contract.kind,
            "requirements": thaw_json(
                definition.convergence_contract.requirements
            ),
        },
        "counterfactual_domain": {
            "valid_rules": thaw_json(
                definition.counterfactual_domain.valid_rules
            ),
            "invalid_rules": thaw_json(
                definition.counterfactual_domain.invalid_rules
            ),
        },
        "oracle_id": definition.oracle_id,
        "resource_limits": _policy_limits_payload(
            definition.resource_limits
        ),
    }


def _eligibility_payload(benchmark_id, decision):
    return {
        "benchmark_id": benchmark_id,
        "selector_fields": list(decision.selector_fields),
        "disposition": decision.disposition,
        "adapter_id": decision.adapter_id,
        "oracle_id": decision.oracle_id,
        "reason": decision.reason,
    }


def _adapter_policy_values(definition):
    from validation import literature_evidence_isolation as isolation

    definition_payload = _canonical_adapter_definition_payload(definition)
    benchmark_id, decision = next(
        (key, item)
        for key, item in ADAPTER_ELIGIBILITY.items()
        if item.adapter_id == definition.adapter_id
    )
    proof_bindings = _policy_output_payload(definition.output_schema)
    domain = definition_payload["counterfactual_domain"]
    size_policy = definition_payload["problem_size_policy"]
    convergence = definition_payload["convergence_contract"]
    catalog = {
        key: _eligibility_payload(key, value)
        for key, value in ADAPTER_ELIGIBILITY.items()
    }
    canonical_bytes = canonical_json_bytes(definition_payload)
    values = {
        "schema_version": "scientific_policy_commitment_v1",
        "role": "adapter",
        "definition_id": definition.adapter_id,
        "canonical_definition_bytes": canonical_bytes,
        "canonical_definition_sha256": hashlib.sha256(
            canonical_bytes
        ).hexdigest(),
        "eligibility_row_sha256": canonical_sha256(
            _eligibility_payload(benchmark_id, decision)
        ),
        "eligibility_catalog_sha256": canonical_sha256(catalog),
        "entry_closure_sha256": _sha256_text("entry-closure-canary"),
        "output_or_invariant_proof_bindings": proof_bindings,
        "domain_sha256": canonical_sha256(domain),
        "size_policy_sha256": canonical_sha256(size_policy),
        "convergence_sha256": canonical_sha256(convergence),
        "static_scan_sha256": _sha256_text("static-scan-canary"),
    }
    values["combined_sha256"] = (
        isolation.scientific_policy_combined_sha256(values)
    )
    return values


def test_policy_accepts_real_canonical_adapter_definition_schema():
    from validation import literature_evidence_isolation as isolation

    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    values = _adapter_policy_values(definition)
    accepted = isolation.ScientificPolicyCommitment(**values)
    assert accepted.definition_id == definition.adapter_id


@pytest.mark.parametrize(
    "mutation",
    (
        "scientific_input_schema",
        "runtime_requirements",
        "resource_limits",
        "parameter_sources",
    ),
)
def test_adapter_policy_rejects_each_detached_same_id_definition(mutation):
    from validation import literature_evidence_isolation as isolation

    canonical = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    definition_values = {
        field.name: getattr(canonical, field.name)
        for field in dataclasses.fields(AdapterDefinition)
    }
    if mutation == "scientific_input_schema":
        definition_values["scientific_input_schema"] = _object_schema(
            (("exchange", _number_schema(lower=None, units="J")),)
        )
    elif mutation == "runtime_requirements":
        runtime = canonical.runtime_requirements
        definition_values["runtime_requirements"] = RuntimeRequirements(
            runtime.interpreter,
            runtime.packages + ("numpy",),
            runtime.native_libraries,
            runtime.backend_resources,
        )
    elif mutation == "resource_limits":
        limits = canonical.resource_limits
        definition_values["resource_limits"] = ResourceLimits(
            limits.cpu_seconds + 1,
            limits.wall_seconds,
            limits.address_space_bytes,
            limits.output_bytes,
            limits.file_descriptors,
            limits.process_count,
        )
    else:
        source = canonical.parameter_sources[0]
        details = thaw_json(source.details)
        details["physical_role"] = "detached exchange role"
        definition_values["parameter_sources"] = (
            ParameterSource(source.parameter_name, source.kind, details),
        )
    detached = AdapterDefinition(**definition_values)
    values = _adapter_policy_values(detached)
    with pytest.raises(
        AdapterContractError,
        match="canonical.*catalog|catalog.*canonical",
    ):
        isolation.ScientificPolicyCommitment(**values)


@pytest.mark.parametrize(
    "mutation",
    (
        "nested_definition",
        "proof_bindings",
        "domain",
        "size_policy",
        "convergence",
        "eligibility_row",
        "eligibility_catalog",
    ),
)
def test_policy_recomputes_definition_derived_commitments(mutation):
    from validation import literature_evidence_isolation as isolation

    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    values = _adapter_policy_values(definition)
    if mutation == "nested_definition":
        payload = json.loads(values["canonical_definition_bytes"])
        payload["scientific_input_schema"]["unknown_nested_field"] = True
        canonical_bytes = canonical_json_bytes(payload)
        values["canonical_definition_bytes"] = canonical_bytes
        values["canonical_definition_sha256"] = hashlib.sha256(
            canonical_bytes
        ).hexdigest()
    elif mutation == "proof_bindings":
        values["output_or_invariant_proof_bindings"] = {
            "fields": {
                "tc_over_j": {
                    "value_schema": _policy_value_schema_payload(
                        definition.output_schema["tc_over_j"].value_schema
                    ),
                    "raw_field": "mutated_raw_field",
                    "proof_kind": "bounded_numeric_value",
                }
            }
        }
    elif mutation == "domain":
        values["domain_sha256"] = _sha256_text("mutated-domain")
    elif mutation == "size_policy":
        values["size_policy_sha256"] = _sha256_text("mutated-size")
    elif mutation == "convergence":
        values["convergence_sha256"] = _sha256_text(
            "mutated-convergence"
        )
    elif mutation == "eligibility_row":
        values["eligibility_row_sha256"] = _sha256_text("mutated-row")
    else:
        values["eligibility_catalog_sha256"] = _sha256_text(
            "mutated-catalog"
        )
    values["combined_sha256"] = (
        isolation.scientific_policy_combined_sha256(values)
    )
    with pytest.raises(AdapterContractError, match=mutation.split("_")[0]):
        isolation.ScientificPolicyCommitment(**values)


def test_worker_request_direct_constructor_enforces_canonical_adapter_schema():
    from validation import literature_evidence_isolation as isolation

    with pytest.raises(AdapterContractError, match="scientific_inputs|unknown"):
        isolation.WorkerRequest(
            schema_version="worker_request_v1",
            opaque_run_nonce="direct-constructor-canary",
            adapter_id="square_ising_self_dual_tc",
            scientific_inputs={"exchange": 1.0, "target_answer": 2.0},
            numerical_controls={
                "maximum_refinement_iterations": 64,
                "root_residual_threshold": 1e-12,
            },
            capsule_sha256=_sha256_text("capsule-canary"),
        )


def test_worker_request_serializer_revalidates_pre_tampered_record():
    request = _valid_worker_request()
    object.__setattr__(
        request,
        "scientific_inputs",
        freeze_json({"exchange": 1.0, "target_answer": 2.0}),
    )
    with pytest.raises(AdapterContractError):
        request.to_frozen_json()


def test_authority_parameter_provenance_has_closed_requirement_and_locator():
    from validation import literature_evidence_isolation as isolation

    payload = _authority_context_payload()
    payload["parameter_provenance"] = {
        "exchange": {
            "kind": "canonical_model_parameter",
            "requirement": {
                "canonical_path": ["hamiltonian", "exchange"],
                "physical_role": "isotropic ferromagnetic exchange",
            },
            "locator": {
                "kind": "canonical_spec_path",
                "path": ["hamiltonian", "exchange"],
            },
            "commitment_sha256": _sha256_text(
                "parameter-provenance-canary"
            ),
            "target_equivalent": False,
        }
    }
    payload = _rehash_authority_payload(payload)

    accepted = isolation.validate_authority_context(
        payload, allow_test_producer=True
    )
    assert accepted.parameter_provenance["exchange"]["requirement"] == {
        "canonical_path": ("hamiltonian", "exchange"),
        "physical_role": "isotropic ferromagnetic exchange",
    }


def test_worker_projection_binds_provenance_kind_to_canonical_definition():
    from validation import literature_evidence_isolation as isolation

    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    payload = _authority_context_payload()
    payload["parameter_provenance"] = {
        "exchange": {
            "kind": "universal_probe",
            "requirement": {"probe_role": "alternate probe canary"},
            "locator": {
                "kind": "universal_probe",
                "probe_id": "alternate-probe-canary",
            },
            "commitment_sha256": _sha256_text(
                "alternate-probe-commitment-canary"
            ),
            "target_equivalent": False,
        }
    }
    authority = isolation.validate_authority_context(
        _rehash_authority_payload(payload), allow_test_producer=True
    )
    with pytest.raises(AdapterContractError, match="provenance|kind"):
        isolation.make_worker_request(
            definition,
            authority,
            opaque_run_nonce="opaque-worker-run-nonce-provenance-canary",
            capsule_sha256=_sha256_text("provenance-capsule-canary"),
            allow_test_producer=True,
        )


def _strict_residual_local_payload():
    payload = _local_observable_payload()
    payload["raw_convergence_evidence"] = {
        "kind": "residual_bound",
        "samples": [2.26918531420, 2.269185314213022],
        "residuals": [2e-11, 2e-14],
        "controls": {
            "maximum_refinement_iterations": 64,
            "root_residual_threshold": 1e-12,
        },
        "error_bound": 2e-13,
        "certificate": {
            "kind": "residual_envelope",
            "certificate_sha256": _sha256_text(
                "residual-envelope-canary"
            ),
        },
    }
    payload["backend_diagnostics"] = {
        "backend_kind": "analytic",
        "interpreter_implementation": "cpython",
        "interpreter_version": "canary-version",
        "interpreter_binary_sha256": _sha256_text(
            "python-binary-canary"
        ),
        "packages": {
            "scipy": {
                "version": "canary-version",
                "binary_sha256": _sha256_text("scipy-binary-canary"),
            }
        },
        "native_libraries": {},
        "numerical_backend": {
            "name": "not_applicable",
            "version": None,
            "binary_sha256": None,
            "applicability": "not_applicable",
        },
        "backend_resources": {
            "single_cpu_core": {"applicability": "used"}
        },
    }
    return payload


@pytest.mark.parametrize(
    "mutation",
    (
        "missing_controls",
        "missing_error_bound",
        "backend_kind_mismatch",
        "zero_approximate_uncertainty",
    ),
)
def test_local_result_rejects_each_recalculation_contract_bypass(mutation):
    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    payload = _strict_residual_local_payload()
    if mutation == "missing_controls":
        payload["raw_convergence_evidence"].pop("controls")
    elif mutation == "missing_error_bound":
        payload["raw_convergence_evidence"].pop("error_bound")
    elif mutation == "backend_kind_mismatch":
        payload["backend_diagnostics"]["backend_kind"] = "numpy_dense"
    else:
        payload["uncertainty"]["tc_over_j"] = 0.0
    with pytest.raises(AdapterContractError, match="control|error|backend|uncertainty"):
        adapters.validate_local_observable_result(definition, payload)


FAILURE_LEAKAGE_MUTATIONS = (
    ("diagnostic", "isolated_recomputation_succeeded"),
    ("diagnostic", "strict_literature_match"),
    ("attestation", "isolated_recomputation_succeeded"),
    ("attestation", "strict_literature_match"),
    ("attestation", "succeeded"),
    ("attestation", "registry_operand"),
    ("attestation", "target_value"),
    ("attestation", "source_payload"),
    ("attestation", "environment_secret"),
    ("attestation", "report_content"),
)


@pytest.mark.parametrize(("location", "leak_key"), FAILURE_LEAKAGE_MUTATIONS)
def test_failure_contract_rejects_each_answer_or_success_leak(
    location,
    leak_key,
):
    from validation import literature_evidence_isolation as isolation

    payload = _failure_payload()
    if location == "diagnostic":
        payload["diagnostic"] = leak_key
    else:
        payload["available_attestations"] = {leak_key: 7}
    with pytest.raises(AdapterContractError, match="diagnostic|attestation"):
        isolation.validate_failure(payload)


def test_contract_modules_do_not_reverse_export_dependency_symbols():
    with pytest.raises(ImportError):
        exec(
            "from validation.literature_evidence_isolation "
            "import validate_adapter_definition",
            {},
        )
    with pytest.raises(ImportError):
        exec(
            "from validation.literature_evidence_adapter_oracles "
            "import ResourceLimits",
            {},
        )


def test_task4_public_all_surfaces_are_exact():
    from validation import literature_evidence_adapters as adapter_contracts
    from validation import literature_evidence_adapter_oracles as oracles
    from validation import literature_evidence_isolation as isolation

    assert set(adapter_contracts.__all__) == {
        "AdapterContractError",
        "FrozenJsonObject",
        "freeze_json",
        "thaw_json",
        "canonical_json_bytes",
        "canonical_sha256",
        "require_exact_keys",
        "require_identifier",
        "ValueSchema",
        "OUTPUT_PROOF_KINDS",
        "OutputFieldBinding",
        "OutputSchema",
        "ParameterSource",
        "CounterfactualDomain",
        "ConvergenceContract",
        "ProblemSizePolicy",
        "RuntimeRequirements",
        "ResourceLimits",
        "AdapterDefinition",
        "SOURCE_PARSE_ONLY_REASONS",
        "EligibilityDecision",
        "ADAPTER_ELIGIBILITY",
        "ADAPTER_DEFINITIONS",
        "get_adapter_definition",
        "validate_adapter_definition",
        "adapter_definition_to_frozen_json",
        "adapter_definition_from_frozen_json",
        "adapter_eligibility_row_to_frozen_json",
        "adapter_eligibility_catalog_to_frozen_json",
        "validate_scientific_inputs",
        "validate_numerical_controls",
        "LocalObservableResult",
        "validate_local_observable_result",
    }
    assert set(oracles.__all__) == {
        "OracleDefinition",
        "ORACLE_DEFINITIONS",
        "get_oracle_definition",
        "validate_oracle_definition",
        "oracle_definition_to_frozen_json",
        "oracle_definition_from_frozen_json",
    }
    assert set(isolation.__all__) == {
        "AdapterAuthorityContext",
        "WorkerRequest",
        "ScientificClosure",
        "ScientificPolicyCommitment",
        "InfrastructureClosure",
        "StaticScanReport",
        "RuntimeResourceManifest",
        "RuntimeSnapshot",
        "CapabilityPreflightReport",
        "CounterfactualPoint",
        "ProcessAttestation",
        "TracePolicyReport",
        "PointExecutionEvidence",
        "ConvergenceDecision",
        "OracleDecision",
        "AdapterExecutionEvidence",
        "AdapterRunFailure",
        "AdapterRunOutcome",
        "EventRecord",
        "FAILURE_STATUSES",
        "FAILURE_STAGES",
        "FAILURE_REASON_CODES",
        "validate_authority_context",
        "make_worker_request",
        "build_scientific_closure",
        "build_scientific_policy_commitment",
        "build_infrastructure_closure",
        "scan_scientific_closure",
        "discover_runtime_resources",
        "build_runtime_snapshot",
        "revalidate_runtime_snapshot",
        "record_and_freeze_hashes",
        "acquire_run_seed",
        "derive_counterfactual_points",
        "assert_disjoint_scientific_closures",
        "assert_complete_dependency_partition",
        "scientific_policy_combined_sha256",
        "validate_failure",
    }


def _synthetic_oracle_definition():
    from validation import literature_evidence_adapter_oracles as oracles

    return oracles.OracleDefinition(
        oracle_id="synthetic_residual_oracle",
        entry_symbol=(
            "validation.literature_evidence_adapter_oracles:"
            "oracle_synthetic_residual_oracle"
        ),
        input_schema=ValueSchema(
            "object",
            True,
            None,
            None,
            None,
            (("exchange", _number_schema(units="J")),),
            "",
        ),
        result_schema=ValueSchema(
            "object",
            True,
            None,
            None,
            None,
            (("residual_norm", _number_schema(lower=0.0)),),
            "",
        ),
        runtime_requirements=RuntimeRequirements(
            "python3", ("numpy",), (), ("single_cpu_core",)
        ),
        convergence_invariant_contract={
            "kind": "residual_bound",
            "rule": "independent residual contracts under refinement",
        },
        resource_limits=ResourceLimits(
            10, 20, 256_000_000, 100_000, 32, 1
        ),
    )


def _oracle_policy_values(definition):
    from validation import literature_evidence_adapter_oracles as oracles
    from validation import literature_evidence_isolation as isolation

    payload = oracles.oracle_definition_to_frozen_json(definition)
    canonical_bytes = canonical_json_bytes(payload)
    not_applicable = {"kind": "not_applicable"}
    values = {
        "schema_version": "scientific_policy_commitment_v1",
        "role": "oracle",
        "definition_id": definition.oracle_id,
        "canonical_definition_bytes": canonical_bytes,
        "canonical_definition_sha256": hashlib.sha256(
            canonical_bytes
        ).hexdigest(),
        "eligibility_row_sha256": None,
        "eligibility_catalog_sha256": None,
        "entry_closure_sha256": _sha256_text(
            "oracle-entry-closure-canary"
        ),
        "output_or_invariant_proof_bindings": {
            "result_schema": payload["result_schema"],
            "convergence_invariant_contract": payload[
                "convergence_invariant_contract"
            ],
        },
        "domain_sha256": canonical_sha256(not_applicable),
        "size_policy_sha256": canonical_sha256(not_applicable),
        "convergence_sha256": canonical_sha256(
            payload["convergence_invariant_contract"]
        ),
        "static_scan_sha256": _sha256_text(
            "oracle-static-scan-canary"
        ),
    }
    values["combined_sha256"] = isolation.scientific_policy_combined_sha256(
        values
    )
    return values


def test_definition_codecs_round_trip_all_adapters_and_synthetic_oracle():
    from validation import literature_evidence_adapter_oracles as oracles

    for definition in adapters.ADAPTER_DEFINITIONS.values():
        frozen = adapters.adapter_definition_to_frozen_json(definition)
        rebuilt = adapters.adapter_definition_from_frozen_json(frozen)
        assert canonical_json_bytes(
            adapters.adapter_definition_to_frozen_json(rebuilt)
        ) == canonical_json_bytes(frozen)
        assert rebuilt.adapter_id == definition.adapter_id

    oracle = _synthetic_oracle_definition()
    frozen_oracle = oracles.oracle_definition_to_frozen_json(oracle)
    rebuilt_oracle = oracles.oracle_definition_from_frozen_json(
        frozen_oracle
    )
    assert rebuilt_oracle.oracle_id == oracle.oracle_id
    assert canonical_json_bytes(
        oracles.oracle_definition_to_frozen_json(rebuilt_oracle)
    ) == canonical_json_bytes(frozen_oracle)


def test_definition_codecs_reject_nested_unknown_fields():
    from validation import literature_evidence_adapter_oracles as oracles

    adapter_payload = thaw_json(
        adapters.adapter_definition_to_frozen_json(
            adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
        )
    )
    adapter_payload["output_schema"]["fields"]["tc_over_j"][
        "unknown_binding"
    ] = True
    with pytest.raises(AdapterContractError, match="unknown"):
        adapters.adapter_definition_from_frozen_json(adapter_payload)

    oracle_payload = thaw_json(
        oracles.oracle_definition_to_frozen_json(
            _synthetic_oracle_definition()
        )
    )
    oracle_payload["result_schema"]["unknown_nested"] = True
    with pytest.raises(AdapterContractError, match="unknown"):
        oracles.oracle_definition_from_frozen_json(oracle_payload)


def test_policy_accepts_synthetic_valid_oracle_with_locked_derivations():
    from validation import literature_evidence_isolation as isolation

    definition = _synthetic_oracle_definition()
    values = _oracle_policy_values(definition)
    accepted = isolation.ScientificPolicyCommitment(**values)
    assert accepted.definition_id == definition.oracle_id
    assert accepted.eligibility_row_sha256 is None
    assert accepted.eligibility_catalog_sha256 is None


@pytest.mark.parametrize(
    "mutation",
    (
        "eligibility_row",
        "eligibility_catalog",
        "invariant_bindings",
        "domain",
        "size_policy",
        "convergence",
    ),
)
def test_oracle_policy_rejects_adapter_eligibility_or_mutated_invariants(
    mutation,
):
    from validation import literature_evidence_isolation as isolation

    values = _oracle_policy_values(_synthetic_oracle_definition())
    if mutation == "eligibility_row":
        values["eligibility_row_sha256"] = _sha256_text("forbidden-row")
    elif mutation == "eligibility_catalog":
        values["eligibility_catalog_sha256"] = _sha256_text(
            "forbidden-catalog"
        )
    elif mutation == "invariant_bindings":
        values["output_or_invariant_proof_bindings"] = {
            "result_schema": values[
                "output_or_invariant_proof_bindings"
            ]["result_schema"],
            "convergence_invariant_contract": {
                "kind": "mutated_invariant",
                "rule": "mutated rule",
            },
        }
    else:
        values[f"{mutation}_sha256"] = _sha256_text(
            f"mutated-oracle-{mutation}"
        )
    values["combined_sha256"] = isolation.scientific_policy_combined_sha256(
        values
    )
    with pytest.raises(
        AdapterContractError,
        match="eligibility|invariant|domain|size policy|convergence",
    ):
        isolation.ScientificPolicyCommitment(**values)


def _example_schema_value(schema):
    if schema.kind == "boolean":
        return True
    if schema.kind == "integer":
        if schema.lower is not None:
            return int(schema.lower)
        if schema.upper is not None and schema.upper < 1:
            return int(schema.upper)
        return 1
    if schema.kind == "number":
        if schema.lower is not None:
            return float(schema.lower)
        if schema.upper is not None and schema.upper < 1:
            return float(schema.upper)
        return 1.0
    if schema.kind == "string":
        return "calculation-canary"
    if schema.kind == "list":
        count = schema.lower if schema.lower is not None else 1
        if count == 0 and schema.upper != 0:
            count = 1
        return [
            _example_schema_value(schema.item_schema)
            for _ in range(count)
        ]
    return {
        name: _example_schema_value(child)
        for name, child in schema.properties
    }


def _authority_payload_for_definition(definition):
    scientific_inputs = _example_schema_value(
        definition.scientific_input_schema
    )
    numerical_controls = _example_schema_value(
        definition.numerical_control_schema
    )
    parameter_provenance = {}
    for source in definition.parameter_sources:
        requirement = thaw_json(source.details)
        if source.kind == "canonical_model_parameter":
            locator = {
                "kind": "canonical_spec_path",
                "path": requirement["canonical_path"],
            }
        elif source.kind == "universal_probe":
            locator = {
                "kind": "universal_probe",
                "probe_id": f"{source.parameter_name}-probe-canary",
            }
        else:
            locator = {
                "kind": "source_model_path",
                "source_id": "source-model-canary",
                "path": requirement["source_path"],
            }
        parameter_provenance[source.parameter_name] = {
            "kind": source.kind,
            "requirement": requirement,
            "locator": locator,
            "commitment_sha256": _sha256_text(
                f"{definition.adapter_id}-{source.parameter_name}-source"
            ),
            "target_equivalent": False,
        }
    control_provenance = {
        name: {
            "kind": "numerical_control",
            "locator": f"{definition.adapter_id}-{name}-policy",
            "commitment_sha256": _sha256_text(
                f"{definition.adapter_id}-{name}-control"
            ),
            "registry_independent": True,
        }
        for name in numerical_controls
    }
    payload = {
        "schema_version": "adapter_authority_context_v1",
        "audit_run_id": f"{definition.adapter_id}-audit-canary",
        "benchmark_name": f"{definition.adapter_id}_benchmark_canary",
        "producer_id": "task7_test_authority_v1",
        "producer_code_sha256": _sha256_text(
            "independent-authority-producer-code-v1"
        ),
        "canonical_observable_id": f"{definition.adapter_id}-observable",
        "observable_identity": thaw_json(definition.observable_identity),
        "canonical_spec_path": (
            f"canonical/specifications/{definition.adapter_id}.json"
        ),
        "canonical_spec_sha256": _sha256_text(
            f"{definition.adapter_id}-canonical-spec"
        ),
        "scientific_inputs": scientific_inputs,
        "parameter_provenance": parameter_provenance,
        "numerical_controls": numerical_controls,
        "numerical_control_provenance": control_provenance,
        "registry_snapshot_sha256": _sha256_text(
            f"{definition.adapter_id}-registry-snapshot"
        ),
        "selector_sha256": _sha256_text(
            f"{definition.adapter_id}-selector"
        ),
        "forbidden_output_fingerprints": tuple(
            sorted(
                (
                    _sha256_text(
                        f"{definition.adapter_id}-forbidden-numeric"
                    ),
                    _sha256_text(
                        f"{definition.adapter_id}-forbidden-categorical"
                    ),
                )
            )
        ),
        "fingerprint_algorithm_version": "canonical_json_sha256_v1",
    }
    return _rehash_authority_payload(payload)


@pytest.mark.parametrize(
    "definition",
    tuple(adapters.ADAPTER_DEFINITIONS.values()),
    ids=tuple(adapters.ADAPTER_DEFINITIONS),
)
def test_worker_projection_accepts_exact_provenance_for_all_definitions(
    definition,
):
    from validation import literature_evidence_isolation as isolation

    authority = isolation.validate_authority_context(
        _authority_payload_for_definition(definition),
        allow_test_producer=True,
    )
    request = isolation.make_worker_request(
        definition,
        authority,
        opaque_run_nonce=f"{definition.adapter_id}-worker-nonce",
        capsule_sha256=_sha256_text(
            f"{definition.adapter_id}-capsule"
        ),
        allow_test_producer=True,
    )
    assert request.adapter_id == definition.adapter_id
    assert request.scientific_inputs == authority.scientific_inputs
    assert request.numerical_controls == authority.numerical_controls


@pytest.mark.parametrize("mutation", ("kind", "requirement", "locator"))
def test_provenance_mutations_reach_their_independent_guards(mutation):
    from validation import literature_evidence_isolation as isolation

    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    payload = _authority_payload_for_definition(definition)
    provenance = payload["parameter_provenance"]["exchange"]
    if mutation == "kind":
        provenance.update(
            {
                "kind": "universal_probe",
                "requirement": {"probe_role": "independent probe"},
                "locator": {
                    "kind": "universal_probe",
                    "probe_id": "independent-probe-canary",
                },
            }
        )
    elif mutation == "requirement":
        provenance["requirement"]["physical_role"] = "mutated role"
    else:
        provenance["locator"] = {
            "kind": "canonical_spec_path",
            "unexpected_path": ["hamiltonian", "exchange"],
        }
    payload = _rehash_authority_payload(payload)
    if mutation == "locator":
        with pytest.raises(AdapterContractError, match="locator|unknown|path"):
            isolation.validate_authority_context(
                payload, allow_test_producer=True
            )
        return
    authority = isolation.validate_authority_context(
        payload, allow_test_producer=True
    )
    with pytest.raises(AdapterContractError, match=mutation):
        isolation.make_worker_request(
            definition,
            authority,
            opaque_run_nonce="provenance-mutation-nonce",
            capsule_sha256=_sha256_text("provenance-mutation-capsule"),
            allow_test_producer=True,
        )


def test_control_provenance_registry_independence_guard_is_rehashed():
    from validation import literature_evidence_isolation as isolation

    payload = _authority_context_payload()
    payload["numerical_control_provenance"][
        "root_residual_threshold"
    ]["registry_independent"] = False
    payload = _rehash_authority_payload(payload)
    with pytest.raises(AdapterContractError, match="registry independent"):
        isolation.validate_authority_context(
            payload, allow_test_producer=True
        )


def _local_payload_for_definition(definition):
    fields_payload = {
        selector: _example_schema_value(binding.value_schema)
        for selector, binding in definition.output_schema
    }
    units = {
        selector: binding.value_schema.units
        for selector, binding in definition.output_schema
    }
    uncertainty = {
        selector: (
            1e-9
            if binding.proof_kind == "bounded_numeric_value"
            else 0.0
        )
        for selector, binding in definition.output_schema
    }
    controls = _example_schema_value(definition.numerical_control_schema)
    certificate = {
        "kind": f"{definition.convergence_contract.kind}_certificate",
        "certificate_sha256": _sha256_text(
            f"{definition.adapter_id}-convergence-certificate"
        ),
    }
    kind = definition.convergence_contract.kind
    if kind == "exact":
        convergence = {
            "kind": kind,
            "controls": controls,
            "certificate": certificate,
        }
    elif kind == "residual_bound":
        convergence = {
            "kind": kind,
            "controls": controls,
            "certificate": certificate,
            "samples": [1.0, 1.00000001],
            "residuals": [1e-6, 1e-10],
            "error_bound": 1e-9,
        }
    elif kind == "quadrature":
        convergence = {
            "kind": kind,
            "controls": controls,
            "certificate": certificate,
            "estimates": [1.0, 1.00000001],
            "error_bounds": [1e-5, 1e-9],
            "error_bound": 1e-9,
        }
    elif kind == "finite_size":
        convergence = {
            "kind": kind,
            "controls": controls,
            "certificate": certificate,
            "sizes": [8, 12],
            "estimates": [1.0, 1.0],
            "error_bound": 0.0,
        }
    else:
        convergence = {
            "kind": kind,
            "controls": controls,
            "certificate": certificate,
            "estimates": [1.0, 1.00000001],
            "residuals": [1e-5, 1e-9],
            "refinement_iterations": 2,
            "error_bound": 1e-9,
        }
    runtime = definition.runtime_requirements
    backend = {
        "backend_kind": definition.backend_kind,
        "interpreter_implementation": "cpython",
        "interpreter_version": "test-version",
        "interpreter_binary_sha256": _sha256_text(
            f"{definition.adapter_id}-python-binary"
        ),
        "packages": {
            name: {
                "version": "test-version",
                "binary_sha256": _sha256_text(
                    f"{definition.adapter_id}-{name}-package"
                ),
            }
            for name in runtime.packages
        },
        "native_libraries": {
            name: {
                "version": "test-version",
                "binary_sha256": _sha256_text(
                    f"{definition.adapter_id}-{name}-native"
                ),
            }
            for name in runtime.native_libraries
        },
        "numerical_backend": {
            "name": "not_applicable",
            "version": None,
            "binary_sha256": None,
            "applicability": "not_applicable",
        },
        "backend_resources": {
            name: {"applicability": "used"}
            for name in runtime.backend_resources
        },
    }
    size_policy = definition.problem_size_policy
    if size_policy.kind == "fixed_local":
        size_values = thaw_json(size_policy.fixed_sizes)
    elif size_policy.kind == "scalable_same_observable":
        size_values = {}
        for name, allowed in size_policy.allowed_sizes.items():
            if type(allowed) is tuple:
                size_values[name] = thaw_json(allowed[0])
            else:
                size_values[name] = thaw_json(allowed)
    else:
        size_values = {}
    return {
        "schema_version": "local_observable_result_v1",
        "adapter_id": definition.adapter_id,
        "capsule_sha256": _sha256_text(
            f"{definition.adapter_id}-local-capsule"
        ),
        "request_sha256": _sha256_text(
            f"{definition.adapter_id}-local-request"
        ),
        "observable_identity": thaw_json(definition.observable_identity),
        "fields": fields_payload,
        "units": units,
        "uncertainty": uncertainty,
        "raw_convergence_evidence": convergence,
        "backend_diagnostics": backend,
        "operation_counts_or_sizes": {
            "operation_counts": {"operations": 1},
            "problem_size": {
                "policy_kind": size_policy.kind,
                "values": size_values,
            },
        },
        "worker_started_monotonic_ns": 1_000,
        "worker_finished_monotonic_ns": 2_000,
    }


@pytest.mark.parametrize(
    "definition",
    tuple(adapters.ADAPTER_DEFINITIONS.values()),
    ids=tuple(adapters.ADAPTER_DEFINITIONS),
)
def test_local_result_contract_covers_all_definitions_outputs_and_kinds(
    definition,
):
    payload = _local_payload_for_definition(definition)
    accepted = adapters.validate_local_observable_result(
        definition, payload
    )
    assert accepted["adapter_id"] == definition.adapter_id
    assert set(accepted["fields"]) == set(
        definition.output_schema.selector_fields
    )


def test_local_result_matrix_covers_all_42_outputs_10_proofs_and_5_kinds():
    definitions = tuple(adapters.ADAPTER_DEFINITIONS.values())
    bindings = tuple(
        binding
        for definition in definitions
        for _selector, binding in definition.output_schema
    )
    assert len(definitions) == 29
    assert len(bindings) == 42
    assert {binding.proof_kind for binding in bindings} == set(
        adapters.OUTPUT_PROOF_KINDS
    )
    assert {
        definition.convergence_contract.kind for definition in definitions
    } == {"exact", "residual_bound", "quadrature", "finite_size", "iterative"}
    assert {binding.value_schema.kind for binding in bindings} == {
        "boolean",
        "integer",
        "number",
        "list",
    }


@pytest.mark.parametrize(
    ("adapter_id", "selector", "wrong_value"),
    (
        ("square_ising_self_dual_tc", "tc_over_j", True),
        (
            "compass_line_symmetry_matrix",
            "has_line_flip_symmetries",
            1,
        ),
        (
            "toric_code_stabilizer_rank",
            "torus_ground_state_degeneracy",
            True,
        ),
        (
            "aklt_two_site_projector_ed",
            "two_site_projector_eigenvalues",
            "not-a-list",
        ),
    ),
)
def test_local_result_rejects_each_output_value_kind_mismatch(
    adapter_id,
    selector,
    wrong_value,
):
    definition = adapters.ADAPTER_DEFINITIONS[adapter_id]
    payload = _local_payload_for_definition(definition)
    payload["fields"][selector] = wrong_value
    with pytest.raises(AdapterContractError, match="fields"):
        adapters.validate_local_observable_result(definition, payload)


@pytest.mark.parametrize("mutation", ("negative_count", "negative_timestamp"))
def test_local_result_rejects_negative_counts_and_timestamps(mutation):
    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    payload = _local_payload_for_definition(definition)
    if mutation == "negative_count":
        payload["operation_counts_or_sizes"]["operation_counts"] = {
            "operations": -1
        }
    else:
        payload["worker_started_monotonic_ns"] = -1
    with pytest.raises(AdapterContractError, match="nonnegative|count"):
        adapters.validate_local_observable_result(definition, payload)


ITERATIVE_NUMERIC_DEFINITIONS = tuple(
    definition
    for definition in adapters.ADAPTER_DEFINITIONS.values()
    if definition.backend_kind == "iterative_numeric"
)


@pytest.mark.parametrize(
    "definition",
    ITERATIVE_NUMERIC_DEFINITIONS,
    ids=tuple(
        definition.adapter_id
        for definition in ITERATIVE_NUMERIC_DEFINITIONS
    ),
)
@pytest.mark.parametrize("evidence_position", (0, -1), ids=("first", "last"))
def test_iterative_numeric_evidence_rejects_negative_residual_norms(
    definition,
    evidence_position,
):
    payload = _local_payload_for_definition(definition)
    convergence = payload["raw_convergence_evidence"]
    sequence_name = (
        "residuals"
        if convergence["kind"] == "iterative"
        else "error_bounds"
    )
    convergence[sequence_name][evidence_position] = -1e-9

    with pytest.raises(AdapterContractError, match="nonnegative|positive"):
        adapters._validate_raw_convergence_evidence(
            definition,
            freeze_json(convergence),
        )


FIXED_LOCAL_DEFINITIONS = tuple(
    definition
    for definition in adapters.ADAPTER_DEFINITIONS.values()
    if definition.problem_size_policy.kind == "fixed_local"
)
SCALABLE_DEFINITIONS = tuple(
    definition
    for definition in adapters.ADAPTER_DEFINITIONS.values()
    if definition.problem_size_policy.kind == "scalable_same_observable"
)
NOT_APPLICABLE_SIZE_DEFINITIONS = tuple(
    definition
    for definition in adapters.ADAPTER_DEFINITIONS.values()
    if definition.problem_size_policy.kind == "not_applicable"
)


FIXED_SIZE_TRANSPORT_MUTATIONS = (
    ("empty_transport", "operation_counts|problem_size"),
    ("irrelevant_count_only", "operation_counts|problem_size"),
    ("fixed_value_mismatch", "fixed|problem_size.values|match"),
    ("missing_fixed_dimension", "problem_size.values|missing"),
    ("wrong_policy_kind", "policy_kind does not match definition"),
    ("malformed_values", "problem_size.values|mapping"),
)


@pytest.mark.parametrize(
    "definition",
    FIXED_LOCAL_DEFINITIONS,
    ids=tuple(
        definition.adapter_id for definition in FIXED_LOCAL_DEFINITIONS
    ),
)
@pytest.mark.parametrize(
    "mutation, expected_guard",
    FIXED_SIZE_TRANSPORT_MUTATIONS,
    ids=tuple(item[0] for item in FIXED_SIZE_TRANSPORT_MUTATIONS),
)
def test_fixed_local_result_size_transport_is_exact_and_honest(
    definition,
    mutation,
    expected_guard,
):
    payload = _local_payload_for_definition(definition)
    transport = payload["operation_counts_or_sizes"]
    size_values = transport["problem_size"]["values"]
    if mutation == "empty_transport":
        payload["operation_counts_or_sizes"] = {}
    elif mutation == "irrelevant_count_only":
        payload["operation_counts_or_sizes"] = {"operations": 1}
    elif mutation == "fixed_value_mismatch":
        dimension = next(iter(size_values))
        size_values[dimension] += 1
    elif mutation == "missing_fixed_dimension":
        size_values.pop(next(iter(size_values)))
    elif mutation == "wrong_policy_kind":
        transport["problem_size"][
            "policy_kind"
        ] = "scalable_same_observable"
    else:
        transport["problem_size"]["values"] = []

    with pytest.raises(AdapterContractError, match=expected_guard):
        adapters.validate_local_observable_result(definition, payload)


SCALABLE_SIZE_TRANSPORT_MUTATIONS = (
    ("empty_transport", "operation_counts|problem_size"),
    ("irrelevant_count_only", "operation_counts|problem_size"),
    ("disallowed_selected_size", "allowed|problem_size.values"),
    ("missing_size_dimension", "problem_size.values|missing"),
    ("wrong_policy_kind", "policy_kind does not match definition"),
    ("malformed_values", "problem_size.values|mapping"),
)


@pytest.mark.parametrize(
    "definition",
    SCALABLE_DEFINITIONS,
    ids=tuple(definition.adapter_id for definition in SCALABLE_DEFINITIONS),
)
@pytest.mark.parametrize(
    "mutation, expected_guard",
    SCALABLE_SIZE_TRANSPORT_MUTATIONS,
    ids=tuple(item[0] for item in SCALABLE_SIZE_TRANSPORT_MUTATIONS),
)
def test_scalable_result_size_transport_selects_only_allowed_sizes(
    definition,
    mutation,
    expected_guard,
):
    payload = _local_payload_for_definition(definition)
    transport = payload["operation_counts_or_sizes"]
    size_values = transport["problem_size"]["values"]
    if mutation == "empty_transport":
        payload["operation_counts_or_sizes"] = {}
    elif mutation == "irrelevant_count_only":
        payload["operation_counts_or_sizes"] = {"operations": 1}
    elif mutation == "disallowed_selected_size":
        dimension, allowed = next(
            (name, choices)
            for name, choices in definition.problem_size_policy.allowed_sizes.items()
            if type(choices) is tuple
        )
        first_allowed = allowed[0]
        size_values[dimension] = (
            [999, 999]
            if type(first_allowed) is tuple
            else 999
        )
    elif mutation == "missing_size_dimension":
        size_values.pop(next(iter(size_values)))
    elif mutation == "wrong_policy_kind":
        transport["problem_size"]["policy_kind"] = "fixed_local"
    else:
        transport["problem_size"]["values"] = []

    with pytest.raises(AdapterContractError, match=expected_guard):
        adapters.validate_local_observable_result(definition, payload)


def _scalable_sequence_dimensions(definition):
    return tuple(
        (dimension, allowed)
        for dimension, allowed in (
            definition.problem_size_policy.allowed_sizes.items()
        )
        if type(allowed) is tuple
    )


SCALABLE_DECLARED_INDEX_CASES = tuple(
    (definition, declared_index)
    for definition in SCALABLE_DEFINITIONS
    for declared_index in range(
        len(_scalable_sequence_dimensions(definition)[0][1])
    )
)


SCALABLE_CROSS_INDEX_CASES = tuple(
    (definition, selected_indexes)
    for definition in SCALABLE_DEFINITIONS
    for sequence_dimensions in (
        _scalable_sequence_dimensions(definition),
    )
    if len(sequence_dimensions) > 1
    for selected_indexes in product(
        range(len(sequence_dimensions[0][1])),
        repeat=len(sequence_dimensions),
    )
    if len(set(selected_indexes)) > 1
)


def test_scalable_catalog_sequence_dimensions_are_nonempty_and_aligned():
    assert {
        definition.adapter_id
        for definition, _ in SCALABLE_DECLARED_INDEX_CASES
    } == {definition.adapter_id for definition in SCALABLE_DEFINITIONS}
    for definition in SCALABLE_DEFINITIONS:
        sequence_dimensions = _scalable_sequence_dimensions(definition)
        assert sequence_dimensions
        assert {len(allowed) for _, allowed in sequence_dimensions} == {
            len(sequence_dimensions[0][1])
        }
        assert len(sequence_dimensions[0][1]) > 0


@pytest.mark.parametrize(
    "definition, declared_index",
    SCALABLE_DECLARED_INDEX_CASES,
    ids=tuple(
        f"{definition.adapter_id}-index-{declared_index}"
        for definition, declared_index in SCALABLE_DECLARED_INDEX_CASES
    ),
)
def test_scalable_result_accepts_each_declared_common_size_index(
    definition,
    declared_index,
):
    payload = _local_payload_for_definition(definition)
    size_values = payload["operation_counts_or_sizes"]["problem_size"][
        "values"
    ]
    for dimension, allowed in _scalable_sequence_dimensions(definition):
        size_values[dimension] = thaw_json(allowed[declared_index])

    accepted = adapters.validate_local_observable_result(definition, payload)

    assert accepted["operation_counts_or_sizes"]["problem_size"][
        "values"
    ] == size_values


@pytest.mark.parametrize(
    "definition, selected_indexes",
    SCALABLE_CROSS_INDEX_CASES,
    ids=tuple(
        f"{definition.adapter_id}-indexes-"
        + "-".join(str(index) for index in selected_indexes)
        for definition, selected_indexes in SCALABLE_CROSS_INDEX_CASES
    ),
)
def test_scalable_result_rejects_every_cross_index_size_combination(
    definition,
    selected_indexes,
):
    payload = _local_payload_for_definition(definition)
    size_values = payload["operation_counts_or_sizes"]["problem_size"][
        "values"
    ]
    for (dimension, allowed), selected_index in zip(
        _scalable_sequence_dimensions(definition),
        selected_indexes,
    ):
        size_values[dimension] = thaw_json(allowed[selected_index])

    with pytest.raises(AdapterContractError, match="common index|paired"):
        adapters.validate_local_observable_result(definition, payload)


SCALABLE_SCALAR_DIMENSION_CASES = tuple(
    (definition, dimension)
    for definition in SCALABLE_DEFINITIONS
    for dimension, allowed in (
        definition.problem_size_policy.allowed_sizes.items()
    )
    if type(allowed) is not tuple
)


@pytest.mark.parametrize(
    "definition, scalar_dimension",
    SCALABLE_SCALAR_DIMENSION_CASES,
    ids=tuple(
        f"{definition.adapter_id}-{scalar_dimension}"
        for definition, scalar_dimension in SCALABLE_SCALAR_DIMENSION_CASES
    ),
)
def test_scalable_result_requires_exact_scalar_size_constraints(
    definition,
    scalar_dimension,
):
    payload = _local_payload_for_definition(definition)
    payload["operation_counts_or_sizes"]["problem_size"]["values"][
        scalar_dimension
    ] = "caller_selected_boundary"

    with pytest.raises(AdapterContractError, match="allowed size"):
        adapters.validate_local_observable_result(definition, payload)


def _definition_with_scalable_allowed_sizes(definition, allowed_sizes):
    values = {
        field.name: getattr(definition, field.name)
        for field in dataclasses.fields(AdapterDefinition)
    }
    values["problem_size_policy"] = ProblemSizePolicy(
        kind="scalable_same_observable",
        fixed_sizes={},
        allowed_sizes=allowed_sizes,
    )
    return AdapterDefinition(**values)


@pytest.mark.parametrize(
    "mutation",
    ("empty_sequence", "inconsistent_lengths"),
)
def test_scalable_result_requires_nonempty_consistent_sequence_lengths(
    mutation,
):
    canonical = adapters.ADAPTER_DEFINITIONS[
        "shastry_sutherland_dimer_ed"
    ]
    allowed_sizes = thaw_json(canonical.problem_size_policy.allowed_sizes)
    allowed_sizes["spin_counts"] = (
        [] if mutation == "empty_sequence" else [4]
    )
    detached = _definition_with_scalable_allowed_sizes(
        canonical,
        allowed_sizes,
    )
    payload = _local_payload_for_definition(canonical)

    with pytest.raises(
        AdapterContractError,
        match="nonempty|consistent sequence lengths",
    ):
        adapters.validate_local_observable_result(detached, payload)


@pytest.mark.parametrize(
    "definition",
    NOT_APPLICABLE_SIZE_DEFINITIONS,
    ids=tuple(
        definition.adapter_id
        for definition in NOT_APPLICABLE_SIZE_DEFINITIONS
    ),
)
@pytest.mark.parametrize(
    "mutation",
    ("nonempty_values", "wrong_policy_kind"),
)
def test_not_applicable_result_size_transport_has_exact_empty_values(
    definition,
    mutation,
):
    payload = _local_payload_for_definition(definition)
    problem_size = payload["operation_counts_or_sizes"]["problem_size"]
    if mutation == "nonempty_values":
        problem_size["values"] = {"operations": 1}
    else:
        problem_size["policy_kind"] = "fixed_local"

    with pytest.raises(
        AdapterContractError,
        match=(
            "problem_size.values must be empty"
            if mutation == "nonempty_values"
            else "policy_kind does not match definition"
        ),
    ):
        adapters.validate_local_observable_result(definition, payload)


@pytest.mark.parametrize(
    "operation_counts, expected_guard",
    (
        ({"nested": {"operations": 1}}, "operation_counts must be flat"),
        (
            {"not an identifier": 1},
            "operation_counts key.*must be an identifier",
        ),
        (
            {"operations": True},
            "operation_counts.operations must be a nonnegative integer",
        ),
    ),
    ids=("nested", "nonidentifier", "boolean"),
)
def test_local_result_operation_counts_are_flat_identifier_integer_pairs(
    operation_counts,
    expected_guard,
):
    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    payload = _local_payload_for_definition(definition)
    payload["operation_counts_or_sizes"][
        "operation_counts"
    ] = operation_counts

    with pytest.raises(AdapterContractError, match=expected_guard):
        adapters.validate_local_observable_result(definition, payload)


def test_nonce_and_policy_definition_bytes_have_hard_size_limits():
    from validation import literature_evidence_isolation as isolation

    request = _valid_worker_request()
    request_values = {
        field.name: getattr(request, field.name)
        for field in dataclasses.fields(type(request))
    }
    request_values["opaque_run_nonce"] = "n" * 257
    with pytest.raises(AdapterContractError, match="nonce|long"):
        isolation.WorkerRequest(**request_values)

    values = _adapter_policy_values(
        adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    )
    oversized = b"{" + b" " * 1_048_576 + b"}"
    values["canonical_definition_bytes"] = oversized
    values["canonical_definition_sha256"] = hashlib.sha256(
        oversized
    ).hexdigest()
    values["combined_sha256"] = isolation.scientific_policy_combined_sha256(
        values
    )
    with pytest.raises(AdapterContractError, match="oversized"):
        isolation.ScientificPolicyCommitment(**values)


def test_actual_digest_canaries_bind_authority_request_and_policy_bytes():
    authority_payload = _authority_context_payload()
    authority_body = {
        key: value
        for key, value in authority_payload.items()
        if key != "context_sha256"
    }
    assert authority_payload["context_sha256"] == hashlib.sha256(
        canonical_json_bytes(authority_body)
    ).hexdigest()

    request = _valid_worker_request()
    assert canonical_sha256(request.to_frozen_json()) == hashlib.sha256(
        canonical_json_bytes(request.to_frozen_json())
    ).hexdigest()

    values = _adapter_policy_values(
        adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    )
    assert values["canonical_definition_sha256"] == hashlib.sha256(
        values["canonical_definition_bytes"]
    ).hexdigest()


def test_task4_record_constructors_accept_closed_valid_snapshots():
    from validation import literature_evidence_isolation as isolation

    digest = _sha256_text("task4-record-canary")
    adapter_policy = isolation.ScientificPolicyCommitment(
        **_adapter_policy_values(
            adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
        )
    )
    oracle_policy = isolation.ScientificPolicyCommitment(
        **_oracle_policy_values(_synthetic_oracle_definition())
    )
    adapter_closure = isolation.ScientificClosure(
        "scientific_closure_v1",
        "adapter",
        "validation.canary:adapter_entry",
        ({"module": "validation.canary", "sha256": digest},),
        (),
        digest,
        digest,
    )
    oracle_closure = isolation.ScientificClosure(
        "scientific_closure_v1",
        "oracle",
        "validation.canary:oracle_entry",
        ({"module": "validation.canary_oracle", "sha256": digest},),
        (),
        digest,
        digest,
    )
    infrastructure = isolation.InfrastructureClosure(
        "infrastructure_closure_v1",
        ("validation.runner",),
        ({"module": "validation.runner", "sha256": digest},),
        (),
        {"validation.runner": "transport"},
        digest,
    )
    static_scan_checks = {
        check_name: {"passed": True, "reason": "closed"}
        for check_name in (
            "raw_ast_closed",
            "dependency_graph_closed",
            "imports_closed",
            "capabilities_closed",
            "literal_context_closed",
            "emitted_bytes_closed",
            "fingerprints_absent",
            "role_policy_closed",
        )
    }
    static_scan_values = {
        "schema_version": "static_scan_report_v1",
        "role": "adapter",
        "scanner_version": isolation._STATIC_SCANNER_VERSION,
        "scanner_sha256": isolation._STATIC_SCANNER_SHA256,
        "scanned_closure_sha256": digest,
        "fingerprint_commitment_sha256": digest,
        "checks": static_scan_checks,
        "passed": True,
    }
    static_scan_values["report_sha256"] = canonical_sha256(
        static_scan_values
    )
    static_scan = isolation.StaticScanReport(**static_scan_values)
    manifest = isolation.RuntimeResourceManifest(
        "runtime_resource_manifest_v1",
        ({"kind": "interpreter", "sha256": digest},),
        digest,
    )
    runtime_snapshot = isolation.RuntimeSnapshot(
        "runtime_snapshot_v1",
        manifest,
        "/runtime-snapshot",
        ({"path": "python3", "sha256": digest},),
        digest,
    )
    preflight = isolation.CapabilityPreflightReport(
        "capability_preflight_report_v1",
        "audit-run-canary",
        True,
        {"namespaces": True},
        {"python3": digest},
        {"mount": "isolated"},
        {"root": "readonly"},
        {"probe": 0},
        digest,
        digest,
    )
    process = isolation.ProcessAttestation(
        "process_attestation_v1",
        "adapter",
        "point-canary",
        {"pid_namespace": "isolated"},
        {"root": "readonly"},
        {"environment": "closed"},
        {"cpu_seconds": 1},
        {"chroot": True},
        digest,
    )
    trace = isolation.TracePolicyReport(
        "trace_policy_report_v1",
        digest,
        ({"operation": "read", "path": "/capsule"},),
        (),
        True,
        digest,
    )
    point = isolation.PointExecutionEvidence(
        "point_execution_evidence_v1",
        "point-canary",
        digest,
        digest,
        trace,
        process,
        {"backend_kind": "analytic"},
        0,
        digest,
    )
    convergence = isolation.ConvergenceDecision(
        "convergence_decision_v1",
        "residual_bound",
        True,
        digest,
        "bound_satisfied",
        digest,
    )
    oracle_decision = isolation.OracleDecision(
        "oracle_decision_v1",
        "synthetic_residual_oracle",
        True,
        (digest,),
        {"residual_norm": 1e-12},
        {"bound_satisfied": True},
        "invariant_satisfied",
        digest,
    )
    event = isolation.EventRecord(0, "worker_started", {"point": 0})
    evidence = isolation.AdapterExecutionEvidence(
        "adapter_execution_evidence_v1",
        "isolated_recomputation_succeeded",
        digest,
        {"inputs_sha256": digest},
        {"catalog_sha256": digest},
        adapter_policy,
        oracle_policy,
        adapter_closure,
        oracle_closure,
        infrastructure,
        (static_scan,),
        runtime_snapshot,
        (event,),
        preflight.report_sha256,
        (point,),
        convergence,
        oracle_decision,
        "1" * 64,
        digest,
    )
    outcome = isolation.AdapterRunOutcome(
        "isolated_recomputation_succeeded", evidence, None
    )

    records = (
        adapter_policy,
        oracle_policy,
        adapter_closure,
        oracle_closure,
        infrastructure,
        static_scan,
        manifest,
        runtime_snapshot,
        preflight,
        process,
        trace,
        point,
        convergence,
        oracle_decision,
        event,
        evidence,
        outcome,
    )
    assert all(dataclasses.is_dataclass(record) for record in records)
    assert all(
        type(record).__module__
        == "validation.literature_evidence_isolation"
        for record in records
    )


@pytest.mark.parametrize(
    "mutation",
    (
        "unknown_field",
        "missing_field",
        "schema_version",
        "unknown_adapter",
        "scientific_input_schema",
        "numerical_control_schema",
        "capsule_hash",
    ),
)
def test_worker_request_direct_construction_rejects_each_closed_case(
    mutation,
):
    from validation import literature_evidence_isolation as isolation

    request = _valid_worker_request()
    values = {
        field.name: getattr(request, field.name)
        for field in dataclasses.fields(type(request))
    }
    if mutation == "unknown_field":
        values["answer_metadata"] = 7
    elif mutation == "missing_field":
        values.pop("opaque_run_nonce")
    elif mutation == "schema_version":
        values["schema_version"] = "worker_request_v2"
    elif mutation == "unknown_adapter":
        values["adapter_id"] = "unknown_adapter"
    elif mutation == "scientific_input_schema":
        values["scientific_inputs"] = {
            "exchange": 1.0,
            "target_answer": 2.0,
        }
    elif mutation == "numerical_control_schema":
        values["numerical_controls"] = {
            "maximum_refinement_iterations": 64,
            "caller_tolerance": 1e-12,
        }
    else:
        values["capsule_sha256"] = "f" * 63
    with pytest.raises(AdapterContractError):
        isolation.WorkerRequest(**values)


def test_detached_definition_cannot_weaken_canonical_worker_validation():
    from validation import literature_evidence_isolation as isolation

    canonical = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    values = {
        field.name: getattr(canonical, field.name)
        for field in dataclasses.fields(AdapterDefinition)
    }
    values["scientific_input_schema"] = _object_schema(
        (("exchange", _number_schema(lower=None, units="J")),)
    )
    detached = AdapterDefinition(**values)
    authority = isolation.validate_authority_context(
        _authority_context_payload(), allow_test_producer=True
    )
    with pytest.raises(AdapterContractError, match="detached|canonical"):
        isolation.make_worker_request(
            detached,
            authority,
            opaque_run_nonce="detached-definition-nonce",
            capsule_sha256=_sha256_text("detached-definition-capsule"),
            allow_test_producer=True,
        )


def _source_span_authority_payload():
    payload = _authority_context_payload()
    locator = {
        "kind": "source_model_span",
        "source_id": "source-model-canary",
        "source_sha256": _sha256_text("source-model-artifact-canary"),
        "path": ["model", "exchange"],
        "coordinate_space": "verified_extracted_text_utf8",
        "coordinate_view_sha256": _sha256_text(
            "verified-extracted-text-view-canary"
        ),
        "byte_start": 120,
        "byte_end": 168,
        "span_sha256": _sha256_text("source-model-span-canary"),
    }
    payload["parameter_provenance"] = {
        "exchange": {
            "kind": "source_model_parameter",
            "requirement": {
                "source_path": ["model", "exchange"],
                "physical_role": "source-model exchange",
            },
            "locator": locator,
            "commitment_sha256": canonical_sha256(locator),
            "target_equivalent": False,
        }
    }
    return _rehash_authority_payload(payload)


def test_source_model_provenance_requires_an_exact_source_span():
    from validation import literature_evidence_isolation as isolation

    accepted = isolation.validate_authority_context(
        _source_span_authority_payload(), allow_test_producer=True
    )
    locator = accepted.parameter_provenance["exchange"]["locator"]
    assert locator["kind"] == "source_model_span"
    assert locator["byte_end"] > locator["byte_start"]
    assert accepted.parameter_provenance["exchange"][
        "commitment_sha256"
    ] == canonical_sha256(locator)


@pytest.mark.parametrize(
    "mutation",
    (
        "missing_source_sha256",
        "malformed_source_sha256",
        "missing_coordinate_view_sha256",
        "malformed_coordinate_view_sha256",
        "missing_byte_start",
        "missing_byte_end",
        "missing_span_sha256",
        "malformed_span_sha256",
        "unknown_coordinate_space",
        "empty_bounds",
        "reversed_bounds",
        "path_mismatch",
        "arbitrary_commitment",
        "unknown_field",
    ),
)
def test_source_span_rejects_each_incomplete_or_unbound_record(mutation):
    from validation import literature_evidence_isolation as isolation

    payload = _source_span_authority_payload()
    record = payload["parameter_provenance"]["exchange"]
    locator = record["locator"]
    if mutation.startswith("missing_"):
        locator.pop(mutation.removeprefix("missing_"))
    elif mutation.startswith("malformed_"):
        locator[mutation.removeprefix("malformed_")] = "f" * 63
    elif mutation == "empty_bounds":
        locator["byte_start"] = 16
        locator["byte_end"] = 16
    elif mutation == "reversed_bounds":
        locator["byte_start"] = 32
        locator["byte_end"] = 16
    elif mutation == "path_mismatch":
        locator["path"] = ["model", "mutated_exchange"]
    elif mutation == "unknown_coordinate_space":
        locator["coordinate_space"] = "caller_defined_coordinates"
    elif mutation == "arbitrary_commitment":
        record["commitment_sha256"] = _sha256_text(
            "arbitrary-source-span-commitment"
        )
    else:
        locator["unexpected_span_field"] = True
    payload = _rehash_authority_payload(payload)
    expected_guard = {
        "missing_source_sha256": "missing required field source_sha256",
        "malformed_source_sha256": "source_sha256.*SHA-256",
        "missing_coordinate_view_sha256": (
            "missing required field coordinate_view_sha256"
        ),
        "malformed_coordinate_view_sha256": (
            "coordinate_view_sha256.*SHA-256"
        ),
        "missing_byte_start": "missing required field byte_start",
        "missing_byte_end": "missing required field byte_end",
        "missing_span_sha256": "missing required field span_sha256",
        "malformed_span_sha256": "span_sha256.*SHA-256",
        "unknown_coordinate_space": (
            "coordinate_space.*verified_extracted_text_utf8"
        ),
        "empty_bounds": "greater than byte_start|nonempty source span",
        "reversed_bounds": "greater than byte_start|nonempty source span",
        "path_mismatch": "path.*requirement",
        "arbitrary_commitment": "commitment.*locator",
        "unknown_field": "unexpected_span_field",
    }[mutation]
    with pytest.raises(AdapterContractError, match=expected_guard):
        isolation.validate_authority_context(
            payload, allow_test_producer=True
        )


def test_dependency_public_symbols_are_not_reverse_module_attributes():
    from validation import literature_evidence_adapter_oracles as oracles
    from validation import literature_evidence_isolation as isolation

    dependency_symbols = {
        "AdapterContractError",
        "AdapterDefinition",
        "FrozenJsonObject",
        "ResourceLimits",
        "RuntimeRequirements",
        "ValueSchema",
        "canonical_json_bytes",
        "canonical_sha256",
        "require_exact_keys",
        "require_identifier",
        "validate_adapter_definition",
        "validate_numerical_controls",
        "validate_scientific_inputs",
    }
    assert not dependency_symbols.intersection(vars(oracles))
    assert not dependency_symbols.intersection(vars(isolation))
    for public_name in oracles.__all__:
        value = getattr(oracles, public_name)
        if callable(value):
            assert value.__module__ == oracles.__name__
    for public_name in isolation.__all__:
        value = getattr(isolation, public_name)
        if callable(value):
            assert value.__module__ == isolation.__name__


EXACT_BOUNDARY_MISSING_FIELD_CASES = tuple(
    ("authority", field_name)
    for field_name in sorted(AUTHORITY_CONTEXT_FIELDS)
) + tuple(
    ("failure", field_name)
    for field_name in sorted(FAILURE_CONTRACT_FIELDS)
) + tuple(
    ("local", field_name)
    for field_name in sorted(LOCAL_OBSERVABLE_RESULT_FIELDS)
) + tuple(
    ("worker", field_name)
    for field_name in sorted(WORKER_REQUEST_FIELDS)
)


def _exact_public_boundary_record(record_kind):
    from validation import literature_evidence_isolation as isolation

    if record_kind == "authority":
        return isolation.validate_authority_context(
            _authority_context_payload(),
            allow_test_producer=True,
        )
    if record_kind == "failure":
        return isolation.validate_failure(_failure_payload())
    if record_kind == "local":
        return adapters.LocalObservableResult(**_local_observable_payload())
    return _valid_worker_request()


def _invoke_exact_public_boundary(record_kind, record):
    from validation import literature_evidence_isolation as isolation

    if record_kind == "authority":
        return isolation.validate_authority_context(
            record,
            allow_test_producer=True,
        )
    if record_kind == "failure":
        return isolation.validate_failure(record)
    if record_kind == "local":
        definition = adapters.ADAPTER_DEFINITIONS[
            "square_ising_self_dual_tc"
        ]
        return adapters.validate_local_observable_result(definition, record)
    return record.to_frozen_json()


@pytest.mark.parametrize(
    "record_kind, missing_field",
    EXACT_BOUNDARY_MISSING_FIELD_CASES,
    ids=tuple(
        f"{record_kind}-{field_name}"
        for record_kind, field_name in EXACT_BOUNDARY_MISSING_FIELD_CASES
    ),
)
def test_exact_public_boundaries_normalize_every_missing_attribute(
    record_kind,
    missing_field,
):
    record = _exact_public_boundary_record(record_kind)
    object.__delattr__(record, missing_field)

    with pytest.raises(AdapterContractError):
        _invoke_exact_public_boundary(record_kind, record)


@pytest.mark.parametrize(
    "record_kind",
    ("authority", "failure", "local", "worker"),
)
def test_exact_public_boundaries_normalize_blank_exact_records(record_kind):
    from validation import literature_evidence_isolation as isolation

    record_types = {
        "authority": isolation.AdapterAuthorityContext,
        "failure": isolation.AdapterRunFailure,
        "local": adapters.LocalObservableResult,
        "worker": isolation.WorkerRequest,
    }
    blank_record = object.__new__(record_types[record_kind])

    with pytest.raises(AdapterContractError):
        _invoke_exact_public_boundary(record_kind, blank_record)


@pytest.mark.parametrize(
    "record_kind",
    ("authority", "local", "worker"),
)
def test_public_record_serializers_freshly_revalidate_semantic_tampering(
    record_kind,
):
    record = _exact_public_boundary_record(record_kind)
    if record_kind == "authority":
        object.__setattr__(
            record,
            "scientific_inputs",
            freeze_json({"exchange": 2.0}),
        )
    elif record_kind == "local":
        object.__setattr__(record, "worker_finished_monotonic_ns", 0)
    else:
        object.__setattr__(
            record,
            "scientific_inputs",
            freeze_json({"exchange": "not-a-number"}),
        )

    with pytest.raises(AdapterContractError):
        record.to_frozen_json()


CANONICAL_DEFINITION_BYTE_FAILURES = (
    (
        "deep_json",
        b"[" * 2_000 + b"0" + b"]" * 2_000,
    ),
    (
        "oversized",
        b"{" + b" " * 1_048_576 + b"}",
    ),
    (
        "huge_integer",
        b'{"value":' + b"9" * 5_000 + b"}",
    ),
    (
        "duplicate_key",
        b'{"adapter_id":"a","adapter_id":"b"}',
    ),
    (
        "noncanonical",
        b'{ "adapter_id":"a"}',
    ),
    (
        "nonfinite",
        b'{"value":NaN}',
    ),
)


@pytest.mark.parametrize(
    "case_name, malformed_bytes",
    CANONICAL_DEFINITION_BYTE_FAILURES,
    ids=tuple(case[0] for case in CANONICAL_DEFINITION_BYTE_FAILURES),
)
def test_canonical_definition_byte_failures_are_contract_errors(
    case_name,
    malformed_bytes,
):
    from validation import literature_evidence_isolation as isolation

    values = _adapter_policy_values(
        adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    )
    values["canonical_definition_bytes"] = malformed_bytes
    values["canonical_definition_sha256"] = hashlib.sha256(
        malformed_bytes
    ).hexdigest()
    values["combined_sha256"] = isolation.scientific_policy_combined_sha256(
        values
    )

    with pytest.raises(AdapterContractError):
        isolation.ScientificPolicyCommitment(**values)


TASK5_NODE_FIELDS = {
    "relative_path",
    "raw_file_sha256",
    "node_kind",
    "qualified_name",
    "source_span_sha256",
    "emitted_node_sha256",
    "dependency_edges",
    "scanner_version",
}


def _write_task5_source(source_root, module_name, source_bytes):
    source_path = source_root.joinpath(*module_name.split(".")).with_suffix(
        ".py"
    )
    source_path.parent.mkdir(parents=True, exist_ok=True)
    if type(source_bytes) is str:
        source_bytes = source_bytes.encode("utf-8")
    with source_path.open("xb") as stream:
        stream.write(source_bytes)
    return source_path


def _task5_pure_scientific_source(helper_increment=""):
    return (
        "from math import sqrt as square_root\n"
        "\n"
        "SCALE = (2.0, 3.0)\n"
        "UNRELATED_REGISTRY_RESULTS = {\"phase_label\": \"canary\"}\n"
        "\n"
        "def normalize(value):\n"
        f"    return square_root(value{helper_increment}) * SCALE[0]\n"
        "\n"
        "def adapter_entry(value):\n"
        "    return normalize(value)\n"
    )


def _build_task5_scientific_closure(source_root):
    from validation import literature_evidence_isolation as isolation

    return isolation.build_scientific_closure(
        "synthetic_science.adapters:adapter_entry",
        role="adapter",
        source_roots=(source_root,),
    )


def test_scientific_closure_has_exact_deterministic_transitive_manifest(
    tmp_path,
):
    source = _task5_pure_scientific_source()
    source_path = _write_task5_source(
        tmp_path, "synthetic_science.adapters", source
    )

    first = _build_task5_scientific_closure(tmp_path)
    second = _build_task5_scientific_closure(tmp_path)

    assert first == second
    assert first.role == "adapter"
    assert first.entry_symbol == (
        "synthetic_science.adapters:adapter_entry"
    )
    assert first.bundle_sha256 == second.bundle_sha256
    assert first.emitted_source_sha256 == second.emitted_source_sha256
    assert all(set(node) == TASK5_NODE_FIELDS for node in first.nodes)
    assert all(
        node["relative_path"] == "synthetic_science/adapters.py"
        for node in first.nodes
    )
    raw_file_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
    assert {node["raw_file_sha256"] for node in first.nodes} == {
        raw_file_sha256
    }
    assert {node["scanner_version"] for node in first.nodes} == {
        "deterministic_ast_closure_v1"
    }

    by_name = {node["qualified_name"]: node for node in first.nodes}
    assert set(by_name) == {
        "synthetic_science.adapters.square_root",
        "synthetic_science.adapters.SCALE",
        "synthetic_science.adapters.normalize",
        "synthetic_science.adapters.adapter_entry",
    }
    assert {node["node_kind"] for node in first.nodes} == {
        "import",
        "immutable_constant",
        "function",
    }
    assert (
        "synthetic_science.adapters.adapter_entry",
        "synthetic_science.adapters.normalize",
    ) in first.dependency_edges
    assert (
        "synthetic_science.adapters.normalize",
        "synthetic_science.adapters.square_root",
    ) in first.dependency_edges
    assert (
        "synthetic_science.adapters.normalize",
        "synthetic_science.adapters.SCALE",
    ) in first.dependency_edges
    assert tuple(
        edge
        for node in first.nodes
        for edge in node["dependency_edges"]
    ) == first.dependency_edges

    emitted_source = (
        "from math import sqrt as square_root\n"
        "\n"
        "SCALE = (2.0, 3.0)\n"
        "\n"
        "def normalize(value):\n"
        "    return square_root(value) * SCALE[0]\n"
        "\n"
        "def adapter_entry(value):\n"
        "    return normalize(value)\n"
    ).encode("utf-8")
    assert b"UNRELATED_REGISTRY_RESULTS" not in emitted_source
    assert first.emitted_source_sha256 == hashlib.sha256(
        emitted_source
    ).hexdigest()


def test_scientific_closure_normalizes_only_emitted_line_endings(tmp_path):
    lf_root = tmp_path / "lf"
    crlf_root = tmp_path / "crlf"
    source = _task5_pure_scientific_source()
    _write_task5_source(lf_root, "synthetic_science.adapters", source)
    _write_task5_source(
        crlf_root,
        "synthetic_science.adapters",
        source.replace("\n", "\r\n"),
    )

    lf_closure = _build_task5_scientific_closure(lf_root)
    crlf_closure = _build_task5_scientific_closure(crlf_root)

    assert lf_closure.emitted_source_sha256 == (
        crlf_closure.emitted_source_sha256
    )
    assert {
        node["qualified_name"]: node["emitted_node_sha256"]
        for node in lf_closure.nodes
    } == {
        node["qualified_name"]: node["emitted_node_sha256"]
        for node in crlf_closure.nodes
    }
    assert {
        node["raw_file_sha256"] for node in lf_closure.nodes
    } != {node["raw_file_sha256"] for node in crlf_closure.nodes}
    assert {
        node["source_span_sha256"] for node in lf_closure.nodes
    } != {node["source_span_sha256"] for node in crlf_closure.nodes}
    assert lf_closure.bundle_sha256 != crlf_closure.bundle_sha256


def test_transitive_hash_changes_when_only_helper_source_changes(tmp_path):
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    _write_task5_source(
        first_root,
        "synthetic_science.adapters",
        _task5_pure_scientific_source(),
    )
    _write_task5_source(
        second_root,
        "synthetic_science.adapters",
        _task5_pure_scientific_source(" + 1.0"),
    )

    first = _build_task5_scientific_closure(first_root)
    second = _build_task5_scientific_closure(second_root)
    first_nodes = {
        node["qualified_name"]: node for node in first.nodes
    }
    second_nodes = {
        node["qualified_name"]: node for node in second.nodes
    }

    helper = "synthetic_science.adapters.normalize"
    entry = "synthetic_science.adapters.adapter_entry"
    assert first_nodes[helper]["source_span_sha256"] != (
        second_nodes[helper]["source_span_sha256"]
    )
    assert first_nodes[helper]["emitted_node_sha256"] != (
        second_nodes[helper]["emitted_node_sha256"]
    )
    assert first_nodes[entry]["source_span_sha256"] == (
        second_nodes[entry]["source_span_sha256"]
    )
    assert first.emitted_source_sha256 != second.emitted_source_sha256
    assert first.bundle_sha256 != second.bundle_sha256


def test_scientific_closure_rejects_cross_module_emitted_binding_collision(
    tmp_path,
):
    _write_task5_source(
        tmp_path,
        "synthetic_science.left_helper",
        "SCALE = 2.0\n"
        "def left(value):\n"
        "    return value * SCALE\n",
    )
    _write_task5_source(
        tmp_path,
        "synthetic_science.right_helper",
        "SCALE = 3.0\n"
        "def right(value):\n"
        "    return value * SCALE\n",
    )
    _write_task5_source(
        tmp_path,
        "synthetic_science.adapters",
        "from synthetic_science.left_helper import left\n"
        "from synthetic_science.right_helper import right\n"
        "def adapter_entry(value):\n"
        "    return left(value) + right(value)\n",
    )

    with pytest.raises(AdapterContractError, match="binding|collision|module"):
        _build_task5_scientific_closure(tmp_path)


TASK5_UNSUPPORTED_SCIENTIFIC_SOURCES = (
    (
        "unresolved_dependency",
        "def adapter_entry(value):\n"
        "    return missing_helper(value)\n",
    ),
    (
        "cyclic_initializer",
        "LEFT = RIGHT + 1\n"
        "RIGHT = LEFT + 1\n"
        "def adapter_entry(value):\n"
        "    return value + LEFT\n",
    ),
    (
        "star_import",
        "from math import *\n"
        "def adapter_entry(value):\n"
        "    return sqrt(value)\n",
    ),
    (
        "dynamic_import",
        "def adapter_entry(value):\n"
        "    return __import__(\"math\").sqrt(value)\n",
    ),
    (
        "mutable_global",
        "CACHE = []\n"
        "def adapter_entry(value):\n"
        "    return value + len(CACHE)\n",
    ),
    (
        "decorator_side_effect",
        "def register():\n"
        "    return lambda function: function\n"
        "@register()\n"
        "def adapter_entry(value):\n"
        "    return value\n",
    ),
    (
        "descriptor",
        "class Descriptor:\n"
        "    def __get__(self, instance, owner):\n"
        "        return 1\n"
        "def adapter_entry(value):\n"
        "    return Descriptor()\n",
    ),
    (
        "metaclass",
        "class Meta(type):\n"
        "    pass\n"
        "class Scientific(metaclass=Meta):\n"
        "    pass\n"
        "def adapter_entry(value):\n"
        "    return Scientific()\n",
    ),
    (
        "module_mutation",
        "VALUE = 1\n"
        "VALUE += 1\n"
        "def adapter_entry(value):\n"
        "    return value + VALUE\n",
    ),
    (
        "runtime_closure",
        "def adapter_entry(value):\n"
        "    def hidden():\n"
        "        return value\n"
        "    return hidden()\n",
    ),
    (
        "source_evaluation",
        "def adapter_entry(value):\n"
        "    return eval(\"value\")\n",
    ),
    (
        "comprehension_scope",
        "HELPERS = (1, 2)\n"
        "def helper(value):\n"
        "    return value + 1\n"
        "def adapter_entry(value):\n"
        "    return [helper(item) for helper in HELPERS]\n",
    ),
)


@pytest.mark.parametrize(
    "case_name, source",
    TASK5_UNSUPPORTED_SCIENTIFIC_SOURCES,
    ids=tuple(case[0] for case in TASK5_UNSUPPORTED_SCIENTIFIC_SOURCES),
)
def test_scientific_closure_rejects_each_unsupported_ast_construct(
    tmp_path,
    case_name,
    source,
):
    del case_name
    _write_task5_source(tmp_path, "synthetic_science.adapters", source)

    with pytest.raises(AdapterContractError):
        _build_task5_scientific_closure(tmp_path)


TASK5_DEFINITION_TIME_EXECUTION_SOURCES = (
    (
        "helper_call_in_positional_default",
        "def make_default():\n"
        "    return 1\n"
        "def adapter_entry(value=make_default()):\n"
        "    return value\n",
    ),
    (
        "helper_call_in_keyword_default",
        "def make_default():\n"
        "    return 1\n"
        "def adapter_entry(value, *, control=make_default()):\n"
        "    return value\n",
    ),
    (
        "helper_call_in_argument_annotation",
        "def make_annotation():\n"
        "    return object\n"
        "def adapter_entry(value: make_annotation()):\n"
        "    return value\n",
    ),
    (
        "helper_call_in_return_annotation",
        "def make_annotation():\n"
        "    return object\n"
        "def adapter_entry(value) -> make_annotation():\n"
        "    return value\n",
    ),
    (
        "module_annotated_assignment_execution",
        "PAYLOAD: __import__('os').system('blocked') = (1,)\n"
        "def adapter_entry(value):\n"
        "    return value + PAYLOAD[0]\n",
    ),
    (
        "class_annotated_assignment_execution",
        "class Payload:\n"
        "    item: __import__('os').system('blocked') = 1\n"
        "def adapter_entry(value):\n"
        "    return value, Payload\n",
    ),
    (
        "subscripted_function_default",
        "DEFAULTS = (1,)\n"
        "def adapter_entry(value=DEFAULTS[0]):\n"
        "    return value\n",
    ),
    (
        "class_getitem_initializer",
        "class Hook:\n"
        "    def __class_getitem__(cls, item):\n"
        "        return (item,)\n"
        "PAYLOAD = Hook[0]\n"
        "def adapter_entry(value):\n"
        "    return value + PAYLOAD[0]\n",
    ),
)


@pytest.mark.parametrize(
    "case_name, source",
    TASK5_DEFINITION_TIME_EXECUTION_SOURCES,
    ids=tuple(case[0] for case in TASK5_DEFINITION_TIME_EXECUTION_SOURCES),
)
def test_scientific_closure_rejects_definition_time_expression_execution(
    tmp_path,
    case_name,
    source,
):
    del case_name
    _write_task5_source(tmp_path, "synthetic_science.adapters", source)

    with pytest.raises(
        AdapterContractError,
        match="definition|initializer|immutable|source|hook|unsupported",
    ):
        _build_task5_scientific_closure(tmp_path)


@pytest.mark.parametrize(
    "case_name, source",
    (
        (
            "constant_defaults_and_annotations",
            "def adapter_entry(\n"
            "    value: object = None, *, control: float = 2.0\n"
            ") -> object:\n"
            "    return value\n",
        ),
        (
            "annotated_immutable_module_and_class_state",
            "SCALE: tuple = (2.0, 3.0)\n"
            "class Plain:\n"
            "    label: str = 'transport'\n"
            "def adapter_entry(value):\n"
            "    return value * SCALE[0], Plain\n",
        ),
        (
            "named_immutable_initializer",
            "BASE = 2\n"
            "SCALE = (BASE, 3)\n"
            "def adapter_entry(value):\n"
            "    return value * SCALE[0]\n",
        ),
        (
            "tuple_default",
            "def adapter_entry(value=(1, 2)):\n"
            "    return value[0]\n",
        ),
    ),
    ids=(
        "constant_defaults_and_annotations",
        "annotated_immutable_module_and_class_state",
        "named_immutable_initializer",
        "tuple_default",
    ),
)
def test_scientific_closure_allows_inert_definition_time_control(
    tmp_path,
    case_name,
    source,
):
    del case_name
    _write_task5_source(tmp_path, "synthetic_science.adapters", source)

    closure = _build_task5_scientific_closure(tmp_path)

    assert closure.entry_symbol == (
        "synthetic_science.adapters:adapter_entry"
    )


TASK5_RUNTIME_NAME_DEFINITION_SOURCES = (
    (
        "function_name_default",
        "def helper(value):\n"
        "    return value\n"
        "def adapter_entry(value=helper):\n"
        "    return value\n",
    ),
    (
        "class_name_default",
        "class Payload:\n"
        "    pass\n"
        "def adapter_entry(value=Payload):\n"
        "    return value\n",
    ),
    (
        "function_name_argument_annotation",
        "def helper(value):\n"
        "    return value\n"
        "def adapter_entry(value: helper):\n"
        "    return value\n",
    ),
    (
        "function_name_return_annotation",
        "def helper(value):\n"
        "    return value\n"
        "def adapter_entry(value) -> helper:\n"
        "    return value\n",
    ),
    (
        "class_name_argument_annotation",
        "class Payload:\n"
        "    pass\n"
        "def adapter_entry(value: Payload):\n"
        "    return value\n",
    ),
    (
        "class_name_return_annotation",
        "class Payload:\n"
        "    pass\n"
        "def adapter_entry(value) -> Payload:\n"
        "    return value\n",
    ),
    (
        "function_name_constant_alias",
        "def helper(value):\n"
        "    return value\n"
        "CALLBACK = helper\n"
        "def adapter_entry(value):\n"
        "    return CALLBACK(value)\n",
    ),
    (
        "class_name_constant_alias",
        "class Payload:\n"
        "    pass\n"
        "ALIAS = Payload\n"
        "def adapter_entry(value):\n"
        "    return value, ALIAS\n",
    ),
    (
        "tuple_wrapped_function_default",
        "def helper(value):\n"
        "    return value\n"
        "def adapter_entry(value=(helper,)):\n"
        "    return value\n",
    ),
    (
        "conditional_wrapped_class_default",
        "class Payload:\n"
        "    pass\n"
        "def adapter_entry(value=Payload if True else None):\n"
        "    return value\n",
    ),
    (
        "tuple_wrapped_function_alias",
        "def helper(value):\n"
        "    return value\n"
        "CALLBACKS = (helper,)\n"
        "def adapter_entry(value):\n"
        "    return CALLBACKS[0](value)\n",
    ),
    (
        "boolean_wrapped_function_alias",
        "def helper(value):\n"
        "    return value\n"
        "CALLBACK = helper or None\n"
        "def adapter_entry(value):\n"
        "    return CALLBACK(value)\n",
    ),
    (
        "unary_wrapped_function_alias",
        "def helper(value):\n"
        "    return value\n"
        "CALLBACK = +helper\n"
        "def adapter_entry(value):\n"
        "    return CALLBACK(value)\n",
    ),
    (
        "binary_wrapped_class_alias",
        "class Payload:\n"
        "    pass\n"
        "ALIAS = Payload | object\n"
        "def adapter_entry(value):\n"
        "    return value, ALIAS\n",
    ),
    (
        "comparison_wrapped_function_alias",
        "def helper(value):\n"
        "    return value\n"
        "MATCH = helper == helper\n"
        "def adapter_entry(value):\n"
        "    return value, MATCH\n",
    ),
    (
        "import_name_constant_alias",
        "from math import sqrt\n"
        "CALLBACK = sqrt\n"
        "def adapter_entry(value):\n"
        "    return CALLBACK(value)\n",
    ),
    (
        "callable_builtin_default",
        "def adapter_entry(value=tuple):\n"
        "    return value\n",
    ),
    (
        "callable_builtin_constant_alias",
        "CALLBACK = tuple\n"
        "def adapter_entry(value):\n"
        "    return CALLBACK((value,))\n",
    ),
    (
        "non_type_builtin_annotation",
        "def adapter_entry(value: len):\n"
        "    return value\n",
    ),
    (
        "import_name_annotation",
        "from math import sqrt\n"
        "def adapter_entry(value: sqrt):\n"
        "    return value\n",
    ),
)


@pytest.mark.parametrize(
    "case_name, source",
    TASK5_RUNTIME_NAME_DEFINITION_SOURCES,
    ids=tuple(case[0] for case in TASK5_RUNTIME_NAME_DEFINITION_SOURCES),
)
def test_scientific_closure_rejects_runtime_name_in_inert_context(
    tmp_path,
    case_name,
    source,
):
    del case_name
    _write_task5_source(tmp_path, "synthetic_science.adapters", source)

    with pytest.raises(
        AdapterContractError,
        match="annotation|constant|immutable|binding|runtime|type|import",
    ):
        _build_task5_scientific_closure(tmp_path)


@pytest.mark.parametrize(
    "case_name, source",
    (
        (
            "immutable_name_default",
            "DEFAULT = 2\n"
            "def adapter_entry(value=DEFAULT):\n"
            "    return value\n",
        ),
        (
            "transitive_scalar_and_tuple_aliases",
            "BASE = 2\n"
            "ALIAS = BASE\n"
            "PAIR = (ALIAS, 3)\n"
            "NESTED = (PAIR, ALIAS)\n"
            "def adapter_entry(value):\n"
            "    return value + NESTED[0][0]\n",
        ),
        (
            "wrapped_immutable_names",
            "BASE = 2\n"
            "INCREMENT = BASE + 1\n"
            "FLAG = INCREMENT > BASE\n"
            "CHOICE = INCREMENT if FLAG else BASE\n"
            "OPTIONS = (CHOICE, FLAG)\n"
            "def adapter_entry(value):\n"
            "    return value + OPTIONS[0]\n",
        ),
        (
            "ordinary_builtin_annotations",
            "def adapter_entry(value: int = 1) -> float:\n"
            "    return value\n",
        ),
    ),
    ids=(
        "immutable_name_default",
        "transitive_scalar_and_tuple_aliases",
        "wrapped_immutable_names",
        "ordinary_builtin_annotations",
    ),
)
def test_scientific_closure_allows_context_approved_names(
    tmp_path,
    case_name,
    source,
):
    del case_name
    _write_task5_source(tmp_path, "synthetic_science.adapters", source)

    closure = _build_task5_scientific_closure(tmp_path)

    assert closure.entry_symbol == (
        "synthetic_science.adapters:adapter_entry"
    )


def test_scientific_closure_preserves_future_annotations_semantics(
    tmp_path,
):
    source = (
        "from __future__ import annotations\n"
        "def adapter_entry(value: int) -> str:\n"
        "    return value\n"
    )
    _write_task5_source(
        tmp_path,
        "synthetic_science.adapters",
        source,
    )

    closure = _build_task5_scientific_closure(tmp_path)

    assert tuple(
        node["qualified_name"] for node in closure.nodes
    ) == (
        "synthetic_science.adapters.__future_annotations__",
        "synthetic_science.adapters.adapter_entry",
    )
    emitted_source = source.replace(
        "annotations\ndef", "annotations\n\ndef"
    ).encode("utf-8")
    assert closure.emitted_source_sha256 == hashlib.sha256(
        emitted_source
    ).hexdigest()


def test_scientific_closure_does_not_resolve_future_annotation_names(
    tmp_path,
):
    _write_task5_source(
        tmp_path,
        "synthetic_science.adapters",
        "from __future__ import annotations\n"
        "class Payload:\n"
        "    pass\n"
        "def adapter_entry(\n"
        "    value: list[Payload] | MissingType,\n"
        ") -> Payload:\n"
        "    return value\n",
    )

    closure = _build_task5_scientific_closure(tmp_path)

    assert tuple(
        node["qualified_name"] for node in closure.nodes
    ) == (
        "synthetic_science.adapters.__future_annotations__",
        "synthetic_science.adapters.adapter_entry",
    )


def test_scientific_closure_preserves_all_future_annotation_imports(
    tmp_path,
):
    _write_task5_source(
        tmp_path,
        "synthetic_science.helpers",
        "from __future__ import annotations\n"
        "from math import cos\n"
        "def helper(value: int) -> int:\n"
        "    return cos(value)\n",
    )
    _write_task5_source(
        tmp_path,
        "synthetic_science.adapters",
        "from __future__ import annotations\n"
        "import math\n"
        "from synthetic_science.helpers import helper\n"
        "def adapter_entry(value: int) -> int:\n"
        "    return helper(value) + math.sin(value)\n",
    )

    closure = _build_task5_scientific_closure(tmp_path)

    assert tuple(
        node["qualified_name"]
        for node in closure.nodes
        if node["qualified_name"].endswith(".__future_annotations__")
    ) == (
        "synthetic_science.adapters.__future_annotations__",
        "synthetic_science.helpers.__future_annotations__",
    )
    assert tuple(node["node_kind"] for node in closure.nodes[:2]) == (
        "import",
        "import",
    )
    assert tuple(
        node["qualified_name"] for node in closure.nodes[2:4]
    ) == (
        "synthetic_science.adapters.math",
        "synthetic_science.helpers.cos",
    )


def test_scientific_closure_rejects_mixed_future_annotation_semantics(
    tmp_path,
):
    _write_task5_source(
        tmp_path,
        "synthetic_science.helpers",
        "def helper(value: int) -> int:\n"
        "    return value\n",
    )
    _write_task5_source(
        tmp_path,
        "synthetic_science.adapters",
        "from __future__ import annotations\n"
        "from synthetic_science.helpers import helper\n"
        "def adapter_entry(value: int) -> int:\n"
        "    return helper(value)\n",
    )

    with pytest.raises(
        AdapterContractError,
        match="future|annotation|semantic|mixed|preserv",
    ):
        _build_task5_scientific_closure(tmp_path)


def test_scientific_closure_parses_source_without_executing_module(tmp_path):
    source = (
        "EXECUTION_CANARY = 1 / 0\n"
        "def adapter_entry(value):\n"
        "    return value + 1\n"
    )
    _write_task5_source(tmp_path, "synthetic_science.adapters", source)

    closure = _build_task5_scientific_closure(tmp_path)

    assert tuple(
        node["qualified_name"] for node in closure.nodes
    ) == ("synthetic_science.adapters.adapter_entry",)


def test_scientific_closure_rejects_multi_alias_import_piggyback(tmp_path):
    _write_task5_source(
        tmp_path,
        "synthetic_science.adapters",
        "import math, os\n"
        "def adapter_entry(value):\n"
        "    return math.sqrt(value)\n",
    )

    with pytest.raises(AdapterContractError, match="import|alias|static"):
        _build_task5_scientific_closure(tmp_path)


@pytest.mark.parametrize(
    "role, module_name, entry_name",
    (
        (
            "adapter",
            "synthetic_science.adapter_oracles",
            "oracle_entry",
        ),
        ("oracle", "synthetic_science.adapters", "adapter_entry"),
    ),
)
def test_scientific_closure_rejects_opposite_role_modules(
    tmp_path,
    role,
    module_name,
    entry_name,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_source(
        tmp_path,
        module_name,
        f"def {entry_name}(value):\n    return value + 1\n",
    )

    with pytest.raises(AdapterContractError, match="role|adapter|oracle"):
        isolation.build_scientific_closure(
            f"{module_name}:{entry_name}",
            role=role,
            source_roots=(tmp_path,),
        )


def _build_task5_shared_closures(source_root, *, share_helper):
    from validation import literature_evidence_isolation as isolation

    shared_import = (
        "from synthetic_science.shared import shared_helper\n"
        if share_helper
        else ""
    )
    adapter_expression = "shared_helper(value)" if share_helper else "value + 1"
    oracle_expression = "shared_helper(value)" if share_helper else "value - 1"
    if share_helper:
        _write_task5_source(
            source_root,
            "synthetic_science.shared",
            "def shared_helper(value):\n    return value * value\n",
        )
    _write_task5_source(
        source_root,
        "synthetic_science.adapters",
        shared_import
        + "def adapter_entry(value):\n"
        + f"    return {adapter_expression}\n",
    )
    _write_task5_source(
        source_root,
        "synthetic_science.adapter_oracles",
        shared_import
        + "def oracle_entry(value):\n"
        + f"    return {oracle_expression}\n",
    )
    adapter_closure = isolation.build_scientific_closure(
        "synthetic_science.adapters:adapter_entry",
        role="adapter",
        source_roots=(source_root,),
    )
    oracle_closure = isolation.build_scientific_closure(
        "synthetic_science.adapter_oracles:oracle_entry",
        role="oracle",
        source_roots=(source_root,),
    )
    return adapter_closure, oracle_closure


def test_disjoint_scientific_closures_reject_shared_transitive_node(tmp_path):
    from validation import literature_evidence_isolation as isolation

    adapter_closure, oracle_closure = _build_task5_shared_closures(
        tmp_path, share_helper=True
    )

    with pytest.raises(AdapterContractError, match="overlap|disjoint|shared"):
        isolation.assert_disjoint_scientific_closures(
            adapter_closure, oracle_closure
        )


def test_disjoint_scientific_closures_accept_independent_nodes(tmp_path):
    from validation import literature_evidence_isolation as isolation

    adapter_closure, oracle_closure = _build_task5_shared_closures(
        tmp_path, share_helper=False
    )

    assert (
        isolation.assert_disjoint_scientific_closures(
            adapter_closure, oracle_closure
        )
        is None
    )


def _task5_policy_record_for_closure(values, closure):
    from validation import literature_evidence_isolation as isolation

    values = dict(values)
    values["entry_closure_sha256"] = closure.bundle_sha256
    values["static_scan_sha256"] = canonical_sha256(
        {
            "schema_version": "scientific_definition_policy_scan_v2",
            "scanner_version": isolation._STATIC_SCANNER_VERSION,
            "scanner_sha256": isolation._STATIC_SCANNER_SHA256,
            "role": values["role"],
            "canonical_definition_sha256": values[
                "canonical_definition_sha256"
            ],
            "entry_closure_sha256": closure.bundle_sha256,
            "checks": {
                "canonical_definition_valid": True,
                "role_and_entry_bound": True,
                "proof_bindings_closed": True,
                "domain_policy_closed": True,
                "size_policy_closed": True,
                "convergence_policy_closed": True,
                "forbidden_structures_absent": True,
            },
        }
    )
    values["combined_sha256"] = (
        isolation.scientific_policy_combined_sha256(values)
    )
    return isolation.ScientificPolicyCommitment(**values)


def _task5_partition_fixture(tmp_path, *, shared_science=False):
    from validation import literature_evidence_isolation as isolation

    shared_import = (
        "from validation.task5_shared import shared_helper\n"
        if shared_science
        else ""
    )
    extra_source_by_module = {
        "validation.literature_evidence_adapters": (
            shared_import
            + "def adapter_square_ising_self_dual_tc(value):\n"
            + (
                "    return shared_helper(value)\n"
                if shared_science
                else "    return value + 1\n"
            )
        ),
        "validation.literature_evidence_adapter_oracles": (
            shared_import
            + "def oracle_synthetic_residual_oracle(value):\n"
            + (
                "    return shared_helper(value)\n"
                if shared_science
                else "    return value - 1\n"
            )
        ),
    }
    if shared_science:
        _write_task5_source(
            tmp_path,
            "validation.task5_shared",
            "def shared_helper(value):\n    return value * value\n",
        )
    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module=extra_source_by_module,
    )
    adapter_closure = isolation.build_scientific_closure(
        (
            "validation.literature_evidence_adapters:"
            "adapter_square_ising_self_dual_tc"
        ),
        role="adapter",
        source_roots=(tmp_path,),
    )
    oracle_closure = isolation.build_scientific_closure(
        (
            "validation.literature_evidence_adapter_oracles:"
            "oracle_synthetic_residual_oracle"
        ),
        role="oracle",
        source_roots=(tmp_path,),
    )
    adapter_policy = _task5_policy_record_for_closure(
        _adapter_policy_values(
            adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
        ),
        adapter_closure,
    )
    oracle_policy = _task5_policy_record_for_closure(
        _oracle_policy_values(_synthetic_oracle_definition()),
        oracle_closure,
    )
    infrastructure = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )
    referenced = tuple(
        sorted(
            node["qualified_name"]
            for closure in (
                adapter_closure,
                oracle_closure,
                infrastructure,
            )
            for node in closure.nodes
        )
    )
    return (
        adapter_closure,
        adapter_policy,
        oracle_closure,
        oracle_policy,
        infrastructure,
        referenced,
    )


def _assert_task5_partition(fixture, referenced_project_nodes):
    from validation import literature_evidence_isolation as isolation

    return isolation.assert_complete_dependency_partition(
        *fixture[:5],
        referenced_project_nodes=referenced_project_nodes,
    )


def test_complete_dependency_partition_returns_deterministic_hash(tmp_path):
    fixture = _task5_partition_fixture(tmp_path)

    first = _assert_task5_partition(fixture, fixture[5])
    second = _assert_task5_partition(fixture, fixture[5])

    assert first == second
    assert len(first) == 64
    assert set(first) <= set("0123456789abcdef")


def test_dependency_partition_rejects_caller_chosen_policy_scan_hash(tmp_path):
    from validation import literature_evidence_isolation as isolation

    fixture = _task5_partition_fixture(tmp_path)
    policy_values = {
        field.name: getattr(fixture[1], field.name)
        for field in dataclasses.fields(type(fixture[1]))
    }
    policy_values["static_scan_sha256"] = _sha256_text(
        "caller-chosen-policy-structure-scan"
    )
    policy_values["combined_sha256"] = (
        isolation.scientific_policy_combined_sha256(policy_values)
    )
    forged_policy = isolation.ScientificPolicyCommitment(**policy_values)
    forged_fixture = (
        fixture[0],
        forged_policy,
        *fixture[2:],
    )

    with pytest.raises(AdapterContractError, match="policy|scan|commitment"):
        _assert_task5_partition(forged_fixture, fixture[5])


@pytest.mark.parametrize(
    "mutation",
    ("missing", "multiple", "dynamic", "uncommitted"),
)
def test_complete_dependency_partition_rejects_each_incomplete_case(
    tmp_path,
    mutation,
):
    from validation import literature_evidence_isolation as isolation

    fixture = _task5_partition_fixture(
        tmp_path, shared_science=mutation == "multiple"
    )
    referenced = fixture[5]
    if mutation == "missing":
        referenced = referenced[:-1]
    elif mutation == "dynamic":
        referenced = referenced + ("validation.dynamic.*",)
    elif mutation == "uncommitted":
        infrastructure = isolation.InfrastructureClosure(
            "infrastructure_closure_v1",
            fixture[4].roots,
            fixture[4].nodes,
            (
                (
                    "validation.task5_infrastructure.transport",
                    "committed_data:validation.task5.UNKNOWN_MAPPING",
                ),
            ),
            fixture[4].purpose_bindings,
            fixture[4].bundle_sha256,
        )
        fixture = (*fixture[:4], infrastructure, referenced)

    with pytest.raises(AdapterContractError):
        _assert_task5_partition(fixture, referenced)


EXPECTED_INFRASTRUCTURE_ROOTS = frozenset(
    {
        "validation.literature_evidence_adapters.freeze_json",
        "validation.literature_evidence_adapters.thaw_json",
        "validation.literature_evidence_adapters.canonical_json_bytes",
        "validation.literature_evidence_adapters.canonical_sha256",
        (
            "validation.literature_evidence_adapters."
            "validate_adapter_definition"
        ),
        (
            "validation.literature_evidence_adapter_oracles."
            "validate_oracle_definition"
        ),
        (
            "validation.literature_evidence_adapters."
            "validate_scientific_inputs"
        ),
        (
            "validation.literature_evidence_adapters."
            "validate_numerical_controls"
        ),
        (
            "validation.literature_evidence_adapters."
            "validate_local_observable_result"
        ),
        (
            "validation.literature_evidence_isolation."
            "validate_authority_context"
        ),
        "validation.literature_evidence_isolation.make_worker_request",
        "validation.literature_evidence_isolation.validate_failure",
        (
            "validation.literature_evidence_isolation."
            "build_scientific_closure"
        ),
        (
            "validation.literature_evidence_isolation."
            "build_scientific_policy_commitment"
        ),
        (
            "validation.literature_evidence_isolation."
            "build_infrastructure_closure"
        ),
        (
            "validation.literature_evidence_isolation."
            "scan_scientific_closure"
        ),
        (
            "validation.literature_evidence_isolation."
            "discover_runtime_resources"
        ),
        (
            "validation.literature_evidence_isolation."
            "build_runtime_snapshot"
        ),
        (
            "validation.literature_evidence_isolation."
            "revalidate_runtime_snapshot"
        ),
        (
            "validation.literature_evidence_isolation."
            "record_and_freeze_hashes"
        ),
        "validation.literature_evidence_isolation.acquire_run_seed",
        (
            "validation.literature_evidence_isolation."
            "derive_counterfactual_points"
        ),
        (
            "validation.literature_evidence_isolation."
            "write_worker_request_exclusive"
        ),
        (
            "validation.literature_evidence_isolation."
            "run_capability_preflight"
        ),
        (
            "validation.literature_evidence_isolation."
            "emit_scientific_capsule"
        ),
        "validation.literature_evidence_isolation.emit_fixed_worker",
        (
            "validation.literature_evidence_isolation."
            "create_run_directories"
        ),
        (
            "validation.literature_evidence_isolation."
            "construct_private_root"
        ),
        (
            "validation.literature_evidence_isolation."
            "run_namespace_supervisor"
        ),
        (
            "validation.literature_evidence_isolation."
            "launch_traced_tracee"
        ),
        (
            "validation.literature_evidence_isolation."
            "apply_tracee_security_policy"
        ),
        (
            "validation.literature_evidence_isolation."
            "validate_process_attestation"
        ),
        "validation.literature_evidence_isolation.evaluate_strace",
        (
            "validation.literature_evidence_isolation."
            "ingest_worker_output"
        ),
        (
            "validation.literature_evidence_isolation."
            "collect_backend_diagnostics"
        ),
        (
            "validation.literature_evidence_isolation."
            "interpret_output_proofs"
        ),
        (
            "validation.literature_evidence_isolation."
            "derive_convergence_decision"
        ),
        (
            "validation.literature_evidence_isolation."
            "derive_oracle_decision"
        ),
        (
            "validation.literature_evidence_isolation."
            "assert_complete_dependency_partition"
        ),
        (
            "validation.literature_evidence_isolation."
            "validate_adapter_execution_evidence"
        ),
        (
            "validation.literature_evidence_isolation."
            "_run_isolated_recomputation_core"
        ),
        (
            "validation.literature_evidence_isolation."
            "run_isolated_recomputation"
        ),
    }
)


EXPECTED_INFRASTRUCTURE_PURPOSES = {
    "canonical_transport": frozenset(
        {
            "freeze_json",
            "thaw_json",
            "canonical_json_bytes",
            "canonical_sha256",
        }
    ),
    "contract_validation": frozenset(
        {
            "validate_adapter_definition",
            "validate_oracle_definition",
            "validate_scientific_inputs",
            "validate_numerical_controls",
            "validate_local_observable_result",
            "validate_authority_context",
            "make_worker_request",
            "validate_failure",
        }
    ),
    "closure_and_policy_transport": frozenset(
        {
            "build_scientific_closure",
            "build_scientific_policy_commitment",
            "build_infrastructure_closure",
            "scan_scientific_closure",
            "emit_scientific_capsule",
            "emit_fixed_worker",
            "assert_complete_dependency_partition",
        }
    ),
    "runtime_resource_integrity": frozenset(
        {
            "discover_runtime_resources",
            "build_runtime_snapshot",
            "revalidate_runtime_snapshot",
        }
    ),
    "event_and_counterfactual_transport": frozenset(
        {
            "record_and_freeze_hashes",
            "acquire_run_seed",
            "derive_counterfactual_points",
            "write_worker_request_exclusive",
        }
    ),
    "capability_isolation_transport": frozenset(
        {
            "run_capability_preflight",
            "create_run_directories",
            "construct_private_root",
            "run_namespace_supervisor",
            "launch_traced_tracee",
            "apply_tracee_security_policy",
            "validate_process_attestation",
        }
    ),
    "trace_and_output_transport": frozenset(
        {"evaluate_strace", "ingest_worker_output"}
    ),
    "proof_adjudication_transport": frozenset(
        {
            "collect_backend_diagnostics",
            "interpret_output_proofs",
            "derive_convergence_decision",
            "derive_oracle_decision",
        }
    ),
    "coordinator_transport": frozenset(
        {
            "validate_adapter_execution_evidence",
            "_run_isolated_recomputation_core",
            "run_isolated_recomputation",
        }
    ),
}


def _task5_expected_purpose_bindings():
    bindings = {}
    for purpose, root_names in EXPECTED_INFRASTRUCTURE_PURPOSES.items():
        for qualified_name in EXPECTED_INFRASTRUCTURE_ROOTS:
            if qualified_name.rsplit(".", 1)[1] in root_names:
                assert qualified_name not in bindings
                bindings[qualified_name] = purpose
    assert set(bindings) == EXPECTED_INFRASTRUCTURE_ROOTS
    return bindings


def _write_task5_infrastructure_sources(
    source_root,
    *,
    omit_root=None,
    helper_name="_transport_identity",
    extra_source_by_module=None,
    body_by_root=None,
    declaration_by_root=None,
):
    if extra_source_by_module is None:
        extra_source_by_module = {}
    if body_by_root is None:
        body_by_root = {}
    if declaration_by_root is None:
        declaration_by_root = {}
    roots_by_module = {}
    for qualified_name in EXPECTED_INFRASTRUCTURE_ROOTS:
        module_name, root_name = qualified_name.rsplit(".", 1)
        roots_by_module.setdefault(module_name, []).append(root_name)
    for module_name, root_names in roots_by_module.items():
        source = (
            'INFRASTRUCTURE_PROTOCOL = "task5-v1"\n'
            f"def {helper_name}(value=None):\n"
            "    return value if INFRASTRUCTURE_PROTOCOL else None\n"
        )
        for root_name in sorted(root_names):
            if root_name == omit_root:
                continue
            if root_name in declaration_by_root:
                source += declaration_by_root[root_name]
                continue
            source += f"def {root_name}(value=None):\n"
            if root_name in body_by_root:
                source += body_by_root[root_name]
            elif root_name == "_run_isolated_recomputation_core":
                source += (
                    f"    return {helper_name}(value), "
                    "ADAPTER_ELIGIBILITY, ADAPTER_DEFINITIONS, "
                    "ORACLE_DEFINITIONS\n"
                )
            else:
                source += f"    return {helper_name}(value)\n"
        source += extra_source_by_module.get(module_name, "")
        _write_task5_source(source_root, module_name, source)


def test_infrastructure_closure_has_exact_roots_purposes_and_dependencies(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(tmp_path)

    first = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )
    second = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )

    assert first == second
    assert first.roots == tuple(sorted(EXPECTED_INFRASTRUCTURE_ROOTS))
    assert set(first.purpose_bindings) == EXPECTED_INFRASTRUCTURE_ROOTS
    assert first.purpose_bindings == _task5_expected_purpose_bindings()
    assert all(set(node) == TASK5_NODE_FIELDS for node in first.nodes)
    node_names = {node["qualified_name"] for node in first.nodes}
    assert EXPECTED_INFRASTRUCTURE_ROOTS <= node_names
    for module_name in {
        root.rsplit(".", 1)[0] for root in EXPECTED_INFRASTRUCTURE_ROOTS
    }:
        assert f"{module_name}._transport_identity" in node_names
        assert f"{module_name}.INFRASTRUCTURE_PROTOCOL" in node_names
    for root in EXPECTED_INFRASTRUCTURE_ROOTS:
        module_name = root.rsplit(".", 1)[0]
        assert (
            root,
            f"{module_name}._transport_identity",
        ) in first.dependency_edges

    committed_edges = {
        edge
        for edge in first.dependency_edges
        if edge[1].startswith("committed_data:")
    }
    core = (
        "validation.literature_evidence_isolation."
        "_run_isolated_recomputation_core"
    )
    assert committed_edges == {
        (
            core,
            (
                "committed_data:validation.literature_evidence_adapters."
                "ADAPTER_ELIGIBILITY"
            ),
        ),
        (
            core,
            (
                "committed_data:validation.literature_evidence_adapters."
                "ADAPTER_DEFINITIONS"
            ),
        ),
        (
            core,
            (
                "committed_data:"
                "validation.literature_evidence_adapter_oracles."
                "ORACLE_DEFINITIONS"
            ),
        ),
    }
    assert not any(
        node["qualified_name"].rsplit(".", 1)[-1]
        in {
            "ADAPTER_ELIGIBILITY",
            "ADAPTER_DEFINITIONS",
            "ORACLE_DEFINITIONS",
        }
        for node in first.nodes
    )


def test_infrastructure_closure_rejects_local_committed_data_shadow(tmp_path):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": (
                'ADAPTER_DEFINITIONS = "malicious-local-shadow"\n'
            )
        },
    )

    with pytest.raises(
        AdapterContractError, match="committed|data|shadow|edge"
    ):
        isolation.build_infrastructure_closure(
            source_roots=(tmp_path,)
        )


def test_infrastructure_closure_rejects_missing_root_and_caller_extras(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path, omit_root="collect_backend_diagnostics"
    )
    with pytest.raises(AdapterContractError, match="root|missing|resolve"):
        isolation.build_infrastructure_closure(
            source_roots=(tmp_path,)
        )
    with pytest.raises(TypeError):
        isolation.build_infrastructure_closure(
            source_roots=(tmp_path,),
            roots=("validation.caller.extra",),
        )


@pytest.mark.parametrize(
    "helper_name",
    ("_build_model_hamiltonian", "_derive_method_result"),
)
def test_infrastructure_closure_rejects_scientific_or_result_helper(
    tmp_path,
    helper_name,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path, helper_name=helper_name
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|scientific|result|Hamiltonian|purpose",
    ):
        isolation.build_infrastructure_closure(
            source_roots=(tmp_path,)
        )


def _task5_minimal_scientific_closure(entry_symbol, role, seed):
    from validation import literature_evidence_isolation as isolation

    module_name, function_name = entry_symbol.split(":", 1)
    source_bytes = (
        f"def {function_name}(value):\n"
        f"    return value  # {seed}\n"
    ).encode("utf-8")
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    qualified_name = f"{module_name}.{function_name}"
    node = {
        "relative_path": module_name.replace(".", "/") + ".py",
        "raw_file_sha256": source_sha256,
        "node_kind": "function",
        "qualified_name": qualified_name,
        "source_span_sha256": source_sha256,
        "emitted_node_sha256": source_sha256,
        "dependency_edges": (),
        "scanner_version": "deterministic_ast_closure_v1",
    }
    emitted_source_sha256 = source_sha256
    payload = {
        "schema_version": "scientific_closure_v1",
        "role": role,
        "entry_symbol": entry_symbol,
        "nodes": (node,),
        "dependency_edges": (),
        "emitted_source_sha256": emitted_source_sha256,
        "builder_version": "deterministic_ast_closure_v1",
    }
    return isolation.ScientificClosure(
        "scientific_closure_v1",
        role,
        entry_symbol,
        (node,),
        (),
        emitted_source_sha256,
        canonical_sha256(payload),
    )


def _task5_adapter_closure(seed="canonical"):
    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    return _task5_minimal_scientific_closure(
        definition.entry_symbol, "adapter", seed
    )


def _task5_oracle_closure(seed="canonical"):
    definition = _synthetic_oracle_definition()
    return _task5_minimal_scientific_closure(
        definition.entry_symbol, "oracle", seed
    )


def test_task5_builder_public_signatures_are_exact_and_not_overridable():
    from validation import literature_evidence_isolation as isolation

    assert str(inspect.signature(isolation.build_scientific_closure)) == (
        "(entry_symbol, *, role, source_roots)"
    )
    assert str(
        inspect.signature(isolation.build_scientific_policy_commitment)
    ) == "(definition, closure, *, role)"
    assert str(inspect.signature(isolation.build_infrastructure_closure)) == (
        "(*, source_roots)"
    )

    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    closure = _task5_adapter_closure()
    with pytest.raises(TypeError):
        isolation.build_scientific_policy_commitment(
            definition,
            closure,
            role="adapter",
            static_scan_sha256=_sha256_text("caller-forged-scan"),
        )


def _task5_legacy_structure_scan(commitment, closure):
    return {
        "schema_version": "task5_policy_structure_scan_v1",
        "role": commitment.role,
        "canonical_definition_sha256": (
            commitment.canonical_definition_sha256
        ),
        "entry_closure_sha256": closure.bundle_sha256,
        "checks": {
            "canonical_definition_valid": True,
            "role_and_entry_bound": True,
            "proof_bindings_closed": True,
            "domain_policy_closed": True,
            "size_policy_closed": True,
            "convergence_policy_closed": True,
            "forbidden_structures_absent": True,
        },
    }


def _task5_expected_structure_scan(commitment, closure):
    from validation import literature_evidence_isolation as isolation

    payload = _task5_legacy_structure_scan(commitment, closure)
    payload["schema_version"] = "scientific_definition_policy_scan_v2"
    payload["scanner_version"] = isolation._STATIC_SCANNER_VERSION
    payload["scanner_sha256"] = isolation._STATIC_SCANNER_SHA256
    return payload


def test_policy_builder_binds_canonical_adapter_and_internal_structure_scan():
    from validation import literature_evidence_isolation as isolation

    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    closure = _task5_adapter_closure()

    commitment = isolation.build_scientific_policy_commitment(
        definition, closure, role="adapter"
    )

    assert commitment.role == "adapter"
    assert commitment.definition_id == definition.adapter_id
    assert commitment.entry_closure_sha256 == closure.bundle_sha256
    assert commitment.static_scan_sha256 == canonical_sha256(
        _task5_expected_structure_scan(commitment, closure)
    )
    assert commitment == isolation.ScientificPolicyCommitment(
        **{
            field.name: getattr(commitment, field.name)
            for field in dataclasses.fields(type(commitment))
        }
    )


def test_policy_builder_allows_closed_synthetic_oracle_and_binds_role():
    from validation import literature_evidence_isolation as isolation

    definition = _synthetic_oracle_definition()
    closure = _task5_oracle_closure()

    commitment = isolation.build_scientific_policy_commitment(
        definition, closure, role="oracle"
    )

    assert commitment.definition_id == definition.oracle_id
    assert commitment.eligibility_row_sha256 is None
    assert commitment.eligibility_catalog_sha256 is None
    assert commitment.static_scan_sha256 == canonical_sha256(
        _task5_expected_structure_scan(commitment, closure)
    )
    with pytest.raises(AdapterContractError, match="role|entry"):
        isolation.build_scientific_policy_commitment(
            definition, closure, role="adapter"
        )


def _task5_detached_adapter(mutation):
    canonical = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    values = {
        field.name: getattr(canonical, field.name)
        for field in dataclasses.fields(AdapterDefinition)
    }
    if mutation == "definition":
        identity = thaw_json(canonical.observable_identity)
        identity["conditions"]["rule"] += " and a detached condition"
        values["observable_identity"] = identity
    elif mutation == "domain":
        valid = thaw_json(canonical.counterfactual_domain.valid_rules)
        valid["additional_probe_count"] = 5
        values["counterfactual_domain"] = CounterfactualDomain(
            valid, canonical.counterfactual_domain.invalid_rules
        )
    elif mutation == "size":
        values["problem_size_policy"] = ProblemSizePolicy(
            "fixed_local", {"sites": 2}, {}
        )
    elif mutation == "convergence":
        requirements = thaw_json(
            canonical.convergence_contract.requirements
        )
        requirements["bound_rule"] += " under two detached checks"
        values["convergence_contract"] = ConvergenceContract(
            canonical.convergence_contract.kind, requirements
        )
    elif mutation == "proof":
        selector, binding = canonical.output_schema.fields[0]
        values["output_schema"] = adapters.OutputSchema(
            (
                (
                    selector,
                    adapters.OutputFieldBinding(
                        binding.value_schema,
                        "alternate_local_value",
                        binding.proof_kind,
                    ),
                ),
            )
        )
    elif mutation == "runtime":
        runtime = canonical.runtime_requirements
        values["runtime_requirements"] = RuntimeRequirements(
            runtime.interpreter,
            runtime.packages + ("numpy",),
            runtime.native_libraries,
            runtime.backend_resources,
        )
    elif mutation == "resource":
        limits = canonical.resource_limits
        values["resource_limits"] = ResourceLimits(
            limits.cpu_seconds + 1,
            limits.wall_seconds,
            limits.address_space_bytes,
            limits.output_bytes,
            limits.file_descriptors,
            limits.process_count,
        )
    else:
        values["oracle_id"] = "detached_oracle_id"
    return AdapterDefinition(**values)


@pytest.mark.parametrize(
    "mutation",
    (
        "definition",
        "domain",
        "size",
        "convergence",
        "proof",
        "runtime",
        "resource",
        "oracle_id",
    ),
)
def test_policy_builder_rejects_each_detached_adapter_commitment(mutation):
    from validation import literature_evidence_isolation as isolation

    with pytest.raises(AdapterContractError, match="canonical|catalog"):
        isolation.build_scientific_policy_commitment(
            _task5_detached_adapter(mutation),
            _task5_adapter_closure(),
            role="adapter",
        )


def _task5_mutated_oracle(mutation):
    from validation import literature_evidence_adapter_oracles as oracles

    canonical = _synthetic_oracle_definition()
    values = {
        field.name: getattr(canonical, field.name)
        for field in dataclasses.fields(type(canonical))
    }
    if mutation == "runtime":
        runtime = canonical.runtime_requirements
        values["runtime_requirements"] = RuntimeRequirements(
            runtime.interpreter,
            runtime.packages + ("scipy",),
            runtime.native_libraries,
            runtime.backend_resources,
        )
    elif mutation == "resource":
        limits = canonical.resource_limits
        values["resource_limits"] = ResourceLimits(
            limits.cpu_seconds + 1,
            limits.wall_seconds,
            limits.address_space_bytes,
            limits.output_bytes,
            limits.file_descriptors,
            limits.process_count,
        )
    elif mutation == "convergence":
        contract = thaw_json(canonical.convergence_invariant_contract)
        contract["secondary_bound"] = 1e-12
        values["convergence_invariant_contract"] = contract
    else:
        values["result_schema"] = ValueSchema(
            "object",
            True,
            None,
            None,
            None,
            canonical.result_schema.properties
            + (("secondary_residual", _number_schema(lower=0.0)),),
            "",
        )
    return oracles.OracleDefinition(**values)


@pytest.mark.parametrize(
    "mutation", ("runtime", "resource", "convergence", "proof")
)
def test_policy_builder_commits_each_synthetic_oracle_change(mutation):
    from validation import literature_evidence_isolation as isolation

    closure = _task5_oracle_closure()
    canonical = isolation.build_scientific_policy_commitment(
        _synthetic_oracle_definition(), closure, role="oracle"
    )
    changed = isolation.build_scientific_policy_commitment(
        _task5_mutated_oracle(mutation), closure, role="oracle"
    )

    assert changed.canonical_definition_sha256 != (
        canonical.canonical_definition_sha256
    )
    assert changed.static_scan_sha256 != canonical.static_scan_sha256
    assert changed.combined_sha256 != canonical.combined_sha256


def test_policy_builder_commits_entry_closure_changes():
    from validation import literature_evidence_isolation as isolation

    definition = _synthetic_oracle_definition()
    first = isolation.build_scientific_policy_commitment(
        definition, _task5_oracle_closure("first"), role="oracle"
    )
    second = isolation.build_scientific_policy_commitment(
        definition, _task5_oracle_closure("second"), role="oracle"
    )

    assert first.entry_closure_sha256 != second.entry_closure_sha256
    assert first.static_scan_sha256 != second.static_scan_sha256
    assert first.combined_sha256 != second.combined_sha256


TASK5_FORBIDDEN_POLICY_STRUCTURES = (
    ("fingerprints", {"fingerprints": ("a" * 64,)}),
    ("lookup", {"lookup_table": {"probe": 1.25}}),
    ("categorical", {"categorical_label": "ordered_phase"}),
    ("expression", {"derivation": "lambda value: value + 1"}),
    (
        "adapter_id_branch",
        {"adapter_id_branch": {"synthetic_adapter": "alternate"}},
    ),
)


@pytest.mark.parametrize(
    "case_name, forbidden_contract",
    TASK5_FORBIDDEN_POLICY_STRUCTURES,
    ids=tuple(case[0] for case in TASK5_FORBIDDEN_POLICY_STRUCTURES),
)
def test_policy_builder_rejects_each_forbidden_definition_structure(
    case_name,
    forbidden_contract,
):
    from validation import literature_evidence_adapter_oracles as oracles
    from validation import literature_evidence_isolation as isolation

    del case_name
    canonical = _synthetic_oracle_definition()
    values = {
        field.name: getattr(canonical, field.name)
        for field in dataclasses.fields(type(canonical))
    }
    values["convergence_invariant_contract"] = forbidden_contract
    definition = oracles.OracleDefinition(**values)

    with pytest.raises(
        AdapterContractError,
        match="policy|forbidden|fingerprint|lookup|categorical|expression|branch",
    ):
        isolation.build_scientific_policy_commitment(
            definition, _task5_oracle_closure(), role="oracle"
        )


def test_policy_builder_rejects_target_fingerprint_and_unknown_proof_kind():
    from validation import literature_evidence_adapter_oracles as oracles
    from validation import literature_evidence_isolation as isolation

    oracle = _synthetic_oracle_definition()
    values = {
        field.name: getattr(oracle, field.name)
        for field in dataclasses.fields(type(oracle))
    }
    values["convergence_invariant_contract"] = {
        "target_fingerprints": ("a" * 64,)
    }
    with pytest.raises(AdapterContractError, match="forbidden"):
        oracles.OracleDefinition(**values)

    payload = adapters.adapter_definition_to_frozen_json(
        adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    )
    detached = adapters.adapter_definition_from_frozen_json(payload)
    binding = detached.output_schema.fields[0][1]
    object.__setattr__(binding, "proof_kind", "caller_expression")
    with pytest.raises(AdapterContractError, match="proof|approved"):
        isolation.build_scientific_policy_commitment(
            detached, _task5_adapter_closure(), role="adapter"
        )


def test_policy_builder_rejects_nonrecord_encoding_and_entry_mismatch():
    from validation import literature_evidence_isolation as isolation

    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    with pytest.raises(AdapterContractError, match="definition|exact"):
        isolation.build_scientific_policy_commitment(
            canonical_json_bytes(
                adapters.adapter_definition_to_frozen_json(definition)
            ),
            _task5_adapter_closure(),
            role="adapter",
        )
    mismatched = _task5_minimal_scientific_closure(
        "validation.synthetic:adapter_other", "adapter", "mismatch"
    )
    with pytest.raises(AdapterContractError, match="entry|closure"):
        isolation.build_scientific_policy_commitment(
            definition, mismatched, role="adapter"
        )


def test_scientific_closure_rejects_symlink_escape_from_source_root(tmp_path):
    from validation import literature_evidence_isolation as isolation

    source_root = tmp_path / "source-root"
    module_parent = source_root / "synthetic_science"
    module_parent.mkdir(parents=True)
    outside_source = tmp_path / "outside-adapters.py"
    with outside_source.open("xb") as stream:
        stream.write(
            b"def adapter_entry(value):\n    return value + 1\n"
        )
    (module_parent / "adapters.py").symlink_to(outside_source)

    with pytest.raises(AdapterContractError, match="symlink|escape|root"):
        isolation.build_scientific_closure(
            "synthetic_science.adapters:adapter_entry",
            role="adapter",
            source_roots=(source_root,),
        )


def test_scientific_closure_rejects_symlinked_source_root(tmp_path):
    from validation import literature_evidence_isolation as isolation

    real_root = tmp_path / "real-root"
    _write_task5_source(
        real_root,
        "synthetic_science.adapters",
        "def adapter_entry(value):\n    return value + 1\n",
    )
    linked_root = tmp_path / "linked-root"
    linked_root.symlink_to(real_root, target_is_directory=True)

    with pytest.raises(AdapterContractError, match="symlink|root"):
        isolation.build_scientific_closure(
            "synthetic_science.adapters:adapter_entry",
            role="adapter",
            source_roots=(linked_root,),
        )


def test_scientific_closure_rejects_symlinked_intermediate_directory(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    source_root = tmp_path / "source-root"
    real_package = source_root / "real-package"
    _write_task5_source(
        real_package,
        "adapters",
        "def adapter_entry(value):\n    return value + 1\n",
    )
    synthetic_package = source_root / "synthetic_science"
    synthetic_package.symlink_to(real_package, target_is_directory=True)

    with pytest.raises(AdapterContractError, match="symlink|root"):
        isolation.build_scientific_closure(
            "synthetic_science.adapters:adapter_entry",
            role="adapter",
            source_roots=(source_root,),
        )


def test_scientific_closure_rejects_ambiguous_duplicate_module_roots(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    first_root = tmp_path / "first-root"
    second_root = tmp_path / "second-root"
    source = "def adapter_entry(value):\n    return value + 1\n"
    _write_task5_source(
        first_root, "synthetic_science.adapters", source
    )
    _write_task5_source(
        second_root, "synthetic_science.adapters", source
    )

    with pytest.raises(AdapterContractError, match="ambiguous|duplicate"):
        isolation.build_scientific_closure(
            "synthetic_science.adapters:adapter_entry",
            role="adapter",
            source_roots=(first_root, second_root),
        )


def test_scientific_closure_rejects_entry_path_traversal(tmp_path):
    from validation import literature_evidence_isolation as isolation

    with pytest.raises(AdapterContractError, match="entry_symbol|qualified"):
        isolation.build_scientific_closure(
            "synthetic_science..adapters:adapter_entry",
            role="adapter",
            source_roots=(tmp_path,),
        )


@pytest.mark.parametrize(
    "mutation",
    ("bundle", "raw_hash", "emitted_hash", "edge", "path_traversal"),
)
def test_scientific_policy_rejects_each_tampered_closure_record(mutation):
    from validation import literature_evidence_isolation as isolation

    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    closure = _task5_adapter_closure("record-integrity")
    nodes = [dict(node.items()) for node in closure.nodes]
    edges = closure.dependency_edges
    bundle_sha256 = closure.bundle_sha256
    if mutation == "bundle":
        bundle_sha256 = _sha256_text("forged-closure-bundle")
    elif mutation == "raw_hash":
        nodes[0]["raw_file_sha256"] = _sha256_text("forged-raw-file")
    elif mutation == "emitted_hash":
        nodes[0]["emitted_node_sha256"] = _sha256_text(
            "forged-emitted-node"
        )
    elif mutation == "edge":
        edge = (nodes[0]["qualified_name"], "validation.dynamic.ghost")
        nodes[0]["dependency_edges"] = (edge,)
        edges = (edge,)
    else:
        nodes[0]["relative_path"] = "../outside.py"
    tampered = isolation.ScientificClosure(
        closure.schema_version,
        closure.role,
        closure.entry_symbol,
        tuple(nodes),
        edges,
        closure.emitted_source_sha256,
        bundle_sha256,
    )

    with pytest.raises(AdapterContractError, match="closure|bundle|path"):
        isolation.build_scientific_policy_commitment(
            definition, tampered, role="adapter"
        )


def _task5_rehashed_scientific_closure(
    closure,
    nodes,
    *,
    emitted_source_sha256=None,
):
    from validation import literature_evidence_isolation as isolation

    nodes = tuple(nodes)
    if emitted_source_sha256 is None:
        emitted_source_sha256 = closure.emitted_source_sha256
    edges = tuple(
        edge for node in nodes for edge in node["dependency_edges"]
    )
    payload = {
        "schema_version": closure.schema_version,
        "role": closure.role,
        "entry_symbol": closure.entry_symbol,
        "nodes": nodes,
        "dependency_edges": edges,
        "emitted_source_sha256": emitted_source_sha256,
        "builder_version": "deterministic_ast_closure_v1",
    }
    return isolation.ScientificClosure(
        closure.schema_version,
        closure.role,
        closure.entry_symbol,
        nodes,
        edges,
        emitted_source_sha256,
        canonical_sha256(payload),
    )


@pytest.mark.parametrize(
    "mutation",
    ("node_order", "edge_destination", "edge_order", "path_module", "raw_hash"),
)
def test_scientific_policy_rejects_rehashed_structural_closure_tampering(
    tmp_path,
    mutation,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_source(
        tmp_path,
        "validation.literature_evidence_adapters",
        _task5_pure_scientific_source().replace(
            "adapter_entry", "adapter_square_ising_self_dual_tc"
        ),
    )
    closure = isolation.build_scientific_closure(
        (
            "validation.literature_evidence_adapters:"
            "adapter_square_ising_self_dual_tc"
        ),
        role="adapter",
        source_roots=(tmp_path,),
    )
    nodes = [dict(node.items()) for node in closure.nodes]
    if mutation == "node_order":
        nodes.reverse()
    elif mutation == "edge_destination":
        node = next(item for item in nodes if item["dependency_edges"])
        source, _destination = node["dependency_edges"][0]
        node["dependency_edges"] = (
            (source, "validation.uncommitted.ghost"),
            *node["dependency_edges"][1:],
        )
    elif mutation == "edge_order":
        node = next(
            item for item in nodes if len(item["dependency_edges"]) > 1
        )
        node["dependency_edges"] = tuple(
            reversed(node["dependency_edges"])
        )
    elif mutation == "path_module":
        nodes[0]["relative_path"] = "validation/wrong_module.py"
    else:
        nodes[1]["raw_file_sha256"] = _sha256_text(
            "coherently-rehashed-raw-file"
        )
    tampered = _task5_rehashed_scientific_closure(closure, nodes)
    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]

    with pytest.raises(AdapterContractError, match="closure|node|edge|path|file"):
        isolation.build_scientific_policy_commitment(
            definition, tampered, role="adapter"
        )


@pytest.mark.parametrize(
    "mutation",
    ("roots", "purpose", "bundle", "node_hash", "committed_edge"),
)
def test_dependency_partition_rejects_each_tampered_infrastructure_record(
    tmp_path,
    mutation,
):
    from validation import literature_evidence_isolation as isolation

    fixture = _task5_partition_fixture(tmp_path)
    infrastructure = fixture[4]
    roots = infrastructure.roots
    nodes = [dict(node.items()) for node in infrastructure.nodes]
    edges = infrastructure.dependency_edges
    purposes = dict(infrastructure.purpose_bindings.items())
    bundle_sha256 = infrastructure.bundle_sha256
    if mutation == "roots":
        roots = roots[:-1]
    elif mutation == "purpose":
        purposes[roots[0]] = "caller_defined_purpose"
    elif mutation == "bundle":
        bundle_sha256 = _sha256_text("forged-infrastructure-bundle")
    elif mutation == "node_hash":
        nodes[0]["source_span_sha256"] = _sha256_text(
            "forged-infrastructure-node"
        )
    else:
        edges = tuple(
            edge
            for edge in edges
            if not edge[1].startswith("committed_data:")
        )
        for node in nodes:
            node["dependency_edges"] = tuple(
                edge
                for edge in node["dependency_edges"]
                if not edge[1].startswith("committed_data:")
            )
    tampered = isolation.InfrastructureClosure(
        infrastructure.schema_version,
        roots,
        tuple(nodes),
        edges,
        purposes,
        bundle_sha256,
    )
    tampered_fixture = (*fixture[:4], tampered, fixture[5])

    with pytest.raises(AdapterContractError):
        _assert_task5_partition(tampered_fixture, fixture[5])


def _task5_rehashed_infrastructure_closure(infrastructure, nodes, roots=None):
    from validation import literature_evidence_isolation as isolation

    nodes = tuple(nodes)
    edges = tuple(
        edge for node in nodes for edge in node["dependency_edges"]
    )
    if roots is None:
        roots = infrastructure.roots
    payload = {
        "schema_version": infrastructure.schema_version,
        "roots": roots,
        "nodes": nodes,
        "dependency_edges": edges,
        "purpose_bindings": infrastructure.purpose_bindings,
        "builder_version": "deterministic_ast_closure_v1",
    }
    return isolation.InfrastructureClosure(
        infrastructure.schema_version,
        roots,
        nodes,
        edges,
        infrastructure.purpose_bindings,
        canonical_sha256(payload),
    )


@pytest.mark.parametrize(
    "mutation",
    ("node_order", "edge_destination", "path_module", "raw_hash", "root_order"),
)
def test_dependency_partition_rejects_rehashed_infrastructure_tampering(
    tmp_path,
    mutation,
):
    fixture = _task5_partition_fixture(tmp_path)
    infrastructure = fixture[4]
    nodes = [dict(node.items()) for node in infrastructure.nodes]
    roots = infrastructure.roots
    if mutation == "node_order":
        nodes.reverse()
    elif mutation == "edge_destination":
        node = next(item for item in nodes if item["dependency_edges"])
        source, _destination = node["dependency_edges"][0]
        node["dependency_edges"] = (
            (source, "validation.uncommitted.ghost"),
            *node["dependency_edges"][1:],
        )
    elif mutation == "path_module":
        nodes[0]["relative_path"] = "validation/wrong_module.py"
    elif mutation == "raw_hash":
        path = nodes[0]["relative_path"]
        same_file = [
            node for node in nodes if node["relative_path"] == path
        ]
        assert len(same_file) > 1
        same_file[0]["raw_file_sha256"] = _sha256_text(
            "coherently-rehashed-infrastructure-file"
        )
    else:
        roots = tuple(reversed(roots))
    tampered = _task5_rehashed_infrastructure_closure(
        infrastructure, nodes, roots
    )
    tampered_fixture = (*fixture[:4], tampered, fixture[5])

    with pytest.raises(AdapterContractError, match="infrastructure|node|edge|path|file|root"):
        _assert_task5_partition(tampered_fixture, fixture[5])


def test_dependency_partition_rejects_rehashed_committed_data_source_rebinding(
    tmp_path,
):
    fixture = _task5_partition_fixture(tmp_path)
    infrastructure = fixture[4]
    nodes = [dict(node.items()) for node in infrastructure.nodes]
    committed_edges = tuple(
        edge
        for edge in infrastructure.dependency_edges
        if edge[1].startswith("committed_data:")
    )
    original_source = committed_edges[0][0]
    original_node = next(
        node for node in nodes if node["qualified_name"] == original_source
    )
    original_node["dependency_edges"] = tuple(
        edge
        for edge in original_node["dependency_edges"]
        if not edge[1].startswith("committed_data:")
    )
    rebound_node = next(
        node
        for node in nodes
        if node["node_kind"] == "function"
        and node["qualified_name"] != original_source
    )
    rebound_source = rebound_node["qualified_name"]
    rebound_node["dependency_edges"] = tuple(
        sorted(
            rebound_node["dependency_edges"]
            + tuple(
                (rebound_source, destination)
                for _source, destination in committed_edges
            )
        )
    )
    tampered = _task5_rehashed_infrastructure_closure(
        infrastructure, nodes
    )
    tampered_fixture = (*fixture[:4], tampered, fixture[5])

    with pytest.raises(AdapterContractError, match="committed|data|edge|source"):
        _assert_task5_partition(tampered_fixture, fixture[5])


def _task5_synthetic_manifest_node(
    qualified_name,
    *,
    node_kind="function",
    seed="synthetic-node",
    dependency_edges=(),
):
    source_bytes = (
        f"{qualified_name}:{node_kind}:{seed}\n"
    ).encode("utf-8")
    node_sha256 = hashlib.sha256(source_bytes).hexdigest()
    module_name = qualified_name.rsplit(".", 1)[0]
    return {
        "relative_path": module_name.replace(".", "/") + ".py",
        "raw_file_sha256": node_sha256,
        "node_kind": node_kind,
        "qualified_name": qualified_name,
        "source_span_sha256": node_sha256,
        "emitted_node_sha256": node_sha256,
        "dependency_edges": tuple(dependency_edges),
        "scanner_version": "deterministic_ast_closure_v1",
    }


def _task5_canonical_manifest_order(nodes):
    by_name = {node["qualified_name"]: node for node in nodes}
    assert len(by_name) == len(nodes)
    priority = {
        "import": 0,
        "immutable_constant": 1,
        "class": 2,
        "function": 3,
    }
    pending = set(by_name)
    ordered = []
    while pending:
        ready = [
            by_name[name]
            for name in pending
            if not {
                destination
                for _source, destination in by_name[name][
                    "dependency_edges"
                ]
                if destination in by_name
            }
            & pending
        ]
        assert ready
        ready.sort(
            key=lambda node: (
                priority[node["node_kind"]],
                node["qualified_name"],
            )
        )
        for node in ready:
            ordered.append(node)
            pending.remove(node["qualified_name"])
    return tuple(ordered)


@pytest.mark.parametrize(
    "detached_module",
    (
        "validation.detached_adapters",
        "validation.detached_oracles",
    ),
    ids=("same_role", "opposite_role"),
)
def test_partition_rejects_rehashed_disconnected_scientific_node(
    tmp_path,
    detached_module,
):
    from validation import literature_evidence_isolation as isolation

    fixture = _task5_partition_fixture(tmp_path)
    adapter = fixture[0]
    detached_name = f"{detached_module}.detached_helper"
    detached = _task5_synthetic_manifest_node(
        detached_name,
        seed=detached_module,
    )
    nodes = _task5_canonical_manifest_order(
        tuple(dict(node.items()) for node in adapter.nodes) + (detached,)
    )
    tampered = _task5_rehashed_scientific_closure(
        adapter,
        nodes,
        emitted_source_sha256=_sha256_text(
            f"emitted:{detached_module}"
        ),
    )
    definition = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]

    with pytest.raises(
        AdapterContractError, match="closure|reachable|role|disconnected"
    ):
        policy = isolation.build_scientific_policy_commitment(
            definition, tampered, role="adapter"
        )
        tampered_fixture = (
            tampered,
            policy,
            *fixture[2:5],
            tuple(sorted(fixture[5] + (detached_name,))),
        )
        _assert_task5_partition(tampered_fixture, tampered_fixture[5])


def test_partition_rejects_rehashed_disconnected_infrastructure_formula_node(
    tmp_path,
):
    fixture = _task5_partition_fixture(tmp_path)
    infrastructure = fixture[4]
    detached_name = "validation.detached_transport.derive_formula_result"
    detached = _task5_synthetic_manifest_node(
        detached_name,
        seed="scientific-formula-result",
    )
    nodes = _task5_canonical_manifest_order(
        tuple(dict(node.items()) for node in infrastructure.nodes)
        + (detached,)
    )
    tampered = _task5_rehashed_infrastructure_closure(
        infrastructure, nodes
    )
    referenced = tuple(sorted(fixture[5] + (detached_name,)))
    tampered_fixture = (*fixture[:4], tampered, referenced)

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|reachable|formula|result|disconnected",
    ):
        _assert_task5_partition(tampered_fixture, referenced)


@pytest.mark.parametrize("entry_kind", ("immutable_constant", "class"))
def test_fresh_scientific_validator_requires_function_entry(
    entry_kind,
):
    from validation import literature_evidence_isolation as isolation

    closure = _task5_adapter_closure(f"fresh-{entry_kind}")
    nodes = [dict(node.items()) for node in closure.nodes]
    nodes[0]["node_kind"] = entry_kind
    nodes = _task5_canonical_manifest_order(nodes)
    tampered = _task5_rehashed_scientific_closure(closure, nodes)

    with pytest.raises(AdapterContractError, match="entry|function|kind"):
        isolation.build_scientific_policy_commitment(
            adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"],
            tampered,
            role="adapter",
        )


def test_fresh_infrastructure_validator_requires_function_roots(tmp_path):
    fixture = _task5_partition_fixture(tmp_path)
    infrastructure = fixture[4]
    root_name = infrastructure.roots[0]
    nodes = [dict(node.items()) for node in infrastructure.nodes]
    root_node = next(
        node for node in nodes if node["qualified_name"] == root_name
    )
    root_node["node_kind"] = "immutable_constant"
    nodes = _task5_canonical_manifest_order(nodes)
    tampered = _task5_rehashed_infrastructure_closure(
        infrastructure, nodes
    )
    tampered_fixture = (*fixture[:4], tampered, fixture[5])

    with pytest.raises(AdapterContractError, match="root|function|kind"):
        _assert_task5_partition(tampered_fixture, fixture[5])


@pytest.mark.parametrize(
    "entry_source",
    (
        "adapter_entry = 1\n",
        "class adapter_entry:\n    pass\n",
    ),
    ids=("constant", "class"),
)
def test_scientific_builder_requires_function_entry(tmp_path, entry_source):
    _write_task5_source(
        tmp_path, "synthetic_science.adapters", entry_source
    )

    with pytest.raises(AdapterContractError, match="entry|function|kind"):
        _build_task5_scientific_closure(tmp_path)


@pytest.mark.parametrize(
    "root_declaration",
    (
        "validate_failure = 1\n",
        "class validate_failure:\n    pass\n",
    ),
    ids=("constant", "class"),
)
def test_infrastructure_builder_requires_function_roots(
    tmp_path,
    root_declaration,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        declaration_by_root={"validate_failure": root_declaration},
    )

    with pytest.raises(AdapterContractError, match="root|function|kind"):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "source",
    (
        "class Meta(type):\n"
        "    pass\n"
        "def adapter_entry(value):\n"
        "    return Meta()\n",
        "class Base:\n"
        "    def __init_subclass__(cls):\n"
        "        return None\n"
        "def adapter_entry(value):\n"
        "    return Base\n",
        "class Descriptor:\n"
        "    def __set_name__(self, owner, name):\n"
        "        return None\n"
        "def adapter_entry(value):\n"
        "    return Descriptor()\n",
        "def make_base():\n"
        "    return object\n"
        "class Computed(make_base()):\n"
        "    pass\n"
        "def adapter_entry(value):\n"
        "    return Computed()\n",
    ),
    ids=(
        "metaclass_definition",
        "init_subclass_hook",
        "set_name_hook",
        "computed_base",
    ),
)
def test_scientific_closure_rejects_definition_time_class_execution(
    tmp_path,
    source,
):
    _write_task5_source(
        tmp_path, "synthetic_science.adapters", source
    )

    with pytest.raises(
        AdapterContractError,
        match="class|base|metaclass|descriptor|hook|definition",
    ):
        _build_task5_scientific_closure(tmp_path)


@pytest.mark.parametrize(
    "class_declaration",
    (
        "class Plain:\n    pass\n",
        "class Plain(object):\n    pass\n",
    ),
    ids=("plain", "object_base"),
)
def test_scientific_closure_allows_plain_nonexecuting_class_control(
    tmp_path,
    class_declaration,
):
    _write_task5_source(
        tmp_path,
        "synthetic_science.adapters",
        class_declaration
        + "def adapter_entry(value):\n"
        + "    return Plain()\n",
    )

    closure = _build_task5_scientific_closure(tmp_path)

    assert {
        node["qualified_name"] for node in closure.nodes
    } == {
        "synthetic_science.adapters.Plain",
        "synthetic_science.adapters.adapter_entry",
    }


def test_scientific_closure_rejects_external_importfrom_piggyback(tmp_path):
    _write_task5_source(
        tmp_path,
        "synthetic_science.adapters",
        "from numpy import sqrt, load\n"
        "def adapter_entry(value):\n"
        "    return sqrt(value)\n",
    )

    with pytest.raises(AdapterContractError, match="import|alias|static"):
        _build_task5_scientific_closure(tmp_path)


def test_scientific_closure_allows_fully_used_external_importfrom(tmp_path):
    source = (
        "from math import sin, cos\n"
        "def adapter_entry(value):\n"
        "    return sin(value) + cos(value)\n"
    )
    _write_task5_source(
        tmp_path,
        "synthetic_science.adapters",
        source,
    )

    closure = _build_task5_scientific_closure(tmp_path)

    import_nodes = tuple(
        node for node in closure.nodes if node["node_kind"] == "import"
    )
    assert len(import_nodes) == 1
    import_node = import_nodes[0]
    assert import_node["emitted_node_sha256"] == hashlib.sha256(
        b"from math import sin, cos\n"
    ).hexdigest()
    entry_name = "synthetic_science.adapters.adapter_entry"
    entry_node = next(
        node
        for node in closure.nodes
        if node["qualified_name"] == entry_name
    )
    assert entry_node["dependency_edges"] == (
        (entry_name, import_node["qualified_name"]),
    )
    emitted_source = (
        b"from math import sin, cos\n\n"
        b"def adapter_entry(value):\n"
        b"    return sin(value) + cos(value)\n"
    )
    assert closure.emitted_source_sha256 == hashlib.sha256(
        emitted_source
    ).hexdigest()


def test_scientific_closure_keeps_project_importfrom_semantics(tmp_path):
    _write_task5_source(
        tmp_path,
        "synthetic_science.helpers",
        "def left(value):\n"
        "    return value + 1\n"
        "def right(value):\n"
        "    return value - 1\n",
    )
    _write_task5_source(
        tmp_path,
        "synthetic_science.adapters",
        "from synthetic_science.helpers import left, right\n"
        "def adapter_entry(value):\n"
        "    return left(value) + right(value)\n",
    )

    closure = _build_task5_scientific_closure(tmp_path)

    node_names = {node["qualified_name"] for node in closure.nodes}
    assert {
        "synthetic_science.helpers.left",
        "synthetic_science.helpers.right",
    } <= node_names
    assert not any(
        node["node_kind"] == "import" for node in closure.nodes
    )


@pytest.mark.parametrize(
    "export_name, expression",
    (
        ("len", "len((value,))"),
        ("tuple", "tuple((value,))"),
        ("object", "object()"),
    ),
    ids=("len", "tuple", "object"),
)
def test_scientific_closure_rejects_missing_project_builtin_export(
    tmp_path,
    export_name,
    expression,
):
    _write_task5_source(
        tmp_path,
        "synthetic_science.helpers",
        "OTHER = 2\n",
    )
    _write_task5_source(
        tmp_path,
        "synthetic_science.adapters",
        f"from synthetic_science.helpers import {export_name}\n"
        "def adapter_entry(value):\n"
        f"    return {expression}\n",
    )

    with pytest.raises(
        AdapterContractError,
        match="binding|dependency|export|import|unresolved",
    ):
        _build_task5_scientific_closure(tmp_path)


def test_scientific_closure_allows_imported_immutable_default(tmp_path):
    _write_task5_source(
        tmp_path,
        "synthetic_science.helpers",
        "BASE = 2\n",
    )
    _write_task5_source(
        tmp_path,
        "synthetic_science.adapters",
        "from synthetic_science.helpers import BASE\n"
        "def adapter_entry(value=BASE):\n"
        "    return value\n",
    )

    closure = _build_task5_scientific_closure(tmp_path)

    assert tuple(
        node["qualified_name"] for node in closure.nodes
    ) == (
        "synthetic_science.helpers.BASE",
        "synthetic_science.adapters.adapter_entry",
    )
    assert closure.dependency_edges == (
        (
            "synthetic_science.adapters.adapter_entry",
            "synthetic_science.helpers.BASE",
        ),
    )


def test_scientific_closure_allows_imported_immutable_initializer(
    tmp_path,
):
    _write_task5_source(
        tmp_path,
        "synthetic_science.helpers",
        "BASE = 2\n",
    )
    _write_task5_source(
        tmp_path,
        "synthetic_science.adapters",
        "from synthetic_science.helpers import BASE\n"
        "SCALE = BASE + 1\n"
        "def adapter_entry(value):\n"
        "    return value * SCALE\n",
    )

    closure = _build_task5_scientific_closure(tmp_path)

    assert tuple(
        node["qualified_name"] for node in closure.nodes
    ) == (
        "synthetic_science.helpers.BASE",
        "synthetic_science.adapters.SCALE",
        "synthetic_science.adapters.adapter_entry",
    )
    assert closure.dependency_edges == (
        (
            "synthetic_science.adapters.SCALE",
            "synthetic_science.helpers.BASE",
        ),
        (
            "synthetic_science.adapters.adapter_entry",
            "synthetic_science.adapters.SCALE",
        ),
    )


def test_scientific_closure_allows_multi_hop_imported_immutable(
    tmp_path,
):
    _write_task5_source(
        tmp_path,
        "synthetic_science.constants",
        "BASE = 2\n",
    )
    _write_task5_source(
        tmp_path,
        "synthetic_science.helpers",
        "from synthetic_science.constants import BASE\n",
    )
    _write_task5_source(
        tmp_path,
        "synthetic_science.adapters",
        "from synthetic_science.helpers import BASE\n"
        "def adapter_entry(value=BASE):\n"
        "    return value + BASE\n",
    )

    closure = _build_task5_scientific_closure(tmp_path)

    assert tuple(
        node["qualified_name"] for node in closure.nodes
    ) == (
        "synthetic_science.constants.BASE",
        "synthetic_science.adapters.adapter_entry",
    )
    assert closure.dependency_edges == (
        (
            "synthetic_science.adapters.adapter_entry",
            "synthetic_science.constants.BASE",
        ),
    )


def test_scientific_closure_rejects_project_import_binding_cycle(
    tmp_path,
):
    _write_task5_source(
        tmp_path,
        "synthetic_science.left",
        "from synthetic_science.right import BASE\n",
    )
    _write_task5_source(
        tmp_path,
        "synthetic_science.right",
        "from synthetic_science.left import BASE\n",
    )
    _write_task5_source(
        tmp_path,
        "synthetic_science.adapters",
        "from synthetic_science.left import BASE\n"
        "def adapter_entry(value=BASE):\n"
        "    return value\n",
    )

    with pytest.raises(AdapterContractError, match="cycle|cyclic"):
        _build_task5_scientific_closure(tmp_path)


@pytest.mark.parametrize(
    "helper_source, imported_name",
    (
        (
            "def helper(value):\n"
            "    return value\n",
            "helper",
        ),
        (
            "class Payload:\n"
            "    pass\n",
            "Payload",
        ),
        ("from math import sqrt\n", "sqrt"),
    ),
    ids=("function", "class", "external_import"),
)
def test_scientific_closure_rejects_imported_runtime_binding_as_default(
    tmp_path,
    helper_source,
    imported_name,
):
    _write_task5_source(
        tmp_path,
        "synthetic_science.helpers",
        helper_source,
    )
    _write_task5_source(
        tmp_path,
        "synthetic_science.adapters",
        f"from synthetic_science.helpers import {imported_name}\n"
        f"def adapter_entry(value={imported_name}):\n"
        "    return value\n",
    )

    with pytest.raises(
        AdapterContractError,
        match="binding|callable|class|immutable|import|runtime",
    ):
        _build_task5_scientific_closure(tmp_path)


def test_scientific_closure_allows_runtime_imported_project_function(
    tmp_path,
):
    _write_task5_source(
        tmp_path,
        "synthetic_science.helpers",
        "def helper(value):\n"
        "    return value + 1\n",
    )
    _write_task5_source(
        tmp_path,
        "synthetic_science.adapters",
        "from synthetic_science.helpers import helper\n"
        "def adapter_entry(value):\n"
        "    return helper(value)\n",
    )

    closure = _build_task5_scientific_closure(tmp_path)

    assert {
        node["qualified_name"] for node in closure.nodes
    } == {
        "synthetic_science.helpers.helper",
        "synthetic_science.adapters.adapter_entry",
    }
    assert closure.dependency_edges == (
        (
            "synthetic_science.adapters.adapter_entry",
            "synthetic_science.helpers.helper",
        ),
    )


def test_scientific_closure_rejects_aliased_project_import(tmp_path):
    _write_task5_source(
        tmp_path,
        "synthetic_science.helpers",
        "def helper(value):\n"
        "    return value\n",
    )
    _write_task5_source(
        tmp_path,
        "synthetic_science.adapters",
        "from synthetic_science.helpers import helper as renamed\n"
        "def adapter_entry(value):\n"
        "    return renamed(value)\n",
    )

    with pytest.raises(AdapterContractError, match="alias|import|static"):
        _build_task5_scientific_closure(tmp_path)


def test_scientific_closure_rejects_missing_project_annotation_export(
    tmp_path,
):
    _write_task5_source(
        tmp_path,
        "synthetic_science.helpers",
        "OTHER = 2\n",
    )
    _write_task5_source(
        tmp_path,
        "synthetic_science.adapters",
        "from synthetic_science.helpers import int\n"
        "def adapter_entry(value: int):\n"
        "    return value\n",
    )

    with pytest.raises(
        AdapterContractError,
        match="annotation|binding|dependency|export|import|unresolved",
    ):
        _build_task5_scientific_closure(tmp_path)


TASK5_FORBIDDEN_INFRASTRUCTURE_CONTENT = (
    (
        "neutral_numeric_equation",
        "    return value * 1.23456789\n",
    ),
    (
        "neutral_numeric_constant",
        "    coefficient = 0.3141592653589793\n"
        "    return coefficient\n",
    ),
    (
        "scientific_equation",
        "    scientific_constant = 2.0\n"
        "    return value ** scientific_constant\n",
    ),
    (
        "hamiltonian_builder",
        "    hamiltonian_builder = value\n"
        "    return hamiltonian_builder\n",
    ),
    (
        "method_result_derivation",
        "    method_specific_result = value\n"
        "    return method_specific_result\n",
    ),
    (
        "adapter_definition",
        '    definition_type = "AdapterDefinition"\n'
        "    return definition_type\n",
    ),
    (
        "oracle_definition",
        '    definition_type = "OracleDefinition"\n'
        "    return definition_type\n",
    ),
    (
        "policy_bytes",
        '    canonical_policy_bytes = b"detached-policy"\n'
        "    return canonical_policy_bytes\n",
    ),
)


@pytest.mark.parametrize(
    "case_name, root_body",
    TASK5_FORBIDDEN_INFRASTRUCTURE_CONTENT,
    ids=tuple(case[0] for case in TASK5_FORBIDDEN_INFRASTRUCTURE_CONTENT),
)
def test_infrastructure_builder_rejects_forbidden_neutral_root_ast_content(
    tmp_path,
    case_name,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={"validate_failure": root_body},
    )

    with pytest.raises(
        AdapterContractError,
        match=(
            "infrastructure|scientific|equation|Hamiltonian|result|"
            "definition|policy"
        ),
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


TASK5_EQUIVALENT_SCIENTIFIC_INFRASTRUCTURE_CONTENT = (
    (
        "integer_scientific_constant",
        "    scientific_constant = 2\n"
        "    return scientific_constant\n",
    ),
    (
        "integer_power_equation",
        "    return value ** 2\n",
    ),
    (
        "conditional_integer_energy",
        "    energy = 2 if value is None else value\n"
        "    return energy\n",
    ),
    (
        "augmented_integer_energy",
        "    energy = value\n"
        "    energy += 2\n"
        "    return energy\n",
    ),
    (
        "tuple_unpacked_integer_energy",
        "    (energy,) = (2,)\n"
        "    return energy\n",
    ),
    (
        "boolean_integer_energy",
        "    energy = 2 or value\n"
        "    return energy\n",
    ),
    (
        "annotated_integer_energy_alias",
        "    coefficient: int = 2\n"
        "    energy = coefficient\n"
        "    return energy\n",
    ),
    (
        "integer_energy_constant",
        "    energy = 2\n"
        "    return energy\n",
    ),
    (
        "integer_scientific_coefficient",
        "    scientific_coefficient = 2\n"
        "    return scientific_coefficient\n",
    ),
    (
        "aliased_integer_energy_constant",
        "    energy = coefficient\n"
        "    coefficient = 2\n"
        "    return energy\n",
    ),
    (
        "compute_method_result",
        "    compute_method_result = value\n"
        "    return compute_method_result\n",
    ),
    (
        "computed_method_result",
        "    computed_method_result = value\n"
        "    return computed_method_result\n",
    ),
    (
        "computing_method_result",
        "    computing_method_result = value\n"
        "    return computing_method_result\n",
    ),
    (
        "derive_method_result",
        "    derive_method_result = value\n"
        "    return derive_method_result\n",
    ),
    (
        "derived_method_result",
        "    derived_method_result = value\n"
        "    return derived_method_result\n",
    ),
    (
        "deriving_method_result",
        "    deriving_method_result = value\n"
        "    return deriving_method_result\n",
    ),
    (
        "calculate_method_result",
        "    calculate_method_result = value\n"
        "    return calculate_method_result\n",
    ),
    (
        "calculated_method_result",
        "    calculated_method_result = value\n"
        "    return calculated_method_result\n",
    ),
    (
        "calculating_method_result",
        "    calculating_method_result = value\n"
        "    return calculating_method_result\n",
    ),
    (
        "evaluate_method_result",
        "    evaluate_method_result = value\n"
        "    return evaluate_method_result\n",
    ),
    (
        "evaluated_method_result",
        "    evaluated_method_result = value\n"
        "    return evaluated_method_result\n",
    ),
    (
        "evaluating_method_result",
        "    evaluating_method_result = value\n"
        "    return evaluating_method_result\n",
    ),
    (
        "computes_method_result",
        "    computes_method_result = value\n"
        "    return computes_method_result\n",
    ),
    (
        "derives_method_result",
        "    derives_method_result = value\n"
        "    return derives_method_result\n",
    ),
    (
        "calculates_method_result",
        "    calculates_method_result = value\n"
        "    return calculates_method_result\n",
    ),
    (
        "evaluates_method_result",
        "    evaluates_method_result = value\n"
        "    return evaluates_method_result\n",
    ),
    (
        "method_result_computation",
        "    method_result_computation = value\n"
        "    return method_result_computation\n",
    ),
    (
        "method_result_derivation",
        "    method_result_derivation = value\n"
        "    return method_result_derivation\n",
    ),
    (
        "method_result_calculation",
        "    method_result_calculation = value\n"
        "    return method_result_calculation\n",
    ),
    (
        "method_result_evaluation",
        "    method_result_evaluation = value\n"
        "    return method_result_evaluation\n",
    ),
    (
        "method_result_computations",
        "    method_result_computations = value\n"
        "    return method_result_computations\n",
    ),
    (
        "method_result_derivations",
        "    method_result_derivations = value\n"
        "    return method_result_derivations\n",
    ),
    (
        "method_result_calculations",
        "    method_result_calculations = value\n"
        "    return method_result_calculations\n",
    ),
    (
        "method_result_evaluations",
        "    method_result_evaluations = value\n"
        "    return method_result_evaluations\n",
    ),
    (
        "model_arithmetic",
        "    model = value + 1\n"
        "    return model\n",
    ),
    (
        "scientific_value_arithmetic",
        "    scientific_value = value + 1\n"
        "    return scientific_value\n",
    ),
    (
        "observable_arithmetic",
        "    observable = value + 1\n"
        "    return observable\n",
    ),
    (
        "annotated_model_arithmetic",
        "    model: object = value + len(value)\n"
        "    return model\n",
    ),
    (
        "named_model_arithmetic",
        "    return (model := value + len(value))\n",
    ),
    (
        "unpacked_model_arithmetic",
        "    (model,) = (value + len(value),)\n"
        "    return model\n",
    ),
    (
        "augmented_model_arithmetic",
        "    model = value\n"
        "    model += len(value)\n"
        "    return model\n",
    ),
    (
        "augmented_power_equation",
        "    bounded_size = len(value)\n"
        "    bounded_size **= value\n"
        "    return bounded_size\n",
    ),
    (
        "call_argument_integer_energy",
        "    energy = max(value, 2)\n"
        "    return energy\n",
    ),
    (
        "set_container_integer_energy",
        "    energy = {value, 2}\n"
        "    return energy\n",
    ),
    (
        "dict_container_integer_energy",
        '    energy = {"transport": value, "fallback": 2}\n'
        "    return energy\n",
    ),
    (
        "subscripted_integer_energy",
        "    coefficients = (2,)\n"
        "    energy = coefficients[0]\n"
        "    return energy\n",
    ),
    (
        "split_bound_numeric_method",
        "    method = (2).__int__\n"
        "    energy = method()\n"
        "    return energy\n",
    ),
    (
        "direct_numeric_attribute",
        "    energy = (2).real\n"
        "    return energy\n",
    ),
    (
        "subscripted_bound_numeric_method",
        "    methods = ((2).__int__,)\n"
        "    energy = methods[0]()\n"
        "    return energy\n",
    ),
)


@pytest.mark.parametrize(
    "case_name, root_body",
    TASK5_EQUIVALENT_SCIENTIFIC_INFRASTRUCTURE_CONTENT,
    ids=tuple(
        case[0]
        for case in TASK5_EQUIVALENT_SCIENTIFIC_INFRASTRUCTURE_CONTENT
    ),
)
def test_infrastructure_builder_rejects_equivalent_scientific_ast_content(
    tmp_path,
    case_name,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={"validate_failure": root_body},
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|scientific|equation|constant|method|result",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


TASK5_PURPOSE_PROVENANCE_REJECTIONS = (
    (
        "neutral_direct_ratio",
        "",
        "    numerator = 1\n"
        "    denominator = 2\n"
        "    return numerator / denominator\n",
    ),
    (
        "neutral_input_factor_alias",
        "",
        "    factor = 2\n"
        "    renamed = factor\n"
        "    return value * renamed\n",
    ),
    (
        "neutral_helper_literal_return",
        "def transform():\n"
        "    left = 1\n"
        "    right = 2\n"
        "    return left / right\n",
        "    return transform()\n",
    ),
    (
        "parameterized_helper_unconstrained_input",
        "def transform(item):\n"
        "    return item + 1\n",
        "    return transform(value)\n",
    ),
    ("tuple_flow", "", "    return (value, 2)\n"),
    ("list_flow", "", "    return [value, 2]\n"),
    ("set_flow", "", "    return {value, 2}\n"),
    (
        "dict_flow",
        "",
        '    return {"primary": value, "fallback": 2}\n',
    ),
    (
        "conditional_flow",
        "",
        "    return 2 if value is None else value\n",
    ),
    ("boolean_flow", "", "    return value or 2\n"),
    (
        "subscripted_container_flow",
        "",
        "    candidates = (2,)\n"
        "    return candidates[0]\n",
    ),
    ("direct_attribute_flow", "", "    return (2).real\n"),
    (
        "split_bound_method_flow",
        "",
        "    operation = (2).__int__\n"
        "    return operation()\n",
    ),
    (
        "subscripted_bound_method_flow",
        "",
        "    operations = ((2).__int__,)\n"
        "    return operations[0]()\n",
    ),
    (
        "general_call_argument_flow",
        "def select(*items):\n"
        "    return items[0]\n",
        "    return select(value, 2)\n",
    ),
    (
        "multi_helper_flow",
        "def first(item):\n"
        "    return item + 1\n"
        "def second(item):\n"
        "    return first(item)\n",
        "    return second(value)\n",
    ),
    (
        "neutral_renaming",
        "def a(b):\n"
        "    c = 2\n"
        "    return b * c\n",
        "    return a(value)\n",
    ),
    (
        "resolved_module_constant_alias",
        "MULTIPLIER = 2\n",
        "    renamed = MULTIPLIER\n"
        "    return value * renamed\n",
    ),
    (
        "imported_len_is_not_builtin",
        "from math import floor as len\n",
        "    return len(value) + 1\n",
    ),
    (
        "helper_numeric_default",
        "def transform(item=2):\n"
        "    return item\n",
        "    return transform()\n",
    ),
    (
        "reachable_class_method",
        "class Transport:\n"
        "    def transform(self, item):\n"
        "        return item * 2\n",
        "    return Transport()\n",
    ),
    (
        "returned_literal_comparison",
        "",
        "    return value < 2\n",
    ),
)


@pytest.mark.parametrize(
    "case_name, helper_source, root_body",
    TASK5_PURPOSE_PROVENANCE_REJECTIONS,
    ids=tuple(case[0] for case in TASK5_PURPOSE_PROVENANCE_REJECTIONS),
)
def test_infrastructure_builder_rejects_numeric_provenance_by_structure(
    tmp_path,
    case_name,
    helper_source,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": helper_source
        },
        body_by_root={"validate_failure": root_body},
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|literal|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


def test_infrastructure_builder_intersects_shared_helper_purposes(tmp_path):
    from validation import literature_evidence_isolation as isolation

    helper_source = (
        "def occurrence_total(items):\n"
        "    total = 0\n"
        "    for item in items:\n"
        "        total += 1\n"
        "    return total\n"
    )
    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": helper_source
        },
        body_by_root={
            "record_and_freeze_hashes": (
                "    return occurrence_total(value)\n"
            ),
            "validate_failure": "    return occurrence_total(value)\n",
        },
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|literal|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


def test_infrastructure_builder_bounds_deep_numeric_expression(tmp_path):
    from validation import literature_evidence_isolation as isolation

    expression = "value" + " + 1" * 1200
    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={"validate_failure": f"    return {expression}\n"},
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|literal|provenance|bound|complex",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


def test_infrastructure_builder_bounds_long_reverse_alias_chain(tmp_path):
    from validation import literature_evidence_isolation as isolation

    alias_count = 1200
    root_body = "    output = alias_0\n"
    root_body += "".join(
        f"    alias_{index} = alias_{index + 1}\n"
        for index in range(alias_count - 1)
    )
    root_body += f"    alias_{alias_count - 1} = 2\n"
    root_body += "    return output\n"
    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={"validate_failure": root_body},
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|literal|provenance|bound|complex",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


def test_infrastructure_builder_scans_helper_called_only_as_with_context(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": (
                "def transform():\n"
                "    numerator = 1\n"
                "    denominator = 2\n"
                "    return numerator / denominator\n"
            )
        },
        body_by_root={
            "validate_failure": (
                "    with transform():\n"
                "        return value\n"
            )
        },
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|literal|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


def test_infrastructure_builder_intersects_noncall_helper_reference_purposes(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    helper_source = (
        "def occurrence_total(items):\n"
        "    total = 0\n"
        "    for item in items:\n"
        "        total += 1\n"
        "    return total\n"
    )
    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": helper_source
        },
        body_by_root={
            "record_and_freeze_hashes": (
                "    return occurrence_total(value)\n"
            ),
            "validate_failure": "    return occurrence_total\n",
        },
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|literal|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


def test_infrastructure_builder_resolves_same_module_constant_default(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": (
                "BASE = 2\n"
                "def transform(item=BASE):\n"
                "    return item\n"
            )
        },
        body_by_root={"validate_failure": "    return transform()\n"},
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|literal|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


def test_infrastructure_builder_resolves_multihop_imported_constant_default(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_source(
        tmp_path,
        "validation.task5_constant_origin",
        "BASE = 2\n",
    )
    _write_task5_source(
        tmp_path,
        "validation.task5_constant_bridge",
        "from validation.task5_constant_origin import BASE\n"
        "FORWARDED = BASE\n",
    )
    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": (
                "from validation.task5_constant_bridge import FORWARDED\n"
                "def transform(item=FORWARDED):\n"
                "    return item\n"
            )
        },
        body_by_root={"validate_failure": "    return transform()\n"},
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|literal|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


def test_infrastructure_builder_resolves_class_constant_attributes(tmp_path):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": (
                "class Transport:\n"
                "    FACTOR = 2\n"
                "    def transform(self, item):\n"
                "        return item * self.FACTOR\n"
            )
        },
        body_by_root={"validate_failure": "    return Transport()\n"},
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|literal|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


def test_infrastructure_builder_resolves_class_method_numeric_defaults(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": (
                "class Transport:\n"
                "    def transform(self, item=2):\n"
                "        return item\n"
            )
        },
        body_by_root={"validate_failure": "    return Transport()\n"},
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|literal|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


def test_infrastructure_builder_rejects_imported_callable_named_len(tmp_path):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": (
                "from math import floor as len\n"
            )
        },
        body_by_root={"validate_failure": "    return len(value)\n"},
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|unknown|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


def test_infrastructure_builder_rejects_unapproved_external_call_result(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": (
                "from math import sqrt\n"
            )
        },
        body_by_root={"validate_failure": "    return sqrt(value)\n"},
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|unknown|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "case_name, root_body",
    (
        (
            "if_expression_test",
            "    return value if value < 2 else value\n",
        ),
        (
            "if_statement_test",
            "    if value < 2:\n"
            "        return value\n"
            "    return value\n",
        ),
        (
            "while_statement_test",
            "    while value < 2:\n"
            "        break\n"
            "    return value\n",
        ),
        (
            "assert_test",
            "    assert value < 2\n"
            "    return value\n",
        ),
        (
            "returned_threshold_decision",
            "    decision = True if value < 2 else False\n"
            "    return decision\n",
        ),
    ),
)
def test_infrastructure_builder_rejects_literal_threshold_control_contexts(
    tmp_path,
    case_name,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={"validate_failure": root_body},
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|literal|control|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


def test_infrastructure_builder_limits_frozen_threshold_to_proof_purpose(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    root_body = (
        '    threshold = value["frozen_policy"]["threshold"]\n'
        '    result = value["result"]\n'
        "    return result <= threshold\n"
    )
    proof_root = tmp_path / "proof"
    contract_root = tmp_path / "contract"
    _write_task5_infrastructure_sources(
        proof_root,
        body_by_root={"derive_convergence_decision": root_body},
    )
    proof = isolation.build_infrastructure_closure(
        source_roots=(proof_root,)
    )
    assert len(proof.roots) == 42

    _write_task5_infrastructure_sources(
        contract_root,
        body_by_root={"validate_failure": root_body},
    )
    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|threshold|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(
            source_roots=(contract_root,)
        )


@pytest.mark.parametrize(
    "case_name, root_body",
    (
        (
            "if_statement_test",
            '    threshold = value["frozen_policy"]["threshold"]\n'
            '    result = value["result"]\n'
            "    if result <= threshold:\n"
            "        return value\n"
            "    return None\n",
        ),
        (
            "if_expression_test",
            '    threshold = value["frozen_policy"]["threshold"]\n'
            '    result = value["result"]\n'
            "    return value if result <= threshold else None\n",
        ),
    ),
)
def test_infrastructure_builder_rejects_contract_frozen_threshold_control(
    tmp_path,
    case_name,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={"validate_failure": root_body},
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|threshold|control|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "case_name, root_body",
    (
        (
            "returned_comparison",
            '    threshold = value["frozen_policy"]["threshold"]\n'
            '    result = value["result"]\n'
            "    return result <= threshold\n",
        ),
        (
            "if_statement_test",
            '    threshold = value["frozen_policy"]["threshold"]\n'
            '    result = value["result"]\n'
            "    if result <= threshold:\n"
            "        return True\n"
            "    return False\n",
        ),
        (
            "if_expression_test",
            '    threshold = value["frozen_policy"]["threshold"]\n'
            '    result = value["result"]\n'
            "    return True if result <= threshold else False\n",
        ),
    ),
)
def test_infrastructure_builder_allows_proof_frozen_threshold_positions(
    tmp_path,
    case_name,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={"derive_convergence_decision": root_body},
    )

    closure = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )

    assert len(closure.roots) == 42


def test_infrastructure_builder_scans_helper_call_in_exception_type(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": (
                "def transform():\n"
                "    numerator = 1\n"
                "    denominator = 2\n"
                "    return numerator / denominator\n"
            )
        },
        body_by_root={
            "validate_failure": (
                "    try:\n"
                "        return value\n"
                "    except transform():\n"
                "        return None\n"
            )
        },
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|literal|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "case_name, target_statement",
    (
        ("attribute_assignment", "    transform().field = value\n"),
        ("subscript_assignment", "    transform()[0] = value\n"),
        ("attribute_deletion", "    del transform().field\n"),
        ("subscript_deletion", "    del transform()[0]\n"),
    ),
)
def test_infrastructure_builder_scans_helper_call_in_mutation_target_base(
    tmp_path,
    case_name,
    target_statement,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": (
                "def transform():\n"
                "    numerator = 1\n"
                "    denominator = 2\n"
                "    return numerator / denominator\n"
            )
        },
        body_by_root={
            "validate_failure": target_statement + "    return value\n"
        },
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|literal|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "root_name",
    ("validate_failure", "derive_convergence_decision"),
)
def test_infrastructure_builder_rejects_bare_frozen_comparison_expression(
    tmp_path,
    root_name,
):
    from validation import literature_evidence_isolation as isolation

    root_body = (
        '    threshold = value["frozen_policy"]["threshold"]\n'
        '    result = value["result"]\n'
        "    result <= threshold\n"
        "    return value\n"
    )
    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={root_name: root_body},
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|comparison|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "case_name, return_expression",
    (
        (
            "boolean_and",
            "(result <= threshold) and (left == right)",
        ),
        (
            "boolean_or",
            "(left == right) or (result <= threshold)",
        ),
        (
            "if_expression_branches",
            "(result <= threshold) if choice else (left == right)",
        ),
        (
            "tuple_wrapper",
            "(result <= threshold, left == right)",
        ),
        (
            "list_wrapper",
            "[result <= threshold, left == right]",
        ),
        (
            "dict_wrapper",
            '{"frozen": result <= threshold, "other": left == right}',
        ),
    ),
)
def test_infrastructure_builder_rejects_mixed_proof_comparisons(
    tmp_path,
    case_name,
    return_expression,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    root_body = (
        '    threshold = value["frozen_policy"]["threshold"]\n'
        '    result = value["result"]\n'
        '    left = value["left"]\n'
        '    right = value["right"]\n'
        '    choice = value["choice"]\n'
        f"    return {return_expression}\n"
    )
    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={"derive_convergence_decision": root_body},
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|comparison|threshold|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


def test_infrastructure_builder_rejects_mixed_proof_comparisons_through_call(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": (
                "def carry(*items):\n"
                "    return items\n"
            )
        },
        body_by_root={
            "derive_convergence_decision": (
                '    threshold = value["frozen_policy"]["threshold"]\n'
                '    result = value["result"]\n'
                '    left = value["left"]\n'
                '    right = value["right"]\n'
                "    return carry(\n"
                "        result <= threshold, left == right\n"
                "    )\n"
            )
        },
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|comparison|threshold|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "control_expression",
    (
        "(value is None) or len(value)",
        "(value is None) and len(value)",
        "len(value) or (value is None)",
        "len(value) and (value is None)",
        "(len(value) != 64) or (value is None)",
        "(len(value) != 64) and (value is None)",
        "(value is None) or (len(value) != 64)",
        "(value is None) and (len(value) != 64)",
    ),
)
def test_infrastructure_builder_rejects_mixed_none_and_len_control(
    tmp_path,
    control_expression,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={
            "validate_failure": (
                f"    return value if {control_expression} else None\n"
            )
        },
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|comparison|control|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "control_expression",
    (
        "value is None",
        "value is not None",
        "len(value)",
        "len([value])",
    ),
)
def test_infrastructure_builder_allows_exact_none_or_len_control(
    tmp_path,
    control_expression,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={
            "validate_failure": (
                f"    return value if {control_expression} else None\n"
            )
        },
    )

    closure = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )

    assert len(closure.roots) == 42


def test_infrastructure_builder_rejects_imported_len_comparison_control(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": (
                "from math import floor as len\n"
            )
        },
        body_by_root={
            "validate_failure": (
                "    if len(value) != 64:\n"
                "        return None\n"
                "    return value\n"
            )
        },
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|comparison|control|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "case_name, extra_source, root_body",
    (
        (
            "len_list",
            "",
            "    if len([value is None]) != 64:\n"
            "        return None\n"
            "    return value\n",
        ),
        (
            "len_nested_tuple",
            "",
            "    if len(((value is None,),)) != 64:\n"
            "        return None\n"
            "    return value\n",
        ),
        (
            "len_nested_dict",
            "",
            '    if len({"nested": [value is None]}) != 64:\n'
            "        return None\n"
            "    return value\n",
        ),
        (
            "range_argument",
            "",
            "    for index in range(value is None):\n"
            "        value[index]\n"
            "    return value\n",
        ),
        (
            "enumerate_argument",
            "",
            "    for index, item in enumerate([value is None]):\n"
            "        value[index]\n"
            "    return value\n",
        ),
        (
            "index_helper",
            "",
            "    return value[len([value is None])]\n",
        ),
        (
            "bound_helper",
            "",
            '    return value[:len({"nested": value is None})]\n',
        ),
        (
            "approved_constructor",
            "class Transport:\n"
            "    pass\n",
            "    return Transport(value is None)\n",
        ),
        (
            "project_helper_argument",
            "def ignore(item):\n"
            "    return None\n",
            "    return ignore(value is None)\n",
        ),
        (
            "project_helper_result",
            "def boxed(item):\n"
            "    return [item is None]\n",
            "    if len(boxed(value)) != 64:\n"
            "        return None\n"
            "    return value\n",
        ),
    ),
)
def test_infrastructure_builder_rejects_comparison_bearing_call_inputs(
    tmp_path,
    case_name,
    extra_source,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": extra_source
        },
        body_by_root={"validate_failure": root_body},
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|comparison|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "case_name, extra_source, root_body",
    (
        (
            "instance_attribute_literal_ratio",
            "class Transport:\n"
            "    def __init__(self, value):\n"
            "        self.factor = 1 / 2\n"
            "    def reveal(self):\n"
            "        return self.factor\n",
            "    return Transport(value)\n",
        ),
        (
            "instance_attribute_input_times_literal",
            "class Transport:\n"
            "    def __init__(self, value):\n"
            "        self.factor = value * 2\n"
            "    def reveal(self):\n"
            "        return self.factor\n",
            "    return Transport(value)\n",
        ),
        (
            "instance_attribute_unknown",
            "from math import floor as external\n"
            "class Transport:\n"
            "    def __init__(self, value):\n"
            "        self.factor = external(value)\n"
            "    def reveal(self):\n"
            "        return self.factor\n",
            "    return Transport(value)\n",
        ),
        (
            "instance_attribute_comparison",
            "class Transport:\n"
            "    def __init__(self, value):\n"
            "        self.factor = value is None\n"
            "    def reveal(self):\n"
            "        return self.factor\n",
            "    return Transport(value)\n",
        ),
        (
            "instance_attribute_annassign",
            "class Transport:\n"
            "    def __init__(self, value):\n"
            "        self.factor: object = 1 / 2\n",
            "    return Transport(value)\n",
        ),
        (
            "instance_attribute_augassign",
            "class Transport:\n"
            "    def __init__(self, value):\n"
            "        self.factor = value\n"
            "        self.factor += 1 / 2\n",
            "    return Transport(value)\n",
        ),
        (
            "subscript_literal_ratio",
            "",
            '    value["factor"] = 1 / 2\n'
            "    return value\n",
        ),
        (
            "subscript_input_times_literal",
            "",
            '    value["factor"] = value * 2\n'
            "    return value\n",
        ),
        (
            "nested_subscript_unknown",
            "from math import floor as external\n",
            '    value["nested"]["factor"] = external(value)\n'
            "    return value\n",
        ),
        (
            "nested_attribute_comparison",
            "",
            '    value["nested"].factor = value is None\n'
            "    return value\n",
        ),
        (
            "subscript_augassign",
            "",
            '    value["factor"] += 1 / 2\n'
            "    return value\n",
        ),
        (
            "subscript_annassign",
            "",
            '    value["factor"]: object = 1 / 2\n'
            "    return value\n",
        ),
        (
            "tuple_destructuring",
            "",
            '    (value.factor, value["factor"]) = (\n'
            "        1 / 2, value is None\n"
            "    )\n"
            "    return value\n",
        ),
        (
            "list_destructuring",
            "",
            '    [value.factor, value["factor"]] = [\n'
            "        value * 2, 1 / 2\n"
            "    ]\n"
            "    return value\n",
        ),
        (
            "starred_nested_attribute_destructuring",
            "",
            '    (*value["nested"].factors,) = [1 / 2]\n'
            "    return value\n",
        ),
        (
            "starred_nested_subscript_destructuring",
            "",
            '    (*value["nested"]["factors"],) = [value is None]\n'
            "    return value\n",
        ),
    ),
)
def test_infrastructure_builder_rejects_unsafe_mutation_values(
    tmp_path,
    case_name,
    extra_source,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": extra_source
        },
        body_by_root={"validate_failure": root_body},
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|mutation|provenance|purpose|unknown",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "case_name, root_body",
    (
        (
            "for_literal",
            "    for value.factor in [1 / 2]:\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "for_comparison",
            "    for value.factor in [value is None]:\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "with_literal",
            "    with (1 / 2) as value.factor:\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "with_comparison",
            "    with (value is None) as value.factor:\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "comprehension_comparison",
            "    [None for value.factor in [value is None]]\n"
            "    return value\n",
        ),
    ),
)
def test_infrastructure_builder_rejects_unsafe_mutation_bindings(
    tmp_path,
    case_name,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={"validate_failure": root_body},
    )

    with pytest.raises(
        AdapterContractError,
        match=(
            "infrastructure|numeric|mutation|provenance|purpose|control|"
            "comprehension|scope"
        ),
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "root_body",
    (
        "    for value.factor in external(value):\n"
        "        pass\n"
        "    return value\n",
        "    with external(value) as value.factor:\n"
        "        pass\n"
        "    return value\n",
    ),
)
def test_infrastructure_builder_rejects_unknown_mutation_bindings(
    tmp_path,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": (
                "from math import floor as external\n"
            )
        },
        body_by_root={"validate_failure": root_body},
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|mutation|provenance|purpose|unknown",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "case_name, extra_source, root_body",
    (
        (
            "direct_opaque_for",
            "",
            "    for value.factor in value:\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "local_opaque_for",
            "",
            "    for entered in value:\n"
            "        value.factor = entered\n"
            "    return value\n",
        ),
        (
            "direct_aliased_opaque_for",
            "",
            "    items = value\n"
            "    for value.factor in items:\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "local_aliased_opaque_for",
            "",
            "    items = value\n"
            "    for entered in items:\n"
            "        value.factor = entered\n"
            "    return value\n",
        ),
        (
            "direct_project_helper_opaque_for",
            "def forward_items(value):\n"
            "    return value\n",
            "    for value.factor in forward_items(value):\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "local_project_helper_opaque_for",
            "def forward_items(value):\n"
            "    return value\n",
            "    for entered in forward_items(value):\n"
            "        value.factor = entered\n"
            "    return value\n",
        ),
        (
            "direct_opaque_unpack",
            "",
            "    (value.factor,) = value\n"
            "    return value\n",
        ),
        (
            "local_opaque_unpack",
            "",
            "    (entered,) = value\n"
            "    value.factor = entered\n"
            "    return value\n",
        ),
        (
            "direct_aliased_opaque_unpack",
            "",
            "    payload = value\n"
            "    (value.factor,) = payload\n"
            "    return value\n",
        ),
        (
            "direct_project_helper_opaque_unpack",
            "def forward_items(value):\n"
            "    return value\n",
            "    (value.factor,) = forward_items(value)\n"
            "    return value\n",
        ),
        (
            "nested_opaque_unpack",
            "",
            "    ((value.factor,),) = value\n"
            "    return value\n",
        ),
        (
            "exact_outer_opaque_inner_unpack",
            "",
            "    ((value.factor,),) = (value,)\n"
            "    return value\n",
        ),
        (
            "direct_starred_opaque_unpack",
            "",
            "    (*value.factor,) = value\n"
            "    return value\n",
        ),
        (
            "local_starred_opaque_unpack",
            "",
            "    (*entered,) = value\n"
            "    value.factor = entered\n"
            "    return value\n",
        ),
        (
            "chained_name_and_opaque_unpack",
            "",
            "    direct = (value.factor,) = value\n"
            "    return direct\n",
        ),
        (
            "direct_subscript_opaque_for",
            "",
            '    for value["factor"] in value:\n'
            "        pass\n"
            "    return value\n",
        ),
        (
            "direct_subscript_opaque_unpack",
            "",
            '    (value["factor"],) = value\n'
            "    return value\n",
        ),
    ),
)
def test_infrastructure_builder_rejects_opaque_binding_results(
    tmp_path,
    case_name,
    extra_source,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": extra_source
        },
        body_by_root={"validate_failure": root_body},
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|mutation|provenance|purpose|unknown",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "target_and_body",
    (
        "    async for value.factor in value:\n"
        "        pass\n",
        "    async for entered in value:\n"
        "        value.factor = entered\n",
    ),
)
def test_infrastructure_builder_rejects_async_bindings_before_numeric_analysis(
    tmp_path,
    target_and_body,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        declaration_by_root={
            "validate_failure": (
                "async def validate_failure(value=None):\n"
                + target_and_body
                + "    return value\n"
            )
        },
    )

    with pytest.raises(
        AdapterContractError,
        match="asynchronous|forbidden",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "case_name, root_body",
    (
        (
            "literal_exact_unpack",
            "    unused, value.factor = (value, 1 / 2)\n"
            "    return value\n",
        ),
        (
            "comparison_exact_unpack",
            '    unused, value["factor"] = (value, value is None)\n'
            "    return value\n",
        ),
        (
            "literal_exact_for",
            "    for value.factor in [1 / 2]:\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "comparison_exact_for",
            '    for value["factor"] in (value is None,):\n'
            "        pass\n"
            "    return value\n",
        ),
        (
            "opaque_enumerate_attribute_element",
            "    for index, value.factor in enumerate(value):\n"
            "        value[index]\n"
            "    return value\n",
        ),
        (
            "opaque_enumerate_subscript_element",
            "    for index, entered in enumerate(value):\n"
            '        value["factor"] = entered\n'
            "        value[index]\n"
            "    return value\n",
        ),
    ),
)
def test_infrastructure_builder_rejects_unsafe_exact_binding_elements(
    tmp_path,
    case_name,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={"validate_failure": root_body},
    )

    with pytest.raises(
        AdapterContractError,
        match=(
            "infrastructure|numeric|mutation|provenance|purpose|unknown|"
            "comparison|literal|structural"
        ),
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "case_name, root_body",
    (
        (
            "exact_tuple_unpack",
            "    (value.factor,) = (value,)\n"
            "    return value\n",
        ),
        (
            "exact_list_unpack",
            '    [value["factor"]] = [value]\n'
            "    return value\n",
        ),
        (
            "nested_exact_tuple_unpack",
            "    ((value.factor,),) = ((value,),)\n"
            "    return value\n",
        ),
        (
            "nested_exact_list_unpack",
            '    [[value["factor"]]] = [[value]]\n'
            "    return value\n",
        ),
        (
            "mixed_exact_unpack",
            "    unused, value.factor = (1 / 2, value)\n"
            "    return value\n",
        ),
        (
            "exact_tuple_for",
            "    for value.factor in (value,):\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "exact_list_for",
            '    for value["factor"] in [value]:\n'
            "        pass\n"
            "    return value\n",
        ),
        (
            "unused_opaque_for",
            "    for item in value:\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "exact_enumerate_index_and_element",
            "    for index, entered in enumerate([value]):\n"
            "        value.factor = entered\n"
            "        value[index]\n"
            "    return value\n",
        ),
    ),
)
def test_infrastructure_builder_allows_exact_binding_element_provenance(
    tmp_path,
    case_name,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={"validate_failure": root_body},
    )

    closure = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )

    assert len(closure.roots) == 42


@pytest.mark.parametrize(
    "case_name, root_body",
    (
        (
            "exact_assignment_too_few",
            "    left, right = (value,)\n"
            "    return value\n",
        ),
        (
            "exact_assignment_too_many",
            "    left, right = (value, value, value)\n"
            "    return value\n",
        ),
        (
            "exact_starred_assignment_below_minimum",
            "    left, *middle, right = (value,)\n"
            "    return value\n",
        ),
        (
            "nested_exact_tuple_mismatch",
            "    ((left, right),) = ((value,),)\n"
            "    return value\n",
        ),
        (
            "nested_exact_list_mismatch",
            "    [[left, right], tail] = [[value], value]\n"
            "    return value\n",
        ),
        (
            "exact_for_element_mismatch",
            "    for left, right in ((value,),):\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "mixed_exact_for_element_mismatch",
            "    for left, right in (\n"
            "        (value, value), (value,)\n"
            "    ):\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "enumerate_target_too_many",
            "    for index, element, extra in enumerate([value]):\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "enumerate_target_too_few",
            "    for (only,) in enumerate([value]):\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "enumerate_starred_target_below_minimum",
            "    for index, *middle, element, extra in enumerate([value]):\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "range_target_mismatch",
            "    for left, right in range(len(value)):\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "tuple_source_starred_unpack",
            "    left, right = (*value,)\n"
            "    return value\n",
        ),
        (
            "list_source_starred_unpack",
            "    [left, right] = [*value]\n"
            "    return value\n",
        ),
        (
            "nested_source_starred_unpack",
            "    ((left, right),) = ((*value,),)\n"
            "    return value\n",
        ),
        (
            "exact_for_nested_source_star",
            "    for left, right in ((*value,),):\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "exact_for_top_level_source_star",
            "    for item in (*value,):\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "source_star_mutation_laundering",
            "    expanded = (*value,)\n"
            "    value.factor = expanded\n"
            "    return value\n",
        ),
    ),
)
def test_infrastructure_builder_rejects_invalid_exact_binding_shapes(
    tmp_path,
    case_name,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={"validate_failure": root_body},
    )

    with pytest.raises(
        AdapterContractError,
        match=(
            "infrastructure|numeric|binding|provenance|shape|exact|"
            "unsupported|mismatch|unknown|mutation"
        ),
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "case_name, root_body",
    (
        (
            "matching_tuple_assignment",
            "    left, right = (value, value)\n"
            "    return value\n",
        ),
        (
            "matching_list_assignment",
            "    [left, right] = [value, value]\n"
            "    return value\n",
        ),
        (
            "starred_target_zero_middle",
            "    left, *middle, right = (value, value)\n"
            "    return value\n",
        ),
        (
            "starred_target_one_middle",
            "    left, *middle, right = (value, value, value)\n"
            "    return value\n",
        ),
        (
            "starred_target_many_middle",
            "    left, *middle, right = (\n"
            "        value, value, value, value\n"
            "    )\n"
            "    return value\n",
        ),
        (
            "matching_nested_tuple",
            "    ((left, right),) = ((value, value),)\n"
            "    return value\n",
        ),
        (
            "matching_nested_list",
            "    [[left, right], tail] = [[value, value], value]\n"
            "    return value\n",
        ),
        (
            "matching_exact_for",
            "    for left, right in ((value, value),):\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "matching_starred_exact_for",
            "    for left, *middle, right in (\n"
            "        (value, value),\n"
            "        (value, value, value),\n"
            "        (value, value, value, value),\n"
            "    ):\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "matching_enumerate",
            "    for index, element in enumerate([value]):\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "matching_range",
            "    for index in range(len(value)):\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "unused_opaque_unpack",
            "    left, right = value\n"
            "    return value\n",
        ),
        (
            "unused_opaque_for_item",
            "    for item in value:\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "unused_opaque_for_unpack",
            "    for left, right in value:\n"
            "        pass\n"
            "    return value\n",
        ),
    ),
)
def test_infrastructure_builder_allows_valid_or_opaque_binding_shapes(
    tmp_path,
    case_name,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={"validate_failure": root_body},
    )

    closure = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )

    assert len(closure.roots) == 42


@pytest.mark.parametrize(
    "container_kind, scalar_source",
    tuple(
        (container_kind, scalar_source)
        for container_kind in ("tuple", "list")
        for scalar_source in (
            "True",
            "1",
            "1.5",
            "1j",
            "None",
            "...",
        )
    ),
)
def test_infrastructure_builder_rejects_nested_exact_scalar_unpack(
    tmp_path,
    container_kind,
    scalar_source,
):
    from validation import literature_evidence_isolation as isolation

    root_body = (
        f"    ((left,),) = ({scalar_source},)\n"
        if container_kind == "tuple"
        else f"    [[left]] = [{scalar_source}]\n"
    )
    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={
            "validate_failure": root_body + "    return value\n"
        },
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|binding|exact|shape|invalid|scalar",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "case_name, root_body",
    (
        (
            "root_tuple_from_integer",
            "    (left,) = 1\n"
            "    return value\n",
        ),
        (
            "root_list_from_none",
            "    [left] = None\n"
            "    return value\n",
        ),
        (
            "root_starred_from_ellipsis",
            "    (*middle,) = ...\n"
            "    return value\n",
        ),
        (
            "exact_tuple_for_none",
            "    for (left,) in (None,):\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "exact_list_for_boolean",
            "    for [left] in [True]:\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "exact_enumerate_tuple_inner",
            "    for index, (left,) in enumerate([1]):\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "exact_enumerate_list_inner",
            "    for index, [left] in enumerate([1j]):\n"
            "        pass\n"
            "    return value\n",
        ),
    ),
)
def test_infrastructure_builder_rejects_exact_scalar_structural_bindings(
    tmp_path,
    case_name,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={"validate_failure": root_body},
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|binding|exact|shape|invalid|scalar",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "case_name, extra_source, root_body",
    (
        (
            "direct_tuple_scalar",
            "",
            "    (left,) = (1,)\n"
            "    return value\n",
        ),
        (
            "direct_list_scalar",
            "",
            "    [left] = [None]\n"
            "    return value\n",
        ),
        (
            "direct_exact_for_scalar",
            "",
            "    for left in (1,):\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "direct_enumerate_scalar",
            "",
            "    for index, left in enumerate([1]):\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "opaque_nested_name",
            "",
            "    ((left,),) = (value,)\n"
            "    return value\n",
        ),
        (
            "opaque_nested_call",
            "def forward(value):\n"
            "    return value\n",
            "    ((left,),) = (forward(value),)\n"
            "    return value\n",
        ),
        (
            "opaque_nested_attribute",
            "",
            "    ((left,),) = (value.items,)\n"
            "    return value\n",
        ),
        (
            "opaque_nested_subscript",
            "",
            '    ((left,),) = (value["items"],)\n'
            "    return value\n",
        ),
        (
            "opaque_nested_string",
            "",
            '    ((left,),) = ("text",)\n'
            "    return value\n",
        ),
        (
            "opaque_nested_dict",
            "",
            '    ((left,),) = ({"item": value},)\n'
            "    return value\n",
        ),
        (
            "opaque_nested_set",
            "",
            "    ((left,),) = ({value},)\n"
            "    return value\n",
        ),
    ),
)
def test_infrastructure_builder_allows_direct_scalar_or_opaque_nested_binding(
    tmp_path,
    case_name,
    extra_source,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": extra_source
        },
        body_by_root={"validate_failure": root_body},
    )

    closure = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )

    assert len(closure.roots) == 42


@pytest.mark.parametrize(
    "container_kind, scalar_expression",
    tuple(
        (container_kind, scalar_expression)
        for container_kind in ("tuple", "list")
        for scalar_expression in (
            "-1",
            "+1",
            "~1",
            "1 / 2",
            "(1 + 2) * (3 - 4)",
            "value is None",
            "value is not None",
            "not value",
        )
    ),
)
def test_infrastructure_builder_rejects_guaranteed_scalar_syntax_unpack(
    tmp_path,
    container_kind,
    scalar_expression,
):
    from validation import literature_evidence_isolation as isolation

    root_body = (
        f"    ((left,),) = ({scalar_expression},)\n"
        if container_kind == "tuple"
        else f"    [[left]] = [{scalar_expression}]\n"
    )
    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={
            "validate_failure": root_body + "    return value\n"
        },
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|binding|exact|shape|invalid|scalar",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "target, scalar_expression",
    (
        ("(item,)", "-1"),
        ("(item,)", "1 / 2"),
        ("item", "1 / 2"),
        ("(item,)", "value is None"),
        ("item", "value is None"),
        ("(item,)", "not value"),
        ("item", "not value"),
    ),
)
def test_infrastructure_builder_rejects_for_guaranteed_scalar_shape_or_sink(
    tmp_path,
    target,
    scalar_expression,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={
            "validate_failure": (
                f"    for {target} in ({scalar_expression},):\n"
                "        pass\n"
                "    return value\n"
            )
        },
    )

    with pytest.raises(
        AdapterContractError,
        match=(
            "infrastructure|binding|exact|shape|invalid|scalar|numeric|"
            "comparison"
        ),
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "scalar_expression",
    ("-1",),
)
def test_infrastructure_builder_allows_direct_for_guaranteed_scalar(
    tmp_path,
    scalar_expression,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={
            "validate_failure": (
                f"    for item in ({scalar_expression},):\n"
                "        pass\n"
                "    return value\n"
            )
        },
    )

    closure = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )

    assert len(closure.roots) == 42


@pytest.mark.parametrize(
    "target, scalar_expression",
    (
        ("(item,)", "-1"),
        ("(item,)", "1 / 2"),
        ("(item,)", "value is None"),
        ("item", "value is None"),
        ("(item,)", "not value"),
        ("item", "not value"),
    ),
)
def test_infrastructure_builder_rejects_enumerate_guaranteed_scalar_shape(
    tmp_path,
    target,
    scalar_expression,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={
            "validate_failure": (
                "    for index, "
                f"{target} in enumerate([{scalar_expression}]):\n"
                "        pass\n"
                "    return value\n"
            )
        },
    )

    with pytest.raises(
        AdapterContractError,
        match=(
            "infrastructure|binding|exact|shape|invalid|scalar|comparison"
        ),
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "scalar_expression",
    ("-1", "1 / 2"),
)
def test_infrastructure_builder_allows_direct_enumerate_guaranteed_scalar(
    tmp_path,
    scalar_expression,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={
            "validate_failure": (
                "    for index, item in "
                f"enumerate([{scalar_expression}]):\n"
                "        pass\n"
                "    return value\n"
            )
        },
    )

    closure = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )

    assert len(closure.roots) == 42


@pytest.mark.parametrize(
    "scalar_expression",
    ("-1", "~1", "1 / 2", "value is None", "not value"),
)
def test_infrastructure_builder_allows_direct_assignment_guaranteed_scalar(
    tmp_path,
    scalar_expression,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={
            "validate_failure": (
                f"    (item,) = ({scalar_expression},)\n"
                "    return value\n"
            )
        },
    )

    closure = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )

    assert len(closure.roots) == 42


@pytest.mark.parametrize(
    "root_body",
    (
        pytest.param(
            "    return not value\n",
            id="direct_return",
        ),
        pytest.param(
            "    local = not value\n"
            "    value.factor = local\n"
            "    return value\n",
            id="attribute_mutation",
        ),
        pytest.param(
            "    local = not value\n"
            '    value["factor"] = local\n'
            "    return value\n",
            id="subscript_mutation",
        ),
    ),
)
def test_infrastructure_builder_rejects_not_expression_sinks(
    tmp_path,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={"validate_failure": root_body},
    )

    with pytest.raises(
        AdapterContractError,
        match=(
            "infrastructure|numeric|mutation|comparison|provenance|purpose|"
            "unknown"
        ),
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "opaque_expression",
    ("value + 1", "value == None"),
)
def test_infrastructure_builder_allows_opaque_nested_scalar_shaped_expression(
    tmp_path,
    opaque_expression,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={
            "validate_failure": (
                f"    ((item,),) = ({opaque_expression},)\n"
                "    return value\n"
            )
        },
    )

    closure = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )

    assert len(closure.roots) == 42


def test_infrastructure_builder_bounds_deep_guaranteed_scalar_syntax(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    scalar_expression = "1" + " + 1" * 1200
    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={
            "validate_failure": (
                f"    ((item,),) = ({scalar_expression},)\n"
                "    return value\n"
            )
        },
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|binding|exact|shape|invalid|scalar|bound",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


TASK7_5_NAME_AUGASSIGN_OPERATORS = (
    ("add", "+="),
    ("subtract", "-="),
    ("multiply", "*="),
    ("matrix_multiply", "@="),
    ("divide", "/="),
    ("modulo", "%="),
    ("power", "**="),
    ("left_shift", "<<="),
    ("right_shift", ">>="),
    ("bitwise_or", "|="),
    ("bitwise_xor", "^="),
    ("bitwise_and", "&="),
    ("floor_divide", "//="),
)


@pytest.mark.parametrize(
    "operator",
    tuple(operator for _name, operator in TASK7_5_NAME_AUGASSIGN_OPERATORS),
    ids=tuple(name for name, _operator in TASK7_5_NAME_AUGASSIGN_OPERATORS),
)
@pytest.mark.parametrize(
    "sink_body",
    (
        pytest.param("    return local\n", id="direct_return"),
        pytest.param(
            "    value.factor = local\n"
            "    return value\n",
            id="alias_mutation",
        ),
    ),
)
def test_infrastructure_builder_rejects_overloaded_name_augassign_sinks(
    tmp_path,
    operator,
    sink_body,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={
            "validate_failure": (
                "    local = value\n"
                f"    local {operator} value\n"
                + sink_body
            )
        },
    )

    with pytest.raises(
        AdapterContractError,
        match=(
            "infrastructure|numeric|mutation|provenance|purpose|unknown|"
            "scientific|power"
        ),
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "operator",
    (
        pytest.param("+", id="positive"),
        pytest.param("-", id="negative"),
        pytest.param("~", id="invert"),
    ),
)
@pytest.mark.parametrize(
    "root_body_template",
    (
        pytest.param(
            "    return {operator}value\n",
            id="direct_return",
        ),
        pytest.param(
            "    local = {operator}value\n"
            "    value.factor = local\n"
            "    return value\n",
            id="alias_mutation",
        ),
    ),
)
def test_infrastructure_builder_rejects_overloaded_unary_sinks(
    tmp_path,
    operator,
    root_body_template,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={
            "validate_failure": root_body_template.format(
                operator=operator
            )
        },
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|mutation|provenance|purpose|unknown",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "operator",
    tuple(
        operator
        for name, operator in TASK7_5_NAME_AUGASSIGN_OPERATORS
        if name != "power"
    ),
    ids=tuple(
        name
        for name, _operator in TASK7_5_NAME_AUGASSIGN_OPERATORS
        if name != "power"
    ),
)
def test_infrastructure_builder_allows_unused_overloaded_name_augassign(
    tmp_path,
    operator,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={
            "validate_failure": (
                "    local = value\n"
                f"    local {operator} value\n"
                "    return value\n"
            )
        },
    )

    closure = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )

    assert len(closure.roots) == 42


@pytest.mark.parametrize(
    "root_name, root_body",
    (
        pytest.param(
            "validate_failure",
            "    protocol_revision = +(1 + 2)\n"
            "    return value if protocol_revision else None\n",
            id="pure_positive_numeric_syntax",
        ),
        pytest.param(
            "validate_failure",
            "    protocol_revision = -(1 * (2 + 3))\n"
            "    return value if protocol_revision else None\n",
            id="pure_negative_numeric_syntax",
        ),
        pytest.param(
            "validate_failure",
            "    protocol_revision = ~1\n"
            "    return value if protocol_revision else None\n",
            id="pure_invert_numeric_syntax",
        ),
        pytest.param(
            "validate_failure",
            "    protocol_revision = 1\n"
            "    protocol_revision += 1\n"
            "    return value if protocol_revision else None\n",
            id="small_literal_control",
        ),
        pytest.param(
            "record_and_freeze_hashes",
            "    total = 0\n"
            "    for item in value:\n"
            "        total += 1\n"
            "    return total\n",
            id="authorized_occurrence_counter",
        ),
        pytest.param(
            "validate_failure",
            "    size = len(value)\n"
            "    size += len(value)\n"
            "    return size\n",
            id="pure_structural_augassign",
        ),
        pytest.param(
            "validate_failure",
            "    return +len(value)\n",
            id="pure_structural_positive",
        ),
        pytest.param(
            "validate_failure",
            "    return -len(value)\n",
            id="pure_structural_negative",
        ),
        pytest.param(
            "validate_failure",
            "    return ~len(value)\n",
            id="pure_structural_invert",
        ),
        pytest.param(
            "validate_failure",
            "    if len(value) != 64:\n"
            "        return None\n"
            "    return value\n",
            id="authorized_structural_control",
        ),
    ),
)
def test_infrastructure_builder_allows_builtin_numeric_and_structural_controls(
    tmp_path,
    root_name,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={root_name: root_body},
    )

    closure = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )

    assert len(closure.roots) == 42


@pytest.mark.parametrize(
    "case_name, extra_source, root_body",
    (
        (
            "before_loop",
            "",
            "    total = 0\n"
            "    total = value\n"
            "    for item in value:\n"
            "        total += 1\n"
            "    return total\n",
        ),
        (
            "next_iteration",
            "",
            "    total = 0\n"
            "    for item in value:\n"
            "        total += 1\n"
            "        total = value\n"
            "    return total\n",
        ),
        (
            "conditional_branch",
            "",
            "    total = 0\n"
            "    for item in value:\n"
            "        total += 1\n"
            "        if value:\n"
            "            total = value\n"
            "    return total\n",
        ),
        (
            "input_alias",
            "",
            "    contaminant = value\n"
            "    total = 0\n"
            "    total = contaminant\n"
            "    for item in value:\n"
            "        total += 1\n"
            "    return total\n",
        ),
        (
            "project_helper_summary",
            "def forward(value):\n"
            "    return value\n",
            "    total = 0\n"
            "    total = forward(value)\n"
            "    for item in value:\n"
            "        total += 1\n"
            "    return total\n",
        ),
    ),
)
def test_infrastructure_builder_rejects_contaminated_occurrence_counter(
    tmp_path,
    case_name,
    extra_source,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": extra_source
        },
        body_by_root={"record_and_freeze_hashes": root_body},
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|counter|unknown|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "return_body",
    (
        pytest.param(
            "    return (total, value)\n",
            id="separate_tuple_element",
        ),
        pytest.param(
            "    return [value, total]\n",
            id="separate_list_element",
        ),
        pytest.param(
            "    return (value, [total])\n",
            id="mixed_tuple_list",
        ),
        pytest.param(
            "    return ([value, (total,)],)\n",
            id="nested_containers",
        ),
    ),
)
def test_infrastructure_builder_rejects_contaminated_counter_in_container(
    tmp_path,
    return_body,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={
            "record_and_freeze_hashes": (
                "    total = 0\n"
                "    for item in value:\n"
                "        total += 1\n"
                "        total = value\n"
                + return_body
            )
        },
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|counter|unknown|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "case_name, extra_source, root_body",
    (
        (
            "str_add_literal_left_direct_return",
            "",
            '    return "prefix" + value\n',
        ),
        (
            "str_add_literal_right_alias_return",
            "",
            '    payload = value + "suffix"\n'
            "    return payload\n",
        ),
        (
            "bytes_add_literal_left_direct_return",
            "",
            '    return b"sha256:" + value\n',
        ),
        (
            "bytes_add_literal_right_helper_attribute_mutation",
            "def forward(value):\n"
            "    return value\n",
            '    value.payload = forward(value) + b""\n'
            "    return value\n",
        ),
        (
            "str_mod_literal_left_direct_return",
            "",
            '    return "%s" % value\n',
        ),
        (
            "str_mod_literal_right_subscript_mutation",
            "",
            '    value["payload"] = value % "%s"\n'
            "    return value\n",
        ),
        (
            "bytes_mod_literal_left_alias_return",
            "",
            '    payload = b"%s" % value\n'
            "    return payload\n",
        ),
        (
            "bytes_mod_literal_right_helper_attribute_mutation",
            "def forward(value):\n"
            "    return value\n",
            '    value.payload = forward(value) % b"%s"\n'
            "    return value\n",
        ),
    ),
)
def test_infrastructure_builder_rejects_categorical_literal_overload(
    tmp_path,
    case_name,
    extra_source,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": extra_source
        },
        body_by_root={"validate_failure": root_body},
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|mutation|unknown|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "root_body",
    (
        '    return "prefix" + "suffix"\n',
        '    return b"%s" % b"value"\n',
    ),
)
def test_infrastructure_builder_allows_exact_categorical_literals(
    tmp_path,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={"validate_failure": root_body},
    )

    closure = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )

    assert len(closure.roots) == 42


@pytest.mark.parametrize(
    "root_body",
    (
        "    if not value:\n"
        "        pass\n"
        "    return value\n",
        "    while not value:\n"
        "        break\n"
        "    return value\n",
        "    assert not value\n"
        "    return value\n",
        "    return value if not value else None\n",
    ),
)
def test_infrastructure_builder_allows_direct_not_control(
    tmp_path,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={"validate_failure": root_body},
    )

    closure = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )

    assert len(closure.roots) == 42


def test_infrastructure_builder_rejects_aliased_not_control(tmp_path):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={
            "validate_failure": (
                "    predicate = not value\n"
                "    if predicate:\n"
                "        pass\n"
                "    return value\n"
            )
        },
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|comparison|control|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "mutation_statement",
    (
        "    value.factor += value\n",
        "    value.factor *= value\n",
        "    value[key] += value\n",
        "    value[key] |= value\n",
    ),
)
def test_infrastructure_builder_rejects_nonlocal_augmented_assignment(
    tmp_path,
    mutation_statement,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={
            "validate_failure": (
                "    key = value\n"
                + mutation_statement
                + "    return value\n"
            )
        },
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|mutation|provenance|purpose|unknown",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "target",
    ("value.factor", "value[key]"),
)
def test_infrastructure_builder_rejects_direct_with_mutation_binding(
    tmp_path,
    target,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={
            "validate_failure": (
                "    key = value\n"
                f"    with value as {target}:\n"
                "        pass\n"
                "    return value\n"
            )
        },
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|mutation|provenance|purpose|unknown",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "mutation_statement",
    (
        "        value.factor = entered\n",
        "        value[key] = entered\n",
    ),
)
def test_infrastructure_builder_rejects_laundered_with_mutation_binding(
    tmp_path,
    mutation_statement,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={
            "validate_failure": (
                "    key = value\n"
                "    with value as entered:\n"
                + mutation_statement
                + "    return value\n"
            )
        },
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|mutation|provenance|purpose|unknown",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "post_with_body",
    (
        "    return entered\n",
        "    entered\n"
        "    return value\n",
    ),
)
def test_infrastructure_builder_rejects_with_binding_use(
    tmp_path,
    post_with_body,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={
            "validate_failure": (
                "    with value as entered:\n"
                "        pass\n"
                + post_with_body
            )
        },
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|provenance|purpose|unknown",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


def test_infrastructure_builder_rejects_unsafe_async_for_mutation_binding(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        declaration_by_root={
            "validate_failure": (
                "async def validate_failure(value=None):\n"
                "    async for value.factor in [value is None]:\n"
                "        pass\n"
                "    return value\n"
            )
        },
    )

    with pytest.raises(
        AdapterContractError,
        match=(
            "infrastructure|numeric|mutation|provenance|purpose|control|"
            "asynchronous|forbidden"
        ),
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "case_name, extra_source, root_body",
    (
        (
            "attribute_input",
            "",
            "    value.factor = value\n"
            "    return value\n",
        ),
        (
            "subscript_input",
            "",
            '    value["factor"] = value\n'
            "    return value\n",
        ),
        (
            "local_numeric_assignment",
            "",
            "    local = 1 / 2\n"
            "    return value\n",
        ),
        (
            "local_input_augmented_assignment",
            "",
            "    local = value\n"
            "    local += value\n"
            "    return value\n",
        ),
        (
            "unused_with_binding",
            "",
            "    with value as entered:\n"
            "        pass\n"
            "    return value\n",
        ),
        (
            "clean_approved_constructor",
            "class Transport:\n"
            "    def __init__(self, value):\n"
            "        self.value = value\n",
            "    return Transport(value)\n",
        ),
    ),
)
def test_infrastructure_builder_allows_safe_mutation_and_local_bindings(
    tmp_path,
    case_name,
    extra_source,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": extra_source
        },
        body_by_root={"validate_failure": root_body},
    )

    closure = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )

    assert len(closure.roots) == 42


def test_infrastructure_builder_allows_small_integer_protocol_control(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={
            "validate_failure": (
                "    protocol_revision = 1\n"
                "    return value if protocol_revision else None\n"
            )
        },
    )

    closure = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )

    assert len(closure.roots) == 42


TASK5_ALLOWED_INFRASTRUCTURE_CONTENT = (
    (
        "bounded_size",
        "    bounded_size = len(value) + 1\n"
        "    return bounded_size\n",
    ),
    (
        "generic_result_transport",
        "    result = value\n"
        "    return result\n",
    ),
    (
        "generic_model_transport",
        "    model = value\n"
        "    return model\n",
    ),
    (
        "generic_observable_transport",
        "    observable = value\n"
        "    return observable\n",
    ),
    (
        "scientific_closure_metadata",
        "    scientific_closure_hash = value\n"
        "    return scientific_closure_hash\n",
    ),
    (
        "freeze_style_depth",
        # A depth increment is structural only after its input is proven to be
        # a cardinality; unconstrained ``value + 1`` is scientific-shaped.
        "    depth = len(value)\n"
        "    next_depth = depth + 1\n"
        "    return next_depth\n",
    ),
    (
        "matrix_index_transport",
        "    matrix = value\n"
        "    energy = matrix[0]\n"
        "    return energy\n",
    ),
    (
        "computed_bound_method_transport",
        "    method = value.strip\n"
        "    policy_payload = method()\n"
        "    return policy_payload\n",
    ),
    (
        "computed_attribute_transport",
        "    energy = value.real\n"
        "    return energy\n",
    ),
    (
        "computed_subscripted_method_transport",
        "    methods = (value.strip,)\n"
        "    policy_payload = methods[0]()\n"
        "    return policy_payload\n",
    ),
    (
        "scientific_words_in_docstring",
        '    """Compute a method result without deriving it here."""\n'
        "    return value\n",
    ),
)


@pytest.mark.parametrize(
    "case_name, root_body",
    TASK5_ALLOWED_INFRASTRUCTURE_CONTENT,
    ids=tuple(case[0] for case in TASK5_ALLOWED_INFRASTRUCTURE_CONTENT),
)
def test_infrastructure_builder_allows_structural_transport_content(
    tmp_path,
    case_name,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={"validate_failure": root_body},
    )

    closure = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )

    assert len(closure.roots) == 42


@pytest.mark.parametrize(
    "case_name, root_body",
    (
        (
            "bounded_size_and_model_transport",
            "    bounded_size = len(value) + 1\n"
            "    model = value\n"
            "    return bounded_size, model\n",
        ),
        (
            "bounded_size_and_scientific_metadata",
            "    bounded_size = len(value) + 1\n"
            "    scientific_closure_hash = value\n"
            "    return bounded_size, scientific_closure_hash\n",
        ),
        (
            "annotated_bounded_size_and_model_transport",
            "    bounded_size: int = len(value) + 1\n"
            "    model = value\n"
            "    return bounded_size, model\n",
        ),
        (
            "named_bounded_size_and_scientific_metadata",
            "    bounded_size = (next_depth := len(value) + 1)\n"
            "    scientific_closure_hash = value\n"
            "    return bounded_size, scientific_closure_hash\n",
        ),
        (
            "unpacked_bounded_size_and_model_transport",
            "    (bounded_size,) = (len(value) + 1,)\n"
            "    model = value\n"
            "    return bounded_size, model\n",
        ),
        (
            "augmented_bounded_size_and_model_transport",
            "    bounded_size = len(value)\n"
            "    bounded_size += len(value)\n"
            "    model = value\n"
            "    return bounded_size, model\n",
        ),
    ),
)
def test_infrastructure_builder_allows_composed_transport_statements(
    tmp_path,
    case_name,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={"validate_failure": root_body},
    )

    closure = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )

    assert len(closure.roots) == 42


@pytest.mark.parametrize(
    "helper_name",
    ("_validate_scientific_closure", "_transport_result"),
)
def test_infrastructure_builder_allows_transport_helper_names(
    tmp_path,
    helper_name,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        helper_name=helper_name,
    )

    closure = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )

    assert any(
        node["qualified_name"].endswith(f".{helper_name}")
        for node in closure.nodes
    )


def test_infrastructure_builder_allows_transitive_transport_arithmetic(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_source(
        tmp_path,
        "validation.task5_transport_helpers",
        "def advance_depth(depth):\n"
        "    next_depth = depth + 1\n"
        "    return next_depth\n",
    )
    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": (
                "from validation.task5_transport_helpers "
                "import advance_depth\n"
            )
        },
        body_by_root={
            # The helper formal is structurally proven at this call site.
            "validate_failure": "    return advance_depth(len(value))\n"
        },
    )

    closure = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )

    assert "validation.task5_transport_helpers.advance_depth" in {
        node["qualified_name"] for node in closure.nodes
    }


@pytest.mark.parametrize(
    "case_name, root_name, root_body",
    (
        (
            "fixed_nested_index",
            "validate_failure",
            "    return value[0][1]\n",
        ),
        (
            "range_and_index",
            "validate_failure",
            "    for index in range(len(value)):\n"
            "        value[index]\n"
            "    return value\n",
        ),
        (
            "enumerate_ordinal",
            "validate_failure",
            "    for index, item in enumerate(value):\n"
            "        value[index]\n"
            "    return value\n",
        ),
        (
            "hash_length_guard",
            "validate_failure",
            "    if len(value) != 64:\n"
            "        return None\n"
            "    return value\n",
        ),
        (
            "byte_bound_slice",
            "validate_failure",
            "    return value[:256]\n",
        ),
        (
            "event_occurrence_counter",
            "record_and_freeze_hashes",
            "    total = 0\n"
            "    for item in value:\n"
            "        total += 1\n"
            "    return total\n",
        ),
        (
            "frozen_policy_threshold",
            "derive_convergence_decision",
            '    threshold = value["threshold"]\n'
            '    return value["result"] <= threshold\n',
        ),
    ),
)
def test_infrastructure_builder_allows_bound_structural_numeric_sinks(
    tmp_path,
    case_name,
    root_name,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={root_name: root_body},
    )

    closure = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )

    assert len(closure.roots) == 42


@pytest.mark.parametrize(
    "case_name, extra_source, root_body",
    (
        (
            "adapter_definition_symbol",
            "class AdapterDefinition:\n"
            "    pass\n",
            "    validated = AdapterDefinition()\n"
            "    return validated\n",
        ),
        (
            "policy_bytes_transport",
            "def encode(value):\n"
            "    return value\n",
            "    policy_payload = value\n"
            "    canonical_bytes = encode(policy_payload)\n"
            "    return canonical_bytes\n",
        ),
    ),
)
def test_infrastructure_builder_allows_definition_and_policy_transport(
    tmp_path,
    case_name,
    extra_source,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": extra_source
        },
        body_by_root={"validate_failure": root_body},
    )

    closure = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )

    assert len(closure.roots) == 42


TASK5_LITERAL_POLICY_BYTES_FLOWS = (
    (
        "literal_concatenation",
        '    canonical_policy_bytes = b"detached-" + b"payload"\n'
        "    return canonical_policy_bytes\n",
    ),
    (
        "direct_local_alias",
        '    payload = b"detached"\n'
        "    canonical_policy_bytes = payload\n"
        "    return canonical_policy_bytes\n",
    ),
    (
        "forward_alias_chain",
        '    first = b"detached"\n'
        "    second = first\n"
        "    third = second\n"
        "    canonical_policy_bytes = third\n"
        "    return canonical_policy_bytes\n",
    ),
    (
        "reverse_alias_chain",
        "    canonical_policy_bytes = third\n"
        "    third = second\n"
        "    second = first\n"
        '    first = b"detached"\n'
        "    return canonical_policy_bytes\n",
    ),
    (
        "aliased_literal_concatenation",
        '    prefix = b"detached-"\n'
        '    suffix = b"payload"\n'
        "    combined = prefix + suffix\n"
        "    canonical_policy_bytes = combined\n"
        "    return canonical_policy_bytes\n",
    ),
    (
        "policy_target_without_bytes_name",
        '    policy_payload = b"detached"\n'
        "    return policy_payload\n",
    ),
    (
        "policy_target_alias",
        '    payload = b"detached"\n'
        "    policy_payload = payload\n"
        "    return policy_payload\n",
    ),
    (
        "policy_literal_without_sink",
        '    return b"scientific-policy"\n',
    ),
    (
        "concatenated_policy_literal_without_sink",
        '    return b"scientific-" + b"policy"\n',
    ),
    (
        "walrus_policy_literal",
        '    return (canonical_policy_bytes := b"detached")\n',
    ),
    (
        "walrus_policy_literal_alias",
        '    payload = b"detached"\n'
        "    return (policy_payload := payload)\n",
    ),
    (
        "conditional_policy_literal",
        "    canonical_policy_bytes = (\n"
        '        b"detached" if value is None else value\n'
        "    )\n"
        "    return canonical_policy_bytes\n",
    ),
    (
        "augmented_policy_literal",
        "    policy_payload = value\n"
        '    policy_payload += b"detached"\n'
        "    return policy_payload\n",
    ),
    (
        "tuple_unpacked_policy_literal",
        '    (policy_payload,) = (b"detached",)\n'
        "    return policy_payload\n",
    ),
    (
        "list_unpacked_policy_literal",
        '    [policy_payload] = [b"detached"]\n'
        "    return policy_payload\n",
    ),
    (
        "boolean_policy_literal",
        '    canonical_policy_bytes = b"detached" or value\n'
        "    return canonical_policy_bytes\n",
    ),
    (
        "annotated_multistep_policy_literal",
        '    source: bytes = b"detached"\n'
        "    middle = source\n"
        "    canonical_policy_bytes = middle\n"
        "    return canonical_policy_bytes\n",
    ),
    (
        "conditional_multistep_policy_literal",
        "    branch = b\"detached\" if value is None else value\n"
        "    alias = branch\n"
        "    canonical_policy_bytes = alias\n"
        "    return canonical_policy_bytes\n",
    ),
    (
        "modulo_policy_literal",
        '    policy_payload = b"%s" % value\n'
        "    return policy_payload\n",
    ),
    (
        "multiplied_policy_literal",
        '    policy_payload = b"detached" * value\n'
        "    return policy_payload\n",
    ),
    (
        "set_container_policy_literal",
        '    policy_payload = {value, b"detached"}\n'
        "    return policy_payload\n",
    ),
    (
        "dict_container_policy_literal",
        "    policy_payload = {\n"
        '        "transport": value, "fallback": b"detached"\n'
        "    }\n"
        "    return policy_payload\n",
    ),
    (
        "for_binding_policy_literal",
        '    for policy_payload in (b"detached",):\n'
        "        return policy_payload\n"
        "    return value\n",
    ),
    (
        "subscripted_policy_literal",
        '    payload = b"detached"\n'
        "    policy_payload = payload[:]\n"
        "    return policy_payload\n",
    ),
    (
        "subscripted_policy_container_literal",
        '    payloads = (b"detached",)\n'
        "    policy_payload = payloads[0]\n"
        "    return policy_payload\n",
    ),
    (
        "split_bound_policy_method",
        '    method = b"detached".strip\n'
        "    policy_payload = method()\n"
        "    return policy_payload\n",
    ),
    (
        "aliased_split_bound_policy_method",
        '    receiver = b"detached"\n'
        "    method = receiver.strip\n"
        "    alias = method\n"
        "    policy_payload = alias()\n"
        "    return policy_payload\n",
    ),
    (
        "subscripted_bound_policy_method",
        '    methods = (b"detached".strip,)\n'
        "    policy_payload = methods[0]()\n"
        "    return policy_payload\n",
    ),
)


@pytest.mark.parametrize(
    "case_name, root_body",
    TASK5_LITERAL_POLICY_BYTES_FLOWS,
    ids=tuple(case[0] for case in TASK5_LITERAL_POLICY_BYTES_FLOWS),
)
def test_infrastructure_builder_rejects_literal_policy_bytes_flow(
    tmp_path,
    case_name,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={"validate_failure": root_body},
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|scientific|policy|bytes|literal",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


def test_infrastructure_builder_rejects_literal_policy_call_argument(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": (
                "def choose(*values):\n"
                "    return values[0]\n"
            )
        },
        body_by_root={
            "validate_failure": (
                '    policy_payload = choose(value, b"detached")\n'
                "    return policy_payload\n"
            )
        },
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|scientific|policy|bytes|literal",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


def test_infrastructure_builder_rejects_computed_input_augmented_policy(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": (
                "def canonical_json_bytes(value):\n"
                "    return value\n"
            )
        },
        body_by_root={
            "validate_failure": (
                "    policy_payload = value\n"
                "    policy_payload += canonical_json_bytes(value)\n"
                "    return policy_payload\n"
            )
        },
    )

    with pytest.raises(
        AdapterContractError,
        match="infrastructure|numeric|unknown|provenance|purpose",
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


@pytest.mark.parametrize(
    "case_name, extra_source, root_body",
    (
        (
            "computed_policy_bytes",
            "def canonical_json_bytes(value):\n"
            "    return value\n",
            "    canonical_policy_bytes = canonical_json_bytes(value)\n"
            "    return canonical_policy_bytes\n",
        ),
        (
            "computed_policy_bytes_alias",
            "def canonical_json_bytes(value):\n"
            "    return value\n",
            "    computed = canonical_json_bytes(value)\n"
            "    alias = computed\n"
            "    canonical_policy_bytes = alias\n"
            "    return canonical_policy_bytes\n",
        ),
        (
            "reverse_computed_alias",
            "def canonical_json_bytes(value):\n"
            "    return value\n",
            "    canonical_policy_bytes = payload\n"
            "    payload = canonical_json_bytes(value)\n"
            "    return canonical_policy_bytes\n",
        ),
        (
            "nonpolicy_literal_concatenation",
            "",
            '    payload = b"detached-" + b"payload"\n'
            "    return payload\n",
        ),
        (
            "computed_policy_payload",
            "def canonical_json_bytes(value):\n"
            "    return value\n",
            "    policy_payload = canonical_json_bytes(value)\n"
            "    return policy_payload\n",
        ),
        (
            "computed_policy_walrus",
            "def canonical_json_bytes(value):\n"
            "    return value\n",
            "    return (\n"
            "        canonical_policy_bytes := canonical_json_bytes(value)\n"
            "    )\n",
        ),
        (
            "generic_literal_without_policy_sink",
            "",
            '    payload = b"transport"\n'
            "    return payload\n",
        ),
        (
            "computed_policy_conditional",
            "def canonical_json_bytes(value):\n"
            "    return value\n",
            "    canonical_policy_bytes = (\n"
            "        canonical_json_bytes(value)\n"
            "        if value is None\n"
            "        else value\n"
            "    )\n"
            "    return canonical_policy_bytes\n",
        ),
        (
            "computed_policy_tuple",
            "def canonical_json_bytes(value):\n"
            "    return value\n",
            "    policy_payload = (canonical_json_bytes(value), value)\n"
            "    return policy_payload\n",
        ),
        (
            "nonpolicy_conditional_literal",
            "",
            "    payload = b\"detached\" if value is None else value\n"
            "    return payload\n",
        ),
        (
            "nonpolicy_unpacked_literal",
            "",
            '    (payload,) = (b"detached",)\n'
            "    return payload\n",
        ),
        (
            "computed_policy_choice",
            "def canonical_json_bytes(value):\n"
            "    return value\n"
            "def choose(*values):\n"
            "    return values[0]\n",
            "    policy_payload = choose(\n"
            "        value, canonical_json_bytes(value)\n"
            "    )\n"
            "    return policy_payload\n",
        ),
        (
            "computed_policy_containers",
            "def canonical_json_bytes(value):\n"
            "    return value\n",
            "    policy_payload = {\n"
            "        value, canonical_json_bytes(value)\n"
            "    }\n"
            "    return policy_payload\n",
        ),
        (
            "computed_policy_for_binding",
            "def canonical_json_bytes(value):\n"
            "    return value\n",
            "    for policy_payload in (canonical_json_bytes(value),):\n"
            "        return policy_payload\n"
            "    return value\n",
        ),
        (
            "computed_policy_subscript",
            "def canonical_json_bytes(value):\n"
            "    return value\n",
            "    policy_payload = canonical_json_bytes(value)[0]\n"
            "    return policy_payload\n",
        ),
        (
            "nonliteral_policy_subscript",
            "",
            "    payload = value\n"
            "    policy_payload = payload[0]\n"
            "    return policy_payload\n",
        ),
    ),
)
def test_infrastructure_builder_allows_nonliteral_policy_bytes_transport(
    tmp_path,
    case_name,
    extra_source,
    root_body,
):
    from validation import literature_evidence_isolation as isolation

    del case_name
    _write_task5_infrastructure_sources(
        tmp_path,
        extra_source_by_module={
            "validation.literature_evidence_isolation": extra_source
        },
        body_by_root={"validate_failure": root_body},
    )

    closure = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )

    assert len(closure.roots) == 42


TASK5_NEUTRAL_KEY_POLICY_BYPASSES = (
    ("categorical_invariant", {"invariant_rule": "ordered_phase"}),
    ("arbitrary_derivation", {"derivation": "value ** 2 + 1"}),
    ("benchmark_branch", {"branch": {"synthetic_benchmark": 1.25}}),
    ("unknown_proof_kind", {"proof_kind": "caller_expression"}),
)


@pytest.mark.parametrize(
    "case_name, convergence_contract",
    TASK5_NEUTRAL_KEY_POLICY_BYPASSES,
    ids=tuple(case[0] for case in TASK5_NEUTRAL_KEY_POLICY_BYPASSES),
)
def test_policy_builder_rejects_each_neutral_key_oracle_bypass(
    case_name,
    convergence_contract,
):
    from validation import literature_evidence_adapter_oracles as oracles
    from validation import literature_evidence_isolation as isolation

    del case_name
    canonical = _synthetic_oracle_definition()
    values = {
        field.name: getattr(canonical, field.name)
        for field in dataclasses.fields(type(canonical))
    }
    values["convergence_invariant_contract"] = convergence_contract
    bypass = oracles.OracleDefinition(**values)

    with pytest.raises(
        AdapterContractError,
        match=(
            "policy|categorical|derivation|expression|branch|benchmark|"
            "proof"
        ),
    ):
        isolation.build_scientific_policy_commitment(
            bypass, _task5_oracle_closure(), role="oracle"
        )


TASK5_ORACLE_CONVERGENCE_GRAMMAR_BYPASSES = (
    ("categorical_rule", {"rule": "ferromagnetic"}),
    ("expression_rule", {"rule": "value ** 2 + 1"}),
    ("benchmark_selector", {"selector": {"synthetic_benchmark": 1.25}}),
    ("proof_kind_alias", {"proofKind": "caller_expression"}),
)


@pytest.mark.parametrize(
    "case_name, mutation",
    TASK5_ORACLE_CONVERGENCE_GRAMMAR_BYPASSES,
    ids=tuple(
        case[0] for case in TASK5_ORACLE_CONVERGENCE_GRAMMAR_BYPASSES
    ),
)
def test_policy_builder_rejects_oracle_convergence_grammar_bypass(
    case_name,
    mutation,
):
    from validation import literature_evidence_adapter_oracles as oracles
    from validation import literature_evidence_isolation as isolation

    del case_name
    canonical = _synthetic_oracle_definition()
    values = {
        field.name: getattr(canonical, field.name)
        for field in dataclasses.fields(type(canonical))
    }
    contract = thaw_json(canonical.convergence_invariant_contract)
    contract.update(mutation)
    values["convergence_invariant_contract"] = contract
    bypass = oracles.OracleDefinition(**values)

    with pytest.raises(
        AdapterContractError,
        match="policy|convergence|contract|closed|rule|selector|proof",
    ):
        isolation.build_scientific_policy_commitment(
            bypass, _task5_oracle_closure(), role="oracle"
        )


def test_policy_builder_accepts_closed_oracle_secondary_bound_extension():
    from validation import literature_evidence_isolation as isolation

    definition = _task5_mutated_oracle("convergence")

    commitment = isolation.build_scientific_policy_commitment(
        definition, _task5_oracle_closure(), role="oracle"
    )

    assert commitment.definition_id == definition.oracle_id


def _task5_unrelated_adapter_definition():
    canonical = adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"]
    values = {
        field.name: getattr(canonical, field.name)
        for field in dataclasses.fields(type(canonical))
    }
    values["adapter_id"] = "unrelated_membership_adapter"
    values["entry_symbol"] = (
        "validation.literature_evidence_adapters:"
        "adapter_unrelated_membership_adapter"
    )
    return AdapterDefinition(**values)


def _task5_unrelated_oracle_definition():
    from validation import literature_evidence_adapter_oracles as oracles

    canonical = _synthetic_oracle_definition()
    values = {
        field.name: getattr(canonical, field.name)
        for field in dataclasses.fields(type(canonical))
    }
    values["oracle_id"] = "unrelated_membership_oracle"
    values["entry_symbol"] = (
        "validation.literature_evidence_adapter_oracles:"
        "oracle_unrelated_membership_oracle"
    )
    return oracles.OracleDefinition(**values)


@pytest.mark.parametrize("catalog_role", ("adapter", "oracle"))
def test_dependency_partition_commits_whole_definition_catalog_membership(
    tmp_path,
    monkeypatch,
    catalog_role,
):
    from validation import literature_evidence_adapter_oracles as oracles

    fixture = _task5_partition_fixture(tmp_path)
    baseline = _assert_task5_partition(fixture, fixture[5])
    if catalog_role == "adapter":
        catalog = dict(adapters.ADAPTER_DEFINITIONS)
        unrelated = _task5_unrelated_adapter_definition()
        catalog[unrelated.adapter_id] = unrelated
        monkeypatch.setattr(
            adapters, "ADAPTER_DEFINITIONS", MappingProxyType(catalog)
        )
    else:
        catalog = dict(oracles.ORACLE_DEFINITIONS)
        unrelated = _task5_unrelated_oracle_definition()
        catalog[unrelated.oracle_id] = unrelated
        monkeypatch.setattr(
            oracles, "ORACLE_DEFINITIONS", MappingProxyType(catalog)
        )

    changed = _assert_task5_partition(fixture, fixture[5])

    assert changed != baseline


@pytest.mark.parametrize("catalog_role", ("adapter", "oracle"))
def test_dependency_partition_rejects_definition_catalog_key_id_mismatch(
    tmp_path,
    monkeypatch,
    catalog_role,
):
    from validation import literature_evidence_adapter_oracles as oracles

    fixture = _task5_partition_fixture(tmp_path)
    if catalog_role == "adapter":
        catalog = dict(adapters.ADAPTER_DEFINITIONS)
        catalog["mismatched_adapter_key"] = (
            _task5_unrelated_adapter_definition()
        )
        monkeypatch.setattr(
            adapters,
            "ADAPTER_DEFINITIONS",
            MappingProxyType(catalog),
        )
    else:
        monkeypatch.setattr(
            oracles,
            "ORACLE_DEFINITIONS",
            MappingProxyType(
                {"mismatched_oracle_key": _task5_unrelated_oracle_definition()}
            ),
        )

    with pytest.raises(AdapterContractError, match="catalog|key|ID|definition"):
        _assert_task5_partition(fixture, fixture[5])


def test_dependency_partition_rejects_nontext_definition_catalog_key(
    tmp_path,
    monkeypatch,
):
    fixture = _task5_partition_fixture(tmp_path)
    catalog = dict(adapters.ADAPTER_DEFINITIONS)
    catalog[7] = _task5_unrelated_adapter_definition()
    monkeypatch.setattr(
        adapters, "ADAPTER_DEFINITIONS", MappingProxyType(catalog)
    )

    with pytest.raises(AdapterContractError, match="catalog|key|identifier"):
        _assert_task5_partition(fixture, fixture[5])


def _task6_build_scientific_closure(tmp_path, role, source):
    from validation import literature_evidence_isolation as isolation

    module_name = (
        "task6_science.adapters"
        if role == "adapter"
        else "task6_science.adapter_oracles"
    )
    _write_task5_source(tmp_path, module_name, source)
    return isolation.build_scientific_closure(
        f"{module_name}:scientific_entry",
        role=role,
        source_roots=(tmp_path,),
    )


@pytest.mark.parametrize("role", ("adapter", "oracle"))
def test_task6_forbidden_import_rejects_registry_source(tmp_path, role):
    source = (
        "from validation.literature_benchmark_registry "
        "import LITERATURE_STANDARD_RESULTS\n"
        "def scientific_entry(value):\n"
        "    return LITERATURE_STANDARD_RESULTS\n"
    )

    with pytest.raises(AdapterContractError, match="import|approved|project"):
        _task6_build_scientific_closure(tmp_path, role, source)


@pytest.mark.parametrize("role", ("adapter", "oracle"))
def test_task6_static_scan_rejects_eval(tmp_path, role):
    source = (
        "def scientific_entry(value):\n"
        "    return eval('value')\n"
    )

    with pytest.raises(
        AdapterContractError,
        match="dynamic|source|evaluation|capability|API",
    ):
        _task6_build_scientific_closure(tmp_path, role, source)


def test_task6_static_scan_rejects_closure_without_private_material(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    closure = _task6_build_scientific_closure(
        tmp_path,
        "adapter",
        "def scientific_entry(value):\n"
        "    return value + 1\n",
    )
    rebuilt = isolation.ScientificClosure(
        **{
            field.name: getattr(closure, field.name)
            for field in dataclasses.fields(type(closure))
        }
    )
    assert rebuilt == closure
    assert "_static_scan_material" not in vars(rebuilt)

    with pytest.raises(
        AdapterContractError,
        match="static|scan|material|builder|closure",
    ):
        isolation.scan_scientific_closure(
            rebuilt,
            forbidden_fingerprints=(
                canonical_sha256("task6-absent-output-canary"),
            ),
        )


TASK6_ENVIRONMENT_AND_GIT_SOURCES = (
    pytest.param(
        "import os\n"
        "def scientific_entry(value):\n"
        "    return os.environ.get('SCIENTIFIC_ANSWER')\n",
        id="os-environ",
    ),
    pytest.param(
        "import os\n"
        "def scientific_entry(value):\n"
        "    return os.getenv('SCIENTIFIC_ANSWER')\n",
        id="os-getenv",
    ),
    pytest.param(
        "from pathlib import Path\n"
        "def scientific_entry(value):\n"
        "    return Path.cwd(), Path.home()\n",
        id="pathlib-cwd-home",
    ),
    pytest.param(
        "import git\n"
        "def scientific_entry(value):\n"
        "    return git.Repo(search_parent_directories=True)\n",
        id="git-discovery",
    ),
    pytest.param(
        "import subprocess\n"
        "def scientific_entry(value):\n"
        "    return subprocess.check_output(\n"
        "        ('git', 'rev-parse', '--show-toplevel')\n"
        "    )\n",
        id="subprocess-git-probe",
    ),
)


TASK6_DYNAMIC_CAPABILITY_SOURCES = (
    pytest.param(
        "def scientific_entry(value):\n"
        "    return __import__('math').sqrt(value)\n",
        id="dynamic-import",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    return compile('value + 1', '<answer>', 'eval')\n",
        id="compile",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    exec('value = 1')\n"
        "    return value\n",
        id="exec",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    namespace = (globals(), locals(), vars(value))\n"
        "    return namespace\n",
        id="namespace-reflection",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    item = getattr(value, 'real')\n"
        "    setattr(value, 'answer', item)\n"
        "    delattr(value, 'answer')\n"
        "    return item\n",
        id="attribute-reflection",
    ),
    pytest.param(
        "import io\n"
        "from pathlib import Path\n"
        "def scientific_entry(value):\n"
        "    with open(Path('previous-output.json'), 'rb') as stream:\n"
        "        return io.BytesIO(stream.read()).read()\n",
        id="open-io-path-read",
    ),
    pytest.param(
        "import http.client\n"
        "import socket\n"
        "import urllib.request\n"
        "def scientific_entry(value):\n"
        "    return (\n"
        "        socket.create_connection(('127.0.0.1', 80)),\n"
        "        urllib.request.urlopen('http://127.0.0.1'),\n"
        "        http.client.HTTPConnection('127.0.0.1'),\n"
        "    )\n",
        id="socket-urllib-http",
    ),
    pytest.param(
        "import subprocess\n"
        "def scientific_entry(value):\n"
        "    return subprocess.run(('git', 'status'), check=True)\n",
        id="subprocess",
    ),
    pytest.param(
        "import os\n"
        "def scientific_entry(value):\n"
        "    return os.system('git status'), os.popen('git status').read()\n",
        id="os-system-popen",
    ),
    pytest.param(
        "import ctypes\n"
        "def scientific_entry(value):\n"
        "    return ctypes.CDLL('libanswer.so')\n",
        id="ctypes",
    ),
    pytest.param(
        "import cffi\n"
        "def scientific_entry(value):\n"
        "    return cffi.FFI().dlopen('libanswer.so')\n",
        id="cffi",
    ),
    pytest.param(
        "import numpy\n"
        "def scientific_entry(value):\n"
        "    return numpy.ctypeslib.load_library('libanswer', '.')\n",
        id="numpy-native-loader",
    ),
    pytest.param(
        "import scipy\n"
        "def scientific_entry(value):\n"
        "    return scipy.LowLevelCallable.from_cython(\n"
        "        'answer_backend', 'answer_symbol'\n"
        "    )\n",
        id="scipy-native-symbol",
    ),
)


def _task6_absent_fingerprints():
    return (canonical_sha256("task6-absent-output-canary"),)


def _task6_build_and_scan(tmp_path, role, source):
    from validation import literature_evidence_isolation as isolation

    closure = _task6_build_scientific_closure(tmp_path, role, source)
    return isolation.scan_scientific_closure(
        closure,
        forbidden_fingerprints=_task6_absent_fingerprints(),
    )


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize("source", TASK6_ENVIRONMENT_AND_GIT_SOURCES)
def test_task6_forbidden_import_environment_and_git_discovery_is_rejected(
    tmp_path,
    role,
    source,
):
    with pytest.raises(
        AdapterContractError,
        match="import|approved|environment|Git|process|discovery",
    ):
        _task6_build_and_scan(tmp_path, role, source)


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize("source", TASK6_DYNAMIC_CAPABILITY_SOURCES)
def test_task6_static_scan_dynamic_capability_and_native_access_is_rejected(
    tmp_path,
    role,
    source,
):
    with pytest.raises(
        AdapterContractError,
        match=(
            "dynamic|source|evaluation|import|approved|capability|native|"
            "network|process|file|reflection|API"
        ),
    ):
        _task6_build_and_scan(tmp_path, role, source)


def test_task6_static_scan_declares_exact_string_parser_dependency(tmp_path):
    from validation import literature_evidence_isolation as isolation

    source = (
        "import string\n"
        "def scientific_entry(value):\n"
        "    return tuple(string.Formatter().parse(value))\n"
    )
    closure = _task6_build_scientific_closure(
        tmp_path, "adapter", source
    )
    report = isolation.scan_scientific_closure(
        closure,
        forbidden_fingerprints=_task6_absent_fingerprints(),
    )

    assert "string" in isolation._SAFE_EXTERNAL_IMPORT_PREFIXES
    assert report.passed is True


def _task6_safe_scan_closure(tmp_path, *, role="adapter", offset=""):
    source = (
        "from math import sqrt\n"
        "SCALE = (2.0, 0.5)\n"
        "def safe_helper(value):\n"
        f"    return sqrt(value{offset}) * SCALE[1]\n"
        "def scientific_entry(value):\n"
        "    return safe_helper(value)\n"
    )
    return _task6_build_scientific_closure(tmp_path, role, source)


TASK6_STATIC_SCAN_CHECKS = frozenset(
    {
        "raw_ast_closed",
        "dependency_graph_closed",
        "imports_closed",
        "capabilities_closed",
        "literal_context_closed",
        "emitted_bytes_closed",
        "fingerprints_absent",
        "role_policy_closed",
    }
)


def _task6_static_scan_payload(report):
    return {
        field.name: getattr(report, field.name)
        for field in dataclasses.fields(type(report))
        if field.name != "report_sha256"
    }


def test_task6_static_scan_builder_material_report_is_closed_and_deterministic(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    closure = _task6_safe_scan_closure(tmp_path)
    fingerprints = _task6_absent_fingerprints()

    first = isolation.scan_scientific_closure(
        closure, forbidden_fingerprints=fingerprints
    )
    second = isolation.scan_scientific_closure(
        closure, forbidden_fingerprints=fingerprints
    )

    assert first == second
    assert set(first.checks) == TASK6_STATIC_SCAN_CHECKS
    assert first.role == "adapter"
    assert first.schema_version == "static_scan_report_v1"
    assert first.scanned_closure_sha256 == closure.bundle_sha256
    assert first.fingerprint_commitment_sha256 == canonical_sha256(
        {
            "algorithm_version": "canonical_json_sha256_v1",
            "fingerprints": fingerprints,
        }
    )
    assert first.passed is True
    assert first.report_sha256 == canonical_sha256(
        _task6_static_scan_payload(first)
    )
    assert first.scanner_version
    assert len(first.scanner_sha256) == 64
    for check in first.checks.values():
        assert set(check) == {"passed", "reason"}
        assert type(check["passed"]) is bool
        assert check["passed"] is True
        assert type(check["reason"]) is str
        assert 0 < len(check["reason"].encode("utf-8")) <= 160


@pytest.mark.parametrize(
    "mutation",
    ("raw_span", "emitted_node", "emitted_source", "node_order"),
)
def test_task6_static_scan_rejects_private_material_tamper_or_reorder(
    tmp_path,
    mutation,
):
    from validation import literature_evidence_isolation as isolation

    closure = _task6_safe_scan_closure(tmp_path)
    public_bundle_sha256 = closure.bundle_sha256
    assert "_static_scan_material" in vars(closure)
    material = closure._static_scan_material
    assert type(material.nodes) is tuple
    assert len(material.nodes) > 1
    if mutation == "raw_span":
        node = material.nodes[0]
        object.__setattr__(
            node,
            "raw_source_span",
            node.raw_source_span + b" ",
        )
    elif mutation == "emitted_node":
        node = material.nodes[0]
        object.__setattr__(
            node,
            "emitted_node",
            node.emitted_node + b" ",
        )
    elif mutation == "emitted_source":
        object.__setattr__(
            material,
            "emitted_source",
            material.emitted_source + b" ",
        )
    else:
        object.__setattr__(
            material,
            "nodes",
            tuple(reversed(material.nodes)),
        )
    assert closure.bundle_sha256 == public_bundle_sha256

    with pytest.raises(
        AdapterContractError,
        match="static|scan|material|hash|order|closure",
    ):
        isolation.scan_scientific_closure(
            closure,
            forbidden_fingerprints=_task6_absent_fingerprints(),
        )


def test_task6_static_scan_rejects_cross_closure_private_material_replay(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    first = _task6_safe_scan_closure(tmp_path / "first")
    second = _task6_safe_scan_closure(
        tmp_path / "second", offset=" + 1.0"
    )
    assert first.bundle_sha256 != second.bundle_sha256
    assert "_static_scan_material" in vars(second)
    object.__setattr__(
        first,
        "_static_scan_material",
        second._static_scan_material,
    )

    with pytest.raises(
        AdapterContractError,
        match="static|scan|material|hash|closure|replay",
    ):
        isolation.scan_scientific_closure(
            first,
            forbidden_fingerprints=_task6_absent_fingerprints(),
        )


@pytest.mark.parametrize(
    "fingerprints",
    (
        pytest.param((), id="empty"),
        pytest.param(("a" * 64, "a" * 64), id="duplicate"),
        pytest.param(("f" * 64, "0" * 64), id="unsorted"),
        pytest.param(("f" * 63,), id="malformed"),
    ),
)
def test_task6_static_scan_rejects_noncanonical_fingerprint_set(
    tmp_path,
    fingerprints,
):
    from validation import literature_evidence_isolation as isolation

    closure = _task6_safe_scan_closure(tmp_path)
    with pytest.raises(
        AdapterContractError,
        match="fingerprint|nonempty|duplicate|ordering|SHA-256|canonical",
    ):
        isolation.scan_scientific_closure(
            closure, forbidden_fingerprints=fingerprints
        )


def test_task6_static_scan_report_does_not_echo_forbidden_operand(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    secret_operand = "TASK6_SECRET_REGISTERED_OPERAND_DO_NOT_ECHO"
    closure = _task6_safe_scan_closure(tmp_path)
    report = isolation.scan_scientific_closure(
        closure,
        forbidden_fingerprints=(canonical_sha256(secret_operand),),
    )
    report_bytes = canonical_json_bytes(
        {
            **_task6_static_scan_payload(report),
            "report_sha256": report.report_sha256,
        }
    )

    assert secret_operand.encode("utf-8") not in report_bytes


TASK6_REGISTERED_OPERAND = {
    "critical_temperature": 2.269185314213022,
    "phase": "ordered_phase",
}
TASK6_NESTED_REGISTERED_OPERAND = {
    "fields": {
        "critical_temperature": 2.269185314213022,
        "phase": "ordered_phase",
    },
    "units": {"critical_temperature": "J"},
}
TASK6_PARAMETER_RESULT_TABLE = {
    "0.5": 1.134592657106511,
    "1.0": 2.269185314213022,
}
TASK6_FIXED_ANSWER_SEQUENCE = (
    1.134592657106511,
    2.269185314213022,
    "ordered_phase",
)


TASK6_EMBEDDED_OUTPUT_CASES = (
    pytest.param(
        "def scientific_entry(value, benchmark_name):\n"
        "    if benchmark_name == "
        "'two_dimensional_square_ising_onsager_tc':\n"
        "        return 2.269185314213022\n"
        "    return value\n",
        (2.269185314213022,),
        (
            "two_dimensional_square_ising_onsager_tc",
            "2.269185314213022",
        ),
        id="benchmark-name-literal-branch",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    return 'ordered_phase'\n",
        ("ordered_phase",),
        ("ordered_phase",),
        id="exact-categorical-canary",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    return 2.269185314213022\n",
        (2.269185314213022,),
        ("2.269185314213022",),
        id="high-precision-numeric",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    return (\n"
        "        '{\"critical_temperature\":2.269185314213022,'\n"
        "        '\"phase\":\"ordered_phase\"}'\n"
        "    )\n",
        (TASK6_REGISTERED_OPERAND,),
        ("2.269185314213022", "ordered_phase"),
        id="whole-canonical-serialized-string",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    return (\n"
        "        b'{\"critical_temperature\":2.269185314213022,'\n"
        "        b'\"phase\":\"ordered_phase\"}'\n"
        "    )\n",
        (TASK6_REGISTERED_OPERAND,),
        ("2.269185314213022", "ordered_phase"),
        id="whole-canonical-serialized-bytes",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    return {\n"
        "        'fields': {\n"
        "            'critical_temperature': 2.269185314213022,\n"
        "            'phase': 'ordered_phase',\n"
        "        },\n"
        "        'units': {'critical_temperature': 'J'},\n"
        "    }\n",
        (
            TASK6_NESTED_REGISTERED_OPERAND,
            TASK6_NESTED_REGISTERED_OPERAND["fields"],
        ),
        ("2.269185314213022", "ordered_phase"),
        id="nested-field-value-structure",
    ),
    pytest.param(
        "def scientific_entry(parameter):\n"
        "    lookup_table = {\n"
        "        '0.5': 1.134592657106511,\n"
        "        '1.0': 2.269185314213022,\n"
        "    }\n"
        "    return lookup_table[str(parameter)]\n",
        (TASK6_PARAMETER_RESULT_TABLE,),
        ("1.134592657106511", "2.269185314213022"),
        id="parameter-result-lookup-table",
    ),
    pytest.param(
        "FIXED_VALUES = (\n"
        "    1.134592657106511,\n"
        "    2.269185314213022,\n"
        "    'ordered_phase',\n"
        ")\n"
        "def scientific_entry(value):\n"
        "    return FIXED_VALUES\n",
        (TASK6_FIXED_ANSWER_SEQUENCE,),
        (
            "1.134592657106511",
            "2.269185314213022",
            "ordered_phase",
        ),
        id="fixed-answer-sequence-raw-and-emitted",
    ),
    pytest.param(
        "def copied_operand():\n"
        "    return {\n"
        "        'critical_temperature': 2.269185314213022,\n"
        "        'phase': 'ordered_phase',\n"
        "    }\n"
        "def copied_alias():\n"
        "    return copied_operand()\n"
        "def scientific_entry(value):\n"
        "    return copied_alias()\n",
        (TASK6_REGISTERED_OPERAND,),
        ("2.269185314213022", "ordered_phase"),
        id="transitive-helper-copy-alias",
    ),
)


def _task6_fingerprints(*values):
    return tuple(sorted({canonical_sha256(value) for value in values}))


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize(
    "source, forbidden_values, diagnostic_canaries",
    TASK6_EMBEDDED_OUTPUT_CASES,
)
def test_task6_embedded_output_rejects_actual_fingerprint_member(
    tmp_path,
    role,
    source,
    forbidden_values,
    diagnostic_canaries,
):
    from validation import literature_evidence_isolation as isolation

    closure = _task6_build_scientific_closure(tmp_path, role, source)
    fingerprints = _task6_fingerprints(*forbidden_values)
    with pytest.raises(
        AdapterContractError,
        match="static|embedded|fingerprint|literal|lookup|branch|output",
    ) as captured:
        isolation.scan_scientific_closure(
            closure, forbidden_fingerprints=fingerprints
        )

    diagnostic = str(captured.value)
    for canary in diagnostic_canaries:
        assert canary not in diagnostic
    for fingerprint in fingerprints:
        assert fingerprint not in diagnostic


TASK6_CONSTANT_EXPRESSION_BYPASSES = (
    pytest.param(
        "def scientific_entry(value):\n"
        "    return 'ordered_' + 'phase'\n",
        "ordered_phase",
        ("ordered_phase",),
        id="string-concatenation",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    return '%s_phase' % 'ordered'\n",
        "ordered_phase",
        ("ordered_phase",),
        id="constant-percent-formatting",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    return f\"{'ordered'}_{'phase'}\"\n",
        "ordered_phase",
        ("ordered_phase",),
        id="constant-f-string",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    return dict(\n"
        "        critical_temperature=2.269185314213022,\n"
        "        phase='ordered_phase',\n"
        "    )\n",
        TASK6_REGISTERED_OPERAND,
        ("2.269185314213022", "ordered_phase"),
        id="keyword-only-dict-construction",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    return 'xordered_phase'[1:]\n",
        "ordered_phase",
        ("ordered_phase",),
        id="constant-string-slice",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    return ''.join(('ordered', '_', 'phase'))\n",
        "ordered_phase",
        ("ordered_phase",),
        id="constant-string-join",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    return '{}_{}'.format('ordered', 'phase')\n",
        "ordered_phase",
        ("ordered_phase",),
        id="constant-string-format",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    return 'ordered-X'.replace('-X', '_phase')\n",
        "ordered_phase",
        ("ordered_phase",),
        id="unsupported-constant-string-method-fails-closed",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    return f\"{('ordered', '_', 'phase')}\"\n",
        "('ordered', '_', 'phase')",
        ("ordered", "phase"),
        id="constant-f-string-container-operand-fails-closed",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    return '%s' % ['ordered_phase']\n",
        "['ordered_phase']",
        ("ordered_phase",),
        id="percent-container-operand-fails-closed",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    return '{}'.format(['ordered_phase'])\n",
        "['ordered_phase']",
        ("ordered_phase",),
        id="format-container-operand-fails-closed",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    return {\n"
        "        **{'critical_temperature': 2.269185314213022},\n"
        "        **{'phase': 'ordered_phase'},\n"
        "    }\n",
        TASK6_REGISTERED_OPERAND,
        ("2.269185314213022", "ordered_phase"),
        id="constant-dict-unpack",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    return dict([\n"
        "        ('critical_temperature', 2.269185314213022),\n"
        "        ('phase', 'ordered_phase'),\n"
        "    ])\n",
        TASK6_REGISTERED_OPERAND,
        ("2.269185314213022", "ordered_phase"),
        id="constant-positional-dict-construction",
    ),
)


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize(
    "source, forbidden_value, diagnostic_canaries",
    TASK6_CONSTANT_EXPRESSION_BYPASSES,
)
def test_task6_embedded_output_rejects_bounded_constant_expression_bypass(
    tmp_path,
    role,
    source,
    forbidden_value,
    diagnostic_canaries,
):
    from validation import literature_evidence_isolation as isolation

    closure = _task6_build_scientific_closure(tmp_path, role, source)
    fingerprints = _task6_fingerprints(forbidden_value)
    with pytest.raises(
        AdapterContractError,
        match="static|embedded|fingerprint|literal|output",
    ) as captured:
        isolation.scan_scientific_closure(
            closure, forbidden_fingerprints=fingerprints
        )

    diagnostic = str(captured.value)
    for canary in diagnostic_canaries:
        assert canary not in diagnostic
    for fingerprint in fingerprints:
        assert fingerprint not in diagnostic


TASK6_PROPAGATED_CONSTANT_BYPASSES = (
    pytest.param(
        "PREFIX = 'ordered_'\n"
        "SUFFIX = 'phase'\n"
        "def scientific_entry(value):\n"
        "    return PREFIX + SUFFIX\n",
        "ordered_phase",
        ("ordered_phase",),
        id="immutable-module-bindings",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    prefix = 'ordered_'\n"
        "    suffix = 'phase'\n"
        "    return prefix + suffix\n",
        "ordered_phase",
        ("ordered_phase",),
        id="straight-line-local-bindings",
    ),
    pytest.param(
        "def prefix_piece():\n"
        "    return 'ordered_'\n"
        "def suffix_piece():\n"
        "    return 'phase'\n"
        "def scientific_entry(value):\n"
        "    return prefix_piece() + suffix_piece()\n",
        "ordered_phase",
        ("ordered_phase",),
        id="zero-argument-constant-helpers",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    first = {\n"
        "        'critical_temperature': 2.269185314213022,\n"
        "    }\n"
        "    second = {'phase': 'ordered_phase'}\n"
        "    return first | second\n",
        TASK6_REGISTERED_OPERAND,
        ("2.269185314213022", "ordered_phase"),
        id="straight-line-dict-union",
    ),
)


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize(
    "source, forbidden_value, diagnostic_canaries",
    TASK6_PROPAGATED_CONSTANT_BYPASSES,
)
def test_task6_embedded_output_rejects_propagated_constant_composition(
    tmp_path,
    role,
    source,
    forbidden_value,
    diagnostic_canaries,
):
    from validation import literature_evidence_isolation as isolation

    closure = _task6_build_scientific_closure(tmp_path, role, source)
    fingerprints = _task6_fingerprints(forbidden_value)
    with pytest.raises(
        AdapterContractError,
        match="static|embedded|fingerprint|literal|output|constant",
    ) as captured:
        isolation.scan_scientific_closure(
            closure, forbidden_fingerprints=fingerprints
        )

    diagnostic = str(captured.value)
    for canary in diagnostic_canaries:
        assert canary not in diagnostic
    for fingerprint in fingerprints:
        assert fingerprint not in diagnostic


TASK6_EMBEDDED_OUTPUT_CONTROLS = (
    pytest.param(
        "def scientific_entry(value):\n"
        "    return 2.269185314213021\n",
        (2.269185314213022,),
        id="adjacent-high-precision-value",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    return 'ordered_phases'\n",
        ("ordered_phase",),
        id="nearby-categorical-value",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    transport = {'payload': value}\n"
        "    return transport\n",
        (TASK6_REGISTERED_OPERAND,),
        id="pure-transport",
    ),
)


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize(
    "source, forbidden_values", TASK6_EMBEDDED_OUTPUT_CONTROLS
)
def test_task6_embedded_output_allows_nonmember_and_transport_controls(
    tmp_path,
    role,
    source,
    forbidden_values,
):
    from validation import literature_evidence_isolation as isolation

    closure = _task6_build_scientific_closure(tmp_path, role, source)
    report = isolation.scan_scientific_closure(
        closure,
        forbidden_fingerprints=_task6_fingerprints(*forbidden_values),
    )

    assert report.role == role
    assert report.passed is True


def test_task6_lookup_table_rejects_literal_results_without_whole_table_hash(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    source = (
        "def scientific_entry(parameter):\n"
        "    lookup_table = {'0.5': 1.0, '1.0': 2.0}\n"
        "    return lookup_table[str(parameter)]\n"
    )
    closure = _task6_build_scientific_closure(
        tmp_path, "adapter", source
    )
    fingerprints = _task6_fingerprints(1.0, 2.0)
    with pytest.raises(
        AdapterContractError,
        match="static|lookup|literal|result|output",
    ):
        isolation.scan_scientific_closure(
            closure, forbidden_fingerprints=fingerprints
        )


TASK6_INFRASTRUCTURE_PURPOSE_INJECTIONS = (
    pytest.param(
        "    scientific_energy = value * value\n"
        "    return scientific_energy\n",
        "",
        id="scientific-equation",
    ),
    pytest.param(
        "    return build_model_hamiltonian(value)\n",
        "def build_model_hamiltonian(value):\n"
        "    return value * value\n",
        id="hamiltonian-builder",
    ),
    pytest.param(
        "    return derive_method_specific_result_field(value)\n",
        "def derive_method_specific_result_field(value):\n"
        "    return value + value\n",
        id="method-specific-result-field",
    ),
    pytest.param(
        "    if value['adapter_id'] == 'detached_adapter':\n"
        "        return {'computed_field': 1}\n"
        "    return value\n",
        "",
        id="adapter-id-result-derivation",
    ),
    pytest.param(
        "    adapter_definition = {'AdapterDefinition': 'detached'}\n"
        "    return adapter_definition\n",
        "",
        id="adapter-definition",
    ),
    pytest.param(
        "    oracle_definition = {'OracleDefinition': 'detached'}\n"
        "    return oracle_definition\n",
        "",
        id="oracle-definition",
    ),
    pytest.param(
        "    return b'{\"policy\":\"detached\"}'\n",
        "",
        id="policy-bytes",
    ),
    pytest.param(
        "    return caller_designated_extra_root(value)\n",
        "def caller_designated_extra_root(value):\n"
        "    return value\n",
        id="undeclared-extra-root",
    ),
)


@pytest.mark.parametrize(
    "root_body, extra_source", TASK6_INFRASTRUCTURE_PURPOSE_INJECTIONS
)
def test_task6_static_scan_infrastructure_rejects_nontransport_purpose(
    tmp_path,
    root_body,
    extra_source,
):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(
        tmp_path,
        body_by_root={"validate_failure": root_body},
        extra_source_by_module={
            "validation.literature_evidence_isolation": extra_source
        },
    )

    with pytest.raises(
        AdapterContractError,
        match=(
            "(?i)infrastructure.*purpose.*"
            "(scientific|hamiltonian|result|adapter|oracle|policy|root)"
        ),
    ):
        isolation.build_infrastructure_closure(source_roots=(tmp_path,))


def _task6_clean_infrastructure_closure(tmp_path):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(tmp_path)
    return isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )


def test_task6_static_scan_infrastructure_report_is_closed_and_deterministic(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    closure = _task6_clean_infrastructure_closure(tmp_path)
    fingerprints = _task6_absent_fingerprints()
    first = isolation.scan_scientific_closure(
        closure, forbidden_fingerprints=fingerprints
    )
    second = isolation.scan_scientific_closure(
        closure, forbidden_fingerprints=fingerprints
    )

    assert first == second
    assert first.role == "infrastructure"
    assert first.scanned_closure_sha256 == closure.bundle_sha256
    assert set(first.checks) == (
        TASK6_STATIC_SCAN_CHECKS | {"infrastructure_purpose_closed"}
    )
    assert first.passed is True


@pytest.mark.parametrize("mutation", ("missing", "emitted_source"))
def test_task6_static_scan_infrastructure_rejects_material_tamper(
    tmp_path,
    mutation,
):
    from validation import literature_evidence_isolation as isolation

    closure = _task6_clean_infrastructure_closure(tmp_path)
    if mutation == "missing":
        closure = isolation.InfrastructureClosure(
            **{
                field.name: getattr(closure, field.name)
                for field in dataclasses.fields(type(closure))
            }
        )
        assert "_static_scan_material" not in vars(closure)
    else:
        assert "_static_scan_material" in vars(closure)
        material = closure._static_scan_material
        object.__setattr__(
            material,
            "emitted_source",
            material.emitted_source + b" ",
        )

    with pytest.raises(
        AdapterContractError,
        match="static|scan|infrastructure|material|hash|builder",
    ):
        isolation.scan_scientific_closure(
            closure,
            forbidden_fingerprints=_task6_absent_fingerprints(),
        )


TASK6_DEFINITION_POLICY_MUTATIONS = (
    "numeric_fingerprint",
    "numeric_string_fingerprint",
    "categorical_fingerprint",
    "benchmark_proof_binding",
    "answer_lookup_table",
    "fixed_canonical_points",
    "arbitrary_derivation",
    "weakened_domain",
    "post_hoc_threshold",
)


def _task6_mutated_adapter_definition(mutation):
    canonical = adapters.ADAPTER_DEFINITIONS[
        "square_ising_self_dual_tc"
    ]
    payload = thaw_json(
        adapters.adapter_definition_to_frozen_json(canonical)
    )
    requirements = payload["convergence_contract"]["requirements"]
    if mutation == "numeric_fingerprint":
        payload["resource_limits"]["cpu_seconds"] = 2.269185314213022
        canaries = ("2.269185314213022",)
    elif mutation == "numeric_string_fingerprint":
        payload["runtime_requirements"]["backend_resources"].append(
            "2.269185314213022"
        )
        canaries = ("2.269185314213022",)
    elif mutation == "categorical_fingerprint":
        payload["runtime_requirements"]["backend_resources"].append(
            "ordered_phase"
        )
        canaries = ("ordered_phase",)
    elif mutation == "benchmark_proof_binding":
        requirements["benchmark_branch"] = {
            "square_ising_self_dual_tc": "tc_over_j"
        }
        canaries = ("square_ising_self_dual_tc",)
    elif mutation == "answer_lookup_table":
        requirements["lookup_table"] = {
            "exchange_1": 2.269185314213022
        }
        canaries = ("2.269185314213022",)
    elif mutation == "fixed_canonical_points":
        requirements["canonical_points"] = (-2, -1, 0, 1, 2)
        canaries = ("[-2,-1,0,1,2]",)
    elif mutation == "arbitrary_derivation":
        requirements["derivation_expression"] = (
            "lambda exchange: exchange + 2.269185314213022"
        )
        canaries = ("2.269185314213022",)
    elif mutation == "weakened_domain":
        payload["counterfactual_domain"]["valid_rules"]["exchange"] = {
            "kind": "weakened_domain_task6"
        }
        canaries = ("weakened_domain_task6",)
    else:
        requirements["post_hoc_threshold"] = 1e-12
        canaries = ("1e-12",)
    definition = adapters.adapter_definition_from_frozen_json(
        freeze_json(payload)
    )
    return definition, canaries


def _task6_oracle_result_schema(canonical, name, schema):
    return ValueSchema(
        kind="object",
        required=canonical.result_schema.required,
        lower=None,
        upper=None,
        item_schema=None,
        properties=canonical.result_schema.properties + ((name, schema),),
        units="",
    )


def _task6_mutated_oracle_definition(mutation):
    from validation import literature_evidence_adapter_oracles as oracles

    canonical = _synthetic_oracle_definition()
    values = {
        field.name: getattr(canonical, field.name)
        for field in dataclasses.fields(type(canonical))
    }
    if mutation == "numeric_fingerprint":
        limits = canonical.resource_limits
        values["resource_limits"] = ResourceLimits(
            2.269185314213022,
            limits.wall_seconds,
            limits.address_space_bytes,
            limits.output_bytes,
            limits.file_descriptors,
            limits.process_count,
        )
        canaries = ("2.269185314213022",)
    elif mutation == "numeric_string_fingerprint":
        runtime = canonical.runtime_requirements
        values["runtime_requirements"] = RuntimeRequirements(
            runtime.interpreter,
            runtime.packages,
            runtime.native_libraries,
            runtime.backend_resources + ("2.269185314213022",),
        )
        canaries = ("2.269185314213022",)
    elif mutation == "categorical_fingerprint":
        runtime = canonical.runtime_requirements
        values["runtime_requirements"] = RuntimeRequirements(
            runtime.interpreter,
            runtime.packages,
            runtime.native_libraries,
            runtime.backend_resources + ("ordered_phase",),
        )
        canaries = ("ordered_phase",)
    elif mutation == "benchmark_proof_binding":
        values["result_schema"] = _task6_oracle_result_schema(
            canonical,
            "benchmark_branch",
            ValueSchema("boolean", True, None, None, None, (), ""),
        )
        canaries = ("benchmark_branch",)
    elif mutation == "answer_lookup_table":
        values["result_schema"] = _task6_oracle_result_schema(
            canonical,
            "lookup_table",
            _number_schema(
                lower=2.269185314213022,
                upper=2.269185314213022,
            ),
        )
        canaries = ("2.269185314213022",)
    elif mutation == "fixed_canonical_points":
        point_schema = _number_schema(lower=-2, upper=2)
        values["result_schema"] = _task6_oracle_result_schema(
            canonical,
            "canonical_points",
            ValueSchema("list", True, 5, 5, point_schema, (), ""),
        )
        canaries = ("canonical_points",)
    elif mutation == "arbitrary_derivation":
        values["result_schema"] = _task6_oracle_result_schema(
            canonical,
            "derivation_expression",
            _number_schema(lower=None),
        )
        canaries = ("derivation_expression",)
    elif mutation == "weakened_domain":
        schema = canonical.input_schema
        values["input_schema"] = ValueSchema(
            schema.kind,
            False,
            schema.lower,
            schema.upper,
            schema.item_schema,
            schema.properties,
            schema.units,
        )
        canaries = ()
    else:
        values["result_schema"] = _task6_oracle_result_schema(
            canonical,
            "post_hoc_threshold",
            _number_schema(lower=1e-12, upper=1e-12),
        )
        canaries = ("1e-12",)
    return oracles.OracleDefinition(**values), canaries


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize("mutation", TASK6_DEFINITION_POLICY_MUTATIONS)
def test_task6_definition_static_scan_rejects_valid_canonical_mutation(
    monkeypatch,
    role,
    mutation,
):
    from validation import literature_evidence_adapter_oracles as oracles
    from validation import literature_evidence_isolation as isolation

    if role == "adapter":
        definition, canaries = _task6_mutated_adapter_definition(mutation)
        validated = adapters.validate_adapter_definition(definition)
        encoded = adapters.adapter_definition_to_frozen_json(validated)
        assert adapters.adapter_definition_from_frozen_json(encoded) == (
            validated
        )
        catalog = dict(adapters.ADAPTER_DEFINITIONS)
        catalog[validated.adapter_id] = validated
        monkeypatch.setattr(
            adapters,
            "ADAPTER_DEFINITIONS",
            MappingProxyType(catalog),
        )
        closure = _task5_adapter_closure()
    else:
        definition, canaries = _task6_mutated_oracle_definition(mutation)
        validated = oracles.validate_oracle_definition(definition)
        encoded = oracles.oracle_definition_to_frozen_json(validated)
        assert oracles.oracle_definition_from_frozen_json(encoded) == (
            validated
        )
        closure = _task5_oracle_closure()

    with pytest.raises(
        AdapterContractError,
        match=(
            "definition|scientific|policy|fingerprint|categorical|benchmark|"
            "lookup|points|derivation|domain|threshold"
        ),
    ) as captured:
        isolation.build_scientific_policy_commitment(
            validated, closure, role=role
        )
    diagnostic = str(captured.value)
    for canary in canaries:
        assert canary not in diagnostic


def _task6_safely_changed_definition(role):
    if role == "adapter":
        canonical = adapters.ADAPTER_DEFINITIONS[
            "square_ising_self_dual_tc"
        ]
        values = {
            field.name: getattr(canonical, field.name)
            for field in dataclasses.fields(AdapterDefinition)
        }
        limits = canonical.resource_limits
        values["resource_limits"] = ResourceLimits(
            limits.cpu_seconds + 1,
            limits.wall_seconds,
            limits.address_space_bytes,
            limits.output_bytes,
            limits.file_descriptors,
            limits.process_count,
        )
        return AdapterDefinition(**values)
    canonical = _synthetic_oracle_definition()
    values = {
        field.name: getattr(canonical, field.name)
        for field in dataclasses.fields(type(canonical))
    }
    limits = canonical.resource_limits
    values["resource_limits"] = ResourceLimits(
        limits.cpu_seconds + 1,
        limits.wall_seconds,
        limits.address_space_bytes,
        limits.output_bytes,
        limits.file_descriptors,
        limits.process_count,
    )
    return type(canonical)(**values)


def _task6_safely_versioned_resource_definition(role):
    if role == "adapter":
        canonical = adapters.ADAPTER_DEFINITIONS[
            "square_ising_self_dual_tc"
        ]
        values = {
            field.name: getattr(canonical, field.name)
            for field in dataclasses.fields(AdapterDefinition)
        }
    else:
        canonical = _synthetic_oracle_definition()
        values = {
            field.name: getattr(canonical, field.name)
            for field in dataclasses.fields(type(canonical))
        }
    runtime = canonical.runtime_requirements
    values["runtime_requirements"] = RuntimeRequirements(
        runtime.interpreter,
        runtime.packages,
        runtime.native_libraries,
        runtime.backend_resources + ("3.11",),
    )
    return type(canonical)(**values)


@pytest.mark.parametrize("role", ("adapter", "oracle"))
def test_task6_definition_static_scan_allows_ordinary_numeric_version_text(
    monkeypatch,
    role,
):
    from validation import literature_evidence_isolation as isolation

    definition = _task6_safely_versioned_resource_definition(role)
    if role == "adapter":
        catalog = dict(adapters.ADAPTER_DEFINITIONS)
        catalog[definition.adapter_id] = definition
        monkeypatch.setattr(
            adapters,
            "ADAPTER_DEFINITIONS",
            MappingProxyType(catalog),
        )
        closure = _task5_adapter_closure()
    else:
        closure = _task5_oracle_closure()

    commitment = isolation.build_scientific_policy_commitment(
        definition, closure, role=role
    )

    expected_id = (
        definition.adapter_id
        if role == "adapter"
        else definition.oracle_id
    )
    assert commitment.definition_id == expected_id


@pytest.mark.parametrize("role", ("adapter", "oracle"))
def test_task6_definition_static_scan_hash_is_deterministic_and_versioned(
    monkeypatch,
    role,
):
    from validation import literature_evidence_isolation as isolation

    if role == "adapter":
        baseline_definition = adapters.ADAPTER_DEFINITIONS[
            "square_ising_self_dual_tc"
        ]
        closure = _task5_adapter_closure()
    else:
        baseline_definition = _synthetic_oracle_definition()
        closure = _task5_oracle_closure()
    baseline = isolation.build_scientific_policy_commitment(
        baseline_definition, closure, role=role
    )
    changed_definition = _task6_safely_changed_definition(role)
    if role == "adapter":
        catalog = dict(adapters.ADAPTER_DEFINITIONS)
        catalog[changed_definition.adapter_id] = changed_definition
        monkeypatch.setattr(
            adapters,
            "ADAPTER_DEFINITIONS",
            MappingProxyType(catalog),
        )
    first = isolation.build_scientific_policy_commitment(
        changed_definition, closure, role=role
    )
    second = isolation.build_scientific_policy_commitment(
        changed_definition, closure, role=role
    )

    assert first == second
    assert first.canonical_definition_sha256 != (
        baseline.canonical_definition_sha256
    )
    assert first.static_scan_sha256 != baseline.static_scan_sha256
    assert first.combined_sha256 != baseline.combined_sha256
    assert first.static_scan_sha256 != canonical_sha256(
        _task5_legacy_structure_scan(first, closure)
    )


TASK6_SMALL_MATHEMATICAL_VALUES = (-2, -1, -0.5, 0, 0.5, 1, 2)


@pytest.mark.parametrize("role", ("adapter", "oracle"))
def test_task6_static_scan_allows_small_values_in_mathematical_context(
    tmp_path,
    role,
):
    from validation import literature_evidence_isolation as isolation

    source = (
        "SMALL_VALUES = (-2, -1, -0.5, 0, 0.5, 1, 2)\n"
        "def scientific_entry(value, matrix):\n"
        "    dimension = 2\n"
        "    total = 0\n"
        "    for row_index in range(dimension):\n"
        "        total += matrix[row_index][0] + SMALL_VALUES[row_index]\n"
        "    return value + total - matrix[0][1]\n"
    )
    closure = _task6_build_scientific_closure(tmp_path, role, source)
    report = isolation.scan_scientific_closure(
        closure,
        forbidden_fingerprints=_task6_fingerprints(
            *TASK6_SMALL_MATHEMATICAL_VALUES
        ),
    )

    assert report.role == role
    assert report.passed is True


TASK6_SMALL_VALUE_REJECT_CONTEXTS = (
    pytest.param(
        "def scientific_entry(value, benchmark_name):\n"
        "    if benchmark_name == 'task6_benchmark':\n"
        "        return 2\n"
        "    return value\n",
        (2,),
        id="benchmark-literal-return",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    return {'phase_code': 2, 'degeneracy': 1}\n",
        ({"degeneracy": 1, "phase_code": 2},),
        id="field-value-structure",
    ),
    pytest.param(
        "def scientific_entry(parameter):\n"
        "    lookup_table = {'-2': -1, '0': 1, '2': 2}\n"
        "    return lookup_table[str(parameter)]\n",
        (-1, 1, 2),
        id="parameter-result-lookup",
    ),
)


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize(
    "source, forbidden_values", TASK6_SMALL_VALUE_REJECT_CONTEXTS
)
def test_task6_lookup_table_rejects_small_values_in_answer_context(
    tmp_path,
    role,
    source,
    forbidden_values,
):
    from validation import literature_evidence_isolation as isolation

    closure = _task6_build_scientific_closure(tmp_path, role, source)
    with pytest.raises(
        AdapterContractError,
        match="static|lookup|branch|literal|field|output|answer",
    ):
        isolation.scan_scientific_closure(
            closure,
            forbidden_fingerprints=_task6_fingerprints(*forbidden_values),
        )


TASK6_STATIC_SCAN_BOUND_SOURCES = (
    pytest.param(
        "def scientific_entry(value):\n"
        "    return '" + "x" * 1_048_577 + "'\n",
        id="oversized-literal",
    ),
    pytest.param(
        "def scientific_entry(value):\n"
        "    return " + " + ".join("1" for _ in range(1_500)) + "\n",
        id="deep-expression",
    ),
    pytest.param(
        "def scientific_entry(parameter):\n"
        "    lookup_table = {\n"
        + "".join(
            f"        '{index}': {index},\n" for index in range(3_000)
        )
        + "    }\n"
        "    return lookup_table[str(parameter)]\n",
        id="oversized-lookup",
    ),
)


TASK6_EVALUATED_OUTPUT_BOUND_EXPRESSIONS = (
    pytest.param("'abcdefgh' * 5", 32, id="string-multiplication"),
    pytest.param(
        "''.join(('abcdefgh', 'abcdefgh', 'abcdefgh', 'abcdefgh', 'a'))",
        32,
        id="constant-join",
    ),
    pytest.param(
        "'%10s%10s%10s%10s' % ('a', 'b', 'c', 'd')",
        32,
        id="percent-formatting",
    ),
    pytest.param(
        "f\"{'abcdefgh'}{'abcdefgh'}{'abcdefgh'}{'abcdefgh'}{'a'}\"",
        32,
        id="constant-f-string",
    ),
    pytest.param(
        "'{:>10}{:>10}{:>10}{:>10}'.format('a', 'b', 'c', 'd')",
        32,
        id="constant-format-method",
    ),
    pytest.param("'你你' + '你你'", 10, id="utf8-byte-accounting"),
    pytest.param(
        "{'dictionary_key_definitely_exceeds_tiny_limit': 1}",
        32,
        id="dict-key-accounting",
    ),
)


@pytest.mark.parametrize(
    "expression, evaluated_output_limit",
    TASK6_EVALUATED_OUTPUT_BOUND_EXPRESSIONS,
)
def test_task6_static_scan_preflights_constant_output_allocation_bound(
    tmp_path,
    monkeypatch,
    expression,
    evaluated_output_limit,
):
    from validation import literature_evidence_isolation as isolation

    source = (
        "def scientific_entry(value):\n"
        f"    return {expression}\n"
    )
    closure = _task6_build_scientific_closure(
        tmp_path, "adapter", source
    )
    monkeypatch.setattr(
        isolation,
        "_STATIC_SCAN_EVALUATED_OUTPUT_BYTES_LIMIT",
        evaluated_output_limit,
    )

    with pytest.raises(
        AdapterContractError,
        match="static|scan|constant|output|byte|bound|format|allocation",
    ):
        isolation.scan_scientific_closure(
            closure,
            forbidden_fingerprints=_task6_absent_fingerprints(),
        )


def test_task6_static_scan_rejects_fingerprint_count_before_items(
    tmp_path,
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    closure = _task6_safe_scan_closure(tmp_path)
    monkeypatch.setattr(
        isolation, "_STATIC_SCAN_FINGERPRINT_COUNT_LIMIT", 2
    )

    with pytest.raises(
        AdapterContractError,
        match="fingerprint.*count|count.*bound|fingerprint.*bound",
    ):
        isolation.scan_scientific_closure(
            closure,
            forbidden_fingerprints=("not-a-digest",) * 3,
        )


def test_task6_closure_builder_preflights_aggregate_material_before_join(
    tmp_path,
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    monkeypatch.setattr(
        isolation, "_STATIC_SCAN_AGGREGATE_MATERIAL_BYTES_LIMIT", 64
    )
    source = (
        "def helper(value):\n"
        "    return value + 1\n"
        "def scientific_entry(value):\n"
        "    return helper(value)\n"
    )

    with pytest.raises(
        AdapterContractError,
        match="aggregate|material|emitted|raw|byte|bound|source",
    ):
        _task6_build_scientific_closure(
            tmp_path, "adapter", source
        )


def test_task6_static_scan_revalidates_aggregate_material_bound(
    tmp_path,
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    closure = _task6_safe_scan_closure(tmp_path)
    material = closure._static_scan_material
    aggregate_size = max(
        sum(len(node.raw_source_span) for node in material.nodes),
        len(material.emitted_source),
    )
    monkeypatch.setattr(
        isolation,
        "_STATIC_SCAN_AGGREGATE_MATERIAL_BYTES_LIMIT",
        aggregate_size - 1,
    )

    with pytest.raises(
        AdapterContractError,
        match="aggregate|material|emitted|raw|byte|bound|source",
    ):
        isolation.scan_scientific_closure(
            closure,
            forbidden_fingerprints=_task6_absent_fingerprints(),
        )


def test_task6_static_scan_bounds_combined_ast_before_raw_node_scans(
    tmp_path,
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    closure = _task6_safe_scan_closure(tmp_path)
    monkeypatch.setattr(
        isolation, "_STATIC_SCAN_AGGREGATE_AST_NODE_LIMIT", 1
    )
    raw_scan_calls = []

    def unexpected_raw_scan(*args, **kwargs):
        raw_scan_calls.append((args, kwargs))
        raise AssertionError("raw scan ran before aggregate AST preflight")

    monkeypatch.setattr(isolation, "_scan_static_ast", unexpected_raw_scan)
    with pytest.raises(
        AdapterContractError,
        match="static|combined|aggregate|AST|node|bound",
    ):
        isolation.scan_scientific_closure(
            closure,
            forbidden_fingerprints=_task6_absent_fingerprints(),
        )
    assert raw_scan_calls == []


def test_task6_combined_ast_scan_uses_aggregate_not_per_node_budget(
    tmp_path,
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    source = (
        "def helper(value):\n"
        "    return value + 1\n"
        "def scientific_entry(value):\n"
        "    return helper(value)\n"
    )
    closure = _task6_build_scientific_closure(
        tmp_path, "adapter", source
    )
    material = closure._static_scan_material
    raw_counts = tuple(
        sum(
            1
            for _node in ast.walk(
                ast.parse(item.raw_source_span.decode("utf-8"))
            )
        )
        for item in material.nodes
    )
    combined_count = sum(
        1
        for _node in ast.walk(
            ast.parse(material.emitted_source.decode("utf-8"))
        )
    )
    per_node_limit = max(raw_counts)
    assert combined_count > per_node_limit
    monkeypatch.setattr(
        isolation, "_STATIC_SCAN_NODE_LIMIT", per_node_limit
    )
    monkeypatch.setattr(
        isolation,
        "_STATIC_SCAN_AGGREGATE_AST_NODE_LIMIT",
        combined_count,
    )

    report = isolation.scan_scientific_closure(
        closure,
        forbidden_fingerprints=_task6_absent_fingerprints(),
    )

    assert report.passed is True


@pytest.mark.parametrize("source", TASK6_STATIC_SCAN_BOUND_SOURCES)
def test_task6_static_scan_bounds_literal_depth_and_lookup_size(
    tmp_path,
    source,
):
    from validation import literature_evidence_isolation as isolation

    with pytest.raises(
        AdapterContractError,
        match="static|scan|literal|lookup|bound|oversized|depth|source",
    ):
        closure = _task6_build_scientific_closure(
            tmp_path, "adapter", source
        )
        isolation.scan_scientific_closure(
            closure,
            forbidden_fingerprints=_task6_absent_fingerprints(),
        )


@pytest.mark.parametrize("mutation", ("too_many_checks", "long_reason"))
def test_task6_static_scan_report_rejects_unbounded_checks_and_reasons(
    tmp_path,
    mutation,
):
    from validation import literature_evidence_isolation as isolation

    closure = _task6_safe_scan_closure(tmp_path)
    report = isolation.scan_scientific_closure(
        closure,
        forbidden_fingerprints=_task6_absent_fingerprints(),
    )
    values = {
        field.name: getattr(report, field.name)
        for field in dataclasses.fields(type(report))
    }
    if mutation == "too_many_checks":
        values["checks"] = {
            f"closed_check_{index}": {"passed": True, "reason": "closed"}
            for index in range(257)
        }
    else:
        values["checks"] = thaw_json(report.checks)
        first_key = sorted(values["checks"])[0]
        values["checks"][first_key]["reason"] = "r" * 161
    values["report_sha256"] = canonical_sha256(
        {
            key: item
            for key, item in values.items()
            if key != "report_sha256"
        }
    )

    with pytest.raises(
        AdapterContractError,
        match="static|scan|check|reason|bound|oversized",
    ):
        isolation.StaticScanReport(**values)


TASK6_REVIEW_CONSTANT_FLOW_BYPASSES = (
    pytest.param(
        "def scientific_entry(parameter):\n"
        "    return bytes((111, 114, 100, 101, 114, 101, 100, 95, "
        "112, 104, 97, 115, 101)).decode()\n",
        "ordered_phase",
        id="bytes-constructor-decode-chain",
    ),
    pytest.param(
        "def prefix_piece(ignored):\n"
        "    return 'ordered_'\n"
        "def suffix_piece(value):\n"
        "    return value\n"
        "def scientific_entry(parameter):\n"
        "    return prefix_piece(parameter) + suffix_piece('phase')\n",
        "ordered_phase",
        id="parameterized-helper-constant-argument",
    ),
    pytest.param(
        "def choose_piece(flag, piece):\n"
        "    if flag:\n"
        "        selected = piece\n"
        "    else:\n"
        "        selected = piece\n"
        "    return selected\n"
        "def scientific_entry(parameter):\n"
        "    return choose_piece(parameter, 'ordered_') + 'phase'\n",
        "ordered_phase",
        id="parameterized-helper-branch-join",
    ),
    pytest.param(
        "def scientific_entry(parameter):\n"
        "    payload = {}\n"
        "    payload['critical_temperature'] = 2.269185314213022\n"
        "    payload['phase'] = 'ordered_phase'\n"
        "    return payload\n",
        TASK6_REGISTERED_OPERAND,
        id="incremental-dict-construction",
    ),
)


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize(
    "source, forbidden_value", TASK6_REVIEW_CONSTANT_FLOW_BYPASSES
)
def test_task6_review_rejects_constant_flow_bypasses_without_operand_leak(
    tmp_path,
    role,
    source,
    forbidden_value,
):
    from validation import literature_evidence_isolation as isolation

    closure = _task6_build_scientific_closure(tmp_path, role, source)
    fingerprints = _task6_fingerprints(forbidden_value)
    with pytest.raises(
        AdapterContractError,
        match="static|constant|fingerprint|output|parameter|container",
    ) as captured:
        isolation.scan_scientific_closure(
            closure, forbidden_fingerprints=fingerprints
        )

    diagnostic = str(captured.value)
    assert repr(forbidden_value) not in diagnostic
    assert str(forbidden_value) not in diagnostic
    for fingerprint in fingerprints:
        assert fingerprint not in diagnostic


@pytest.mark.parametrize("role", ("adapter", "oracle"))
def test_task6_review_rejects_anonymous_mapping_indexed_by_parameter(
    tmp_path,
    role,
):
    from validation import literature_evidence_isolation as isolation

    source = (
        "def scientific_entry(phase_key):\n"
        "    values = {\n"
        "        'alpha': -2,\n"
        "        'beta': -1,\n"
        "        'gamma': -0.5,\n"
        "        'delta': 0,\n"
        "        'epsilon': 0.5,\n"
        "        'zeta': 1,\n"
        "        'eta': 2,\n"
        "    }\n"
        "    return values[phase_key]\n"
    )
    closure = _task6_build_scientific_closure(tmp_path, role, source)

    with pytest.raises(
        AdapterContractError,
        match="static|literal|mapping|sequence|parameter|index",
    ):
        isolation.scan_scientific_closure(
            closure,
            forbidden_fingerprints=_task6_fingerprints(
                *TASK6_SMALL_MATHEMATICAL_VALUES
            ),
        )


TASK6_FILE_CAPABILITY_SOURCES = (
    pytest.param(
        "import numpy as np\n"
        "def scientific_entry(parameter):\n"
        "    return np.load('detached.npy')\n",
        id="numpy-import-alias-load",
    ),
    pytest.param(
        "from numpy import fromfile as restore\n"
        "def scientific_entry(parameter):\n"
        "    return restore('detached.bin')\n",
        id="numpy-from-import-alias-fromfile",
    ),
    pytest.param(
        "import numpy as np\n"
        "def scientific_entry(parameter):\n"
        "    return np.lib.npyio.load('detached.npy')\n",
        id="numpy-attribute-chain-load",
    ),
    pytest.param(
        "from numpy import memmap\n"
        "def scientific_entry(parameter):\n"
        "    return memmap('detached.bin')\n",
        id="numpy-memmap",
    ),
    pytest.param(
        "from numpy import loadtxt\n"
        "def scientific_entry(parameter):\n"
        "    return loadtxt('detached.txt')\n",
        id="numpy-loadtxt",
    ),
    pytest.param(
        "import numpy as np\n"
        "def scientific_entry(parameter):\n"
        "    return np.genfromtxt('detached.txt')\n",
        id="numpy-genfromtxt",
    ),
    pytest.param(
        "import scipy.io as sio\n"
        "def scientific_entry(parameter):\n"
        "    return sio.loadmat('detached.mat')\n",
        id="scipy-io-import-alias",
    ),
    pytest.param(
        "from scipy import io as sio\n"
        "def scientific_entry(parameter):\n"
        "    return sio.mmread('detached.mtx')\n",
        id="scipy-from-import-attribute-chain",
    ),
    pytest.param(
        "from scipy.io import netcdf_file as reader\n"
        "def scientific_entry(parameter):\n"
        "    return reader('detached.nc')\n",
        id="scipy-io-reader-alias",
    ),
)


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize("source", TASK6_FILE_CAPABILITY_SOURCES)
def test_task6_review_rejects_file_capabilities_by_exact_callable_path(
    tmp_path,
    role,
    source,
):
    with pytest.raises(
        AdapterContractError,
        match="approved|capability|file|reader|import|call",
    ):
        _task6_build_and_scan(tmp_path, role, source)


TASK6_REVIEW_CAPABILITY_OBJECT_SOURCES = (
    pytest.param(
        "{import_numpy}"
        "def scientific_entry(parameter):\n"
        "    load_array = {numpy_name}.load\n"
        "    return load_array('detached.npy')\n",
        id="assigned-numpy-load",
    ),
    pytest.param(
        "{import_numpy}"
        "def scientific_entry(parameter):\n"
        "    operations = ({numpy_name}.load,)\n"
        "    return operations[0]('detached.npy')\n",
        id="tuple-contained-numpy-load",
    ),
    pytest.param(
        "{import_numpy}"
        "def scientific_entry(parameter):\n"
        "    operations = [{numpy_name}.load]\n"
        "    return operations[0]('detached.npy')\n",
        id="list-contained-numpy-load",
    ),
    pytest.param(
        "{import_numpy}"
        "def scientific_entry(parameter):\n"
        "    operations = {{'read': {numpy_name}.load}}\n"
        "    return operations['read']('detached.npy')\n",
        id="dict-contained-numpy-load",
    ),
    pytest.param(
        "{import_numpy}"
        "def scientific_entry(parameter):\n"
        "    array_module = {numpy_name}\n"
        "    load_array = array_module.load\n"
        "    return load_array('detached.npy')\n",
        id="reused-numpy-module-name-and-attribute",
    ),
    pytest.param(
        "import numpy as local_array_lib\n"
        "def unrelated_shadow(local_array_lib):\n"
        "    return local_array_lib\n"
        "def scientific_entry(parameter):\n"
        "    unrelated_shadow(parameter)\n"
        "    return local_array_lib.load('detached.npy')\n",
        id="module-alias-shadowed-only-in-unrelated-function",
    ),
    pytest.param(
        "{import_numpy}"
        "def scientific_entry(parameter):\n"
        "    return {numpy_name}.load.__call__('detached.npy')\n",
        id="numpy-load-call-attribute",
    ),
    pytest.param(
        "{import_scipy}"
        "def scientific_entry(parameter):\n"
        "    load_matrix = {scipy_name}.io.loadmat\n"
        "    return load_matrix('detached.mat')\n",
        id="assigned-scipy-io-loadmat",
    ),
)


TASK6_REVIEW3_MODULE_OBJECT_ESCAPE_SOURCES = (
    pytest.param(
        "{import_numpy}"
        "def scientific_entry(parameter):\n"
        "    modules = ({numpy_name},)\n"
        "    return modules[0].load('detached.npy')\n",
        id="tuple-contained-numpy-module",
    ),
    pytest.param(
        "{import_numpy}"
        "def scientific_entry(parameter):\n"
        "    modules = [{numpy_name}]\n"
        "    return modules[0].load('detached.npy')\n",
        id="list-contained-numpy-module",
    ),
    pytest.param(
        "{import_numpy}"
        "def scientific_entry(parameter):\n"
        "    modules = {{'array': {numpy_name}}}\n"
        "    return modules['array'].load('detached.npy')\n",
        id="dict-contained-numpy-module",
    ),
    pytest.param(
        "{import_numpy}"
        "def consume(array_module):\n"
        "    return array_module.load('detached.npy')\n"
        "def scientific_entry(parameter):\n"
        "    return consume({numpy_name})\n",
        id="numpy-module-helper-argument",
    ),
    pytest.param(
        "{import_numpy}"
        "def scientific_entry(parameter):\n"
        "    array_module = {numpy_name}\n"
        "    payload = array_module.load('detached.npy')\n"
        "    array_module = parameter\n"
        "    return payload\n",
        id="later-store-does-not-erase-numpy-flow",
    ),
    pytest.param(
        "{import_numpy}"
        "def unrelated_shadow({numpy_name}):\n"
        "    return {numpy_name}\n"
        "def scientific_entry(parameter):\n"
        "    return {numpy_name}.load('detached.npy')\n",
        id="other-function-parameter-does-not-shadow-numpy-import",
    ),
    pytest.param(
        "{import_scipy}"
        "def scientific_entry(parameter):\n"
        "    return ({scipy_name},)[0].io.loadmat('detached.mat')\n",
        id="subscripted-scipy-module",
    ),
    pytest.param(
        "{import_numpy}"
        "def scientific_entry(parameter):\n"
        "    return {numpy_name}\n",
        id="returned-numpy-module",
    ),
)


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize("scan_scope", ("raw", "aggregate"))
@pytest.mark.parametrize(
    "source_template", TASK6_REVIEW_CAPABILITY_OBJECT_SOURCES
)
def test_task6_review_rejects_reused_external_capability_objects(
    tmp_path,
    role,
    scan_scope,
    source_template,
):
    from validation import literature_evidence_isolation as isolation

    if scan_scope == "raw":
        imports = {
            "import_numpy": "import numpy\n",
            "numpy_name": "numpy",
            "import_scipy": "import scipy\n",
            "scipy_name": "scipy",
        }
    else:
        imports = {
            "import_numpy": "import numpy as np\n",
            "numpy_name": "np",
            "import_scipy": "import scipy as sp\n",
            "scipy_name": "sp",
        }
    source = source_template.format(**imports)
    closure = _task6_build_scientific_closure(tmp_path, role, source)

    with pytest.raises(
        AdapterContractError,
        match="approved|capability|file|reader|import|call|static",
    ):
        isolation.scan_scientific_closure(
            closure,
            forbidden_fingerprints=_task6_absent_fingerprints(),
        )


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize("scan_scope", ("raw", "aggregate"))
@pytest.mark.parametrize(
    "source_template", TASK6_REVIEW3_MODULE_OBJECT_ESCAPE_SOURCES
)
def test_task6_review3_rejects_external_module_object_escape(
    tmp_path,
    role,
    scan_scope,
    source_template,
):
    from validation import literature_evidence_isolation as isolation

    if scan_scope == "raw":
        imports = {
            "import_numpy": "import numpy\n",
            "numpy_name": "numpy",
            "import_scipy": "import scipy\n",
            "scipy_name": "scipy",
        }
    else:
        imports = {
            "import_numpy": "import numpy as np\n",
            "numpy_name": "np",
            "import_scipy": "import scipy as sp\n",
            "scipy_name": "sp",
        }
    source = source_template.format(**imports)
    closure = _task6_build_scientific_closure(tmp_path, role, source)

    with pytest.raises(
        AdapterContractError,
        match="static|module|capability|escape|import|file|reader",
    ):
        isolation.scan_scientific_closure(
            closure,
            forbidden_fingerprints=_task6_absent_fingerprints(),
        )


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize("scan_scope", ("raw", "aggregate"))
def test_task6_review3_current_scope_parameter_shadows_module_import(
    tmp_path,
    role,
    scan_scope,
):
    if scan_scope == "raw":
        import_source = "import numpy\n"
        module_name = "numpy"
    else:
        import_source = "import numpy as np\n"
        module_name = "np"
    source = (
        import_source
        + f"def scientific_entry({module_name}, parameter):\n"
        + f"    return {module_name}.sin(parameter)\n"
    )

    report = _task6_build_and_scan(tmp_path, role, source)

    assert report.passed is True


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize("scan_scope", ("raw", "aggregate"))
def test_task6_review3_later_store_does_not_erase_prior_direct_capability(
    tmp_path,
    role,
    scan_scope,
):
    if scan_scope == "raw":
        import_source = "import numpy\n"
        module_name = "numpy"
    else:
        import_source = "import numpy as np\n"
        module_name = "np"
    source = (
        import_source
        + "def scientific_entry(parameter):\n"
        + f"    payload = {module_name}.load('detached.npy')\n"
        + f"    {module_name} = parameter\n"
        + "    return payload\n"
    )

    with pytest.raises(
        AdapterContractError,
        match="static|capability|file|reader|import|call",
    ):
        _task6_build_and_scan(tmp_path, role, source)


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize("scan_scope", ("raw", "aggregate"))
def test_task6_review3_prior_store_shadows_later_module_spelling(
    tmp_path,
    role,
    scan_scope,
):
    if scan_scope == "raw":
        import_source = "import numpy\n"
        module_name = "numpy"
    else:
        import_source = "import numpy as np\n"
        module_name = "np"
    source = (
        import_source
        + "def scientific_entry(parameter):\n"
        + f"    {module_name} = parameter\n"
        + f"    return {module_name}.sin(parameter)\n"
    )

    report = _task6_build_and_scan(tmp_path, role, source)

    assert report.passed is True


@pytest.mark.parametrize("role", ("adapter", "oracle"))
def test_task6_review3_unknown_external_constant_fails_closed(
    tmp_path,
    role,
):
    source = (
        "import numpy as np\n"
        "def scientific_entry(parameter):\n"
        "    return np.not_a_committed_constant + parameter\n"
    )

    with pytest.raises(
        AdapterContractError,
        match="static|external|constant|allow|approved|reference",
    ):
        _task6_build_and_scan(tmp_path, role, source)


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize(
    "module_name, callable_suffix",
    (
        pytest.param(
            "numpy",
            "not_a_committed_callable(parameter)",
            id="numpy-shallow",
        ),
        pytest.param(
            "numpy",
            "uncommitted_namespace.uncommitted_callable(parameter)",
            id="numpy-deep",
        ),
        pytest.param(
            "scipy",
            "not_a_committed_callable(parameter)",
            id="scipy-shallow",
        ),
        pytest.param(
            "scipy",
            "integrate.not_a_committed_callable(parameter)",
            id="scipy-deep",
        ),
    ),
)
@pytest.mark.parametrize("scan_scope", ("raw", "aggregate"))
def test_task6_review4_unknown_external_callable_fails_closed(
    tmp_path,
    role,
    module_name,
    callable_suffix,
    scan_scope,
):
    local_name = (
        module_name
        if scan_scope == "raw"
        else {"numpy": "np", "scipy": "sp"}[module_name]
    )
    import_source = (
        f"import {module_name}\n"
        if scan_scope == "raw"
        else f"import {module_name} as {local_name}\n"
    )
    source = (
        import_source
        + "def scientific_entry(parameter):\n"
        + f"    return {local_name}.{callable_suffix}\n"
    )

    with pytest.raises(
        AdapterContractError,
        match="static|external|numeric|callable|allow|approved|reference",
    ):
        _task6_build_and_scan(tmp_path, role, source)


@pytest.mark.parametrize("role", ("adapter", "oracle"))
def test_task6_review_keeps_approved_pure_numeric_capabilities(
    tmp_path,
    role,
):
    source = (
        "import numpy as np\n"
        "from scipy.integrate import quad\n"
        "def scientific_entry(parameter, matrix):\n"
        "    eigenvalues = np.linalg.eigvalsh(matrix)\n"
        "    integral, error = quad(np.sin, 0.0, parameter)\n"
        "    return np.sqrt(eigenvalues[0] ** 2) + integral + error\n"
    )

    report = _task6_build_and_scan(tmp_path, role, source)

    assert report.role == role
    assert report.passed is True


@pytest.mark.parametrize("role", ("adapter", "oracle"))
def test_task6_review4_keeps_exactly_committed_numeric_callables(
    tmp_path,
    role,
):
    source = (
        "import numpy as np\n"
        "import scipy\n"
        "def scientific_entry(parameter, matrix):\n"
        "    direct_sine = np.sin(parameter)\n"
        "    numpy_values, _ = np.linalg.eigh(matrix)\n"
        "    scipy_values, _ = scipy.linalg.eigh(matrix)\n"
        "    integral, error = scipy.integrate.quad(\n"
        "        np.sin, 0.0, parameter\n"
        "    )\n"
        "    return (\n"
        "        direct_sine + numpy_values[0] + scipy_values[0]\n"
        "        + integral + error\n"
        "    )\n"
    )

    report = _task6_build_and_scan(tmp_path, role, source)

    assert report.role == role
    assert report.passed is True


@pytest.mark.parametrize("role", ("adapter", "oracle"))
def test_task6_review3_keeps_exactly_allowlisted_numeric_constants(
    tmp_path,
    role,
):
    source = (
        "import numpy as np\n"
        "def scientific_entry(parameter):\n"
        "    return np.pi + np.e + np.inf + parameter\n"
    )

    report = _task6_build_and_scan(tmp_path, role, source)

    assert report.role == role
    assert report.passed is True


TASK6_CASE_SENSITIVE_NUMERIC_PATHS = (
    pytest.param(
        "import numpy as np\n"
        "def scientific_entry(parameter):\n"
        "    return np.Sin(parameter)\n",
        id="numpy-callable-case",
    ),
    pytest.param(
        "import numpy as np\n"
        "def scientific_entry(parameter, matrix):\n"
        "    return np.LINALG.eigh(matrix)[0][0] + parameter\n",
        id="numpy-namespace-case",
    ),
    pytest.param(
        "import scipy\n"
        "def scientific_entry(parameter):\n"
        "    return scipy.Integrate.quad(abs, 0, parameter)\n",
        id="scipy-namespace-case",
    ),
    pytest.param(
        "import numpy as np\n"
        "def scientific_entry(parameter):\n"
        "    return np.PI + parameter\n",
        id="numpy-constant-case",
    ),
    pytest.param(
        "import numpy as np\n"
        "def scientific_entry(NP, parameter):\n"
        "    payload = np.load('detached.npy')\n"
        "    return np.Sin(parameter) + np.PI + payload[0]\n",
        id="case-distinct-parameter-cannot-shadow-import",
    ),
)


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize("scan_scope", ("raw", "aggregate"))
@pytest.mark.parametrize("source", TASK6_CASE_SENSITIVE_NUMERIC_PATHS)
def test_task6_review5_rejects_case_variant_numeric_paths_publicly(
    tmp_path,
    role,
    scan_scope,
    source,
):
    if scan_scope == "raw":
        source = source.replace(" as np", "").replace("np.", "numpy.")
        source = source.replace("NP, parameter", "NUMPY, parameter")

    with pytest.raises(
        AdapterContractError,
        match="static|external|numeric|callable|constant|approved|capability",
    ):
        _task6_build_and_scan(tmp_path, role, source)


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize("scan_scope", ("raw", "aggregate"))
def test_task6_review5_keeps_exact_lowercase_numeric_paths_publicly(
    tmp_path,
    role,
    scan_scope,
):
    import_source = (
        "import numpy\n" if scan_scope == "raw" else "import numpy as np\n"
    )
    module_name = "numpy" if scan_scope == "raw" else "np"
    source = (
        import_source
        + "def scientific_entry(parameter, matrix):\n"
        + f"    values, _ = {module_name}.linalg.eigh(matrix)\n"
        + f"    return {module_name}.sin(parameter) + {module_name}.pi "
        + "+ values[0]\n"
    )

    report = _task6_build_and_scan(tmp_path, role, source)

    assert report.passed is True


@pytest.mark.parametrize("destination", ("setter", "deleter"))
def test_task6_review5_property_commitment_preserves_named_slots(
    monkeypatch,
    destination,
):
    from validation import literature_evidence_isolation as isolation

    owner = next(candidate for candidate in Path.__mro__ if "parts" in vars(candidate))
    original = vars(owner)["parts"]
    baseline = isolation._current_static_scanner_sha256()
    if destination == "setter":
        changed = property(None, original.fget, None, original.__doc__)
    else:
        changed = property(None, None, original.fget, original.__doc__)
    monkeypatch.setattr(owner, "parts", changed)

    changed_sha256 = isolation._current_static_scanner_sha256()

    assert changed_sha256 != baseline


@pytest.mark.parametrize(
    "member_name, source",
    (
        pytest.param(
            "visit_Name",
            "def scientific_entry(parameter):\n"
            "    prefix = 'ordered_'\n"
            "    return prefix + 'phase'\n",
            id="propagated-name-binding",
        ),
        pytest.param(
            "visit_Call",
            "def prefix_piece():\n"
            "    return 'ordered_'\n"
            "def scientific_entry(parameter):\n"
            "    return prefix_piece() + 'phase'\n",
            id="propagated-helper-call",
        ),
    ),
)
def test_task6_review5_dynamic_visitor_binding_changes_commitment_and_verdict(
    tmp_path,
    monkeypatch,
    member_name,
    source,
):
    from validation import literature_evidence_isolation as isolation

    closure = _task6_build_scientific_closure(tmp_path, "adapter", source)
    fingerprints = _task6_fingerprints("ordered_phase")
    with pytest.raises(
        AdapterContractError,
        match="static|constant|fingerprint|output",
    ):
        isolation.scan_scientific_closure(
            closure, forbidden_fingerprints=fingerprints
        )
    baseline = isolation._current_static_scanner_sha256()
    calls = []

    def replacement(self, node):
        calls.append((self, node))
        return node

    monkeypatch.setattr(
        isolation._StaticConstantBindingSubstituter,
        member_name,
        replacement,
    )
    changed_sha256 = isolation._current_static_scanner_sha256()

    assert calls == []
    assert changed_sha256 != baseline
    changed_report = isolation.scan_scientific_closure(
        closure, forbidden_fingerprints=fingerprints
    )
    assert changed_report.passed is True
    assert calls


@pytest.mark.parametrize(
    "class_name, member_name",
    (
        pytest.param(
            "_AstClosureResolver",
            "__init__",
            id="constructed-resolver-init",
        ),
        pytest.param(
            "_StaticConstantBindingSubstituter",
            "__init__",
            id="constructed-transformer-init",
        ),
        pytest.param(
            "ScientificPolicyCommitment",
            "__post_init__",
            id="constructed-policy-post-init",
        ),
    ),
)
def test_task6_review6_actual_project_lifecycle_changes_commitment_without_execution(
    monkeypatch,
    class_name,
    member_name,
):
    from validation import literature_evidence_isolation as isolation

    project_class = getattr(isolation, class_name, None)
    if project_class is None:
        project_class = getattr(adapters, class_name)
    owner = next(
        candidate
        for candidate in project_class.__mro__
        if member_name in vars(candidate)
    )
    original = vars(owner)[member_name]
    calls = []

    def replacement(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    baseline = isolation._current_static_scanner_sha256()
    monkeypatch.setattr(owner, member_name, replacement)
    changed_sha256 = isolation._current_static_scanner_sha256()
    monkeypatch.undo()

    assert calls == []
    assert changed_sha256 != baseline


def test_task6_review6_constructed_error_class_identity_and_mro_are_committed(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    class SpoofedContractError(AdapterContractError):
        pass

    SpoofedContractError.__module__ = AdapterContractError.__module__
    SpoofedContractError.__qualname__ = AdapterContractError.__qualname__
    baseline = isolation._current_static_scanner_sha256()
    monkeypatch.setattr(isolation, "_ContractError", SpoofedContractError)
    changed_sha256 = isolation._current_static_scanner_sha256()
    monkeypatch.undo()

    assert changed_sha256 != baseline


def test_task6_review6_actual_classmethod_slot_changes_commitment(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    original = vars(FrozenJsonObject)["_from_frozen_items"]
    assert type(original) is classmethod
    calls = []

    def replacement(cls, items):
        calls.append((cls, items))
        return original.__func__(cls, items)

    baseline = isolation._current_static_scanner_sha256()
    monkeypatch.setattr(
        FrozenJsonObject,
        "_from_frozen_items",
        classmethod(replacement),
    )
    changed_sha256 = isolation._current_static_scanner_sha256()
    monkeypatch.undo()

    assert calls == []
    assert changed_sha256 != baseline


@pytest.mark.parametrize(
    "class_name, member_name, replacement_kind",
    (
        pytest.param(
            "_AstClosureResolver",
            "_record_loaded_globals",
            "classmethod",
            id="staticmethod-to-classmethod",
        ),
        pytest.param(
            "_AstClosureResolver",
            "_record_loaded_globals",
            "ordinary",
            id="staticmethod-to-ordinary",
        ),
        pytest.param(
            "_AstClosureResolver",
            "resolve_symbol",
            "staticmethod",
            id="ordinary-to-staticmethod",
        ),
        pytest.param(
            "FrozenJsonObject",
            "_from_frozen_items",
            "staticmethod",
            id="classmethod-to-staticmethod",
        ),
    ),
)
def test_task6_review6_actual_descriptor_wrapper_kind_changes_commitment(
    monkeypatch,
    class_name,
    member_name,
    replacement_kind,
):
    from validation import literature_evidence_isolation as isolation

    project_class = getattr(isolation, class_name, None)
    if project_class is None:
        project_class = getattr(adapters, class_name)
    original = vars(project_class)[member_name]
    function = getattr(original, "__func__", original)
    wrappers = {
        "classmethod": classmethod,
        "ordinary": lambda value: value,
        "staticmethod": staticmethod,
    }
    baseline = isolation._current_static_scanner_sha256()
    monkeypatch.setattr(
        project_class,
        member_name,
        wrappers[replacement_kind](function),
    )
    changed_sha256 = isolation._current_static_scanner_sha256()
    monkeypatch.undo()

    assert changed_sha256 != baseline


@pytest.mark.parametrize("mutation", ("field-order", "field-metadata"))
def test_task6_review6_actual_dataclass_field_semantics_change_commitment(
    monkeypatch,
    mutation,
):
    from validation import literature_evidence_isolation as isolation

    project_class = isolation.ScientificPolicyCommitment
    fields_by_name = vars(project_class)["__dataclass_fields__"]
    baseline = isolation._current_static_scanner_sha256()
    if mutation == "field-order":
        monkeypatch.setattr(
            project_class,
            "__dataclass_fields__",
            dict(reversed(tuple(fields_by_name.items()))),
        )
    else:
        first_field = next(iter(fields_by_name.values()))
        monkeypatch.setattr(
            first_field,
            "metadata",
            MappingProxyType({"review_canary": "changed"}),
        )

    changed_sha256 = isolation._current_static_scanner_sha256()
    monkeypatch.undo()

    assert changed_sha256 != baseline


def test_task6_review6_actual_enum_member_semantics_change_commitment(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    member = isolation._InfrastructureNumericProvenance.NUMERIC_LITERAL
    baseline = isolation._current_static_scanner_sha256()
    monkeypatch.setattr(member, "_value_", member.value << 1)

    changed_sha256 = isolation._current_static_scanner_sha256()
    monkeypatch.undo()

    assert changed_sha256 != baseline


@pytest.mark.parametrize(
    "external_class",
    (
        pytest.param(Path, id="path"),
        pytest.param(PurePath, id="pure-path"),
        pytest.param(PurePosixPath, id="pure-posix-path"),
        pytest.param(string.Formatter, id="formatter"),
    ),
)
def test_task6_review6_external_constructor_changes_commitment_without_execution(
    monkeypatch,
    external_class,
):
    from validation import literature_evidence_isolation as isolation

    calls = []

    def replacement(cls, *args, **kwargs):
        calls.append((cls, args, kwargs))
        return object.__new__(cls)

    baseline = isolation._current_static_scanner_sha256()
    monkeypatch.setattr(
        external_class,
        "__new__",
        staticmethod(replacement),
    )
    changed_sha256 = isolation._current_static_scanner_sha256()
    monkeypatch.undo()

    assert calls == []
    assert changed_sha256 != baseline


def test_task6_review6_deque_spoofed_identity_and_mro_change_commitment(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    class SpoofedDeque(deque):
        def __new__(cls, *args, **kwargs):
            raise AssertionError("scanner executed a spoofed constructor")

    SpoofedDeque.__module__ = "collections"
    SpoofedDeque.__qualname__ = "deque"
    baseline = isolation._current_static_scanner_sha256()
    monkeypatch.setattr(isolation, "deque", SpoofedDeque)

    changed_sha256 = isolation._current_static_scanner_sha256()
    monkeypatch.undo()

    assert changed_sha256 != baseline


@pytest.mark.parametrize(
    "external_class, binding_owner, binding_name",
    (
        pytest.param(Path, "isolation", "Path", id="path"),
        pytest.param(PurePath, "isolation", "PurePath", id="pure-path"),
        pytest.param(
            PurePosixPath,
            "isolation",
            "PurePosixPath",
            id="pure-posix-path",
        ),
        pytest.param(
            string.Formatter,
            "string",
            "Formatter",
            id="formatter",
        ),
        pytest.param(deque, "isolation", "deque", id="deque"),
    ),
)
def test_task6_review6_external_same_identity_substitute_changes_commitment(
    monkeypatch,
    external_class,
    binding_owner,
    binding_name,
):
    from validation import literature_evidence_isolation as isolation

    spoofed_class = type(
        external_class.__name__,
        (external_class,),
        {
            "__module__": external_class.__module__,
            "__qualname__": external_class.__qualname__,
        },
    )
    owner = isolation if binding_owner == "isolation" else string
    baseline = isolation._current_static_scanner_sha256()
    monkeypatch.setattr(owner, binding_name, spoofed_class)
    changed_sha256 = isolation._current_static_scanner_sha256()
    monkeypatch.undo()

    assert changed_sha256 != baseline


def test_task6_review6_reachable_nonconstructed_lifecycle_is_not_overcommitted(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    project_class = FrozenJsonObject
    calls = []

    def replacement(self):
        calls.append(self)
        return None

    baseline = isolation._current_static_scanner_sha256()
    monkeypatch.setattr(
        project_class,
        "__post_init__",
        replacement,
        raising=False,
    )
    changed_sha256 = isolation._current_static_scanner_sha256()
    monkeypatch.undo()

    assert calls == []
    assert changed_sha256 == baseline


def test_task6_review6_unused_constructed_class_member_is_not_overcommitted(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    def first_unused_member(self):
        return self

    def second_unused_member(self):
        return None

    monkeypatch.setattr(
        isolation._AstClosureResolver,
        "_review_unused_member",
        first_unused_member,
        raising=False,
    )
    baseline = isolation._current_static_scanner_sha256()
    monkeypatch.setattr(
        isolation._AstClosureResolver,
        "_review_unused_member",
        second_unused_member,
    )
    changed_sha256 = isolation._current_static_scanner_sha256()
    monkeypatch.undo()

    assert changed_sha256 == baseline


def test_task6_review7_unused_post_init_on_constructed_non_dataclass_is_not_committed(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    calls = []

    def unused_post_init(self):
        calls.append(self)

    baseline = isolation._current_static_scanner_sha256()
    monkeypatch.setattr(
        isolation._AstClosureResolver,
        "__post_init__",
        unused_post_init,
        raising=False,
    )
    changed_sha256 = isolation._current_static_scanner_sha256()
    monkeypatch.undo()

    assert calls == []
    assert changed_sha256 == baseline


def test_task6_review7_branch_class_alias_is_marked_constructed():
    from validation import literature_evidence_isolation as isolation

    class BranchClass:
        pass

    namespace = {
        "BranchClass": BranchClass,
        "object": object,
    }
    exec(
        compile(
            "def branch_construct(flag):\n"
            "    if flag:\n"
            "        target = BranchClass\n"
            "    else:\n"
            "        target = object\n"
            "    return target()\n",
            "<task6-review7-branch-class-alias>",
            "exec",
        ),
        namespace,
    )

    usages = isolation._static_code_class_usages(
        namespace["branch_construct"].__code__,
        namespace,
    )

    assert usages["BranchClass"]["constructed"] is True


def test_task6_review7_sequential_class_alias_overwrite_is_not_overcommitted():
    from validation import literature_evidence_isolation as isolation

    class OverwrittenClass:
        pass

    namespace = {
        "OverwrittenClass": OverwrittenClass,
        "object": object,
    }
    exec(
        compile(
            "def sequential_overwrite():\n"
            "    target = OverwrittenClass\n"
            "    target = object\n"
            "    return target()\n",
            "<task6-review7-sequential-overwrite>",
            "exec",
        ),
        namespace,
    )

    usages = isolation._static_code_class_usages(
        namespace["sequential_overwrite"].__code__,
        namespace,
    )

    assert usages["OverwrittenClass"]["constructed"] is False


def test_task6_review7_branch_instance_receiver_member_is_joined():
    from validation import literature_evidence_isolation as isolation

    class ReceiverBase:
        def inherited_member(self):
            return None

    class FirstReceiver(ReceiverBase):
        pass

    class SecondReceiver(ReceiverBase):
        pass

    namespace = {
        "FirstReceiver": FirstReceiver,
        "SecondReceiver": SecondReceiver,
    }
    exec(
        compile(
            "def branch_receiver(flag):\n"
            "    if flag:\n"
            "        target = FirstReceiver()\n"
            "    else:\n"
            "        target = SecondReceiver()\n"
            "    return target.inherited_member()\n",
            "<task6-review7-branch-instance-receiver>",
            "exec",
        ),
        namespace,
    )

    usages = isolation._static_code_class_usages(
        namespace["branch_receiver"].__code__,
        namespace,
    )

    assert usages["FirstReceiver"] == {
        "constructed": True,
        "members": {"inherited_member"},
    }
    assert usages["SecondReceiver"] == {
        "constructed": True,
        "members": {"inherited_member"},
    }


def test_task6_review8_nested_frozenset_normalization_does_not_execute_project_serializer(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    original = vars(FrozenJsonObject)["_from_frozen_items"]
    calls = []

    def replacement(cls, items):
        calls.append((cls, items))
        return original.__func__(cls, items)

    monkeypatch.setattr(
        FrozenJsonObject,
        "_from_frozen_items",
        classmethod(replacement),
    )
    state = {
        "steps": 0,
        "edges": 0,
        "attributes": 0,
        "memo": {},
        "project_functions": {},
    }
    normalized = isolation._static_semantic_value(
        frozenset({frozenset({"x"})}),
        state,
        0,
        binding_name="review8_nested_frozenset",
    )
    monkeypatch.undo()

    assert calls == []
    assert normalized == {
        "kind": "frozenset",
        "token": "node_00000",
        "items": [
            {
                "kind": "frozenset",
                "token": "node_00001",
                "items": ["x"],
            }
        ],
    }


def test_task6_review8_hostile_dataclass_metadata_fails_closed_without_execution(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    calls = []

    class HostileMetadata(Mapping):
        def __iter__(self):
            calls.append("__iter__")
            return iter(("review8",))

        def __len__(self):
            calls.append("__len__")
            return 1

        def __getitem__(self, key):
            calls.append(("__getitem__", key))
            return "hostile"

    first_field = next(
        iter(
            vars(isolation.ScientificPolicyCommitment)[
                "__dataclass_fields__"
            ].values()
        )
    )
    monkeypatch.setattr(first_field, "metadata", HostileMetadata())
    caught = None
    try:
        isolation._current_static_scanner_sha256()
    except AdapterContractError as error:
        caught = error
    monkeypatch.undo()

    assert (caught is not None, calls) == (True, [])
    assert "metadata" in str(caught)


def test_task6_review8_exact_mappingproxy_metadata_changes_commitment(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    first_field = next(
        iter(
            vars(isolation.ScientificPolicyCommitment)[
                "__dataclass_fields__"
            ].values()
        )
    )
    baseline = isolation._current_static_scanner_sha256()
    monkeypatch.setattr(
        first_field,
        "metadata",
        MappingProxyType({"review8_canary": "changed"}),
    )
    changed_sha256 = isolation._current_static_scanner_sha256()
    monkeypatch.undo()

    assert changed_sha256 != baseline


def test_task6_review9_mappingproxy_wrapped_hostile_mapping_fails_without_execution():
    from validation import literature_evidence_isolation as isolation

    calls = []

    class HostileMapping(Mapping):
        def __iter__(self):
            calls.append("__iter__")
            return iter(("review9",))

        def __len__(self):
            calls.append("__len__")
            return 1

        def __getitem__(self, key):
            calls.append(("__getitem__", key))
            return "hostile"

    state = {
        "steps": 0,
        "edges": 0,
        "attributes": 0,
        "memo": {},
        "project_functions": {},
    }
    caught = None
    try:
        isolation._static_semantic_value(
            MappingProxyType(HostileMapping()),
            state,
            0,
            binding_name="review9_hostile_mappingproxy",
        )
    except AdapterContractError as error:
        caught = error

    assert (caught is not None, calls) == (True, [])
    assert "mapping" in str(caught)


def test_task6_review9_mappingproxy_wrapped_exact_dict_is_deterministic():
    from validation import literature_evidence_isolation as isolation

    state = {
        "steps": 0,
        "edges": 0,
        "attributes": 0,
        "memo": {},
        "project_functions": {},
    }
    normalized = isolation._static_semantic_value(
        MappingProxyType({"beta": 2, "alpha": 1}),
        state,
        0,
        binding_name="review9_exact_mappingproxy",
    )

    assert normalized == {
        "kind": "mapping",
        "token": "node_00000",
        "items": [["beta", 2], ["alpha", 1]],
    }


@pytest.mark.parametrize(
    "alternate_setup",
    (
        pytest.param(
            "    else:\n"
            "        target = None\n",
            id="class-or-none",
        ),
        pytest.param(
            "    else:\n"
            "        target = fallback_function\n",
            id="class-or-function",
        ),
        pytest.param("", id="class-or-unbound"),
    ),
)
def test_task6_review10_possible_class_survives_other_or_unbound_join(
    alternate_setup,
):
    from validation import literature_evidence_isolation as isolation

    class BranchClass:
        pass

    def fallback_function():
        return None

    namespace = {
        "BranchClass": BranchClass,
        "fallback_function": fallback_function,
    }
    exec(
        compile(
            "def branch_construct(flag):\n"
            "    if flag:\n"
            "        target = BranchClass\n"
            + alternate_setup
            + "    return target()\n",
            "<task6-review10-possible-class-join>",
            "exec",
        ),
        namespace,
    )

    usages = isolation._static_code_class_usages(
        namespace["branch_construct"].__code__,
        namespace,
    )

    assert usages["BranchClass"]["constructed"] is True


def test_task6_review10_nonclass_branches_do_not_create_class_usage():
    from validation import literature_evidence_isolation as isolation

    def fallback_function():
        return None

    namespace = {"fallback_function": fallback_function}
    exec(
        compile(
            "def branch_nonclass(flag):\n"
            "    if flag:\n"
            "        target = None\n"
            "    else:\n"
            "        target = fallback_function\n"
            "    return target()\n",
            "<task6-review10-nonclass-join>",
            "exec",
        ),
        namespace,
    )

    usages = isolation._static_code_class_usages(
        namespace["branch_nonclass"].__code__,
        namespace,
    )

    assert usages == {}


@pytest.mark.parametrize(
    "tail",
    (
        pytest.param("    return target\n", id="return-without-call"),
        pytest.param(
            "    target = None\n"
            "    return target()\n",
            id="overwrite-before-call",
        ),
    ),
)
def test_task6_review10_possible_class_is_not_constructed_without_later_call(
    tail,
):
    from validation import literature_evidence_isolation as isolation

    class UncalledClass:
        pass

    namespace = {"UncalledClass": UncalledClass}
    exec(
        compile(
            "def branch_uncalled(flag):\n"
            "    if flag:\n"
            "        target = UncalledClass\n"
            "    else:\n"
            "        target = None\n"
            + tail,
            "<task6-review10-uncalled-class-join>",
            "exec",
        ),
        namespace,
    )

    usages = isolation._static_code_class_usages(
        namespace["branch_uncalled"].__code__,
        namespace,
    )

    assert usages["UncalledClass"]["constructed"] is False


def test_task6_review10_possible_instance_receiver_member_survives_none_join():
    from validation import literature_evidence_isolation as isolation

    class ReceiverBase:
        def inherited_member(self):
            return None

    class BranchReceiver(ReceiverBase):
        pass

    namespace = {"BranchReceiver": BranchReceiver}
    exec(
        compile(
            "def branch_receiver(flag):\n"
            "    if flag:\n"
            "        target = BranchReceiver()\n"
            "    else:\n"
            "        target = None\n"
            "    return target.inherited_member()\n",
            "<task6-review10-instance-none-join>",
            "exec",
        ),
        namespace,
    )

    usages = isolation._static_code_class_usages(
        namespace["branch_receiver"].__code__,
        namespace,
    )

    assert usages["BranchReceiver"] == {
        "constructed": True,
        "members": {"inherited_member"},
    }


def test_task6_review11_inherited_visit_constant_changes_commitment_report_and_behavior(
    tmp_path,
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    expression = ast.parse("'ordered_' + 'phase'", mode="eval").body
    baseline_value = isolation._static_constant_with_bindings(
        expression,
        {},
        {},
        node_limit=32,
    )
    report = isolation.scan_scientific_closure(
        _task6_safe_scan_closure(tmp_path),
        forbidden_fingerprints=_task6_absent_fingerprints(),
    )
    values = {
        field.name: getattr(report, field.name)
        for field in dataclasses.fields(type(report))
    }
    baseline_sha256 = isolation._current_static_scanner_sha256()
    calls = []

    def replacement(self, node):
        calls.append((self, node))
        if type(node.value) is str and node.value == "ordered_":
            return ast.copy_location(ast.Constant(value="sanitized"), node)
        return node

    monkeypatch.setattr(ast.NodeVisitor, "visit_Constant", replacement)
    changed_sha256 = isolation._current_static_scanner_sha256()

    assert (baseline_value, calls) == ("ordered_phase", [])
    assert changed_sha256 != baseline_sha256
    with pytest.raises(
        AdapterContractError,
        match="scanner|commitment|unsupported|hash",
    ):
        isolation.StaticScanReport(**values)
    assert calls == []

    changed_value = isolation._static_constant_with_bindings(
        expression,
        {},
        {},
        node_limit=32,
    )
    monkeypatch.undo()

    assert changed_value == "sanitizedphase"
    assert calls


@pytest.mark.parametrize(
    "mutation",
    ("add-inherited-slot", "delete-inherited-slot", "descriptor-kind"),
)
def test_task6_review11_effective_inherited_visit_slots_change_commitment(
    monkeypatch,
    mutation,
):
    from validation import literature_evidence_isolation as isolation

    original = vars(ast.NodeVisitor)["visit_Constant"]
    calls = []

    def added_slot(self, node):
        calls.append((self, node))
        return node

    baseline = isolation._current_static_scanner_sha256()
    if mutation == "add-inherited-slot":
        monkeypatch.setattr(
            ast.NodeTransformer,
            "visit_ReviewCanary",
            added_slot,
            raising=False,
        )
    elif mutation == "delete-inherited-slot":
        monkeypatch.delattr(ast.NodeVisitor, "visit_Constant")
    else:
        monkeypatch.setattr(
            ast.NodeVisitor,
            "visit_Constant",
            staticmethod(original),
        )

    changed_sha256 = isolation._current_static_scanner_sha256()
    monkeypatch.undo()

    assert calls == []
    assert changed_sha256 != baseline


def test_task6_review11_unused_inherited_nonvisitor_member_is_not_committed(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    def first_unused_member(self):
        return self

    def second_unused_member(self):
        return None

    monkeypatch.setattr(
        ast.NodeVisitor,
        "_review_unused_member",
        first_unused_member,
        raising=False,
    )
    baseline = isolation._current_static_scanner_sha256()
    monkeypatch.setattr(
        ast.NodeVisitor,
        "_review_unused_member",
        second_unused_member,
    )
    changed_sha256 = isolation._current_static_scanner_sha256()
    monkeypatch.undo()

    assert changed_sha256 == baseline


def test_task6_review16_loop_backedge_preserves_possible_class_until_call():
    from validation import literature_evidence_isolation as isolation

    class LoopClass:
        pass

    namespace = {"LoopClass": LoopClass}
    exec(
        compile(
            "def loop_construct(flags):\n"
            "    target = None\n"
            "    for flag in flags:\n"
            "        if flag:\n"
            "            target = LoopClass\n"
            "    return target()\n",
            "<task6-review16-loop-backedge>",
            "exec",
        ),
        namespace,
    )

    usages = isolation._static_code_class_usages(
        namespace["loop_construct"].__code__,
        namespace,
    )

    assert usages["LoopClass"]["constructed"] is True


def test_task6_review16_sequential_overwrite_after_loop_clears_class_use():
    from validation import literature_evidence_isolation as isolation

    class OverwrittenLoopClass:
        pass

    namespace = {"OverwrittenLoopClass": OverwrittenLoopClass}
    exec(
        compile(
            "def loop_overwrite(flags):\n"
            "    target = None\n"
            "    for flag in flags:\n"
            "        if flag:\n"
            "            target = OverwrittenLoopClass\n"
            "    target = None\n"
            "    return target()\n",
            "<task6-review16-loop-overwrite>",
            "exec",
        ),
        namespace,
    )

    usages = isolation._static_code_class_usages(
        namespace["loop_overwrite"].__code__,
        namespace,
    )

    assert usages["OverwrittenLoopClass"]["constructed"] is False


def test_task6_review16_try_except_join_preserves_possible_class_until_call():
    from validation import literature_evidence_isolation as isolation

    class TryClass:
        pass

    namespace = {"TryClass": TryClass}
    exec(
        compile(
            "def try_construct(flag):\n"
            "    try:\n"
            "        if flag:\n"
            "            target = TryClass\n"
            "        else:\n"
            "            target = None\n"
            "    except Exception:\n"
            "        target = None\n"
            "    return target()\n",
            "<task6-review16-try-join>",
            "exec",
        ),
        namespace,
    )
    assert "SETUP_FINALLY" in {
        instruction.opname
        for instruction in dis.get_instructions(namespace["try_construct"])
    }

    usages = isolation._static_code_class_usages(
        namespace["try_construct"].__code__,
        namespace,
    )

    assert usages["TryClass"]["constructed"] is True


def test_task6_review16_exception_handler_class_is_constructed_and_used():
    from validation import literature_evidence_isolation as isolation

    class HandlerClass:
        def inherited_member(self):
            return None

    namespace = {"HandlerClass": HandlerClass}
    exec(
        compile(
            "def handler_construct(flag):\n"
            "    try:\n"
            "        target = None\n"
            "        if flag:\n"
            "            raise RuntimeError('review16')\n"
            "    except RuntimeError:\n"
            "        target = HandlerClass\n"
            "    return target().inherited_member()\n",
            "<task6-review16-handler-class>",
            "exec",
        ),
        namespace,
    )

    usages = isolation._static_code_class_usages(
        namespace["handler_construct"].__code__,
        namespace,
    )

    assert usages["HandlerClass"] == {
        "constructed": True,
        "members": {"inherited_member"},
    }


def test_task6_review16_shadowed_higher_mro_visitor_slot_is_not_committed(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    def effective_slot(self, node):
        return node

    def first_shadowed_slot(self, node):
        return self.generic_visit(node)

    def second_shadowed_slot(self, node):
        return node

    monkeypatch.setattr(
        ast.NodeTransformer,
        "visit_Constant",
        effective_slot,
        raising=False,
    )
    monkeypatch.setattr(
        ast.NodeVisitor,
        "visit_Constant",
        first_shadowed_slot,
    )
    baseline = isolation._current_static_scanner_sha256()

    monkeypatch.setattr(
        ast.NodeVisitor,
        "visit_Constant",
        second_shadowed_slot,
    )
    shadow_changed = isolation._current_static_scanner_sha256()

    def changed_effective_slot(self, node):
        return self.generic_visit(node)

    monkeypatch.setattr(
        ast.NodeTransformer,
        "visit_Constant",
        changed_effective_slot,
    )
    effective_changed = isolation._current_static_scanner_sha256()
    monkeypatch.undo()

    assert shadow_changed == baseline
    assert effective_changed != shadow_changed


def _task6_review12_operator_source(symbol, import_form, spelling):
    module_name = "operator" if spelling == "raw" else "operator_api"
    local_symbol = symbol if spelling == "raw" else "operation"
    if import_form == "module-attribute":
        import_statement = (
            "import operator\n"
            if spelling == "raw"
            else "import operator as operator_api\n"
        )
        callable_name = f"{module_name}.{symbol}"
    else:
        import_statement = (
            f"from operator import {symbol}\n"
            if spelling == "raw"
            else f"from operator import {symbol} as operation\n"
        )
        callable_name = local_symbol
    reflected_name = (
        "__class__.__mro__" if symbol == "attrgetter" else "__reduce__"
    )
    return (
        import_statement
        + "def scientific_entry(parameter):\n"
        + f"    return {callable_name}({reflected_name!r})(parameter)\n"
    )


@pytest.mark.parametrize(
    "boundary",
    ("closure-import-validator", "public-build-and-scan"),
)
@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize("spelling", ("raw", "aggregate"))
@pytest.mark.parametrize(
    "import_form", ("module-attribute", "direct-import")
)
@pytest.mark.parametrize("symbol", ("attrgetter", "methodcaller"))
def test_task6_review12_operator_reflection_is_rejected_at_both_boundaries(
    tmp_path,
    boundary,
    role,
    spelling,
    import_form,
    symbol,
):
    source = _task6_review12_operator_source(
        symbol, import_form, spelling
    )

    with pytest.raises(
        AdapterContractError,
        match="operator|external|approved|reflection|callable|reference",
    ):
        if boundary == "closure-import-validator":
            _task6_build_scientific_closure(tmp_path, role, source)
        else:
            _task6_build_and_scan(tmp_path, role, source)


@pytest.mark.parametrize("spelling", ("raw", "aggregate"))
@pytest.mark.parametrize(
    "import_form", ("module-attribute", "direct-import")
)
@pytest.mark.parametrize("symbol", ("attrgetter", "methodcaller"))
def test_task6_review12_raw_static_scan_rejects_operator_reflection(
    spelling,
    import_form,
    symbol,
):
    from validation import literature_evidence_isolation as isolation

    source = _task6_review12_operator_source(
        symbol, import_form, spelling
    )

    with pytest.raises(
        AdapterContractError,
        match="operator|approved|reflection|callable|reference",
    ):
        isolation._scan_static_ast(
            ast.parse(source),
            role="adapter",
            forbidden_fingerprints=frozenset(
                _task6_absent_fingerprints()
            ),
            entry_function_name="scientific_entry",
        )


@pytest.mark.parametrize("role", ("adapter", "oracle"))
def test_task6_review12_empty_operator_allowlist_is_not_a_token_blacklist(
    tmp_path,
    role,
):
    from validation import literature_evidence_isolation as isolation

    assert isolation._STATIC_SAFE_OPERATOR_CALLABLE_PATHS == frozenset()
    report = _task6_build_and_scan(
        tmp_path,
        role,
        "def scientific_entry(parameter):\n"
        "    operator = parameter + 1\n"
        "    return operator * 2\n",
    )

    assert report.role == role


def test_task6_review12_operator_allowlist_changes_scanner_commitment(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    baseline = isolation._current_static_scanner_sha256()
    monkeypatch.setattr(
        isolation,
        "_STATIC_SAFE_OPERATOR_CALLABLE_PATHS",
        frozenset({("operator", "add")}),
    )
    changed_sha256 = isolation._current_static_scanner_sha256()
    monkeypatch.undo()

    assert changed_sha256 != baseline


TASK6_REVIEW13_FORBIDDEN_PROJECT_MODULES = (
    "reports.generate_literature_reproduction_audit_pdf",
    "validation.fetch_literature_evidence_sources",
    "validation.literature_benchmark_registry",
    "validation.literature_evidence_comparators",
    "validation.literature_evidence_inventory",
    "validation.literature_evidence_parsers",
    "validation.literature_evidence_record_loader",
    "validation.literature_evidence_schema",
    "validation.literature_evidence_sources",
    "validation.literature_reproduction_audit",
    "validation.literature_reproduction_manifest",
    "validation.literature_reproduction_report",
    "validation.literature_runtime_evidence",
    "validation.literature_source_cache",
    "validation.literature_source_index",
    "validation.literature_source_provisioning",
    "validation.literature_spin_model_benchmarks",
    "validation.verify_literature_reproduction_manifest",
)


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize(
    "forbidden_module", TASK6_REVIEW13_FORBIDDEN_PROJECT_MODULES
)
def test_task6_review13_real_project_source_families_are_rejected(
    tmp_path,
    role,
    forbidden_module,
):
    _write_task5_source(
        tmp_path,
        forbidden_module,
        "def pure_helper(parameter):\n"
        "    return parameter + 1\n",
    )
    source = (
        f"from {forbidden_module} import pure_helper\n"
        "def scientific_entry(parameter):\n"
        "    return pure_helper(parameter)\n"
    )

    with pytest.raises(
        AdapterContractError,
        match="project|module|source|family|forbidden|approved",
    ):
        _task6_build_and_scan(tmp_path, role, source)


@pytest.mark.parametrize("role", ("adapter", "oracle"))
def test_task6_review13_nearby_pure_project_module_is_allowed(
    tmp_path,
    role,
):
    allowed_module = "validation.literature_evidence_math_helpers"
    _write_task5_source(
        tmp_path,
        allowed_module,
        "def pure_helper(parameter):\n"
        "    return parameter + 1\n",
    )
    report = _task6_build_and_scan(
        tmp_path,
        role,
        f"from {allowed_module} import pure_helper\n"
        "def scientific_entry(parameter):\n"
        "    return pure_helper(parameter)\n",
    )

    assert report.role == role


def test_task6_review13_policy_is_exact_and_component_based():
    from validation import literature_evidence_isolation as isolation

    expected = tuple(
        tuple(module_name.split("."))
        for module_name in TASK6_REVIEW13_FORBIDDEN_PROJECT_MODULES
    )

    assert isolation._FORBIDDEN_SCIENTIFIC_PROJECT_MODULE_PREFIXES == (
        expected
    )
    assert isolation._scientific_project_module_is_forbidden(
        "validation.literature_evidence_inventory.records"
    )
    assert not isolation._scientific_project_module_is_forbidden(
        "validation.literature_evidence_inventory_math"
    )


@pytest.mark.parametrize("role", ("adapter", "oracle"))
def test_task6_review13_postbuild_manifest_and_material_recheck_policy(
    tmp_path,
    monkeypatch,
    role,
):
    from validation import literature_evidence_isolation as isolation

    closure = _task6_build_scientific_closure(
        tmp_path,
        role,
        "def scientific_entry(parameter):\n"
        "    return parameter + 1\n",
    )
    entry_module = closure.entry_symbol.split(":", 1)[0]
    changed_policy = tuple(
        sorted(
            (
                *isolation._FORBIDDEN_SCIENTIFIC_PROJECT_MODULE_PREFIXES,
                tuple(entry_module.split(".")),
            )
        )
    )
    monkeypatch.setattr(
        isolation,
        "_FORBIDDEN_SCIENTIFIC_PROJECT_MODULE_PREFIXES",
        changed_policy,
    )

    with pytest.raises(
        AdapterContractError,
        match="project|module|source|family|forbidden|approved",
    ):
        isolation._validate_scientific_closure_record(closure)
    with pytest.raises(
        AdapterContractError,
        match="project|module|source|family|forbidden|approved",
    ):
        isolation.scan_scientific_closure(
            closure,
            forbidden_fingerprints=_task6_absent_fingerprints(),
        )


def test_task6_review13_module_family_policy_changes_scanner_commitment(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    baseline = isolation._current_static_scanner_sha256()
    monkeypatch.setattr(
        isolation,
        "_FORBIDDEN_SCIENTIFIC_PROJECT_MODULE_PREFIXES",
        tuple(
            sorted(
                (
                    *isolation._FORBIDDEN_SCIENTIFIC_PROJECT_MODULE_PREFIXES,
                    ("validation", "review13_canary"),
                )
            )
        ),
    )
    changed_sha256 = isolation._current_static_scanner_sha256()
    monkeypatch.undo()

    assert changed_sha256 != baseline


def _task6_review14_decimal_mutation_source(case_name, spelling):
    module_name = "decimal" if spelling == "raw" else "decimal_api"
    if case_name == "module-setcontext":
        import_source = (
            "import decimal\n"
            if spelling == "raw"
            else "import decimal as decimal_api\n"
        )
        body = (
            f"    {module_name}.setcontext("
            f"{module_name}.Context(prec=3))\n"
        )
    elif case_name == "direct-setcontext":
        import_source = (
            "from decimal import Context, setcontext\n"
            if spelling == "raw"
            else (
                "from decimal import Context as decimal_context, "
                "setcontext as install_context\n"
            )
        )
        context_name = "Context" if spelling == "raw" else "decimal_context"
        setter_name = "setcontext" if spelling == "raw" else "install_context"
        body = f"    {setter_name}({context_name}(prec=3))\n"
    elif case_name == "module-attribute-store":
        import_source = (
            "import decimal\n"
            if spelling == "raw"
            else "import decimal as decimal_api\n"
        )
        body = f"    {module_name}.DefaultContext.prec = 3\n"
    else:
        import_source = (
            "import decimal\n"
            if spelling == "raw"
            else "import decimal as decimal_api\n"
        )
        body = (
            f"    context = {module_name}.getcontext()\n"
            "    context.prec = 3\n"
        )
    return (
        import_source
        + "def scientific_entry(parameter):\n"
        + body
        + "    return parameter\n"
    )


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize("spelling", ("raw", "aggregate"))
@pytest.mark.parametrize(
    "case_name",
    (
        "module-setcontext",
        "direct-setcontext",
        "module-attribute-store",
        "derived-context-store",
    ),
)
def test_task6_review14_decimal_global_mutation_is_rejected_end_to_end(
    tmp_path,
    role,
    spelling,
    case_name,
):
    source = _task6_review14_decimal_mutation_source(
        case_name, spelling
    )

    with pytest.raises(
        AdapterContractError,
        match="external|decimal|mutation|callable|reference|approved|import",
    ):
        _task6_build_and_scan(tmp_path, role, source)


@pytest.mark.parametrize("spelling", ("raw", "aggregate"))
@pytest.mark.parametrize(
    "case_name",
    (
        "module-setcontext",
        "direct-setcontext",
        "module-attribute-store",
        "derived-context-store",
    ),
)
def test_task6_review14_raw_scan_independently_rejects_decimal_mutation(
    spelling,
    case_name,
):
    from validation import literature_evidence_isolation as isolation

    with pytest.raises(
        AdapterContractError,
        match="external|decimal|mutation|callable|reference|approved|import",
    ):
        isolation._scan_static_ast(
            ast.parse(
                _task6_review14_decimal_mutation_source(
                    case_name, spelling
                )
            ),
            role="adapter",
            forbidden_fingerprints=frozenset(
                _task6_absent_fingerprints()
            ),
            entry_function_name="scientific_entry",
        )


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize("spelling", ("module", "direct"))
def test_task6_review14_decimal_construction_and_arithmetic_remain_allowed(
    tmp_path,
    role,
    spelling,
):
    if spelling == "module":
        source = (
            "import decimal as decimal_api\n"
            "def scientific_entry(parameter):\n"
            "    value = decimal_api.Decimal(parameter)\n"
            "    return value + decimal_api.Decimal('1')\n"
        )
    else:
        source = (
            "from decimal import Decimal as decimal_number\n"
            "def scientific_entry(parameter):\n"
            "    value = decimal_number(parameter)\n"
            "    return value + decimal_number('1')\n"
        )

    report = _task6_build_and_scan(tmp_path, role, source)

    assert report.role == role


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize(
    "source",
    (
        "from math import factorial\n"
        "def scientific_entry(parameter):\n"
        "    return factorial(parameter)\n",
        "import statistics\n"
        "def scientific_entry(parameter):\n"
        "    return statistics.mean(parameter)\n",
    ),
)
def test_task6_review14_unknown_external_symbol_fails_closed(
    tmp_path,
    role,
    source,
):
    with pytest.raises(
        AdapterContractError,
        match="external|callable|reference|approved|import",
    ):
        _task6_build_and_scan(tmp_path, role, source)


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize(
    "source",
    (
        "import math\n"
        "def scientific_entry(parameter):\n"
        "    math.pi = parameter\n"
        "    return parameter\n",
        "import string\n"
        "def scientific_entry(parameter):\n"
        "    string.whitespace = 'changed'\n"
        "    return parameter\n",
    ),
)
def test_task6_review14_external_module_attribute_store_is_generic(
    tmp_path,
    role,
    source,
):
    with pytest.raises(
        AdapterContractError,
        match="external|mutation|attribute|reference|approved|module",
    ):
        _task6_build_and_scan(tmp_path, role, source)


def test_task6_review14_stdlib_capability_policy_changes_commitment(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    baseline = isolation._current_static_scanner_sha256()
    monkeypatch.setattr(
        isolation,
        "_STATIC_SAFE_STDLIB_CALLABLE_PATHS",
        frozenset(
            {
                *isolation._STATIC_SAFE_STDLIB_CALLABLE_PATHS,
                ("math", "review14_canary"),
            }
        ),
    )
    changed_sha256 = isolation._current_static_scanner_sha256()
    monkeypatch.undo()

    assert changed_sha256 != baseline


def _task6_review15_external_function_records(manifest):
    records = {}
    pending = [manifest]
    while pending:
        item = pending.pop()
        if type(item) is dict:
            if item.get("kind") == "external_function":
                records[(item["module"], item["qualname"])] = item
            pending.extend(item.values())
        elif type(item) is list:
            pending.extend(item)
    return records


def test_task6_review15_path_is_symlink_global_changes_commitment_and_behavior(
    tmp_path,
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    target = tmp_path / "review15-target"
    link = tmp_path / "review15-link"
    target.write_text("target", encoding="utf-8")
    link.symlink_to(target)
    assert link.is_symlink() is True
    report = isolation.scan_scientific_closure(
        _task6_safe_scan_closure(tmp_path / "science"),
        forbidden_fingerprints=_task6_absent_fingerprints(),
    )
    values = {
        field.name: getattr(report, field.name)
        for field in dataclasses.fields(type(report))
    }
    baseline = isolation._current_static_scanner_sha256()
    calls = []

    def replacement(mode):
        calls.append(mode)
        return False

    monkeypatch.setattr(pathlib, "S_ISLNK", replacement)
    changed_sha256 = isolation._current_static_scanner_sha256()

    assert changed_sha256 != baseline
    assert calls == []
    with pytest.raises(
        AdapterContractError,
        match="scanner|commitment|unsupported|hash",
    ):
        isolation.StaticScanReport(**values)
    assert calls == []
    assert link.is_symlink() is False
    assert len(calls) == 1


def test_task6_review15_formatter_parse_module_global_is_transitive(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    original_backend = string._string
    replacement_backend = ModuleType("review15_formatter_backend")
    replacement_backend.formatter_parser = (
        original_backend.formatter_parser
    )
    baseline = isolation._current_static_scanner_sha256()
    monkeypatch.setattr(string, "_string", replacement_backend)
    changed_sha256 = isolation._current_static_scanner_sha256()

    assert changed_sha256 != baseline
    assert tuple(string.Formatter().parse("{value}")) == (
        ("", "value", "", None),
    )


def test_task6_review15_external_function_globals_are_inverse_exact():
    from validation import literature_evidence_isolation as isolation

    records = _task6_review15_external_function_records(
        isolation._static_scanner_dependency_manifest()
    )

    assert set(records[("pathlib", "Path.is_symlink")]["globals"]) == {
        "OSError",
        "S_ISLNK",
        "ValueError",
        "_ignore_error",
    }
    assert set(records[("string", "Formatter.parse")]["globals"]) == {
        "_string"
    }


def test_task6_review15_unloaded_external_module_global_is_not_committed(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    monkeypatch.setattr(
        pathlib, "_review15_unused_global", "first", raising=False
    )
    baseline = isolation._current_static_scanner_sha256()
    monkeypatch.setattr(
        pathlib, "_review15_unused_global", "second"
    )
    changed_sha256 = isolation._current_static_scanner_sha256()
    monkeypatch.undo()

    assert changed_sha256 == baseline


def test_task6_review17_json_scanner_parse_int_state_changes_commitment(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    baseline = isolation._current_static_scanner_sha256()
    calls = []

    def replacement_parse_int(text):
        calls.append(text)
        return 731

    replacement_decoder = json.JSONDecoder(
        parse_int=replacement_parse_int
    )
    monkeypatch.setattr(
        json._default_decoder,
        "scan_once",
        replacement_decoder.scan_once,
    )
    changed = isolation._current_static_scanner_sha256()

    assert calls == []
    assert changed != baseline
    assert json.loads("1") == 731
    assert calls == ["1"]


def test_task6_review17_json_scanner_bound_native_receiver_is_committed(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    baseline_value = json.loads("NaN")
    baseline = isolation._current_static_scanner_sha256()
    replacement_constants = {
        "NaN": 731,
        "Infinity": 732,
        "-Infinity": -732,
    }
    replacement_decoder = json.JSONDecoder(
        parse_constant=replacement_constants.__getitem__
    )
    monkeypatch.setattr(
        json._default_decoder,
        "scan_once",
        replacement_decoder.scan_once,
    )
    changed = isolation._current_static_scanner_sha256()

    assert math.isnan(baseline_value)
    assert changed != baseline
    assert json.loads("NaN") == 731


def test_task6_review17_external_native_instance_state_policy_is_exact():
    from validation import literature_evidence_isolation as isolation

    assert isolation._STATIC_SCANNER_EXTERNAL_OPAQUE_INSTANCE_TYPES == (
        frozenset()
    )
    assert isolation._STATIC_SCANNER_EXTERNAL_INSTANCE_SLOT_PATHS == {
        ("_json", "Scanner"): (
            "__call__",
            "object_hook",
            "object_pairs_hook",
            "parse_constant",
            "parse_float",
            "parse_int",
            "strict",
        )
    }


TASK6_REVIEW18_FORBIDDEN_MODULES = (
    "validation.environment_discovery",
    "validation.git_helper",
    "validation.previous_output_helper",
    "validation.target_values_helper",
    "validation.workspace_helper",
)

TASK6_REVIEW18_ALLOWED_NEIGHBORS = (
    "validation.environmental_model",
    "validation.legitimate",
    "validation.literature_evidence_math_helpers",
    "validation.workspace_basis_math",
)


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize(
    "module_name", TASK6_REVIEW18_FORBIDDEN_MODULES
)
def test_task6_review18_resolver_role_gate_rejects_forbidden_module_family(
    tmp_path,
    role,
    module_name,
):
    from validation import literature_evidence_isolation as isolation

    resolver = isolation._AstClosureResolver((tmp_path,), role=role)

    with pytest.raises(
        AdapterContractError,
        match="forbidden project module family",
    ):
        resolver._check_module_role(module_name)


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize(
    "module_name", TASK6_REVIEW18_FORBIDDEN_MODULES
)
def test_task6_review18_importfrom_forbidden_family_is_rejected(
    tmp_path,
    role,
    module_name,
):
    _write_task5_source(
        tmp_path,
        module_name,
        "def neutral_helper(parameter):\n"
        "    return parameter + 1\n",
    )

    with pytest.raises(
        AdapterContractError,
        match="forbidden project module family",
    ):
        _task6_build_scientific_closure(
            tmp_path,
            role,
            f"from {module_name} import neutral_helper\n"
            "def scientific_entry(parameter):\n"
            "    return neutral_helper(parameter)\n",
        )


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize(
    "module_name",
    (
        "validation.git_helper",
        "validation.target_values_helper",
    ),
)
def test_task6_review18_direct_project_import_hits_family_policy_first(
    tmp_path,
    role,
    module_name,
):
    _write_task5_source(
        tmp_path,
        module_name,
        "def neutral_helper(parameter):\n"
        "    return parameter + 1\n",
    )

    with pytest.raises(
        AdapterContractError,
        match="forbidden project module family",
    ):
        _task6_build_scientific_closure(
            tmp_path,
            role,
            f"import {module_name}\n"
            "def scientific_entry(parameter):\n"
            f"    return {module_name}.neutral_helper(parameter)\n",
        )


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize("module_name", TASK6_REVIEW18_ALLOWED_NEIGHBORS)
def test_task6_review18_exact_nearby_scientific_module_is_allowed(
    tmp_path,
    role,
    module_name,
):
    _write_task5_source(
        tmp_path,
        module_name,
        "def neutral_helper(parameter):\n"
        "    return parameter + 1\n",
    )

    closure = _task6_build_scientific_closure(
        tmp_path,
        role,
        f"from {module_name} import neutral_helper\n"
        "def scientific_entry(parameter):\n"
        "    return neutral_helper(parameter)\n",
    )

    assert any(
        node["qualified_name"] == f"{module_name}.neutral_helper"
        for node in closure.nodes
    )


@pytest.mark.parametrize("role", ("adapter", "oracle"))
def test_task6_review18_postbuild_manifest_and_material_recheck_token_family(
    tmp_path,
    monkeypatch,
    role,
):
    from validation import literature_evidence_isolation as isolation

    module_name = "validation.previous_output_helper"
    _write_task5_source(
        tmp_path,
        module_name,
        "def neutral_helper(parameter):\n"
        "    return parameter + 1\n",
    )
    with monkeypatch.context() as context:
        context.setattr(
            isolation,
            "_FORBIDDEN_SCIENTIFIC_PROJECT_MODULE_TOKEN_PATTERNS",
            (),
            raising=False,
        )
        context.setattr(
            isolation,
            "_FORBIDDEN_SCIENTIFIC_PROJECT_MODULE_CONTIGUOUS_PATTERNS",
            frozenset(),
        )
        closure = _task6_build_scientific_closure(
            tmp_path,
            role,
            f"from {module_name} import neutral_helper\n"
            "def scientific_entry(parameter):\n"
            "    return neutral_helper(parameter)\n",
        )
    material = getattr(closure, "_static_scan_material")

    with pytest.raises(
        AdapterContractError,
        match="forbidden project module family",
    ):
        isolation._validate_scientific_closure_record(closure)
    with pytest.raises(
        AdapterContractError,
        match="forbidden project module family",
    ):
        isolation._validate_static_scan_material(closure, material)


def test_task6_review18_token_family_policy_is_closed_exact_and_case_sensitive():
    from validation import literature_evidence_isolation as isolation

    assert (
        isolation._FORBIDDEN_SCIENTIFIC_PROJECT_MODULE_TOKEN_PATTERNS
        == (
            ("environment", "discovery"),
            ("environment", "helper"),
            ("environment", "helpers"),
            ("expected",),
            ("git",),
            ("previous", "output"),
            ("result",),
            ("target",),
            ("verdict",),
            ("workspace", "discovery"),
            ("workspace", "helper"),
            ("workspace", "helpers"),
        )
    )
    for module_name in TASK6_REVIEW18_FORBIDDEN_MODULES:
        assert isolation._scientific_project_module_is_forbidden(module_name)
        assert isolation._scientific_project_module_is_forbidden(
            f"{module_name}.records"
        )
    for module_name in (
        *TASK6_REVIEW18_ALLOWED_NEIGHBORS,
        "validation.Git_helper",
        "validation.expectedness",
    ):
        assert not isolation._scientific_project_module_is_forbidden(
            module_name
        )


def test_task6_review18_token_family_policy_changes_scanner_commitment(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    baseline = isolation._current_static_scanner_sha256()
    monkeypatch.setattr(
        isolation,
        "_FORBIDDEN_SCIENTIFIC_PROJECT_MODULE_TOKEN_PATTERNS",
        tuple(
            sorted(
                {
                    *isolation._FORBIDDEN_SCIENTIFIC_PROJECT_MODULE_TOKEN_PATTERNS,
                    ("review18",),
                }
            )
        ),
    )
    changed = isolation._current_static_scanner_sha256()
    monkeypatch.undo()

    assert changed != baseline


TASK6_REVIEW19_PLURAL_HELPER_MODULES = (
    "validation.environment_helpers",
    "validation.workspace_helpers",
)


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize(
    "module_name", TASK6_REVIEW19_PLURAL_HELPER_MODULES
)
def test_task6_review19_plural_helper_family_is_rejected_by_role_gate(
    tmp_path,
    role,
    module_name,
):
    from validation import literature_evidence_isolation as isolation

    resolver = isolation._AstClosureResolver((tmp_path,), role=role)

    with pytest.raises(
        AdapterContractError,
        match="forbidden project module family",
    ):
        resolver._check_module_role(module_name)


@pytest.mark.parametrize("role", ("adapter", "oracle"))
@pytest.mark.parametrize(
    "module_name", TASK6_REVIEW19_PLURAL_HELPER_MODULES
)
def test_task6_review19_plural_helper_importfrom_is_rejected(
    tmp_path,
    role,
    module_name,
):
    _write_task5_source(
        tmp_path,
        module_name,
        "def neutral_helper(parameter):\n"
        "    return parameter + 1\n",
    )

    with pytest.raises(
        AdapterContractError,
        match="forbidden project module family",
    ):
        _task6_build_scientific_closure(
            tmp_path,
            role,
            f"from {module_name} import neutral_helper\n"
            "def scientific_entry(parameter):\n"
            "    return neutral_helper(parameter)\n",
        )


def test_task6_review20_derived_regex_cache_population_is_not_committed():
    from validation import literature_evidence_isolation as isolation

    baseline = isolation._current_static_scanner_sha256()
    assert re.findall(
        r"task6-review20-cache-probe-[A-Z]+-[0-9]+",
        "task6-review20-cache-probe-CACHE-731",
    ) == ["task6-review20-cache-probe-CACHE-731"]
    changed = isolation._current_static_scanner_sha256()

    assert changed == baseline


def test_task6_review20_scanner_manifest_has_no_python_regex_cache_graph():
    from validation import literature_evidence_isolation as isolation

    external_modules = set()
    external_function_modules = set()
    external_function_globals = set()
    pending = [isolation._static_scanner_dependency_manifest()]
    while pending:
        item = pending.pop()
        if type(item) is dict:
            if item.get("kind") == "module":
                external_modules.add(item["name"])
            elif item.get("kind") == "external_function":
                external_function_modules.add(item["module"])
                external_function_globals.update(item["globals"])
            pending.extend(item.values())
        elif type(item) is list:
            pending.extend(item)

    prohibited_modules = {"re", "sre_compile", "sre_parse"}
    assert external_modules.isdisjoint(prohibited_modules)
    assert external_function_modules.isdisjoint(prohibited_modules)
    assert "_cache" not in external_function_globals


def test_task6_review6_old_report_fails_after_constructor_binding_change(
    tmp_path,
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    report = isolation.scan_scientific_closure(
        _task6_safe_scan_closure(tmp_path),
        forbidden_fingerprints=_task6_absent_fingerprints(),
    )
    values = {
        field.name: getattr(report, field.name)
        for field in dataclasses.fields(type(report))
    }
    calls = []

    def replacement(cls, *args, **kwargs):
        calls.append((cls, args, kwargs))
        return object.__new__(cls)

    monkeypatch.setattr(Path, "__new__", staticmethod(replacement))
    caught = None
    try:
        isolation.StaticScanReport(**values)
    except AdapterContractError as error:
        caught = error
    monkeypatch.undo()

    assert caught is not None
    assert re.search(
        "scanner|commitment|unsupported|hash",
        str(caught),
    )
    assert calls == []


def test_task6_review_scanner_commitment_changes_with_rule_manifest(
    tmp_path,
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    closure = _task6_safe_scan_closure(tmp_path)
    baseline = isolation.scan_scientific_closure(
        closure, forbidden_fingerprints=_task6_absent_fingerprints()
    )
    monkeypatch.setattr(
        isolation,
        "_STATIC_FORBIDDEN_NAME_TOKENS",
        frozenset(
            isolation._STATIC_FORBIDDEN_NAME_TOKENS - {"verdict"}
        ),
    )

    changed = isolation.scan_scientific_closure(
        closure, forbidden_fingerprints=_task6_absent_fingerprints()
    )

    assert changed.scanner_sha256 != baseline.scanner_sha256


def test_task6_review_scanner_commitment_changes_with_implementation(
    tmp_path,
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    closure = _task6_safe_scan_closure(tmp_path)
    baseline = isolation.scan_scientific_closure(
        closure, forbidden_fingerprints=_task6_absent_fingerprints()
    )
    original = isolation._static_call_path

    def semantically_equivalent_static_call_path(value):
        return original(value)

    monkeypatch.setattr(
        isolation,
        "_static_call_path",
        semantically_equivalent_static_call_path,
    )

    changed = isolation.scan_scientific_closure(
        closure, forbidden_fingerprints=_task6_absent_fingerprints()
    )

    assert changed.scanner_sha256 != baseline.scanner_sha256


@pytest.mark.parametrize(
    "helper_name",
    (
        "_lexical_tokens",
        "_ast_authored_tokens",
        "_assignment_parts",
        "_target_tokens",
    ),
)
def test_task6_review2_commitment_tracks_transitive_helper_rebinding(
    monkeypatch,
    helper_name,
):
    from validation import literature_evidence_isolation as isolation

    baseline = isolation._current_static_scanner_sha256()

    def replacement(*_args, **_kwargs):
        return frozenset()

    monkeypatch.setattr(isolation, helper_name, replacement)

    assert isolation._current_static_scanner_sha256() != baseline


def test_task6_review2_commitment_tracks_helper_that_changes_verdict(
    tmp_path,
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    closure = _task6_build_scientific_closure(
        tmp_path,
        "adapter",
        "def scientific_entry(parameter):\n"
        "    verdict = parameter + 1\n"
        "    return verdict\n",
    )
    baseline = isolation._current_static_scanner_sha256()
    with pytest.raises(AdapterContractError, match="vocabulary|static|scan"):
        isolation.scan_scientific_closure(
            closure,
            forbidden_fingerprints=_task6_absent_fingerprints(),
        )
    monkeypatch.setattr(
        isolation,
        "_lexical_tokens",
        lambda _value: frozenset(),
    )

    changed = isolation.scan_scientific_closure(
        closure,
        forbidden_fingerprints=_task6_absent_fingerprints(),
    )

    assert changed.scanner_sha256 != baseline


def test_task6_review2_commitment_tracks_in_place_code_replacement(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    target = isolation._static_call_path
    baseline = isolation._current_static_scanner_sha256()

    def replacement(_value):
        return ("changed",)

    monkeypatch.setattr(target, "__code__", replacement.__code__)

    assert isolation._current_static_scanner_sha256() != baseline


@pytest.mark.parametrize("mutation", ("defaults", "kwdefaults", "closure"))
def test_task6_review2_commitment_tracks_function_state_mutation(
    monkeypatch,
    mutation,
):
    from validation import literature_evidence_isolation as isolation

    closure_state = ["closed"]

    def stateful_helper(value, marker="first", *, mode="strict"):
        if closure_state and marker and mode:
            return {value.lower()}
        return set()

    monkeypatch.setattr(isolation, "_lexical_tokens", stateful_helper)
    baseline = isolation._current_static_scanner_sha256()
    if mutation == "defaults":
        monkeypatch.setattr(stateful_helper, "__defaults__", ("second",))
    elif mutation == "kwdefaults":
        monkeypatch.setattr(
            stateful_helper,
            "__kwdefaults__",
            {"mode": "relaxed"},
        )
    else:
        closure_state.append("mutated")

    assert isolation._current_static_scanner_sha256() != baseline


def test_task6_review2_commitment_is_stable_without_semantic_mutation():
    from validation import literature_evidence_isolation as isolation

    first = isolation._current_static_scanner_sha256()
    second = isolation._current_static_scanner_sha256()

    assert second == first


def test_task6_review2_commitment_is_stable_across_hash_seeds():
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "scripts")
    command = (
        "from validation import literature_evidence_isolation as m; "
        "print(m._current_static_scanner_sha256())"
    )
    commitments = []
    for seed in ("0", "1"):
        environment["PYTHONHASHSEED"] = seed
        completed = subprocess.run(
            (sys.executable, "-c", command),
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
        commitments.append(completed.stdout.strip())

    assert commitments[1] == commitments[0]


def test_task6_review2_uninspectable_policy_callable_fails_closed(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    monkeypatch.setattr(isolation, "_scan_policy_forbidden_structures", len)

    with pytest.raises(
        AdapterContractError,
        match="scanner|implementation|commit|normalize|callable|source",
    ):
        isolation._current_static_scanner_sha256()


def test_task6_review3_commitment_tracks_builder_import_validator(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    baseline = isolation._current_static_scanner_sha256()
    original = isolation._AstClosureResolver._validate_external_import

    def replacement(self, source):
        return original(self, source)

    monkeypatch.setattr(
        isolation._AstClosureResolver,
        "_validate_external_import",
        replacement,
    )

    assert isolation._current_static_scanner_sha256() != baseline


def test_task6_review3_commitment_tracks_bounded_source_reader(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    baseline = isolation._current_static_scanner_sha256()
    original = isolation._bounded_read_python_source

    def replacement(source_root, relative_path, module_name):
        return original(source_root, relative_path, module_name)

    monkeypatch.setattr(
        isolation,
        "_bounded_read_python_source",
        replacement,
    )

    assert isolation._current_static_scanner_sha256() != baseline


def test_task6_review3_commitment_tracks_ast_walk_binding(monkeypatch):
    from validation import literature_evidence_isolation as isolation

    baseline = isolation._current_static_scanner_sha256()
    original = ast.walk

    def replacement(node):
        return original(node)

    monkeypatch.setattr(ast, "walk", replacement)

    assert isolation._current_static_scanner_sha256() != baseline


def test_task6_review3_commitment_tracks_os_open_binding(monkeypatch):
    from validation import literature_evidence_isolation as isolation

    baseline = isolation._current_static_scanner_sha256()
    original = os.open

    def replacement(path, flags, mode=0o777, *, dir_fd=None):
        return original(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", replacement)

    assert isolation._current_static_scanner_sha256() != baseline


def test_task6_review3_commitment_tracks_path_inherited_method_binding(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    baseline = isolation._current_static_scanner_sha256()
    original = Path.is_absolute

    def replacement(self):
        return original(self)

    monkeypatch.setattr(Path, "is_absolute", replacement)

    assert isolation._current_static_scanner_sha256() != baseline


@pytest.mark.parametrize(
    "receiver_class, member_name",
    (
        pytest.param(Path, "absolute", id="path-absolute"),
        pytest.param(Path, "resolve", id="path-resolve"),
        pytest.param(Path, "is_dir", id="path-is-dir"),
        pytest.param(Path, "is_file", id="path-is-file"),
        pytest.param(Path, "is_symlink", id="path-is-symlink"),
        pytest.param(Path, "is_absolute", id="pure-path-is-absolute"),
        pytest.param(Path, "relative_to", id="pure-path-relative-to"),
        pytest.param(Path, "with_suffix", id="pure-path-with-suffix"),
        pytest.param(Path, "as_posix", id="pure-path-as-posix"),
        pytest.param(Path, "parts", id="pure-path-parts-property"),
        pytest.param(Path, "anchor", id="pure-path-anchor-property"),
        pytest.param(Path, "__truediv__", id="pure-path-division"),
        pytest.param(Path, "__str__", id="pure-path-string"),
        pytest.param(string.Formatter, "parse", id="formatter-parse"),
    ),
)
def test_task6_review4_commitment_tracks_exact_external_receiver_binding(
    monkeypatch,
    receiver_class,
    member_name,
):
    from validation import literature_evidence_isolation as isolation

    baseline = isolation._current_static_scanner_sha256()
    owner = next(
        candidate
        for candidate in receiver_class.__mro__
        if member_name in vars(candidate)
    )
    original = vars(owner)[member_name]
    calls = []

    if type(original) is property:

        def replacement(instance):
            calls.append(instance)
            return original.fget(instance)

        changed = property(
            replacement,
            original.fset,
            original.fdel,
            original.__doc__,
        )
    else:

        def replacement(*args, **kwargs):
            calls.append((args, kwargs))
            return original(*args, **kwargs)

        changed = replacement
    monkeypatch.setattr(owner, member_name, changed)
    changed_sha256 = isolation._current_static_scanner_sha256()
    monkeypatch.undo()

    assert calls == []
    assert changed_sha256 != baseline


def test_task6_review4_external_receiver_manifest_omission_fails_closed(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    binding = ("pathlib", "Path", "absolute")
    assert binding in isolation._STATIC_SCANNER_EXTERNAL_RECEIVER_BINDINGS
    monkeypatch.setattr(
        isolation,
        "_STATIC_SCANNER_EXTERNAL_RECEIVER_BINDINGS",
        frozenset(
            isolation._STATIC_SCANNER_EXTERNAL_RECEIVER_BINDINGS - {binding}
        ),
    )

    with pytest.raises(
        AdapterContractError,
        match="scanner|external|receiver|binding|manifest|missing|closed",
    ):
        isolation._current_static_scanner_sha256()


def test_task6_review4_new_unmanifested_external_receiver_access_fails_closed(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    target = isolation._assert_no_symlink_components

    def replacement(path, field_name):
        absolute = path.absolute()
        current = Path(absolute.anchor)
        for component in absolute.parts[1:]:
            current /= component
            if current.is_symlink() or current.is_file():
                return None
        return field_name and None

    monkeypatch.setattr(target, "__code__", replacement.__code__)

    with pytest.raises(
        AdapterContractError,
        match="scanner|external|receiver|manifest|missing|binding|closed",
    ):
        isolation._current_static_scanner_sha256()


def test_task6_review3_commitment_ignores_unreferenced_ast_binding(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    baseline = isolation._current_static_scanner_sha256()
    original = ast.dump

    def replacement(node, *args, **kwargs):
        return original(node, *args, **kwargs)

    monkeypatch.setattr(ast, "dump", replacement)

    assert isolation._current_static_scanner_sha256() == baseline


@pytest.mark.parametrize(
    "limit_name, diagnostic",
    (
        ("_STATIC_SCANNER_COMMITMENT_EDGE_LIMIT", "edge"),
        ("_STATIC_SCANNER_COMMITMENT_ATTRIBUTE_LIMIT", "attribute"),
    ),
)
def test_task6_review3_commitment_enforces_independent_graph_bounds(
    monkeypatch,
    limit_name,
    diagnostic,
):
    from validation import literature_evidence_isolation as isolation

    monkeypatch.setattr(isolation, limit_name, 0, raising=False)

    with pytest.raises(
        AdapterContractError,
        match=f"scanner|semantic|dependency|{diagnostic}|bound",
    ):
        isolation._current_static_scanner_sha256()


def test_task6_review3_old_report_fails_after_external_binding_change(
    tmp_path,
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    report = isolation.scan_scientific_closure(
        _task6_safe_scan_closure(tmp_path),
        forbidden_fingerprints=_task6_absent_fingerprints(),
    )
    values = {
        field.name: getattr(report, field.name)
        for field in dataclasses.fields(type(report))
    }
    original = ast.walk

    def replacement(node):
        return original(node)

    monkeypatch.setattr(ast, "walk", replacement)

    with pytest.raises(
        AdapterContractError,
        match="scanner|commitment|unsupported|hash",
    ):
        isolation.StaticScanReport(**values)


def test_task6_review_static_scan_report_rejects_forged_scanner_identity(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    report = isolation.scan_scientific_closure(
        _task6_safe_scan_closure(tmp_path),
        forbidden_fingerprints=_task6_absent_fingerprints(),
    )
    values = {
        field.name: getattr(report, field.name)
        for field in dataclasses.fields(type(report))
    }
    values["scanner_version"] = "unrelated_scanner_v999"
    values["scanner_sha256"] = "0" * 64
    values["report_sha256"] = canonical_sha256(
        {
            key: value
            for key, value in values.items()
            if key != "report_sha256"
        }
    )

    with pytest.raises(
        AdapterContractError,
        match="scanner|version|supported|identity|commitment",
    ):
        isolation.StaticScanReport(**values)


@pytest.mark.parametrize("mutation", ("count", "reason"))
def test_task6_review_report_preflights_checks_before_recursive_freeze(
    tmp_path,
    monkeypatch,
    mutation,
):
    from validation import literature_evidence_isolation as isolation

    report = isolation.scan_scientific_closure(
        _task6_safe_scan_closure(tmp_path),
        forbidden_fingerprints=_task6_absent_fingerprints(),
    )
    values = {
        field.name: getattr(report, field.name)
        for field in dataclasses.fields(type(report))
    }
    bounded_iterations = None
    if mutation == "count":
        bounded_iterations = []

        class DeceptiveChecks(Mapping):
            def __len__(self):
                return len(report.checks)

            def __iter__(self):
                for index in range(isolation._STATIC_SCAN_CHECK_LIMIT + 1):
                    bounded_iterations.append(index)
                    yield f"check_{index}"
                bounded_iterations.append("overrun")
                raise AssertionError(
                    "static scan checks iterator exceeded its closed bound"
                )

            def __getitem__(self, key):
                return {"passed": True, "reason": "closed"}

        values["checks"] = DeceptiveChecks()
    else:
        values["checks"] = thaw_json(report.checks)
        first = next(iter(values["checks"]))
        values["checks"][first]["reason"] = (
            "r" * (isolation._STATIC_SCAN_REASON_BYTES_LIMIT + 1)
        )

    freeze_calls = []

    def unexpected_recursive_freeze(*args, **kwargs):
        freeze_calls.append((args, kwargs))
        raise AssertionError("recursive freeze ran before report preflight")

    monkeypatch.setattr(
        isolation, "_snapshot_json", unexpected_recursive_freeze
    )
    with pytest.raises(
        AdapterContractError,
        match="static|scan|check|reason|bound|oversized",
    ):
        isolation.StaticScanReport(**values)
    assert freeze_calls == []
    if bounded_iterations is not None:
        assert bounded_iterations == list(
            range(len(report.checks) + 1)
        )


def test_task6_review_builder_fstats_source_before_read_allocation(
    tmp_path,
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    module_name = "task6_science.adapters"
    _write_task5_source(
        tmp_path,
        module_name,
        "def scientific_entry(parameter):\n"
        "    return parameter + 123456789\n",
    )
    monkeypatch.setattr(
        isolation, "_STATIC_SCAN_AGGREGATE_MATERIAL_BYTES_LIMIT", 32
    )
    read_calls = []

    def unexpected_read_bytes(path):
        read_calls.append(path)
        raise AssertionError("source was read before fstat size preflight")

    monkeypatch.setattr(Path, "read_bytes", unexpected_read_bytes)
    with pytest.raises(
        AdapterContractError,
        match="source|file|material|byte|size|bound",
    ):
        isolation.build_scientific_closure(
            f"{module_name}:scientific_entry",
            role="adapter",
            source_roots=(tmp_path,),
        )
    assert read_calls == []


def test_task6_review2_reason_rejects_large_unicode_before_utf8_allocation():
    from validation import literature_evidence_isolation as isolation

    reason = "界" * 250_000
    encoded_size = len(reason.encode("utf-8"))
    checks = {
        name: {"passed": True, "reason": "closed"}
        for name in isolation._STATIC_SCAN_COMMON_CHECKS
    }
    first_name = sorted(checks)[0]
    checks[first_name]["reason"] = reason

    tracemalloc.start()
    try:
        with pytest.raises(
            AdapterContractError,
            match="static|scan|reason|bound|oversized",
        ):
            isolation._preflight_static_scan_checks(checks, "adapter")
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert peak < encoded_size // 2


def test_task6_review2_source_read_rejects_intermediate_symlink_swap(
    tmp_path,
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    source_root = tmp_path / "source-root"
    module_name = "task6_science.adapters"
    source = (
        "def scientific_entry(parameter):\n"
        "    return parameter + 1\n"
    )
    source_path = _write_task5_source(source_root, module_name, source)
    package_path = source_path.parent
    parked_package = tmp_path / "parked-package"
    outside_package = tmp_path / "outside-package"
    _write_task5_source(outside_package, "adapters", source)
    original_read = isolation._bounded_read_python_source
    swapped = []

    def swap_before_open(*args, **kwargs):
        package_path.rename(parked_package)
        package_path.symlink_to(outside_package, target_is_directory=True)
        swapped.append(True)
        return original_read(*args, **kwargs)

    monkeypatch.setattr(
        isolation, "_bounded_read_python_source", swap_before_open
    )

    with pytest.raises(
        AdapterContractError,
        match="source|symlink|open|safe|changed|root",
    ):
        isolation.build_scientific_closure(
            f"{module_name}:scientific_entry",
            role="adapter",
            source_roots=(source_root,),
        )
    assert swapped == [True]


@pytest.mark.parametrize(
    "mutation",
    ("same_size_content", "mode", "link_count", "timestamp"),
)
def test_task6_review2_source_read_rejects_in_place_change(
    tmp_path,
    monkeypatch,
    mutation,
):
    from validation import literature_evidence_isolation as isolation

    module_name = "task6_science.adapters"
    source = (
        "def scientific_entry(parameter):\n"
        "    return parameter + 1\n"
    )
    source_path = _write_task5_source(tmp_path, module_name, source)
    replacement = source.replace("+ 1", "+ 2").encode("utf-8")
    assert len(replacement) == source_path.stat().st_size
    original_read = isolation.os.read
    mutation_calls = []

    def mutate_after_read(descriptor, count):
        chunk = original_read(descriptor, count)
        if chunk and not mutation_calls:
            if mutation == "same_size_content":
                writer = os.open(source_path, os.O_WRONLY)
                try:
                    os.pwrite(writer, replacement, 0)
                finally:
                    os.close(writer)
            elif mutation == "mode":
                os.chmod(source_path, source_path.stat().st_mode ^ 0o100)
            elif mutation == "link_count":
                os.link(source_path, tmp_path / "linked-source.py")
            else:
                before = source_path.stat()
                os.utime(
                    source_path,
                    ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000),
                )
            mutation_calls.append(mutation)
        return chunk

    monkeypatch.setattr(isolation.os, "read", mutate_after_read)

    with pytest.raises(
        AdapterContractError,
        match="source|changed|read|safe",
    ):
        isolation.build_scientific_closure(
            f"{module_name}:scientific_entry",
            role="adapter",
            source_roots=(tmp_path,),
        )
    assert mutation_calls == [mutation]


def test_task6_review2_source_read_accepts_unchanged_regular_file(tmp_path):
    closure = _task6_build_scientific_closure(
        tmp_path,
        "adapter",
        "def scientific_entry(parameter):\n"
        "    return parameter + 1\n",
    )

    assert closure.role == "adapter"


def test_task6_review_formatter_stops_before_unbounded_materialization(
    tmp_path,
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    closure = _task6_build_scientific_closure(
        tmp_path,
        "adapter",
        "def scientific_entry(parameter):\n"
        "    return '{}'.format('x')\n",
    )
    monkeypatch.setattr(isolation, "_STATIC_SCAN_LOOKUP_ENTRY_LIMIT", 2)
    yielded = []

    def instrumented_parse(_formatter, _template):
        for index in range(3):
            yielded.append(index)
            yield "", str(index), "", None
        raise AssertionError("formatter parser was fully materialized")

    monkeypatch.setattr(string.Formatter, "parse", instrumented_parse)
    with pytest.raises(
        AdapterContractError,
        match="static|format|field|bound",
    ):
        isolation.scan_scientific_closure(
            closure,
            forbidden_fingerprints=_task6_absent_fingerprints(),
        )
    assert yielded == [0, 1, 2]


def test_task6_review_dict_union_preflights_projected_mapping_before_merge(
    tmp_path,
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    closure = _task6_build_scientific_closure(
        tmp_path,
        "adapter",
        "def scientific_entry(parameter):\n"
        "    return {'alpha': 1} | {'beta': 2}\n",
    )
    monkeypatch.setattr(isolation, "_STATIC_SCAN_LOOKUP_ENTRY_LIMIT", 1)
    calls = []
    original_preflight = isolation._static_preflight_mapping_merge

    def instrumented_preflight(left, right, *, reject_overlap):
        call = (tuple(left), tuple(right), reject_overlap)
        calls.append(call)
        if call == (("alpha",), ("beta",), False):
            raise AdapterContractError(
                "static scan mapping projected cardinality exceeds bound"
            )
        return original_preflight(
            left, right, reject_overlap=reject_overlap
        )

    monkeypatch.setattr(
        isolation,
        "_static_preflight_mapping_merge",
        instrumented_preflight,
    )
    with pytest.raises(
        AdapterContractError,
        match="mapping|projected|cardinality|bound",
    ):
        isolation.scan_scientific_closure(
            closure,
            forbidden_fingerprints=_task6_absent_fingerprints(),
        )
    assert (("alpha",), ("beta",), False) in calls


def _task6_review21_static_scan_report_values(*, failed_check=None):
    from validation import literature_evidence_isolation as isolation

    checks = FrozenJsonObject(
        {
            check_name: {
                "passed": check_name != failed_check,
                "reason": "bounded review21 check",
            }
            for check_name in isolation._STATIC_SCAN_COMMON_CHECKS
        }
    )
    values = {
        "schema_version": "static_scan_report_v1",
        "role": "adapter",
        "scanner_version": isolation._STATIC_SCANNER_VERSION,
        "scanner_sha256": isolation._current_static_scanner_sha256(),
        "scanned_closure_sha256": "1" * 64,
        "fingerprint_commitment_sha256": "2" * 64,
        "checks": checks,
        "passed": True,
    }
    values["report_sha256"] = canonical_sha256(values)
    return values


def test_task6_review21_shadowed_values_cannot_accept_failed_check(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    values = _task6_review21_static_scan_report_values(
        failed_check="raw_ast_closed"
    )
    baseline_sha256 = values["scanner_sha256"]
    with pytest.raises(
        AdapterContractError,
        match="static|scan|pass|status|check",
    ):
        isolation.StaticScanReport(**values)
    calls = []

    def empty_values(receiver):
        calls.append(receiver)
        return ()

    monkeypatch.setattr(
        FrozenJsonObject, "values", empty_values, raising=False
    )

    assert isolation._current_static_scanner_sha256() == baseline_sha256
    assert calls == []
    with pytest.raises(
        AdapterContractError,
        match="static|scan|pass|status|check",
    ):
        isolation.StaticScanReport(**values)
    assert calls == []


def test_task6_review21_exact_storage_requires_canonical_key_order():
    from validation import literature_evidence_isolation as isolation

    values = _task6_review21_static_scan_report_values()
    canonical_checks = values["checks"]
    reversed_checks = object.__new__(FrozenJsonObject)
    object.__setattr__(
        reversed_checks,
        "_items",
        tuple(reversed(canonical_checks._items)),
    )
    values["checks"] = reversed_checks
    values["report_sha256"] = canonical_sha256(
        {
            key: value
            for key, value in values.items()
            if key != "report_sha256"
        }
    )

    with pytest.raises(
        AdapterContractError,
        match="static|scan|frozen|storage|exact|canonical",
    ):
        isolation.StaticScanReport(**values)


def test_task6_review21_behavior_change_makes_old_report_stale(monkeypatch):
    from validation import literature_evidence_isolation as isolation

    values = _task6_review21_static_scan_report_values()
    baseline_sha256 = values["scanner_sha256"]
    monkeypatch.setattr(
        isolation,
        "_STATIC_SCAN_REASON_BYTES_LIMIT",
        isolation._STATIC_SCAN_REASON_BYTES_LIMIT + 1,
    )

    assert isolation._current_static_scanner_sha256() != baseline_sha256
    with pytest.raises(
        AdapterContractError,
        match="scanner|commitment|unsupported|hash",
    ):
        isolation.StaticScanReport(**values)


@pytest.mark.parametrize(
    "member_name,expected_owner",
    (
        pytest.param("__getitem__", FrozenJsonObject, id="getitem"),
        pytest.param("__iter__", FrozenJsonObject, id="iter"),
        pytest.param("__len__", FrozenJsonObject, id="len"),
        pytest.param("values", Mapping, id="inherited-values"),
        pytest.param("items", Mapping, id="inherited-items"),
    ),
)
def test_task6_review21_effective_mapping_slots_are_outside_report_semantics(
    monkeypatch,
    member_name,
    expected_owner,
):
    from validation import literature_evidence_isolation as isolation

    values = _task6_review21_static_scan_report_values()
    baseline_sha256 = values["scanner_sha256"]
    owner = next(
        candidate
        for candidate in FrozenJsonObject.__mro__
        if member_name in vars(candidate)
    )
    descriptor = vars(owner)[member_name]
    assert owner is expected_owner
    assert inspect.isfunction(descriptor)
    calls = []

    def replacement(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError(
            f"trusted report validation executed {member_name}"
        )

    monkeypatch.setattr(owner, member_name, replacement)

    assert isolation._current_static_scanner_sha256() == baseline_sha256
    assert calls == []
    accepted = isolation.StaticScanReport(**values)
    assert accepted.passed is True
    assert calls == []


@pytest.mark.parametrize("member_name", ("values", "items"))
def test_task6_review21_mapping_shadows_are_outside_report_semantics(
    monkeypatch,
    member_name,
):
    from validation import literature_evidence_isolation as isolation

    values = _task6_review21_static_scan_report_values()
    baseline_sha256 = values["scanner_sha256"]
    assert member_name not in vars(FrozenJsonObject)
    assert member_name in vars(Mapping)
    calls = []

    def replacement(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError(
            f"trusted report validation executed shadowed {member_name}"
        )

    monkeypatch.setattr(
        FrozenJsonObject, member_name, replacement, raising=False
    )

    assert isolation._current_static_scanner_sha256() == baseline_sha256
    assert calls == []
    accepted = isolation.StaticScanReport(**values)
    assert accepted.passed is True
    assert calls == []


class _Task6Review22AlternateItemsAccessor:
    def __init__(self):
        self.calls = []

    @staticmethod
    def _alternate(items):
        if type(items) is not tuple:
            return items
        return tuple(
            (key, True) if key == "passed" else pair
            for pair in items
            for key in (pair[0],)
        )

    def __get__(self, instance, owner=None):
        self.calls.append(("get", instance))
        if instance is None:
            return self
        namespace = object.__getattribute__(instance, "__dict__")
        return self._alternate(dict.__getitem__(namespace, "_items"))

    def __set__(self, instance, value):
        self.calls.append(("set", instance))
        namespace = object.__getattribute__(instance, "__dict__")
        dict.__setitem__(namespace, "_items", self._alternate(value))


def _task6_review22_with_items_accessor(callback):
    missing = object()
    previous = vars(FrozenJsonObject).get("_items", missing)
    accessor = _Task6Review22AlternateItemsAccessor()
    setattr(FrozenJsonObject, "_items", accessor)
    try:
        result = callback()
    finally:
        if previous is missing:
            delattr(FrozenJsonObject, "_items")
        else:
            setattr(FrozenJsonObject, "_items", previous)
    return result, accessor.calls


def _task6_review22_exact_frozen(items):
    value = object.__new__(FrozenJsonObject)
    namespace = object.__getattribute__(value, "__dict__")
    dict.__setitem__(namespace, "_items", items)
    return value


def test_task6_review22_items_accessor_is_unreachable_from_sha_and_reports():
    from validation import literature_evidence_isolation as isolation

    values = _task6_review21_static_scan_report_values()
    baseline_sha256 = values["scanner_sha256"]
    original = isolation.StaticScanReport(**values)

    def exercise():
        current_sha256 = isolation._current_static_scanner_sha256()
        created_checks = isolation._static_scan_checks("adapter")
        accepted = isolation.StaticScanReport(**values)
        reconstructed = isolation._snapshot_exact_record(
            original,
            isolation.StaticScanReport,
            "scan_report",
        )
        return current_sha256, created_checks, accepted, reconstructed

    observed, calls = _task6_review22_with_items_accessor(exercise)
    current_sha256, created_checks, accepted, reconstructed = observed

    assert current_sha256 == baseline_sha256
    assert type(created_checks) is dict
    assert accepted.report_sha256 == original.report_sha256
    assert reconstructed.report_sha256 == original.report_sha256
    assert calls == [], (
        "validated report data must not be sent back through general "
        "FrozenJsonObject attribute-based serialization"
    )


def test_task6_review22_alternate_nested_data_cannot_replace_preflight_data():
    from validation import literature_evidence_isolation as isolation

    values = _task6_review21_static_scan_report_values(
        failed_check="raw_ast_closed"
    )
    passed_checks = thaw_json(values["checks"])
    passed_checks["raw_ast_closed"]["passed"] = True
    passed_payload = {
        key: (passed_checks if key == "checks" else value)
        for key, value in values.items()
        if key != "report_sha256"
    }
    values["report_sha256"] = canonical_sha256(passed_payload)

    def exercise():
        try:
            isolation.StaticScanReport(**values)
        except AdapterContractError as error:
            return error
        return None

    observed_error, calls = _task6_review22_with_items_accessor(exercise)

    assert calls == [], (
        "report validation must use only the exact built-in data returned "
        "by preflight"
    )
    assert isinstance(observed_error, AdapterContractError)
    assert re.search(
        "static|scan|pass|status|check",
        str(observed_error),
        flags=re.IGNORECASE,
    )


def test_task6_review22_normal_wire_digest_and_reconstruction_are_compatible():
    from validation import literature_evidence_isolation as isolation

    values = _task6_review21_static_scan_report_values()
    report = isolation.StaticScanReport(**values)
    built_in_checks = thaw_json(report.checks)
    wire_payload = {
        field.name: (
            built_in_checks
            if field.name == "checks"
            else getattr(report, field.name)
        )
        for field in dataclasses.fields(type(report))
        if field.name != "report_sha256"
    }
    reconstructed = isolation.StaticScanReport(
        **{**wire_payload, "report_sha256": report.report_sha256}
    )

    assert report.schema_version == "static_scan_report_v1"
    assert report.report_sha256 == canonical_sha256(wire_payload)
    assert canonical_json_bytes(_task6_static_scan_payload(report)) == (
        canonical_json_bytes(wire_payload)
    )
    assert thaw_json(reconstructed.checks) == built_in_checks
    assert reconstructed.report_sha256 == report.report_sha256


@pytest.mark.parametrize("malformation", ("outer_order", "nested_order"))
def test_task6_review22_malformed_exact_storage_fails_closed(malformation):
    from validation import literature_evidence_isolation as isolation

    values = _task6_review21_static_scan_report_values()
    outer_namespace = object.__getattribute__(values["checks"], "__dict__")
    outer_items = dict.__getitem__(outer_namespace, "_items")
    if malformation == "outer_order":
        malformed_items = tuple(reversed(outer_items))
    else:
        first_name, first_check = outer_items[0]
        nested_namespace = object.__getattribute__(first_check, "__dict__")
        nested_items = dict.__getitem__(nested_namespace, "_items")
        malformed_check = _task6_review22_exact_frozen(
            tuple(reversed(nested_items))
        )
        malformed_items = (
            (first_name, malformed_check),
            *outer_items[1:],
        )
    values["checks"] = _task6_review22_exact_frozen(malformed_items)

    with pytest.raises(
        AdapterContractError,
        match="static|scan|frozen|storage|exact|canonical",
    ):
        isolation.StaticScanReport(**values)


class _Task6Review23EmptyItemsAccessor:
    def __init__(self):
        self.calls = []

    def __get__(self, instance, owner=None):
        self.calls.append(("get", instance))
        return self if instance is None else ()

    def __set__(self, instance, value):
        self.calls.append(("set", instance))
        namespace = object.__getattribute__(instance, "__dict__")
        dict.__setitem__(namespace, "_items", value)


def _task6_review23_with_empty_items_accessor(callback):
    missing = object()
    previous = vars(FrozenJsonObject).get("_items", missing)
    accessor = _Task6Review23EmptyItemsAccessor()
    setattr(FrozenJsonObject, "_items", accessor)
    try:
        try:
            outcome = callback()
        except Exception as error:
            outcome = error
    finally:
        if previous is missing:
            delattr(FrozenJsonObject, "_items")
        else:
            setattr(FrozenJsonObject, "_items", previous)
    return outcome, accessor.calls


@pytest.mark.parametrize("role", ("adapter", "oracle"))
def test_task6_review23_policy_builder_rejects_forbidden_exact_data_without_accessor(
    monkeypatch,
    role,
):
    from validation import literature_evidence_isolation as isolation

    if role == "adapter":
        definition, _canaries = _task6_mutated_adapter_definition(
            "answer_lookup_table"
        )
        catalog = dict(adapters.ADAPTER_DEFINITIONS)
        catalog[definition.adapter_id] = definition
        monkeypatch.setattr(
            adapters,
            "ADAPTER_DEFINITIONS",
            MappingProxyType(catalog),
        )
        closure = _task5_adapter_closure()
    else:
        definition, _canaries = _task6_mutated_oracle_definition(
            "answer_lookup_table"
        )
        closure = _task5_oracle_closure()
    original_scan = isolation._scan_policy_forbidden_structures
    accessor_calls = []

    def instrumented_scan(value, **kwargs):
        setattr(
            isolation,
            "_scan_policy_forbidden_structures",
            original_scan,
        )
        outcome, calls = _task6_review23_with_empty_items_accessor(
            lambda: original_scan(value, **kwargs)
        )
        accessor_calls.extend(calls)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(
        isolation,
        "_scan_policy_forbidden_structures",
        instrumented_scan,
    )
    try:
        commitment = isolation.build_scientific_policy_commitment(
            definition,
            closure,
            role=role,
        )
    except AdapterContractError as error:
        observed_error = error
        commitment = None
    finally:
        setattr(
            isolation,
            "_scan_policy_forbidden_structures",
            original_scan,
        )

    assert accessor_calls == [], (
        "scientific-policy scanning must not resolve a class-level "
        "FrozenJsonObject._items accessor"
    )
    assert commitment is None
    assert isinstance(observed_error, AdapterContractError)
    assert re.search(
        "definition|scientific|policy|lookup|forbidden",
        str(observed_error),
        flags=re.IGNORECASE,
    )


@pytest.mark.parametrize("role", ("adapter", "oracle"))
def test_task6_review23_canonical_policy_scan_is_accessor_independent(
    role,
):
    from validation import literature_evidence_adapter_oracles as oracles
    from validation import literature_evidence_isolation as isolation

    if role == "adapter":
        definition = adapters.ADAPTER_DEFINITIONS[
            "square_ising_self_dual_tc"
        ]
        payload = adapters.adapter_definition_to_frozen_json(definition)
        closure = _task5_adapter_closure()
    else:
        definition = _synthetic_oracle_definition()
        payload = oracles.oracle_definition_to_frozen_json(definition)
        closure = _task5_oracle_closure()
    expected_bytes = canonical_json_bytes(payload)
    baseline_sha256 = isolation._current_static_scanner_sha256()

    def exercise():
        current_sha256 = isolation._current_static_scanner_sha256()
        isolation._scan_policy_forbidden_structures(payload, role=role)
        return current_sha256

    observed, calls = _task6_review23_with_empty_items_accessor(exercise)
    commitment = isolation.build_scientific_policy_commitment(
        definition,
        closure,
        role=role,
    )

    assert observed == baseline_sha256
    assert calls == []
    assert commitment.canonical_definition_bytes == expected_bytes
    assert commitment.canonical_definition_sha256 == hashlib.sha256(
        expected_bytes
    ).hexdigest()


@pytest.mark.parametrize("role", ("adapter", "oracle"))
def test_task6_review23_policy_scan_rejects_noncanonical_exact_storage(role):
    from validation import literature_evidence_adapter_oracles as oracles
    from validation import literature_evidence_isolation as isolation

    if role == "adapter":
        definition = adapters.ADAPTER_DEFINITIONS[
            "square_ising_self_dual_tc"
        ]
        payload = adapters.adapter_definition_to_frozen_json(definition)
    else:
        payload = oracles.oracle_definition_to_frozen_json(
            _synthetic_oracle_definition()
        )
    namespace = object.__getattribute__(payload, "__dict__")
    items = dict.__getitem__(namespace, "_items")
    malformed = _task6_review22_exact_frozen(tuple(reversed(items)))

    with pytest.raises(
        AdapterContractError,
        match="scientific|policy|frozen|storage|exact|canonical",
    ):
        isolation._scan_policy_forbidden_structures(
            malformed,
            role=role,
        )


class _Task6Review24EmptyItemsAccessor:
    def __init__(self):
        self.calls = []

    def __get__(self, instance, owner=None):
        self.calls.append(("get", instance))
        return self if instance is None else ()

    def __set__(self, instance, value):
        self.calls.append(("set", instance))
        namespace = object.__getattribute__(instance, "__dict__")
        dict.__setitem__(namespace, "_items", ())


def _task6_review24_at_policy_scan_boundary(isolation, callback):
    original_scan = isolation._scan_policy_forbidden_structures
    accessor = _Task6Review24EmptyItemsAccessor()

    def boundary_scan(value, **kwargs):
        setattr(
            isolation,
            "_scan_policy_forbidden_structures",
            original_scan,
        )
        missing = object()
        previous = vars(FrozenJsonObject).get("_items", missing)
        setattr(FrozenJsonObject, "_items", accessor)
        try:
            return original_scan(value, **kwargs)
        finally:
            if previous is missing:
                delattr(FrozenJsonObject, "_items")
            else:
                setattr(FrozenJsonObject, "_items", previous)

    setattr(isolation, "_scan_policy_forbidden_structures", boundary_scan)
    try:
        try:
            outcome = callback()
        except Exception as error:
            outcome = error
    finally:
        setattr(
            isolation,
            "_scan_policy_forbidden_structures",
            original_scan,
        )
    return outcome, accessor.calls


def _task6_review24_definition_with_authored_text(
    monkeypatch,
    role,
    authored_text,
):
    from validation import literature_evidence_adapter_oracles as oracles

    if role == "adapter":
        canonical = adapters.ADAPTER_DEFINITIONS[
            "square_ising_self_dual_tc"
        ]
        payload = thaw_json(
            adapters.adapter_definition_to_frozen_json(canonical)
        )
        payload["runtime_requirements"]["backend_resources"].append(
            authored_text
        )
        definition = adapters.adapter_definition_from_frozen_json(
            freeze_json(payload)
        )
        catalog = dict(adapters.ADAPTER_DEFINITIONS)
        catalog[definition.adapter_id] = definition
        monkeypatch.setattr(
            adapters,
            "ADAPTER_DEFINITIONS",
            MappingProxyType(catalog),
        )
        return definition, _task5_adapter_closure()
    canonical = _synthetic_oracle_definition()
    runtime = canonical.runtime_requirements
    definition = oracles.OracleDefinition(
        **{
            field.name: (
                RuntimeRequirements(
                    runtime.interpreter,
                    runtime.packages,
                    runtime.native_libraries,
                    runtime.backend_resources + (authored_text,),
                )
                if field.name == "runtime_requirements"
                else getattr(canonical, field.name)
            )
            for field in dataclasses.fields(type(canonical))
        }
    )
    return definition, _task5_oracle_closure()


@pytest.mark.parametrize("role", ("adapter", "oracle"))
def test_task6_review24_policy_builder_rejects_forbidden_canonical_json_text_without_accessor(
    monkeypatch,
    role,
):
    from validation import literature_evidence_isolation as isolation

    forbidden_text = '{"lookup_table":{"alpha":731}}'
    definition, closure = _task6_review24_definition_with_authored_text(
        monkeypatch,
        role,
        forbidden_text,
    )
    baseline_sha256 = isolation._current_static_scanner_sha256()

    outcome, calls = _task6_review24_at_policy_scan_boundary(
        isolation,
        lambda: isolation.build_scientific_policy_commitment(
            definition,
            closure,
            role=role,
        ),
    )

    assert isolation._current_static_scanner_sha256() == baseline_sha256
    assert calls == [], (
        "parsed policy text must remain exact built-in JSON from parsing "
        "through nested scanning"
    )
    assert isinstance(outcome, AdapterContractError)
    assert re.search(
        "definition|scientific|policy|lookup|forbidden",
        str(outcome),
        flags=re.IGNORECASE,
    )


def test_task6_review24_focused_parsed_text_scan_is_accessor_independent():
    from validation import literature_evidence_isolation as isolation

    baseline_sha256 = isolation._current_static_scanner_sha256()
    outcome, calls = _task6_review24_at_policy_scan_boundary(
        isolation,
        lambda: isolation._scan_policy_forbidden_structures(
            '{"lookup_table":{"alpha":731}}',
            role="adapter",
        ),
    )

    assert isolation._current_static_scanner_sha256() == baseline_sha256
    assert calls == []
    assert isinstance(outcome, AdapterContractError)
    assert re.search(
        "definition|scientific|policy|lookup|forbidden",
        str(outcome),
        flags=re.IGNORECASE,
    )


@pytest.mark.parametrize(
    "text",
    (
        '  {"lookup_table":{"alpha":731}}\n',
        '"{\\"lookup_table\\":{\\"alpha\\":731}}"',
    ),
    ids=("stripped-canonical", "nested-json-string"),
)
def test_task6_review24_canonical_text_layers_remain_recursively_scanned(text):
    from validation import literature_evidence_isolation as isolation

    with pytest.raises(
        AdapterContractError,
        match="definition|scientific|policy|lookup|forbidden",
    ):
        isolation._scan_policy_forbidden_structures(text, role="adapter")


@pytest.mark.parametrize("role", ("adapter", "oracle"))
def test_task6_review24_ordinary_canonical_text_preserves_commitment_bytes(
    monkeypatch,
    role,
):
    from validation import literature_evidence_adapter_oracles as oracles
    from validation import literature_evidence_isolation as isolation

    definition, closure = _task6_review24_definition_with_authored_text(
        monkeypatch,
        role,
        '{"method":"bounded"}',
    )
    if role == "adapter":
        expected_payload = adapters.adapter_definition_to_frozen_json(
            definition
        )
    else:
        expected_payload = oracles.oracle_definition_to_frozen_json(
            definition
        )
    expected_bytes = canonical_json_bytes(expected_payload)

    commitment = isolation.build_scientific_policy_commitment(
        definition,
        closure,
        role=role,
    )

    assert commitment.canonical_definition_bytes == expected_bytes
    assert commitment.canonical_definition_sha256 == hashlib.sha256(
        expected_bytes
    ).hexdigest()


@pytest.mark.parametrize(
    "text",
    (
        '{"lookup_table": {"alpha":731}}',
        '{"z":0,"lookup_table":{"alpha":731}}',
        '{"lookup_table":',
        '{"lookup_table":NaN}',
    ),
    ids=("spacing", "key-order", "malformed", "nonfinite-token"),
)
def test_task6_review24_noncanonical_or_invalid_text_is_not_nested_json(text):
    from validation import literature_evidence_isolation as isolation

    isolation._scan_policy_forbidden_structures(text, role="adapter")


@pytest.mark.parametrize(
    "text,diagnostic",
    (
        (
            '"' + ("x" * (1_048_576 + 1)) + '"',
            "byte",
        ),
        (
            ("[" * 257) + "0" + ("]" * 257),
            "depth",
        ),
        (
            str(1 << 4096),
            "integer",
        ),
        (
            "1e999",
            "JSON",
        ),
    ),
    ids=("oversized", "deep", "integer", "nonfinite-number"),
)
def test_task6_review24_parsed_text_respects_closed_json_bounds(
    text,
    diagnostic,
):
    from validation import literature_evidence_isolation as isolation

    with pytest.raises(
        AdapterContractError,
        match=f"static|scan|canonical|text|JSON|{diagnostic}|bound",
    ):
        isolation._scan_policy_forbidden_structures(text, role="adapter")


@pytest.mark.parametrize(
    "value",
    (
        math.nan,
        math.inf,
        -math.inf,
        (1,),
        b"1",
        type("Task6Review24Dict", (dict,), {})({"alpha": 1}),
        type("Task6Review24List", (list,), {})([1]),
    ),
    ids=(
        "nan",
        "positive-infinity",
        "negative-infinity",
        "tuple",
        "bytes",
        "dict-subclass",
        "list-subclass",
    ),
)
def test_task6_review24_exact_json_serializer_rejects_nonexact_values(value):
    from validation import literature_evidence_isolation as isolation

    with pytest.raises(
        AdapterContractError,
        match="scientific|canonical|text|exact|JSON",
    ):
        isolation._static_exact_builtin_json_bytes(value)


def test_task6_review24_exact_json_serializer_is_mapping_order_independent():
    from validation import literature_evidence_isolation as isolation

    expected = b'{"alpha":1,"zeta":[2,3]}'

    assert isolation._static_exact_builtin_json_bytes(
        {"zeta": [2, 3], "alpha": 1}
    ) == expected
    assert isolation._static_exact_builtin_json_bytes(
        {"alpha": 1, "zeta": [2, 3]}
    ) == expected


def _task6_review25_nested_canonical_text(layer_count, scalar_size):
    text = "x" * scalar_size
    for _ in range(layer_count):
        text = json.dumps(
            text,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    return text


def test_task6_review25_policy_scan_rejects_cumulative_canonical_text_material():
    from validation import literature_evidence_isolation as isolation

    text = _task6_review25_nested_canonical_text(18, 500_000)

    with pytest.raises(
        AdapterContractError,
        match="scientific|canonical|text|material|bound",
    ):
        isolation._scan_policy_forbidden_structures(text, role="adapter")


@pytest.mark.parametrize("role", ("adapter", "oracle"))
def test_task6_review25_policy_builders_reject_cumulative_canonical_text_material(
    monkeypatch,
    role,
):
    from validation import literature_evidence_isolation as isolation

    text = _task6_review25_nested_canonical_text(18, 500_000)
    definition, closure = _task6_review24_definition_with_authored_text(
        monkeypatch,
        role,
        text,
    )

    with pytest.raises(
        AdapterContractError,
        match="scientific|canonical|text|material|bound",
    ):
        isolation.build_scientific_policy_commitment(
            definition,
            closure,
            role=role,
        )


def test_task6_review25_policy_scan_accepts_canonical_text_under_material_bound():
    from validation import literature_evidence_isolation as isolation

    text = _task6_review25_nested_canonical_text(16, 500_000)

    isolation._scan_policy_forbidden_structures(text, role="adapter")


def test_task6_review25_policy_scan_shares_exact_material_bound_across_siblings(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    text = json.dumps("bounded", separators=(",", ":"))
    exact_bound = 4 * len(text.encode("utf-8"))
    monkeypatch.setattr(
        isolation,
        "_STATIC_SCAN_AGGREGATE_MATERIAL_BYTES_LIMIT",
        exact_bound,
    )
    isolation._scan_policy_forbidden_structures(
        (text, text),
        role="adapter",
    )

    monkeypatch.setattr(
        isolation,
        "_STATIC_SCAN_AGGREGATE_MATERIAL_BYTES_LIMIT",
        exact_bound - 1,
    )
    with pytest.raises(
        AdapterContractError,
        match="scientific|canonical|text|material|bound",
    ):
        isolation._scan_policy_forbidden_structures(
            (text, text),
            role="adapter",
        )


@pytest.mark.parametrize(
    "text",
    (
        '{"method": "bounded"}',
        '{"method":',
    ),
    ids=("noncanonical", "malformed"),
)
def test_task6_review25_policy_scan_does_not_charge_unparsed_authored_text(
    monkeypatch,
    text,
):
    from validation import literature_evidence_isolation as isolation

    monkeypatch.setattr(
        isolation,
        "_STATIC_SCAN_AGGREGATE_MATERIAL_BYTES_LIMIT",
        0,
    )

    isolation._scan_policy_forbidden_structures(text, role="adapter")


def test_task6_review25_policy_scan_still_rejects_nested_lookup():
    from validation import literature_evidence_isolation as isolation

    with pytest.raises(
        AdapterContractError,
        match="definition|scientific|policy|lookup|forbidden",
    ):
        isolation._scan_policy_forbidden_structures(
            '"{\\"lookup_table\\":{\\"alpha\\":731}}"',
            role="adapter",
        )


def _task7_resource_row(path, destination, purpose, *, distribution=None,
                        version=None, link_identity=()):
    resolved = path.resolve(strict=True)
    metadata = resolved.stat()
    return {
        "logical_destination": destination,
        "resolved_path": str(resolved),
        "link_identity": link_identity,
        "file_type": "regular",
        "size": metadata.st_size,
        "mode": metadata.st_mode & 0o777,
        "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
        "distribution": distribution,
        "version": version,
        "purpose": purpose,
    }


def _task7_manifest(*rows):
    from validation import literature_evidence_isolation as isolation

    body = {
        "schema_version": "runtime_resource_manifest_v1",
        "resources": rows,
    }
    return isolation.RuntimeResourceManifest(
        body["schema_version"], rows, canonical_sha256(body)
    )


def _task7_build_snapshot(tmp_path, monkeypatch, *, source_bytes=b"frozen"):
    from validation import literature_evidence_isolation as isolation

    source = tmp_path / "installed-resource.bin"
    source.write_bytes(source_bytes)
    source.chmod(0o644)
    manifest = _task7_manifest(
        _task7_resource_row(
            source,
            "/runtime/backend/resource.bin",
            "declared_backend_resource",
        )
    )
    monkeypatch.setattr(
        isolation, "discover_runtime_resources", lambda requirements: manifest
    )
    snapshot = isolation.build_runtime_snapshot(
        RuntimeRequirements("python3", (), (), (str(source),)),
        run_directory=tmp_path / "exclusive-run",
        event_recorder=lambda event_name, details: None,
    )
    copied_name = os.listdir(snapshot.snapshot_root)[0]
    return source, snapshot, Path(snapshot.snapshot_root) / copied_name


def _task7_ldd_output(tmp_path):
    loader = tmp_path / "ld-linux-task7.so.2"
    if not loader.exists():
        loader.write_bytes(b"task7-loader")
        loader.chmod(0o755)
    return f"{loader} (0x1)\n"


def test_runtime_resource_discovery_closes_exact_declared_file_set(tmp_path):
    from validation import literature_evidence_isolation as isolation

    resource_dir = tmp_path / "installed-runtime"
    resource_dir.mkdir()
    paths = {
        name: resource_dir / name
        for name in (
            "python-real", "ld-linux.so", "libdemo.so", "token_native.so",
            "json.py", "demo_dist.py", "backend-table.dat",
        )
    }
    payloads = {
        "python-real": b"interpreter-v1",
        "ld-linux.so": b"loader-v1",
        "libdemo.so": b"ldd-library-v1",
        "token_native.so": b"declared-native-v1",
        "json.py": b"stdlib-v1",
        "demo_dist.py": b"distribution-v1",
        "backend-table.dat": b"backend-resource-v1",
    }
    for name, path in paths.items():
        path.write_bytes(payloads[name])
        path.chmod(0o755 if name in {"python-real", "ld-linux.so"} else 0o644)
    interpreter_link = resource_dir / "python3"
    interpreter_link.symlink_to(paths["python-real"].name)

    def command_probe(argv):
        assert argv == ("ldd", str(paths["python-real"].resolve()))
        return (
            f"libdemo.so => {paths['libdemo.so']} (0x1)\n"
            f"{paths['ld-linux.so']} (0x2)\n"
        )

    def file_probe(operation, value):
        responses = {
            ("resolve_interpreter", "python3"): interpreter_link,
            ("imported_stdlib_files", ("demo-dist",)): (
                ("json.py", paths["json.py"]),
            ),
            ("distribution", "demo-dist"): {
                "name": "demo-dist",
                "version": "1.2.3",
                "files": (paths["demo_dist.py"],),
            },
            ("native_library", "token-native"): paths["token_native.so"],
            ("backend_resource", str(paths["backend-table.dat"])): paths[
                "backend-table.dat"
            ],
        }
        response = responses[(operation, value)]
        if operation == "distribution":
            response = {
                **response,
                "files": (("demo_dist.py", response["files"][0]),),
            }
        return response

    requirements = RuntimeRequirements(
        "python3", ("demo-dist",), ("token-native",),
        (str(paths["backend-table.dat"]),)
    )
    manifest = isolation.discover_runtime_resources(
        requirements,
        command_probe=command_probe,
        file_probe=file_probe,
    )

    assert type(manifest) is isolation.RuntimeResourceManifest
    assert len(manifest.resources) == 7
    assert {row["resolved_path"] for row in manifest.resources} == {
        str(path.resolve()) for path in paths.values()
    }
    assert {
        row["purpose"] for row in manifest.resources
    } == {
        "interpreter", "dynamic_loader", "dynamic_library",
        "declared_native_library", "imported_standard_library",
        "declared_distribution_file", "declared_backend_resource",
    }
    expected_keys = {
        "logical_destination", "resolved_path", "link_identity", "file_type",
        "size", "mode", "sha256", "distribution", "version", "purpose",
    }
    for row in manifest.resources:
        assert set(row) == expected_keys
        assert row["file_type"] == "regular"
        assert row["size"] == len(Path(row["resolved_path"]).read_bytes())
        assert row["mode"] in {0o644, 0o755}
        assert row["sha256"] == hashlib.sha256(
            Path(row["resolved_path"]).read_bytes()
        ).hexdigest()
    interpreter_row = next(
        row for row in manifest.resources if row["purpose"] == "interpreter"
    )
    assert len(interpreter_row["link_identity"]) == 1
    assert interpreter_row["link_identity"][0]["path"] == str(
        interpreter_link
    )
    distribution_row = next(
        row
        for row in manifest.resources
        if row["purpose"] == "declared_distribution_file"
    )
    assert distribution_row["distribution"] == "demo-dist"
    assert distribution_row["version"] == "1.2.3"
    assert manifest.manifest_sha256 == canonical_sha256(
        {
            "schema_version": "runtime_resource_manifest_v1",
            "resources": manifest.resources,
        }
    )


def test_runtime_ldd_parser_accepts_only_anchored_dynamic_rows(tmp_path):
    from validation import literature_evidence_isolation as isolation

    library = tmp_path / "libdemo.so"
    loader = tmp_path / "ld-linux-x86-64.so.2"
    output = (
        "\tlinux-vdso.so.1 =>   (0x00007fff)\n"
        f"libdemo.so\t=>\t{library}\t  (0x000012ab)\n"
        f"  {loader}    (0x000034cd)\n"
    )

    assert isolation._runtime_ldd_paths(output) == (
        ("libdemo.so", library, False, False),
        (loader.name, loader, True, True),
    )


@pytest.mark.parametrize(
    "unsafe_output",
    (
        "",
        "   \n\t",
        "statically linked\n",
        "not a dynamic executable\n",
        "libmissing.so => not found\n",
        "unexpected diagnostic text\n",
        "/absolute/noise-without-address\n",
        "/absolute/noise-with-address (0x1)\n",
    ),
)
def test_runtime_ldd_parser_fails_closed_on_incomplete_or_unknown_output(
    unsafe_output,
):
    from validation import literature_evidence_isolation as isolation

    with pytest.raises(AdapterContractError, match="ldd|loader|dynamic"):
        isolation._runtime_ldd_paths(unsafe_output)


def test_runtime_resource_discovery_requires_a_dynamic_loader_identity(tmp_path):
    library = tmp_path / "libdemo.so"
    library.write_bytes(b"library")

    with pytest.raises(AdapterContractError, match="loader"):
        _task7_discover_only_ldd(
            tmp_path, f"libdemo.so => {library} (0x1)\n"
        )


def test_runtime_resource_discovery_deduplicates_ldd_file_identity(tmp_path):
    from validation import literature_evidence_isolation as isolation

    interpreter = tmp_path / "python"
    library = tmp_path / "libdemo.so"
    library_alias = tmp_path / "libdemo-alias.so"
    loader = tmp_path / "ld-linux-x86-64.so.2"
    for path in (interpreter, library, loader):
        path.write_bytes(path.name.encode())
    os.link(library, library_alias)

    def probe(operation, value):
        if operation == "resolve_interpreter":
            return interpreter
        if operation == "imported_stdlib_files":
            return ()
        raise AssertionError((operation, value))

    manifest = isolation.discover_runtime_resources(
        RuntimeRequirements("python3", (), (), ()),
        command_probe=lambda argv: (
            f"libdemo.so => {library} (0x1)\n"
            f"libdemo-alias.so => {library_alias} (0x2)\n"
            f"{loader} (0x3)\n"
        ),
        file_probe=probe,
    )

    ldd_rows = tuple(
        row
        for row in manifest.resources
        if row["purpose"] in {"dynamic_library", "dynamic_loader"}
    )
    assert [row["purpose"] for row in ldd_rows] == [
        "dynamic_loader", "dynamic_library"
    ]


def _task7_discover_only_ldd(tmp_path, output):
    from validation import literature_evidence_isolation as isolation

    interpreter = tmp_path / "python"
    if not interpreter.exists():
        interpreter.write_bytes(b"python")

    def probe(operation, value):
        if operation == "resolve_interpreter":
            return interpreter
        if operation == "imported_stdlib_files":
            return ()
        raise AssertionError((operation, value))

    return isolation.discover_runtime_resources(
        RuntimeRequirements("python3", (), (), ()),
        command_probe=lambda argv: output,
        file_probe=probe,
    )


def test_runtime_ldd_accepts_vdso64_and_ld64_loader(tmp_path):
    loader = tmp_path / "ld64.so.2"
    loader.write_bytes(b"power-loader")

    manifest = _task7_discover_only_ldd(
        tmp_path,
        "linux-vdso64.so.1 => (0x1000)\n"
        f"{loader} (0x2000)\n",
    )

    loader_rows = tuple(
        row
        for row in manifest.resources
        if row["purpose"] == "dynamic_loader"
    )
    assert len(loader_rows) == 1
    assert loader_rows[0]["resolved_path"] == str(loader.resolve())


def test_runtime_ldd_groups_duplicate_loader_aliases_before_cardinality(
    tmp_path,
):
    first = tmp_path / "ld64.so.1"
    second = tmp_path / "ld64.so.2"
    first.write_bytes(b"one-loader-inode")
    os.link(first, second)
    first_output = f"{first} (0x1)\n{second} (0x2)\n"
    second_output = f"{second} (0x2)\n{first} (0x1)\n"

    manifest_one = _task7_discover_only_ldd(tmp_path, first_output)
    manifest_two = _task7_discover_only_ldd(tmp_path, second_output)

    assert manifest_one.resources == manifest_two.resources
    assert manifest_one.manifest_sha256 == manifest_two.manifest_sha256
    assert sum(
        row["purpose"] == "dynamic_loader"
        for row in manifest_one.resources
    ) == 1


def test_runtime_ldd_groups_musl_libc_alias_with_direct_loader(tmp_path):
    loader = tmp_path / "ld-musl-s390x.so.1"
    loader.write_bytes(b"musl-loader")

    manifest = _task7_discover_only_ldd(
        tmp_path,
        f"libc.musl-s390x.so.1 => {loader} (0x1)\n"
        f"{loader} (0x2)\n",
    )

    ldd_rows = tuple(
        row
        for row in manifest.resources
        if row["purpose"] in {"dynamic_library", "dynamic_loader"}
    )
    assert len(ldd_rows) == 1
    assert ldd_rows[0]["purpose"] == "dynamic_loader"


def _task7_discover_two_ldd_symlink_aliases(tmp_path, *, reversed_rows=False):
    real_library = tmp_path / "libshared-real.so"
    first_alias = tmp_path / "libshared-first.so"
    second_alias = tmp_path / "libshared-second.so"
    loader = tmp_path / "ld-linux-alias-test.so.2"
    real_library.write_bytes(b"shared-library")
    first_alias.symlink_to(real_library.name)
    second_alias.symlink_to(real_library.name)
    loader.write_bytes(b"loader")
    library_rows = (
        f"libshared-first.so => {first_alias} (0x1)",
        f"libshared-second.so => {second_alias} (0x2)",
    )
    if reversed_rows:
        library_rows = tuple(reversed(library_rows))
    output = "\n".join((*library_rows, f"{loader} (0x3)")) + "\n"
    manifest = _task7_discover_only_ldd(tmp_path, output)
    return manifest, real_library, first_alias, second_alias


@pytest.mark.parametrize("changed_alias_index", (0, 1))
def test_runtime_ldd_group_unions_and_revalidates_all_symlink_aliases(
    tmp_path, monkeypatch, changed_alias_index
):
    from validation import literature_evidence_isolation as isolation

    manifest, real_library, first_alias, second_alias = (
        _task7_discover_two_ldd_symlink_aliases(tmp_path)
    )
    reordered_dir = tmp_path / "reordered"
    reordered_dir.mkdir()
    reordered, _real, _first, _second = (
        _task7_discover_two_ldd_symlink_aliases(
            reordered_dir, reversed_rows=True
        )
    )
    grouped = next(
        row
        for row in manifest.resources
        if row["purpose"] == "dynamic_library"
    )
    reordered_grouped = next(
        row
        for row in reordered.resources
        if row["purpose"] == "dynamic_library"
    )
    assert tuple(
        Path(identity["path"]).name
        for identity in grouped["link_identity"]
    ) == ("libshared-first.so", "libshared-second.so")
    assert tuple(
        Path(identity["path"]).name
        for identity in reordered_grouped["link_identity"]
    ) == ("libshared-first.so", "libshared-second.so")

    same_directory_reordered = _task7_discover_only_ldd(
        tmp_path,
        f"libshared-second.so => {second_alias} (0x2)\n"
        f"libshared-first.so => {first_alias} (0x1)\n"
        f"{tmp_path / 'ld-linux-alias-test.so.2'} (0x3)\n",
    )
    assert manifest.resources == same_directory_reordered.resources
    assert manifest.manifest_sha256 == same_directory_reordered.manifest_sha256

    changed_alias = (first_alias, second_alias)[changed_alias_index]
    changed_alias.unlink()
    changed_alias.symlink_to(tmp_path / "changed-target.so")
    monkeypatch.setattr(
        isolation, "discover_runtime_resources", lambda requirements: manifest
    )
    with pytest.raises(AdapterContractError, match="link|identity"):
        isolation.build_runtime_snapshot(
            RuntimeRequirements("python3", (), (), ()),
            run_directory=tmp_path / f"run-{changed_alias_index}",
            event_recorder=lambda event_name, details: None,
        )
    assert real_library.read_bytes() == b"shared-library"


def test_runtime_ldd_rejects_two_distinct_loader_identities(tmp_path):
    first = tmp_path / "ld-linux-one.so.2"
    second = tmp_path / "ld-linux-two.so.2"
    first.write_bytes(b"first-loader")
    second.write_bytes(b"second-loader")

    with pytest.raises(AdapterContractError, match="loader"):
        _task7_discover_only_ldd(
            tmp_path,
            f"{first} (0x1)\n{second} (0x2)\n",
        )


def test_runtime_snapshot_freezes_bytes_and_revalidates_retained_dirfd(
    tmp_path, monkeypatch
):
    from validation import literature_evidence_isolation as isolation

    source = tmp_path / "installed-resource.bin"
    source.write_bytes(b"frozen-original-bytes")
    source.chmod(0o644)
    manifest = _task7_manifest(
        _task7_resource_row(
            source, "/runtime/backend/resource.bin",
            "declared_backend_resource",
        )
    )
    monkeypatch.setattr(
        isolation, "discover_runtime_resources", lambda requirements: manifest
    )
    events = []

    def record(event_name, details):
        events.append((event_name, dict(details)))

    run_directory = tmp_path / "exclusive-run"
    snapshot = isolation.build_runtime_snapshot(
        RuntimeRequirements("python3", (), (), ("resource",)),
        run_directory=run_directory,
        event_recorder=record,
    )
    snapshot_root = Path(snapshot.snapshot_root)
    copied_names = os.listdir(snapshot_root)
    assert len(copied_names) == 1
    copied = snapshot_root / copied_names[0]
    assert copied.read_bytes() == b"frozen-original-bytes"
    source.write_bytes(b"changed-original-data")

    retained_root = tmp_path / "retained-snapshot-moved"
    run_directory.chmod(0o700)
    snapshot_root.chmod(0o700)
    snapshot_root.rename(retained_root)
    retained_root.chmod(0o500)
    snapshot_root.mkdir(mode=0o700)
    (snapshot_root / copied.name).write_bytes(b"path-replacement")
    isolation.revalidate_runtime_snapshot(snapshot)

    with pytest.raises(AdapterContractError, match="consumed|retained"):
        isolation.revalidate_runtime_snapshot(snapshot)

    assert (retained_root / copied.name).read_bytes() == b"frozen-original-bytes"
    assert [name for name, _ in events] == [
        "runtime_resources_discovered",
        "runtime_source_validated",
        "runtime_resource_copied",
        "runtime_resource_byte_compared",
        "runtime_manifest_hashed",
        "runtime_snapshot_frozen",
    ]


def test_runtime_snapshot_final_event_failure_has_one_retained_fd_owner(
    tmp_path, monkeypatch
):
    import gc

    from validation import literature_evidence_isolation as isolation

    source = tmp_path / "installed-resource.bin"
    source.write_bytes(b"owned-once")
    source.chmod(0o644)
    manifest = _task7_manifest(
        _task7_resource_row(
            source,
            "/runtime/backend/resource.bin",
            "declared_backend_resource",
        )
    )
    monkeypatch.setattr(
        isolation, "discover_runtime_resources", lambda requirements: manifest
    )
    original_close = isolation.os.close
    original_runtime_close = isolation._runtime_close_fd
    original_state_type = isolation._RetainedRuntimeSnapshotState
    close_calls = []
    finalizer_calls = []
    retained = {}

    def spy_close(descriptor):
        close_calls.append(descriptor)
        return original_close(descriptor)

    def spy_runtime_close(descriptor):
        finalizer_calls.append(descriptor)
        return original_runtime_close(descriptor)

    def capture_state(**kwargs):
        retained["fd"] = kwargs["root_fd"]
        retained["owner"] = kwargs["owner"]
        return original_state_type(**kwargs)

    monkeypatch.setattr(isolation.os, "close", spy_close)
    monkeypatch.setattr(isolation, "_runtime_close_fd", spy_runtime_close)
    monkeypatch.setattr(
        isolation, "_RetainedRuntimeSnapshotState", capture_state
    )

    def fail_final_event(event_name, details):
        if event_name == "runtime_snapshot_frozen":
            raise RuntimeError("final recorder failure")

    with pytest.raises(RuntimeError, match="final recorder failure"):
        isolation.build_runtime_snapshot(
            RuntimeRequirements("python3", (), (), (str(source),)),
            run_directory=tmp_path / "exclusive-run",
            event_recorder=fail_final_event,
        )
    assert len(finalizer_calls) == 1
    retained_fd = retained["fd"]
    assert finalizer_calls[0] == retained_fd
    assert close_calls.count(retained_fd) == 1
    with pytest.raises(OSError):
        os.fstat(retained_fd)

    foreign_fd = os.open(source, os.O_RDONLY)
    if foreign_fd != retained_fd:
        os.dup2(foreign_fd, retained_fd)
        os.close(foreign_fd)
    retained.clear()
    gc.collect()
    assert len(finalizer_calls) == 1
    assert os.fstat(retained_fd).st_ino == source.stat().st_ino
    os.close(retained_fd)


def test_runtime_snapshot_copy_event_precedes_byte_comparison(
    tmp_path, monkeypatch
):
    from validation import literature_evidence_isolation as isolation

    source = tmp_path / "installed-resource.bin"
    source.write_bytes(b"boundary-original")
    source.chmod(0o644)
    manifest = _task7_manifest(
        _task7_resource_row(
            source,
            "/runtime/backend/resource.bin",
            "declared_backend_resource",
        )
    )
    monkeypatch.setattr(
        isolation, "discover_runtime_resources", lambda requirements: manifest
    )
    snapshot_root = tmp_path / "exclusive-run" / "runtime-snapshot"

    def mutate_at_copy_boundary(event_name, details):
        if event_name == "runtime_resource_copied":
            copied = next(snapshot_root.iterdir())
            copied.chmod(0o600)
            copied.write_bytes(b"boundary-tampered")
            copied.chmod(0o444)

    with pytest.raises(AdapterContractError, match="comparison|identity|hash"):
        isolation.build_runtime_snapshot(
            RuntimeRequirements("python3", (), (), (str(source),)),
            run_directory=tmp_path / "exclusive-run",
            event_recorder=mutate_at_copy_boundary,
        )


@pytest.mark.parametrize(
    "mutation_event",
    (
        "runtime_resource_byte_compared",
        "runtime_manifest_hashed",
        "runtime_snapshot_frozen",
    ),
)
def test_runtime_snapshot_final_audit_rejects_nonraising_event_mutation(
    tmp_path, monkeypatch, mutation_event
):
    from validation import literature_evidence_isolation as isolation

    source = tmp_path / "installed-resource.bin"
    source.write_bytes(b"final-audit")
    source.chmod(0o644)
    manifest = _task7_manifest(
        _task7_resource_row(
            source,
            "/runtime/backend/resource.bin",
            "declared_backend_resource",
        )
    )
    monkeypatch.setattr(
        isolation, "discover_runtime_resources", lambda requirements: manifest
    )
    run_path = tmp_path / "exclusive-run"
    snapshot_root = run_path / "runtime-snapshot"
    original_create = isolation._runtime_create_private_directory
    original_close = isolation.os.close
    created = []
    root_fd = []
    root_close_calls = []

    def capture_created(parent_fd, basename):
        descriptor = original_create(parent_fd, basename)
        created.append(descriptor)
        if basename == "runtime-snapshot":
            root_fd.append(descriptor)
        return descriptor

    def capture_root_close(descriptor):
        if root_fd and descriptor == root_fd[0]:
            root_close_calls.append(descriptor)
        return original_close(descriptor)

    monkeypatch.setattr(
        isolation, "_runtime_create_private_directory", capture_created
    )
    monkeypatch.setattr(isolation.os, "close", capture_root_close)

    def mutate_without_raising(event_name, details):
        if event_name != mutation_event:
            return
        copied = next(snapshot_root.iterdir())
        if event_name == "runtime_resource_byte_compared":
            (snapshot_root / "undeclared").write_bytes(b"extra")
        elif event_name == "runtime_manifest_hashed":
            os.link(copied, tmp_path / "external-hardlink")
        else:
            snapshot_root.chmod(0o700)

    before_fds = len(os.listdir("/proc/self/fd"))
    with pytest.raises(AdapterContractError, match="snapshot|identity|basename"):
        isolation.build_runtime_snapshot(
            RuntimeRequirements("python3", (), (), (str(source),)),
            run_directory=run_path,
            event_recorder=mutate_without_raising,
        )

    assert len(created) == 2
    assert len(root_fd) == 1
    assert root_close_calls == [root_fd[0]]
    with pytest.raises(OSError):
        os.fstat(root_fd[0])
    assert len(os.listdir("/proc/self/fd")) == before_fds


@pytest.mark.parametrize("audit_path", ("builder", "revalidate"))
@pytest.mark.parametrize(
    "late_mutation",
    (
        "file_chmod_after_hash",
        "file_hardlink_after_hash",
        "file_mutate_after_hash",
        "entry_after_initial_list",
        "root_chmod_after_initial_list",
    ),
)
def test_runtime_snapshot_audit_brackets_late_file_and_root_changes(
    tmp_path, monkeypatch, audit_path, late_mutation
):
    from validation import literature_evidence_isolation as isolation

    source = tmp_path / "installed-resource.bin"
    source.write_bytes(b"bracketed-audit")
    source.chmod(0o644)
    manifest = _task7_manifest(
        _task7_resource_row(
            source,
            "/runtime/backend/resource.bin",
            "declared_backend_resource",
        )
    )
    monkeypatch.setattr(
        isolation, "discover_runtime_resources", lambda requirements: manifest
    )
    run_path = tmp_path / "exclusive-run"
    original_create = isolation._runtime_create_private_directory
    retained_fd = []

    def capture_root_fd(parent_fd, basename):
        descriptor = original_create(parent_fd, basename)
        if basename == "runtime-snapshot":
            retained_fd.append(descriptor)
        return descriptor

    monkeypatch.setattr(
        isolation, "_runtime_create_private_directory", capture_root_fd
    )
    snapshot = None
    if audit_path == "revalidate":
        snapshot = isolation.build_runtime_snapshot(
            RuntimeRequirements("python3", (), (), (str(source),)),
            run_directory=run_path,
            event_recorder=lambda event_name, details: None,
        )
        assert len(retained_fd) == 1
    original_runtime_close = isolation._runtime_close_fd
    root_close_calls = []

    def capture_root_close(descriptor):
        if retained_fd and descriptor == retained_fd[0]:
            root_close_calls.append(descriptor)
        return original_runtime_close(descriptor)

    monkeypatch.setattr(isolation, "_runtime_close_fd", capture_root_close)
    mutated = False
    if late_mutation.endswith("after_hash"):
        original_hash = isolation._runtime_hash_descriptor

        def hash_then_mutate(descriptor):
            nonlocal mutated
            result = original_hash(descriptor)
            if not mutated:
                mutated = True
                copied = next((run_path / "runtime-snapshot").iterdir())
                if late_mutation == "file_chmod_after_hash":
                    os.fchmod(descriptor, 0o644)
                elif late_mutation == "file_hardlink_after_hash":
                    os.link(copied, tmp_path / "late-hardlink")
                else:
                    copied.chmod(0o600)
                    copied.write_bytes(b"mutated-content")
                    copied.chmod(0o444)
            return result

        monkeypatch.setattr(
            isolation, "_runtime_hash_descriptor", hash_then_mutate
        )
    else:
        original_listdir = isolation.os.listdir

        def list_then_add_entry(descriptor):
            nonlocal mutated
            result = original_listdir(descriptor)
            if (
                not mutated
                and retained_fd
                and descriptor == retained_fd[0]
            ):
                mutated = True
                os.fchmod(descriptor, 0o700)
                if late_mutation == "entry_after_initial_list":
                    extra_fd = os.open(
                        "late-entry",
                        os.O_WRONLY
                        | os.O_CREAT
                        | os.O_EXCL
                        | os.O_NOFOLLOW
                        | os.O_CLOEXEC,
                        0o444,
                        dir_fd=descriptor,
                    )
                    os.close(extra_fd)
                    os.fchmod(descriptor, 0o500)
            return result

        monkeypatch.setattr(isolation.os, "listdir", list_then_add_entry)

    caught = None
    if audit_path == "builder":
        try:
            snapshot = isolation.build_runtime_snapshot(
                RuntimeRequirements("python3", (), (), (str(source),)),
                run_directory=run_path,
                event_recorder=lambda event_name, details: None,
            )
        except AdapterContractError as error:
            caught = error
        if snapshot is not None:
            try:
                isolation.revalidate_runtime_snapshot(snapshot)
            except AdapterContractError:
                pass
    else:
        try:
            isolation.revalidate_runtime_snapshot(snapshot)
        except AdapterContractError as error:
            caught = error

    assert mutated is True
    assert type(caught) is AdapterContractError
    assert len(retained_fd) == 1
    root_fd = retained_fd[0]
    assert root_close_calls == [root_fd]
    with pytest.raises(OSError):
        os.fstat(root_fd)


@pytest.mark.parametrize(
    "stop_event, expected_run_mode, expected_root_mode, expected_file_count",
    (
        ("runtime_resources_discovered", None, None, 0),
        ("runtime_source_validated", 0o700, 0o700, 0),
        ("runtime_resource_copied", 0o700, 0o700, 1),
        ("runtime_resource_byte_compared", 0o700, 0o700, 1),
        ("runtime_manifest_hashed", 0o700, 0o700, 1),
        ("runtime_snapshot_frozen", 0o500, 0o500, 1),
    ),
)
def test_runtime_snapshot_event_boundaries_match_filesystem_stage(
    tmp_path,
    monkeypatch,
    stop_event,
    expected_run_mode,
    expected_root_mode,
    expected_file_count,
):
    from validation import literature_evidence_isolation as isolation

    source = tmp_path / "installed-resource.bin"
    source.write_bytes(b"boundary-stage")
    source.chmod(0o644)
    manifest = _task7_manifest(
        _task7_resource_row(
            source,
            "/runtime/backend/resource.bin",
            "declared_backend_resource",
        )
    )
    monkeypatch.setattr(
        isolation, "discover_runtime_resources", lambda requirements: manifest
    )
    run_path = tmp_path / "exclusive-run"
    snapshot_root = run_path / "runtime-snapshot"
    observed = {}

    def stop_at_boundary(event_name, details):
        if event_name != stop_event:
            return
        observed["run_mode"] = (
            stat.S_IMODE(run_path.stat().st_mode) if run_path.exists() else None
        )
        observed["root_mode"] = (
            stat.S_IMODE(snapshot_root.stat().st_mode)
            if snapshot_root.exists()
            else None
        )
        observed["file_count"] = (
            len(tuple(snapshot_root.iterdir()))
            if snapshot_root.exists()
            else 0
        )
        raise RuntimeError(f"stop at {event_name}")

    before_fds = len(os.listdir("/proc/self/fd"))
    with pytest.raises(RuntimeError, match=f"stop at {stop_event}"):
        isolation.build_runtime_snapshot(
            RuntimeRequirements("python3", (), (), (str(source),)),
            run_directory=run_path,
            event_recorder=stop_at_boundary,
        )

    assert observed == {
        "run_mode": expected_run_mode,
        "root_mode": expected_root_mode,
        "file_count": expected_file_count,
    }
    assert len(os.listdir("/proc/self/fd")) == before_fds


@pytest.mark.parametrize(
    "mutation",
    ("replace", "chmod", "hardlink", "mutate", "undeclared_entry"),
)
def test_runtime_snapshot_revalidation_rejects_post_hash_changes(
    tmp_path, monkeypatch, mutation
):
    from validation import literature_evidence_isolation as isolation

    _source, snapshot, copied = _task7_build_snapshot(
        tmp_path, monkeypatch, source_bytes=b"immutable-snapshot"
    )
    root = copied.parent
    if mutation == "replace":
        root.chmod(0o700)
        copied.rename(tmp_path / "old-copy")
        copied.write_bytes(b"replacement-bytes")
        copied.chmod(0o444)
        root.chmod(0o500)
    elif mutation == "chmod":
        copied.chmod(0o644)
    elif mutation == "hardlink":
        os.link(copied, tmp_path / "linked-copy")
    elif mutation == "mutate":
        copied.chmod(0o600)
        copied.write_bytes(b"corrupted-snapshot")
        copied.chmod(0o444)
    else:
        root.chmod(0o700)
        (root / "undeclared").write_bytes(b"extra")
        root.chmod(0o500)

    with pytest.raises(AdapterContractError):
        isolation.revalidate_runtime_snapshot(snapshot)
    with pytest.raises(AdapterContractError, match="consumed|retained"):
        isolation.revalidate_runtime_snapshot(snapshot)


def test_runtime_snapshot_source_post_compare_fstat_detects_mutation(
    tmp_path, monkeypatch
):
    from validation import literature_evidence_isolation as isolation

    source = tmp_path / "changing-source.bin"
    source.write_bytes(b"source-window")
    source.chmod(0o644)
    manifest = _task7_manifest(
        _task7_resource_row(
            source, "/runtime/backend/changing.bin",
            "declared_backend_resource",
        )
    )
    monkeypatch.setattr(
        isolation, "discover_runtime_resources", lambda requirements: manifest
    )
    original_read = isolation.os.read
    source_inode = source.stat().st_ino
    source_eof_count = 0

    def mutate_after_compare(fd, size):
        nonlocal source_eof_count
        chunk = original_read(fd, size)
        if not chunk and os.fstat(fd).st_ino == source_inode:
            source_eof_count += 1
            if source_eof_count == 3:
                source.chmod(0o600)
        return chunk

    monkeypatch.setattr(isolation.os, "read", mutate_after_compare)
    with pytest.raises(AdapterContractError, match="source.*changed"):
        isolation.build_runtime_snapshot(
            RuntimeRequirements("python3", (), (), (str(source),)),
            run_directory=tmp_path / "exclusive-run",
            event_recorder=lambda event_name, details: None,
        )


def test_runtime_snapshot_modes_ignore_restrictive_umask(tmp_path, monkeypatch):
    source, snapshot, copied = _task7_build_snapshot(tmp_path, monkeypatch)
    assert stat.S_IMODE((tmp_path / "exclusive-run").stat().st_mode) == 0o500
    assert stat.S_IMODE(Path(snapshot.snapshot_root).stat().st_mode) == 0o500
    assert stat.S_IMODE(copied.stat().st_mode) == 0o444
    Path(snapshot.snapshot_root).chmod(0o700)
    (tmp_path / "exclusive-run").chmod(0o700)


def test_runtime_snapshot_plain_constructor_and_copied_state_fail_closed(
    tmp_path, monkeypatch
):
    from validation import literature_evidence_isolation as isolation

    _source, snapshot, _copied = _task7_build_snapshot(tmp_path, monkeypatch)
    forged = isolation.RuntimeSnapshot(
        snapshot.schema_version,
        snapshot.manifest,
        snapshot.snapshot_root,
        snapshot.directory_identities,
        snapshot.snapshot_sha256,
    )
    object.__setattr__(
        forged,
        "_retained_runtime_state",
        object.__getattribute__(snapshot, "__dict__")[
            "_retained_runtime_state"
        ],
    )
    with pytest.raises(AdapterContractError, match="authentic|retained"):
        isolation.revalidate_runtime_snapshot(forged)
    state = object.__getattribute__(snapshot, "__dict__")[
        "_retained_runtime_state"
    ]
    duplicated_fd = os.dup(object.__getattribute__(state, "root_fd"))
    try:
        with pytest.raises(AdapterContractError, match="authorized"):
            isolation._RetainedRuntimeSnapshotState(
                owner=forged,
                root_fd=duplicated_fd,
                root_identity=object.__getattribute__(state, "root_identity"),
                files=object.__getattribute__(state, "files"),
                snapshot_material=object.__getattribute__(
                    state, "snapshot_material"
                ),
            )
    finally:
        os.close(duplicated_fd)
    snapshot.revalidate()


def test_runtime_resource_distribution_preserves_relative_layout(tmp_path):
    from validation import literature_evidence_isolation as isolation

    runtime = tmp_path / "outside" / "runtime"
    (runtime / "pkg" / "a").mkdir(parents=True)
    (runtime / "pkg" / "b").mkdir()
    interpreter = runtime / "python"
    loader = runtime / "ld-linux.so"
    first = runtime / "pkg" / "a" / "data.bin"
    second = runtime / "pkg" / "b" / "data.bin"
    for path in (interpreter, loader, first, second):
        path.write_bytes(path.name.encode())
        path.chmod(0o755 if path in (interpreter, loader) else 0o644)

    def file_probe(operation, value):
        if operation == "resolve_interpreter":
            return interpreter
        if operation == "imported_stdlib_files":
            return ()
        if operation == "distribution":
            return {
                "name": "demo",
                "version": "1",
                "files": (
                    ("pkg/a/data.bin", first),
                    ("pkg/b/data.bin", second),
                ),
            }
        raise AssertionError((operation, value))

    manifest = isolation.discover_runtime_resources(
        RuntimeRequirements("python3", ("demo",), (), ("single_cpu_core",)),
        command_probe=lambda argv: f"{loader} (0x1)\n",
        file_probe=file_probe,
    )
    destinations = {row["logical_destination"] for row in manifest.resources}
    assert "/runtime/distributions/demo/pkg/a/data.bin" in destinations
    assert "/runtime/distributions/demo/pkg/b/data.bin" in destinations
    capability = next(
        row for row in manifest.resources if row["file_type"] == "capability"
    )
    assert capability["resolved_path"] is None
    assert capability["size"] == capability["mode"] == 0


@pytest.mark.parametrize(
    "declared_kind",
    ("metadata_none", "missing", "directory", "dangling_symlink"),
)
def test_default_runtime_distribution_probe_rejects_underclosed_metadata(
    tmp_path, monkeypatch, declared_kind
):
    from validation import literature_evidence_isolation as isolation

    declared = tmp_path / "package-entry"
    if declared_kind == "directory":
        declared.mkdir()
    elif declared_kind == "dangling_symlink":
        declared.symlink_to(tmp_path / "absent-target")

    class FakeDistribution:
        metadata = {"Name": "demo"}
        version = "1.0"
        files = None if declared_kind == "metadata_none" else ("pkg/data.bin",)

        @staticmethod
        def locate_file(item):
            assert item == "pkg/data.bin"
            return declared

    monkeypatch.setattr(
        isolation._importlib_metadata,
        "distribution",
        lambda name: FakeDistribution(),
    )

    with pytest.raises(AdapterContractError, match="distribution|file|metadata"):
        isolation._default_runtime_file_probe("distribution", "demo")


def test_default_runtime_distribution_probe_accepts_explicit_empty_files(
    monkeypatch,
):
    from validation import literature_evidence_isolation as isolation

    class FakeDistribution:
        metadata = {"Name": "empty-demo"}
        version = "1.0"
        files = ()

        @staticmethod
        def locate_file(item):
            raise AssertionError("empty metadata must not locate a file")

    monkeypatch.setattr(
        isolation._importlib_metadata,
        "distribution",
        lambda name: FakeDistribution(),
    )

    assert isolation._default_runtime_file_probe(
        "distribution", "empty-demo"
    ) == {"name": "empty-demo", "version": "1.0", "files": ()}


def test_runtime_resource_stdlib_preserves_relative_layout_for_same_basename(
    tmp_path,
):
    from validation import literature_evidence_isolation as isolation

    runtime = tmp_path / "runtime"
    (runtime / "encodings").mkdir(parents=True)
    (runtime / "json").mkdir()
    interpreter = runtime / "python"
    encoding_init = runtime / "encodings" / "__init__.py"
    json_init = runtime / "json" / "__init__.py"
    for path in (interpreter, encoding_init, json_init):
        path.write_bytes(str(path).encode())

    def file_probe(operation, value):
        if operation == "resolve_interpreter":
            return interpreter
        if operation == "imported_stdlib_files":
            return (
                ("encodings/__init__.py", encoding_init),
                ("json/__init__.py", json_init),
            )
        raise AssertionError((operation, value))

    manifest = isolation.discover_runtime_resources(
        RuntimeRequirements("python3", (), (), ()),
        command_probe=lambda argv: _task7_ldd_output(tmp_path),
        file_probe=file_probe,
    )
    stdlib_destinations = {
        row["logical_destination"]
        for row in manifest.resources
        if row["purpose"] == "imported_standard_library"
    }
    assert stdlib_destinations == {
        "/runtime/stdlib/encodings/__init__.py",
        "/runtime/stdlib/json/__init__.py",
    }


def test_default_runtime_stdlib_probe_disables_child_bytecode(monkeypatch):
    from validation import literature_evidence_isolation as isolation

    observed = {}

    class Result:
        returncode = 0
        stdout = "[]\n"
        stderr = ""

    def run(argv, **kwargs):
        observed["argv"] = argv
        observed["kwargs"] = kwargs
        return Result()

    monkeypatch.setattr(isolation.subprocess, "run", run)

    assert isolation._default_runtime_file_probe(
        "imported_stdlib_files", ()
    ) == ()
    assert observed["argv"][:5] == (
        isolation.sys.executable, "-I", "-S", "-B", "-c"
    )
    assert "sys.flags.dont_write_bytecode" in observed["argv"][5]
    assert observed["kwargs"] == {
        "check": False,
        "shell": False,
        "stdout": isolation.subprocess.PIPE,
        "stderr": isolation.subprocess.PIPE,
        "text": True,
    }


@pytest.mark.parametrize(
    "bad_relative",
    ("../escape.py", "/absolute.py", "pkg/../escape.py", "pkg//data.py"),
)
def test_runtime_resource_distribution_rejects_unsafe_relative_path(
    tmp_path, bad_relative
):
    from validation import literature_evidence_isolation as isolation

    interpreter = tmp_path / "python"
    package_file = tmp_path / "data.py"
    interpreter.write_bytes(b"python")
    package_file.write_bytes(b"data")

    def probe(operation, value):
        if operation == "resolve_interpreter":
            return interpreter
        if operation == "imported_stdlib_files":
            return ()
        if operation == "distribution":
            return {
                "name": "demo", "version": "1",
                "files": ((bad_relative, package_file),),
            }
        raise AssertionError

    with pytest.raises(AdapterContractError):
        isolation.discover_runtime_resources(
            RuntimeRequirements("python3", ("demo",), (), ()),
            command_probe=lambda argv: _task7_ldd_output(tmp_path),
            file_probe=probe,
        )


def test_runtime_resource_symlink_chain_records_nested_target_links(tmp_path):
    from validation import literature_evidence_isolation as isolation

    target_dir = tmp_path / "target"
    target_dir.mkdir()
    real = target_dir / "python-real"
    real.write_bytes(b"python")
    nested = tmp_path / "nested"
    nested.symlink_to(target_dir, target_is_directory=True)
    outer = tmp_path / "python3"
    outer.symlink_to(nested / real.name)

    manifest = isolation.discover_runtime_resources(
        RuntimeRequirements("python3", (), (), ()),
        command_probe=lambda argv: _task7_ldd_output(tmp_path),
        file_probe=lambda operation, value: (
            outer if operation == "resolve_interpreter" else ()
        ),
    )
    interpreter = next(
        row for row in manifest.resources if row["purpose"] == "interpreter"
    )
    assert {item["path"] for item in interpreter["link_identity"]} == {
        str(outer), str(nested)
    }


def test_runtime_snapshot_rejects_changed_declared_symlink_identity(
    tmp_path, monkeypatch
):
    from validation import literature_evidence_isolation as isolation

    first = tmp_path / "first-python"
    second = tmp_path / "second-python"
    link = tmp_path / "python3"
    first.write_bytes(b"first-python")
    second.write_bytes(b"second-python")
    link.symlink_to(first.name)
    manifest = isolation.discover_runtime_resources(
        RuntimeRequirements("python3", (), (), ()),
        command_probe=lambda argv: _task7_ldd_output(tmp_path),
        file_probe=lambda operation, value: (
            link if operation == "resolve_interpreter" else ()
        ),
    )
    link.unlink()
    link.symlink_to(second.name)
    monkeypatch.setattr(
        isolation, "discover_runtime_resources", lambda requirements: manifest
    )

    with pytest.raises(AdapterContractError, match="link|identity"):
        isolation.build_runtime_snapshot(
            RuntimeRequirements("python3", (), (), ()),
            run_directory=tmp_path / "run",
            event_recorder=lambda event_name, details: None,
        )


@pytest.mark.parametrize(
    "boundary",
    ("project", "worktree_parent", "source_cache", "reports", "user_config"),
)
def test_runtime_resource_discovery_rejects_each_forbidden_root(
    tmp_path, monkeypatch, boundary
):
    from validation import literature_evidence_isolation as isolation

    root = tmp_path / boundary
    root.mkdir()
    resource = root / "python"
    resource.write_bytes(b"forbidden")
    monkeypatch.setattr(isolation, "_runtime_forbidden_roots", lambda: (root,))

    with pytest.raises(AdapterContractError, match="forbidden"):
        isolation.discover_runtime_resources(
            RuntimeRequirements("python3", (), (), ()),
            command_probe=lambda argv: pytest.fail("ldd must not execute"),
            file_probe=lambda operation, value: (
                resource if operation == "resolve_interpreter" else ()
            ),
        )


def test_runtime_resource_discovery_rejects_undeclared_distribution(tmp_path):
    from validation import literature_evidence_isolation as isolation

    interpreter = tmp_path / "python"
    interpreter.write_bytes(b"python")

    def probe(operation, value):
        if operation == "resolve_interpreter":
            return interpreter
        if operation == "imported_stdlib_files":
            return ()
        if operation == "distribution":
            return {"name": "other", "version": "1", "files": ()}
        raise AssertionError

    with pytest.raises(AdapterContractError, match="undeclared"):
        isolation.discover_runtime_resources(
            RuntimeRequirements("python3", ("declared",), (), ()),
            command_probe=lambda argv: _task7_ldd_output(tmp_path),
            file_probe=probe,
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "unknown_key", "duplicate_destination", "parent_file",
        "same_source", "forged_capability",
    ),
)
def test_runtime_snapshot_rejects_malformed_or_ambiguous_manifest(
    tmp_path, monkeypatch, mutation
):
    from validation import literature_evidence_isolation as isolation

    first = tmp_path / "first.bin"
    second = tmp_path / "second.bin"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    row_one = _task7_resource_row(
        first, "/runtime/pkg", "declared_backend_resource"
    )
    row_two = _task7_resource_row(
        second, "/runtime/other", "declared_backend_resource"
    )
    if mutation == "unknown_key":
        row_one["caller_key"] = True
        rows = (row_one,)
    elif mutation == "duplicate_destination":
        row_two["logical_destination"] = row_one["logical_destination"]
        rows = (row_one, row_two)
    elif mutation == "parent_file":
        row_two["logical_destination"] = "/runtime/pkg/child.bin"
        rows = (row_one, row_two)
    elif mutation == "same_source":
        row_two["resolved_path"] = row_one["resolved_path"]
        row_two["size"] = row_one["size"]
        row_two["mode"] = row_one["mode"]
        row_two["sha256"] = row_one["sha256"]
        rows = (row_one, row_two)
    else:
        rows = ({
            "logical_destination": "/runtime/capabilities/network",
            "resolved_path": None,
            "link_identity": (),
            "file_type": "capability",
            "size": 0,
            "mode": 0,
            "sha256": _sha256_text("forged-network-capability"),
            "distribution": None,
            "version": None,
            "purpose": "declared_backend_capability",
        },)
    manifest = _task7_manifest(*rows)
    monkeypatch.setattr(
        isolation, "discover_runtime_resources", lambda requirements: manifest
    )

    with pytest.raises(AdapterContractError):
        isolation.build_runtime_snapshot(
            RuntimeRequirements("python3", (), (), (str(first),)),
            run_directory=tmp_path / "run",
            event_recorder=lambda event_name, details: None,
        )


def test_runtime_snapshot_rejects_source_path_replacement_during_copy(
    tmp_path, monkeypatch
):
    from validation import literature_evidence_isolation as isolation

    source = tmp_path / "source.bin"
    replacement = tmp_path / "replacement.bin"
    source.write_bytes(b"original-source")
    replacement.write_bytes(b"replacement-data")
    manifest = _task7_manifest(
        _task7_resource_row(
            source, "/runtime/source.bin", "declared_backend_resource"
        )
    )
    monkeypatch.setattr(
        isolation, "discover_runtime_resources", lambda requirements: manifest
    )
    original_read = isolation.os.read
    source_inode = source.stat().st_ino
    source_eof_count = 0

    def replace_after_copy(fd, size):
        nonlocal source_eof_count
        chunk = original_read(fd, size)
        if not chunk and os.fstat(fd).st_ino == source_inode:
            source_eof_count += 1
            if source_eof_count == 2:
                os.replace(replacement, source)
        return chunk

    monkeypatch.setattr(isolation.os, "read", replace_after_copy)
    with pytest.raises(AdapterContractError, match="source.*(path|changed)"):
        isolation.build_runtime_snapshot(
            RuntimeRequirements("python3", (), (), (str(source),)),
            run_directory=tmp_path / "run",
            event_recorder=lambda event_name, details: None,
        )


def test_runtime_snapshot_short_read_fails_and_closes_temporary_fds(
    tmp_path, monkeypatch
):
    from validation import literature_evidence_isolation as isolation

    source = tmp_path / "source.bin"
    source.write_bytes(b"source-for-short-read")
    manifest = _task7_manifest(
        _task7_resource_row(
            source, "/runtime/source.bin", "declared_backend_resource"
        )
    )
    monkeypatch.setattr(
        isolation, "discover_runtime_resources", lambda requirements: manifest
    )
    original_read = isolation.os.read
    source_inode = source.stat().st_ino
    source_eof_count = 0

    def short_copy(fd, size):
        nonlocal source_eof_count
        if os.fstat(fd).st_ino == source_inode and source_eof_count == 1:
            source_eof_count += 1
            return b""
        chunk = original_read(fd, size)
        if not chunk and os.fstat(fd).st_ino == source_inode:
            source_eof_count += 1
        return chunk

    before_fds = len(os.listdir("/proc/self/fd"))
    monkeypatch.setattr(isolation.os, "read", short_copy)
    with pytest.raises(AdapterContractError, match="source changed|while copying"):
        isolation.build_runtime_snapshot(
            RuntimeRequirements("python3", (), (), (str(source),)),
            run_directory=tmp_path / "run",
            event_recorder=lambda event_name, details: None,
        )
    assert len(os.listdir("/proc/self/fd")) == before_fds


def test_runtime_snapshot_closed_and_reused_retained_fd_fails_closed(
    tmp_path, monkeypatch
):
    from validation import literature_evidence_isolation as isolation

    _source, snapshot, _copied = _task7_build_snapshot(tmp_path, monkeypatch)
    state = object.__getattribute__(snapshot, "__dict__")[
        "_retained_runtime_state"
    ]
    retained_fd = object.__getattribute__(state, "root_fd")
    os.close(retained_fd)
    foreign_fds = []
    while retained_fd not in foreign_fds:
        foreign_fds.append(
            os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        )
    foreign = retained_fd
    try:
        with pytest.raises(AdapterContractError, match="retained"):
            isolation.revalidate_runtime_snapshot(snapshot)
        os.fstat(foreign)
    finally:
        for descriptor in foreign_fds:
            os.close(descriptor)


@pytest.mark.parametrize(
    "public_tamper",
    ("manifest", "snapshot_sha256", "directory_identities"),
)
def test_runtime_snapshot_pre_fstat_commitment_failure_closes_owned_fd(
    tmp_path, monkeypatch, public_tamper
):
    from validation import literature_evidence_isolation as isolation

    _source, snapshot, _copied = _task7_build_snapshot(tmp_path, monkeypatch)
    state = object.__getattribute__(snapshot, "__dict__")[
        "_retained_runtime_state"
    ]
    retained_fd = object.__getattribute__(state, "root_fd")
    root_identity = os.fstat(retained_fd)
    assert root_identity.st_ino == snapshot.directory_identities[0]["inode"]
    if public_tamper == "manifest":
        object.__setattr__(snapshot.manifest, "manifest_sha256", "0" * 64)
    elif public_tamper == "snapshot_sha256":
        object.__setattr__(snapshot, "snapshot_sha256", "0" * 64)
    else:
        object.__setattr__(snapshot, "directory_identities", ())

    with pytest.raises(AdapterContractError):
        isolation.revalidate_runtime_snapshot(snapshot)
    with pytest.raises(OSError) as closed:
        os.fstat(retained_fd)
    assert closed.value.errno == 9
    Path(snapshot.snapshot_root).chmod(0o700)
    Path(snapshot.snapshot_root).parent.chmod(0o700)


def test_task7_runtime_public_signatures_are_stable_and_closed():
    from validation import literature_evidence_isolation as isolation

    assert str(inspect.signature(isolation.discover_runtime_resources)) == (
        "(requirements, *, command_probe=None, file_probe=None)"
    )
    assert str(inspect.signature(isolation.build_runtime_snapshot)) == (
        "(requirements, *, run_directory, event_recorder)"
    )
    assert str(inspect.signature(isolation.revalidate_runtime_snapshot)) == (
        "(snapshot)"
    )
    assert {field.name for field in dataclasses.fields(isolation.RuntimeSnapshot)} == {
        "schema_version", "manifest", "snapshot_root",
        "directory_identities", "snapshot_sha256",
    }


def test_task7_runtime_functions_have_exact_infrastructure_category(tmp_path):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(tmp_path)
    closure = isolation.build_infrastructure_closure(
        source_roots=(tmp_path,)
    )
    roots = {
        "validation.literature_evidence_isolation.discover_runtime_resources",
        "validation.literature_evidence_isolation.build_runtime_snapshot",
        "validation.literature_evidence_isolation.revalidate_runtime_snapshot",
    }
    assert roots <= {node["qualified_name"] for node in closure.nodes}
    assert {
        closure.purpose_bindings[root] for root in roots
    } == {"runtime_resource_integrity"}


def test_runtime_snapshot_creation_is_umask_independent(tmp_path, monkeypatch):
    previous_umask = os.umask(0o777)
    try:
        _source, snapshot, copied = _task7_build_snapshot(tmp_path, monkeypatch)
    finally:
        os.umask(previous_umask)

    assert stat.S_IMODE((tmp_path / "exclusive-run").stat().st_mode) == 0o500
    assert stat.S_IMODE(Path(snapshot.snapshot_root).stat().st_mode) == 0o500
    assert stat.S_IMODE(copied.stat().st_mode) == 0o444
    Path(snapshot.snapshot_root).chmod(0o700)
    (tmp_path / "exclusive-run").chmod(0o700)


def test_runtime_snapshot_rejects_symlink_component_in_run_parent(
    tmp_path, monkeypatch
):
    from validation import literature_evidence_isolation as isolation

    source = tmp_path / "source.bin"
    source.write_bytes(b"source")
    manifest = _task7_manifest(
        _task7_resource_row(
            source, "/runtime/source.bin", "declared_backend_resource"
        )
    )
    monkeypatch.setattr(
        isolation, "discover_runtime_resources", lambda requirements: manifest
    )
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    (real_parent / "child").mkdir()
    link_parent = tmp_path / "linked-parent"
    link_parent.symlink_to(real_parent, target_is_directory=True)

    with pytest.raises(AdapterContractError):
        isolation.build_runtime_snapshot(
            RuntimeRequirements("python3", (), (), (str(source),)),
            run_directory=link_parent / "child" / "run",
            event_recorder=lambda event_name, details: None,
        )
    assert not (real_parent / "child" / "run").exists()


_TASK8_PRE_FREEZE_EVENTS = (
    "definition_and_provenance_validated",
    "scientific_closures_hashed",
    "scientific_policies_hashed",
    "infrastructure_partition_hashed",
    "runtime_snapshot_hashed",
    "capsules_hashed",
    "capability_preflight_hashed",
)


def _task8_hash_material(definition):
    definition_sha256 = hashlib.sha256(
        canonical_json_bytes(
            adapters.adapter_definition_to_frozen_json(definition)
        )
    ).hexdigest()
    return {
        "adapter_closure_sha256": _sha256_text("task8-adapter-closure"),
        "oracle_closure_sha256": _sha256_text("task8-oracle-closure"),
        "adapter_definition_sha256": definition_sha256,
        "oracle_definition_sha256": _sha256_text("task8-oracle-definition"),
        "adapter_policy_sha256": _sha256_text("task8-adapter-policy"),
        "oracle_policy_sha256": _sha256_text("task8-oracle-policy"),
        "infrastructure_closure_sha256": _sha256_text(
            "task8-infrastructure-closure"
        ),
        "infrastructure_scan_sha256": _sha256_text(
            "task8-infrastructure-scan"
        ),
        "adapter_scan_sha256": _sha256_text("task8-adapter-scan"),
        "oracle_scan_sha256": _sha256_text("task8-oracle-scan"),
        "scanner_sha256": _sha256_text("task8-static-scanner"),
        "dependency_partition_sha256": _sha256_text(
            "task8-dependency-partition"
        ),
        "runtime_snapshot_sha256": _sha256_text("task8-runtime-snapshot"),
        "adapter_capsule_sha256": _sha256_text("task8-adapter-capsule"),
        "oracle_capsule_sha256": _sha256_text("task8-oracle-capsule"),
        "worker_capsule_sha256": _sha256_text("task8-worker-capsule"),
    }


def _task8_preflight(isolation, audit_run_id, command_hashes):
    payload = {
        "schema_version": "capability_preflight_report_v1",
        "audit_run_id": audit_run_id,
        "available": True,
        "checks": {"fresh_executed_probe": True},
        "command_identities": dict(command_hashes),
        "namespace_identifiers": {"user": "fresh-user-namespace"},
        "mount_facts": {"root": "fresh-read-only-root"},
        "probe_result_codes": {"fresh_probe": 0},
        "trace_sha256": _sha256_text("task8-preflight-trace-" + audit_run_id),
    }
    payload["report_sha256"] = hashlib.sha256(
        canonical_json_bytes(payload)
    ).hexdigest()
    return isolation.CapabilityPreflightReport(**payload)


class _Task8OrderingFixture:
    def __init__(self, isolation, definition, audit_run_id):
        self.isolation = isolation
        self.definition = definition
        self.audit_run_id = audit_run_id
        self.events = []
        self.hash_material = _task8_hash_material(definition)
        self.command_hashes = {
            "sha256sum": _sha256_text("task8-sha256sum-command"),
            "unshare": _sha256_text("task8-unshare-command"),
        }
        self.preflight = _task8_preflight(
            isolation, audit_run_id, self.command_hashes
        )

    def record(self, event_name, details):
        self.events.append(
            self.isolation.EventRecord(
                len(self.events), event_name, dict(details)
            )
        )

    def prerequisite_details(self, event_name):
        hashes = self.hash_material
        details_by_event = {
            "definition_and_provenance_validated": {
                "audit_run_id": self.audit_run_id,
                "adapter_definition_sha256": hashes[
                    "adapter_definition_sha256"
                ],
            },
            "scientific_closures_hashed": {
                "audit_run_id": self.audit_run_id,
                "adapter_closure_sha256": hashes[
                    "adapter_closure_sha256"
                ],
                "oracle_closure_sha256": hashes["oracle_closure_sha256"],
            },
            "scientific_policies_hashed": {
                "audit_run_id": self.audit_run_id,
                "adapter_definition_sha256": hashes[
                    "adapter_definition_sha256"
                ],
                "oracle_definition_sha256": hashes[
                    "oracle_definition_sha256"
                ],
                "adapter_policy_sha256": hashes["adapter_policy_sha256"],
                "oracle_policy_sha256": hashes["oracle_policy_sha256"],
            },
            "infrastructure_partition_hashed": {
                "audit_run_id": self.audit_run_id,
                "infrastructure_closure_sha256": hashes[
                    "infrastructure_closure_sha256"
                ],
                "infrastructure_scan_sha256": hashes[
                    "infrastructure_scan_sha256"
                ],
                "adapter_scan_sha256": hashes["adapter_scan_sha256"],
                "oracle_scan_sha256": hashes["oracle_scan_sha256"],
                "scanner_sha256": hashes["scanner_sha256"],
                "dependency_partition_sha256": hashes[
                    "dependency_partition_sha256"
                ],
            },
            "runtime_snapshot_hashed": {
                "audit_run_id": self.audit_run_id,
                "runtime_snapshot_sha256": hashes[
                    "runtime_snapshot_sha256"
                ],
            },
            "capsules_hashed": {
                "audit_run_id": self.audit_run_id,
                "adapter_capsule_sha256": hashes[
                    "adapter_capsule_sha256"
                ],
                "oracle_capsule_sha256": hashes["oracle_capsule_sha256"],
                "worker_capsule_sha256": hashes["worker_capsule_sha256"],
            },
            "capability_preflight_hashed": {
                "audit_run_id": self.audit_run_id,
                "capability_preflight": {
                    field.name: getattr(self.preflight, field.name)
                    for field in dataclasses.fields(type(self.preflight))
                },
                "capability_preflight_sha256": self.preflight.report_sha256,
                "infrastructure_command_hashes": dict(self.command_hashes),
            },
        }
        return details_by_event[event_name]

    def record_prerequisites(self):
        for event_name in _TASK8_PRE_FREEZE_EVENTS:
            self.record(event_name, self.prerequisite_details(event_name))

    def freeze(self, *, frozen_snapshot=None):
        return self.isolation.record_and_freeze_hashes(
            self.definition,
            audit_run_id=self.audit_run_id,
            ordered_events=tuple(self.events),
            hash_material=self.hash_material,
            capability_preflight=self.preflight,
            infrastructure_command_hashes=self.command_hashes,
            event_recorder=self.record,
            frozen_snapshot=frozen_snapshot,
        )


def test_event_order_requires_freeze_before_exact_32_byte_random_acquisition():
    from validation import literature_evidence_isolation as isolation

    fixture = _Task8OrderingFixture(
        isolation,
        adapters.ADAPTER_DEFINITIONS["xxx_bethe_energy"],
        "task8-ordering-run-a",
    )
    for event_name in _TASK8_PRE_FREEZE_EVENTS:
        fixture.record(event_name, fixture.prerequisite_details(event_name))
        with pytest.raises(AdapterContractError, match="frozen|ordering"):
            isolation.acquire_run_seed(
                None,
                ordered_events=tuple(fixture.events),
                random_bytes=lambda count: b"r" * count,
                event_recorder=fixture.record,
            )

    frozen = fixture.freeze()
    seed = isolation.acquire_run_seed(
        frozen,
        ordered_events=tuple(fixture.events),
        random_bytes=lambda count: b"s" * count,
        event_recorder=fixture.record,
    )

    assert seed == b"s" * 32
    assert tuple(event.event_name for event in fixture.events) == (
        *_TASK8_PRE_FREEZE_EVENTS,
        "frozen_hashes",
        "random_seed_acquired",
    )
    assert tuple(event.sequence_number for event in fixture.events) == tuple(
        range(len(fixture.events))
    )


@pytest.mark.parametrize("bad_bytes", (b"", b"x" * 31, b"x" * 33, bytearray(32)))
def test_event_order_seed_acquisition_rejects_non_exact_provider_bytes(
    bad_bytes,
):
    from validation import literature_evidence_isolation as isolation

    fixture = _Task8OrderingFixture(
        isolation,
        adapters.ADAPTER_DEFINITIONS["xxx_bethe_energy"],
        "task8-ordering-run-provider",
    )
    fixture.record_prerequisites()
    frozen = fixture.freeze()
    before = tuple(fixture.events)
    with pytest.raises(AdapterContractError, match="exactly 32 bytes"):
        isolation.acquire_run_seed(
            frozen,
            ordered_events=tuple(fixture.events),
            random_bytes=lambda count: bad_bytes,
            event_recorder=fixture.record,
        )
    assert tuple(fixture.events) == before


@pytest.mark.parametrize("event_index", range(len(_TASK8_PRE_FREEZE_EVENTS)))
@pytest.mark.parametrize("tamper_kind", ("missing", "modified", "extra"))
def test_event_order_rejects_each_exact_stage_detail_tamper_before_random(
    event_index,
    tamper_kind,
):
    from validation import literature_evidence_isolation as isolation

    fixture = _Task8OrderingFixture(
        isolation,
        adapters.ADAPTER_DEFINITIONS["xxx_bethe_energy"],
        "task8-ordering-exact-stage-details",
    )
    fixture.record_prerequisites()
    frozen = fixture.freeze()
    events = list(fixture.events)
    details = thaw_json(events[event_index].details)
    material_keys = tuple(
        key for key in details if key != "audit_run_id"
    )
    if tamper_kind == "missing":
        details.pop(material_keys[0])
    elif tamper_kind == "modified":
        details[material_keys[0]] = "0" * 64
    else:
        details["undeclared_commitment"] = "0" * 64
    original = events[event_index]
    events[event_index] = isolation.EventRecord(
        original.sequence_number,
        original.event_name,
        details,
    )
    provider_calls = []

    with pytest.raises(AdapterContractError, match="event|detail|tamper|mismatch"):
        isolation.acquire_run_seed(
            frozen,
            ordered_events=tuple(events),
            random_bytes=lambda count: provider_calls.append(count) or b"s" * count,
            event_recorder=fixture.record,
        )
    assert provider_calls == []


def test_event_order_rejects_swapped_stage_commitments_before_random():
    from validation import literature_evidence_isolation as isolation

    fixture = _Task8OrderingFixture(
        isolation,
        adapters.ADAPTER_DEFINITIONS["xxx_bethe_energy"],
        "task8-ordering-swapped-stage-details",
    )
    fixture.record_prerequisites()
    frozen = fixture.freeze()
    events = list(fixture.events)
    details = thaw_json(events[1].details)
    details["adapter_closure_sha256"], details["oracle_closure_sha256"] = (
        details["oracle_closure_sha256"],
        details["adapter_closure_sha256"],
    )
    original = events[1]
    events[1] = isolation.EventRecord(
        original.sequence_number,
        original.event_name,
        details,
    )
    provider_calls = []

    with pytest.raises(AdapterContractError, match="event|detail|tamper|mismatch"):
        isolation.acquire_run_seed(
            frozen,
            ordered_events=tuple(events),
            random_bytes=lambda count: provider_calls.append(count) or b"s" * count,
            event_recorder=fixture.record,
        )
    assert provider_calls == []


def test_event_order_rejects_pre_tampered_frozen_hash_snapshot():
    from validation import literature_evidence_isolation as isolation

    fixture = _Task8OrderingFixture(
        isolation,
        adapters.ADAPTER_DEFINITIONS["xxx_bethe_energy"],
        "task8-ordering-run-frozen-tamper",
    )
    fixture.record_prerequisites()
    frozen = fixture.freeze()
    object.__setattr__(frozen, "hash_material", freeze_json({}))

    with pytest.raises(AdapterContractError, match="frozen|tamper|mismatch"):
        isolation.acquire_run_seed(
            frozen,
            ordered_events=tuple(fixture.events),
            random_bytes=lambda count: b"s" * count,
            event_recorder=fixture.record,
        )


@pytest.mark.parametrize(
    "tamper_kind",
    (
        "definition",
        "domain",
        "size_policy",
        "output_proof",
        "convergence",
        "preflight",
        "command_hash",
        "scanner_hash",
        "dependency_partition",
        "infrastructure_closure",
    ),
)
def test_event_order_rejects_each_post_freeze_tamper_before_point_derivation(
    tamper_kind,
):
    from validation import literature_evidence_isolation as isolation

    fixture = _Task8OrderingFixture(
        isolation,
        _detached_adapter_definition(
            adapters.ADAPTER_DEFINITIONS["xxx_bethe_energy"]
        ),
        "task8-ordering-run-b",
    )
    fixture.record_prerequisites()
    frozen = fixture.freeze()

    if tamper_kind in {
        "definition", "domain", "size_policy", "output_proof", "convergence"
    }:
        if tamper_kind == "definition":
            object.__setattr__(fixture.definition, "oracle_id", "tampered_oracle")
        elif tamper_kind == "domain":
            object.__setattr__(
                fixture.definition.counterfactual_domain,
                "valid_rules",
                freeze_json({"exchange": {"kind": "finite"}}),
            )
        elif tamper_kind == "size_policy":
            object.__setattr__(
                fixture.definition.problem_size_policy,
                "kind",
                "fixed_local",
            )
        elif tamper_kind == "output_proof":
            object.__setattr__(
                fixture.definition.output_schema.fields[0][1],
                "proof_kind",
                "interval_bound",
            )
        else:
            object.__setattr__(
                fixture.definition.convergence_contract,
                "kind",
                "iterative",
            )
    elif tamper_kind == "preflight":
        object.__setattr__(fixture.preflight, "available", False)
    elif tamper_kind == "command_hash":
        fixture.command_hashes["unshare"] = "0" * 64
    elif tamper_kind == "scanner_hash":
        fixture.hash_material["scanner_sha256"] = "0" * 64
    else:
        field_name = tamper_kind + "_sha256"
        fixture.hash_material[field_name] = "0" * 64

    with pytest.raises(AdapterContractError, match="changed|mismatch|tamper"):
        fixture.freeze(frozen_snapshot=frozen)
    assert "counterfactual_points_derived" not in {
        event.event_name for event in fixture.events
    }


def _task8_point_payload(point):
    return {
        field.name: getattr(point, field.name)
        for field in dataclasses.fields(type(point))
    }


def _task8_behavior_payload(point):
    payload = _task8_point_payload(point)
    payload.pop("point_id")
    payload.pop("run_nonce")
    payload.pop("numerical_controls")
    return payload


def _task8_valid_points(points):
    return tuple(point for point in points if point.kind == "valid")


def _task8_expected_nonce(seed, adapter_id, point_kind, point_index):
    message = (
        b"counterfactual_domain_v1\0"
        + adapter_id.encode("ascii")
        + b"\0"
        + point_kind.encode("ascii")
        + b"\0"
        + point_index.to_bytes(8, "big")
        + (0).to_bytes(8, "big")
    )
    return hmac.new(seed, message, hashlib.sha256).hexdigest()


def test_counterfactual_point_is_public_exact_frozen_sealed_contract():
    from validation import literature_evidence_isolation as isolation

    assert "CounterfactualPoint" in isolation.__all__
    assert dataclasses.is_dataclass(isolation.CounterfactualPoint)
    assert {field.name for field in dataclasses.fields(
        isolation.CounterfactualPoint
    )} == {
        "schema_version",
        "domain_version",
        "adapter_id",
        "point_id",
        "run_nonce",
        "kind",
        "scientific_inputs",
        "numerical_controls",
        "problem_size",
        "expected_validation",
        "scientific_configuration",
        "metamorphic_metadata",
    }
    with pytest.raises(TypeError):
        class CounterfactualPointSubclass(isolation.CounterfactualPoint):
            pass


def test_counterfactual_point_constructor_is_exact_and_snapshots_aliases():
    from validation import literature_evidence_isolation as isolation

    point = isolation.derive_counterfactual_points(
        adapters.ADAPTER_DEFINITIONS["xxx_bethe_energy"], bytes(range(32))
    )[0]
    payload = _task8_point_payload(point)
    caller_inputs = thaw_json(point.scientific_inputs)
    caller_metadata = thaw_json(point.metamorphic_metadata)
    payload["scientific_inputs"] = caller_inputs
    payload["metamorphic_metadata"] = caller_metadata
    stored = isolation.CounterfactualPoint(**payload)
    caller_inputs["exchange"] = 99.0
    caller_metadata["relations"].append({"kind": "bounds"})

    assert stored.scientific_inputs == point.scientific_inputs
    assert stored.metamorphic_metadata == point.metamorphic_metadata
    missing = dict(payload)
    missing.pop("point_id")
    with pytest.raises(AdapterContractError, match="missing required field"):
        isolation.CounterfactualPoint(**missing)
    with pytest.raises(AdapterContractError, match="unknown field"):
        isolation.CounterfactualPoint(**payload, scientific_answer=1.0)

    object.__setattr__(stored, "kind", "forged_kind")
    with pytest.raises(AdapterContractError, match="unknown kind"):
        isolation.CounterfactualPoint(**_task8_point_payload(stored))


@pytest.mark.parametrize(
    ("point_kind", "expected_validation"),
    (
        (
            "canonical",
            {
                "outcome": "rejected",
                "reason_code": "scientific_input_rejected",
            },
        ),
        (
            "valid",
            {
                "outcome": "rejected",
                "reason_code": "scientific_input_rejected",
            },
        ),
        (
            "invalid",
            {"outcome": "accepted", "reason_code": "none"},
        ),
    ),
)
def test_counterfactual_point_binds_kind_to_validation_outcome(
    point_kind,
    expected_validation,
):
    from validation import literature_evidence_isolation as isolation

    points = isolation.derive_counterfactual_points(
        adapters.ADAPTER_DEFINITIONS["xxx_bethe_energy"], bytes(range(32))
    )
    source = next(point for point in points if point.kind == point_kind)
    payload = _task8_point_payload(source)
    payload["expected_validation"] = expected_validation

    with pytest.raises(AdapterContractError, match="kind|validation"):
        isolation.CounterfactualPoint(**payload)


@pytest.mark.parametrize(
    ("location", "forbidden_name"),
    (
        ("metadata", "candidate_values"),
        ("relation", "expected_answer"),
        ("relation", "literature_value"),
    ),
)
def test_counterfactual_point_rejects_answer_bearing_metamorphic_metadata(
    location,
    forbidden_name,
):
    from validation import literature_evidence_isolation as isolation

    point = isolation.derive_counterfactual_points(
        adapters.ADAPTER_DEFINITIONS["xxx_bethe_energy"], bytes(range(32))
    )[1]
    payload = _task8_point_payload(point)
    metadata = thaw_json(point.metamorphic_metadata)
    if location == "metadata":
        metadata[forbidden_name] = [1.0, 2.0]
    else:
        metadata["relations"][0][forbidden_name] = 1.0
    payload["metamorphic_metadata"] = metadata

    with pytest.raises(AdapterContractError, match="metamorphic|relation"):
        isolation.CounterfactualPoint(**payload)


def test_counterfactual_hmac_canary_and_seed_adapter_domain_separation():
    from validation import literature_evidence_isolation as isolation

    definition = adapters.ADAPTER_DEFINITIONS["xxx_bethe_energy"]
    seed = bytes(range(32))
    points = isolation.derive_counterfactual_points(definition, seed)

    assert points[0].kind == "canonical"
    assert points[0].run_nonce == _task8_expected_nonce(
        seed, "xxx_bethe_energy", "canonical", 0
    )
    domain_payload = {
        "valid_rules": definition.counterfactual_domain.valid_rules,
        "invalid_rules": definition.counterfactual_domain.invalid_rules,
    }
    domain_counter = int.from_bytes(
        hashlib.sha256(canonical_json_bytes(domain_payload)).digest()[:8],
        "big",
    )
    message = (
        b"counterfactual_domain_v1\0xxx_bethe_energy\0valid\0"
        + (0).to_bytes(8, "big")
        + ((domain_counter + 1) % (1 << 64)).to_bytes(8, "big")
    )
    unit_draw = int.from_bytes(
        hmac.new(seed, message, hashlib.sha256).digest()[:8], "big"
    ) / float(1 << 64)
    assert points[1].scientific_inputs["exchange"] == 0.75 + unit_draw
    assert points == isolation.derive_counterfactual_points(definition, seed)
    different_seed_points = isolation.derive_counterfactual_points(
        definition, bytes(reversed(range(32)))
    )
    assert tuple(map(_task8_behavior_payload, points)) != tuple(
        map(_task8_behavior_payload, different_seed_points)
    )
    assert points != isolation.derive_counterfactual_points(
        adapters.ADAPTER_DEFINITIONS["square_ising_self_dual_tc"], seed
    )

    changed_domain = _detached_adapter_definition(definition)
    object.__setattr__(
        changed_domain.counterfactual_domain,
        "valid_rules",
        freeze_json(
            {
                "exchange": {"kind": "finite_nonzero"},
                "physical_size_rule": {
                    "kind": "declared_limit_unchanged"
                },
            }
        ),
    )
    assert points != isolation.derive_counterfactual_points(
        changed_domain, seed
    )


@pytest.mark.parametrize("bad_seed", (b"", b"x" * 31, b"x" * 33, bytearray(32)))
def test_counterfactual_generator_rejects_every_non_exact_32_byte_seed(bad_seed):
    from validation import literature_evidence_isolation as isolation

    with pytest.raises(AdapterContractError, match="32 bytes"):
        isolation.derive_counterfactual_points(
            adapters.ADAPTER_DEFINITIONS["xxx_bethe_energy"], bad_seed
        )


def test_counterfactual_generation_is_fresh_process_deterministic():
    from validation import literature_evidence_isolation as isolation

    seed = bytes(range(32))
    definition = adapters.ADAPTER_DEFINITIONS["tfim_bdg_critical_point"]
    local_sha256 = hashlib.sha256(
        canonical_json_bytes(
            [_task8_point_payload(point) for point in
             isolation.derive_counterfactual_points(definition, seed)]
        )
    ).hexdigest()
    script = (
        "import dataclasses, hashlib, sys\n"
        "sys.path.insert(0, 'scripts')\n"
        "from validation import literature_evidence_adapters as a\n"
        "from validation import literature_evidence_isolation as i\n"
        "points = i.derive_counterfactual_points("
        "a.ADAPTER_DEFINITIONS['tfim_bdg_critical_point'], bytes(range(32)))\n"
        "payload = [{f.name: getattr(p, f.name) for f in "
        "dataclasses.fields(type(p))} for p in points]\n"
        "print(hashlib.sha256(a.canonical_json_bytes(payload)).hexdigest())\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == local_sha256


_TASK8_ALL_DEFINITION_IDS = (
    "xxx_bethe_energy",
    "square_ising_self_dual_tc",
    "triangular_ising_af_entropy_quadrature",
    "xy_chain_bdg_boundaries",
    "diamond_spiral_threshold_fourier",
    "spin_ice_tetrahedron_enumeration",
    "spin_ladder_rung_dense_ed",
    "pauling_entropy_combinatorics",
    "uls_two_site_su3_matrix",
    "aklt_projector_angle",
    "compass_line_symmetry_matrix",
    "kitaev_field_majorana_mass",
    "toric_code_stabilizer_rank",
    "aklt_two_site_projector_ed",
    "blume_capel_level_crossing",
    "checkerboard_plaquette_enumeration",
    "honeycomb_ising_star_triangle_tc",
    "kagome_ising_af_entropy_quadrature",
    "kagome_ising_star_triangle_tc",
    "majumdar_ghosh_dimer_ed",
    "ising_chain_transfer_matrix",
    "pyrochlore_coulomb_fourier",
    "shastry_sutherland_dimer_ed",
    "simple_cubic_j1_j2_fourier",
    "spin1_single_ion_dense_ed",
    "fully_frustrated_ising_entropy_series",
    "tfim_bdg_critical_point",
    "triangular_ising_star_triangle_tc",
    "xx_chain_fermion_integral",
)


@pytest.mark.parametrize("adapter_id", _TASK8_ALL_DEFINITION_IDS)
def test_counterfactual_matrix_covers_every_definition_and_family_minimum(
    adapter_id,
):
    from validation import literature_evidence_isolation as isolation

    assert tuple(adapters.ADAPTER_DEFINITIONS) == _TASK8_ALL_DEFINITION_IDS
    definition = adapters.ADAPTER_DEFINITIONS[adapter_id]
    points = isolation.derive_counterfactual_points(definition, bytes(range(32)))
    canonical = tuple(point for point in points if point.kind == "canonical")
    valid = _task8_valid_points(points)
    invalid = tuple(point for point in points if point.kind == "invalid")

    assert len(canonical) == 1
    assert len(invalid) == 1
    assert len({point.run_nonce for point in points}) == len(points)
    assert all(type(point) is isolation.CounterfactualPoint for point in points)
    assert all(point.adapter_id == adapter_id for point in points)
    assert all(point.domain_version == "counterfactual_domain_v1" for point in points)
    assert invalid[0].expected_validation["outcome"] == "rejected"
    assert invalid[0].expected_validation["reason_code"] in {
        "scientific_input_rejected",
        "numerical_control_rejected",
        "physical_size_rejected",
    }

    for point in (*canonical, *valid):
        adapters.validate_scientific_inputs(definition, point.scientific_inputs)
        adapters.validate_numerical_controls(definition, point.numerical_controls)
        assert point.expected_validation == freeze_json(
            {"outcome": "accepted", "reason_code": "none"}
        )

    size_kind = definition.problem_size_policy.kind
    if definition.backend_kind == "analytic":
        assert len(valid) == 3
        distinct_inputs = len({
            canonical_json_bytes(p.scientific_inputs) for p in valid
        })
        rule_kinds = {
            rule["kind"]
            for rule in definition.counterfactual_domain.valid_rules.values()
        }
        assert distinct_inputs == (
            1 if "tetrahedral_positive_integer" in rule_kinds else 3
        )
    elif definition.backend_kind in {"enumeration", "dense_ed"}:
        if size_kind == "fixed_local":
            assert len(valid) == 3
            assert all(
                p.problem_size == definition.problem_size_policy.fixed_sizes
                for p in valid
            )
        else:
            assert size_kind == "scalable_same_observable"
            assert len(valid) == 4
            sizes = [canonical_json_bytes(p.problem_size) for p in valid]
            assert len(set(sizes)) == 2
            assert all(sizes.count(size) == 2 for size in set(sizes))
            assert invalid[0].expected_validation["reason_code"] == (
                "physical_size_rejected"
            )
    elif definition.backend_kind == "glt_fourier":
        assert len(valid) == 6
        model_inputs = [canonical_json_bytes(p.scientific_inputs) for p in valid]
        assert len(set(model_inputs)) == 3
        assert all(model_inputs.count(value) == 2 for value in set(model_inputs))
        configurations = [
            canonical_json_bytes(p.scientific_configuration) for p in valid
        ]
        assert len(set(configurations)) == len(configurations)
        assert {
            p.scientific_configuration["representation"] for p in valid
        } == {"real_space", "fourier_space"}
        assert "real_fourier" in {
            relation["kind"]
            for p in valid
            for relation in p.metamorphic_metadata["relations"]
        }
    else:
        assert definition.backend_kind == "iterative_numeric"
        assert len(valid) >= 3
        assert len({canonical_json_bytes(p.scientific_inputs) for p in valid}) == 1
        assert invalid[0].expected_validation["reason_code"] == (
            "numerical_control_rejected"
        )
        for control_name, schema in definition.numerical_control_schema.properties:
            values = [point.numerical_controls[control_name] for point in valid]
            if "threshold" in control_name or "cutoff" in control_name:
                assert values == sorted(values, reverse=True)
                assert len(set(values)) == len(values)
            else:
                assert values == sorted(values)
                assert len(set(values)) == len(values)


_TASK8_GLT_DEFINITION_IDS = (
    "xy_chain_bdg_boundaries",
    "diamond_spiral_threshold_fourier",
    "kitaev_field_majorana_mass",
    "pyrochlore_coulomb_fourier",
    "simple_cubic_j1_j2_fourier",
    "tfim_bdg_critical_point",
)


@pytest.mark.parametrize("adapter_id", _TASK8_GLT_DEFINITION_IDS)
def test_glt_configuration_pairs_are_seeded_closed_and_executable(adapter_id):
    from validation import literature_evidence_isolation as isolation

    seed = bytes(range(32))
    definition = adapters.ADAPTER_DEFINITIONS[adapter_id]
    valid = _task8_valid_points(
        isolation.derive_counterfactual_points(definition, seed)
    )
    by_inputs = {}
    for point in valid:
        by_inputs.setdefault(
            canonical_json_bytes(point.scientific_inputs), []
        ).append(point)
        configuration = point.scientific_configuration
        assert set(configuration) == {
            "schema_version",
            "representation",
            "coordinates",
            "gauge_phase_fraction",
        }
        assert configuration["schema_version"] == (
            "glt_scientific_configuration_v1"
        )
        assert configuration["representation"] in {
            "real_space", "fourier_space",
        }
        assert len(configuration["coordinates"]) == 3
        assert all(
            type(value) is float and math.isfinite(value)
            and -1.0 <= value <= 1.0
            for value in configuration["coordinates"]
        )
        assert type(configuration["gauge_phase_fraction"]) is float
        assert 0.0 <= configuration["gauge_phase_fraction"] < 1.0
    assert len(by_inputs) == 3
    coupling_configurations = []
    for pair in by_inputs.values():
        assert len(pair) == 2
        assert {
            point.scientific_configuration["representation"] for point in pair
        } == {"real_space", "fourier_space"}
        assert pair[0].scientific_configuration["coordinates"] == (
            pair[1].scientific_configuration["coordinates"]
        )
        assert pair[0].scientific_configuration[
            "gauge_phase_fraction"
        ] == pair[1].scientific_configuration["gauge_phase_fraction"]
        coupling_configurations.append(
            (
                pair[0].scientific_configuration["coordinates"],
                pair[0].scientific_configuration["gauge_phase_fraction"],
            )
        )
        assert _task8_behavior_payload(pair[0]) != _task8_behavior_payload(pair[1])
    assert len(set(coupling_configurations)) == 3

    alternate = _task8_valid_points(
        isolation.derive_counterfactual_points(
            definition, bytes(reversed(range(32)))
        )
    )
    assert [point.scientific_configuration for point in valid] != [
        point.scientific_configuration for point in alternate
    ]


@pytest.mark.parametrize(
    "adapter_id",
    tuple(
        adapter_id
        for adapter_id in _TASK8_ALL_DEFINITION_IDS
        if adapters.ADAPTER_DEFINITIONS[
            adapter_id
        ].problem_size_policy.kind == "not_applicable"
        and adapters.ADAPTER_DEFINITIONS[
            adapter_id
        ].backend_kind != "iterative_numeric"
    ),
)
def test_not_applicable_invalid_points_use_numeric_domain_boundaries(
    adapter_id,
):
    from validation import literature_evidence_isolation as isolation

    definition = adapters.ADAPTER_DEFINITIONS[adapter_id]
    invalid = next(
        point
        for point in isolation.derive_counterfactual_points(
            definition, bytes(range(32))
        )
        if point.kind == "invalid"
    )
    adapters.validate_scientific_inputs(definition, invalid.scientific_inputs)
    numeric_values = tuple(
        invalid.scientific_inputs[name]
        for name, schema in definition.scientific_input_schema.properties
        if schema.kind in {"number", "integer"}
    )
    assert numeric_values
    assert all(type(value) in {int, float} for value in numeric_values)
    evaluation_payload = _task8_point_payload(invalid)
    evaluation_payload["kind"] = "valid"
    evaluation_payload["expected_validation"] = {
        "outcome": "accepted",
        "reason_code": "none",
    }
    evaluation_point = isolation.CounterfactualPoint(**evaluation_payload)
    assert isolation._counterfactual_validation_reason(
        definition, evaluation_point
    ) == "scientific_input_rejected"


def test_counterfactual_metadata_is_outer_relational_and_answer_free():
    from validation import literature_evidence_isolation as isolation

    allowed_relations = {
        "scaling", "symmetry", "continuity", "bounds", "basis_gauge",
        "real_fourier",
    }
    observed = set()
    forbidden_tokens = {
        "answer", "candidate", "literature", "output", "result", "target",
        "expected_value", "canonical_value",
    }
    for definition in adapters.ADAPTER_DEFINITIONS.values():
        for point in isolation.derive_counterfactual_points(
            definition, bytes(range(32))
        ):
            encoded = canonical_json_bytes(point.metamorphic_metadata).decode(
                "utf-8"
            ).lower()
            assert not any(token in encoded for token in forbidden_tokens)
            relations = point.metamorphic_metadata["relations"]
            observed.update(relation["kind"] for relation in relations)
            assert {relation["kind"] for relation in relations} <= allowed_relations
    assert observed == allowed_relations


@pytest.mark.parametrize(
    ("adapter_id", "expected_relations"),
    (
        (
            "xxx_bethe_energy",
            {"scaling", "continuity", "bounds"},
        ),
        (
            "spin_ice_tetrahedron_enumeration",
            {"scaling", "basis_gauge", "symmetry"},
        ),
        (
            "compass_line_symmetry_matrix",
            {"scaling", "continuity"},
        ),
        (
            "tfim_bdg_critical_point",
            {"real_fourier", "symmetry"},
        ),
        (
            "fully_frustrated_ising_entropy_series",
            {"continuity", "bounds", "scaling"},
        ),
    ),
)
def test_counterfactual_relations_bind_multiple_points_for_outer_validation(
    adapter_id,
    expected_relations,
):
    from validation import literature_evidence_isolation as isolation

    valid = _task8_valid_points(
        isolation.derive_counterfactual_points(
            adapters.ADAPTER_DEFINITIONS[adapter_id], bytes(range(32))
        )
    )
    for point in valid:
        assert {
            relation["kind"]
            for relation in point.metamorphic_metadata["relations"]
        } == expected_relations


def test_task8_public_signatures_are_stable_and_closed():
    from validation import literature_evidence_isolation as isolation

    assert str(inspect.signature(isolation.derive_counterfactual_points)) == (
        "(definition, seed)"
    )
    assert str(inspect.signature(isolation.acquire_run_seed)) == (
        "(frozen_snapshot, *, ordered_events, random_bytes, event_recorder)"
    )
    assert str(inspect.signature(isolation.record_and_freeze_hashes)) == (
        "(definition, *, audit_run_id, ordered_events, hash_material, "
        "capability_preflight, infrastructure_command_hashes, "
        "event_recorder, frozen_snapshot=None)"
    )


def test_task8_functions_have_exact_infrastructure_category(tmp_path):
    from validation import literature_evidence_isolation as isolation

    _write_task5_infrastructure_sources(tmp_path)
    closure = isolation.build_infrastructure_closure(source_roots=(tmp_path,))
    roots = {
        "validation.literature_evidence_isolation.record_and_freeze_hashes",
        "validation.literature_evidence_isolation.acquire_run_seed",
        "validation.literature_evidence_isolation.derive_counterfactual_points",
    }
    assert roots <= {node["qualified_name"] for node in closure.nodes}
    assert {
        closure.purpose_bindings[root] for root in roots
    } == {"event_and_counterfactual_transport"}
