import copy
import ast
import json
import math
import re
import shutil
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from validation.literature_evidence_inventory import (
    INVENTORY_ROOT,
    InventoryError,
    build_inventory_data,
    canonical_source_identity,
    derive_unresolved_status,
    load_canonical_observable_specs,
    load_and_validate_inventory,
    resolve_registry_selector,
    validate_inventory,
)
from validation.literature_evidence_schema import (
    EvidenceSchemaError,
    EvidenceRecord,
    ProvisionalEvidenceRecord,
)
from validation.literature_evidence_sources import authoritative_route_for_identity
from validation.literature_spin_model_benchmarks import (
    LITERATURE_STANDARD_RESULTS,
    classical_projection_verification_tasks,
    fecl3_cable_helix_geometry,
    pitch_and_ordering_vector_verification_tasks,
    residual_projection_verification_tasks,
)


EXPECTED_CORRECTED_CANONICAL_CONTRACTS = {
    "ba3irti2o9_honeycomb_kitaev_reference": ("local_source_parse", ("spin_liquid_candidate",)),
    "clinoatacamite_distorted_kagome_reference": ("local_source_parse", ("distorted_kagome_reference",)),
    "crcl3_honeycomb_heisenberg_reference": ("local_source_parse", ("ferromagnetic_honeycomb_layers",)),
    "crgete3_honeycomb_ferromagnet_reference": ("local_source_parse", ("ferromagnetic_order",)),
    "cu2iro3_honeycomb_kitaev_reference": ("local_source_parse", ("honeycomb_frustrated_iridate_identity",)),
    "cu2oseo3_skyrmion_lattice_reference": ("local_source_parse", ("skyrmion_lattice_phase",)),
    "dy2ti2o7_spin_ice_entropy_reference": ("local_source_parse", ("pauling_entropy_observed",)),
    "edwardsite_kagome_antiferromagnet_reference": ("local_source_parse", ("kagome_antiferromagnet_reference",)),
    "er2ti2o7_xy_pyrochlore_order_by_disorder_reference": ("local_source_parse", ("psi2_order_selected",)),
    "fe8_molecular_spin_tunneling_reference": ("local_source_parse", ("macroscopic_quantum_tunneling_observed",)),
    "fe_ps3_honeycomb_ising_reference": ("local_source_parse", ("ising_like_zigzag_order",)),
    "gadolinium_gallium_garnet_hyperkagome_reference": ("local_source_parse", ("strong_frustration",)),
    "gamma_li2iro3_3d_kitaev_reference": ("local_source_parse", ("incommensurate_spiral_order",)),
    "garnet_gd3te2li3o12_hyperkagome_reference": ("local_source_parse", ("garnet_frustrated_magnet",)),
    "h3liir2o6_kitaev_spin_liquid_candidate_reference": ("local_source_parse", ("no_magnetic_order_reported",)),
    "honeycomb_j1_j2_j3_classical_phase_diagram": ("local_source_parse", ("phases",)),
    "honeycomb_j1_j2_kitaev_material_na2iro3_reference": ("local_source_parse", ("zigzag_order_relevant",)),
    "honeycomb_kitaev_heisenberg_four_sublattice_phases": ("local_source_parse", ("ordered_phases",)),
    "j1_j2_chain_bkt_transition_reference": ("local_source_parse", ("critical_j2_over_j1_approx",)),
    "j1_j2_chain_okamoto_nomura_critical_point": ("local_source_parse", ("critical_j2_over_j1",)),
    "kagome_heisenberg_dmrg_spin_liquid_yan_reference": ("local_source_parse", ("energy_per_site", "spin_gap_over_j")),
    "kagome_spin_half_heisenberg_energy_reference": ("local_source_parse", ("energy_per_site_approx",)),
    "licuvo4_spiral_chain_reference": ("local_source_parse", ("incommensurate_spiral_order",)),
    "lieb_lattice_heisenberg_ferrimagnet_reference": ("local_source_parse", ("ground_state_spin_per_unit_cell",)),
    "mn_ps3_honeycomb_antiferromagnet_reference": ("local_source_parse", ("neel_order_reference",)),
    "mnsi_chiral_helimagnet_reference": ("local_source_parse", ("long_wavelength_helix",)),
    "nacuo2_triangular_heisenberg_material_reference": ("local_source_parse", ("unconventional_spin_order_reference",)),
    "ru_br3_kitaev_material_reference": ("local_source_parse", ("ru_honeycomb_kitaev_candidate",)),
    "ruby_lattice_heisenberg_flat_band_reference": ("local_source_parse", ("supports_localized_magnons",)),
    "shuriken_lattice_heisenberg_reference": ("local_source_parse", ("square_kagome_reference",)),
    "square_heisenberg_spin_half_spin_stiffness_reference": ("local_source_parse", ("rho_s_over_j",)),
    "square_heisenberg_spin_half_staggered_magnetization_reference": ("local_source_parse", ("staggered_magnetization",)),
    "square_heisenberg_spin_wave_velocity_reference": ("local_source_parse", ("renormalized_velocity_over_j_approx",)),
    "square_ring_exchange_neel_vbs_reference": ("local_source_parse", ("ring_exchange_drives_vbs_phase",)),
    "star_lattice_heisenberg_spin_liquid_reference": ("local_source_parse", ("spin_liquid_or_valence_bond_reference",)),
    "triangular_heisenberg_magnetization_plateau_reference": ("local_source_parse", ("one_third_plateau",)),
    "vesignieite_kagome_material_reference": ("local_source_parse", ("distorted_kagome_relevant",)),
    "blume_capel_spin1_zero_temperature_level_crossing": ("local_recompute", ("square_lattice_d_over_j_crossing",)),
    "checkerboard_heisenberg_afm_planar_pyrochlore_reference": ("local_recompute", ("zero_total_spin_per_crossed_plaquette",)),
    "cubic_ising_critical_temperature_reference": ("local_recompute", ("tc_over_j",)),
    "fcc_j1_j2_heisenberg_type_order_reference": ("local_recompute", ("common_orders",)),
    "honeycomb_ising_ferromagnet_exact_tc": ("local_recompute", ("tc_over_j",)),
    "honeycomb_j1_j2_spiral_ring_reference": ("local_recompute", ("ring_condition",)),
    "kagome_ising_antiferromagnet_residual_entropy_reference": ("local_recompute", ("macroscopic_ground_state_degeneracy",)),
    "kagome_ising_ferromagnet_exact_tc": ("local_recompute", ("tc_over_j",)),
    "majundar_ghosh_chain_exact_dimer_point": ("local_recompute", ("energy_per_site", "degenerate_dimer_coverings")),
    "one_dimensional_classical_ising_no_finite_t_transition": ("local_recompute", ("finite_temperature_transition", "tc_over_j")),
    "pyrochlore_heisenberg_afm_coulomb_phase_reference": ("local_recompute", ("zero_total_spin_per_tetrahedron", "pinch_points")),
    "shastry_sutherland_exact_dimer_product": ("local_recompute", ("energy_per_dimer", "energy_per_spin")),
    "simple_cubic_j1_j2_collinear_reference": ("local_recompute", ("neel_to_collinear_boundary_j2_over_j1",)),
    "single_ion_spin1_anisotropy_levels": ("local_recompute", ("levels", "degeneracies")),
    "square_fully_frustrated_ising_residual_entropy_reference": ("local_recompute", ("macroscopic_ground_state_degeneracy",)),
    "takhtajan_babujian_spin1_critical_point": ("local_recompute", ("theta_radians", "is_integrable")),
    "transverse_field_ising_chain_critical_point": ("local_recompute", ("critical_field_over_exchange",)),
    "transverse_field_ising_chain_gap": ("local_recompute", ("gap_formula", "gap_formula_at_g_0_6")),
    "triangular_ising_ferromagnet_exact_tc": ("local_recompute", ("tc_over_j",)),
    "xx_spin_half_chain_free_fermion_energy": ("local_recompute", ("energy_per_site",)),
    "xxz_spin_half_chain_phase_boundaries": ("local_recompute", ("ferromagnetic_boundary_delta", "neel_boundary_delta", "gapless_interval")),
}


EXPECTED_DOMAIN_CANONICAL_CONTRACTS = {'ba3irti2o9_honeycomb_kitaev_reference': {'identity': 'site_diluted_triangular_spin_liquid_candidate_assessment_in_ba3irti2o9',
                                           'primary_semantic': 'Boolean assessment of the '
                                                               'spin-liquid-candidate proposition '
                                                               'for site-diluted '
                                                               'triangular-lattice Ba3IrTi2O9.'},
 'blume_capel_spin1_zero_temperature_level_crossing': {'identity': 'square_lattice_d_over_j_crossing_in_spin_1_blume_capel',
                                                       'primary_semantic': 'Canonical literature '
                                                                           'observable: square '
                                                                           'lattice d over j '
                                                                           'crossing in spin 1 '
                                                                           'blume capel.'},
 'checkerboard_heisenberg_afm_planar_pyrochlore_reference': {'identity': 'zero_total_spin_per_crossed_plaquette_in_checkerboard_heisenberg_antiferromagnet',
                                                             'primary_semantic': 'Canonical '
                                                                                 'literature '
                                                                                 'observable: zero '
                                                                                 'total spin per '
                                                                                 'crossed '
                                                                                 'plaquette in '
                                                                                 'checkerboard '
                                                                                 'heisenberg '
                                                                                 'antiferromagnet.'},
 'clinoatacamite_distorted_kagome_reference': {'identity': 'distorted_kagome_characterization_in_clinoatacamite_distorted_kagome',
                                               'primary_semantic': 'Canonical literature '
                                                                   'observable: distorted kagome '
                                                                   'characterization in '
                                                                   'clinoatacamite distorted '
                                                                   'kagome.'},
 'crcl3_honeycomb_heisenberg_reference': {'identity': 'ferromagnetic_honeycomb_layers_in_crcl3_honeycomb_heisenberg',
                                          'primary_semantic': 'Canonical literature observable: '
                                                              'ferromagnetic honeycomb layers in '
                                                              'crcl3 honeycomb heisenberg.'},
 'crgete3_honeycomb_ferromagnet_reference': {'identity': 'ferromagnetic_order_in_crgete3_honeycomb_ferromagnet',
                                             'primary_semantic': 'Canonical literature observable: '
                                                                 'ferromagnetic order in crgete3 '
                                                                 'honeycomb ferromagnet.'},
 'cu2iro3_honeycomb_kitaev_reference': {'identity': 'honeycomb_frustrated_iridate_identity_of_cu2iro3',
                                        'primary_semantic': 'published identification of Cu2IrO3 '
                                                            'as a honeycomb frustrated iridate'},
 'cu2oseo3_skyrmion_lattice_reference': {'identity': 'skyrmion_lattice_phase_in_cu2oseo3_chiral_ferrimagnet',
                                         'primary_semantic': 'Canonical literature observable: '
                                                             'skyrmion lattice phase in cu2oseo3 '
                                                             'chiral ferrimagnet.'},
 'cubic_ising_critical_temperature_reference': {'identity': 'tc_over_j_in_classical_cubic_ising',
                                                'primary_semantic': 'Canonical literature '
                                                                    'observable: tc over j in '
                                                                    'classical cubic ising.'},
 'dy2ti2o7_spin_ice_entropy_reference': {'identity': 'pauling_entropy_observed_in_dy2ti2o7_spin_ice',
                                         'primary_semantic': 'Canonical literature observable: '
                                                             'pauling entropy observed in dy2ti2o7 '
                                                             'spin ice.'},
 'edwardsite_kagome_antiferromagnet_reference': {'identity': 'deformed_kagome_antiferromagnet_classification_in_hydrated_edwardsite',
                                                 'primary_semantic': 'Boolean classification '
                                                                     'proposition for hydrated '
                                                                     'spin-half edwardsite within '
                                                                     'a deformed-kagome '
                                                                     'antiferromagnet model.'},
 'er2ti2o7_xy_pyrochlore_order_by_disorder_reference': {'identity': 'psi2_order_selected_in_xy_pyrochlore_antiferromagnet',
                                                        'primary_semantic': 'Canonical literature '
                                                                            'observable: psi2 '
                                                                            'order selected in xy '
                                                                            'pyrochlore '
                                                                            'antiferromagnet.'},
 'fcc_j1_j2_heisenberg_type_order_reference': {'identity': 'common_orders_in_fcc_j1_j2_heisenberg',
                                               'primary_semantic': 'Canonical literature '
                                                                   'observable: common orders in '
                                                                   'fcc j1 j2 heisenberg.'},
 'fe8_molecular_spin_tunneling_reference': {'identity': 'macroscopic_quantum_tunneling_observed_in_fe8_single_molecule_magnet',
                                            'primary_semantic': 'Canonical literature observable: '
                                                                'macroscopic quantum tunneling '
                                                                'observed in fe8 single molecule '
                                                                'magnet.'},
 'fe_ps3_honeycomb_ising_reference': {'identity': 'ising_like_zigzag_order_in_feps3_honeycomb_ising',
                                      'primary_semantic': 'Canonical literature observable: ising '
                                                          'like zigzag order in feps3 honeycomb '
                                                          'ising.'},
 'gadolinium_gallium_garnet_hyperkagome_reference': {'identity': 'strong_geometric_frustration_assessment_in_gadolinium_gallium_garnet',
                                                     'primary_semantic': 'Boolean assessment of '
                                                                         'strong geometric '
                                                                         'frustration in the '
                                                                         'exchange-dipolar model '
                                                                         'of gadolinium gallium '
                                                                         'garnet.'},
 'gamma_li2iro3_3d_kitaev_reference': {'identity': 'incommensurate_spiral_order_in_gamma_li2iro3_3d_kitaev_gamma',
                                       'primary_semantic': 'Canonical literature observable: '
                                                           'incommensurate spiral order in gamma '
                                                           'li2iro3 3d kitaev gamma.'},
 'garnet_gd3te2li3o12_hyperkagome_reference': {'identity': 'first_order_long_range_order_proposition_in_gd3te2li3o12_hyperkagome_garnet',
                                               'primary_semantic': 'Boolean proposition for a '
                                                                   'first-order transition into '
                                                                   'long-range magnetic order in '
                                                                   'hyperkagome Gd3Te2Li3O12.'},
 'h3liir2o6_kitaev_spin_liquid_candidate_reference': {'identity': 'no_magnetic_order_reported_in_h3liir2o6_honeycomb_kitaev',
                                                      'primary_semantic': 'Canonical literature '
                                                                          'observable: no magnetic '
                                                                          'order reported in '
                                                                          'h3liir2o6 honeycomb '
                                                                          'kitaev.'},
 'honeycomb_ising_ferromagnet_exact_tc': {'identity': 'tc_over_j_in_classical_honeycomb_ising',
                                          'primary_semantic': 'Canonical literature observable: tc '
                                                              'over j in classical honeycomb '
                                                              'ising.'},
 'honeycomb_j1_j2_j3_classical_phase_diagram': {'identity': 'phases_in_honeycomb_j1_j2_j3_heisenberg',
                                                'primary_semantic': 'Canonical literature '
                                                                    'observable: phases in '
                                                                    'honeycomb j1 j2 j3 '
                                                                    'heisenberg.'},
 'honeycomb_j1_j2_kitaev_material_na2iro3_reference': {'identity': 'zigzag_order_relevant_in_na2iro3_honeycomb_kitaev_heisenberg',
                                                       'primary_semantic': 'Canonical literature '
                                                                           'observable: zigzag '
                                                                           'order relevant in '
                                                                           'na2iro3 honeycomb '
                                                                           'kitaev heisenberg.'},
 'honeycomb_j1_j2_spiral_ring_reference': {'identity': 'ring_condition_in_honeycomb_j1_j2_heisenberg',
                                           'primary_semantic': 'Canonical literature observable: '
                                                               'ring condition in honeycomb j1 j2 '
                                                               'heisenberg.'},
 'honeycomb_kitaev_heisenberg_four_sublattice_phases': {'identity': 'ordered_phases_in_honeycomb_kitaev_heisenberg',
                                                        'primary_semantic': 'Canonical literature '
                                                                            'observable: ordered '
                                                                            'phases in honeycomb '
                                                                            'kitaev heisenberg.'},
 'j1_j2_chain_bkt_transition_reference': {'identity': 'critical_j2_over_j1_approx_in_spin_1_2_j1_j2_chain',
                                          'primary_semantic': 'Canonical literature observable: '
                                                              'critical j2 over j1 approx in spin '
                                                              '1 2 j1 j2 chain.'},
 'j1_j2_chain_okamoto_nomura_critical_point': {'identity': 'critical_j2_over_j1_in_spin_1_2_j1_j2_chain',
                                               'primary_semantic': 'Canonical literature '
                                                                   'observable: critical j2 over '
                                                                   'j1 in spin 1 2 j1 j2 chain.'},
 'kagome_heisenberg_dmrg_spin_liquid_yan_reference': {'identity': 'energy_per_site_and_spin_gap_over_j_in_spin_1_2_kagome_heisenberg_afm',
                                                      'primary_semantic': 'Canonical literature '
                                                                          'observable: energy per '
                                                                          'site, spin gap over j '
                                                                          'in spin 1 2 kagome '
                                                                          'heisenberg afm.'},
 'kagome_ising_antiferromagnet_residual_entropy_reference': {'identity': 'macroscopic_ground_state_degeneracy_in_classical_kagome_ising_antiferromagnet',
                                                             'primary_semantic': 'Canonical '
                                                                                 'literature '
                                                                                 'observable: '
                                                                                 'macroscopic '
                                                                                 'ground state '
                                                                                 'degeneracy in '
                                                                                 'classical kagome '
                                                                                 'ising '
                                                                                 'antiferromagnet.'},
 'kagome_ising_ferromagnet_exact_tc': {'identity': 'tc_over_j_in_classical_kagome_ising',
                                       'primary_semantic': 'Canonical literature observable: tc '
                                                           'over j in classical kagome ising.'},
 'kagome_spin_half_heisenberg_energy_reference': {'identity': 'energy_per_site_approx_in_spin_1_2_kagome_heisenberg',
                                                  'primary_semantic': 'Canonical literature '
                                                                      'observable: energy per site '
                                                                      'approx in spin 1 2 kagome '
                                                                      'heisenberg.'},
 'licuvo4_spiral_chain_reference': {'identity': 'incommensurate_spiral_order_in_licuvo4_j1_j2_chain',
                                    'primary_semantic': 'Canonical literature observable: '
                                                        'incommensurate spiral order in licuvo4 j1 '
                                                        'j2 chain.'},
 'lieb_lattice_heisenberg_ferrimagnet_reference': {'identity': 'ground_state_spin_per_unit_cell_in_lieb_lattice_heisenberg',
                                                   'primary_semantic': 'Canonical literature '
                                                                       'observable: ground state '
                                                                       'spin per unit cell in lieb '
                                                                       'lattice heisenberg.'},
 'majundar_ghosh_chain_exact_dimer_point': {'identity': 'energy_per_site_and_degenerate_dimer_coverings_in_spin_1_2_j1_j2_chain',
                                            'primary_semantic': 'Canonical literature observable: '
                                                                'energy per site, degenerate dimer '
                                                                'coverings in spin 1 2 j1 j2 '
                                                                'chain.'},
 'mn_ps3_honeycomb_antiferromagnet_reference': {'identity': 'neel_order_characterization_in_mnps3_honeycomb_antiferromagnet',
                                                'primary_semantic': 'Canonical literature '
                                                                    'observable: neel order '
                                                                    'characterization in mnps3 '
                                                                    'honeycomb antiferromagnet.'},
 'mnsi_chiral_helimagnet_reference': {'identity': 'long_wavelength_helix_in_mnsi_chiral_helimagnet',
                                      'primary_semantic': 'Canonical literature observable: long '
                                                          'wavelength helix in mnsi chiral '
                                                          'helimagnet.'},
 'nacuo2_triangular_heisenberg_material_reference': {'identity': 'material_spin_order_reference_for_triangular_lattice_nacro2',
                                                     'primary_semantic': 'published '
                                                                         'neutron-scattering '
                                                                         'reference for '
                                                                         'unconventional spin '
                                                                         'order in '
                                                                         'triangular-lattice '
                                                                         'NaCrO2'},
 'one_dimensional_classical_ising_no_finite_t_transition': {'identity': 'finite_temperature_transition_and_tc_over_j_in_classical_ising_chain',
                                                            'primary_semantic': 'Canonical '
                                                                                'literature '
                                                                                'observable: '
                                                                                'finite '
                                                                                'temperature '
                                                                                'transition, tc '
                                                                                'over j in '
                                                                                'classical ising '
                                                                                'chain.'},
 'pyrochlore_heisenberg_afm_coulomb_phase_reference': {'identity': 'zero_total_spin_per_tetrahedron_and_pinch_points_in_classical_pyrochlore_heisenberg_afm',
                                                       'primary_semantic': 'Canonical literature '
                                                                           'observable: zero total '
                                                                           'spin per tetrahedron, '
                                                                           'pinch points in '
                                                                           'classical pyrochlore '
                                                                           'heisenberg afm.'},
 'ru_br3_kitaev_material_reference': {'identity': 'ideal_kitaev_candidate_assessment_in_competing_exchange_rubr3',
                                      'primary_semantic': 'Boolean assessment of the '
                                                          'ideal-Kitaev-candidate proposition for '
                                                          'RuBr3 under a competing Gamma-J3 '
                                                          'exchange description.'},
 'ruby_lattice_heisenberg_flat_band_reference': {'identity': 'localized_one_magnon_support_in_ruby_lattice_heisenberg',
                                                 'primary_semantic': 'Boolean assessment of '
                                                                     'whether the ruby-lattice '
                                                                     'Heisenberg model supports an '
                                                                     'exact localized one-magnon '
                                                                     'eigenstate.'},
 'shastry_sutherland_exact_dimer_product': {'identity': 'energy_per_dimer_and_energy_per_spin_in_shastry_sutherland',
                                            'primary_semantic': 'Canonical literature observable: '
                                                                'energy per dimer, energy per spin '
                                                                'in shastry sutherland.'},
    'shuriken_lattice_heisenberg_reference': {'identity': 'square_kagome_spin_liquid_like_and_localized_magnon_assessment',
                                           'primary_semantic': 'Boolean source-classification '
                                                               'proposition for spin-liquid-like '
                                                               'and localized-magnon behavior in '
                                                               'the uniform square-kagome '
                                                               'Heisenberg antiferromagnet.'},
 'simple_cubic_j1_j2_collinear_reference': {'identity': 'neel_to_collinear_boundary_j2_over_j1_in_simple_cubic_j1_j2_heisenberg',
                                            'primary_semantic': 'Canonical literature observable: '
                                                                'neel to collinear boundary j2 '
                                                                'over j1 in simple cubic j1 j2 '
                                                                'heisenberg.'},
 'single_ion_spin1_anisotropy_levels': {'identity': 'levels_and_degeneracies_in_spin_1_single_ion_anisotropy',
                                        'primary_semantic': 'Canonical literature observable: '
                                                            'levels, degeneracies in spin 1 single '
                                                            'ion anisotropy.'},
 'square_fully_frustrated_ising_residual_entropy_reference': {'identity': 'macroscopic_ground_state_degeneracy_in_fully_frustrated_square_ising',
                                                              'primary_semantic': 'Canonical '
                                                                                  'literature '
                                                                                  'observable: '
                                                                                  'macroscopic '
                                                                                  'ground state '
                                                                                  'degeneracy in '
                                                                                  'fully '
                                                                                  'frustrated '
                                                                                  'square ising.'},
 'square_heisenberg_spin_half_spin_stiffness_reference': {'identity': 'spin_stiffness_over_exchange_in_spin_half_square_heisenberg_antiferromagnet',
                                                          'primary_semantic': 'Spin stiffness '
                                                                              'rho_s/J of the '
                                                                              'thermodynamic '
                                                                              'spin-half '
                                                                              'square-lattice '
                                                                              'Heisenberg '
                                                                              'antiferromagnet.'},
 'square_heisenberg_spin_half_staggered_magnetization_reference': {'identity': 'staggered_magnetization_density_in_spin_half_square_heisenberg_antiferromagnet',
                                                                   'primary_semantic': 'Staggered '
                                                                                       'magnetization '
                                                                                       'density of '
                                                                                       'the '
                                                                                       'thermodynamic '
                                                                                       'spin-half '
                                                                                       'square-lattice '
                                                                                       'Heisenberg '
                                                                                       'antiferromagnet.'},
 'square_heisenberg_spin_wave_velocity_reference': {'identity': 'renormalized_spin_wave_velocity_in_spin_half_square_heisenberg_antiferromagnet',
                                                    'primary_semantic': 'Renormalized spin-wave '
                                                                        'velocity c/(Ja) of the '
                                                                        'thermodynamic spin-half '
                                                                        'square-lattice Heisenberg '
                                                                        'antiferromagnet.'},
 'square_ring_exchange_neel_vbs_reference': {'identity': 'bond_spin_peierls_order_proposition_in_square_xy_ring_exchange',
                                             'primary_semantic': 'Boolean phase-classification '
                                                                 'proposition for bond-plaquette '
                                                                 'or spin-Peierls order in the '
                                                                 'square-lattice spin-half XY '
                                                                 'model with four-spin ring '
                                                                 'exchange.'},
 'star_lattice_heisenberg_spin_liquid_reference': {'identity': 'valence_bond_crystal_classification_in_uniform_star_lattice_heisenberg',
                                                   'primary_semantic': 'Boolean '
                                                                       'phase-classification '
                                                                       'proposition for a '
                                                                       'valence-bond crystal in '
                                                                       'the uniform spin-half '
                                                                       'star-lattice Heisenberg '
                                                                       'antiferromagnet.'},
 'takhtajan_babujian_spin1_critical_point': {'identity': 'theta_radians_and_property_integrable_in_spin_1_bilinear_biquadratic_chain',
                                             'primary_semantic': 'Canonical literature observable: '
                                                                 'theta radians, property '
                                                                 'integrable in spin 1 bilinear '
                                                                 'biquadratic chain.'},
 'transverse_field_ising_chain_critical_point': {'identity': 'critical_field_over_exchange_in_spin_1_2_transverse_field_ising_chain',
                                                 'primary_semantic': 'Canonical literature '
                                                                     'observable: critical field '
                                                                     'over exchange in spin 1 2 '
                                                                     'transverse field ising '
                                                                     'chain.'},
 'transverse_field_ising_chain_gap': {'identity': 'gap_formula_and_gap_formula_at_g_0_6_in_spin_1_2_transverse_field_ising_chain',
                                      'primary_semantic': 'Canonical literature observable: gap '
                                                          'formula, gap formula at g 0 6 in spin 1 '
                                                          '2 transverse field ising chain.'},
 'triangular_heisenberg_magnetization_plateau_reference': {'identity': 'one_third_magnetization_plateau_proposition_in_triangular_heisenberg_spin_wave_expansion',
                                                           'primary_semantic': 'Boolean '
                                                                               'proposition for a '
                                                                               'one-third '
                                                                               'magnetization '
                                                                               'plateau over a '
                                                                               'finite field '
                                                                               'interval in the '
                                                                               'spin-wave '
                                                                               'expansion of the '
                                                                               'triangular-lattice '
                                                                               'Heisenberg '
                                                                               'antiferromagnet.'},
 'triangular_ising_ferromagnet_exact_tc': {'identity': 'tc_over_j_in_classical_triangular_ising',
                                           'primary_semantic': 'Canonical literature observable: '
                                                               'tc over j in classical triangular '
                                                               'ising.'},
 'vesignieite_kagome_material_reference': {'identity': 'structural_distortion_relevance_in_dominant_j3_vesignieite',
                                           'primary_semantic': 'Boolean assessment of whether '
                                                               'structural kagome distortion is '
                                                               'the relevant mechanism in the '
                                                               'dominant-J3 model of vesignieite.'},
 'xx_spin_half_chain_free_fermion_energy': {'identity': 'energy_per_site_in_spin_1_2_xx_chain',
                                            'primary_semantic': 'Canonical literature observable: '
                                                                'energy per site in spin 1 2 xx '
                                                                'chain.'},
 'xxz_spin_half_chain_phase_boundaries': {'identity': 'ferromagnetic_boundary_delta_and_neel_boundary_delta_and_gapless_interval_in_spin_1_2_xxz_chain',
                                          'primary_semantic': 'Canonical literature observable: '
                                                              'ferromagnetic boundary delta, neel '
                                                              'boundary delta, gapless interval in '
                                                              'spin 1 2 xxz chain.'}}


@pytest.fixture(scope="module")
def loaded_inventory():
    return validate_inventory(
        build_inventory_data(LITERATURE_STANDARD_RESULTS),
        LITERATURE_STANDARD_RESULTS,
    )


def mutable_inventory(loaded_inventory):
    return copy.deepcopy(loaded_inventory.as_plain_data())


def test_inventory_has_exact_registry_contract_record_and_locator_name_sets(
    loaded_inventory,
):
    registry_names = {entry["name"] for entry in LITERATURE_STANDARD_RESULTS}
    contract_names = {
        contract.benchmark_name for contract in loaded_inventory.contracts
    }
    record_names = {record.benchmark_name for record in loaded_inventory.records}
    locator_names = {
        row["benchmark_name"] for row in loaded_inventory.locator_inventory
    }
    filenames = {path.stem for path in (INVENTORY_ROOT / "records").glob("*.json")}

    assert len(registry_names) == 155
    assert len(loaded_inventory.contracts) == 155
    assert len(loaded_inventory.records) == 155
    assert len(loaded_inventory.locator_inventory) == 155
    assert filenames == registry_names == contract_names == record_names == locator_names


def test_contracts_define_complete_concrete_claim_identity(loaded_inventory):
    generic_observables = {
        "material_reference",
        "material_model_reference",
        "phase_diagram_reference",
        "phase_reference",
        "status",
    }
    required = {
        "subject",
        "system",
        "hamiltonian",
        "parameter_regime",
        "size_or_limit",
        "observable",
        "representation",
        "units",
        "conditions",
    }
    for contract in loaded_inventory.contracts:
        assert required <= set(contract.as_plain_data())
        assert contract.observable["identity"] not in generic_observables
        assert contract.observable["claim_fields"]
        assert {
            field["id"] for field in contract.representation["fields"]
        } == set(contract.observable["claim_fields"])


def test_contracts_reject_all_generic_placeholder_families(loaded_inventory):
    forbidden_exact = {
        "Registered literature claim identified by named fields",
        "multi_field_registered_claim",
        "source_defined_registered_regime",
        "registry_defined_or_dimensionless",
    }
    forbidden_patterns = ("registered literature claim", "source_defined", "registry_defined")
    subjects = []
    for contract in loaded_inventory.contracts:
        plain = contract.as_plain_data()
        subjects.append(contract.subject)
        checked = (
            contract.subject,
            contract.observable["identity"],
            contract.size_or_limit["category"],
            contract.units,
        )
        assert forbidden_exact.isdisjoint(checked)
        assert not any(
            pattern in value.lower()
            for value in checked
            for pattern in forbidden_patterns
        )
        assert not contract.observable["identity"].startswith(
            ("published_observable_", "material_model_", "phase_diagram_")
        )
        assert all(
            "under the declared parameter regime" not in semantic
            and "published published observable" not in semantic
            for semantic in contract.observable["semantics"]
        )
        for field in contract.representation["fields"]:
            assert field["units"]
            assert field["convention"]
    assert len(set(subjects)) == 155


def test_every_benchmark_has_an_explicit_canonical_observable_spec():
    registry_names = {entry["name"] for entry in LITERATURE_STANDARD_RESULTS}
    specs = load_canonical_observable_specs()
    assert set(specs) == registry_names
    for name, spec in specs.items():
        assert set(spec) == {"identity", "primary_semantic"}, name
        assert spec["identity"].strip()
        assert spec["primary_semantic"].strip()
        assert not spec["identity"].endswith(
            ("_reference", "_candidate", "_status", "_claim")
        )


def test_exact_58_scientific_correction_contracts_are_source_derived_and_target_free(
    loaded_inventory,
):
    contracts = {
        contract.benchmark_name: contract
        for contract in loaded_inventory.contracts
    }

    assert len(EXPECTED_CORRECTED_CANONICAL_CONTRACTS) == 58
    assert len(EXPECTED_DOMAIN_CANONICAL_CONTRACTS) == 58
    assert set(EXPECTED_DOMAIN_CANONICAL_CONTRACTS) == set(
        EXPECTED_CORRECTED_CANONICAL_CONTRACTS
    )
    assert set(EXPECTED_CORRECTED_CANONICAL_CONTRACTS) <= set(contracts)
    for name, (mode, fields) in EXPECTED_CORRECTED_CANONICAL_CONTRACTS.items():
        contract = contracts[name]
        expected_domain = EXPECTED_DOMAIN_CANONICAL_CONTRACTS[name]

        assert contract.observable["identity"] == expected_domain["identity"]
        assert (
            contract.observable["semantics"][0]
            == expected_domain["primary_semantic"]
        )
        assert contract.observable["claim_fields"] == fields
        assert tuple(
            field["id"] for field in contract.representation["fields"]
        ) == fields
        assert {
            field["derivation"]
            for field in contract.representation["fields"]
        } == {mode}

        serialized = json.dumps(contract.as_plain_data(), sort_keys=True).lower()
        for forbidden in (
            '"answer"',
            '"target"',
            '"source_excerpt"',
            '"source_sha256"',
            '"verdict"',
            '"pass"',
        ):
            assert forbidden not in serialized


def test_exact_58_domain_identities_exclude_execution_modes_and_legacy_keys(
    loaded_inventory,
):
    contracts = {
        contract.benchmark_name: contract
        for contract in loaded_inventory.contracts
    }

    for name in EXPECTED_CORRECTED_CANONICAL_CONTRACTS:
        contract = contracts[name]
        identity = contract.observable["identity"]
        primary_semantic = contract.observable["semantics"][0]
        for execution_mode in ("local_source_parse", "local_recompute"):
            assert execution_mode not in identity
            assert execution_mode not in primary_semantic
        assert name not in identity
        assert name not in primary_semantic


def test_jiang_canonical_contracts_do_not_embed_numeric_target_tokens(
    loaded_inventory,
):
    contracts = {
        contract.benchmark_name: contract.as_plain_data()
        for contract in loaded_inventory.contracts
    }
    jiang_targets = {
        "square_heisenberg_spin_half_spin_stiffness_reference": "0.18081",
        "square_heisenberg_spin_half_staggered_magnetization_reference": "0.30743",
        "square_heisenberg_spin_wave_velocity_reference": "1.6586",
    }

    for name, token in jiang_targets.items():
        serialized = json.dumps(contracts[name], sort_keys=True)
        bounded_token = rf"(?<![0-9A-Za-z_.]){re.escape(token)}(?![0-9A-Za-z_.])"
        assert re.search(bounded_token, serialized) is None


AUDITED_CANONICAL_NUMERIC_TARGET_INPUTS = frozenset(
    {
        # The Lieb-lattice spin-1/2 input happens to equal the theorem output.
        (
            "lieb_lattice_heisenberg_ferrimagnet_reference",
            "ground_state_spin_per_unit_cell",
            ("conditions", "model_parameters", "spin"),
            float,
            0.5,
        ),
        (
            "lieb_lattice_heisenberg_ferrimagnet_reference",
            "ground_state_spin_per_unit_cell",
            ("parameter_regime", "spin"),
            float,
            0.5,
        ),
        # Unit spin and unit anisotropy set the single-ion reference scale.
        (
            "single_ion_spin1_anisotropy_levels",
            "levels",
            ("conditions", "model_parameters", "anisotropy"),
            float,
            1.0,
        ),
        (
            "single_ion_spin1_anisotropy_levels",
            "levels",
            ("conditions", "model_parameters", "spin"),
            float,
            1.0,
        ),
        (
            "single_ion_spin1_anisotropy_levels",
            "levels",
            ("parameter_regime", "anisotropy"),
            float,
            1.0,
        ),
        (
            "single_ion_spin1_anisotropy_levels",
            "levels",
            ("parameter_regime", "spin"),
            float,
            1.0,
        ),
        # Unit exchange sets the transverse-field Ising normalization.
        (
            "transverse_field_ising_chain_critical_point",
            "critical_field_over_exchange",
            ("conditions", "model_parameters", "exchange"),
            float,
            1.0,
        ),
        (
            "transverse_field_ising_chain_critical_point",
            "critical_field_over_exchange",
            ("parameter_regime", "exchange"),
            float,
            1.0,
        ),
    }
)


def test_exact_58_canonical_surfaces_do_not_embed_selected_target_values(
    loaded_inventory,
):
    contracts = {
        contract.benchmark_name: contract.as_plain_data()
        for contract in loaded_inventory.contracts
    }
    registry = {
        entry["name"]: entry for entry in LITERATURE_STANDARD_RESULTS
    }

    for name, (_, fields) in EXPECTED_CORRECTED_CANONICAL_CONTRACTS.items():
        contract = contracts[name]
        text_surface = "\n".join(_recursive_strings(contract)).lower()
        numeric_surface = _recursive_numeric_leaves(contract)
        selected_targets = {
            field: registry[name]["standard_result"][field]
            for field in fields
        }
        for selected_field, selected_target in selected_targets.items():
            for target in _recursive_leaves(selected_target):
                numeric_matches = _matching_numeric_target_leaves(
                    numeric_surface,
                    target,
                    benchmark_name=name,
                    selected_field=selected_field,
                )
                assert numeric_matches == [], (
                    name,
                    selected_field,
                    target,
                    numeric_matches,
                )
                pattern = _bounded_target_token_pattern(target)
                if pattern is not None:
                    assert re.search(pattern, text_surface) is None, (
                        name,
                        selected_field,
                        target,
                    )


def test_numeric_target_guard_only_allows_audited_input_paths():
    lieb_name = "lieb_lattice_heisenberg_ferrimagnet_reference"
    lieb_field = "ground_state_spin_per_unit_cell"
    lieb_input_surface = {
        "conditions": {"model_parameters": {"spin": 0.5}},
        "parameter_regime": {"spin": 0.5},
    }
    assert _matching_numeric_target_leaves(
        _recursive_numeric_leaves(lieb_input_surface),
        0.5,
        benchmark_name=lieb_name,
        selected_field=lieb_field,
    ) == []

    mutated_lieb_surface = copy.deepcopy(lieb_input_surface)
    mutated_lieb_surface["observable"] = {"predeclared_result": 0.5}
    assert _matching_numeric_target_leaves(
        _recursive_numeric_leaves(mutated_lieb_surface),
        0.5,
        benchmark_name=lieb_name,
        selected_field=lieb_field,
    ) == [(("observable", "predeclared_result"), 0.5)]

    assert _matching_numeric_target_leaves(
        _recursive_numeric_leaves(
            {"parameter_regime": {"theta": -math.pi / 4.0}}
        ),
        -math.pi / 4.0,
        benchmark_name="takhtajan_babujian_spin1_critical_point",
        selected_field="theta_radians",
    ) == [(("parameter_regime", "theta"), -math.pi / 4.0)]


def test_takhtajan_babujian_contract_does_not_predeclare_selected_outputs(
    loaded_inventory,
):
    name = "takhtajan_babujian_spin1_critical_point"
    contract = next(
        item.as_plain_data()
        for item in loaded_inventory.contracts
        if item.benchmark_name == name
    )
    registry_entry = next(
        item for item in LITERATURE_STANDARD_RESULTS if item["name"] == name
    )
    theta_target = registry_entry["standard_result"]["theta_radians"]
    theta_matches = _matching_numeric_target_leaves(
        _recursive_numeric_leaves(contract),
        theta_target,
        benchmark_name=name,
        selected_field="theta_radians",
    )

    assert theta_matches == []
    expected_regime = {
        "coupling_constraint": (
            "positive_bilinear_and_equal_magnitude_negative_biquadratic"
        )
    }
    assert registry_entry["parameters"] == expected_regime
    assert contract["parameter_regime"] == expected_regime
    assert contract["conditions"]["model_parameters"] == expected_regime
    for input_surface in (
        registry_entry["parameters"],
        contract["parameter_regime"],
        contract["conditions"]["model_parameters"],
    ):
        _assert_tb_input_surface_is_result_neutral(input_surface)

    assert "is_integrable" in contract["observable"]["claim_fields"]
    assert registry_entry["standard_result"] == {
        "theta_radians": -math.pi / 4.0,
        "is_integrable": True,
    }


def test_takhtajan_babujian_input_guard_rejects_result_bearing_mutations():
    neutral_input = {
        "coupling_constraint": (
            "positive_bilinear_and_equal_magnitude_negative_biquadratic"
        )
    }
    _assert_tb_input_surface_is_result_neutral(neutral_input)

    result_bearing_mutations = (
        {
            "coupling_point": (
                "integrable_bilinear_biquadratic_critical_point"
            )
        },
        {"is_integrable": True},
    )
    for mutated_input in result_bearing_mutations:
        with pytest.raises(AssertionError, match="predeclares selected result"):
            _assert_tb_input_surface_is_result_neutral(mutated_input)


def test_gtlg_contract_and_registry_parameters_exclude_observed_transition_outputs(
    loaded_inventory,
):
    name = "garnet_gd3te2li3o12_hyperkagome_reference"
    contract = next(
        item for item in loaded_inventory.contracts if item.benchmark_name == name
    )
    registry_entry = next(
        item for item in LITERATURE_STANDARD_RESULTS if item["name"] == name
    )
    forbidden_output_fields = {"ordering_temperature_k", "ordering_transition"}
    contract_data = contract.as_plain_data()
    serialized = json.dumps(contract_data, sort_keys=True).lower()

    assert forbidden_output_fields.isdisjoint(_recursive_keys(contract_data))
    assert forbidden_output_fields.isdisjoint(registry_entry["parameters"])
    assert re.search(r"(?<![0-9.])0\.243(?![0-9])", serialized) is None
    assert re.search(r"(?<![0-9])243\s*m?k(?![a-z])", serialized) is None


@pytest.mark.parametrize(
    "placeholder_identity",
    [
        "material_reference",
        "spin_liquid_candidate",
        "plaquette_order_candidate",
        "phase_status",
        "published_claim",
    ],
)
def test_inventory_rejects_status_like_observable_identities(
    loaded_inventory, placeholder_identity
):
    data = mutable_inventory(loaded_inventory)
    contract = data["contracts"][0]
    contract["observable"]["identity"] = placeholder_identity
    with pytest.raises(InventoryError, match="generic observable identity"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


def test_representative_placeholder_fields_expand_to_scientific_observables(
    loaded_inventory,
):
    contracts = {
        item.benchmark_name: item for item in loaded_inventory.contracts
    }
    expected = {
        "ba3irti2o9_honeycomb_kitaev_reference": (
            "site_diluted_triangular_spin_liquid_candidate_assessment_in_ba3irti2o9",
            "Boolean assessment of the spin-liquid-candidate proposition for site-diluted triangular-lattice Ba3IrTi2O9.",
        ),
        "herbertsmithite_kagome_qsl_reference": (
            "assessment_of_quantum_spin_liquid_behavior_in_herbertsmithite",
            "published experimental assessment of quantum-spin-liquid behavior",
        ),
        "checkerboard_heisenberg_plaquette_reference": (
            "plaquette_long_range_order_and_valence_bond_crystal_in_spin_half_checkerboard_heisenberg_antiferromagnet",
            "published long-range order in four-spin S=0 plaquettes and valence-bond-crystal identification",
        ),
        "j1_j2_square_spin_half_neel_collinear_transition_reference": (
            "nonmagnetic_phase_window_in_j2_over_j1",
            "approximate nonmagnetic-phase interval in the J2/J1 coupling ratio",
        ),
        "two_dimensional_xy_bkt_universal_jump": (
            "universal_bkt_helicity_modulus_jump_relation",
            "universal relation between helicity modulus and transition temperature",
        ),
    }
    for benchmark_name, (identity, semantic) in expected.items():
        contract = contracts[benchmark_name]
        assert contract.observable["identity"] == identity
        assert semantic in contract.observable["semantics"]
        assert contract.conditions["physical_regime"]
        assert contract.conditions["source_claim_scope"]
        assert contract.conditions["model_parameters"] == contract.parameter_regime


def test_scientific_sequence_and_normalization_conventions_are_distinct(
    loaded_inventory,
):
    contracts = {
        item.benchmark_name: item for item in loaded_inventory.contracts
    }

    j1_j2 = contracts[
        "j1_j2_square_spin_half_neel_collinear_transition_reference"
    ]
    nonmagnetic_window = j1_j2.representation["fields"][0]
    assert nonmagnetic_window == {
        "id": "nonmagnetic_window_approx",
        "type": "list[number]",
        "units": "dimensionless_j2_over_j1",
        "convention": "closed_interval_endpoints_in_ascending_j2_over_j1",
    }

    bkt = contracts["two_dimensional_xy_bkt_universal_jump"]
    bkt_fields = {field["id"]: field for field in bkt.representation["fields"]}
    assert bkt_fields["helicity_modulus_at_t_1"] == {
        "id": "helicity_modulus_at_t_1",
        "type": "number",
        "units": "helicity_modulus_over_exchange_j",
        "convention": "rho_s_over_j_at_temperature_over_j_equal_one",
    }
    normalization = bkt.conditions["normalization_relation"]
    assert tuple(normalization["normalized_quantities"]) == ("rho_s/J", "T/J")
    assert normalization["universal_coefficient"] == (
        "must_be_parsed_from_authoritative_source"
    )

    expected_nonfallback = {
        "aklt_tan_theta": (
            "dimensionless_tangent_of_bilinear_biquadratic_angle",
            "tan_theta_in_declared_hamiltonian_parameterization",
        ),
        "spin_liquid_window_approx": (
            "dimensionless_j2_over_j1",
            "closed_interval_endpoints_in_ascending_j2_over_j1",
        ),
        "ground_state_spin_per_unit_cell": (
            "spin_angular_momentum_hbar",
            "total_ground_state_spin_per_crystallographic_unit_cell",
        ),
        "degenerate_dimer_coverings": (
            "count",
            "nonnegative_integer_number_of_exact_dimer_coverings",
        ),
        "ising_critical_field": (
            "field_over_exchange_j",
            "critical_transverse_field_normalized_by_exchange_j",
        ),
    }
    observed = {
        field["id"]: (field["units"], field["convention"])
        for contract in loaded_inventory.contracts
        for field in contract.representation["fields"]
        if field["id"] in expected_nonfallback
    }
    assert observed == expected_nonfallback
    forbidden_fallbacks = {
        "field_dependent_sequence",
        "scalar_or_structured_claim",
        "dimensionless_sequence",
        "dimensionless_observable",
        "ordered_values_under_declared_convention",
        "scalar_under_declared_hamiltonian_convention",
    }
    assert not {
        field[key]
        for contract in loaded_inventory.contracts
        for field in contract.representation["fields"]
        for key in ("units", "convention")
    }.intersection(forbidden_fallbacks)

    phase_contract = next(
        item
        for item in loaded_inventory.contracts
        if any(field["id"] == "phases" for field in item.representation["fields"])
    )
    phase_field = next(
        field for field in phase_contract.representation["fields"] if field["id"] == "phases"
    )
    assert phase_field["units"] == "not_applicable"
    assert phase_field["convention"] == "categorical_phase_label_set"

    coupling_contract = next(
        item
        for item in loaded_inventory.contracts
        if any(field["id"] == "couplings" for field in item.representation["fields"])
    )
    coupling_field = next(
        field
        for field in coupling_contract.representation["fields"]
        if field["id"] == "couplings"
    )
    assert coupling_field["units"] == "source_declared_coupling_units"
    assert coupling_field["convention"] == "named_hamiltonian_coupling_parameter_map"

    degeneracy_contract = next(
        item
        for item in loaded_inventory.contracts
        if any(field["id"] == "degeneracies" for field in item.representation["fields"])
    )
    degeneracy_field = next(
        field
        for field in degeneracy_contract.representation["fields"]
        if field["id"] == "degeneracies"
    )
    assert degeneracy_field["units"] == "count"
    assert degeneracy_field["convention"] == "ordered_nonnegative_integer_degeneracies"


def test_selectors_equal_literal_registry_claim_fields(loaded_inventory):
    literal_fields = _literal_registry_claim_fields()
    assert len(literal_fields) == 155
    for record in loaded_inventory.records:
        assert tuple(record.registry_selector["fields"]) == literal_fields[
            record.benchmark_name
        ]


def test_haldane_selector_excludes_runtime_curie_weiss_augmentation(loaded_inventory):
    record = next(
        item
        for item in loaded_inventory.records
        if item.benchmark_name == "haldane_spin1_chain_gap_reference"
    )
    contract = next(
        item
        for item in loaded_inventory.contracts
        if item.benchmark_name == record.benchmark_name
    )
    assert tuple(record.registry_selector["fields"]) == ("gap_over_j",)
    assert contract.observable["claim_fields"] == ("gap_over_j",)
    assert contract.subject == "Spin-1 Heisenberg-chain Haldane excitation gap"
    assert contract.size_or_limit["category"] == "thermodynamic_limit"
    assert contract.representation["fields"][0]["units"] == "dimensionless_ratio"


@pytest.mark.parametrize(
    ("benchmark_name", "subject_terms", "scope_category"),
    [
        (
            "aklt_spin1_chain_projector_ground_state",
            {"aklt", "projector", "ground", "state"},
            "exact_model_limit",
        ),
        (
            "xxz_spin_half_chain_phase_boundaries",
            {"xxz", "phase", "boundaries"},
            "thermodynamic_limit",
        ),
        (
            "square_spin_half_heisenberg_qmc_energy",
            {"square", "heisenberg", "qmc", "energy"},
            "thermodynamic_limit",
        ),
        (
            "alpha_rucl3_kitaev_gamma_zigzag_reference",
            {"alpha", "rucl3", "kitaev", "zigzag"},
            "published_experimental_material_conditions_pending_source_verification",
        ),
    ],
)
def test_representative_contract_categories_are_concrete(
    loaded_inventory, benchmark_name, subject_terms, scope_category
):
    contract = next(
        item for item in loaded_inventory.contracts if item.benchmark_name == benchmark_name
    )
    normalized_subject = set(contract.subject.lower().replace("-", " ").split())
    assert subject_terms <= normalized_subject
    assert contract.size_or_limit["category"] == scope_category
    assert contract.observable["identity"] not in {
        "material_reference",
        "phase_diagram_reference",
        "status",
        "multi_field_registered_claim",
    }


def test_inspected_contract_units_and_material_scope_are_scientific(loaded_inventory):
    contracts = {
        item.benchmark_name: item for item in loaded_inventory.contracts
    }
    locators = {
        row["benchmark_name"]: row for row in loaded_inventory.locator_inventory
    }

    ni_ps3 = contracts["ni_ps3_honeycomb_antiferromagnet_reference"]
    assert ni_ps3.subject == "NiPS3 honeycomb antiferromagnetic order"
    assert ni_ps3.size_or_limit["category"] == (
        "published_experimental_material_conditions_pending_source_verification"
    )
    assert locators[ni_ps3.benchmark_name]["locator_class"] == "abstract"

    tfim = contracts["transverse_field_ising_chain_critical_point"]
    assert tfim.representation["fields"][0]["units"] == "dimensionless_ratio"

    xxz = contracts["xxz_spin_half_chain_phase_boundaries"]
    xxz_fields = {field["id"]: field for field in xxz.representation["fields"]}
    assert xxz_fields["gapless_interval"]["units"] == "dimensionless_anisotropy"

    aklt = contracts["aklt_spin1_chain_projector_ground_state"]
    aklt_fields = {field["id"]: field for field in aklt.representation["fields"]}
    assert aklt_fields["two_site_projector_eigenvalues"] == {
        "id": "two_site_projector_eigenvalues",
        "type": "list[number]",
        "units": "dimensionless_projector_eigenvalue",
        "convention": "ordered_two_site_projector_spectrum",
    }


def test_provisional_records_are_complete_and_fail_closed(loaded_inventory):
    required = {
        "source_id",
        "registry_selector",
        "canonical_observable_id",
        "evidence_mode",
        "target_locator_strategy",
        "parser_strategy",
        "comparator",
        "unresolved_reason",
    }
    forbidden = {
        "source_sha256",
        "parsed_target",
        "source_excerpt",
        "copied_target",
        "target_observable",
        "target_excerpt",
        "verdict",
        "pass",
        "strict",
        "strict_match",
        "strict_literature_match",
    }
    for record in loaded_inventory.records:
        plain = record.as_plain_data()
        assert required <= set(plain)
        assert not forbidden.intersection(_recursive_keys(plain))
        assert record.record_state == "unresolved"
        assert record.unresolved_reason.strip()
        assert derive_unresolved_status(record) == "unresolved"
        with pytest.raises(EvidenceSchemaError):
            EvidenceRecord(**plain)


def test_sources_are_registry_derived_unique_canonical_identities_covering_every_record(
    loaded_inventory,
):
    sources = loaded_inventory.source_index
    expected_identities = {
        canonical_source_identity(entry["source_url"])
        for entry in LITERATURE_STANDARD_RESULTS
    }
    assert len(expected_identities) == 137
    assert len(sources) == len(expected_identities)
    assert len({source["source_id"] for source in sources}) == len(expected_identities)
    assert len({tuple(source["canonical_identity"].items()) for source in sources}) == len(
        expected_identities
    )
    assert {source["source_id"] for source in sources} == {
        record.source_id for record in loaded_inventory.records
    }
    assert sum(len(source["benchmark_names"]) for source in sources) == 155

    by_url = {
        entry["source_url"]: canonical_source_identity(entry["source_url"])
        for entry in LITERATURE_STANDARD_RESULTS
    }
    assert set(by_url.values()) == expected_identities
    assert canonical_source_identity(
        "https://doi.org/10.1103/PhysRevLett.26.832"
    ) == canonical_source_identity("https://DOI.org/10.1103/physrevlett.26.832")
    assert canonical_source_identity(
        "https://arxiv.org/abs/1409.0193"
    ) == canonical_source_identity("https://arxiv.org/pdf/1409.0193.pdf")

    for doi, expected_benchmarks in (
        (
            "10.1103/PhysRevLett.26.832",
            {
                "eight_vertex_zero_field_exact_solution_status",
                "square_ashkin_teller_exact_critical_line",
            },
        ),
        (
            "10.1103/PhysRevX.1.021002",
            {
                "pyrochlore_anisotropic_exchange_jzz_jpm_reference",
                "yb2ti2o7_pyrochlore_exchange_reference",
            },
        ),
    ):
        identity = canonical_source_identity(f"https://doi.org/{doi}")
        matching = [
            source
            for source in sources
            if (
                f"{source['canonical_identity']['kind']}:"
                f"{source['canonical_identity']['value']}"
            )
            == identity
        ]
        assert len(matching) == 1
        assert set(matching[0]["benchmark_names"]) == expected_benchmarks


def test_corrected_material_primary_source_dois_are_registered(loaded_inventory):
    registry_by_name = {
        entry["name"]: entry["source_url"] for entry in LITERATURE_STANDARD_RESULTS
    }
    assert registry_by_name["barlowite_kagome_material_reference"] == (
        "https://doi.org/10.1103/PhysRevLett.113.227203"
    )
    assert registry_by_name["garnet_gd3ga5o12_spin_liquid_reference"] == (
        "https://doi.org/10.1103/PhysRevLett.80.4570"
    )
    assert registry_by_name["crgete3_honeycomb_ferromagnet_reference"] == (
        "https://doi.org/10.1088/0953-8984/7/1/008"
    )
    identities = {
        source["canonical_identity"]["value"]
        for source in loaded_inventory.source_index
    }
    assert "10.1103/physrevlett.113.227203" in identities
    assert "10.1103/physrevlett.80.4570" in identities
    assert "10.1103/physrevb.90.094426" not in identities
    assert "10.1103/physrevb.57.4986" not in identities
    assert "10.1088/0953-8984/7/1/008" in identities
    assert "10.1209/0295-5075/29/4/008" not in identities


def test_corrected_mismatched_primary_source_identities_are_registered(
    loaded_inventory,
):
    registry_by_name = {
        entry["name"]: entry for entry in LITERATURE_STANDARD_RESULTS
    }
    expected = {
        "dy2ti2o7_spin_ice_entropy_reference": (
            "Ramirez_1999",
            "https://doi.org/10.1038/20619",
        ),
        "simple_cubic_j1_j2_collinear_reference": (
            "Pinettes_Diep_1998",
            "https://doi.org/10.1063/1.367729",
        ),
        "crcl3_honeycomb_heisenberg_reference": (
            "Cable_1961",
            "https://doi.org/10.1016/0022-3697(61)90053-1",
        ),
        "square_fully_frustrated_ising_residual_entropy_reference": (
            "Garel_Maillard_1983",
            "https://doi.org/10.1088/0305-4470/16/10/023",
        ),
        "mn_ps3_honeycomb_antiferromagnet_reference": (
            "Ressouche_et_al_2010",
            "https://doi.org/10.1103/physrevb.82.100408",
        ),
        "pyrochlore_dipolar_spin_ice_pauling_entropy": (
            "Bramwell_Gingras_2001",
            "https://doi.org/10.1126/science.1064761",
        ),
        "cu2oseo3_skyrmion_lattice_reference": (
            "Seki_2012",
            "https://doi.org/10.1126/science.1214143",
        ),
        "haydeeite_ferromagnetic_kagome_reference": (
            "Boldrin_2015",
            "https://doi.org/10.1103/PhysRevB.91.220408",
        ),
    }
    for benchmark_name, (source, source_url) in expected.items():
        assert registry_by_name[benchmark_name]["source"] == source
        assert registry_by_name[benchmark_name]["source_url"] == source_url

    identities = {
        source["canonical_identity"]["value"]
        for source in loaded_inventory.source_index
    }
    corrected = {
        canonical_source_identity(source_url).split(":", 1)[1]
        for _, source_url in expected.values()
    }
    invalid = {
        "10.1038/19242",
        "10.1063/1.367780",
        "10.1063/1.1706360",
        "10.1088/0305-4470/10/10/014",
        "10.1088/0953-8984/10/29/012",
        "10.1126/science.1059820",
        "10.1126/science.1224143",
        "10.1021/ja053891p",
    }
    assert corrected <= identities
    assert identities.isdisjoint(invalid)


def test_task5_corrected_source_identities_are_registered(loaded_inventory):
    registry_by_name = {
        entry["name"]: entry for entry in LITERATURE_STANDARD_RESULTS
    }
    expected = {
        "cri3_honeycomb_ferromagnet_reference": (
            "McGuire_2015",
            "https://doi.org/10.1021/cm504242t",
        ),
        "cu2iro3_honeycomb_kitaev_reference": (
            "Abramchuk_2017",
            "https://doi.org/10.1021/jacs.7b06911",
        ),
        "sawtooth_chain_localized_magnon_flat_band": (
            "Derzhko_Richter_2006",
            "https://doi.org/10.1140/epjb/e2006-00273-y",
        ),
        "diamond_chain_localized_magnon_flat_band": (
            "Derzhko_Richter_2006",
            "https://doi.org/10.1140/epjb/e2006-00273-y",
        ),
        "maple_leaf_lattice_heisenberg_reference": (
            "Farnell_Darradi_Schmidt_Richter_2011",
            "https://doi.org/10.1103/PhysRevB.84.104406",
        ),
        "checkerboard_heisenberg_plaquette_reference": (
            "Fouet_Mambrini_Sindzingre_Lhuillier_2003",
            "https://doi.org/10.1103/PhysRevB.67.054411",
        ),
        "licuvo4_spiral_chain_reference": (
            "Enderle_2005",
            "https://doi.org/10.1209/epl/i2004-10484-x",
        ),
        "zn_barlowite_kagome_qsl_reference": (
            "Guterding_Valenti_Jeschke_2016",
            "https://doi.org/10.1103/PhysRevB.94.125136",
        ),
        "kagome_ising_ferromagnet_exact_tc": (
            "Kano_Naya_1953",
            "https://doi.org/10.1143/ptp/10.2.158",
        ),
        "kagome_ising_antiferromagnet_residual_entropy_reference": (
            "Kano_Naya_1953",
            "https://doi.org/10.1143/ptp/10.2.158",
        ),
        "bcc_j1_j2_heisenberg_collinear_reference": (
            "Mueller_Richter_Hauser_Ihle_2015",
            "https://doi.org/10.1140/epjb/e2015-60113-7",
        ),
        "nacuo2_triangular_heisenberg_material_reference": (
            "Hsieh_et_al_arXiv_1405.6184",
            "https://arxiv.org/abs/1405.6184",
        ),
    }

    for benchmark_name, (source, source_url) in expected.items():
        entry = registry_by_name[benchmark_name]
        assert entry["source"] == source
        assert entry["source_url"] == source_url

    plain_inventory = loaded_inventory.as_plain_data()
    source_index_text = json.dumps(
        plain_inventory["source_index"], sort_keys=True
    ).lower()
    corrected_dois = {
        canonical_source_identity(source_url).split(":", 1)[1]
        for _, source_url in expected.values()
    }
    assert corrected_dois <= {
        source["canonical_identity"]["value"]
        for source in loaded_inventory.source_index
    }
    assert "10.1140/epjb/e2006-00273-y" in source_index_text


def test_task5_invalid_source_identities_are_absent_from_every_inventory_surface(
    loaded_inventory,
):
    invalid_dois = {
        "10.1021/acs.chemmater.5b01006",
        "10.1021/jacs.7b08744",
        "10.1140/epjb/e2006-00267-3",
        "10.1140/epjb/e2009-00307-4",
        "10.1209/epl/i2002-00102-3",
        "10.1209/epl/i2005-10075-2",
        "10.1088/1674-1137/41/3/037105",
        "10.1143/ptp.10.158",
        "10.1002/9780470316517",
        "10.1088/0953-8984/19/14/145259",
    }
    plain_inventory = loaded_inventory.as_plain_data()
    surfaces = {
        "registry": [entry["source_url"] for entry in LITERATURE_STANDARD_RESULTS],
        "source_index": plain_inventory["source_index"],
        "source_provisioning": plain_inventory["source_provisioning"],
        "locator_inventory": plain_inventory["locator_inventory"],
        "records": plain_inventory["records"],
    }
    for surface_name, surface in surfaces.items():
        serialized = json.dumps(surface, sort_keys=True).lower()
        for invalid_doi in invalid_dois:
            assert invalid_doi not in serialized, (surface_name, invalid_doi)


def test_task5_tightened_claims_match_direct_source_scope(loaded_inventory):
    registry_by_name = {
        entry["name"]: entry for entry in LITERATURE_STANDARD_RESULTS
    }
    expected = {
        "cu2iro3_honeycomb_kitaev_reference": (
            "honeycomb_frustrated_iridate_identity",
            {"honeycomb_frustrated_iridate_identity": True},
            "abstract: honeycomb frustrated iridate Cu2IrO3",
        ),
        "maple_leaf_lattice_heisenberg_reference": (
            "ground_state_magnetic_long_range_order",
            {"magnetic_long_range_order": True},
            "abstract: magnetically ordered ground state with drastically reduced sublattice magnetization",
        ),
        "checkerboard_heisenberg_plaquette_reference": (
            "plaquette_long_range_order_and_valence_bond_crystal",
            {
                "plaquette_long_range_order": True,
                "valence_bond_crystal": True,
            },
            "abstract: long-range order in four-spin S=0 plaquettes and a valence-bond crystal",
        ),
        "zn_barlowite_kagome_qsl_reference": (
            "substitution_effective_exchange_model",
            {
                "significantly_reduced_interkagome_exchange": True,
                "two_parameter_heisenberg_hamiltonian": True,
            },
            "abstract: nonmagnetic isoelectronic Zn substitution significantly reduces interkagome exchange and yields a two-parameter Heisenberg Hamiltonian",
        ),
        "bcc_j1_j2_heisenberg_collinear_reference": (
            "large_j2_collinear_order",
            {"large_j2_collinear_order": True},
            "abstract: large-J2 collinear order for ferromagnetic J1 and antiferromagnetic J2",
        ),
            "nacuo2_triangular_heisenberg_material_reference": (
                "material_spin_order_reference",
                {"unconventional_spin_order_reference": True},
                "abstract and neutron-scattering results: unconventional dimensional-crossover spin order in NaCrO2",
        ),
    }
    for benchmark_name, (observable, standard_result, locator) in expected.items():
        entry = registry_by_name[benchmark_name]
        assert entry["observable"] == observable
        assert entry["standard_result"] == standard_result
        assert entry["citation_locator"] == locator
        assert "computable_observables" not in entry["standard_result"]

    bcc = registry_by_name["bcc_j1_j2_heisenberg_collinear_reference"]
    assert bcc["model"] == "bcc_ferromagnetic_j1_antiferromagnetic_j2_heisenberg"
    assert bcc["parameters"] == {
        "j1_sign": "ferromagnetic",
        "j2_sign": "antiferromagnetic",
        "spin": "arbitrary",
    }
    assert "J1 < 0" in bcc["hamiltonian"]
    assert "J2 > 0" in bcc["hamiltonian"]

    legacy = registry_by_name["nacuo2_triangular_heisenberg_material_reference"]
    assert legacy["model"] == "nacro2_triangular_heisenberg"
    assert legacy["parameters"] == {"material": "NaCrO2", "spin": 1.5}
    assert "spin-3/2" in legacy["hamiltonian"]
    physical_payload = {key: value for key, value in legacy.items() if key != "name"}
    assert "NaCuO2" not in json.dumps(physical_payload, sort_keys=True)
    assert "120" not in json.dumps(physical_payload, sort_keys=True)

    contracts = {
        contract.benchmark_name: contract for contract in loaded_inventory.contracts
    }
    for benchmark_name, (_, standard_result, _) in expected.items():
        contract = contracts[benchmark_name]
        assert contract.observable["claim_fields"] == tuple(standard_result)
        assert {
            field["id"] for field in contract.representation["fields"]
        } == set(standard_result)

    legacy_contract = contracts["nacuo2_triangular_heisenberg_material_reference"]
    assert legacy_contract.system == "nacro2_triangular_heisenberg"
    assert legacy_contract.parameter_regime == {"material": "NaCrO2", "spin": 1.5}
    assert "NaCuO2" not in json.dumps(
        legacy_contract.as_plain_data(), sort_keys=True
    )


def test_task5_exact_chain_ising_and_lsm_sources_directly_support_registered_claims(
    loaded_inventory,
):
    registry_by_name = {
        entry["name"]: entry for entry in LITERATURE_STANDARD_RESULTS
    }
    expected_sources = {
        "xxx_spin_half_chain_bethe_ground_state": (
            "Yang_Yang_1966_Part_II",
            "https://doi.org/10.1103/PhysRev.150.327",
        ),
        "one_dimensional_classical_ising_correlation_length": (
            "Taylor_2020",
            "https://arxiv.org/abs/2001.01693",
        ),
        "lieb_schultz_mattis_half_integer_constraint": (
            "Tasaki_2018",
            "https://doi.org/10.1007/s10955-017-1946-0",
        ),
    }
    for benchmark_name, (source, source_url) in expected_sources.items():
        entry = registry_by_name[benchmark_name]
        assert entry["source"] == source
        assert entry["source_url"] == source_url

    xxx = registry_by_name["xxx_spin_half_chain_bethe_ground_state"]
    assert xxx["citation_locator"] == (
        "Eq. (31c): isotropic zero-magnetization ground-state energy per lattice site"
    )

    ising = registry_by_name["one_dimensional_classical_ising_correlation_length"]
    assert ising["citation_locator"] == (
        "Eq. (5) and following sentence: <s_i s_{i+l}> = tanh^l(beta J)"
    )

    lsm = registry_by_name["lieb_schultz_mattis_half_integer_constraint"]
    assert lsm["model"] == "half_odd_integer_u1_spin_chain"
    assert lsm["parameters"] == {
        "spin_per_unit_cell": "half_odd_integer",
        "ground_state": "unique",
        "interaction_range": "short_range",
        "symmetries": ["translation", "U(1)"],
    }
    assert lsm["standard_result"] == {
        "unique_ground_state_implies_gapless_excitations": True
    }
    assert lsm["citation_locator"] == (
        "introduction: half-odd-integer spin with a unique ground state has gapless excitations in the infinite-volume limit"
    )

    contracts = {
        contract.benchmark_name: contract for contract in loaded_inventory.contracts
    }
    lsm_contract = contracts["lieb_schultz_mattis_half_integer_constraint"]
    assert lsm_contract.system == "half_odd_integer_u1_spin_chain"
    assert lsm_contract.as_plain_data()["parameter_regime"] == lsm["parameters"]
    assert lsm_contract.observable["claim_fields"] == (
        "unique_ground_state_implies_gapless_excitations",
    )
    records = {
        record.benchmark_name: record for record in loaded_inventory.records
    }
    assert records["lieb_schultz_mattis_half_integer_constraint"].evidence_mode == (
        "local_source_parse"
    )


def test_corrected_classic_primary_source_dois_are_registered(loaded_inventory):
    registry_by_name = {
        entry["name"]: entry["source_url"] for entry in LITERATURE_STANDARD_RESULTS
    }
    expected = {
        "honeycomb_j1_j2_j3_classical_phase_diagram": (
            "https://arxiv.org/abs/1309.3744"
        ),
        "takhtajan_babujian_spin1_critical_point": (
            "https://arxiv.org/abs/cond-mat/9811353"
        ),
        "uimin_lai_sutherland_spin1_su3_point": (
            "https://doi.org/10.1103/PhysRevB.12.3795"
        ),
        "shastry_sutherland_exact_dimer_product": (
            "https://doi.org/10.1016/0378-4363(81)90838-X"
        ),
        "j1_j2_chain_bkt_transition_reference": (
            "https://arxiv.org/abs/1006.5052"
        ),
        "triangular_ising_ferromagnet_exact_tc": (
            "https://doi.org/10.1143/ptp.5.2.177"
        ),
        "honeycomb_ising_ferromagnet_exact_tc": (
            "https://doi.org/10.1143/ptp.5.2.177"
        ),
    }
    for benchmark_name, source_url in expected.items():
        assert registry_by_name[benchmark_name] == source_url

    identities = {
        source["canonical_identity"]["value"]
        for source in loaded_inventory.source_index
    }
    corrected = {
        canonical_source_identity(source_url).split(":", 1)[1]
        for source_url in expected.values()
    }
    invalid = {
        "10.1016/0304-8853(79)90049-2",
        "10.1016/0370-2693(82)90471-0",
        "10.1016/0375-9601(74)90701-2",
        "10.1016/0375-9601(81)90438-x",
        "10.1016/0375-9601(92)90923-5",
        "10.1016/s0031-8914(50)80099-3",
    }
    assert corrected <= identities
    assert identities.isdisjoint(invalid)

    okamoto_identity = canonical_source_identity(
        expected["j1_j2_chain_bkt_transition_reference"]
    )
    okamoto_source = next(
        source
        for source in loaded_inventory.source_index
        if (
            f"{source['canonical_identity']['kind']}:"
            f"{source['canonical_identity']['value']}"
        )
        == okamoto_identity
    )
    assert set(okamoto_source["benchmark_names"]) == {
        "j1_j2_chain_bkt_transition_reference",
        "j1_j2_chain_okamoto_nomura_critical_point",
    }


def test_fecl3_benchmark_uses_published_helimagnetic_structure(loaded_inventory):
    entry = next(
        item
        for item in LITERATURE_STANDARD_RESULTS
        if item["name"] == "fecl3_honeycomb_antiferromagnet_reference"
    )
    assert entry["source"] == "Cable_1962"
    assert entry["source_url"] == "https://doi.org/10.1103/PhysRev.127.714"
    assert entry["standard_result"]["magnetic_order"] == "helimagnetic_spiral"
    assert entry["standard_result"]["propagation_vector_hexagonal"] == [
        4.0 / 15.0,
        1.0 / 15.0,
        3.0 / 2.0,
    ]
    computable = set(entry["standard_result"]["computable_observables"])
    assert computable == {"spiral_geometry_consistency"}
    assert computable.isdisjoint(
        {
            "gamma_staggered_honeycomb_minimum",
            "two_band_lsw_spectrum",
            "classical_luttinger_tisza_minima",
        }
    )
    assert "competing" in entry["hamiltonian"]
    assert "competing_exchange" in entry["hamiltonian_terms"]

    contract = next(
        item
        for item in loaded_inventory.contracts
        if item.benchmark_name == entry["name"]
    )
    assert contract.observable["claim_fields"] == (
        "magnetic_order",
        "propagation_vector_hexagonal",
    )
    assert contract.observable["identity"] == (
        "helimagnetic_order_and_propagation_vector_in_layered_fecl3"
    )
    fields = {field["id"]: field for field in contract.representation["fields"]}
    assert fields["magnetic_order"] == {
        "id": "magnetic_order",
        "type": "string",
        "units": "not_applicable",
        "convention": "categorical_label",
    }
    assert fields["propagation_vector_hexagonal"] == {
        "id": "propagation_vector_hexagonal",
        "type": "list[number]",
        "units": "reciprocal_lattice_unit",
        "convention": "ordering_wavevector_hexagonal_basis",
    }


def test_fecl3_tasks_remove_neel_projection_and_validate_cable_helix_geometry():
    benchmark_name = "fecl3_honeycomb_antiferromagnet_reference"
    all_tasks = (
        classical_projection_verification_tasks()
        + residual_projection_verification_tasks()
        + pitch_and_ordering_vector_verification_tasks()
    )
    fecl3_tasks = [
        task for task in all_tasks if task["benchmark_name"] == benchmark_name
    ]
    assert [task["computable_observable"] for task in fecl3_tasks] == [
        "spiral_geometry_consistency"
    ]
    task = fecl3_tasks[0]
    assert task["projection_kind"] == "source_vector_geometry_consistency"
    assert task["expected_propagation_vector_hexagonal"] == [
        4.0 / 15.0,
        1.0 / 15.0,
        3.0 / 2.0,
    ]

    geometry = fecl3_cable_helix_geometry(
        hexagonal_in_plane_numerators=(4, 1),
        modulation_denominator=15,
        antiferromagnetic_c_axis=True,
    )
    assert geometry == {
        "magnetic_order": "helimagnetic_spiral",
        "propagation_vector_hexagonal": [4.0 / 15.0, 1.0 / 15.0, 3.0 / 2.0],
        "in_plane_period_lattice_spacings": 15,
        "successive_plane_turn_angle_radians": 2.0 * math.pi / 15.0,
    }


def test_provisioning_has_one_publisher_specific_unacquired_route_per_source(
    loaded_inventory,
):
    routes = loaded_inventory.source_provisioning
    assert len(routes) == len(loaded_inventory.source_index) == 137
    assert {route["source_id"] for route in routes} == {
        source["source_id"] for source in loaded_inventory.source_index
    }
    for route in routes:
        source = next(
            item
            for item in loaded_inventory.source_index
            if item["source_id"] == route["source_id"]
        )
        expected = authoritative_route_for_identity(source["canonical_identity"])
        assert route["authoritative_retrieval_route"] == {
            "kind": expected["kind"],
            "url": expected["url"],
            "artifact_identifier": expected["artifact_identifier"],
            "work_identity_evidence": expected["work_identity_evidence"],
        }
        assert route["access_mode"] == expected["access_mode"]
        assert route["authoritative_retrieval_route"]["kind"] != (
            "doi_content_negotiation"
        )
        assert route["expected_media_type"] in {
            "application/pdf",
            "application/xml",
        }
        assert route["expected_media_type"] == expected["expected_media_type"]
        assert route["redistributability"] == "unresolved"
        assert route["current_availability"] == "not_acquired"
        extension = "xml" if route["expected_media_type"] == "application/xml" else "pdf"
        assert route["local_cache_location"] == (
            f"source-cache/{route['source_id']}/source.{extension}"
        )


def test_locator_inventory_is_structured_target_free_and_complete(loaded_inventory):
    allowed_classes = {
        "equation",
        "table",
        "abstract",
        "body_text",
        "figure_caption",
        "supplemental",
        "metadata_field",
    }
    forbidden = {
        "answer",
        "value",
        "expected_value",
        "parsed_target",
        "source_excerpt",
        "copied_target",
        "verdict",
    }
    for row in loaded_inventory.locator_inventory:
        assert row["locator_class"] in allowed_classes
        assert row["expected_container"]
        assert row["target_representation"]["fields"]
        strategy = row["locator_strategy"]
        assert strategy["source_context_hint"]
        assert len(strategy["search_anchors"]) >= 2
        assert all(anchor.strip() for anchor in strategy["search_anchors"])
        assert strategy["rationale"]
        assert set(strategy["locator_basis"]) == {
            "citation_locator",
            "benchmark_name",
            "observable_semantics",
            "canonical_source_identity",
        }
        assert not forbidden.intersection(_recursive_keys(row))


def test_locator_forecasts_are_source_specific_and_honest(loaded_inventory):
    locators = {
        row["benchmark_name"]: row for row in loaded_inventory.locator_inventory
    }

    phase_diagram = locators["honeycomb_kitaev_gamma_phase_diagram_reference"]
    assert phase_diagram["locator_class"] in {"body_text", "figure_caption"}
    assert "generic spin model for honeycomb iridates" in phase_diagram[
        "locator_strategy"
    ]["source_context_hint"]
    assert "phase diagram" in phase_diagram["locator_strategy"]["search_anchors"]

    qmc = locators["square_spin_half_heisenberg_qmc_energy"]
    assert qmc["expected_container"] != "main_text_or_supplemental_table"
    assert "QMC" in qmc["locator_strategy"]["source_context_hint"]

    material = locators["ni_ps3_honeycomb_antiferromagnet_reference"]
    assert material["locator_class"] in {"abstract", "body_text", "figure_caption"}
    assert "NiPS3" in material["locator_strategy"]["search_anchors"]
    assert "spin waves" in material["locator_strategy"]["search_anchors"]


def test_claim_surfaces_do_not_copy_registry_target_values(loaded_inventory):
    registry_by_name = {
        entry["name"]: entry for entry in LITERATURE_STANDARD_RESULTS
    }
    locator_by_name = {
        row["benchmark_name"]: row for row in loaded_inventory.locator_inventory
    }
    for contract, record in zip(loaded_inventory.contracts, loaded_inventory.records):
        standard_result = registry_by_name[contract.benchmark_name]["standard_result"]
        target_leaves = {
            (type(value).__name__, repr(value))
            for key, target in standard_result.items()
            if key not in {"computable_observables", "tolerance"}
            for value in _recursive_leaves(target)
        }
        locator = locator_by_name[contract.benchmark_name]
        identity_surfaces = (
            contract.observable,
            contract.representation,
            contract.conditions,
            record.target_locator_strategy,
            record.parser_strategy,
            record.comparator,
            locator["target_representation"],
        )
        identity_leaves = {
            (type(value).__name__, repr(value))
            for surface in identity_surfaces
            for value in _recursive_leaves(surface)
        }
        assert target_leaves.isdisjoint(identity_leaves), contract.benchmark_name


def test_selectors_resolve_only_registered_claim_operands_and_ignore_record_metadata(
    loaded_inventory,
):
    registry_by_name = {
        entry["name"]: entry for entry in LITERATURE_STANDARD_RESULTS
    }
    for record in loaded_inventory.records:
        registry_entry = registry_by_name[record.benchmark_name]
        selected = resolve_registry_selector(registry_entry, record.registry_selector)
        assert selected
        assert "computable_observables" not in selected
        assert "tolerance" not in selected

        plain = record.as_plain_data()
        for key in set(plain) - {"registry_selector"}:
            mutated = copy.deepcopy(plain)
            mutated[key] = _different_value(mutated[key])
            assert (
                resolve_registry_selector(registry_entry, mutated["registry_selector"])
                == selected
            )


def test_generated_artifact_surfaces_do_not_share_mutable_nested_objects():
    data = build_inventory_data(LITERATURE_STANDARD_RESULTS)
    contract_fields = data["contracts"][0]["representation"]["fields"]
    record = data["records"][0]
    locator = data["locator_inventory"][0]

    assert contract_fields is not record["parser_strategy"]["output_fields"]
    assert record["parser_strategy"]["output_fields"] is not record["comparator"]["fields"]
    assert record["target_locator_strategy"] is not locator["locator_strategy"]

    original_contract_units = contract_fields[0]["units"]
    original_comparator_units = record["comparator"]["fields"][0]["units"]
    original_locator_units = locator["target_representation"]["fields"][0]["units"]
    record["parser_strategy"]["output_fields"][0]["units"] = "mutated"

    assert contract_fields[0]["units"] == original_contract_units
    assert record["comparator"]["fields"][0]["units"] == original_comparator_units
    assert locator["target_representation"]["fields"][0]["units"] == original_locator_units


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda c: c.update(subject="generic"), "subject"),
        (lambda c: c.update(size_or_limit={"kind": "generic"}), "size or limit"),
        (lambda c: c.update(units="generic"), "top-level units"),
        (
            lambda c: c["conditions"].update(physical_regime="generic"),
            "physical regime",
        ),
        (
            lambda c: c["conditions"].update(source_claim_scope="generic"),
            "source claim scope",
        ),
        (
            lambda c: c["conditions"].update(backend_scope="generic"),
            "backend scope",
        ),
    ],
)
def test_inventory_rejects_corrupted_canonical_identity_dimensions(
    loaded_inventory, mutation, message
):
    data = mutable_inventory(loaded_inventory)
    mutation(data["contracts"][0])
    with pytest.raises(InventoryError, match=message):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda data: data["contracts"].pop(), "missing canonical contracts"),
        (
            lambda data: data["contracts"].append(copy.deepcopy(data["contracts"][0])),
            "duplicate canonical contract names",
        ),
        (
            lambda data: data["contracts"][0].update(benchmark_name="orphan_contract"),
            "orphan canonical contracts",
        ),
        (
            lambda data: data["records"][0].update(benchmark_name="orphan_record"),
            "missing provisional records",
        ),
    ],
)
def test_inventory_rejects_missing_orphan_and_duplicate_names(
    loaded_inventory, mutation, message
):
    data = mutable_inventory(loaded_inventory)
    mutation(data)
    with pytest.raises(InventoryError, match=message):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


def test_inventory_rejects_generic_contract(loaded_inventory):
    data = mutable_inventory(loaded_inventory)
    data["contracts"][0]["observable"] = {
        "identity": "material_reference",
        "claim_fields": ["material_reference"],
    }
    with pytest.raises((InventoryError, EvidenceSchemaError), match="generic"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


@pytest.mark.parametrize(
    "forbidden_key",
    ["parsed_target", "source_excerpt", "copied_target", "verdict", "pass"],
)
def test_inventory_rejects_forbidden_target_and_verdict_fields_recursively(
    loaded_inventory, forbidden_key
):
    data = mutable_inventory(loaded_inventory)
    data["records"][0]["parser_strategy"]["nested"] = {forbidden_key: "leak"}
    with pytest.raises((InventoryError, EvidenceSchemaError), match="forbidden"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


@pytest.mark.parametrize(
    ("collection", "nested_key", "forbidden_key"),
    [
        ("contracts", "conditions", "verdict"),
        ("source_index", "canonical_identity", "source_excerpt"),
        (
            "source_provisioning",
            "authoritative_retrieval_route",
            "copied_target",
        ),
    ],
)
def test_all_inventory_artifacts_reject_recursive_evidence_leakage(
    loaded_inventory, collection, nested_key, forbidden_key
):
    data = mutable_inventory(loaded_inventory)
    data[collection][0][nested_key][forbidden_key] = "leak"
    with pytest.raises(InventoryError, match="forbidden"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


@pytest.mark.parametrize("source_hash", ["0" * 64, "a" * 64])
def test_provisional_record_rejects_any_source_hash(source_hash, loaded_inventory):
    plain = loaded_inventory.records[0].as_plain_data()
    plain["source_sha256"] = source_hash
    with pytest.raises(EvidenceSchemaError, match="source_sha256"):
        ProvisionalEvidenceRecord(**plain)


def test_inventory_rejects_bad_source_count_or_identity(loaded_inventory):
    data = mutable_inventory(loaded_inventory)
    data["source_index"].pop()
    with pytest.raises(InventoryError, match="canonical source identities exactly"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)

    data = mutable_inventory(loaded_inventory)
    data["source_index"][0]["canonical_identity"]["value"] = "10.0/fake"
    with pytest.raises(InventoryError, match="canonical source identity"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)

    data = mutable_inventory(loaded_inventory)
    data["records"][0]["source_id"] = data["records"][1]["source_id"]
    with pytest.raises(InventoryError, match="record source identity mismatch"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


def test_provisional_record_requires_nonempty_unresolved_reason(loaded_inventory):
    plain = loaded_inventory.records[0].as_plain_data()
    plain["unresolved_reason"] = " "
    with pytest.raises(EvidenceSchemaError, match="unresolved_reason"):
        ProvisionalEvidenceRecord(**plain)


def test_inventory_rejects_locator_answer_leakage(loaded_inventory):
    data = mutable_inventory(loaded_inventory)
    data["locator_inventory"][0]["target_representation"]["answer"] = 1
    with pytest.raises(InventoryError, match="forbidden"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


def test_inventory_rejects_locator_source_or_empty_strategy(loaded_inventory):
    data = mutable_inventory(loaded_inventory)
    data["locator_inventory"][0]["source_id"] = data["source_index"][1]["source_id"]
    with pytest.raises(InventoryError, match="locator source identity mismatch"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)

    data = mutable_inventory(loaded_inventory)
    data["locator_inventory"][0]["locator_strategy"] = {}
    data["records"][0]["target_locator_strategy"] = {}
    with pytest.raises(InventoryError, match="locator strategy"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


def test_inventory_rejects_provisioning_mismatch(loaded_inventory):
    data = mutable_inventory(loaded_inventory)
    data["source_provisioning"][0]["source_id"] = "orphan_source"
    with pytest.raises(InventoryError, match="provisioning"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)

    data = mutable_inventory(loaded_inventory)
    route = data["source_provisioning"][0]
    current_kind = route["authoritative_retrieval_route"]["kind"]
    route["authoritative_retrieval_route"]["kind"] = current_kind + "_mutated"
    with pytest.raises(InventoryError, match="retrieval route"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)

    data = mutable_inventory(loaded_inventory)
    data["source_provisioning"][0]["current_availability"] = "unavailable"
    with pytest.raises(InventoryError, match="not_acquired"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


@pytest.mark.parametrize(
    "cache_location",
    [
        "source-cache/../../outside/source.pdf",
        "source-cache/",
        "source-cache//etc/passwd",
        "/source-cache/source.pdf",
        "source-cache/./source.pdf",
    ],
)
def test_inventory_rejects_unsafe_provisioning_cache_paths(
    loaded_inventory, cache_location
):
    data = mutable_inventory(loaded_inventory)
    data["source_provisioning"][0]["local_cache_location"] = cache_location
    with pytest.raises(InventoryError, match="local cache location"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


def test_inventory_rejects_duplicate_provisioning_cache_paths(loaded_inventory):
    data = mutable_inventory(loaded_inventory)
    data["source_provisioning"][1]["local_cache_location"] = data[
        "source_provisioning"
    ][0]["local_cache_location"]
    with pytest.raises(InventoryError, match="duplicate local cache location"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


def test_inventory_rejects_bad_canonical_source_url(loaded_inventory):
    data = mutable_inventory(loaded_inventory)
    data["source_index"][0]["canonical_url"] = "https://example.invalid/source"
    with pytest.raises(InventoryError, match="canonical URL"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


@pytest.mark.parametrize("strategy_name", ["parser_strategy", "comparator"])
def test_inventory_rejects_empty_parser_or_comparator_strategy(
    loaded_inventory, strategy_name
):
    data = mutable_inventory(loaded_inventory)
    data["records"][0][strategy_name] = {}
    with pytest.raises(InventoryError, match=strategy_name.replace("_", " ")):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


def test_loader_rejects_record_filename_mismatch(tmp_path):
    copied_root = tmp_path / "literature-evidence"
    shutil.copytree(INVENTORY_ROOT, copied_root)
    record_path = next((copied_root / "records").glob("*.json"))
    record_path.rename(record_path.with_name("wrong-record-filename.json"))
    with pytest.raises(InventoryError, match="record filenames"):
        load_and_validate_inventory(copied_root)


@pytest.mark.parametrize(
    "malformation", ["duplicate_key", "non_finite", "overflowing_float"]
)
def test_loader_rejects_ambiguous_or_nonstandard_json(tmp_path, malformation):
    copied_root = tmp_path / "literature-evidence"
    shutil.copytree(INVENTORY_ROOT, copied_root)
    record_path = next((copied_root / "records").glob("*.json"))
    raw = record_path.read_text(encoding="utf-8")
    if malformation == "duplicate_key":
        raw = raw.replace(
            '"benchmark_name":',
            '"benchmark_name": "duplicate",\n  "benchmark_name":',
            1,
        )
    elif malformation == "non_finite":
        raw = raw.replace('"schema_version": 1', '"schema_version": NaN', 1)
    else:
        raw = raw.replace('"schema_version": 1', '"schema_version": 1e999', 1)
    record_path.write_text(raw, encoding="utf-8")
    with pytest.raises(InventoryError, match="duplicate JSON key|non-finite JSON"):
        load_and_validate_inventory(copied_root)


def test_canonical_contract_artifact_is_independent_of_mutated_runtime_records(
    loaded_inventory,
):
    contract_path = INVENTORY_ROOT / "canonical-observables.json"
    before = contract_path.read_bytes()
    records = [record.as_plain_data() for record in loaded_inventory.records]
    records[0]["unresolved_reason"] = "mutated runtime metadata"
    records[0]["parser_strategy"] = {"kind": "manual_future_parse"}

    assert contract_path.read_bytes() == before


def test_canonical_contracts_are_not_regenerated_from_registry_observable_labels():
    baseline = build_inventory_data(LITERATURE_STANDARD_RESULTS)["contracts"]
    mutated_registry = copy.deepcopy(LITERATURE_STANDARD_RESULTS)
    for entry in mutated_registry:
        entry["observable"] = "generic_registry_label_that_must_not_define_contract"

    rebuilt = build_inventory_data(mutated_registry)["contracts"]

    assert rebuilt == baseline


def test_alternate_root_generation_reads_that_roots_canonical_contracts(tmp_path):
    copied_root = tmp_path / "literature-evidence"
    shutil.copytree(INVENTORY_ROOT, copied_root)
    contract_path = copied_root / "canonical-observables.json"
    document = json.loads(contract_path.read_text(encoding="utf-8"))
    marker = "alternate_root_exact_projector_and_vbs_observable"
    document["canonical_observables"][0]["observable"]["identity"] = marker
    contract_path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    generated = build_inventory_data(
        LITERATURE_STANDARD_RESULTS, inventory_root=copied_root
    )

    assert generated["contracts"][0]["observable"]["identity"] == marker


def _recursive_keys(value):
    if isinstance(value, dict):
        keys = set(value)
        for item in value.values():
            keys.update(_recursive_keys(item))
        return keys
    if isinstance(value, (list, tuple)):
        keys = set()
        for item in value:
            keys.update(_recursive_keys(item))
        return keys
    return set()


def _different_value(value):
    if isinstance(value, str):
        return value + "_mutated"
    if isinstance(value, dict):
        return {"mutated": "metadata"}
    if isinstance(value, list):
        return ["mutated"]
    return None


def _recursive_leaves(value):
    if isinstance(value, dict):
        return [leaf for item in value.values() for leaf in _recursive_leaves(item)]
    if isinstance(value, (list, tuple)):
        return [leaf for item in value for leaf in _recursive_leaves(item)]
    return [value]


def _recursive_strings(value):
    if isinstance(value, dict):
        return [
            string
            for key, item in value.items()
            for string in (str(key), *_recursive_strings(item))
        ]
    if isinstance(value, (list, tuple)):
        return [
            string
            for item in value
            for string in _recursive_strings(item)
        ]
    if isinstance(value, str):
        return [value]
    return []


def _recursive_numeric_leaves(value, path=()):
    if isinstance(value, dict):
        return [
            numeric
            for key, item in value.items()
            for numeric in _recursive_numeric_leaves(item, (*path, key))
        ]
    if isinstance(value, (list, tuple)):
        return [
            numeric
            for index, item in enumerate(value)
            for numeric in _recursive_numeric_leaves(item, (*path, index))
        ]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [(path, value)]
    return []


def _matching_numeric_target_leaves(
    numeric_surface,
    target,
    *,
    benchmark_name,
    selected_field,
):
    if isinstance(target, bool) or not isinstance(target, (int, float)):
        return []
    matches = [
        (path, value)
        for path, value in numeric_surface
        if type(value) is type(target) and value == target
    ]
    return [
        (path, value)
        for path, value in matches
        if (
            benchmark_name,
            selected_field,
            path,
            type(value),
            value,
        )
        not in AUDITED_CANONICAL_NUMERIC_TARGET_INPUTS
    ]


def _assert_tb_input_surface_is_result_neutral(input_surface):
    serialized = json.dumps(input_surface, sort_keys=True).lower()
    result_bearing_tokens = tuple(
        token
        for token in ("integrable", "true", "false", "result")
        if token in serialized
    )
    assert result_bearing_tokens == (), (
        "Takhtajan-Babujian input surface predeclares selected result via "
        f"{result_bearing_tokens}: {input_surface}"
    )


def _bounded_target_token_pattern(target):
    if isinstance(target, bool) or target is None:
        return None
    if isinstance(target, (int, float)):
        numeric = float(target)
        if numeric.is_integer():
            return None
        token = format(target, ".15g").lower()
        return rf"(?<![0-9a-z_.]){re.escape(token)}(?![0-9a-z_.])"
    if isinstance(target, str) and len(target) >= 4:
        token = target.lower()
        return rf"(?<![0-9a-z_]){re.escape(token)}(?![0-9a-z_])"
    return None


def _literal_registry_claim_fields():
    registry_path = (
        PROJECT_ROOT / "scripts" / "validation" / "literature_spin_model_benchmarks.py"
    )
    tree = ast.parse(registry_path.read_text(encoding="utf-8"))
    list_nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name)
            and target.id == "LITERATURE_STANDARD_RESULTS"
            for target in node.targets
        ):
            list_nodes.append(node.value)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            function = node.value.func
            if (
                isinstance(function, ast.Attribute)
                and isinstance(function.value, ast.Name)
                and function.value.id == "LITERATURE_STANDARD_RESULTS"
                and function.attr == "extend"
            ):
                list_nodes.append(node.value.args[0])

    result = {}
    for list_node in list_nodes:
        for entry_node in list_node.elts:
            entry = {
                key.value: value
                for key, value in zip(entry_node.keys, entry_node.values)
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
            name = ast.literal_eval(entry["name"])
            fields = tuple(
                key.value
                for key in entry["standard_result"].keys
                if isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and key.value not in {"tolerance", "computable_observables"}
            )
            result[name] = fields
    return result
