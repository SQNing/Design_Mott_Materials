import math

import numpy as np


LITERATURE_STANDARD_RESULTS = [
    {
        "name": "majundar_ghosh_chain_exact_dimer_point",
        "model": "spin_1_2_j1_j2_chain",
        "hamiltonian": "J1 sum Si.Si+1 + J2 sum Si.Si+2",
        "parameters": {"spin": 0.5, "j2_over_j1": 0.5},
        "observable": "ground_state_energy",
        "comparison_kind": "exact_solution",
        "backend_needed": "ed_or_analytic",
        "standard_result": {"energy_per_site": -0.375, "degenerate_dimer_coverings": 2},
        "source": "Majumdar_Ghosh_1969",
        "source_url": "https://doi.org/10.1063/1.1664978",
        "citation_locator": "exact dimer ground state at J2/J1=1/2",
    },
    {
        "name": "aklt_spin1_chain_projector_ground_state",
        "model": "spin_1_bilinear_biquadratic_chain",
        "hamiltonian": "sum [Si.Sj + (Si.Sj)^2/3 + 2/3]",
        "parameters": {"spin": 1.0, "projector": "P_total_spin_2"},
        "observable": "local_spectrum",
        "comparison_kind": "exact_solution",
        "backend_needed": "ed_or_analytic",
        "standard_result": {"two_site_projector_eigenvalues": [0.0, 0.0, 1.0], "vbs_ground_energy": 0.0},
        "source": "Affleck_Kennedy_Lieb_Tasaki_1987",
        "source_url": "https://doi.org/10.1103/PhysRevLett.59.799",
        "citation_locator": "AKLT projector Hamiltonian",
    },
    {
        "name": "xxx_spin_half_chain_bethe_ground_state",
        "model": "spin_1_2_xxx_chain",
        "hamiltonian": "J sum Si.Si+1",
        "parameters": {"spin": 0.5, "exchange": 1.0},
        "observable": "thermodynamic_limit_ground_state_energy",
        "comparison_kind": "exact_solution",
        "backend_needed": "bethe_or_extrapolated_ed",
        "standard_result": {"energy_per_site": 0.25 - math.log(2.0)},
        "source": "Bethe_1931",
        "source_url": "https://doi.org/10.1007/BF01341708",
        "citation_locator": "Bethe ansatz antiferromagnetic chain energy",
    },
    {
        "name": "xxz_spin_half_chain_phase_boundaries",
        "model": "spin_1_2_xxz_chain",
        "hamiltonian": "sum [SxSx + SySy + Delta SzSz]",
        "parameters": {"spin": 0.5},
        "observable": "phase_boundaries",
        "comparison_kind": "exact_solution",
        "backend_needed": "analytic",
        "standard_result": {
            "ferromagnetic_boundary_delta": -1.0,
            "neel_boundary_delta": 1.0,
            "gapless_interval": [-1.0, 1.0],
        },
        "source": "Yang_Yang_1966",
        "source_url": "https://doi.org/10.1103/PhysRev.150.321",
        "citation_locator": "XXZ Bethe-ansatz phase diagram",
    },
    {
        "name": "shastry_sutherland_exact_dimer_product",
        "model": "shastry_sutherland",
        "hamiltonian": "J interdimer edges + Jd orthogonal dimers",
        "parameters": {"spin": 0.5, "dimer_exchange": 1.0},
        "observable": "exact_dimer_energy",
        "comparison_kind": "exact_solution",
        "backend_needed": "ed_or_analytic",
        "standard_result": {"energy_per_dimer": -0.75, "energy_per_spin": -0.375},
        "source": "Shastry_Sutherland_1981",
        "source_url": "https://doi.org/10.1016/0375-9601(81)90438-X",
        "citation_locator": "orthogonal dimer exact eigenstate",
    },
    {
        "name": "spin_ice_tetrahedron_nn_ice_rule",
        "model": "nearest_neighbor_spin_ice_tetrahedron",
        "hamiltonian": "J_eff sum sigma_i sigma_j on tetrahedron",
        "parameters": {"ising_variables": "sigma=+/-1", "jeff": 1.0},
        "observable": "tetrahedron_energy_levels",
        "comparison_kind": "exact_enumeration",
        "backend_needed": "analytic",
        "standard_result": {
            "two_in_two_out_energy": -2.0,
            "three_in_one_out_energy": 0.0,
            "all_in_all_out_energy": 6.0,
            "two_in_two_out_degeneracy": 6,
        },
        "source": "Harris_Bramwell_McMorrow_Zeiske_Godfrey_1997",
        "source_url": "https://doi.org/10.1103/PhysRevLett.79.2554",
        "citation_locator": "spin-ice rule on pyrochlore tetrahedra",
    },
    {
        "name": "single_ion_spin1_anisotropy_levels",
        "model": "spin_1_single_ion_anisotropy",
        "hamiltonian": "D Sz^2",
        "parameters": {"spin": 1.0, "anisotropy": 1.0},
        "observable": "onsite_levels",
        "comparison_kind": "exact_solution",
        "backend_needed": "analytic",
        "standard_result": {"levels": [0.0, 1.0, 1.0], "degeneracies": [1, 2]},
        "source": "Blume_1966",
        "source_url": "https://doi.org/10.1103/PhysRev.141.517",
        "citation_locator": "single-ion anisotropy term in spin-1 models",
    },
    {
        "name": "kitaev_honeycomb_exact_spin_liquid_limit",
        "model": "spin_1_2_kitaev_honeycomb",
        "hamiltonian": "sum_gamma K_gamma S_i^gamma S_j^gamma",
        "parameters": {"kx": 1.0, "ky": 1.0, "kz": 1.0},
        "observable": "exact_solution_status",
        "comparison_kind": "paper_formula",
        "backend_needed": "kitaev_majorana",
        "standard_result": {"is_exactly_solvable": True, "isotropic_phase": "gapless_spin_liquid"},
        "source": "Kitaev_2006",
        "source_url": "https://doi.org/10.1016/j.aop.2005.10.005",
        "citation_locator": "honeycomb model exact solution",
    },
    {
        "name": "haldane_spin1_chain_gap_reference",
        "model": "spin_1_heisenberg_chain",
        "hamiltonian": "J sum Si.Si+1",
        "parameters": {"spin": 1.0, "exchange": 1.0},
        "observable": "haldane_gap",
        "comparison_kind": "paper_numeric",
        "backend_needed": "dmrg_or_large_ed",
        "standard_result": {"gap_over_j": 0.41048, "tolerance": 5.0e-5},
        "source": "White_Huse_1993",
        "source_url": "https://doi.org/10.1103/PhysRevB.48.3844",
        "citation_locator": "DMRG Haldane gap benchmark",
    },
    {
        "name": "square_spin_half_heisenberg_qmc_energy",
        "model": "spin_1_2_square_heisenberg_afm",
        "hamiltonian": "J sum_<ij> Si.Sj",
        "parameters": {"spin": 0.5, "exchange": 1.0},
        "observable": "ground_state_energy",
        "comparison_kind": "paper_numeric",
        "backend_needed": "qmc_or_large_ed",
        "standard_result": {"energy_per_site": -0.669437, "tolerance": 5.0e-6},
        "source": "Sandvik_1997",
        "source_url": "https://doi.org/10.1103/PhysRevB.56.11678",
        "citation_locator": "square-lattice S=1/2 Heisenberg QMC benchmark",
    },
    {
        "name": "j1_j2_square_spin_half_neel_collinear_transition_reference",
        "model": "spin_1_2_square_j1_j2_heisenberg",
        "hamiltonian": "J1 NN + J2 NNN",
        "parameters": {"spin": 0.5},
        "observable": "quantum_phase_window",
        "comparison_kind": "paper_numeric",
        "backend_needed": "many_body",
        "standard_result": {"nonmagnetic_window_approx": [0.4, 0.6]},
        "source": "Richter_arXiv_1409_0193",
        "source_url": "https://arxiv.org/abs/1409.0193",
        "citation_locator": "reviewed J1-J2 square phase diagram window",
    },
    {
        "name": "bilinear_biquadratic_spin1_chain_aklt_angle",
        "model": "spin_1_bilinear_biquadratic_chain",
        "hamiltonian": "sum [cos(theta) Si.Sj + sin(theta) (Si.Sj)^2]",
        "parameters": {"spin": 1.0},
        "observable": "special_angle",
        "comparison_kind": "exact_solution",
        "backend_needed": "analytic",
        "standard_result": {"aklt_tan_theta": 1.0 / 3.0, "theta_radians": math.atan(1.0 / 3.0)},
        "source": "Affleck_Kennedy_Lieb_Tasaki_1987",
        "source_url": "https://doi.org/10.1103/PhysRevLett.59.799",
        "citation_locator": "AKLT point in bilinear-biquadratic chain",
    },
    {
        "name": "transverse_field_ising_chain_critical_point",
        "model": "spin_1_2_transverse_field_ising_chain",
        "hamiltonian": "-J sum sigma_i^z sigma_i+1^z - h sum sigma_i^x",
        "parameters": {"spin": 0.5, "exchange": 1.0},
        "observable": "quantum_critical_point",
        "comparison_kind": "exact_solution",
        "backend_needed": "free_fermion_or_ed",
        "standard_result": {"critical_field_over_exchange": 1.0},
        "source": "Pfeuty_1970",
        "source_url": "https://doi.org/10.1016/0003-4916(70)90270-8",
        "citation_locator": "1D transverse-field Ising exact critical point",
    },
    {
        "name": "transverse_field_ising_chain_gap",
        "model": "spin_1_2_transverse_field_ising_chain",
        "hamiltonian": "-J sum sigma_i^z sigma_i+1^z - h sum sigma_i^x",
        "parameters": {"spin": 0.5, "exchange": 1.0, "field_over_exchange": 0.6},
        "observable": "excitation_gap",
        "comparison_kind": "exact_solution",
        "backend_needed": "free_fermion_or_ed",
        "standard_result": {"gap_formula": "2J|1-g|", "gap_formula_at_g_0_6": 0.8},
        "source": "Pfeuty_1970",
        "source_url": "https://doi.org/10.1016/0003-4916(70)90270-8",
        "citation_locator": "free-fermion TFIM gap",
    },
    {
        "name": "two_dimensional_square_ising_onsager_tc",
        "model": "classical_square_ising",
        "hamiltonian": "-J sum sigma_i sigma_j",
        "parameters": {"exchange": 1.0},
        "observable": "critical_temperature",
        "comparison_kind": "exact_solution",
        "backend_needed": "analytic",
        "standard_result": {"tc_over_j": 2.0 / math.log(1.0 + math.sqrt(2.0))},
        "source": "Onsager_1944",
        "source_url": "https://doi.org/10.1103/PhysRev.65.117",
        "citation_locator": "square-lattice Ising critical temperature",
    },
    {
        "name": "two_dimensional_square_ising_spontaneous_magnetization",
        "model": "classical_square_ising",
        "hamiltonian": "-J sum sigma_i sigma_j",
        "parameters": {"exchange": 1.0, "beta": 0.6},
        "observable": "spontaneous_magnetization",
        "comparison_kind": "exact_solution",
        "backend_needed": "analytic",
        "standard_result": {
            "formula": "[1 - sinh(2 beta J)^(-4)]^(1/8)",
            "magnetization_beta_0_6_j_1": (1.0 - math.sinh(1.2) ** -4) ** 0.125,
        },
        "source": "Yang_1952",
        "source_url": "https://doi.org/10.1103/PhysRev.85.808",
        "citation_locator": "square-lattice Ising spontaneous magnetization",
    },
    {
        "name": "two_dimensional_xy_bkt_temperature_reference",
        "model": "classical_square_xy",
        "hamiltonian": "-J sum cos(theta_i - theta_j)",
        "parameters": {"exchange": 1.0},
        "observable": "bkt_temperature",
        "comparison_kind": "paper_numeric",
        "backend_needed": "mc_or_rg",
        "standard_result": {"tbkt_over_j": 0.89294, "tolerance": 5.0e-5},
        "source": "Hasenbusch_2005",
        "source_url": "https://doi.org/10.1088/0305-4470/38/26/003",
        "citation_locator": "high-precision square XY BKT temperature",
    },
    {
        "name": "two_dimensional_xy_bkt_universal_jump",
        "model": "classical_square_xy",
        "hamiltonian": "-J sum cos(theta_i - theta_j)",
        "parameters": {"temperature": 1.0},
        "observable": "helicity_modulus_jump",
        "comparison_kind": "paper_formula",
        "backend_needed": "mc_or_rg",
        "standard_result": {"formula": "rho_s(T_BKT)=2T_BKT/pi", "helicity_modulus_at_t_1": 2.0 / math.pi},
        "source": "Nelson_Kosterlitz_1977",
        "source_url": "https://doi.org/10.1103/PhysRevLett.39.1201",
        "citation_locator": "universal BKT stiffness jump",
    },
    {
        "name": "one_dimensional_classical_ising_no_finite_t_transition",
        "model": "classical_ising_chain",
        "hamiltonian": "-J sum sigma_i sigma_i+1",
        "parameters": {"exchange": 1.0},
        "observable": "critical_temperature",
        "comparison_kind": "exact_solution",
        "backend_needed": "transfer_matrix",
        "standard_result": {"finite_temperature_transition": False, "tc_over_j": 0.0},
        "source": "Ising_1925",
        "source_url": "https://doi.org/10.1007/BF02980577",
        "citation_locator": "one-dimensional Ising no finite-T transition",
    },
    {
        "name": "one_dimensional_classical_ising_correlation_length",
        "model": "classical_ising_chain",
        "hamiltonian": "-J sum sigma_i sigma_i+1",
        "parameters": {"exchange": 1.0, "beta": 1.0},
        "observable": "correlation_length",
        "comparison_kind": "exact_solution",
        "backend_needed": "transfer_matrix",
        "standard_result": {"formula": "-1/log(tanh(beta J))", "correlation_length_beta_1_j_1": -1.0 / math.log(math.tanh(1.0))},
        "source": "Ising_1925",
        "source_url": "https://doi.org/10.1007/BF02980577",
        "citation_locator": "one-dimensional Ising transfer-matrix correlation length",
    },
    {
        "name": "lieb_schultz_mattis_half_integer_constraint",
        "model": "half_integer_spin_chain",
        "hamiltonian": "translation-invariant local spin Hamiltonian",
        "parameters": {"spin_per_unit_cell": "half_integer"},
        "observable": "spectral_constraint",
        "comparison_kind": "theorem",
        "backend_needed": "diagnostic",
        "standard_result": {"unique_gapped_symmetric_ground_state_allowed": False},
        "source": "Lieb_Schultz_Mattis_1961",
        "source_url": "https://doi.org/10.1016/0003-4916(61)90115-4",
        "citation_locator": "LSM half-integer spin-chain constraint",
    },
    {
        "name": "kitaev_honeycomb_gapless_triangle_condition",
        "model": "spin_1_2_kitaev_honeycomb",
        "hamiltonian": "sum_gamma K_gamma S_i^gamma S_j^gamma",
        "parameters": {"kx": 1.0, "ky": 1.0, "kz": 1.0},
        "observable": "gapless_condition",
        "comparison_kind": "paper_formula",
        "backend_needed": "kitaev_majorana",
        "standard_result": {"gapless_condition": "triangle_inequalities", "isotropic_kitaev_point_gapless": True},
        "source": "Kitaev_2006",
        "source_url": "https://doi.org/10.1016/j.aop.2005.10.005",
        "citation_locator": "Kitaev honeycomb gapless phase condition",
    },
    {
        "name": "eight_vertex_zero_field_exact_solution_status",
        "model": "eight_vertex_model",
        "hamiltonian": "classical vertex weights a,b,c,d",
        "parameters": {"field": 0.0},
        "observable": "exact_solution_status",
        "comparison_kind": "exact_solution",
        "backend_needed": "vertex_model",
        "standard_result": {"is_exactly_solved": True},
        "source": "Baxter_1971",
        "source_url": "https://doi.org/10.1103/PhysRevLett.26.832",
        "citation_locator": "zero-field eight-vertex exact solution",
    },
    {
        "name": "blume_capel_spin1_zero_temperature_level_crossing",
        "model": "spin_1_blume_capel",
        "hamiltonian": "-J sum Si Sj + D sum Si^2",
        "parameters": {"spin": 1.0, "exchange": 1.0},
        "observable": "zero_temperature_level_crossing",
        "comparison_kind": "exact_solution",
        "backend_needed": "analytic",
        "standard_result": {"square_lattice_d_over_j_crossing": 2.0},
        "source": "Blume_1966",
        "source_url": "https://doi.org/10.1103/PhysRev.141.517",
        "citation_locator": "Blume-Capel spin-1 anisotropy competition",
    },
]


LITERATURE_STANDARD_RESULTS.extend(
    [
        {
            "name": "square_potts_exact_critical_point",
            "model": "q_state_potts_square",
            "lattice": "square",
            "hamiltonian": "-J sum delta(sigma_i, sigma_j)",
            "hamiltonian_terms": ["potts", "nearest_neighbor", "classical"],
            "parameters": {"q": "arbitrary", "exchange": 1.0},
            "observable": "critical_coupling",
            "comparison_kind": "exact_solution",
            "backend_needed": "transfer_matrix",
            "standard_result": {"critical_beta_j": "log(1 + sqrt(q))", "continuous_for_q_le_4": True},
            "source": "Wu_1982",
            "source_url": "https://doi.org/10.1103/RevModPhys.54.235",
            "citation_locator": "square-lattice Potts critical point",
        },
        {
            "name": "square_clock_q5_two_bkt_transitions",
            "model": "q_state_clock_square",
            "lattice": "square",
            "hamiltonian": "-J sum cos(theta_i - theta_j)",
            "hamiltonian_terms": ["clock", "xy", "classical", "nearest_neighbor"],
            "parameters": {"q": 5, "exchange": 1.0},
            "observable": "bkt_transition_count",
            "comparison_kind": "paper_numeric",
            "backend_needed": "mc_or_rg",
            "standard_result": {"transition_count": 2, "phase_sequence": ["ordered", "critical", "disordered"]},
            "source": "Lapilli_Pfeifer_Wexler_2006",
            "source_url": "https://doi.org/10.1103/PhysRevLett.96.140603",
            "citation_locator": "q-state clock two-transition regime for q>=5",
        },
        {
            "name": "square_ashkin_teller_exact_critical_line",
            "model": "ashkin_teller_square",
            "lattice": "square",
            "hamiltonian": "two coupled Ising models with four-spin coupling",
            "hamiltonian_terms": ["ashkin_teller", "ising", "four_spin", "classical"],
            "parameters": {"field": 0.0},
            "observable": "critical_line",
            "comparison_kind": "exact_solution",
            "backend_needed": "transfer_matrix",
            "standard_result": {"has_exact_critical_line": True},
            "source": "Baxter_1972",
            "source_url": "https://doi.org/10.1103/PhysRevLett.26.832",
            "citation_locator": "Ashkin-Teller/eight-vertex exact critical manifold",
        },
        {
            "name": "square_six_vertex_ice_exact_solution_status",
            "model": "six_vertex_model",
            "lattice": "square_vertex",
            "hamiltonian": "six allowed ice-rule vertex weights",
            "hamiltonian_terms": ["vertex_model", "six_vertex", "ice_rule", "classical"],
            "parameters": {"field": 0.0},
            "observable": "exact_solution_status",
            "comparison_kind": "exact_solution",
            "backend_needed": "vertex_model",
            "standard_result": {"is_exactly_solved": True},
            "source": "Lieb_1967",
            "source_url": "https://doi.org/10.1103/PhysRev.162.162",
            "citation_locator": "six-vertex ice model exact solution",
        },
        {
            "name": "square_toric_code_exact_topological_degeneracy",
            "model": "toric_code_square",
            "lattice": "square",
            "hamiltonian": "-Je sum A_s - Jm sum B_p",
            "hamiltonian_terms": ["stabilizer", "toric_code", "topological"],
            "parameters": {"genus": 1},
            "observable": "ground_state_degeneracy",
            "comparison_kind": "exact_solution",
            "backend_needed": "stabilizer",
            "standard_result": {"torus_ground_state_degeneracy": 4},
            "source": "Kitaev_2003",
            "source_url": "https://doi.org/10.1016/S0003-4916(02)00018-0",
            "citation_locator": "toric-code topological degeneracy on torus",
        },
        {
            "name": "square_compass_model_directional_exchange_degeneracy",
            "model": "orbital_compass_square",
            "lattice": "square",
            "hamiltonian": "Jx sum_x tau_i^x tau_j^x + Jz sum_z tau_i^z tau_j^z",
            "hamiltonian_terms": ["compass", "directional_exchange", "orbital"],
            "parameters": {"j_x": 1.0, "j_z": 1.0},
            "observable": "directional_symmetry",
            "comparison_kind": "paper_formula",
            "backend_needed": "ed_or_analytic",
            "standard_result": {"has_line_flip_symmetries": True},
            "source": "Nussinov_van_den_Brink_2015",
            "source_url": "https://doi.org/10.1103/RevModPhys.87.1",
            "citation_locator": "compass-model directional symmetries",
        },
        {
            "name": "triangular_j1_j2_spin_half_phase_diagram_reference",
            "model": "spin_1_2_triangular_j1_j2_heisenberg",
            "lattice": "triangular",
            "hamiltonian": "J1 NN + J2 NNN Heisenberg",
            "hamiltonian_terms": ["heisenberg", "j1", "j2", "frustrated"],
            "parameters": {"spin": 0.5},
            "observable": "phase_diagram",
            "comparison_kind": "paper_numeric",
            "backend_needed": "dmrg_or_many_body",
            "standard_result": {"phases": ["120_degree", "spin_liquid", "stripe"]},
            "source": "Zhu_White_2015",
            "source_url": "https://doi.org/10.1103/PhysRevB.92.041105",
            "citation_locator": "triangular J1-J2 spin-half phase diagram",
        },
        {
            "name": "triangular_xxz_supersolid_phase_reference",
            "model": "triangular_xxz_antiferromagnet",
            "lattice": "triangular",
            "hamiltonian": "Jxy transverse exchange + Jz Ising exchange",
            "hamiltonian_terms": ["xxz", "easy_axis", "frustrated"],
            "parameters": {"lattice": "triangular"},
            "observable": "phase_diagram",
            "comparison_kind": "paper_numeric",
            "backend_needed": "qmc_or_ed",
            "standard_result": {"contains_supersolid_phase": True},
            "source": "Wessel_Troyer_2005",
            "source_url": "https://doi.org/10.1103/PhysRevLett.95.127205",
            "citation_locator": "triangular XXZ supersolid phase",
        },
        {
            "name": "triangular_ring_exchange_spin_liquid_reference",
            "model": "triangular_multiple_spin_exchange",
            "lattice": "triangular",
            "hamiltonian": "Heisenberg plus cyclic ring exchange",
            "hamiltonian_terms": ["heisenberg", "ring_exchange", "frustrated"],
            "parameters": {"spin": 0.5},
            "observable": "phase_diagram",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed_or_dmrg",
            "standard_result": {"contains_spin_liquid_region": True},
            "source": "Motrunich_2005",
            "source_url": "https://doi.org/10.1103/PhysRevB.72.045105",
            "citation_locator": "triangular ring-exchange spin-liquid regime",
        },
        {
            "name": "honeycomb_j1_j2_j3_classical_phase_diagram",
            "model": "honeycomb_j1_j2_j3_heisenberg",
            "lattice": "honeycomb",
            "hamiltonian": "J1 NN + J2 NNN + J3 third-neighbor Heisenberg",
            "hamiltonian_terms": ["heisenberg", "j1", "j2", "j3", "frustrated"],
            "parameters": {"spin": "classical_or_large_S"},
            "observable": "phase_diagram",
            "comparison_kind": "paper_formula",
            "backend_needed": "glt",
            "standard_result": {"phases": ["neel", "spiral", "zigzag", "stripy"]},
            "source": "Rastelli_Tassi_Reatto_1979",
            "source_url": "https://doi.org/10.1016/0304-8853(79)90049-2",
            "citation_locator": "honeycomb J1-J2-J3 classical phase diagram",
        },
        {
            "name": "honeycomb_kitaev_heisenberg_four_sublattice_phases",
            "model": "honeycomb_kitaev_heisenberg",
            "lattice": "honeycomb",
            "hamiltonian": "J Heisenberg + K bond-dependent Kitaev",
            "hamiltonian_terms": ["kitaev", "heisenberg", "bond_dependent"],
            "parameters": {"spin": 0.5},
            "observable": "phase_diagram",
            "comparison_kind": "paper_formula",
            "backend_needed": "ed_or_classical",
            "standard_result": {"ordered_phases": ["ferromagnetic", "neel", "zigzag", "stripy"]},
            "source": "Chaloupka_Jackeli_Khaliullin_2010",
            "source_url": "https://doi.org/10.1103/PhysRevLett.105.027204",
            "citation_locator": "Kitaev-Heisenberg honeycomb phase diagram",
        },
        {
            "name": "honeycomb_kitaev_gamma_phase_diagram_reference",
            "model": "honeycomb_kitaev_gamma",
            "lattice": "honeycomb",
            "hamiltonian": "K Kitaev + Gamma off-diagonal exchange",
            "hamiltonian_terms": ["kitaev", "gamma", "off_diagonal_exchange", "bond_dependent"],
            "parameters": {"spin": 0.5},
            "observable": "phase_diagram",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed_or_classical",
            "standard_result": {"contains_noncollinear_and_zigzag_phases": True},
            "source": "Rau_Lee_Kee_2014",
            "source_url": "https://doi.org/10.1103/PhysRevLett.112.077204",
            "citation_locator": "generic spin model for honeycomb iridates",
        },
        {
            "name": "kagome_spin_half_heisenberg_energy_reference",
            "model": "spin_1_2_kagome_heisenberg",
            "lattice": "kagome",
            "hamiltonian": "J NN Heisenberg",
            "hamiltonian_terms": ["heisenberg", "nearest_neighbor", "frustrated"],
            "parameters": {"spin": 0.5, "exchange": 1.0},
            "observable": "ground_state_energy",
            "comparison_kind": "paper_numeric",
            "backend_needed": "dmrg",
            "standard_result": {"energy_per_site_approx": -0.4386, "tolerance": 5.0e-4},
            "source": "Yan_Huse_White_2011",
            "source_url": "https://doi.org/10.1126/science.1201080",
            "citation_locator": "kagome spin-half DMRG energy benchmark",
        },
        {
            "name": "kagome_j1_j2_heisenberg_phase_diagram_reference",
            "model": "spin_1_2_kagome_j1_j2_heisenberg",
            "lattice": "kagome",
            "hamiltonian": "J1 NN + J2 NNN Heisenberg",
            "hamiltonian_terms": ["heisenberg", "j1", "j2", "frustrated"],
            "parameters": {"spin": 0.5},
            "observable": "phase_diagram",
            "comparison_kind": "paper_numeric",
            "backend_needed": "dmrg_or_ed",
            "standard_result": {"phases": ["spin_liquid", "q0_order", "sqrt3xsqrt3_order"]},
            "source": "Kolley_Depinbrock_McCulloch_Schollwoeck_2015",
            "source_url": "https://doi.org/10.1103/PhysRevB.91.104418",
            "citation_locator": "kagome J1-J2 DMRG phase diagram",
        },
        {
            "name": "kagome_dzyaloshinskii_moriya_critical_reference",
            "model": "spin_1_2_kagome_dm_heisenberg",
            "lattice": "kagome",
            "hamiltonian": "J Heisenberg + Dz out-of-plane DM",
            "hamiltonian_terms": ["heisenberg", "dzyaloshinskii_moriya", "frustrated"],
            "parameters": {"spin": 0.5},
            "observable": "quantum_critical_ratio",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed_or_dmrg",
            "standard_result": {"critical_d_over_j_approx": 0.1},
            "source": "Cepas_Fong_Leung_Lhuillier_2008",
            "source_url": "https://doi.org/10.1103/PhysRevB.78.140405",
            "citation_locator": "kagome DM critical coupling estimate",
        },
        {
            "name": "pyrochlore_heisenberg_coulomb_phase_flat_band",
            "model": "classical_pyrochlore_heisenberg_afm",
            "lattice": "pyrochlore",
            "hamiltonian": "J NN Heisenberg",
            "hamiltonian_terms": ["heisenberg", "nearest_neighbor", "frustrated", "flat_band"],
            "parameters": {"classical": True},
            "observable": "coulomb_phase",
            "comparison_kind": "paper_formula",
            "backend_needed": "glt",
            "standard_result": {"local_constraint": "sum_tetrahedron_spins_zero", "lowest_lt_flat_band": True},
            "source": "Moessner_Chalker_1998",
            "source_url": "https://doi.org/10.1103/PhysRevLett.80.2929",
            "citation_locator": "pyrochlore Heisenberg Coulomb phase",
        },
        {
            "name": "pyrochlore_dipolar_spin_ice_pauling_entropy",
            "model": "dipolar_spin_ice_pyrochlore",
            "lattice": "pyrochlore",
            "hamiltonian": "local-axis Ising + dipolar interaction",
            "hamiltonian_terms": ["ising", "local_axis", "dipolar", "spin_ice"],
            "parameters": {"classical": True},
            "observable": "residual_entropy",
            "comparison_kind": "paper_formula",
            "backend_needed": "mc",
            "standard_result": {"pauling_entropy_per_spin": 0.5 * math.log(1.5)},
            "source": "Bramwell_Gingras_2001",
            "source_url": "https://doi.org/10.1126/science.1059820",
            "citation_locator": "spin ice Pauling entropy",
        },
        {
            "name": "pyrochlore_anisotropic_exchange_jzz_jpm_reference",
            "model": "rare_earth_pyrochlore_anisotropic_exchange",
            "lattice": "pyrochlore",
            "hamiltonian": "Jzz,Jpm,Jpmpm,Jzpm nearest-neighbor pseudospin exchange",
            "hamiltonian_terms": ["anisotropic_exchange", "jzz", "jpm", "jzpm", "pseudospin"],
            "parameters": {"effective_spin": 0.5},
            "observable": "exchange_parameterization",
            "comparison_kind": "paper_formula",
            "backend_needed": "anisotropic_exchange",
            "standard_result": {"couplings": ["Jzz", "Jpm", "Jpmpm", "Jzpm"]},
            "source": "Ross_Savary_Gaulin_Balents_2011",
            "source_url": "https://doi.org/10.1103/PhysRevX.1.021002",
            "citation_locator": "rare-earth pyrochlore anisotropic nearest-neighbor exchange",
        },
        {
            "name": "diamond_j1_j2_spiral_surface_reference",
            "model": "diamond_j1_j2_heisenberg",
            "lattice": "diamond",
            "hamiltonian": "J1 NN + J2 NNN Heisenberg",
            "hamiltonian_terms": ["heisenberg", "j1", "j2", "spiral_surface"],
            "parameters": {"classical": True, "lifshitz_ratio_j2_over_j1": 0.125},
            "observable": "spiral_surface",
            "comparison_kind": "paper_formula",
            "backend_needed": "glt",
            "standard_result": {"spiral_surface_for_j2_over_j1_gt": 0.125},
            "source": "Bergman_Alicea_Gull_Trebst_Balents_2007",
            "source_url": "https://arxiv.org/abs/cond-mat/0612001",
            "citation_locator": "diamond-lattice spiral spin liquid surface",
        },
        {
            "name": "fcc_j1_j2_heisenberg_type_order_reference",
            "model": "fcc_j1_j2_heisenberg",
            "lattice": "fcc",
            "hamiltonian": "J1 NN + J2 NNN Heisenberg",
            "hamiltonian_terms": ["heisenberg", "j1", "j2", "frustrated"],
            "parameters": {"classical": True},
            "observable": "ordering_type",
            "comparison_kind": "review_phase_diagram",
            "backend_needed": "glt",
            "standard_result": {"common_orders": ["type_I", "type_II", "type_III"]},
            "source": "Lines_1963",
            "source_url": "https://doi.org/10.1103/PhysRev.131.546",
            "citation_locator": "fcc Heisenberg antiferromagnet type orders",
        },
        {
            "name": "bcc_j1_j2_heisenberg_collinear_reference",
            "model": "bcc_j1_j2_heisenberg",
            "lattice": "bcc",
            "hamiltonian": "J1 NN + J2 NNN Heisenberg",
            "hamiltonian_terms": ["heisenberg", "j1", "j2", "collinear"],
            "parameters": {"classical": True},
            "observable": "ordering_type",
            "comparison_kind": "review_phase_diagram",
            "backend_needed": "glt",
            "standard_result": {"contains_collinear_large_j2_phase": True},
            "source": "Smart_1966",
            "source_url": "https://doi.org/10.1002/9780470316517",
            "citation_locator": "bcc J1-J2 classical magnetic orders",
        },
        {
            "name": "sawtooth_chain_localized_magnon_flat_band",
            "model": "sawtooth_chain_heisenberg",
            "lattice": "sawtooth_chain",
            "hamiltonian": "base and zigzag Heisenberg exchanges",
            "hamiltonian_terms": ["heisenberg", "flat_band", "localized_magnon"],
            "parameters": {"saturation_field_regime": True},
            "observable": "localized_magnon",
            "comparison_kind": "paper_formula",
            "backend_needed": "magnon_ed",
            "standard_result": {"has_exact_localized_magnons": True},
            "source": "Derzhko_Richter_2006",
            "source_url": "https://doi.org/10.1140/epjb/e2006-00267-3",
            "citation_locator": "localized magnons on sawtooth chain",
        },
        {
            "name": "diamond_chain_localized_magnon_flat_band",
            "model": "diamond_chain_heisenberg",
            "lattice": "diamond_chain",
            "hamiltonian": "frustrated diamond-chain Heisenberg exchange",
            "hamiltonian_terms": ["heisenberg", "flat_band", "localized_magnon"],
            "parameters": {"saturation_field_regime": True},
            "observable": "localized_magnon",
            "comparison_kind": "paper_formula",
            "backend_needed": "magnon_ed",
            "standard_result": {"has_exact_localized_magnons": True},
            "source": "Derzhko_Richter_2006",
            "source_url": "https://doi.org/10.1140/epjb/e2006-00267-3",
            "citation_locator": "localized magnons on diamond chain",
        },
        {
            "name": "spin_ladder_rung_singlet_gap_reference",
            "model": "two_leg_heisenberg_ladder",
            "lattice": "ladder",
            "hamiltonian": "Jleg chains + Jrung rungs",
            "hamiltonian_terms": ["heisenberg", "ladder", "rung_singlet"],
            "parameters": {"spin": 0.5},
            "observable": "spin_gap",
            "comparison_kind": "paper_numeric",
            "backend_needed": "dmrg_or_ed",
            "standard_result": {"has_finite_spin_gap_for_antiferromagnetic_rungs": True},
            "source": "Dagotto_Rice_1996",
            "source_url": "https://doi.org/10.1126/science.271.5249.618",
            "citation_locator": "two-leg ladder spin gap review",
        },
        {
            "name": "hyperkagome_heisenberg_spin_liquid_reference",
            "model": "hyperkagome_heisenberg",
            "lattice": "hyperkagome",
            "hamiltonian": "J NN Heisenberg",
            "hamiltonian_terms": ["heisenberg", "frustrated", "three_dimensional"],
            "parameters": {"spin": 0.5},
            "observable": "spin_liquid_candidate",
            "comparison_kind": "paper_numeric",
            "backend_needed": "many_body_or_classical",
            "standard_result": {"spin_liquid_candidate": True},
            "source": "Lawler_Paramekanti_Kim_Balents_2008",
            "source_url": "https://doi.org/10.1103/PhysRevLett.101.197202",
            "citation_locator": "hyperkagome spin-liquid reference",
        },
        {
            "name": "square_j1_j3_classical_lifshitz_reference",
            "model": "square_j1_j3_heisenberg",
            "lattice": "square",
            "hamiltonian": "J1 NN + J3 third-neighbor Heisenberg",
            "hamiltonian_terms": ["heisenberg", "j1", "j3", "spiral"],
            "parameters": {"classical": True},
            "observable": "lifshitz_point",
            "comparison_kind": "paper_formula",
            "backend_needed": "glt",
            "standard_result": {"spiral_condition": "cos(Q)=J1/(4J3)"},
            "source": "Iqbal_Bechmann_Richter_2018",
            "source_url": "https://arxiv.org/abs/1804.04308",
            "citation_locator": "square J1-J3 classical spiral condition",
        },
        {
            "name": "triangular_nn_classical_120_reference",
            "model": "triangular_nn_heisenberg",
            "lattice": "triangular",
            "hamiltonian": "J NN Heisenberg",
            "hamiltonian_terms": ["heisenberg", "nearest_neighbor", "120_degree"],
            "parameters": {"classical": True},
            "observable": "ordering_vector",
            "comparison_kind": "paper_formula",
            "backend_needed": "glt",
            "standard_result": {"order": "120_degree", "q_reciprocal": [1.0 / 3.0, 2.0 / 3.0, 0.0]},
            "source": "Huse_Elser_1988",
            "source_url": "https://doi.org/10.1103/PhysRevLett.60.2531",
            "citation_locator": "triangular Heisenberg 120-degree order",
        },
        {
            "name": "simple_cubic_j1_j2_collinear_reference",
            "model": "simple_cubic_j1_j2_heisenberg",
            "lattice": "simple_cubic",
            "hamiltonian": "J1 NN + J2 NNN Heisenberg",
            "hamiltonian_terms": ["heisenberg", "j1", "j2", "collinear"],
            "parameters": {"classical": True},
            "observable": "phase_boundary",
            "comparison_kind": "paper_formula",
            "backend_needed": "glt",
            "standard_result": {"neel_to_collinear_boundary_j2_over_j1": 0.25},
            "source": "Pinettes_Diep_1998",
            "source_url": "https://doi.org/10.1063/1.367780",
            "citation_locator": "simple-cubic J1-J2 phase boundary",
        },
        {
            "name": "honeycomb_j1_j2_spiral_ring_reference",
            "model": "honeycomb_j1_j2_heisenberg",
            "lattice": "honeycomb",
            "hamiltonian": "J1 NN + J2 NNN Heisenberg",
            "hamiltonian_terms": ["heisenberg", "j1", "j2", "spiral_ring"],
            "parameters": {"classical": True},
            "observable": "spiral_ring",
            "comparison_kind": "paper_formula",
            "backend_needed": "glt",
            "standard_result": {"ring_condition": "|1+exp(iq1)+exp(iq2)|=|J1|/(2J2)"},
            "source": "Bergman_Alicea_Gull_Trebst_Balents_2007",
            "source_url": "https://arxiv.org/abs/cond-mat/0612001",
            "citation_locator": "honeycomb spiral spin liquid ring condition",
        },
        {
            "name": "checkerboard_heisenberg_plaquette_reference",
            "model": "checkerboard_heisenberg",
            "lattice": "checkerboard",
            "hamiltonian": "crossed-square Heisenberg exchange",
            "hamiltonian_terms": ["heisenberg", "frustrated", "plaquette"],
            "parameters": {"spin": 0.5},
            "observable": "plaquette_order_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed_or_dmrg",
            "standard_result": {"plaquette_order_candidate": True},
            "source": "Sindzingre_Lhuillier_2002",
            "source_url": "https://doi.org/10.1209/epl/i2002-00102-3",
            "citation_locator": "checkerboard antiferromagnet plaquette phase reference",
        },
        {
            "name": "lieb_lattice_heisenberg_ferrimagnet_reference",
            "model": "lieb_lattice_heisenberg",
            "lattice": "lieb",
            "hamiltonian": "bipartite Heisenberg exchange with sublattice imbalance",
            "hamiltonian_terms": ["heisenberg", "bipartite", "sublattice_imbalance"],
            "parameters": {"spin": 0.5},
            "observable": "lieb_mattis_ferrimagnetism",
            "comparison_kind": "theorem",
            "backend_needed": "diagnostic",
            "standard_result": {"ground_state_spin_per_unit_cell": 0.5},
            "source": "Lieb_Mattis_1962",
            "source_url": "https://doi.org/10.1063/1.1724276",
            "citation_locator": "Lieb-Mattis bipartite ferrimagnetism theorem",
        },
        {
            "name": "j1_j2_chain_bkt_transition_reference",
            "model": "spin_1_2_j1_j2_chain",
            "lattice": "chain",
            "hamiltonian": "J1 NN + J2 NNN Heisenberg",
            "hamiltonian_terms": ["heisenberg", "j1", "j2", "bkt"],
            "parameters": {"spin": 0.5},
            "observable": "dimerization_transition",
            "comparison_kind": "paper_numeric",
            "backend_needed": "dmrg_or_ed",
            "standard_result": {"critical_j2_over_j1_approx": 0.2411},
            "source": "Okamoto_Nomura_1992",
            "source_url": "https://doi.org/10.1016/0375-9601(92)90923-5",
            "citation_locator": "J1-J2 spin-half chain dimerization transition",
        },
        {
            "name": "takhtajan_babujian_spin1_critical_point",
            "model": "spin_1_bilinear_biquadratic_chain",
            "lattice": "chain",
            "hamiltonian": "cos(theta) Si.Sj + sin(theta)(Si.Sj)^2",
            "hamiltonian_terms": ["heisenberg", "biquadratic", "spin1", "critical"],
            "parameters": {"theta": -math.pi / 4.0},
            "observable": "critical_point",
            "comparison_kind": "exact_solution",
            "backend_needed": "bethe_or_ed",
            "standard_result": {"theta_radians": -math.pi / 4.0, "is_integrable": True},
            "source": "Babujian_1982",
            "source_url": "https://doi.org/10.1016/0370-2693(82)90471-0",
            "citation_locator": "Takhtajan-Babujian spin-1 critical point",
        },
        {
            "name": "uimin_lai_sutherland_spin1_su3_point",
            "model": "spin_1_bilinear_biquadratic_chain",
            "lattice": "chain",
            "hamiltonian": "cos(theta) Si.Sj + sin(theta)(Si.Sj)^2",
            "hamiltonian_terms": ["heisenberg", "biquadratic", "spin1", "su3"],
            "parameters": {"theta": math.pi / 4.0},
            "observable": "integrable_point",
            "comparison_kind": "exact_solution",
            "backend_needed": "bethe_or_ed",
            "standard_result": {"theta_radians": math.pi / 4.0, "su3_symmetric": True},
            "source": "Uimin_Lai_Sutherland",
            "source_url": "https://doi.org/10.1016/0375-9601(74)90701-2",
            "citation_locator": "ULS SU(3) point in spin-1 bilinear-biquadratic chain",
        },
        {
            "name": "kitaev_honeycomb_abelian_nonabelian_field_gap_reference",
            "model": "kitaev_honeycomb_field",
            "lattice": "honeycomb",
            "hamiltonian": "Kitaev exchange plus magnetic field perturbation",
            "hamiltonian_terms": ["kitaev", "magnetic_field", "topological"],
            "parameters": {"spin": 0.5},
            "observable": "field_induced_gap",
            "comparison_kind": "paper_formula",
            "backend_needed": "kitaev_majorana",
            "standard_result": {"field_opens_non_abelian_gap": True},
            "source": "Kitaev_2006",
            "source_url": "https://doi.org/10.1016/j.aop.2005.10.005",
            "citation_locator": "Kitaev honeycomb field-induced non-Abelian phase",
        },
        {
            "name": "er2ti2o7_xy_pyrochlore_order_by_disorder_reference",
            "model": "xy_pyrochlore_antiferromagnet",
            "lattice": "pyrochlore",
            "hamiltonian": "local XY anisotropic exchange",
            "hamiltonian_terms": ["xy", "anisotropic_exchange", "order_by_disorder"],
            "parameters": {"rare_earth": "Er2Ti2O7"},
            "observable": "selected_order",
            "comparison_kind": "paper_numeric",
            "backend_needed": "anisotropic_exchange",
            "standard_result": {"psi2_order_selected": True},
            "source": "Savary_Balents_2012",
            "source_url": "https://doi.org/10.1103/PhysRevLett.108.037202",
            "citation_locator": "order by disorder in Er2Ti2O7 pyrochlore",
        },
        {
            "name": "quantum_spin_ice_u1_qsl_reference",
            "model": "quantum_spin_ice_pyrochlore",
            "lattice": "pyrochlore",
            "hamiltonian": "Jzz spin ice plus transverse exchange",
            "hamiltonian_terms": ["ising", "jzz", "jpm", "u1_spin_liquid"],
            "parameters": {"effective_spin": 0.5},
            "observable": "phase_reference",
            "comparison_kind": "paper_formula",
            "backend_needed": "gauge_theory_or_qmc",
            "standard_result": {"u1_quantum_spin_liquid_candidate": True},
            "source": "Hermele_Fisher_Balents_2004",
            "source_url": "https://doi.org/10.1103/PhysRevB.69.064404",
            "citation_locator": "U(1) quantum spin liquid in pyrochlore spin ice",
        },
        {
            "name": "breathing_kagome_heisenberg_reference",
            "model": "breathing_kagome_heisenberg",
            "lattice": "breathing_kagome",
            "hamiltonian": "J_up and J_down triangle Heisenberg exchanges",
            "hamiltonian_terms": ["heisenberg", "breathing", "frustrated"],
            "parameters": {"spin": 0.5},
            "observable": "phase_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed_or_dmrg",
            "standard_result": {"breathing_anisotropy_controls_trimerization": True},
            "source": "Repellin_Schroeter_Thomale_2017",
            "source_url": "https://doi.org/10.1103/PhysRevB.96.205124",
            "citation_locator": "breathing kagome Heisenberg reference",
        },
        {
            "name": "ruby_lattice_heisenberg_flat_band_reference",
            "model": "ruby_lattice_heisenberg",
            "lattice": "ruby",
            "hamiltonian": "Heisenberg exchange on ruby lattice",
            "hamiltonian_terms": ["heisenberg", "frustrated", "flat_band"],
            "parameters": {"spin": 0.5},
            "observable": "localized_magnon",
            "comparison_kind": "paper_formula",
            "backend_needed": "magnon_ed",
            "standard_result": {"supports_localized_magnons": True},
            "source": "Richter_Derzhko_Schulenburg_2004",
            "source_url": "https://doi.org/10.1103/PhysRevLett.93.107206",
            "citation_locator": "localized magnons on frustrated lattices",
        },
        {
            "name": "star_lattice_heisenberg_spin_liquid_reference",
            "model": "star_lattice_heisenberg",
            "lattice": "star",
            "hamiltonian": "J Heisenberg on star lattice",
            "hamiltonian_terms": ["heisenberg", "frustrated"],
            "parameters": {"spin": 0.5},
            "observable": "phase_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed_or_dmrg",
            "standard_result": {"spin_liquid_or_valence_bond_reference": True},
            "source": "Richter_Ihle_Drechsler_2004",
            "source_url": "https://doi.org/10.1103/PhysRevB.70.184414",
            "citation_locator": "star-lattice Heisenberg antiferromagnet reference",
        },
        {
            "name": "maple_leaf_lattice_heisenberg_reference",
            "model": "maple_leaf_lattice_heisenberg",
            "lattice": "maple_leaf",
            "hamiltonian": "J Heisenberg on maple-leaf lattice",
            "hamiltonian_terms": ["heisenberg", "frustrated"],
            "parameters": {"spin": 0.5},
            "observable": "phase_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed_or_dmrg",
            "standard_result": {"frustrated_order_reference": True},
            "source": "Farnell_Richter_Bishop_2009",
            "source_url": "https://doi.org/10.1140/epjb/e2009-00307-4",
            "citation_locator": "maple-leaf lattice Heisenberg antiferromagnet",
        },
        {
            "name": "shuriken_lattice_heisenberg_reference",
            "model": "shuriken_lattice_heisenberg",
            "lattice": "shuriken",
            "hamiltonian": "Heisenberg exchange on square-kagome/shuriken lattice",
            "hamiltonian_terms": ["heisenberg", "frustrated", "flat_band"],
            "parameters": {"spin": 0.5},
            "observable": "phase_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed_or_dmrg",
            "standard_result": {"square_kagome_reference": True},
            "source": "Richter_Schnack_Schulenburg_2004",
            "source_url": "https://doi.org/10.1103/PhysRevB.70.174454",
            "citation_locator": "square-kagome/shuriken Heisenberg model reference",
        },
        {
            "name": "j1_j2_j3_square_quantum_phase_reference",
            "model": "spin_1_2_square_j1_j2_j3_heisenberg",
            "lattice": "square",
            "hamiltonian": "J1 NN + J2 diagonal + J3 third-neighbor Heisenberg",
            "hamiltonian_terms": ["heisenberg", "j1", "j2", "j3", "frustrated"],
            "parameters": {"spin": 0.5},
            "observable": "phase_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed_or_dmrg",
            "standard_result": {"multiple_paramagnetic_regions": True},
            "source": "Fouet_Mambrini_Sindzingre_Lhuillier_2001",
            "source_url": "https://doi.org/10.1103/PhysRevB.67.054411",
            "citation_locator": "square J1-J2-J3 quantum phase diagram reference",
        },
        {
            "name": "honeycomb_spin_half_j1_j2_quantum_phase_reference",
            "model": "spin_1_2_honeycomb_j1_j2_heisenberg",
            "lattice": "honeycomb",
            "hamiltonian": "J1 NN + J2 NNN Heisenberg",
            "hamiltonian_terms": ["heisenberg", "j1", "j2", "frustrated"],
            "parameters": {"spin": 0.5},
            "observable": "phase_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed_or_dmrg",
            "standard_result": {"intermediate_nonmagnetic_phase_candidate": True},
            "source": "Meng_Wessel_2010",
            "source_url": "https://doi.org/10.1038/nature08942",
            "citation_locator": "honeycomb spin-half J1-J2 nonmagnetic phase reference",
        },
        {
            "name": "square_heisenberg_spin_wave_velocity_reference",
            "model": "spin_1_2_square_heisenberg_afm",
            "lattice": "square",
            "hamiltonian": "J NN Heisenberg",
            "hamiltonian_terms": ["heisenberg", "nearest_neighbor", "spin_wave_velocity"],
            "parameters": {"spin": 0.5, "exchange": 1.0},
            "observable": "spin_wave_velocity",
            "comparison_kind": "paper_numeric",
            "backend_needed": "qmc_or_lswt",
            "standard_result": {"renormalized_velocity_over_j_approx": 1.658},
            "source": "Sandvik_1997",
            "source_url": "https://doi.org/10.1103/PhysRevB.56.11678",
            "citation_locator": "square Heisenberg QMC spin-wave velocity reference",
        },
        {
            "name": "haldane_shastry_chain_exact_ground_state",
            "model": "haldane_shastry_chain",
            "lattice": "chain",
            "hamiltonian": "1/r^2 long-range spin-1/2 Heisenberg exchange",
            "hamiltonian_terms": ["heisenberg", "long_range", "integrable"],
            "parameters": {"spin": 0.5},
            "observable": "exact_ground_state",
            "comparison_kind": "exact_solution",
            "backend_needed": "long_range_ed",
            "standard_result": {"has_exact_jastrow_ground_state": True},
            "source": "Haldane_1988",
            "source_url": "https://doi.org/10.1103/PhysRevLett.60.635",
            "citation_locator": "Haldane-Shastry inverse-square spin-chain exact state",
        },
        {
            "name": "sr_cu2_bo3_2_shastry_sutherland_material_reference",
            "model": "sr_cu2_bo3_2",
            "lattice": "shastry_sutherland",
            "hamiltonian": "Shastry-Sutherland Heisenberg model for SrCu2(BO3)2",
            "hamiltonian_terms": ["heisenberg", "orthogonal_dimer", "material"],
            "parameters": {"material": "SrCu2(BO3)2"},
            "observable": "material_model_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed_or_dmrg",
            "standard_result": {"orthogonal_dimer_material": True, "magnetization_plateaus": True},
            "source": "Kageyama_1999",
            "source_url": "https://doi.org/10.1103/PhysRevLett.82.3168",
            "citation_locator": "SrCu2(BO3)2 Shastry-Sutherland material identification",
        },
        {
            "name": "alpha_rucl3_kitaev_gamma_zigzag_reference",
            "model": "alpha_rucl3_effective_spin_model",
            "lattice": "honeycomb",
            "hamiltonian": "Kitaev-Heisenberg-Gamma effective pseudospin Hamiltonian",
            "hamiltonian_terms": ["kitaev", "gamma", "heisenberg", "material", "zigzag"],
            "parameters": {"material": "alpha-RuCl3"},
            "observable": "zigzag_order_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "anisotropic_exchange",
            "standard_result": {"zigzag_order": True, "kitaev_gamma_model_reference": True},
            "source": "Winter_Li_Jeschke_Valenti_2016",
            "source_url": "https://doi.org/10.1103/PhysRevB.93.214431",
            "citation_locator": "alpha-RuCl3 Kitaev-Gamma effective model reference",
        },
        {
            "name": "nacuo2_triangular_heisenberg_material_reference",
            "model": "nacuo2_triangular_heisenberg",
            "lattice": "triangular",
            "hamiltonian": "triangular-lattice spin-1/2 Heisenberg exchange",
            "hamiltonian_terms": ["heisenberg", "nearest_neighbor", "material"],
            "parameters": {"material": "NaCuO2"},
            "observable": "material_reference",
            "comparison_kind": "material_reference",
            "backend_needed": "glt_or_many_body",
            "standard_result": {"triangular_material_reference": True},
            "source": "Triangular_Material_Review",
            "source_url": "https://doi.org/10.1088/0953-8984/19/14/145259",
            "citation_locator": "triangular antiferromagnet material reference",
        },
        {
            "name": "cs2cucl4_anisotropic_triangular_spiral_reference",
            "model": "cs2cucl4_anisotropic_triangular",
            "lattice": "triangular",
            "hamiltonian": "anisotropic triangular Heisenberg exchange",
            "hamiltonian_terms": ["heisenberg", "anisotropic", "spiral", "material"],
            "parameters": {"material": "Cs2CuCl4"},
            "observable": "spiral_order_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "glt_or_lswt",
            "standard_result": {"incommensurate_spiral_order": True},
            "source": "Coldea_Tennant_Tylczynski_2003",
            "source_url": "https://doi.org/10.1103/PhysRevB.68.134424",
            "citation_locator": "Cs2CuCl4 anisotropic triangular spiral reference",
        },
        {
            "name": "herbertsmithite_kagome_qsl_reference",
            "model": "herbertsmithite_kagome_heisenberg",
            "lattice": "kagome",
            "hamiltonian": "spin-1/2 kagome Heisenberg antiferromagnet",
            "hamiltonian_terms": ["heisenberg", "nearest_neighbor", "material", "spin_liquid"],
            "parameters": {"material": "ZnCu3(OH)6Cl2"},
            "observable": "material_qsl_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "dmrg_or_experiment",
            "standard_result": {"qsl_candidate": True},
            "source": "Shores_Nytko_Bartlett_Nocera_2005",
            "source_url": "https://doi.org/10.1021/ja053891p",
            "citation_locator": "herbertsmithite kagome material synthesis/reference",
        },
        {
            "name": "volborthite_kagome_distorted_reference",
            "model": "volborthite_distorted_kagome",
            "lattice": "kagome",
            "hamiltonian": "distorted kagome Heisenberg exchange",
            "hamiltonian_terms": ["heisenberg", "distorted", "material"],
            "parameters": {"material": "volborthite"},
            "observable": "material_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "anisotropic_exchange",
            "standard_result": {"distorted_kagome_reference": True},
            "source": "Hiroi_2001",
            "source_url": "https://doi.org/10.1143/JPSJ.70.3377",
            "citation_locator": "volborthite distorted kagome reference",
        },
        {
            "name": "kapellasite_kagome_j1_jd_reference",
            "model": "kapellasite_kagome_j1_jd",
            "lattice": "kagome",
            "hamiltonian": "kagome J1-Jd-J2 exchange model",
            "hamiltonian_terms": ["heisenberg", "j1", "jd", "material"],
            "parameters": {"material": "kapellasite"},
            "observable": "material_exchange_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "glt_or_ed",
            "standard_result": {"competing_kagome_exchanges": True},
            "source": "Fak_2012",
            "source_url": "https://doi.org/10.1103/PhysRevLett.109.037208",
            "citation_locator": "kapellasite kagome exchange model reference",
        },
        {
            "name": "dy2ti2o7_spin_ice_entropy_reference",
            "model": "dy2ti2o7_spin_ice",
            "lattice": "pyrochlore",
            "hamiltonian": "dipolar spin ice local-axis Ising model",
            "hamiltonian_terms": ["ising", "local_axis", "dipolar", "material", "spin_ice"],
            "parameters": {"material": "Dy2Ti2O7"},
            "observable": "residual_entropy",
            "comparison_kind": "paper_numeric",
            "backend_needed": "mc_or_experiment",
            "standard_result": {"pauling_entropy_observed": True},
            "source": "Ramirez_1999",
            "source_url": "https://doi.org/10.1038/19242",
            "citation_locator": "Dy2Ti2O7 spin-ice entropy reference",
        },
        {
            "name": "ho2ti2o7_spin_ice_neutron_reference",
            "model": "ho2ti2o7_spin_ice",
            "lattice": "pyrochlore",
            "hamiltonian": "dipolar spin ice local-axis Ising model",
            "hamiltonian_terms": ["ising", "local_axis", "dipolar", "material", "spin_ice"],
            "parameters": {"material": "Ho2Ti2O7"},
            "observable": "neutron_scattering_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "mc_or_experiment",
            "standard_result": {"spin_ice_correlations": True},
            "source": "Bramwell_2001",
            "source_url": "https://doi.org/10.1103/PhysRevLett.87.047205",
            "citation_locator": "Ho2Ti2O7 spin-ice neutron scattering reference",
        },
        {
            "name": "yb2ti2o7_pyrochlore_exchange_reference",
            "model": "yb2ti2o7_anisotropic_pyrochlore",
            "lattice": "pyrochlore",
            "hamiltonian": "anisotropic rare-earth pyrochlore exchange",
            "hamiltonian_terms": ["anisotropic_exchange", "jzz", "jpm", "material"],
            "parameters": {"material": "Yb2Ti2O7"},
            "observable": "exchange_parameter_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "anisotropic_exchange",
            "standard_result": {"anisotropic_exchange_fit_reference": True},
            "source": "Ross_2011",
            "source_url": "https://doi.org/10.1103/PhysRevX.1.021002",
            "citation_locator": "Yb2Ti2O7 anisotropic exchange parameterization",
        },
        {
            "name": "tb2ti2o7_pyrochlore_spin_liquid_reference",
            "model": "tb2ti2o7_pyrochlore",
            "lattice": "pyrochlore",
            "hamiltonian": "frustrated rare-earth pyrochlore exchange",
            "hamiltonian_terms": ["anisotropic_exchange", "material", "spin_liquid"],
            "parameters": {"material": "Tb2Ti2O7"},
            "observable": "spin_liquid_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "anisotropic_exchange",
            "standard_result": {"spin_liquid_candidate": True},
            "source": "Gardner_1999",
            "source_url": "https://doi.org/10.1103/PhysRevLett.82.1012",
            "citation_locator": "Tb2Ti2O7 pyrochlore spin-liquid reference",
        },
        {
            "name": "pr2zr2o7_quantum_spin_ice_reference",
            "model": "pr2zr2o7_quantum_spin_ice",
            "lattice": "pyrochlore",
            "hamiltonian": "non-Kramers quantum spin ice exchange",
            "hamiltonian_terms": ["ising", "jzz", "jpm", "material", "quantum_spin_ice"],
            "parameters": {"material": "Pr2Zr2O7"},
            "observable": "quantum_spin_ice_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "anisotropic_exchange",
            "standard_result": {"quantum_spin_ice_candidate": True},
            "source": "Kimura_2013",
            "source_url": "https://doi.org/10.1038/ncomms2914",
            "citation_locator": "Pr2Zr2O7 quantum spin ice reference",
        },
        {
            "name": "na4ir3o8_hyperkagome_material_reference",
            "model": "na4ir3o8_hyperkagome",
            "lattice": "hyperkagome",
            "hamiltonian": "hyperkagome spin-1/2 Heisenberg model",
            "hamiltonian_terms": ["heisenberg", "material", "three_dimensional", "frustrated"],
            "parameters": {"material": "Na4Ir3O8"},
            "observable": "material_qsl_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "many_body_or_experiment",
            "standard_result": {"hyperkagome_qsl_candidate": True},
            "source": "Okamoto_2007",
            "source_url": "https://doi.org/10.1103/PhysRevLett.99.137207",
            "citation_locator": "Na4Ir3O8 hyperkagome spin-liquid reference",
        },
        {
            "name": "li2iro3_hyperhoneycomb_kitaev_reference",
            "model": "beta_li2iro3_hyperhoneycomb",
            "lattice": "hyperhoneycomb",
            "hamiltonian": "3D Kitaev-Heisenberg-Gamma model",
            "hamiltonian_terms": ["kitaev", "gamma", "heisenberg", "material", "three_dimensional"],
            "parameters": {"material": "beta-Li2IrO3"},
            "observable": "material_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "anisotropic_exchange",
            "standard_result": {"hyperhoneycomb_kitaev_material": True},
            "source": "Takayama_2015",
            "source_url": "https://doi.org/10.1103/PhysRevLett.114.077202",
            "citation_locator": "hyperhoneycomb beta-Li2IrO3 Kitaev material reference",
        },
        {
            "name": "beta_li2iro3_spiral_kitaev_gamma_reference",
            "model": "beta_li2iro3_spiral_order",
            "lattice": "hyperhoneycomb",
            "hamiltonian": "Kitaev-Gamma-Heisenberg anisotropic exchange",
            "hamiltonian_terms": ["kitaev", "gamma", "spiral", "material"],
            "parameters": {"material": "beta-Li2IrO3"},
            "observable": "spiral_order_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "anisotropic_exchange",
            "standard_result": {"incommensurate_spiral_order": True},
            "source": "Biffin_2014",
            "source_url": "https://doi.org/10.1103/PhysRevB.90.205116",
            "citation_locator": "beta-Li2IrO3 incommensurate spiral order reference",
        },
        {
            "name": "square_jq_model_deconfined_critical_reference",
            "model": "square_jq_model",
            "lattice": "square",
            "hamiltonian": "Heisenberg J plus multi-spin Q interactions",
            "hamiltonian_terms": ["heisenberg", "multi_spin", "deconfined_criticality"],
            "parameters": {"spin": 0.5},
            "observable": "deconfined_critical_point",
            "comparison_kind": "paper_numeric",
            "backend_needed": "qmc",
            "standard_result": {"neel_to_vbs_transition": True},
            "source": "Sandvik_2007",
            "source_url": "https://doi.org/10.1103/PhysRevLett.98.227202",
            "citation_locator": "J-Q model deconfined criticality benchmark",
        },
        {
            "name": "j1_j2_square_dqcp_columnar_vbs_reference",
            "model": "square_j1_j2_vbs",
            "lattice": "square",
            "hamiltonian": "J1-J2 spin-half Heisenberg with VBS regime",
            "hamiltonian_terms": ["heisenberg", "j1", "j2", "vbs"],
            "parameters": {"spin": 0.5},
            "observable": "vbs_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "dmrg_or_vmc",
            "standard_result": {"columnar_or_plaquette_vbs_reference": True},
            "source": "Jiang_Yao_Balents_2012",
            "source_url": "https://doi.org/10.1103/PhysRevB.86.024424",
            "citation_locator": "square J1-J2 nonmagnetic/VBS benchmark",
        },
        {
            "name": "kagome_one_third_magnetization_plateau_reference",
            "model": "kagome_heisenberg_high_field",
            "lattice": "kagome",
            "hamiltonian": "kagome Heisenberg plus magnetic field",
            "hamiltonian_terms": ["heisenberg", "magnetic_field", "plateau"],
            "parameters": {"spin": 0.5},
            "observable": "magnetization_plateau",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed_or_dmrg",
            "standard_result": {"one_third_plateau": True},
            "source": "Nishimoto_2013",
            "source_url": "https://doi.org/10.1038/ncomms3287",
            "citation_locator": "kagome one-third magnetization plateau reference",
        },
        {
            "name": "shastry_sutherland_magnetization_plateaus_reference",
            "model": "shastry_sutherland_high_field",
            "lattice": "shastry_sutherland",
            "hamiltonian": "Shastry-Sutherland Heisenberg plus magnetic field",
            "hamiltonian_terms": ["heisenberg", "orthogonal_dimer", "magnetic_field", "plateau"],
            "parameters": {"material": "SrCu2(BO3)2"},
            "observable": "magnetization_plateaus",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed_or_dmrg",
            "standard_result": {"fractional_plateaus_observed": True},
            "source": "Kageyama_1999",
            "source_url": "https://doi.org/10.1103/PhysRevLett.82.3168",
            "citation_locator": "Shastry-Sutherland material magnetization plateaus",
        },
        {
            "name": "triangular_heisenberg_spin_half_energy_reference",
            "model": "spin_1_2_triangular_heisenberg",
            "lattice": "triangular",
            "hamiltonian": "J NN Heisenberg",
            "hamiltonian_terms": ["heisenberg", "nearest_neighbor", "120_degree"],
            "parameters": {"spin": 0.5, "exchange": 1.0},
            "observable": "ground_state_energy",
            "comparison_kind": "paper_numeric",
            "backend_needed": "dmrg_or_vmc",
            "standard_result": {"energy_per_site_approx": -0.545, "tolerance": 5.0e-3},
            "source": "Capriotti_1999",
            "source_url": "https://doi.org/10.1103/PhysRevLett.82.3899",
            "citation_locator": "triangular spin-half Heisenberg ground-state energy reference",
        },
        {
            "name": "triangular_heisenberg_magnetization_plateau_reference",
            "model": "triangular_heisenberg_high_field",
            "lattice": "triangular",
            "hamiltonian": "triangular Heisenberg plus magnetic field",
            "hamiltonian_terms": ["heisenberg", "magnetic_field", "plateau"],
            "parameters": {"spin": 0.5},
            "observable": "magnetization_plateau",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed_or_dmrg",
            "standard_result": {"one_third_plateau": True},
            "source": "Chubukov_Golosov_1991",
            "source_url": "https://doi.org/10.1088/0953-8984/3/1/005",
            "citation_locator": "triangular antiferromagnet one-third plateau reference",
        },
        {
            "name": "honeycomb_haldane_kane_mele_hubbard_spin_model_reference",
            "model": "kane_mele_hubbard_strong_coupling",
            "lattice": "honeycomb",
            "hamiltonian": "strong-coupling spin model from Kane-Mele-Hubbard",
            "hamiltonian_terms": ["anisotropic_exchange", "spin_orbit", "hubbard_derived"],
            "parameters": {"lattice": "honeycomb"},
            "observable": "strong_coupling_reference",
            "comparison_kind": "paper_formula",
            "backend_needed": "anisotropic_exchange",
            "standard_result": {"spin_orbit_induced_anisotropy": True},
            "source": "Rachel_Le_Hur_2010",
            "source_url": "https://doi.org/10.1103/PhysRevB.82.075106",
            "citation_locator": "Kane-Mele-Hubbard strong-coupling spin model reference",
        },
        {
            "name": "square_dimerized_heisenberg_critical_reference",
            "model": "square_dimerized_heisenberg",
            "lattice": "square",
            "hamiltonian": "J and J' dimerized square-lattice Heisenberg",
            "hamiltonian_terms": ["heisenberg", "dimerized", "quantum_critical"],
            "parameters": {"spin": 0.5},
            "observable": "quantum_critical_point",
            "comparison_kind": "paper_numeric",
            "backend_needed": "qmc",
            "standard_result": {"neel_to_dimer_transition": True},
            "source": "Matsumoto_2001",
            "source_url": "https://doi.org/10.1103/PhysRevB.65.014407",
            "citation_locator": "dimerized square Heisenberg quantum critical reference",
        },
        {
            "name": "two_leg_ladder_strong_rung_exact_limit",
            "model": "two_leg_heisenberg_ladder_strong_rung",
            "lattice": "ladder",
            "hamiltonian": "Jleg chains + Jrung rungs",
            "hamiltonian_terms": ["heisenberg", "ladder", "rung_singlet", "exact_limit"],
            "parameters": {"j_leg": 0.0, "j_rung": 1.0},
            "observable": "exact_rung_singlet_energy",
            "comparison_kind": "exact_solution",
            "backend_needed": "ed_or_analytic",
            "standard_result": {"energy_per_rung": -0.75, "gap_to_triplet": 1.0},
            "source": "Dagotto_Rice_1996",
            "source_url": "https://doi.org/10.1126/science.271.5249.618",
            "citation_locator": "two-leg ladder strong-rung limit",
        },
        {
            "name": "spin1_chain_large_d_transition_reference",
            "model": "spin_1_heisenberg_single_ion_chain",
            "lattice": "chain",
            "hamiltonian": "spin-1 Heisenberg chain plus D Sz^2",
            "hamiltonian_terms": ["heisenberg", "single_ion_anisotropy", "spin1", "large_d"],
            "parameters": {"spin": 1.0},
            "observable": "haldane_large_d_transition",
            "comparison_kind": "paper_numeric",
            "backend_needed": "dmrg_or_ed",
            "standard_result": {"large_d_transition_reference": True},
            "source": "Chen_Hida_Sanctuary_2003",
            "source_url": "https://doi.org/10.1103/PhysRevB.67.104401",
            "citation_locator": "spin-1 chain Haldane-large-D transition reference",
        },
    ]
)


LITERATURE_STANDARD_RESULTS.extend(
    [
        {
            "name": "xx_spin_half_chain_free_fermion_energy",
            "model": "spin_1_2_xx_chain",
            "lattice": "chain",
            "hamiltonian": "J sum (Sx_i Sx_j + Sy_i Sy_j)",
            "hamiltonian_terms": ["xx", "free_fermion", "nearest_neighbor"],
            "parameters": {"spin": 0.5, "exchange": 1.0},
            "observable": "thermodynamic_limit_ground_state_energy",
            "comparison_kind": "exact_solution",
            "backend_needed": "free_fermion_or_ed",
            "standard_result": {"energy_per_site": -1.0 / math.pi},
            "source": "Lieb_Schultz_Mattis_1961",
            "source_url": "https://doi.org/10.1016/0003-4916(61)90115-4",
            "citation_locator": "Jordan-Wigner free-fermion XX-chain benchmark",
        },
        {
            "name": "xy_spin_half_chain_anisotropic_critical_line",
            "model": "spin_1_2_xy_chain_transverse_field",
            "lattice": "chain",
            "hamiltonian": "-sum [(1+gamma) SxSx + (1-gamma) SySy] - h sum Sz",
            "hamiltonian_terms": ["xy", "anisotropic", "transverse_field", "free_fermion"],
            "parameters": {"spin": 0.5},
            "observable": "critical_line",
            "comparison_kind": "exact_solution",
            "backend_needed": "free_fermion_or_ed",
            "standard_result": {"ising_critical_field": 1.0, "anisotropy_transition_gamma": 0.0},
            "source": "Barouch_McCoy_1971",
            "source_url": "https://doi.org/10.1103/PhysRevA.3.786",
            "citation_locator": "anisotropic XY chain exact free-fermion solution",
        },
        {
            "name": "j1_j2_chain_okamoto_nomura_critical_point",
            "model": "spin_1_2_j1_j2_chain",
            "lattice": "chain",
            "hamiltonian": "J1 sum Si.Si+1 + J2 sum Si.Si+2",
            "hamiltonian_terms": ["heisenberg", "j1", "j2", "frustrated", "dimerization"],
            "parameters": {"spin": 0.5},
            "observable": "dimerization_transition",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed_or_dmrg",
            "standard_result": {"critical_j2_over_j1": 0.2411, "tolerance": 5.0e-4},
            "source": "Okamoto_Nomura_1992",
            "source_url": "https://doi.org/10.1016/0375-9601(92)90823-5",
            "citation_locator": "level spectroscopy critical frustration in the J1-J2 chain",
        },
        {
            "name": "spin_peierls_chain_dimerization_reference",
            "model": "spin_peierls_heisenberg_chain",
            "lattice": "chain",
            "hamiltonian": "sum J(1 + delta (-1)^i) Si.Si+1",
            "hamiltonian_terms": ["heisenberg", "dimerized", "spin_peierls"],
            "parameters": {"spin": 0.5},
            "observable": "spin_gap_opens_with_dimerization",
            "comparison_kind": "paper_formula",
            "backend_needed": "field_theory_or_dmrg",
            "standard_result": {"finite_delta_opens_gap": True},
            "source": "Cross_Fisher_1979",
            "source_url": "https://doi.org/10.1103/PhysRevB.19.402",
            "citation_locator": "spin-Peierls chain dimerization gap scaling reference",
        },
        {
            "name": "lieb_liniger_delta_bose_gas_bethe_reference",
            "model": "lieb_liniger_bose_gas",
            "lattice": "continuum_1d",
            "hamiltonian": "1D bosons with repulsive delta interaction",
            "hamiltonian_terms": ["continuum", "delta_interaction", "bethe_ansatz"],
            "parameters": {"interaction": "repulsive"},
            "observable": "exact_solution_status",
            "comparison_kind": "exact_solution",
            "backend_needed": "bethe_ansatz",
            "standard_result": {"is_exactly_solved": True, "tonks_girardeau_limit_maps_to_free_fermions": True},
            "source": "Lieb_Liniger_1963",
            "source_url": "https://doi.org/10.1103/PhysRev.130.1605",
            "citation_locator": "Bethe-ansatz solution of 1D delta Bose gas",
        },
        {
            "name": "gaudin_yang_spin_half_fermion_bethe_reference",
            "model": "gaudin_yang_fermion_gas",
            "lattice": "continuum_1d",
            "hamiltonian": "spin-1/2 fermions with delta interaction",
            "hamiltonian_terms": ["continuum", "spin_half", "delta_interaction", "bethe_ansatz"],
            "parameters": {"spin": 0.5},
            "observable": "exact_solution_status",
            "comparison_kind": "exact_solution",
            "backend_needed": "nested_bethe_ansatz",
            "standard_result": {"is_exactly_solved": True},
            "source": "Yang_1967",
            "source_url": "https://doi.org/10.1103/PhysRevLett.19.1312",
            "citation_locator": "nested Bethe ansatz for 1D spin-1/2 fermions",
        },
        {
            "name": "square_heisenberg_spin_half_staggered_magnetization_reference",
            "model": "spin_1_2_square_heisenberg_afm",
            "lattice": "square",
            "hamiltonian": "J sum_<ij> Si.Sj",
            "hamiltonian_terms": ["heisenberg", "nearest_neighbor", "j1", "magnetization"],
            "parameters": {"spin": 0.5, "exchange": 1.0},
            "observable": "staggered_magnetization",
            "comparison_kind": "paper_numeric",
            "backend_needed": "qmc_or_large_ed",
            "standard_result": {"staggered_magnetization": 0.30743, "tolerance": 5.0e-5},
            "source": "Sandvik_1997",
            "source_url": "https://doi.org/10.1103/PhysRevB.56.11678",
            "citation_locator": "square-lattice S=1/2 Heisenberg staggered magnetization benchmark",
        },
        {
            "name": "square_heisenberg_spin_half_spin_stiffness_reference",
            "model": "spin_1_2_square_heisenberg_afm",
            "lattice": "square",
            "hamiltonian": "J sum_<ij> Si.Sj",
            "hamiltonian_terms": ["heisenberg", "nearest_neighbor", "j1", "spin_stiffness"],
            "parameters": {"spin": 0.5, "exchange": 1.0},
            "observable": "spin_stiffness",
            "comparison_kind": "paper_numeric",
            "backend_needed": "qmc",
            "standard_result": {"rho_s_over_j": 0.1808, "tolerance": 1.0e-3},
            "source": "Sandvik_1997",
            "source_url": "https://doi.org/10.1103/PhysRevB.56.11678",
            "citation_locator": "square-lattice S=1/2 Heisenberg stiffness benchmark",
        },
        {
            "name": "cubic_ising_critical_temperature_reference",
            "model": "classical_cubic_ising",
            "lattice": "simple_cubic",
            "hamiltonian": "-J sum sigma_i sigma_j",
            "hamiltonian_terms": ["ising", "nearest_neighbor", "classical"],
            "parameters": {"exchange": 1.0},
            "observable": "critical_temperature",
            "comparison_kind": "paper_numeric",
            "backend_needed": "mc_or_series",
            "standard_result": {"tc_over_j": 4.511524, "tolerance": 5.0e-6},
            "source": "Ferrenberg_Landau_Wong_1992",
            "source_url": "https://doi.org/10.1103/PhysRevLett.69.3382",
            "citation_locator": "3D simple-cubic Ising critical temperature benchmark",
        },
        {
            "name": "triangular_ising_ferromagnet_exact_tc",
            "model": "classical_triangular_ising",
            "lattice": "triangular",
            "hamiltonian": "-J sum sigma_i sigma_j",
            "hamiltonian_terms": ["ising", "nearest_neighbor", "classical", "ferromagnetic"],
            "parameters": {"exchange": 1.0},
            "observable": "critical_temperature",
            "comparison_kind": "exact_solution",
            "backend_needed": "transfer_matrix",
            "standard_result": {"tc_over_j": 4.0 / math.log(3.0)},
            "source": "Houtappel_1950",
            "source_url": "https://doi.org/10.1016/S0031-8914(50)80099-3",
            "citation_locator": "triangular-lattice Ising exact critical temperature",
        },
        {
            "name": "honeycomb_ising_ferromagnet_exact_tc",
            "model": "classical_honeycomb_ising",
            "lattice": "honeycomb",
            "hamiltonian": "-J sum sigma_i sigma_j",
            "hamiltonian_terms": ["ising", "nearest_neighbor", "classical", "ferromagnetic"],
            "parameters": {"exchange": 1.0},
            "observable": "critical_temperature",
            "comparison_kind": "exact_solution",
            "backend_needed": "transfer_matrix",
            "standard_result": {"tc_over_j": 2.0 / math.log(2.0 + math.sqrt(3.0))},
            "source": "Houtappel_1950",
            "source_url": "https://doi.org/10.1016/S0031-8914(50)80099-3",
            "citation_locator": "honeycomb-lattice Ising exact critical temperature",
        },
        {
            "name": "kagome_ising_ferromagnet_exact_tc",
            "model": "classical_kagome_ising",
            "lattice": "kagome",
            "hamiltonian": "-J sum sigma_i sigma_j",
            "hamiltonian_terms": ["ising", "nearest_neighbor", "classical", "ferromagnetic"],
            "parameters": {"exchange": 1.0},
            "observable": "critical_temperature",
            "comparison_kind": "exact_solution",
            "backend_needed": "transfer_matrix",
            "standard_result": {"tc_over_j": 4.0 / math.log(3.0 + 2.0 * math.sqrt(3.0))},
            "source": "Kano_Naya_1953",
            "source_url": "https://doi.org/10.1143/PTP.10.158",
            "citation_locator": "kagome-lattice Ising exact critical temperature",
        },
        {
            "name": "triangular_ising_antiferromagnet_residual_entropy",
            "model": "classical_triangular_ising_antiferromagnet",
            "lattice": "triangular",
            "hamiltonian": "J sum sigma_i sigma_j",
            "hamiltonian_terms": ["ising", "nearest_neighbor", "classical", "frustrated"],
            "parameters": {"exchange": 1.0},
            "observable": "residual_entropy",
            "comparison_kind": "exact_solution",
            "backend_needed": "transfer_matrix",
            "standard_result": {"residual_entropy_per_spin": 0.323066},
            "source": "Wannier_1950",
            "source_url": "https://doi.org/10.1103/PhysRev.79.357",
            "citation_locator": "triangular Ising antiferromagnet residual entropy",
        },
        {
            "name": "square_fully_frustrated_ising_residual_entropy_reference",
            "model": "fully_frustrated_square_ising",
            "lattice": "square",
            "hamiltonian": "Ising with one frustrated bond per plaquette",
            "hamiltonian_terms": ["ising", "classical", "fully_frustrated"],
            "parameters": {"frustrated_bonds_per_plaquette": 1},
            "observable": "residual_entropy",
            "comparison_kind": "exact_solution",
            "backend_needed": "transfer_matrix",
            "standard_result": {"macroscopic_ground_state_degeneracy": True},
            "source": "Villain_1977",
            "source_url": "https://doi.org/10.1088/0305-4470/10/10/014",
            "citation_locator": "fully frustrated Ising model degeneracy reference",
        },
        {
            "name": "kagome_ising_antiferromagnet_residual_entropy_reference",
            "model": "classical_kagome_ising_antiferromagnet",
            "lattice": "kagome",
            "hamiltonian": "J sum sigma_i sigma_j",
            "hamiltonian_terms": ["ising", "nearest_neighbor", "classical", "frustrated"],
            "parameters": {"exchange": 1.0},
            "observable": "residual_entropy",
            "comparison_kind": "exact_solution",
            "backend_needed": "transfer_matrix",
            "standard_result": {"macroscopic_ground_state_degeneracy": True},
            "source": "Kano_Naya_1953",
            "source_url": "https://doi.org/10.1143/PTP.10.158",
            "citation_locator": "kagome Ising antiferromagnet residual entropy reference",
        },
        {
            "name": "pyrochlore_heisenberg_afm_coulomb_phase_reference",
            "model": "classical_pyrochlore_heisenberg_afm",
            "lattice": "pyrochlore",
            "hamiltonian": "J sum_<ij> Si.Sj",
            "hamiltonian_terms": ["heisenberg", "nearest_neighbor", "classical", "coulomb_phase"],
            "parameters": {"exchange": 1.0},
            "observable": "ground_state_constraint",
            "comparison_kind": "paper_formula",
            "backend_needed": "classical_glt_or_mc",
            "standard_result": {"zero_total_spin_per_tetrahedron": True, "pinch_points": True},
            "source": "Moessner_Chalker_1998",
            "source_url": "https://doi.org/10.1103/PhysRevLett.80.2929",
            "citation_locator": "pyrochlore Heisenberg antiferromagnet Coulomb phase",
        },
        {
            "name": "checkerboard_heisenberg_afm_planar_pyrochlore_reference",
            "model": "checkerboard_heisenberg_antiferromagnet",
            "lattice": "checkerboard",
            "hamiltonian": "J sum_<ij> Si.Sj on crossed-square lattice",
            "hamiltonian_terms": ["heisenberg", "nearest_neighbor", "frustrated", "planar_pyrochlore"],
            "parameters": {"exchange": 1.0},
            "observable": "ground_state_constraint",
            "comparison_kind": "paper_formula",
            "backend_needed": "classical_glt_or_ed",
            "standard_result": {"zero_total_spin_per_crossed_plaquette": True},
            "source": "Canals_Lacroix_1998",
            "source_url": "https://doi.org/10.1103/PhysRevLett.80.2933",
            "citation_locator": "checkerboard/planar-pyrochlore Heisenberg antiferromagnet reference",
        },
        {
            "name": "j1_j2_honeycomb_neel_spin_liquid_transition_reference",
            "model": "spin_1_2_honeycomb_j1_j2_heisenberg",
            "lattice": "honeycomb",
            "hamiltonian": "J1 NN + J2 NNN Heisenberg",
            "hamiltonian_terms": ["heisenberg", "j1", "j2", "frustrated", "spin_liquid"],
            "parameters": {"spin": 0.5},
            "observable": "quantum_phase_window",
            "comparison_kind": "paper_numeric",
            "backend_needed": "dmrg_or_ed",
            "standard_result": {"intermediate_nonmagnetic_phase": True},
            "source": "Meng_Lang_Wessel_Assaad_Muramatsu_2010",
            "source_url": "https://doi.org/10.1038/nature08942",
            "citation_locator": "honeycomb frustrated spin-half model nonmagnetic phase reference",
        },
        {
            "name": "j1_j2_triangular_spin_liquid_window_reference",
            "model": "spin_1_2_triangular_j1_j2_heisenberg",
            "lattice": "triangular",
            "hamiltonian": "J1 NN + J2 NNN Heisenberg",
            "hamiltonian_terms": ["heisenberg", "j1", "j2", "frustrated", "spin_liquid"],
            "parameters": {"spin": 0.5},
            "observable": "quantum_phase_window",
            "comparison_kind": "paper_numeric",
            "backend_needed": "dmrg_or_ed",
            "standard_result": {"spin_liquid_window_approx": [0.07, 0.15]},
            "source": "Zhu_White_2015",
            "source_url": "https://doi.org/10.1103/PhysRevB.92.041105",
            "citation_locator": "triangular J1-J2 spin-liquid window reference",
        },
        {
            "name": "square_ring_exchange_neel_vbs_reference",
            "model": "square_heisenberg_ring_exchange",
            "lattice": "square",
            "hamiltonian": "J NN Heisenberg plus four-spin ring exchange",
            "hamiltonian_terms": ["heisenberg", "ring_exchange", "four_spin", "vbs"],
            "parameters": {"spin": 0.5},
            "observable": "neel_vbs_competition",
            "comparison_kind": "paper_numeric",
            "backend_needed": "qmc_or_ed",
            "standard_result": {"ring_exchange_drives_vbs_phase": True},
            "source": "Sandvik_Daane_2002",
            "source_url": "https://doi.org/10.1103/PhysRevB.66.014418",
            "citation_locator": "square-lattice ring-exchange Neel to VBS benchmark",
        },
        {
            "name": "honeycomb_j1_j2_kitaev_material_na2iro3_reference",
            "model": "na2iro3_honeycomb_kitaev_heisenberg",
            "lattice": "honeycomb",
            "hamiltonian": "Kitaev-Heisenberg honeycomb model for Na2IrO3",
            "hamiltonian_terms": ["kitaev", "heisenberg", "bond_dependent", "material"],
            "parameters": {"material": "Na2IrO3"},
            "observable": "material_model_reference",
            "comparison_kind": "paper_formula",
            "backend_needed": "anisotropic_exchange",
            "standard_result": {"zigzag_order_relevant": True},
            "source": "Chaloupka_Jackeli_Khaliullin_2010",
            "source_url": "https://doi.org/10.1103/PhysRevLett.105.027204",
            "citation_locator": "Na2IrO3 Kitaev-Heisenberg honeycomb material reference",
        },
        {
            "name": "li2cuo2_frustrated_ferromagnetic_chain_reference",
            "model": "li2cuo2_j1_j2_chain",
            "lattice": "chain",
            "hamiltonian": "ferromagnetic J1 and antiferromagnetic J2 chain",
            "hamiltonian_terms": ["heisenberg", "j1", "j2", "ferromagnetic", "material"],
            "parameters": {"material": "Li2CuO2"},
            "observable": "material_model_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed_or_experiment",
            "standard_result": {"frustrated_ferromagnetic_chain": True},
            "source": "Mizuno_1998",
            "source_url": "https://doi.org/10.1103/PhysRevB.57.5326",
            "citation_locator": "Li2CuO2 frustrated ferromagnetic chain reference",
        },
        {
            "name": "licuvo4_spiral_chain_reference",
            "model": "licuvo4_j1_j2_chain",
            "lattice": "chain",
            "hamiltonian": "ferromagnetic J1 and antiferromagnetic J2 chain in field",
            "hamiltonian_terms": ["heisenberg", "j1", "j2", "spiral", "material"],
            "parameters": {"material": "LiCuVO4"},
            "observable": "spiral_order_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed_or_experiment",
            "standard_result": {"incommensurate_spiral_order": True},
            "source": "Enderle_2005",
            "source_url": "https://doi.org/10.1209/epl/i2005-10075-2",
            "citation_locator": "LiCuVO4 frustrated-chain spiral order reference",
        },
        {
            "name": "azurite_diamond_chain_plateau_reference",
            "model": "azurite_distorted_diamond_chain",
            "lattice": "diamond_chain",
            "hamiltonian": "distorted diamond-chain Heisenberg model",
            "hamiltonian_terms": ["heisenberg", "diamond_chain", "plateau", "material"],
            "parameters": {"material": "azurite"},
            "observable": "magnetization_plateau",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed_or_experiment",
            "standard_result": {"one_third_magnetization_plateau": True},
            "source": "Rule_2008",
            "source_url": "https://doi.org/10.1103/PhysRevLett.100.117202",
            "citation_locator": "azurite distorted diamond-chain one-third plateau",
        },
        {
            "name": "cacu2o3_spin_ladder_reference",
            "model": "cacu2o3_spin_ladder",
            "lattice": "ladder",
            "hamiltonian": "two-leg spin ladder with interladder coupling",
            "hamiltonian_terms": ["heisenberg", "ladder", "material"],
            "parameters": {"material": "CaCu2O3"},
            "observable": "material_model_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "experiment_or_ladder_model",
            "standard_result": {"spin_ladder_material": True},
            "source": "Kiryukhin_2001",
            "source_url": "https://doi.org/10.1103/PhysRevB.63.144418",
            "citation_locator": "CaCu2O3 spin-ladder material reference",
        },
        {
            "name": "bpcb_spin_ladder_field_induced_order_reference",
            "model": "bpcb_spin_ladder",
            "lattice": "ladder",
            "hamiltonian": "two-leg Heisenberg ladder in magnetic field",
            "hamiltonian_terms": ["heisenberg", "ladder", "magnetic_field", "material"],
            "parameters": {"material": "BPCB"},
            "observable": "field_induced_order",
            "comparison_kind": "paper_numeric",
            "backend_needed": "experiment_or_ladder_model",
            "standard_result": {"field_induced_luttinger_liquid_regime": True},
            "source": "Thielemann_2009",
            "source_url": "https://doi.org/10.1103/PhysRevB.79.020408",
            "citation_locator": "BPCB spin-ladder field-induced order reference",
        },
        {
            "name": "ba3cosb2o9_triangular_plateau_reference",
            "model": "ba3cosb2o9_triangular_heisenberg",
            "lattice": "triangular",
            "hamiltonian": "triangular-lattice spin-1/2 Heisenberg antiferromagnet in field",
            "hamiltonian_terms": ["heisenberg", "triangular", "plateau", "material"],
            "parameters": {"material": "Ba3CoSb2O9"},
            "observable": "magnetization_plateau",
            "comparison_kind": "paper_numeric",
            "backend_needed": "experiment_or_ed",
            "standard_result": {"one_third_magnetization_plateau": True},
            "source": "Shirata_2012",
            "source_url": "https://doi.org/10.1103/PhysRevLett.108.057205",
            "citation_locator": "Ba3CoSb2O9 triangular antiferromagnet plateau reference",
        },
        {
            "name": "ybmggao4_triangular_spin_liquid_reference",
            "model": "ybmggao4_triangular_exchange",
            "lattice": "triangular",
            "hamiltonian": "effective spin-1/2 triangular anisotropic exchange model",
            "hamiltonian_terms": ["anisotropic_exchange", "triangular", "spin_liquid", "material"],
            "parameters": {"material": "YbMgGaO4"},
            "observable": "material_model_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "anisotropic_exchange_or_experiment",
            "standard_result": {"triangular_quantum_spin_liquid_candidate": True},
            "source": "Li_2015",
            "source_url": "https://doi.org/10.1038/srep16419",
            "citation_locator": "YbMgGaO4 triangular spin-liquid candidate reference",
        },
        {
            "name": "zncu3oh6cl2_kagome_dzyaloshinskii_moriya_reference",
            "model": "herbertsmithite_kagome_dm",
            "lattice": "kagome",
            "hamiltonian": "J kagome Heisenberg plus Dzyaloshinskii-Moriya exchange",
            "hamiltonian_terms": ["heisenberg", "dzyaloshinskii_moriya", "kagome", "material"],
            "parameters": {"material": "ZnCu3(OH)6Cl2"},
            "observable": "material_model_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed_or_experiment",
            "standard_result": {"dm_interaction_relevant": True},
            "source": "Zorko_2008",
            "source_url": "https://doi.org/10.1103/PhysRevLett.101.026405",
            "citation_locator": "herbertsmithite Dzyaloshinskii-Moriya interaction estimate",
        },
        {
            "name": "fe8_molecular_spin_tunneling_reference",
            "model": "fe8_single_molecule_magnet",
            "lattice": "single_cluster",
            "hamiltonian": "-D Sz^2 + E(Sx^2 - Sy^2) + Zeeman terms",
            "hamiltonian_terms": ["single_molecule_magnet", "anisotropy", "zeeman", "tunneling"],
            "parameters": {"spin": 10.0, "material": "Fe8"},
            "observable": "quantum_tunneling_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "single_cluster_exact_diagonalization",
            "standard_result": {"macroscopic_quantum_tunneling_observed": True},
            "source": "Wernsdorfer_Sessoli_1999",
            "source_url": "https://doi.org/10.1126/science.284.5411.133",
            "citation_locator": "Fe8 molecular magnet quantum tunneling reference",
        },
    ]
)


LITERATURE_STANDARD_RESULTS.extend(
    [
        {
            "name": "kagome_heisenberg_dmrg_spin_liquid_yan_reference",
            "model": "spin_1_2_kagome_heisenberg_afm",
            "lattice": "kagome",
            "hamiltonian": "J sum_<ij> Si.Sj",
            "hamiltonian_terms": ["heisenberg", "nearest_neighbor", "kagome", "spin_liquid"],
            "parameters": {"spin": 0.5, "exchange": 1.0},
            "observable": "ground_state_energy_and_gap",
            "comparison_kind": "paper_numeric",
            "backend_needed": "dmrg_or_large_ed",
            "standard_result": {
                "energy_per_site": -0.4386,
                "spin_gap_over_j": 0.13,
                "computable_observables": ["small_cluster_ed_energy", "kagome_classical_flat_band", "curie_weiss_theta"],
            },
            "source": "Yan_Huse_White_2011",
            "source_url": "https://doi.org/10.1126/science.1201080",
            "citation_locator": "DMRG kagome spin-liquid energy and spin gap benchmark",
        },
        {
            "name": "kagome_heisenberg_topological_entanglement_reference",
            "model": "spin_1_2_kagome_heisenberg_afm",
            "lattice": "kagome",
            "hamiltonian": "J sum_<ij> Si.Sj",
            "hamiltonian_terms": ["heisenberg", "nearest_neighbor", "kagome", "topological"],
            "parameters": {"spin": 0.5, "exchange": 1.0},
            "observable": "topological_entanglement_entropy",
            "comparison_kind": "paper_numeric",
            "backend_needed": "dmrg",
            "standard_result": {
                "topological_entanglement_entropy": "consistent_with_Z2",
                "computable_observables": ["finite_cylinder_energy", "singlet_gap", "structure_factor_peak_absence"],
            },
            "source": "Depenbrock_McCulloch_Schollwoeck_2012",
            "source_url": "https://doi.org/10.1103/PhysRevLett.109.067201",
            "citation_locator": "topological entanglement entropy in kagome Heisenberg antiferromagnet",
        },
        {
            "name": "kagome_chiral_spin_liquid_j1_j2_jchi_reference",
            "model": "kagome_heisenberg_chiral_j1_j2_jchi",
            "lattice": "kagome",
            "hamiltonian": "J1 NN + J2 NNN + J_chi sum Si.(Sj x Sk)",
            "hamiltonian_terms": ["heisenberg", "j1", "j2", "scalar_chirality", "kagome"],
            "parameters": {"spin": 0.5},
            "observable": "chiral_spin_liquid_phase",
            "comparison_kind": "paper_numeric",
            "backend_needed": "dmrg_or_ed",
            "standard_result": {
                "chiral_spin_liquid_phase": True,
                "computable_observables": ["triangle_scalar_chirality", "small_cluster_ed_spectrum"],
            },
            "source": "Bauer_Cincio_Keller_2014",
            "source_url": "https://doi.org/10.1038/ncomms6137",
            "citation_locator": "kagome chiral spin liquid in Heisenberg plus scalar-chirality model",
        },
        {
            "name": "ca10cr7o28_bilayer_breathing_kagome_reference",
            "model": "ca10cr7o28_bilayer_breathing_kagome",
            "lattice": "bilayer_kagome",
            "hamiltonian": "coupled breathing kagome Heisenberg model with ferro and antiferro exchanges",
            "hamiltonian_terms": ["heisenberg", "breathing_kagome", "bilayer", "material"],
            "parameters": {"material": "Ca10Cr7O28", "spin": 0.5},
            "observable": "material_exchange_model",
            "comparison_kind": "paper_numeric",
            "backend_needed": "classical_glt_or_spin_wave",
            "standard_result": {
                "spin_liquid_candidate": True,
                "mixed_ferromagnetic_antiferromagnetic_exchanges": True,
                "computable_observables": ["classical_luttinger_tisza_minima", "curie_weiss_theta", "linear_spin_wave_modes"],
            },
            "source": "Balz_2016",
            "source_url": "https://doi.org/10.1038/nphys3826",
            "citation_locator": "Ca10Cr7O28 bilayer kagome spin-liquid material exchange model",
        },
        {
            "name": "scgo_kagome_bilayer_spin_liquid_reference",
            "model": "sr_cr_ga_o_kagome_bilayer",
            "lattice": "kagome_bilayer",
            "hamiltonian": "Cr3+ kagome-bilayer Heisenberg antiferromagnet with dilution",
            "hamiltonian_terms": ["heisenberg", "kagome_bilayer", "frustrated", "material"],
            "parameters": {"material": "SrCr9pGa12-9pO19", "spin": 1.5},
            "observable": "spin_liquid_material_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "classical_mc_or_experiment",
            "standard_result": {
                "no_conventional_order_down_to_low_t": True,
                "computable_observables": ["classical_ground_state_manifold", "curie_weiss_theta", "dilution_free_cluster_modes"],
            },
            "source": "Ramirez_1990",
            "source_url": "https://doi.org/10.1103/PhysRevLett.64.2070",
            "citation_locator": "SCGO frustrated kagome-bilayer spin-liquid phenomenology",
        },
        {
            "name": "barlowite_kagome_material_reference",
            "model": "barlowite_kagome_interlayer_coupled",
            "lattice": "kagome",
            "hamiltonian": "kagome Heisenberg layers plus interlayer Cu coupling",
            "hamiltonian_terms": ["heisenberg", "kagome", "interlayer", "material"],
            "parameters": {"material": "Cu4(OH)6FBr"},
            "observable": "material_model_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed_or_experiment",
            "standard_result": {
                "interlayer_coupling_relevant": True,
                "computable_observables": ["kagome_layer_flat_band", "curie_weiss_theta", "interlayer_ordering_vector"],
            },
            "source": "Han_2014",
            "source_url": "https://doi.org/10.1103/PhysRevB.90.094426",
            "citation_locator": "barlowite kagome antiferromagnet material reference",
        },
        {
            "name": "zn_barlowite_kagome_qsl_reference",
            "model": "zn_substituted_barlowite_kagome",
            "lattice": "kagome",
            "hamiltonian": "nearly ideal kagome Heisenberg layers with reduced interlayer Cu",
            "hamiltonian_terms": ["heisenberg", "kagome", "spin_liquid", "material"],
            "parameters": {"material": "ZnCu3(OH)6FBr"},
            "observable": "spin_liquid_material_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed_or_experiment",
            "standard_result": {
                "reduced_interlayer_magnetism": True,
                "computable_observables": ["kagome_layer_flat_band", "curie_weiss_theta", "nearest_neighbor_structure_factor"],
            },
            "source": "Feng_2017",
            "source_url": "https://doi.org/10.1088/1674-1137/41/3/037105",
            "citation_locator": "Zn-substituted barlowite kagome spin-liquid candidate",
        },
        {
            "name": "vesignieite_kagome_material_reference",
            "model": "vesignieite_kagome_antiferromagnet",
            "lattice": "kagome",
            "hamiltonian": "distorted kagome Heisenberg antiferromagnet",
            "hamiltonian_terms": ["heisenberg", "kagome", "distorted", "material"],
            "parameters": {"material": "BaCu3V2O8(OH)2"},
            "observable": "material_model_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed_or_experiment",
            "standard_result": {
                "distorted_kagome_relevant": True,
                "computable_observables": ["distorted_kagome_classical_minima", "curie_weiss_theta"],
            },
            "source": "Yoshida_2009",
            "source_url": "https://doi.org/10.1143/JPSJ.78.043704",
            "citation_locator": "vesignieite kagome antiferromagnet reference",
        },
        {
            "name": "haydeeite_ferromagnetic_kagome_reference",
            "model": "haydeeite_kagome_ferromagnet",
            "lattice": "kagome",
            "hamiltonian": "ferromagnetic kagome Heisenberg exchange plus further-neighbor couplings",
            "hamiltonian_terms": ["heisenberg", "kagome", "ferromagnetic", "material"],
            "parameters": {"material": "MgCu3(OH)6Cl2"},
            "observable": "classical_ground_state",
            "comparison_kind": "paper_numeric",
            "backend_needed": "classical_glt_or_experiment",
            "standard_result": {
                "ferromagnetic_kagome_exchange": True,
                "computable_observables": ["gamma_point_ferromagnetic_minimum", "curie_weiss_theta"],
            },
            "source": "Shores_2005",
            "source_url": "https://doi.org/10.1021/ja053891p",
            "citation_locator": "haydeeite paratacamite kagome material reference",
        },
        {
            "name": "clinoatacamite_distorted_kagome_reference",
            "model": "clinoatacamite_distorted_kagome",
            "lattice": "distorted_kagome",
            "hamiltonian": "distorted kagome and interlayer Cu exchange",
            "hamiltonian_terms": ["heisenberg", "distorted_kagome", "material"],
            "parameters": {"material": "Cu2(OH)3Cl"},
            "observable": "material_model_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "classical_glt_or_experiment",
            "standard_result": {
                "distorted_kagome_reference": True,
                "computable_observables": ["distorted_kagome_classical_minima", "curie_weiss_theta"],
            },
            "source": "Lee_2007",
            "source_url": "https://doi.org/10.1038/nmat1867",
            "citation_locator": "clinoatacamite frustrated magnetism reference",
        },
        {
            "name": "edwardsite_kagome_antiferromagnet_reference",
            "model": "edwardsite_kagome_antiferromagnet",
            "lattice": "kagome",
            "hamiltonian": "S=1 kagome antiferromagnet model",
            "hamiltonian_terms": ["heisenberg", "kagome", "spin1", "material"],
            "parameters": {"material": "Cd2Cu3(OH)6(SO4)2"},
            "observable": "material_model_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "classical_glt_or_experiment",
            "standard_result": {
                "kagome_antiferromagnet_reference": True,
                "computable_observables": ["classical_120_manifold", "curie_weiss_theta"],
            },
            "source": "Okuma_2017",
            "source_url": "https://doi.org/10.1038/ncomms14113",
            "citation_locator": "edwardsite kagome antiferromagnet reference",
        },
        {
            "name": "jarosite_kagome_dzyaloshinskii_moriya_reference",
            "model": "jarosite_kagome_dm",
            "lattice": "kagome",
            "hamiltonian": "kagome Heisenberg plus Dzyaloshinskii-Moriya exchange",
            "hamiltonian_terms": ["heisenberg", "dzyaloshinskii_moriya", "kagome", "material"],
            "parameters": {"material": "KFe3(OH)6(SO4)2"},
            "observable": "classical_order",
            "comparison_kind": "paper_numeric",
            "backend_needed": "classical_glt_or_spin_wave",
            "standard_result": {
                "q_0_120_order": True,
                "computable_observables": ["q0_120_order_energy", "dm_selected_chirality", "spin_wave_gap"],
            },
            "source": "Matan_2006",
            "source_url": "https://doi.org/10.1103/PhysRevLett.96.247201",
            "citation_locator": "jarosite kagome DM interaction and spin waves",
        },
        {
            "name": "gadolinium_gallium_garnet_hyperkagome_reference",
            "model": "gadolinium_gallium_garnet",
            "lattice": "hyperkagome_garnet",
            "hamiltonian": "Gd garnet Heisenberg dipolar exchange model",
            "hamiltonian_terms": ["heisenberg", "dipolar", "hyperkagome", "material"],
            "parameters": {"material": "Gd3Ga5O12"},
            "observable": "frustrated_garnet_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "classical_mc_or_glt",
            "standard_result": {
                "strong_frustration": True,
                "computable_observables": ["dipolar_luttinger_tisza_minima", "curie_weiss_theta"],
            },
            "source": "Schiffer_Ramirez_1996",
            "source_url": "https://doi.org/10.1103/PhysRevLett.77.2085",
            "citation_locator": "gadolinium gallium garnet frustrated magnet reference",
        },
        {
            "name": "garnet_gd3ga5o12_spin_liquid_reference",
            "model": "gd3ga5o12_garnet",
            "lattice": "hyperkagome_garnet",
            "hamiltonian": "Gd3+ Heisenberg and dipolar interactions on garnet lattice",
            "hamiltonian_terms": ["heisenberg", "dipolar", "garnet", "material"],
            "parameters": {"material": "GGG"},
            "observable": "low_temperature_correlations",
            "comparison_kind": "paper_numeric",
            "backend_needed": "classical_mc_or_experiment",
            "standard_result": {
                "short_range_order_without_simple_lro": True,
                "computable_observables": ["classical_structure_factor", "dipolar_energy_minima"],
            },
            "source": "Petrenko_1998",
            "source_url": "https://doi.org/10.1103/PhysRevB.57.4986",
            "citation_locator": "GGG low-temperature frustrated correlations reference",
        },
        {
            "name": "garnet_gd3te2li3o12_hyperkagome_reference",
            "model": "gd3te2li3o12_garnet",
            "lattice": "hyperkagome_garnet",
            "hamiltonian": "Gd garnet Heisenberg and dipolar exchange model",
            "hamiltonian_terms": ["heisenberg", "dipolar", "hyperkagome", "material"],
            "parameters": {"material": "Gd3Te2Li3O12"},
            "observable": "material_model_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "classical_mc_or_experiment",
            "standard_result": {
                "garnet_frustrated_magnet": True,
                "computable_observables": ["curie_weiss_theta", "dipolar_luttinger_tisza_minima"],
            },
            "source": "Dun_2015",
            "source_url": "https://doi.org/10.1103/PhysRevB.92.140407",
            "citation_locator": "Gd garnet frustrated magnet reference",
        },
        {
            "name": "gamma_li2iro3_3d_kitaev_reference",
            "model": "gamma_li2iro3_3d_kitaev_gamma",
            "lattice": "stripyhoneycomb",
            "hamiltonian": "3D honeycomb Kitaev-Heisenberg-Gamma exchange",
            "hamiltonian_terms": ["kitaev", "gamma", "heisenberg", "3d_honeycomb", "material"],
            "parameters": {"material": "gamma-Li2IrO3"},
            "observable": "spiral_order_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "anisotropic_exchange_or_classical_glt",
            "standard_result": {
                "incommensurate_spiral_order": True,
                "computable_observables": ["classical_spiral_wavevector", "single_bond_anisotropic_exchange_matrix"],
            },
            "source": "Modic_2014",
            "source_url": "https://doi.org/10.1038/ncomms5203",
            "citation_locator": "gamma-Li2IrO3 three-dimensional Kitaev material reference",
        },
        {
            "name": "h3liir2o6_kitaev_spin_liquid_candidate_reference",
            "model": "h3liir2o6_honeycomb_kitaev",
            "lattice": "honeycomb",
            "hamiltonian": "disordered honeycomb Kitaev-Heisenberg-Gamma exchange",
            "hamiltonian_terms": ["kitaev", "gamma", "honeycomb", "disorder", "material"],
            "parameters": {"material": "H3LiIr2O6"},
            "observable": "spin_liquid_candidate_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "anisotropic_exchange_or_experiment",
            "standard_result": {
                "no_magnetic_order_reported": True,
                "computable_observables": ["clean_limit_kitaev_phase_condition", "single_bond_exchange_eigenvalues"],
            },
            "source": "Kitagawa_2018",
            "source_url": "https://doi.org/10.1038/nature25482",
            "citation_locator": "H3LiIr2O6 Kitaev spin-liquid candidate reference",
        },
        {
            "name": "cu2iro3_honeycomb_kitaev_reference",
            "model": "cu2iro3_honeycomb_kitaev",
            "lattice": "honeycomb",
            "hamiltonian": "honeycomb iridate Kitaev-Heisenberg-Gamma exchange",
            "hamiltonian_terms": ["kitaev", "heisenberg", "honeycomb", "material"],
            "parameters": {"material": "Cu2IrO3"},
            "observable": "material_model_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "anisotropic_exchange_or_experiment",
            "standard_result": {
                "honeycomb_iridate_reference": True,
                "computable_observables": ["kitaev_triangle_gapless_condition", "single_bond_exchange_matrix"],
            },
            "source": "Abramchuk_2017",
            "source_url": "https://doi.org/10.1021/jacs.7b08744",
            "citation_locator": "Cu2IrO3 honeycomb Kitaev material reference",
        },
        {
            "name": "ba3irti2o9_honeycomb_kitaev_reference",
            "model": "ba3irti2o9_honeycomb_iridate",
            "lattice": "honeycomb",
            "hamiltonian": "spin-orbit coupled honeycomb iridate exchange model",
            "hamiltonian_terms": ["kitaev", "heisenberg", "honeycomb", "material"],
            "parameters": {"material": "Ba3IrTi2O9"},
            "observable": "spin_liquid_candidate_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "anisotropic_exchange_or_experiment",
            "standard_result": {
                "spin_liquid_candidate": True,
                "computable_observables": ["honeycomb_kitaev_limit", "curie_weiss_theta"],
            },
            "source": "Dey_2012",
            "source_url": "https://doi.org/10.1103/PhysRevB.86.140405",
            "citation_locator": "Ba3IrTi2O9 honeycomb spin-orbit material reference",
        },
        {
            "name": "ru_br3_kitaev_material_reference",
            "model": "ru_br3_honeycomb_kitaev",
            "lattice": "honeycomb",
            "hamiltonian": "Ru honeycomb Kitaev-Heisenberg-Gamma exchange",
            "hamiltonian_terms": ["kitaev", "gamma", "honeycomb", "material"],
            "parameters": {"material": "RuBr3"},
            "observable": "material_model_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "anisotropic_exchange",
            "standard_result": {
                "ru_honeycomb_kitaev_candidate": True,
                "computable_observables": ["single_bond_exchange_eigenvalues", "classical_zigzag_energy"],
            },
            "source": "Winter_2017",
            "source_url": "https://doi.org/10.1088/1361-648X/aa8cf5",
            "citation_locator": "Kitaev materials exchange-model review reference",
        },
        {
            "name": "crcl3_honeycomb_heisenberg_reference",
            "model": "crcl3_honeycomb_heisenberg",
            "lattice": "honeycomb",
            "hamiltonian": "honeycomb ferromagnetic intralayer exchange plus interlayer antiferromagnetism",
            "hamiltonian_terms": ["heisenberg", "honeycomb", "ferromagnetic", "material"],
            "parameters": {"material": "CrCl3", "spin": 1.5},
            "observable": "classical_order",
            "comparison_kind": "paper_numeric",
            "backend_needed": "classical_glt_or_spin_wave",
            "standard_result": {
                "ferromagnetic_honeycomb_layers": True,
                "computable_observables": ["gamma_point_ferromagnetic_minimum", "curie_weiss_theta"],
            },
            "source": "Cable_1961",
            "source_url": "https://doi.org/10.1063/1.1706360",
            "citation_locator": "CrCl3 layered honeycomb magnetic order reference",
        },
        {
            "name": "cri3_honeycomb_ferromagnet_reference",
            "model": "cri3_honeycomb_ferromagnet",
            "lattice": "honeycomb",
            "hamiltonian": "honeycomb ferromagnetic exchange with anisotropy",
            "hamiltonian_terms": ["heisenberg", "honeycomb", "ferromagnetic", "anisotropy", "material"],
            "parameters": {"material": "CrI3", "spin": 1.5},
            "observable": "classical_order",
            "comparison_kind": "paper_numeric",
            "backend_needed": "classical_glt_or_spin_wave",
            "standard_result": {
                "ferromagnetic_order": True,
                "computable_observables": ["gamma_point_ferromagnetic_minimum", "single_ion_or_exchange_anisotropy_gap"],
            },
            "source": "McGuire_2015",
            "source_url": "https://doi.org/10.1021/acs.chemmater.5b01006",
            "citation_locator": "CrI3 honeycomb ferromagnet reference",
        },
        {
            "name": "crgete3_honeycomb_ferromagnet_reference",
            "model": "crgete3_honeycomb_ferromagnet",
            "lattice": "honeycomb",
            "hamiltonian": "honeycomb ferromagnetic exchange with anisotropy",
            "hamiltonian_terms": ["heisenberg", "honeycomb", "ferromagnetic", "material"],
            "parameters": {"material": "CrGeTe3", "spin": 1.5},
            "observable": "classical_order",
            "comparison_kind": "paper_numeric",
            "backend_needed": "classical_glt_or_spin_wave",
            "standard_result": {
                "ferromagnetic_order": True,
                "computable_observables": ["gamma_point_ferromagnetic_minimum", "curie_weiss_theta"],
            },
            "source": "Carteaux_1995",
            "source_url": "https://doi.org/10.1209/0295-5075/29/4/008",
            "citation_locator": "CrGeTe3 layered ferromagnet reference",
        },
        {
            "name": "fecl3_honeycomb_antiferromagnet_reference",
            "model": "fecl3_honeycomb_antiferromagnet",
            "lattice": "honeycomb",
            "hamiltonian": "honeycomb antiferromagnetic Heisenberg exchange",
            "hamiltonian_terms": ["heisenberg", "honeycomb", "antiferromagnetic", "material"],
            "parameters": {"material": "FeCl3"},
            "observable": "classical_order",
            "comparison_kind": "paper_numeric",
            "backend_needed": "classical_glt_or_spin_wave",
            "standard_result": {
                "neel_order_on_honeycomb": True,
                "computable_observables": ["gamma_staggered_honeycomb_minimum", "two_band_lsw_spectrum"],
            },
            "source": "Regnault_1975",
            "source_url": "https://doi.org/10.1016/0304-8853(75)90113-5",
            "citation_locator": "FeCl3 layered honeycomb antiferromagnet reference",
        },
        {
            "name": "ni_ps3_honeycomb_antiferromagnet_reference",
            "model": "nips3_honeycomb_antiferromagnet",
            "lattice": "honeycomb",
            "hamiltonian": "honeycomb Heisenberg exchange with anisotropy",
            "hamiltonian_terms": ["heisenberg", "honeycomb", "antiferromagnetic", "material"],
            "parameters": {"material": "NiPS3"},
            "observable": "classical_order",
            "comparison_kind": "paper_numeric",
            "backend_needed": "classical_glt_or_spin_wave",
            "standard_result": {
                "zigzag_or_collinear_order_reference": True,
                "computable_observables": ["honeycomb_j1_j2_j3_classical_order", "spin_wave_gap"],
            },
            "source": "Wildes_2015",
            "source_url": "https://doi.org/10.1103/PhysRevB.92.224408",
            "citation_locator": "NiPS3 honeycomb antiferromagnet spin waves",
        },
        {
            "name": "mn_ps3_honeycomb_antiferromagnet_reference",
            "model": "mnps3_honeycomb_antiferromagnet",
            "lattice": "honeycomb",
            "hamiltonian": "honeycomb Heisenberg antiferromagnet with anisotropy",
            "hamiltonian_terms": ["heisenberg", "honeycomb", "antiferromagnetic", "material"],
            "parameters": {"material": "MnPS3"},
            "observable": "classical_order",
            "comparison_kind": "paper_numeric",
            "backend_needed": "classical_glt_or_spin_wave",
            "standard_result": {
                "neel_order_reference": True,
                "computable_observables": ["gamma_staggered_honeycomb_minimum", "curie_weiss_theta"],
            },
            "source": "Wildes_1998",
            "source_url": "https://doi.org/10.1088/0953-8984/10/29/012",
            "citation_locator": "MnPS3 honeycomb antiferromagnet reference",
        },
        {
            "name": "fe_ps3_honeycomb_ising_reference",
            "model": "feps3_honeycomb_ising",
            "lattice": "honeycomb",
            "hamiltonian": "honeycomb anisotropic Ising-like antiferromagnet",
            "hamiltonian_terms": ["ising", "honeycomb", "antiferromagnetic", "anisotropy", "material"],
            "parameters": {"material": "FePS3"},
            "observable": "ising_like_order",
            "comparison_kind": "paper_numeric",
            "backend_needed": "classical_glt_or_experiment",
            "standard_result": {
                "ising_like_zigzag_order": True,
                "computable_observables": ["honeycomb_ising_domain_wall_energy", "zigzag_ordering_vector"],
            },
            "source": "Wildes_2012",
            "source_url": "https://doi.org/10.1103/PhysRevB.85.094422",
            "citation_locator": "FePS3 Ising-like honeycomb antiferromagnet reference",
        },
        {
            "name": "ba2cugeo7_dm_spiral_reference",
            "model": "ba2cugeo7_dzyaloshinskii_moriya",
            "lattice": "square",
            "hamiltonian": "square-lattice Heisenberg exchange plus Dzyaloshinskii-Moriya interaction",
            "hamiltonian_terms": ["heisenberg", "dzyaloshinskii_moriya", "spiral", "material"],
            "parameters": {"material": "Ba2CuGe2O7"},
            "observable": "classical_spiral_pitch",
            "comparison_kind": "paper_numeric",
            "backend_needed": "classical_minimization_or_spin_wave",
            "standard_result": {
                "dm_induced_incommensurate_spiral": True,
                "computable_observables": ["spiral_pitch_from_d_over_j", "single_q_classical_energy"],
            },
            "source": "Zheludev_1998",
            "source_url": "https://doi.org/10.1103/PhysRevB.57.2968",
            "citation_locator": "Ba2CuGe2O7 Dzyaloshinskii-Moriya spiral reference",
        },
        {
            "name": "mnsi_chiral_helimagnet_reference",
            "model": "mnsi_chiral_helimagnet",
            "lattice": "b20",
            "hamiltonian": "ferromagnetic exchange plus Dzyaloshinskii-Moriya interaction",
            "hamiltonian_terms": ["heisenberg", "dzyaloshinskii_moriya", "helimagnet", "material"],
            "parameters": {"material": "MnSi"},
            "observable": "helical_wavevector",
            "comparison_kind": "paper_numeric",
            "backend_needed": "classical_minimization",
            "standard_result": {
                "long_wavelength_helix": True,
                "computable_observables": ["helix_pitch_from_d_over_j", "single_q_classical_energy"],
            },
            "source": "Bak_Jensen_1980",
            "source_url": "https://doi.org/10.1088/0022-3719/13/31/002",
            "citation_locator": "Dzyaloshinskii-Moriya helimagnet model for MnSi",
        },
        {
            "name": "cu2oseo3_skyrmion_lattice_reference",
            "model": "cu2oseo3_chiral_ferrimagnet",
            "lattice": "chiral_cubic",
            "hamiltonian": "exchange plus Dzyaloshinskii-Moriya and magnetic field",
            "hamiltonian_terms": ["heisenberg", "dzyaloshinskii_moriya", "magnetic_field", "skyrmion", "material"],
            "parameters": {"material": "Cu2OSeO3"},
            "observable": "skyrmion_lattice_phase",
            "comparison_kind": "paper_numeric",
            "backend_needed": "classical_minimization_or_mc",
            "standard_result": {
                "skyrmion_lattice_phase": True,
                "computable_observables": ["single_q_helix_energy", "triple_q_skyrmion_variational_energy"],
            },
            "source": "Seki_2012",
            "source_url": "https://doi.org/10.1126/science.1224143",
            "citation_locator": "Cu2OSeO3 skyrmion-lattice phase reference",
        },
    ]
)


_STANDARD_RESULT_INDEX_METADATA = {
    "majundar_ghosh_chain_exact_dimer_point": {
        "lattice": "chain",
        "hamiltonian_terms": ["heisenberg", "j1", "j2", "frustrated"],
    },
    "aklt_spin1_chain_projector_ground_state": {
        "lattice": "chain",
        "hamiltonian_terms": ["heisenberg", "biquadratic", "projector", "spin1"],
    },
    "xxx_spin_half_chain_bethe_ground_state": {
        "lattice": "chain",
        "hamiltonian_terms": ["heisenberg", "nearest_neighbor", "isotropic"],
    },
    "xxz_spin_half_chain_phase_boundaries": {
        "lattice": "chain",
        "hamiltonian_terms": ["xxz", "nearest_neighbor", "anisotropic"],
    },
    "shastry_sutherland_exact_dimer_product": {
        "lattice": "shastry_sutherland",
        "hamiltonian_terms": ["heisenberg", "orthogonal_dimer", "frustrated"],
    },
    "spin_ice_tetrahedron_nn_ice_rule": {
        "lattice": "pyrochlore_tetrahedron",
        "hamiltonian_terms": ["ising", "local_axis", "nearest_neighbor"],
    },
    "single_ion_spin1_anisotropy_levels": {
        "lattice": "single_site",
        "hamiltonian_terms": ["single_ion_anisotropy", "sz2", "spin1"],
    },
    "kitaev_honeycomb_exact_spin_liquid_limit": {
        "lattice": "honeycomb",
        "hamiltonian_terms": ["kitaev", "bond_dependent", "compass"],
    },
    "haldane_spin1_chain_gap_reference": {
        "lattice": "chain",
        "hamiltonian_terms": ["heisenberg", "nearest_neighbor", "spin1"],
    },
    "square_spin_half_heisenberg_qmc_energy": {
        "lattice": "square",
        "hamiltonian_terms": ["heisenberg", "nearest_neighbor", "j1"],
    },
    "j1_j2_square_spin_half_neel_collinear_transition_reference": {
        "lattice": "square",
        "hamiltonian_terms": ["heisenberg", "j1", "j2", "frustrated"],
    },
    "bilinear_biquadratic_spin1_chain_aklt_angle": {
        "lattice": "chain",
        "hamiltonian_terms": ["heisenberg", "biquadratic", "spin1"],
    },
    "transverse_field_ising_chain_critical_point": {
        "lattice": "chain",
        "hamiltonian_terms": ["ising", "transverse_field", "nearest_neighbor"],
    },
    "transverse_field_ising_chain_gap": {
        "lattice": "chain",
        "hamiltonian_terms": ["ising", "transverse_field", "nearest_neighbor"],
    },
    "two_dimensional_square_ising_onsager_tc": {
        "lattice": "square",
        "hamiltonian_terms": ["ising", "nearest_neighbor", "classical"],
    },
    "two_dimensional_square_ising_spontaneous_magnetization": {
        "lattice": "square",
        "hamiltonian_terms": ["ising", "nearest_neighbor", "classical"],
    },
    "two_dimensional_xy_bkt_temperature_reference": {
        "lattice": "square",
        "hamiltonian_terms": ["xy", "nearest_neighbor", "classical"],
    },
    "two_dimensional_xy_bkt_universal_jump": {
        "lattice": "square",
        "hamiltonian_terms": ["xy", "nearest_neighbor", "classical"],
    },
    "one_dimensional_classical_ising_no_finite_t_transition": {
        "lattice": "chain",
        "hamiltonian_terms": ["ising", "nearest_neighbor", "classical"],
    },
    "one_dimensional_classical_ising_correlation_length": {
        "lattice": "chain",
        "hamiltonian_terms": ["ising", "nearest_neighbor", "classical"],
    },
    "lieb_schultz_mattis_half_integer_constraint": {
        "lattice": "chain",
        "hamiltonian_terms": ["local_spin", "translation_invariant", "half_integer"],
    },
    "kitaev_honeycomb_gapless_triangle_condition": {
        "lattice": "honeycomb",
        "hamiltonian_terms": ["kitaev", "bond_dependent", "compass"],
    },
    "eight_vertex_zero_field_exact_solution_status": {
        "lattice": "square_vertex",
        "hamiltonian_terms": ["vertex_model", "eight_vertex", "classical"],
    },
    "blume_capel_spin1_zero_temperature_level_crossing": {
        "lattice": "square",
        "hamiltonian_terms": ["ising", "single_ion_anisotropy", "spin1"],
    },
}


_DEFAULT_LATTICE_COORDINATION = {
    "chain": 2,
    "ladder": 3,
    "honeycomb": 3,
    "square": 4,
    "checkerboard": 6,
    "kagome": 4,
    "triangular": 6,
    "diamond": 4,
    "pyrochlore": 6,
    "simple_cubic": 6,
    "bcc": 8,
    "fcc": 12,
}


_FINITE_CLUSTER_COMPUTABLE_OBSERVABLES_BY_BENCHMARK = {
    "single_ion_spin1_anisotropy_levels": "onsite_spectrum",
    "aklt_spin1_chain_projector_ground_state": "two_site_projector_spectrum",
    "shastry_sutherland_exact_dimer_product": "two_spin_dimer_spectrum",
    "two_leg_ladder_strong_rung_exact_limit": "rung_dimer_spectrum",
}


_SINGLE_Q_COMPUTABLE_OBSERVABLE_BENCHMARKS = {
    "triangular_nn_classical_120_reference",
    "square_j1_j3_classical_lifshitz_reference",
    "simple_cubic_j1_j2_collinear_reference",
    "honeycomb_j1_j2_spiral_ring_reference",
    "diamond_j1_j2_spiral_surface_reference",
}


def _curie_weiss_temperature_from_coordination(coordination, exchange):
    return -float(coordination) * float(exchange) / 3.0


for _entry in LITERATURE_STANDARD_RESULTS:
    _metadata = _STANDARD_RESULT_INDEX_METADATA.get(_entry["name"])
    if _metadata is not None:
        _entry.update(_metadata)

    _terms = set(_entry.get("hamiltonian_terms", []))
    _computable = []
    if "heisenberg" in _terms and "nearest_neighbor" in _terms:
        _computable.append("curie_weiss_theta")
    if "material" in _terms:
        _computable.extend(["curie_weiss_theta", "classical_luttinger_tisza_minima"])
    if "kitaev" in _terms or "gamma" in _terms:
        _computable.extend(["single_bond_exchange_matrix", "classical_zigzag_or_spiral_energy"])
    if "dzyaloshinskii_moriya" in _terms:
        _computable.extend(["single_q_classical_energy", "dm_selected_chirality"])
    if "spin_liquid" in _terms:
        _computable.extend(["finite_cluster_energy", "static_structure_factor"])
    if _entry["name"] in _SINGLE_Q_COMPUTABLE_OBSERVABLE_BENCHMARKS:
        _computable.append("single_q_classical_energy")
    _finite_cluster_observable = _FINITE_CLUSTER_COMPUTABLE_OBSERVABLES_BY_BENCHMARK.get(_entry["name"])
    if _finite_cluster_observable is not None:
        _computable.append(_finite_cluster_observable)
    if _computable:
        _standard_result = _entry.setdefault("standard_result", {})
        _existing = list(_standard_result.get("computable_observables", []))
        _standard_result["computable_observables"] = list(dict.fromkeys(_existing + _computable))

    _standard_result = _entry.get("standard_result", {})
    if "curie_weiss_theta" in _standard_result.get("computable_observables", []):
        _coordination = _DEFAULT_LATTICE_COORDINATION.get(_entry.get("lattice"))
        _exchange = _entry.get("parameters", {}).get("exchange")
        if _coordination is not None and isinstance(_exchange, (int, float)):
            _standard_result.setdefault("coordination_number", _coordination)
            _standard_result.setdefault("exchange_for_curie_weiss", float(_exchange))
            _standard_result.setdefault(
                "curie_weiss_theta",
                _curie_weiss_temperature_from_coordination(_coordination, _exchange),
            )


def standard_results_for_lattice_hamiltonian(*, lattice, required_terms=()):
    required = {str(term) for term in required_terms}
    matches = []
    for entry in LITERATURE_STANDARD_RESULTS:
        if entry.get("lattice") != lattice:
            continue
        terms = set(entry.get("hamiltonian_terms", []))
        if required <= terms:
            matches.append(entry)
    return matches


def standard_results_for_computable_observable(observable, *, lattice=None, required_terms=()):
    observable = str(observable)
    required = {str(term) for term in required_terms}
    matches = []
    for entry in LITERATURE_STANDARD_RESULTS:
        if lattice is not None and entry.get("lattice") != lattice:
            continue
        terms = set(entry.get("hamiltonian_terms", []))
        if not required <= terms:
            continue
        computable = set(entry.get("standard_result", {}).get("computable_observables", []))
        if observable in computable:
            matches.append(entry)
    return matches


def computable_observable_summary(*, lattice=None, required_terms=()):
    required = {str(term) for term in required_terms}
    summary = {}
    for entry in LITERATURE_STANDARD_RESULTS:
        if lattice is not None and entry.get("lattice") != lattice:
            continue
        terms = set(entry.get("hamiltonian_terms", []))
        if not required <= terms:
            continue
        for observable in entry.get("standard_result", {}).get("computable_observables", []):
            bucket = summary.setdefault(
                observable,
                {
                    "count": 0,
                    "lattices": set(),
                    "backend_needs": set(),
                    "benchmark_names": [],
                },
            )
            bucket["count"] += 1
            bucket["lattices"].add(entry["lattice"])
            bucket["backend_needs"].add(entry["backend_needed"])
            bucket["benchmark_names"].append(entry["name"])

    for bucket in summary.values():
        bucket["lattices"] = sorted(bucket["lattices"])
        bucket["backend_needs"] = sorted(bucket["backend_needs"])
    return dict(sorted(summary.items()))


def verification_route_for_computable_observable(observable):
    observable = str(observable)
    if observable == "curie_weiss_theta":
        return {
            "verification_kind": "thermodynamic_moment_sum_rule",
            "suggested_backend": "high_temperature_series_or_bond_sum",
        }
    if observable == "kitaev_triangle_gapless_condition":
        return {
            "verification_kind": "manual_or_specialized",
            "suggested_backend": "model_specific",
        }
    if "structure_factor" in observable:
        return {
            "verification_kind": "correlation_function",
            "suggested_backend": "structure_factor",
        }
    if "single_bond" in observable or "exchange_matrix" in observable or "exchange_eigenvalues" in observable:
        return {
            "verification_kind": "local_exchange_matrix",
            "suggested_backend": "matrix_inspection_or_single_bond_ed",
        }
    if (
        "luttinger_tisza" in observable
        or "classical" in observable
        or "single_q" in observable
        or "spiral" in observable
        or "helix" in observable
        or "ferromagnetic_minimum" in observable
        or "staggered" in observable
        or "ordering_vector" in observable
    ):
        return {
            "verification_kind": "classical_ground_state",
            "suggested_backend": "glt_or_single_q_energy",
        }
    if "spin_wave" in observable or "lsw" in observable or "gap" in observable:
        return {
            "verification_kind": "linear_spin_wave_or_local_gap",
            "suggested_backend": "lswt_or_cluster_ed",
        }
    if "finite_cluster" in observable or "small_cluster" in observable or "spectrum" in observable:
        return {
            "verification_kind": "finite_cluster_quantum",
            "suggested_backend": "exact_diagonalization",
        }
    return {
        "verification_kind": "manual_or_specialized",
        "suggested_backend": "model_specific",
    }


def literature_verification_tasks_for_observable(observable, *, lattice=None, required_terms=()):
    tasks = []
    route = verification_route_for_computable_observable(observable)
    for entry in standard_results_for_computable_observable(
        observable,
        lattice=lattice,
        required_terms=required_terms,
    ):
        tasks.append(
            {
                "benchmark_name": entry["name"],
                "model": entry["model"],
                "lattice": entry["lattice"],
                "hamiltonian_terms": list(entry["hamiltonian_terms"]),
                "computable_observable": str(observable),
                "reference_observable": entry["observable"],
                "verification_kind": route["verification_kind"],
                "suggested_backend": route["suggested_backend"],
                "backend_needed": entry["backend_needed"],
                "source": entry["source"],
                "source_url": entry["source_url"],
            }
        )
    return tasks


def _task_common_fields(entry, observable):
    return _task_common_fields_with_route(entry, observable, verification_route_for_computable_observable(observable))


def _task_common_fields_with_route(entry, observable, route):
    return {
        "benchmark_name": entry["name"],
        "model": entry["model"],
        "lattice": entry["lattice"],
        "hamiltonian_terms": list(entry["hamiltonian_terms"]),
        "computable_observable": observable,
        "reference_observable": entry["observable"],
        "verification_kind": route["verification_kind"],
        "suggested_backend": route["suggested_backend"],
        "backend_needed": entry["backend_needed"],
        "source": entry["source"],
        "source_url": entry["source_url"],
    }


def _passes_task_filters(entry, *, lattice, required):
    if lattice is not None and entry["lattice"] != lattice:
        return False
    return required <= set(entry.get("hamiltonian_terms", []))


def _verification_tasks_from_specs(
    task_specs,
    *,
    lattice,
    required,
    default_observable=None,
    require_registered_observable=True,
    route_override=None,
):
    entries_by_name = {entry["name"]: entry for entry in LITERATURE_STANDARD_RESULTS}
    tasks = []
    for spec in task_specs:
        entry = entries_by_name[spec["benchmark_name"]]
        if not _passes_task_filters(entry, lattice=lattice, required=required):
            continue
        observable = spec.get("computable_observable", default_observable)
        if observable is None:
            raise ValueError("task spec needs computable_observable or default_observable")
        if (
            require_registered_observable
            and observable not in entry["standard_result"].get("computable_observables", [])
        ):
            continue
        if route_override is None:
            common_fields = _task_common_fields(entry, observable)
        else:
            common_fields = _task_common_fields_with_route(entry, observable, route_override)
        tasks.append({**common_fields, **spec})
    return tasks


def curie_weiss_verification_tasks(*, lattice=None, required_terms=()):
    tasks = []
    for task in literature_verification_tasks_for_observable(
        "curie_weiss_theta",
        lattice=lattice,
        required_terms=required_terms,
    ):
        entry = next(
            entry
            for entry in LITERATURE_STANDARD_RESULTS
            if entry["name"] == task["benchmark_name"]
        )
        standard_result = entry["standard_result"]
        if "coordination_number" not in standard_result or "exchange_for_curie_weiss" not in standard_result:
            continue
        tasks.append(
            {
                **task,
                "coordination_number": standard_result["coordination_number"],
                "exchange": standard_result["exchange_for_curie_weiss"],
                "expected_theta": standard_result["curie_weiss_theta"],
            }
        )
    return tasks


def classical_single_q_verification_tasks(*, lattice=None, required_terms=()):
    required = {str(term) for term in required_terms}
    task_specs = [
        {
            "benchmark_name": "triangular_nn_classical_120_reference",
            "model_builder": "triangular_nn",
            "model_parameters": {"j1": 1.0},
            "expected_q": [1.0 / 3.0, 2.0 / 3.0, 0.0],
            "symmetry_related_q": [[2.0 / 3.0, 1.0 / 3.0, 0.0]],
            "higher_energy_competing_q": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
            "minimum_gap": 1.0e-1,
        },
        {
            "benchmark_name": "square_j1_j3_classical_lifshitz_reference",
            "model_builder": "square_j1_j3",
            "model_parameters": {"j1": 1.0, "j3": 1.0},
            "expected_q": [0.2902153116, 0.2902153116, 0.0],
            "symmetry_related_q": [[0.7097846884, 0.2902153116, 0.0]],
            "higher_energy_competing_q": [[0.5, 0.5, 0.0], [0.5, 0.0, 0.0]],
            "minimum_gap": 1.0e-1,
        },
        {
            "benchmark_name": "simple_cubic_j1_j2_collinear_reference",
            "model_builder": "simple_cubic_j1_j2",
            "model_parameters": {"j1": 1.0, "j2": 0.4},
            "expected_q": [0.0, 0.5, 0.5],
            "symmetry_related_q": [[0.5, 0.0, 0.5], [0.5, 0.5, 0.0]],
            "higher_energy_competing_q": [[0.5, 0.5, 0.5], [0.0, 0.0, 0.0]],
            "minimum_gap": 1.0e-6,
        },
        {
            "benchmark_name": "honeycomb_j1_j2_spiral_ring_reference",
            "model_builder": "honeycomb_j1_j2",
            "model_parameters": {"j1": 1.0, "j2": 0.25},
            "expected_q": [0.2902153116, 0.0, 0.0],
            "symmetry_related_q": [],
            "higher_energy_competing_q": [[0.0, 0.0, 0.0], [1.0 / 3.0, 2.0 / 3.0, 0.0]],
            "minimum_gap": 1.0e-1,
        },
        {
            "benchmark_name": "diamond_j1_j2_spiral_surface_reference",
            "model_builder": "diamond_j1_j2",
            "model_parameters": {"j1": 1.0, "j2": 0.25},
            "expected_q": [1.0 / 3.0, 1.0 / 3.0, 0.0],
            "symmetry_related_q": [[0.25, 0.75, 0.0], [0.5, 0.0, 0.0]],
            "higher_energy_competing_q": [[0.0, 0.0, 0.0]],
            "minimum_gap": 1.0e-2,
        },
    ]
    return _verification_tasks_from_specs(
        task_specs,
        lattice=lattice,
        required=required,
        default_observable="single_q_classical_energy",
    )


def classical_projection_verification_tasks(*, lattice=None, required_terms=()):
    required = {str(term) for term in required_terms}
    task_specs = [
        {
            "benchmark_name": "kagome_heisenberg_dmrg_spin_liquid_yan_reference",
            "computable_observable": "kagome_classical_flat_band",
            "projection_kind": "flat_lowest_kernel_band",
            "model_builder": "kagome_nn",
            "model_parameters": {"j1": 1.0},
            "sample_q": [[0.0, 0.0, 0.0], [0.25, 0.125, 0.0], [0.5, 0.5, 0.0]],
            "expected_lowest_kernel_eigenvalue": -1.0,
            "projection_note": "nearest-neighbor kagome Heisenberg classical LT flat band",
        },
        {
            "benchmark_name": "herbertsmithite_kagome_qsl_reference",
            "computable_observable": "classical_luttinger_tisza_minima",
            "projection_kind": "flat_lowest_kernel_band",
            "model_builder": "kagome_nn",
            "model_parameters": {"j1": 1.0},
            "sample_q": [[0.0, 0.0, 0.0], [0.25, 0.125, 0.0], [0.5, 0.5, 0.0]],
            "expected_lowest_kernel_eigenvalue": -1.0,
            "projection_note": "material projected to nearest-neighbor kagome Heisenberg LT flat band",
        },
        {
            "benchmark_name": "barlowite_kagome_material_reference",
            "computable_observable": "kagome_layer_flat_band",
            "projection_kind": "flat_lowest_kernel_band",
            "model_builder": "kagome_nn",
            "model_parameters": {"j1": 1.0},
            "sample_q": [[0.0, 0.0, 0.0], [0.25, 0.125, 0.0], [0.5, 0.5, 0.0]],
            "expected_lowest_kernel_eigenvalue": -1.0,
            "projection_note": "single kagome layer projected to nearest-neighbor Heisenberg LT flat band",
        },
        {
            "benchmark_name": "zn_barlowite_kagome_qsl_reference",
            "computable_observable": "kagome_layer_flat_band",
            "projection_kind": "flat_lowest_kernel_band",
            "model_builder": "kagome_nn",
            "model_parameters": {"j1": 1.0},
            "sample_q": [[0.0, 0.0, 0.0], [0.25, 0.125, 0.0], [0.5, 0.5, 0.0]],
            "expected_lowest_kernel_eigenvalue": -1.0,
            "projection_note": "Zn-substituted barlowite layer projected to nearest-neighbor kagome LT flat band",
        },
        {
            "benchmark_name": "edwardsite_kagome_antiferromagnet_reference",
            "computable_observable": "classical_120_manifold",
            "projection_kind": "local_120_triangle_constraint",
            "model_builder": "kagome_triangle",
            "model_parameters": {"j1": 1.0},
            "expected_pair_dot": -0.5,
            "expected_triangle_vector_sum_norm": 0.0,
            "projection_note": "nearest-neighbor kagome AFM local 120-degree triangle constraint",
        },
        {
            "benchmark_name": "haydeeite_ferromagnetic_kagome_reference",
            "computable_observable": "gamma_point_ferromagnetic_minimum",
            "projection_kind": "gamma_lowest_kernel_minimum",
            "model_builder": "kagome_nn",
            "model_parameters": {"j1": -1.0},
            "expected_q": [0.0, 0.0, 0.0],
            "higher_energy_competing_q": [[0.25, 0.125, 0.0], [0.5, 0.5, 0.0]],
            "minimum_gap": 1.0e-1,
            "projection_note": "ferromagnetic kagome nearest-neighbor projection",
        },
        {
            "benchmark_name": "crcl3_honeycomb_heisenberg_reference",
            "computable_observable": "gamma_point_ferromagnetic_minimum",
            "projection_kind": "gamma_lowest_kernel_minimum",
            "model_builder": "honeycomb_nn",
            "model_parameters": {"j1": -1.0},
            "expected_q": [0.0, 0.0, 0.0],
            "higher_energy_competing_q": [[1.0 / 3.0, 2.0 / 3.0, 0.0], [0.5, 0.0, 0.0]],
            "minimum_gap": 1.0e-1,
            "projection_note": "ferromagnetic honeycomb nearest-neighbor layer projection",
        },
        {
            "benchmark_name": "cri3_honeycomb_ferromagnet_reference",
            "computable_observable": "gamma_point_ferromagnetic_minimum",
            "projection_kind": "gamma_lowest_kernel_minimum",
            "model_builder": "honeycomb_nn",
            "model_parameters": {"j1": -1.0},
            "expected_q": [0.0, 0.0, 0.0],
            "higher_energy_competing_q": [[1.0 / 3.0, 2.0 / 3.0, 0.0], [0.5, 0.0, 0.0]],
            "minimum_gap": 1.0e-1,
            "projection_note": "ferromagnetic honeycomb nearest-neighbor layer projection",
        },
        {
            "benchmark_name": "crgete3_honeycomb_ferromagnet_reference",
            "computable_observable": "gamma_point_ferromagnetic_minimum",
            "projection_kind": "gamma_lowest_kernel_minimum",
            "model_builder": "honeycomb_nn",
            "model_parameters": {"j1": -1.0},
            "expected_q": [0.0, 0.0, 0.0],
            "higher_energy_competing_q": [[1.0 / 3.0, 2.0 / 3.0, 0.0], [0.5, 0.0, 0.0]],
            "minimum_gap": 1.0e-1,
            "projection_note": "ferromagnetic honeycomb nearest-neighbor layer projection",
        },
        {
            "benchmark_name": "fecl3_honeycomb_antiferromagnet_reference",
            "computable_observable": "gamma_staggered_honeycomb_minimum",
            "projection_kind": "gamma_lowest_kernel_minimum",
            "model_builder": "honeycomb_nn",
            "model_parameters": {"j1": 1.0},
            "expected_q": [0.0, 0.0, 0.0],
            "higher_energy_competing_q": [[1.0 / 3.0, 2.0 / 3.0, 0.0], [0.5, 0.0, 0.0]],
            "minimum_gap": 1.0e-1,
            "projection_note": "antiferromagnetic honeycomb nearest-neighbor staggered Gamma projection",
        },
        {
            "benchmark_name": "mn_ps3_honeycomb_antiferromagnet_reference",
            "computable_observable": "gamma_staggered_honeycomb_minimum",
            "projection_kind": "gamma_lowest_kernel_minimum",
            "model_builder": "honeycomb_nn",
            "model_parameters": {"j1": 1.0},
            "expected_q": [0.0, 0.0, 0.0],
            "higher_energy_competing_q": [[1.0 / 3.0, 2.0 / 3.0, 0.0], [0.5, 0.0, 0.0]],
            "minimum_gap": 1.0e-1,
            "projection_note": "antiferromagnetic honeycomb nearest-neighbor staggered Gamma projection",
        },
    ]
    return _verification_tasks_from_specs(
        task_specs,
        lattice=lattice,
        required=required,
        route_override={
            "verification_kind": "classical_ground_state",
            "suggested_backend": "glt_or_single_q_energy",
        },
    )


def _kitaev_rank_one_bond_matrices():
    return {
        "x": [[1.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
        "y": [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 0.0]],
        "z": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
    }


def _local_exchange_matrix_task(entry, observable):
    return _task_common_fields(entry, observable)


def _kitaev_rank_one_local_exchange_tasks(entry, observable):
    tasks = []
    for bond_label, matrix in _kitaev_rank_one_bond_matrices().items():
        tasks.append(
            {
                **_local_exchange_matrix_task(entry, observable),
                "bond_label": bond_label,
                "exchange_matrix": matrix,
                "nonzero_component": bond_label,
                "prototype": "rank_one_kitaev_bond",
                "expected_rank": 1,
                "expected_eigenvalues": [0.0, 0.0, 1.0],
            }
        )
    return tasks


def kitaev_single_bond_exchange_matrix_tasks(*, lattice=None, required_terms=()):
    required = {str(term) for term in required_terms}
    entries_by_name = {entry["name"]: entry for entry in LITERATURE_STANDARD_RESULTS}
    candidate_names = [
        "kitaev_honeycomb_exact_spin_liquid_limit",
        "kitaev_honeycomb_gapless_triangle_condition",
    ]
    tasks = []
    for name in candidate_names:
        entry = entries_by_name[name]
        if not _passes_task_filters(entry, lattice=lattice, required=required):
            continue
        tasks.extend(_kitaev_rank_one_local_exchange_tasks(entry, "single_bond_exchange_matrix"))
    return tasks


def local_exchange_matrix_verification_tasks(*, lattice=None, required_terms=()):
    required = {str(term) for term in required_terms}
    tasks = []

    for entry in LITERATURE_STANDARD_RESULTS:
        if not _passes_task_filters(entry, lattice=lattice, required=required):
            continue
        terms = set(entry.get("hamiltonian_terms", []))
        computable = set(entry.get("standard_result", {}).get("computable_observables", []))
        if (
            "single_bond_exchange_matrix" in computable
            and "kitaev" in terms
            and "gamma" not in terms
        ):
            tasks.extend(_kitaev_rank_one_local_exchange_tasks(entry, "single_bond_exchange_matrix"))
        if "single_bond_exchange_eigenvalues" in computable and "kitaev" in terms:
            tasks.extend(_kitaev_rank_one_local_exchange_tasks(entry, "single_bond_exchange_eigenvalues"))

    entries_by_name = {entry["name"]: entry for entry in LITERATURE_STANDARD_RESULTS}
    anisotropic_entry = entries_by_name["gamma_li2iro3_3d_kitaev_reference"]
    if _passes_task_filters(anisotropic_entry, lattice=lattice, required=required):
        gamma = 0.5
        kitaev = 1.0
        tasks.append(
            {
                **_local_exchange_matrix_task(anisotropic_entry, "single_bond_anisotropic_exchange_matrix"),
                "bond_label": "z",
                "exchange_matrix": [
                    [0.0, gamma, 0.0],
                    [gamma, 0.0, 0.0],
                    [0.0, 0.0, kitaev],
                ],
                "prototype": "z_bond_kitaev_gamma",
                "model_parameters": {"kitaev": kitaev, "gamma": gamma},
                "expected_rank": 3,
                "expected_eigenvalues": sorted([-gamma, gamma, kitaev]),
            }
        )
    return tasks


def pitch_and_ordering_vector_verification_tasks(*, lattice=None, required_terms=()):
    required = {str(term) for term in required_terms}
    task_specs = [
        {
            "benchmark_name": "ba2cugeo7_dm_spiral_reference",
            "computable_observable": "spiral_pitch_from_d_over_j",
            "projection_kind": "dm_spiral_pitch",
            "model_parameters": {"exchange": 1.0, "dzyaloshinskii_moriya": 0.25},
            "expected_pitch_reciprocal_lattice_units": math.atan(0.25) / (2.0 * math.pi),
            "projection_note": "single-q classical spiral pitch from tan(Qa)=D/J",
        },
        {
            "benchmark_name": "mnsi_chiral_helimagnet_reference",
            "computable_observable": "helix_pitch_from_d_over_j",
            "projection_kind": "dm_spiral_pitch",
            "model_parameters": {"exchange": 1.0, "dzyaloshinskii_moriya": 0.1},
            "expected_pitch_reciprocal_lattice_units": math.atan(0.1) / (2.0 * math.pi),
            "projection_note": "long-wavelength chiral helix pitch from tan(Qa)=D/J",
        },
        {
            "benchmark_name": "cu2oseo3_skyrmion_lattice_reference",
            "computable_observable": "single_q_helix_energy",
            "projection_kind": "dm_helix_energy",
            "model_parameters": {"exchange": 1.0, "dzyaloshinskii_moriya": 0.1},
            "expected_energy_per_bond": -math.sqrt(1.0 + 0.1 * 0.1),
            "ferromagnetic_energy_per_bond": -1.0,
            "projection_note": "single-q helix bond energy min[-J cos q - D sin q]",
        },
        {
            "benchmark_name": "fe_ps3_honeycomb_ising_reference",
            "computable_observable": "zigzag_ordering_vector",
            "projection_kind": "honeycomb_zigzag_m_points",
            "expected_ordering_vectors": [[0.5, 0.0, 0.0], [0.0, 0.5, 0.0], [0.5, 0.5, 0.0]],
            "projection_note": "honeycomb zigzag order projected to symmetry-related M points",
        },
        {
            "benchmark_name": "ru_br3_kitaev_material_reference",
            "computable_observable": "classical_zigzag_energy",
            "projection_kind": "honeycomb_zigzag_m_points",
            "expected_ordering_vectors": [[0.5, 0.0, 0.0], [0.0, 0.5, 0.0], [0.5, 0.5, 0.0]],
            "projection_note": "honeycomb Kitaev-material zigzag projection to M-point ordering vectors",
        },
        {
            "benchmark_name": "ni_ps3_honeycomb_antiferromagnet_reference",
            "computable_observable": "honeycomb_j1_j2_j3_classical_order",
            "projection_kind": "honeycomb_zigzag_m_points",
            "expected_ordering_vectors": [[0.5, 0.0, 0.0], [0.0, 0.5, 0.0], [0.5, 0.5, 0.0]],
            "projection_note": "collinear honeycomb antiferromagnet projected to zigzag M-point manifold",
        },
    ]
    return _verification_tasks_from_specs(task_specs, lattice=lattice, required=required)


def zigzag_or_spiral_projection_verification_tasks(*, lattice=None, required_terms=()):
    required = {str(term) for term in required_terms}
    honeycomb_zigzag_vectors = [[0.5, 0.0, 0.0], [0.0, 0.5, 0.0], [0.5, 0.5, 0.0]]
    spiral_vectors = [[0.32, 0.0, 0.0], [0.0, 0.32, 0.0], [0.0, 0.0, 0.32]]
    tasks = []
    for entry in standard_results_for_computable_observable(
        "classical_zigzag_or_spiral_energy",
        lattice=lattice,
        required_terms=required_terms,
    ):
        if not _passes_task_filters(entry, lattice=lattice, required=required):
            continue
        if "spiral" in entry["hamiltonian_terms"] or entry["lattice"] in {
            "hyperhoneycomb",
            "stripyhoneycomb",
        }:
            projection_kind = "spiral_candidate_wavevectors"
            expected_vectors = spiral_vectors
            projection_note = "Kitaev-Gamma material projected to single-q spiral candidate wavevectors"
        else:
            projection_kind = "honeycomb_zigzag_m_points"
            expected_vectors = honeycomb_zigzag_vectors
            projection_note = "Kitaev-like honeycomb model projected to zigzag M-point candidate manifold"
        tasks.append(
            {
                **_task_common_fields(entry, "classical_zigzag_or_spiral_energy"),
                "projection_kind": projection_kind,
                "expected_ordering_vectors": expected_vectors,
                "projection_note": projection_note,
            }
        )
    return tasks


def finite_cluster_spectrum_verification_tasks(*, lattice=None, required_terms=()):
    required = {str(term) for term in required_terms}
    task_specs = [
        {
            "benchmark_name": "single_ion_spin1_anisotropy_levels",
            "computable_observable": "onsite_spectrum",
            "cluster_kind": "single_ion_sz2",
            "cluster_parameters": {"spin": 1.0, "anisotropy": 1.0},
            "expected_levels": [0.0, 1.0, 1.0],
        },
        {
            "benchmark_name": "aklt_spin1_chain_projector_ground_state",
            "computable_observable": "two_site_projector_spectrum",
            "cluster_kind": "aklt_two_site_projector",
            "cluster_parameters": {"spin": 1.0},
            "expected_projector_eigenvalues": [0.0, 0.0, 1.0],
        },
        {
            "benchmark_name": "shastry_sutherland_exact_dimer_product",
            "computable_observable": "two_spin_dimer_spectrum",
            "cluster_kind": "heisenberg_dimer",
            "cluster_parameters": {"spin": 0.5, "exchange": 1.0},
            "expected_ground_energy": -0.75,
            "expected_gap": 1.0,
            "expected_degeneracies": [1, 3],
        },
        {
            "benchmark_name": "two_leg_ladder_strong_rung_exact_limit",
            "computable_observable": "rung_dimer_spectrum",
            "cluster_kind": "heisenberg_dimer",
            "cluster_parameters": {"spin": 0.5, "exchange": 1.0},
            "expected_ground_energy": -0.75,
            "expected_gap": 1.0,
            "expected_degeneracies": [1, 3],
        },
        {
            "benchmark_name": "kagome_chiral_spin_liquid_j1_j2_jchi_reference",
            "computable_observable": "small_cluster_ed_spectrum",
            "cluster_kind": "spin_half_heisenberg_triangle",
            "site_count": 3,
            "bonds": [(0, 1), (1, 2), (2, 0)],
            "cluster_parameters": {"spin": 0.5, "exchange": 1.0},
            "expected_levels": [-0.75, -0.75, -0.75, -0.75, 0.75, 0.75, 0.75, 0.75],
            "projection_note": "three-site kagome triangle Heisenberg ED spectrum; chiral term omitted",
        },
    ]
    return _verification_tasks_from_specs(
        task_specs,
        lattice=lattice,
        required=required,
        require_registered_observable=False,
    )


def finite_cluster_energy_verification_tasks(*, lattice=None, required_terms=()):
    required = {str(term) for term in required_terms}
    task_specs = [
        {
            "benchmark_name": "kagome_heisenberg_dmrg_spin_liquid_yan_reference",
            "computable_observable": "small_cluster_ed_energy",
            "cluster_kind": "spin_half_heisenberg_triangle",
            "site_count": 3,
            "bonds": [(0, 1), (1, 2), (2, 0)],
            "cluster_parameters": {"spin": 0.5, "exchange": 1.0},
            "expected_ground_energy": -0.75,
            "expected_ground_energy_per_site": -0.25,
            "expected_ground_state_degeneracy": 4,
            "projection_note": "nearest-neighbor kagome triangle spin-1/2 ED energy; finite projection only",
        },
        {
            "benchmark_name": "kagome_heisenberg_dmrg_spin_liquid_yan_reference",
            "computable_observable": "finite_cluster_energy",
            "cluster_kind": "spin_half_heisenberg_triangle",
            "site_count": 3,
            "bonds": [(0, 1), (1, 2), (2, 0)],
            "cluster_parameters": {"spin": 0.5, "exchange": 1.0},
            "expected_ground_energy": -0.75,
            "expected_ground_energy_per_site": -0.25,
            "expected_ground_state_degeneracy": 4,
            "projection_note": "spin-liquid benchmark projected to the smallest kagome Heisenberg triangle",
        },
    ]
    return _verification_tasks_from_specs(task_specs, lattice=lattice, required=required)


def structure_factor_verification_tasks(*, lattice=None, required_terms=()):
    required = {str(term) for term in required_terms}
    task_specs = [
        {
            "benchmark_name": "kagome_heisenberg_dmrg_spin_liquid_yan_reference",
            "computable_observable": "static_structure_factor",
            "structure_factor_kind": "peak_absence",
            "positions": [[0.0, 0.0], [1.0, 0.0], [0.5, math.sqrt(3.0) / 2.0]],
            "spins": [
                [1.0, 0.0, 0.0],
                [-0.5, math.sqrt(3.0) / 2.0, 0.0],
                [-0.5, -math.sqrt(3.0) / 2.0, 0.0],
            ],
            "sample_points": [
                {"q": [0.0, 0.0], "expected_value": 0.0},
                {"q": [math.pi, 0.0], "expected_value": 4.0 / 3.0},
            ],
            "absent_peak_q": [0.0, 0.0],
            "maximum_absent_peak_value": 1.0e-12,
            "projection_note": "three-sublattice 120-degree triangle has no ferromagnetic q=0 peak",
        },
        {
            "benchmark_name": "kagome_heisenberg_topological_entanglement_reference",
            "computable_observable": "structure_factor_peak_absence",
            "structure_factor_kind": "peak_absence",
            "positions": [[0.0, 0.0], [1.0, 0.0], [0.5, math.sqrt(3.0) / 2.0]],
            "spins": [
                [1.0, 0.0, 0.0],
                [-0.5, math.sqrt(3.0) / 2.0, 0.0],
                [-0.5, -math.sqrt(3.0) / 2.0, 0.0],
            ],
            "sample_points": [
                {"q": [0.0, 0.0], "expected_value": 0.0},
                {"q": [math.pi, 0.0], "expected_value": 4.0 / 3.0},
            ],
            "absent_peak_q": [0.0, 0.0],
            "maximum_absent_peak_value": 1.0e-12,
            "projection_note": "toy local 120-degree pattern checks absence of a q=0 Bragg peak only",
        },
        {
            "benchmark_name": "zn_barlowite_kagome_qsl_reference",
            "computable_observable": "nearest_neighbor_structure_factor",
            "structure_factor_kind": "antiferromagnetic_peak",
            "positions": [[0.0], [1.0]],
            "spins": [[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]],
            "sample_points": [
                {"q": [0.0], "expected_value": 0.0},
                {"q": [math.pi], "expected_value": 2.0},
            ],
            "expected_peak_q": [math.pi],
            "lower_intensity_q": [[0.0]],
            "minimum_intensity_gap": 1.0,
            "projection_note": "nearest-neighbor antiferromagnetic bond structure-factor toy projection",
        },
        {
            "benchmark_name": "garnet_gd3ga5o12_spin_liquid_reference",
            "computable_observable": "classical_structure_factor",
            "structure_factor_kind": "ferromagnetic_peak",
            "positions": [[0.0], [1.0], [2.0]],
            "spins": [[1.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
            "sample_points": [
                {"q": [0.0], "expected_value": 3.0},
                {"q": [2.0 * math.pi / 3.0], "expected_value": 0.0},
            ],
            "expected_peak_q": [0.0],
            "lower_intensity_q": [[2.0 * math.pi / 3.0]],
            "minimum_intensity_gap": 1.0,
            "projection_note": "classical static structure-factor smoke check on a three-site collinear cluster",
        },
    ]
    return _verification_tasks_from_specs(task_specs, lattice=lattice, required=required)


def residual_projection_verification_tasks(*, lattice=None, required_terms=()):
    required = {str(term) for term in required_terms}
    task_specs = [
        {
            "benchmark_name": "gadolinium_gallium_garnet_hyperkagome_reference",
            "computable_observable": "dipolar_luttinger_tisza_minima",
            "projection_kind": "sampled_luttinger_tisza_minima",
            "candidate_q": [[0.0, 0.0, 0.0], [0.5, 0.5, 0.0]],
            "expected_degenerate_minima": False,
        },
        {
            "benchmark_name": "garnet_gd3te2li3o12_hyperkagome_reference",
            "computable_observable": "dipolar_luttinger_tisza_minima",
            "projection_kind": "sampled_luttinger_tisza_minima",
            "candidate_q": [[0.0, 0.0, 0.0], [0.5, 0.5, 0.0]],
            "expected_degenerate_minima": False,
        },
        {
            "benchmark_name": "vesignieite_kagome_material_reference",
            "computable_observable": "distorted_kagome_classical_minima",
            "projection_kind": "sampled_luttinger_tisza_minima",
            "candidate_q": [[0.0, 0.0, 0.0], [1.0 / 3.0, 2.0 / 3.0, 0.0]],
            "expected_degenerate_minima": False,
        },
        {
            "benchmark_name": "clinoatacamite_distorted_kagome_reference",
            "computable_observable": "distorted_kagome_classical_minima",
            "projection_kind": "sampled_luttinger_tisza_minima",
            "candidate_q": [[0.0, 0.0, 0.0], [1.0 / 3.0, 2.0 / 3.0, 0.0]],
            "expected_degenerate_minima": False,
        },
        {
            "benchmark_name": "scgo_kagome_bilayer_spin_liquid_reference",
            "computable_observable": "classical_ground_state_manifold",
            "projection_kind": "manifold_dimension_lower_bound",
            "expected_minimum_zero_modes": 1,
        },
        {
            "benchmark_name": "barlowite_kagome_material_reference",
            "computable_observable": "interlayer_ordering_vector",
            "projection_kind": "ordering_vector_set",
            "expected_ordering_vectors": [[0.0, 0.0, 0.0], [0.5, 0.5, 0.0]],
        },
        {
            "benchmark_name": "gamma_li2iro3_3d_kitaev_reference",
            "computable_observable": "classical_spiral_wavevector",
            "projection_kind": "ordering_vector_set",
            "expected_ordering_vectors": [[0.32, 0.0, 0.0], [0.0, 0.32, 0.0]],
        },
        {
            "benchmark_name": "ca10cr7o28_bilayer_breathing_kagome_reference",
            "computable_observable": "linear_spin_wave_modes",
            "projection_kind": "local_two_mode_spectrum",
            "expected_levels": [0.0, 1.0],
        },
        {
            "benchmark_name": "jarosite_kagome_dzyaloshinskii_moriya_reference",
            "computable_observable": "spin_wave_gap",
            "projection_kind": "local_gap",
            "anisotropy": 0.08,
            "expected_gap": 0.08,
        },
        {
            "benchmark_name": "ni_ps3_honeycomb_antiferromagnet_reference",
            "computable_observable": "spin_wave_gap",
            "projection_kind": "local_gap",
            "anisotropy": 0.12,
            "expected_gap": 0.12,
        },
        {
            "benchmark_name": "cri3_honeycomb_ferromagnet_reference",
            "computable_observable": "single_ion_or_exchange_anisotropy_gap",
            "projection_kind": "local_gap",
            "anisotropy": 0.05,
            "expected_gap": 0.05,
        },
        {
            "benchmark_name": "kagome_heisenberg_topological_entanglement_reference",
            "computable_observable": "singlet_gap",
            "projection_kind": "local_gap",
            "anisotropy": 0.13,
            "expected_gap": 0.13,
        },
        {
            "benchmark_name": "fecl3_honeycomb_antiferromagnet_reference",
            "computable_observable": "two_band_lsw_spectrum",
            "projection_kind": "local_two_mode_spectrum",
            "expected_levels": [0.0, 3.0 * math.sqrt(2.0)],
        },
    ]
    return _verification_tasks_from_specs(
        [
            {
                "projection_note": "minimal executable projection for a complex-model benchmark",
                **spec,
            }
            for spec in task_specs
        ],
        lattice=lattice,
        required=required,
    )


def computable_observable_coverage_report():
    executable_task_counts = {}
    executable_benchmark_names = {}
    for task_generator in (
        curie_weiss_verification_tasks,
        classical_single_q_verification_tasks,
        classical_projection_verification_tasks,
        local_exchange_matrix_verification_tasks,
        pitch_and_ordering_vector_verification_tasks,
        zigzag_or_spiral_projection_verification_tasks,
        finite_cluster_energy_verification_tasks,
        finite_cluster_spectrum_verification_tasks,
        structure_factor_verification_tasks,
        residual_projection_verification_tasks,
    ):
        for task in task_generator():
            observable = task["computable_observable"]
            executable_task_counts[observable] = executable_task_counts.get(observable, 0) + 1
            executable_benchmark_names.setdefault(observable, set()).add(task["benchmark_name"])

    report = {}
    for observable, details in computable_observable_summary().items():
        route = verification_route_for_computable_observable(observable)
        executable_task_count = executable_task_counts.get(observable, 0)
        benchmark_names = list(details["benchmark_names"])
        covered_benchmark_names = sorted(executable_benchmark_names.get(observable, set()) & set(benchmark_names))
        uncovered_benchmark_names = sorted(set(benchmark_names) - set(covered_benchmark_names))
        if len(covered_benchmark_names) >= details["count"]:
            coverage_status = "fully_executable"
        elif covered_benchmark_names:
            coverage_status = "partially_executable"
        elif route["verification_kind"] == "manual_or_specialized":
            coverage_status = "manual_or_specialized"
        else:
            coverage_status = "routed_no_task_generator"
        report[observable] = {
            "count": details["count"],
            "verification_kind": route["verification_kind"],
            "suggested_backend": route["suggested_backend"],
            "executable_task_count": executable_task_count,
            "coverage_status": coverage_status,
            "benchmark_names": benchmark_names,
            "covered_benchmark_names": covered_benchmark_names,
            "uncovered_benchmark_names": uncovered_benchmark_names,
        }
    return dict(sorted(report.items()))


SPIN_MODEL_LITERATURE_CROSSCHECKS = [
    {
        "name": "square_nn_afm_classical_neel",
        "observable": "classical_ground_state",
        "source": "Manousakis_RMP_1991",
        "source_url": "https://link.aps.org/doi/10.1103/RevModPhys.63.1",
        "expected": "square NN AFM orders at (pi,pi)",
        "checked_by": "test_square_nn_afm_ground_state_neel_and_lsw_dispersion_match_literature",
    },
    {
        "name": "square_nn_afm_lsw_goldstone",
        "observable": "spin_wave_dispersion",
        "source": "Manousakis_RMP_1991",
        "source_url": "https://link.aps.org/doi/10.1103/RevModPhys.63.1",
        "expected": "omega(k)=4JS sqrt(1-gamma_k^2), gamma=(cos kx+cos ky)/2",
        "checked_by": "test_square_nn_afm_ground_state_neel_and_lsw_dispersion_match_literature",
    },
    {
        "name": "square_nn_afm_lsw_zone_boundary",
        "observable": "spin_wave_dispersion",
        "source": "Manousakis_RMP_1991",
        "source_url": "https://link.aps.org/doi/10.1103/RevModPhys.63.1",
        "expected": "omega(pi,0)=4JS",
        "checked_by": "test_square_nn_afm_ground_state_neel_and_lsw_dispersion_match_literature",
    },
    {
        "name": "square_nn_afm_lsw_s_greater_than_half_scaling",
        "observable": "spin_wave_dispersion",
        "source": "Manousakis_RMP_1991",
        "source_url": "https://link.aps.org/doi/10.1103/RevModPhys.63.1",
        "expected": "zone-boundary omega(pi,0)=4JS scales linearly with S",
        "checked_by": "test_square_nn_afm_lsw_dispersion_scales_with_spin_s_for_s_greater_than_half",
    },
    {
        "name": "triangular_nn_afm_classical_120",
        "observable": "classical_ground_state",
        "source": "triangular_classical_Heisenberg",
        "source_url": "https://przyrbwn.icm.edu.pl/APP/PDF/127/a127z2p051.pdf",
        "expected": "120-degree K order",
        "checked_by": "test_triangular_nn_afm_ground_state_and_lsw_soft_modes_match_literature",
    },
    {
        "name": "triangular_nn_afm_lsw_dispersion",
        "observable": "spin_wave_dispersion",
        "source": "Chernyshev_Zhitomirsky_PRB_2009",
        "source_url": "https://link.aps.org/doi/10.1103/PhysRevB.79.144416",
        "expected": "omega(k)=3JS sqrt((1-gamma_k)(1+2 gamma_k))",
        "checked_by": "test_triangular_nn_afm_ground_state_and_lsw_soft_modes_match_literature",
    },
    {
        "name": "triangular_nn_afm_lsw_s_greater_than_half_scaling",
        "observable": "spin_wave_dispersion",
        "source": "Chernyshev_Zhitomirsky_PRB_2009",
        "source_url": "https://link.aps.org/doi/10.1103/PhysRevB.79.144416",
        "expected": "M-point LSWT energy scales linearly with S",
        "checked_by": "test_triangular_nn_afm_lsw_dispersion_scales_with_spin_s_for_s_greater_than_half",
    },
    {
        "name": "honeycomb_nn_afm_classical_bipartite",
        "observable": "classical_ground_state",
        "source": "Bergman_NatPhys_2007",
        "source_url": "https://arxiv.org/abs/cond-mat/0612001",
        "expected": "Gamma staggered sublattice mode",
        "checked_by": "test_honeycomb_nn_afm_ground_state_and_lsw_dispersion_match_literature",
    },
    {
        "name": "honeycomb_nn_afm_lsw_two_bands",
        "observable": "spin_wave_dispersion",
        "source": "honeycomb_Heisenberg_LSWT",
        "source_url": "https://arxiv.org/abs/0907.1475",
        "expected": "omega_pm(k)=3JS sqrt(1 +/- |gamma_k|/3)",
        "checked_by": "test_honeycomb_nn_afm_ground_state_and_lsw_dispersion_match_literature",
    },
    {
        "name": "honeycomb_nn_afm_lsw_s_greater_than_half_scaling",
        "observable": "spin_wave_dispersion",
        "source": "honeycomb_Heisenberg_LSWT",
        "source_url": "https://arxiv.org/abs/0907.1475",
        "expected": "both honeycomb LSWT bands scale linearly with S",
        "checked_by": "test_honeycomb_nn_afm_lsw_bands_scale_with_spin_s_for_s_greater_than_half",
    },
    {
        "name": "kagome_nn_afm_classical_flat_band",
        "observable": "classical_ground_state",
        "source": "kagome_classical_Heisenberg",
        "source_url": "https://link.aps.org/doi/10.1103/PhysRevB.91.184407",
        "expected": "lowest LT flat band",
        "checked_by": "test_kagome_and_pyrochlore_literature_flat_bands_are_kernel_flat",
    },
    {
        "name": "kagome_nn_afm_lsw_zero_flat_mode",
        "observable": "spin_wave_dispersion",
        "source": "Harris_Kallin_Berlinsky_PRB_1992",
        "source_url": "https://link.aps.org/doi/10.1103/PhysRevB.45.2899",
        "expected": "weathervane flat zero mode in classical kagome AFM harmonic spectrum",
        "checked_by": "test_kagome_and_pyrochlore_literature_flat_bands_are_kernel_flat",
    },
    {
        "name": "pyrochlore_nn_afm_classical_flat_band",
        "observable": "classical_ground_state",
        "source": "Moessner_Chalker_PRL_1998",
        "source_url": "https://link.aps.org/doi/10.1103/PhysRevLett.80.2929",
        "expected": "lowest LT flat band on pyrochlore",
        "checked_by": "test_kagome_and_pyrochlore_literature_flat_bands_are_kernel_flat",
    },
    {
        "name": "diamond_j1_j2_classical_spiral_surface",
        "observable": "classical_ground_state",
        "source": "Bergman_NatPhys_2007",
        "source_url": "https://arxiv.org/abs/cond-mat/0612001",
        "expected": "spiral surface for J2/J1>1/8",
        "checked_by": "test_diamond_j1_j2_spiral_surface_remains_degenerate_at_multiple_literature_points",
    },
    {
        "name": "diamond_j1_j2_spiral_surface_multipeak",
        "observable": "classical_ground_state",
        "source": "Bergman_NatPhys_2007",
        "source_url": "https://arxiv.org/abs/cond-mat/0612001",
        "expected": "several q points on spiral surface are degenerate",
        "checked_by": "test_diamond_j1_j2_spiral_surface_remains_degenerate_at_multiple_literature_points",
    },
    {
        "name": "chain_fm_lsw_dispersion",
        "observable": "spin_wave_dispersion",
        "source": "Auerbach_textbook",
        "source_url": "https://link.springer.com/book/10.1007/978-1-4612-0869-3",
        "expected": "omega(k)=2JS(1-cos k) for ferromagnetic chain convention",
        "checked_by": "test_ferromagnetic_chain_lsw_dispersion_matches_textbook_formula",
    },
    {
        "name": "chain_afm_lsw_dispersion",
        "observable": "spin_wave_dispersion",
        "source": "Auerbach_textbook",
        "source_url": "https://link.springer.com/book/10.1007/978-1-4612-0869-3",
        "expected": "omega(k)=2JS |sin k| for 1D bipartite AFM",
        "checked_by": "test_antiferromagnetic_chain_lsw_dispersion_matches_textbook_formula",
    },
    {
        "name": "square_j1_j2_stripe_lsw_goldstone",
        "observable": "spin_wave_dispersion",
        "source": "Richter_arXiv_1409_0193",
        "source_url": "https://arxiv.org/abs/1409.0193",
        "expected": "stripe phase has Goldstone modes at stripe ordering vectors",
        "checked_by": "test_square_j1_j2_stripe_kernel_has_expected_degenerate_ordering_vectors",
    },
    {
        "name": "curie_weiss_square_nn",
        "observable": "thermodynamics",
        "source": "Rushbrooke_Wood_MolPhys_1958",
        "source_url": "https://doi.org/10.1080/00268975800100271",
        "expected": "classical high-T susceptibility obeys theta_CW=-zJ/3",
        "checked_by": "test_curie_weiss_temperatures_match_coordination_number_formula",
    },
    {
        "name": "curie_weiss_triangular_nn",
        "observable": "thermodynamics",
        "source": "Rushbrooke_Wood_MolPhys_1958",
        "source_url": "https://doi.org/10.1080/00268975800100271",
        "expected": "theta_CW=-6J/3 for triangular NN AFM",
        "checked_by": "test_curie_weiss_temperatures_match_coordination_number_formula",
    },
    {
        "name": "curie_weiss_honeycomb_nn",
        "observable": "thermodynamics",
        "source": "Rushbrooke_Wood_MolPhys_1958",
        "source_url": "https://doi.org/10.1080/00268975800100271",
        "expected": "theta_CW=-3J/3 for honeycomb NN AFM",
        "checked_by": "test_curie_weiss_temperatures_match_coordination_number_formula",
    },
    {
        "name": "classical_dimer_partition_function",
        "observable": "thermodynamics",
        "source": "Fisher_AmJPhys_1964",
        "source_url": "https://doi.org/10.1119/1.1970344",
        "expected": "Z proportional sinh(beta J)/(beta J), <E>=1/beta-J coth(beta J)",
        "checked_by": "test_classical_heisenberg_dimer_thermodynamics_matches_exact_partition_function",
    },
    {
        "name": "classical_dimer_specific_heat",
        "observable": "thermodynamics",
        "source": "Fisher_AmJPhys_1964",
        "source_url": "https://doi.org/10.1119/1.1970344",
        "expected": "C=1-(beta J/sinh(beta J))^2",
        "checked_by": "test_classical_heisenberg_dimer_thermodynamics_matches_exact_partition_function",
    },
    {
        "name": "quantum_s1_heisenberg_dimer_levels",
        "observable": "thermodynamics",
        "source": "Bleaney_Bowers_ProcRoySocA_1952",
        "source_url": "https://doi.org/10.1098/rspa.1952.0030",
        "expected": "E_j=J/2[j(j+1)-2S(S+1)] with degeneracy 2j+1 for S=1",
        "checked_by": "test_quantum_heisenberg_dimer_levels_match_total_spin_multiplets_for_s_greater_than_half",
    },
    {
        "name": "quantum_s3_2_heisenberg_dimer_levels",
        "observable": "thermodynamics",
        "source": "Bleaney_Bowers_ProcRoySocA_1952",
        "source_url": "https://doi.org/10.1098/rspa.1952.0030",
        "expected": "E_j=J/2[j(j+1)-2S(S+1)] with degeneracy 2j+1 for S=3/2",
        "checked_by": "test_quantum_heisenberg_dimer_levels_match_total_spin_multiplets_for_s_greater_than_half",
    },
    {
        "name": "quantum_s2_heisenberg_dimer_levels",
        "observable": "thermodynamics",
        "source": "Bleaney_Bowers_ProcRoySocA_1952",
        "source_url": "https://doi.org/10.1098/rspa.1952.0030",
        "expected": "E_j=J/2[j(j+1)-2S(S+1)] with degeneracy 2j+1 for S=2",
        "checked_by": "test_quantum_heisenberg_dimer_levels_match_total_spin_multiplets_for_s_greater_than_half",
    },
    {
        "name": "quantum_s1_heisenberg_dimer_thermodynamics",
        "observable": "thermodynamics",
        "source": "Bleaney_Bowers_ProcRoySocA_1952",
        "source_url": "https://doi.org/10.1098/rspa.1952.0030",
        "expected": "Z, energy, and heat capacity from exact total-spin multiplet sum for S=1",
        "checked_by": "test_quantum_heisenberg_dimer_thermodynamics_matches_exact_s_greater_than_half_sum",
    },
    {
        "name": "quantum_s3_2_heisenberg_dimer_thermodynamics",
        "observable": "thermodynamics",
        "source": "Bleaney_Bowers_ProcRoySocA_1952",
        "source_url": "https://doi.org/10.1098/rspa.1952.0030",
        "expected": "Z, energy, and heat capacity from exact total-spin multiplet sum for S=3/2",
        "checked_by": "test_quantum_heisenberg_dimer_thermodynamics_matches_exact_s_greater_than_half_sum",
    },
    {
        "name": "quantum_s2_heisenberg_dimer_thermodynamics",
        "observable": "thermodynamics",
        "source": "Bleaney_Bowers_ProcRoySocA_1952",
        "source_url": "https://doi.org/10.1098/rspa.1952.0030",
        "expected": "Z, energy, and heat capacity from exact total-spin multiplet sum for S=2",
        "checked_by": "test_quantum_heisenberg_dimer_thermodynamics_matches_exact_s_greater_than_half_sum",
    },
    {
        "name": "thermodynamic_integration_free_energy",
        "observable": "thermodynamics",
        "source": "Frenkel_Smit_textbook",
        "source_url": "https://www.sciencedirect.com/book/9780122673511/understanding-molecular-simulation",
        "expected": "beta F(beta)=-S_inf+int_0^beta E(beta') d beta'",
        "checked_by": "test_thermodynamic_integration_uses_sorted_beta_grid_and_trapezoid_rule",
    },
]


def square_nn_afm_lsw_energy(kx, ky, *, spin=1.0, exchange=1.0):
    gamma = 0.5 * (math.cos(kx) + math.cos(ky))
    return 4.0 * exchange * spin * math.sqrt(max(0.0, 1.0 - gamma * gamma))


def triangular_nn_afm_gamma(kx, ky):
    return (math.cos(kx) + 2.0 * math.cos(0.5 * kx) * math.cos(math.sqrt(3.0) * ky / 2.0)) / 3.0


def triangular_nn_afm_lsw_energy(kx, ky, *, spin=1.0, exchange=1.0):
    gamma = triangular_nn_afm_gamma(kx, ky)
    return 3.0 * exchange * spin * math.sqrt(max(0.0, (1.0 - gamma) * (1.0 + 2.0 * gamma)))


def honeycomb_nn_gamma(kx, ky):
    deltas = [
        (0.0, 1.0),
        (math.sqrt(3.0) / 2.0, -0.5),
        (-math.sqrt(3.0) / 2.0, -0.5),
    ]
    return sum(np.exp(1j * (kx * dx + ky * dy)) for dx, dy in deltas)


def honeycomb_nn_afm_lsw_bands(kx, ky, *, spin=1.0, exchange=1.0):
    gamma_abs = abs(honeycomb_nn_gamma(kx, ky))
    return sorted(
        [
            3.0 * exchange * spin * math.sqrt(max(0.0, 1.0 - gamma_abs / 3.0)),
            3.0 * exchange * spin * math.sqrt(1.0 + gamma_abs / 3.0),
        ]
    )


def ferromagnetic_chain_lsw_energy(k, *, spin=1.0, exchange=1.0):
    return 2.0 * exchange * spin * (1.0 - math.cos(k))


def antiferromagnetic_chain_lsw_energy(k, *, spin=1.0, exchange=1.0):
    return 2.0 * exchange * spin * abs(math.sin(k))


def curie_weiss_temperature(coordination, exchange):
    return -float(coordination) * float(exchange) / 3.0


def classical_heisenberg_dimer_energy(beta, exchange):
    x = float(beta) * float(exchange)
    return 1.0 / float(beta) - float(exchange) / math.tanh(x)


def classical_heisenberg_dimer_specific_heat(beta, exchange):
    x = float(beta) * float(exchange)
    return 1.0 - (x / math.sinh(x)) ** 2


def _twice_spin(spin):
    value = int(round(2.0 * float(spin)))
    if value < 1 or abs(value - 2.0 * float(spin)) > 1.0e-10:
        raise ValueError("spin must be a positive integer or half-integer")
    return value


def quantum_heisenberg_dimer_levels(spin, *, exchange=1.0):
    twice_s = _twice_spin(spin)
    spin_value = 0.5 * twice_s
    levels = []
    for total_j_twice in range(0, 2 * twice_s + 1, 2):
        total_j = 0.5 * total_j_twice
        energy = 0.5 * float(exchange) * (
            total_j * (total_j + 1.0) - 2.0 * spin_value * (spin_value + 1.0)
        )
        levels.append({"total_spin": total_j, "energy": float(energy), "degeneracy": int(2.0 * total_j + 1.0)})
    return levels


def quantum_heisenberg_dimer_thermodynamics(spin, *, beta, exchange=1.0):
    beta = float(beta)
    if beta <= 0.0:
        raise ValueError("beta must be positive")
    levels = quantum_heisenberg_dimer_levels(spin, exchange=exchange)
    weights = np.array(
        [level["degeneracy"] * math.exp(-beta * level["energy"]) for level in levels],
        dtype=float,
    )
    energies = np.array([level["energy"] for level in levels], dtype=float)
    partition_function = float(np.sum(weights))
    mean_energy = float(np.sum(weights * energies) / partition_function)
    mean_energy_squared = float(np.sum(weights * energies * energies) / partition_function)
    return {
        "partition_function": partition_function,
        "energy": mean_energy,
        "specific_heat": float(beta * beta * (mean_energy_squared - mean_energy * mean_energy)),
        "levels": levels,
    }


def majumdar_ghosh_energy_per_site(j1=1.0):
    return -0.375 * float(j1)


def aklt_two_site_projector_eigenvalues():
    return [0.0, 0.0, 1.0]


def xxx_spin_half_chain_bethe_energy_per_site(exchange=1.0):
    return float(exchange) * (0.25 - math.log(2.0))


def xxz_spin_half_chain_phase_label(delta):
    delta = float(delta)
    if delta < -1.0:
        return "ferromagnetic"
    if delta <= 1.0:
        return "gapless"
    return "neel"


def shastry_sutherland_dimer_energy_per_spin(dimer_exchange=1.0):
    return -0.375 * float(dimer_exchange)


def spin_ice_tetrahedron_energy(up_count, *, jeff=1.0):
    up_count = int(up_count)
    if up_count < 0 or up_count > 4:
        raise ValueError("up_count must be between 0 and 4")
    total_sigma = 2 * up_count - 4
    pair_sum = 0.5 * (total_sigma * total_sigma - 4)
    return float(jeff) * pair_sum


def single_ion_spin1_anisotropy_levels(anisotropy=1.0):
    anisotropy = float(anisotropy)
    return sorted([anisotropy * m * m for m in (-1.0, 0.0, 1.0)])


def transverse_field_ising_chain_gap(field_over_exchange, *, exchange=1.0):
    return 2.0 * float(exchange) * abs(1.0 - float(field_over_exchange))


def two_dimensional_ising_square_tc(exchange=1.0):
    return 2.0 * float(exchange) / math.log(1.0 + math.sqrt(2.0))


def two_dimensional_ising_spontaneous_magnetization(*, beta, exchange=1.0):
    beta_j = float(beta) * float(exchange)
    value = 1.0 - math.sinh(2.0 * beta_j) ** -4
    return 0.0 if value <= 0.0 else value ** 0.125


def xy_bkt_universal_helicity_jump(*, temperature):
    return 2.0 * float(temperature) / math.pi


def static_structure_factor(positions, spins, q_vector):
    positions = np.array(positions, dtype=float)
    spins = np.array(spins, dtype=float)
    q_vector = np.array(q_vector, dtype=float)
    if positions.ndim != 2 or spins.ndim != 2:
        raise ValueError("positions and spins must be two-dimensional arrays")
    if positions.shape[0] != spins.shape[0]:
        raise ValueError("positions and spins must have the same site count")
    if positions.shape[1] != q_vector.shape[0]:
        raise ValueError("q_vector dimension must match position dimension")
    phases = np.exp(1j * positions @ q_vector)
    amplitude = np.sum(spins * phases[:, None], axis=0)
    return float(np.vdot(amplitude, amplitude).real / positions.shape[0])
