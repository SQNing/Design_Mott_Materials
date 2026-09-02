# Literature Models Through the Generic Workflow

This report is generated from fresh generic-workflow runs. Paper claims and oracle results are not inputs to model computation.

| Layer | Count |
|---|---:|
| Eligible models | 29 |
| Migrated to generic workflow | 29 |
| Not migrated | 0 |
| Normalized | 29 |
| Simplified | 29 |
| Analyzed by a generic backend | 27 |
| Convergence satisfied | 15 |
| Convergence not applicable to exact finite/algebraic result | 12 |
| Inconclusive | 2 |
| Independent oracle verified | 0 |
| Matched to literature after computation | 27 |

## Model status

| Model | Backend family | Migration | Normalize | Simplify | Backend | Computation | Convergence | Oracle | Literature match | Blocker |
|---|---|---|---|---|---|---|---|---|---|---|
| xxx_spin_half_chain_bethe_ground_state | analytic | migrated | completed | completed | available | completed | satisfied | not_connected | matched |  |
| two_dimensional_square_ising_onsager_tc | analytic | migrated | completed | completed | available | completed | satisfied | not_connected | matched |  |
| triangular_ising_antiferromagnet_residual_entropy | iterative_numeric | migrated | completed | completed | available | inconclusive | not_demonstrated | not_connected | not_run | finite periodic clusters do not yet certify the thermodynamic-limit entropy |
| xy_spin_half_chain_anisotropic_critical_line | glt_fourier | migrated | completed | completed | available | completed | not_applicable | not_connected | matched |  |
| diamond_j1_j2_spiral_surface_reference | glt_fourier | migrated | completed | completed | available | completed | satisfied | not_connected | matched |  |
| spin_ice_tetrahedron_nn_ice_rule | enumeration | migrated | completed | completed | available | completed | not_applicable | not_connected | matched |  |
| two_leg_ladder_strong_rung_exact_limit | dense_ed | migrated | completed | completed | available | completed | not_applicable | not_connected | matched |  |
| pyrochlore_dipolar_spin_ice_pauling_entropy | analytic | migrated | completed | completed | available | completed | not_applicable | not_connected | matched |  |
| uimin_lai_sutherland_spin1_su3_point | dense_ed | migrated | completed | completed | available | completed | satisfied | not_connected | matched |  |
| bilinear_biquadratic_spin1_chain_aklt_angle | analytic | migrated | completed | completed | available | completed | satisfied | not_connected | matched |  |
| square_compass_model_directional_exchange_degeneracy | dense_ed | migrated | completed | completed | available | completed | not_applicable | not_connected | matched |  |
| kitaev_honeycomb_abelian_nonabelian_field_gap_reference | glt_fourier | migrated | completed | completed | available | completed | satisfied | not_connected | matched |  |
| square_toric_code_exact_topological_degeneracy | enumeration | migrated | completed | completed | available | completed | not_applicable | not_connected | matched |  |
| aklt_spin1_chain_projector_ground_state | dense_ed | migrated | completed | completed | available | completed | not_applicable | not_connected | matched |  |
| blume_capel_spin1_zero_temperature_level_crossing | enumeration | migrated | completed | completed | available | completed | satisfied | not_connected | matched |  |
| checkerboard_heisenberg_afm_planar_pyrochlore_reference | enumeration | migrated | completed | completed | available | completed | not_applicable | not_connected | matched |  |
| honeycomb_ising_ferromagnet_exact_tc | analytic | migrated | completed | completed | available | completed | satisfied | not_connected | matched |  |
| kagome_ising_antiferromagnet_residual_entropy_reference | iterative_numeric | migrated | completed | completed | available | inconclusive | not_demonstrated | not_connected | not_run | finite periodic clusters do not yet certify the thermodynamic-limit entropy |
| kagome_ising_ferromagnet_exact_tc | analytic | migrated | completed | completed | available | completed | satisfied | not_connected | matched |  |
| majundar_ghosh_chain_exact_dimer_point | dense_ed | migrated | completed | completed | available | completed | not_applicable | not_connected | matched |  |
| one_dimensional_classical_ising_no_finite_t_transition | analytic | migrated | completed | completed | available | completed | not_applicable | not_connected | matched |  |
| pyrochlore_heisenberg_afm_coulomb_phase_reference | glt_fourier | migrated | completed | completed | available | completed | satisfied | not_connected | matched |  |
| shastry_sutherland_exact_dimer_product | dense_ed | migrated | completed | completed | available | completed | not_applicable | not_connected | matched |  |
| simple_cubic_j1_j2_collinear_reference | glt_fourier | migrated | completed | completed | available | completed | satisfied | not_connected | matched |  |
| single_ion_spin1_anisotropy_levels | dense_ed | migrated | completed | completed | available | completed | not_applicable | not_connected | matched |  |
| square_fully_frustrated_ising_residual_entropy_reference | iterative_numeric | migrated | completed | completed | available | completed | satisfied | not_connected | matched |  |
| transverse_field_ising_chain_critical_point | glt_fourier | migrated | completed | completed | available | completed | satisfied | not_connected | matched |  |
| triangular_ising_ferromagnet_exact_tc | analytic | migrated | completed | completed | available | completed | satisfied | not_connected | matched |  |
| xx_spin_half_chain_free_fermion_energy | iterative_numeric | migrated | completed | completed | available | completed | satisfied | not_connected | matched |  |
