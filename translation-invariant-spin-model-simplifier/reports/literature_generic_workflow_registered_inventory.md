# Complete Literature-to-Generic-Workflow Inventory

Paper-side target values are never computation inputs. The registry is used here only for source identity, model/observable metadata, and backend-gap classification. A row is counted as computed only when an answer-free model case runs through the generic product workflow.

| Layer | Count |
|---|---:|
| Registered claims | 155 |
| Canonical literature sources | 137 |
| Distinct registered models | 138 |
| Answer-free model inputs landed | 29 |
| Answer-free model inputs not landed | 126 |
| Claims extracted for post-computation comparison | 27 |
| Normalized | 29 |
| Simplified | 29 |
| Computed | 27 |
| Convergence satisfied | 15 |
| Convergence not applicable to exact finite/algebraic result | 12 |
| Inconclusive | 2 |
| Independent oracle verified | 0 |
| Matched to literature | 27 |
| Explicitly unsupported after model landing | 0 |
| Needs model landing/review | 126 |

## Remaining reusable backend gaps

| Registry backend family | Not-landed claims |
|---|---:|
| anisotropic_exchange | 11 |
| ed_or_dmrg | 10 |
| classical_glt_or_spin_wave | 8 |
| dmrg_or_ed | 7 |
| glt | 6 |
| ed_or_experiment | 5 |
| qmc | 4 |
| anisotropic_exchange_or_experiment | 3 |
| classical_glt_or_experiment | 3 |
| mc_or_rg | 3 |
| transfer_matrix | 3 |
| analytic | 2 |
| classical_mc_or_experiment | 2 |
| diagnostic | 2 |
| dmrg | 2 |
| dmrg_or_large_ed | 2 |
| dmrg_or_vmc | 2 |
| ed | 2 |
| ed_or_classical | 2 |
| experiment | 2 |
| experiment_or_ladder_model | 2 |
| kitaev_majorana | 2 |
| magnon_ed | 2 |
| mc_or_experiment | 2 |
| neutron_scattering_and_spin_wave | 2 |
| qmc_or_large_ed | 2 |
| vertex_model | 2 |
| analytic_magnon | 1 |
| anisotropic_exchange_or_classical_glt | 1 |
| bethe_ansatz | 1 |
| bethe_or_ed | 1 |
| classical_mc_and_thermodynamics | 1 |
| classical_minimization | 1 |
| classical_minimization_or_mc | 1 |
| classical_minimization_or_spin_wave | 1 |
| dmrg_or_experiment | 1 |
| dmrg_or_many_body | 1 |
| experiment_or_ed | 1 |
| field_theory_or_dmrg | 1 |
| first_principles_exchange_mapping | 1 |
| free_fermion_or_ed | 1 |
| gauge_theory_or_qmc | 1 |
| glt_or_ed | 1 |
| glt_or_lswt | 1 |
| long_range_ed | 1 |
| many_body | 1 |
| many_body_or_classical | 1 |
| many_body_or_experiment | 1 |
| many_body_thermodynamics | 1 |
| mc_or_series | 1 |
| nested_bethe_ansatz | 1 |
| neutron_scattering_reference | 1 |
| peps_or_ed_or_dmrg | 1 |
| qmc_or_ed | 1 |
| qmc_or_lswt | 1 |
| single_cluster_exact_diagonalization | 1 |
| specific_heat_and_structural_experiment | 1 |
| spin_wave_1_over_s | 1 |

## Claim status

| Claim | Canonical source | Model | Observable | Required backend | Model input | Normalize | Simplify | Analysis | Convergence | Oracle | Literature match | Blocker |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| aklt_spin1_chain_projector_ground_state | doi:10.1103/physrevlett.59.799 | spin_1_bilinear_biquadratic_chain | local_spectrum | ed_or_analytic | answer_free_ready | completed | completed | completed | not_applicable | not_connected | matched |  |
| alpha_rucl3_kitaev_gamma_zigzag_reference | doi:10.1103/physrevb.93.214431 | alpha_rucl3_effective_spin_model | zigzag_order_reference | anisotropic_exchange | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| azurite_diamond_chain_plateau_reference | doi:10.1103/physrevlett.100.117202 | azurite_distorted_diamond_chain | magnetization_plateau | ed_or_experiment | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| ba2cugeo7_dm_spiral_reference | doi:10.1103/physrevb.57.2968 | ba2cugeo7_dzyaloshinskii_moriya | classical_spiral_pitch | classical_minimization_or_spin_wave | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| ba3cosb2o9_triangular_plateau_reference | doi:10.1103/physrevlett.108.057205 | ba3cosb2o9_triangular_heisenberg | magnetization_plateau | experiment_or_ed | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| ba3irti2o9_honeycomb_kitaev_reference | doi:10.1103/physrevb.86.140405 | ba3irti2o9_site_diluted_triangular_jeff_half | triangular_spin_liquid_candidate | experiment | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| barlowite_kagome_material_reference | doi:10.1103/physrevlett.113.227203 | barlowite_kagome_interlayer_coupled | material_model_reference | ed_or_experiment | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| bcc_j1_j2_heisenberg_collinear_reference | doi:10.1140/epjb/e2015-60113-7 | bcc_ferromagnetic_j1_antiferromagnetic_j2_heisenberg | large_j2_collinear_order | many_body_thermodynamics | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| beta_li2iro3_spiral_kitaev_gamma_reference | doi:10.1103/physrevb.90.205116 | beta_li2iro3_spiral_order | spiral_order_reference | anisotropic_exchange | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| bilinear_biquadratic_spin1_chain_aklt_angle | doi:10.1103/physrevlett.59.799 | spin_1_bilinear_biquadratic_chain | special_angle | analytic | answer_free_ready | completed | completed | completed | satisfied | not_connected | matched |  |
| blume_capel_spin1_zero_temperature_level_crossing | arxiv:1204.5027 | spin_1_blume_capel | zero_temperature_level_crossing | analytic | answer_free_ready | completed | completed | completed | satisfied | not_connected | matched |  |
| bpcb_spin_ladder_field_induced_order_reference | doi:10.1103/physrevb.79.020408 | bpcb_spin_ladder | field_induced_order | experiment_or_ladder_model | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| breathing_kagome_heisenberg_reference | doi:10.1103/physrevb.96.205124 | breathing_kagome_heisenberg | phase_reference | ed_or_dmrg | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| ca10cr7o28_bilayer_breathing_kagome_reference | doi:10.1038/nphys3826 | ca10cr7o28_bilayer_breathing_kagome | material_exchange_model | classical_glt_or_spin_wave | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| cacu2o3_spin_ladder_reference | doi:10.1103/physrevb.63.144418 | cacu2o3_spin_ladder | material_model_reference | experiment_or_ladder_model | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| checkerboard_heisenberg_afm_planar_pyrochlore_reference | arxiv:cond-mat/0108070 | checkerboard_heisenberg_antiferromagnet | ground_state_constraint | classical_glt_or_ed | answer_free_ready | completed | completed | completed | not_applicable | not_connected | matched |  |
| checkerboard_heisenberg_plaquette_reference | doi:10.1103/physrevb.67.054411 | checkerboard_heisenberg | plaquette_long_range_order_and_valence_bond_crystal | ed_or_dmrg | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| clinoatacamite_distorted_kagome_reference | arxiv:2601.21024 | clinoatacamite_distorted_kagome | material_model_reference | classical_glt_or_experiment | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| crcl3_honeycomb_heisenberg_reference | doi:10.1016/0022-3697(61)90053-1 | crcl3_honeycomb_heisenberg | classical_order | classical_glt_or_spin_wave | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| crgete3_honeycomb_ferromagnet_reference | doi:10.1088/0953-8984/7/1/008 | crgete3_honeycomb_ferromagnet | classical_order | classical_glt_or_spin_wave | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| cri3_honeycomb_ferromagnet_reference | doi:10.1021/cm504242t | cri3_honeycomb_ferromagnet | classical_order | classical_glt_or_spin_wave | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| cs2cucl4_anisotropic_triangular_spiral_reference | doi:10.1103/physrevb.68.134424 | cs2cucl4_anisotropic_triangular | spiral_order_reference | glt_or_lswt | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| cu2iro3_honeycomb_kitaev_reference | doi:10.1021/jacs.7b06911 | cu2iro3_honeycomb_kitaev | honeycomb_frustrated_iridate_identity | anisotropic_exchange_or_experiment | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| cu2oseo3_skyrmion_lattice_reference | doi:10.1126/science.1214143 | cu2oseo3_chiral_ferrimagnet | skyrmion_lattice_phase | classical_minimization_or_mc | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| cubic_ising_critical_temperature_reference | arxiv:cond-mat/9509016 | classical_cubic_ising | critical_temperature | mc_or_series | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| diamond_chain_localized_magnon_flat_band | doi:10.1140/epjb/e2006-00273-y | diamond_chain_heisenberg | localized_magnon | magnon_ed | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| diamond_j1_j2_spiral_surface_reference | arxiv:cond-mat/0612001 | diamond_j1_j2_heisenberg | spiral_surface | glt | answer_free_ready | completed | completed | completed | satisfied | not_connected | matched |  |
| dy2ti2o7_spin_ice_entropy_reference | doi:10.1038/20619 | dy2ti2o7_spin_ice | residual_entropy | mc_or_experiment | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| edwardsite_kagome_antiferromagnet_reference | arxiv:1305.2477 | edwardsite_spin_half_deformed_kagome_antiferromagnet | hydrated_spin_half_deformed_kagome_reference | experiment | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| eight_vertex_zero_field_exact_solution_status | doi:10.1103/physrevlett.26.832 | eight_vertex_model | exact_solution_status | vertex_model | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| er2ti2o7_xy_pyrochlore_order_by_disorder_reference | arxiv:1204.1320 | xy_pyrochlore_antiferromagnet | selected_order | anisotropic_exchange | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| fcc_j1_j2_heisenberg_type_order_reference | arxiv:2007.00376 | fcc_j1_j2_heisenberg | ordering_type | glt | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| fe8_molecular_spin_tunneling_reference | doi:10.1126/science.284.5411.133 | fe8_single_molecule_magnet | quantum_tunneling_reference | single_cluster_exact_diagonalization | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| fe_ps3_honeycomb_ising_reference | arxiv:2005.12031 | feps3_honeycomb_ising | ising_like_order | classical_glt_or_experiment | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| fecl3_honeycomb_antiferromagnet_reference | doi:10.1103/physrev.127.714 | fecl3_honeycomb_antiferromagnet | classical_order | classical_glt_or_spin_wave | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| gadolinium_gallium_garnet_hyperkagome_reference | doi:10.1103/physrevlett.73.2500 | gadolinium_gallium_garnet_exchange_dipolar | strong_geometric_frustration_in_ggg | classical_mc_and_thermodynamics | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| gamma_li2iro3_3d_kitaev_reference | doi:10.1103/physrevlett.113.197201 | gamma_li2iro3_3d_kitaev_gamma | spiral_order_reference | anisotropic_exchange_or_classical_glt | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| garnet_gd3ga5o12_spin_liquid_reference | doi:10.1103/physrevlett.80.4570 | gd3ga5o12_garnet | low_temperature_correlations | classical_mc_or_experiment | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| garnet_gd3te2li3o12_hyperkagome_reference | doi:10.1103/physrevb.87.174421 | gd3te2li3o12_hyperkagome_garnet | frustrated_garnet_with_first_order_long_range_order | specific_heat_and_structural_experiment | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| gaudin_yang_spin_half_fermion_bethe_reference | doi:10.1103/physrevlett.19.1312 | gaudin_yang_fermion_gas | exact_solution_status | nested_bethe_ansatz | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| h3liir2o6_kitaev_spin_liquid_candidate_reference | doi:10.1038/nature25482 | h3liir2o6_honeycomb_kitaev | spin_liquid_candidate_reference | anisotropic_exchange_or_experiment | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| haldane_shastry_chain_exact_ground_state | doi:10.1103/physrevlett.60.635 | haldane_shastry_chain | exact_ground_state | long_range_ed | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| haldane_spin1_chain_gap_reference | doi:10.1103/physrevb.48.3844 | spin_1_heisenberg_chain | haldane_gap | dmrg_or_large_ed | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| haydeeite_ferromagnetic_kagome_reference | doi:10.1103/physrevb.91.220408 | haydeeite_kagome_ferromagnet | classical_ground_state | classical_glt_or_experiment | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| herbertsmithite_kagome_qsl_reference | doi:10.1103/physrevlett.98.107204 | herbertsmithite_kagome_heisenberg | material_qsl_reference | dmrg_or_experiment | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| ho2ti2o7_spin_ice_neutron_reference | doi:10.1103/physrevlett.87.047205 | ho2ti2o7_spin_ice | neutron_scattering_reference | mc_or_experiment | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| honeycomb_haldane_kane_mele_hubbard_spin_model_reference | doi:10.1103/physrevb.82.075106 | kane_mele_hubbard_strong_coupling | strong_coupling_reference | anisotropic_exchange | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| honeycomb_ising_ferromagnet_exact_tc | doi:10.1143/ptp/5.2.177 | classical_honeycomb_ising | critical_temperature | transfer_matrix | answer_free_ready | completed | completed | completed | satisfied | not_connected | matched |  |
| honeycomb_j1_j2_j3_classical_phase_diagram | arxiv:1309.3744 | honeycomb_j1_j2_j3_heisenberg | phase_diagram | glt | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| honeycomb_j1_j2_kitaev_material_na2iro3_reference | arxiv:1209.5100 | na2iro3_honeycomb_kitaev_heisenberg | material_model_reference | anisotropic_exchange | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| honeycomb_j1_j2_spiral_ring_reference | arxiv:1004.1119 | honeycomb_j1_j2_heisenberg | spiral_ring | glt | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| honeycomb_kitaev_gamma_phase_diagram_reference | doi:10.1103/physrevlett.112.077204 | honeycomb_kitaev_gamma | phase_diagram | ed_or_classical | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| honeycomb_kitaev_heisenberg_four_sublattice_phases | arxiv:1209.5100 | honeycomb_kitaev_heisenberg | phase_diagram | ed_or_classical | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| honeycomb_spin_half_j1_j2_quantum_phase_reference | doi:10.1103/physrevb.88.165138 | spin_1_2_honeycomb_j1_j2_heisenberg | phase_reference | ed_or_dmrg | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| hyperkagome_heisenberg_spin_liquid_reference | doi:10.1103/physrevlett.101.197202 | hyperkagome_heisenberg | spin_liquid_candidate | many_body_or_classical | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| j1_j2_chain_bkt_transition_reference | arxiv:1006.5052 | spin_1_2_j1_j2_chain | dimerization_transition | dmrg_or_ed | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| j1_j2_chain_okamoto_nomura_critical_point | arxiv:1006.5052 | spin_1_2_j1_j2_chain | dimerization_transition | ed_or_dmrg | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| j1_j2_honeycomb_neel_spin_liquid_transition_reference | doi:10.1103/physrevb.88.165138 | spin_1_2_honeycomb_j1_j2_heisenberg | quantum_phase_window | dmrg_or_ed | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| j1_j2_j3_square_quantum_phase_reference | doi:10.1103/physrevb.109.235116 | spin_1_2_square_j1_j2_j3_heisenberg | phase_reference | peps_or_ed_or_dmrg | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| j1_j2_square_dqcp_columnar_vbs_reference | doi:10.1103/physrevlett.113.027201 | square_j1_j2_vbs | vbs_reference | dmrg_or_vmc | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| j1_j2_square_spin_half_neel_collinear_transition_reference | arxiv:1409.0193 | spin_1_2_square_j1_j2_heisenberg | quantum_phase_window | many_body | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| j1_j2_triangular_spin_liquid_window_reference | doi:10.1103/physrevb.92.140403 | spin_1_2_triangular_j1_j2_heisenberg | quantum_phase_window | dmrg_or_ed | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| jarosite_kagome_dzyaloshinskii_moriya_reference | doi:10.1103/physrevlett.96.247201 | jarosite_kagome_dm | classical_order | classical_glt_or_spin_wave | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| kagome_chiral_spin_liquid_j1_j2_jchi_reference | doi:10.1038/ncomms6137 | kagome_heisenberg_chiral_j1_j2_jchi | chiral_spin_liquid_phase | dmrg_or_ed | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| kagome_dzyaloshinskii_moriya_critical_reference | doi:10.1103/physrevb.78.140405 | spin_1_2_kagome_dm_heisenberg | quantum_critical_ratio | ed_or_dmrg | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| kagome_heisenberg_dmrg_spin_liquid_yan_reference | arxiv:1205.4858 | spin_1_2_kagome_heisenberg_afm | ground_state_energy_and_gap | dmrg_or_large_ed | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| kagome_heisenberg_topological_entanglement_reference | doi:10.1103/physrevlett.109.067201 | spin_1_2_kagome_heisenberg_afm | topological_entanglement_entropy | dmrg | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| kagome_ising_antiferromagnet_residual_entropy_reference | doi:10.1143/ptp/10.2.158 | classical_kagome_ising_antiferromagnet | residual_entropy | transfer_matrix | answer_free_ready | completed | completed | inconclusive | not_demonstrated | not_connected | inconclusive | finite periodic clusters do not yet certify the thermodynamic-limit entropy |
| kagome_ising_ferromagnet_exact_tc | doi:10.1143/ptp/10.2.158 | classical_kagome_ising | critical_temperature | transfer_matrix | answer_free_ready | completed | completed | completed | satisfied | not_connected | matched |  |
| kagome_j1_j2_heisenberg_phase_diagram_reference | doi:10.1103/physrevb.91.104418 | spin_1_2_kagome_j1_j2_heisenberg | phase_diagram | dmrg_or_ed | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| kagome_one_third_magnetization_plateau_reference | doi:10.1038/ncomms3287 | kagome_heisenberg_high_field | magnetization_plateau | ed_or_dmrg | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| kagome_spin_half_heisenberg_energy_reference | arxiv:1205.4858 | spin_1_2_kagome_heisenberg | ground_state_energy | dmrg | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| kapellasite_kagome_j1_jd_reference | doi:10.1103/physrevlett.109.037208 | kapellasite_kagome_j1_jd | material_exchange_reference | glt_or_ed | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| kitaev_honeycomb_abelian_nonabelian_field_gap_reference | doi:10.1016/j.aop.2005.10.005 | kitaev_honeycomb_field | field_induced_gap | kitaev_majorana | answer_free_ready | completed | completed | completed | satisfied | not_connected | matched |  |
| kitaev_honeycomb_exact_spin_liquid_limit | doi:10.1016/j.aop.2005.10.005 | spin_1_2_kitaev_honeycomb | exact_solution_status | kitaev_majorana | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| kitaev_honeycomb_gapless_triangle_condition | doi:10.1016/j.aop.2005.10.005 | spin_1_2_kitaev_honeycomb | gapless_condition | kitaev_majorana | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| li2cuo2_frustrated_ferromagnetic_chain_reference | doi:10.1103/physrevb.57.5326 | li2cuo2_j1_j2_chain | material_model_reference | ed_or_experiment | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| li2iro3_hyperhoneycomb_kitaev_reference | doi:10.1103/physrevlett.114.077202 | beta_li2iro3_hyperhoneycomb | material_reference | anisotropic_exchange | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| licuvo4_spiral_chain_reference | doi:10.1209/epl/i2004-10484-x | licuvo4_j1_j2_chain | spiral_order_reference | ed_or_experiment | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| lieb_lattice_heisenberg_ferrimagnet_reference | arxiv:2409.16715 | lieb_lattice_heisenberg | lieb_mattis_ferrimagnetism | diagnostic | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| lieb_liniger_delta_bose_gas_bethe_reference | doi:10.1103/physrev.130.1605 | lieb_liniger_bose_gas | exact_solution_status | bethe_ansatz | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| lieb_schultz_mattis_half_integer_constraint | doi:10.1007/s10955-017-1946-0 | half_odd_integer_u1_spin_chain | unique_ground_state_gaplessness_constraint | diagnostic | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| majundar_ghosh_chain_exact_dimer_point | doi:10.1088/0305-4470/17/13/020 | spin_1_2_j1_j2_chain | ground_state_energy | ed_or_analytic | answer_free_ready | completed | completed | completed | not_applicable | not_connected | matched |  |
| maple_leaf_lattice_heisenberg_reference | doi:10.1103/physrevb.84.104406 | maple_leaf_lattice_heisenberg | ground_state_magnetic_long_range_order | ed_or_dmrg | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| mn_ps3_honeycomb_antiferromagnet_reference | doi:10.1103/physrevb.82.100408 | mnps3_honeycomb_antiferromagnet | classical_order | classical_glt_or_spin_wave | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| mnsi_chiral_helimagnet_reference | doi:10.1088/0022-3719/13/31/002 | mnsi_chiral_helimagnet | helical_wavevector | classical_minimization | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| na4ir3o8_hyperkagome_material_reference | doi:10.1103/physrevlett.99.137207 | na4ir3o8_hyperkagome | material_qsl_reference | many_body_or_experiment | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| nacuo2_triangular_heisenberg_material_reference | arxiv:1405.6184 | nacro2_triangular_heisenberg | material_spin_order_reference | neutron_scattering_reference | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| ni_ps3_honeycomb_antiferromagnet_reference | doi:10.1103/physrevb.92.224408 | nips3_honeycomb_antiferromagnet | classical_order | classical_glt_or_spin_wave | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| one_dimensional_classical_ising_correlation_length | arxiv:2001.01693 | classical_ising_chain | correlation_length | transfer_matrix | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| one_dimensional_classical_ising_no_finite_t_transition | doi:10.1007/bf02980577 | classical_ising_chain | critical_temperature | transfer_matrix | answer_free_ready | completed | completed | completed | not_applicable | not_connected | matched |  |
| pr2zr2o7_quantum_spin_ice_reference | doi:10.1038/ncomms2914 | pr2zr2o7_quantum_spin_ice | quantum_spin_ice_reference | anisotropic_exchange | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| pyrochlore_anisotropic_exchange_jzz_jpm_reference | doi:10.1103/physrevx.1.021002 | rare_earth_pyrochlore_anisotropic_exchange | exchange_parameterization | anisotropic_exchange | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| pyrochlore_dipolar_spin_ice_pauling_entropy | doi:10.1126/science.1064761 | dipolar_spin_ice_pyrochlore | residual_entropy | mc | answer_free_ready | completed | completed | completed | not_applicable | not_connected | matched |  |
| pyrochlore_heisenberg_afm_coulomb_phase_reference | arxiv:cond-mat/0407005 | classical_pyrochlore_heisenberg_afm | ground_state_constraint | classical_glt_or_mc | answer_free_ready | completed | completed | completed | satisfied | not_connected | matched |  |
| pyrochlore_heisenberg_coulomb_phase_flat_band | doi:10.1103/physrevlett.80.2929 | classical_pyrochlore_heisenberg_afm | coulomb_phase | glt | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| quantum_spin_ice_u1_qsl_reference | doi:10.1103/physrevb.69.064404 | quantum_spin_ice_pyrochlore | phase_reference | gauge_theory_or_qmc | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| ru_br3_kitaev_material_reference | doi:10.1038/s41535-026-00868-6 | rubr3_honeycomb_competing_exchange | kitaev_candidate_with_competing_interactions | neutron_scattering_and_spin_wave | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| ruby_lattice_heisenberg_flat_band_reference | arxiv:2512.14173 | ruby_lattice_heisenberg | exact_localized_one_magnon_eigenstate | analytic_magnon | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| sawtooth_chain_localized_magnon_flat_band | doi:10.1140/epjb/e2006-00273-y | sawtooth_chain_heisenberg | localized_magnon | magnon_ed | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| scgo_kagome_bilayer_spin_liquid_reference | doi:10.1103/physrevlett.64.2070 | sr_cr_ga_o_kagome_bilayer | spin_liquid_material_reference | classical_mc_or_experiment | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| shastry_sutherland_exact_dimer_product | doi:10.1016/0378-4363(81)90838-x | shastry_sutherland | exact_dimer_energy | ed_or_analytic | answer_free_ready | completed | completed | completed | not_applicable | not_connected | matched |  |
| shastry_sutherland_magnetization_plateaus_reference | doi:10.1103/physrevlett.82.3168 | shastry_sutherland_high_field | magnetization_plateaus | ed_or_dmrg | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| shuriken_lattice_heisenberg_reference | arxiv:cond-mat/0411673 | uniform_square_kagome_heisenberg_antiferromagnet | square_kagome_quantum_paramagnet_reference | ed | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| simple_cubic_j1_j2_collinear_reference | doi:10.1063/1.367729 | simple_cubic_j1_j2_heisenberg | phase_boundary | glt | answer_free_ready | completed | completed | completed | satisfied | not_connected | matched |  |
| single_ion_spin1_anisotropy_levels | arxiv:1204.5027 | spin_1_single_ion_anisotropy | onsite_levels | analytic | answer_free_ready | completed | completed | completed | not_applicable | not_connected | matched |  |
| spin1_chain_large_d_transition_reference | doi:10.1103/physrevb.67.104401 | spin_1_heisenberg_single_ion_chain | haldane_large_d_transition | dmrg_or_ed | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| spin_ice_tetrahedron_nn_ice_rule | doi:10.1103/physrevlett.79.2554 | nearest_neighbor_spin_ice_tetrahedron | tetrahedron_energy_levels | analytic | answer_free_ready | completed | completed | completed | not_applicable | not_connected | matched |  |
| spin_ladder_rung_singlet_gap_reference | doi:10.1126/science.271.5249.618 | two_leg_heisenberg_ladder | spin_gap | dmrg_or_ed | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| spin_peierls_chain_dimerization_reference | doi:10.1103/physrevb.19.402 | spin_peierls_heisenberg_chain | spin_gap_opens_with_dimerization | field_theory_or_dmrg | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| square_ashkin_teller_exact_critical_line | doi:10.1103/physrevlett.26.832 | ashkin_teller_square | critical_line | transfer_matrix | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| square_clock_q5_two_bkt_transitions | doi:10.1103/physrevlett.96.140603 | q_state_clock_square | bkt_transition_count | mc_or_rg | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| square_compass_model_directional_exchange_degeneracy | doi:10.1103/revmodphys.87.1 | orbital_compass_square | directional_symmetry | ed_or_analytic | answer_free_ready | completed | completed | completed | not_applicable | not_connected | matched |  |
| square_dimerized_heisenberg_critical_reference | doi:10.1103/physrevb.65.014407 | square_dimerized_heisenberg | quantum_critical_point | qmc | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| square_fully_frustrated_ising_residual_entropy_reference | doi:10.1088/0305-4470/16/10/023 | fully_frustrated_square_ising | residual_entropy | transfer_matrix | answer_free_ready | completed | completed | completed | satisfied | not_connected | matched |  |
| square_heisenberg_spin_half_spin_stiffness_reference | doi:10.1103/physrevb.83.155120 | spin_1_2_square_heisenberg_afm | spin_stiffness | qmc | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| square_heisenberg_spin_half_staggered_magnetization_reference | doi:10.1103/physrevb.83.155120 | spin_1_2_square_heisenberg_afm | staggered_magnetization | qmc_or_large_ed | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| square_heisenberg_spin_wave_velocity_reference | doi:10.1103/physrevb.83.155120 | spin_1_2_square_heisenberg_afm | spin_wave_velocity | qmc_or_lswt | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| square_j1_j3_classical_lifshitz_reference | arxiv:1804.04308 | square_j1_j3_heisenberg | lifshitz_point | glt | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| square_jq_model_deconfined_critical_reference | doi:10.1103/physrevlett.98.227202 | square_jq_model | deconfined_critical_point | qmc | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| square_potts_exact_critical_point | doi:10.1103/revmodphys.54.235 | q_state_potts_square | critical_coupling | transfer_matrix | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| square_ring_exchange_neel_vbs_reference | arxiv:cond-mat/0205270 | square_xy_ring_exchange | ring_exchange_driven_bond_spin_peierls_order | qmc | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| square_six_vertex_ice_exact_solution_status | doi:10.1103/physrev.162.162 | six_vertex_model | exact_solution_status | vertex_model | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| square_spin_half_heisenberg_qmc_energy | doi:10.1103/physrevb.56.11678 | spin_1_2_square_heisenberg_afm | ground_state_energy | qmc_or_large_ed | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| square_toric_code_exact_topological_degeneracy | doi:10.1016/s0003-4916(02)00018-0 | toric_code_square | ground_state_degeneracy | stabilizer | answer_free_ready | completed | completed | completed | not_applicable | not_connected | matched |  |
| sr_cu2_bo3_2_shastry_sutherland_material_reference | doi:10.1103/physrevlett.82.3168 | sr_cu2_bo3_2 | material_model_reference | ed_or_dmrg | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| star_lattice_heisenberg_spin_liquid_reference | doi:10.1103/physrevb.70.174454 | uniform_star_lattice_heisenberg_antiferromagnet | gapped_valence_bond_crystal_reference | ed | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| takhtajan_babujian_spin1_critical_point | arxiv:cond-mat/9811353 | spin_1_bilinear_biquadratic_chain | critical_point | bethe_or_ed | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| tb2ti2o7_pyrochlore_spin_liquid_reference | doi:10.1103/physrevlett.82.1012 | tb2ti2o7_pyrochlore | spin_liquid_reference | anisotropic_exchange | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| transverse_field_ising_chain_critical_point | arxiv:cond-mat/0509490 | spin_1_2_transverse_field_ising_chain | quantum_critical_point | free_fermion_or_ed | answer_free_ready | completed | completed | completed | satisfied | not_connected | matched |  |
| transverse_field_ising_chain_gap | arxiv:cond-mat/0509490 | spin_1_2_transverse_field_ising_chain | excitation_gap | free_fermion_or_ed | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| triangular_heisenberg_magnetization_plateau_reference | doi:10.1088/0953-8984/3/1/005 | spin_half_triangular_heisenberg_in_field | one_third_plateau_from_spin_wave_expansion | spin_wave_1_over_s | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| triangular_heisenberg_spin_half_energy_reference | doi:10.1103/physrevlett.82.3899 | spin_1_2_triangular_heisenberg | ground_state_energy | dmrg_or_vmc | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| triangular_ising_antiferromagnet_residual_entropy | doi:10.1103/physrev.79.357 | classical_triangular_ising_antiferromagnet | residual_entropy | transfer_matrix | answer_free_ready | completed | completed | inconclusive | not_demonstrated | not_connected | inconclusive | finite periodic clusters do not yet certify the thermodynamic-limit entropy |
| triangular_ising_ferromagnet_exact_tc | doi:10.1143/ptp/5.2.177 | classical_triangular_ising | critical_temperature | transfer_matrix | answer_free_ready | completed | completed | completed | satisfied | not_connected | matched |  |
| triangular_j1_j2_spin_half_phase_diagram_reference | doi:10.1103/physrevb.92.041105 | spin_1_2_triangular_j1_j2_heisenberg | phase_diagram | dmrg_or_many_body | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| triangular_nn_classical_120_reference | doi:10.1103/physrevlett.60.2531 | triangular_nn_heisenberg | ordering_vector | glt | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| triangular_ring_exchange_spin_liquid_reference | doi:10.1103/physrevb.72.045105 | triangular_multiple_spin_exchange | phase_diagram | ed_or_dmrg | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| triangular_xxz_supersolid_phase_reference | doi:10.1103/physrevlett.95.127205 | triangular_xxz_antiferromagnet | phase_diagram | qmc_or_ed | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| two_dimensional_square_ising_onsager_tc | doi:10.1103/physrev.65.117 | classical_square_ising | critical_temperature | analytic | answer_free_ready | completed | completed | completed | satisfied | not_connected | matched |  |
| two_dimensional_square_ising_spontaneous_magnetization | doi:10.1103/physrev.85.808 | classical_square_ising | spontaneous_magnetization | analytic | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| two_dimensional_xy_bkt_temperature_reference | doi:10.1088/0305-4470/38/26/003 | classical_square_xy | bkt_temperature | mc_or_rg | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| two_dimensional_xy_bkt_universal_jump | doi:10.1103/physrevlett.39.1201 | classical_square_xy | helicity_modulus_jump | mc_or_rg | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| two_leg_ladder_strong_rung_exact_limit | doi:10.1126/science.271.5249.618 | two_leg_heisenberg_ladder_strong_rung | exact_rung_singlet_energy | ed_or_analytic | answer_free_ready | completed | completed | completed | not_applicable | not_connected | matched |  |
| uimin_lai_sutherland_spin1_su3_point | doi:10.1103/physrevb.12.3795 | spin_1_bilinear_biquadratic_chain | integrable_point | bethe_or_ed | answer_free_ready | completed | completed | completed | satisfied | not_connected | matched |  |
| vesignieite_kagome_material_reference | doi:10.1103/physrevlett.121.107203 | vesignieite_dominant_j3_kagome_antiferromagnet | dominant_j3_not_distortion_assessment | neutron_scattering_and_spin_wave | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| volborthite_kagome_distorted_reference | doi:10.1143/jpsj.70.3377 | volborthite_distorted_kagome | material_reference | anisotropic_exchange | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| xx_spin_half_chain_free_fermion_energy | doi:10.1103/physrevb.92.125131 | spin_1_2_xx_chain | thermodynamic_limit_ground_state_energy | free_fermion_or_ed | answer_free_ready | completed | completed | completed | satisfied | not_connected | matched |  |
| xxx_spin_half_chain_bethe_ground_state | doi:10.1103/physrev.150.327 | spin_1_2_xxx_chain | thermodynamic_limit_ground_state_energy | bethe_or_extrapolated_ed | answer_free_ready | completed | completed | completed | satisfied | not_connected | matched |  |
| xxz_spin_half_chain_phase_boundaries | arxiv:cond-mat/9909290 | spin_1_2_xxz_chain | phase_boundaries | analytic | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| xy_spin_half_chain_anisotropic_critical_line | doi:10.1103/physreva.3.786 | spin_1_2_xy_chain_transverse_field | critical_line | free_fermion_or_ed | answer_free_ready | completed | completed | completed | not_applicable | not_connected | matched |  |
| yb2ti2o7_pyrochlore_exchange_reference | doi:10.1103/physrevx.1.021002 | yb2ti2o7_anisotropic_pyrochlore | exchange_parameter_reference | anisotropic_exchange | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| ybmggao4_triangular_spin_liquid_reference | doi:10.1038/srep16419 | ybmggao4_triangular_exchange | material_model_reference | anisotropic_exchange_or_experiment | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| zn_barlowite_kagome_qsl_reference | doi:10.1103/physrevb.94.125136 | zn_substituted_barlowite_kagome | substitution_effective_exchange_model | first_principles_exchange_mapping | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
| zncu3oh6cl2_kagome_dzyaloshinskii_moriya_reference | doi:10.1103/physrevlett.101.026405 | herbertsmithite_kagome_dm | material_model_reference | ed_or_experiment | not_landed | not_run | not_run | not_run | not_run | not_connected | not_run | answer-free generic model input not yet landed |
