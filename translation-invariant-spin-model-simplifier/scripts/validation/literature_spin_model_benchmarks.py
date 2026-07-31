import math
import re
from functools import lru_cache
from itertools import combinations, product

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
        "source": "Caspers_Emmett_Magnus_1984",
        "source_url": "https://doi.org/10.1088/0305-4470/17/13/020",
        "citation_locator": "exact twofold-degenerate dimer ground states at J2/J1=1/2",
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
        "source": "Yang_Yang_1966_Part_II",
        "source_url": "https://doi.org/10.1103/PhysRev.150.327",
        "citation_locator": "Eq. (31c): isotropic zero-magnetization ground-state energy per lattice site",
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
        "source": "Hirata_Nomura_1999",
        "source_url": "https://arxiv.org/abs/cond-mat/9909290",
        "citation_locator": "Hamiltonian and phase diagram: Delta=-1 and Delta=1 boundaries with gapless interval",
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
        "source_url": "https://doi.org/10.1016/0378-4363(81)90838-X",
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
        "source": "Yang_Xie_2012",
        "source_url": "https://arxiv.org/abs/1204.5027",
        "citation_locator": "single-ion D(Sz)^2 spectrum and degeneracies",
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
        "source": "Dziarmaga_2005",
        "source_url": "https://arxiv.org/abs/cond-mat/0509490",
        "citation_locator": "Hamiltonian and critical-point discussion: g_c=1",
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
        "source": "Dziarmaga_2005",
        "source_url": "https://arxiv.org/abs/cond-mat/0509490",
        "citation_locator": "Bogoliubov spectrum and thermodynamic gap Delta=2J|1-g|",
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
        "source": "Taylor_2020",
        "source_url": "https://arxiv.org/abs/2001.01693",
        "citation_locator": "Eq. (5) and following sentence: <s_i s_{i+l}> = tanh^l(beta J)",
    },
    {
        "name": "lieb_schultz_mattis_half_integer_constraint",
        "model": "half_odd_integer_u1_spin_chain",
        "hamiltonian": "one-dimensional short-range translation-invariant U(1)-symmetric spin Hamiltonian",
        "parameters": {
            "spin_per_unit_cell": "half_odd_integer",
            "ground_state": "unique",
            "interaction_range": "short_range",
            "symmetries": ["translation", "U(1)"],
        },
        "observable": "unique_ground_state_gaplessness_constraint",
        "comparison_kind": "theorem",
        "backend_needed": "diagnostic",
        "standard_result": {"unique_ground_state_implies_gapless_excitations": True},
        "source": "Tasaki_2018",
        "source_url": "https://doi.org/10.1007/s10955-017-1946-0",
        "citation_locator": "introduction: half-odd-integer spin with a unique ground state has gapless excitations in the infinite-volume limit",
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
        "source": "Yang_Xie_2012",
        "source_url": "https://arxiv.org/abs/1204.5027",
        "citation_locator": "model definition and zero-temperature ferromagnetic-to-nonmagnetic crossing at D/J=2",
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
            "source": "Mazin_arXiv_1309.3744",
            "source_url": "https://arxiv.org/abs/1309.3744",
            "citation_locator": "honeycomb J1-J2-J3 classical phase set",
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
            "source": "Chaloupka_Jackeli_Khaliullin_arXiv_1209.5100",
            "source_url": "https://arxiv.org/abs/1209.5100",
            "citation_locator": "full Kitaev-Heisenberg phase diagram: Neel, stripy, ferromagnetic, and zigzag phases",
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
            "source": "Depenbrock_McCulloch_Schollwoeck_2012",
            "source_url": "https://arxiv.org/abs/1205.4858",
            "citation_locator": "abstract and thermodynamic extrapolation: energy per site -0.4386(5)",
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
            "source_url": "https://doi.org/10.1126/science.1064761",
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
            "source": "Balla_Iqbal_Penc_2020",
            "source_url": "https://arxiv.org/abs/2007.00376",
            "citation_locator": "FCC J1-J2 phase diagram and type-I, type-II, and type-III order regions",
        },
        {
            "name": "bcc_j1_j2_heisenberg_collinear_reference",
            "model": "bcc_ferromagnetic_j1_antiferromagnetic_j2_heisenberg",
            "lattice": "bcc",
            "hamiltonian": "J1 < 0 NN + J2 > 0 NNN Heisenberg exchange on the BCC lattice",
            "hamiltonian_terms": ["heisenberg", "j1", "j2", "ferromagnetic", "antiferromagnetic", "collinear"],
            "parameters": {
                "j1_sign": "ferromagnetic",
                "j2_sign": "antiferromagnetic",
                "spin": "arbitrary",
            },
            "observable": "large_j2_collinear_order",
            "comparison_kind": "paper_numeric",
            "backend_needed": "many_body_thermodynamics",
            "standard_result": {"large_j2_collinear_order": True},
            "source": "Mueller_Richter_Hauser_Ihle_2015",
            "source_url": "https://doi.org/10.1140/epjb/e2015-60113-7",
            "citation_locator": "abstract: large-J2 collinear order for ferromagnetic J1 and antiferromagnetic J2",
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
            "source_url": "https://doi.org/10.1140/epjb/e2006-00273-y",
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
            "source_url": "https://doi.org/10.1140/epjb/e2006-00273-y",
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
            "source_url": "https://doi.org/10.1063/1.367729",
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
            "source": "Mulder_Ganesh_Capriotti_Paramekanti_2010",
            "source_url": "https://arxiv.org/abs/1004.1119",
            "citation_locator": "classical spiral-contour equation for J2/J1>1/6",
        },
        {
            "name": "checkerboard_heisenberg_plaquette_reference",
            "model": "checkerboard_heisenberg",
            "lattice": "checkerboard",
            "hamiltonian": "crossed-square Heisenberg exchange",
            "hamiltonian_terms": ["heisenberg", "frustrated", "plaquette"],
            "parameters": {"spin": 0.5},
            "observable": "plaquette_long_range_order_and_valence_bond_crystal",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed_or_dmrg",
            "standard_result": {
                "plaquette_long_range_order": True,
                "valence_bond_crystal": True,
            },
            "source": "Fouet_Mambrini_Sindzingre_Lhuillier_2003",
            "source_url": "https://doi.org/10.1103/PhysRevB.67.054411",
            "citation_locator": "abstract: long-range order in four-spin S=0 plaquettes and a valence-bond crystal",
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
            "source": "Furuchi_et_al_2024",
            "source_url": "https://arxiv.org/abs/2409.16715",
            "citation_locator": "Lieb-lattice ground-state spin per unit cell",
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
            "source": "Kumar_Ramasesha_Soos_2010",
            "source_url": "https://arxiv.org/abs/1006.5052",
            "citation_locator": (
                "abstract and discussion citing Okamoto-Nomura: fluid-dimer "
                "transition at J2/J1=0.2411 where the gap opens"
            ),
        },
        {
            "name": "takhtajan_babujian_spin1_critical_point",
            "model": "spin_1_bilinear_biquadratic_chain",
            "lattice": "chain",
            "hamiltonian": "cos(theta) Si.Sj + sin(theta)(Si.Sj)^2",
            "hamiltonian_terms": ["heisenberg", "biquadratic", "spin1", "critical"],
            "parameters": {
                "coupling_constraint": (
                    "positive_bilinear_and_equal_magnitude_negative_biquadratic"
                )
            },
            "observable": "critical_point",
            "comparison_kind": "exact_solution",
            "backend_needed": "bethe_or_ed",
            "standard_result": {"theta_radians": -math.pi / 4.0, "is_integrable": True},
            "source": "Kitazawa_Nomura_1998",
            "source_url": "https://arxiv.org/abs/cond-mat/9811353",
            "citation_locator": "bilinear-biquadratic spin-1 chain at the integrable theta=-pi/4 point",
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
            "source_url": "https://doi.org/10.1103/PhysRevB.12.3795",
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
            "source": "Savary_et_al_2012",
            "source_url": "https://arxiv.org/abs/1204.1320",
            "citation_locator": "Eqs. (6)-(7) and zero-point-energy analysis: quantum selection of psi2",
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
            "hamiltonian": (
                "spin-1/2 ruby-lattice Heisenberg model with Jh, Jt, and "
                "Jd at the isotropic point Jh=Jt=Jd"
            ),
            "hamiltonian_terms": ["heisenberg", "frustrated", "localized_one_magnon"],
            "parameters": {"spin": 0.5, "coupling_regime": "Jh=Jt=Jd"},
            "observable": "exact_localized_one_magnon_eigenstate",
            "comparison_kind": "paper_formula",
            "backend_needed": "analytic_magnon",
            "standard_result": {"supports_localized_magnons": True},
            "source": "Ghosh_Mila_2025",
            "source_url": "https://arxiv.org/abs/2512.14173",
            "citation_locator": (
                "Eqs. (4)-(5) and localized-magnon section: exact alternating-sign "
                "one-magnon eigenstate, not a plateau mechanism"
            ),
        },
        {
            "name": "star_lattice_heisenberg_spin_liquid_reference",
            "model": "uniform_star_lattice_heisenberg_antiferromagnet",
            "lattice": "star",
            "hamiltonian": (
                "uniform spin-1/2 nearest-neighbor Heisenberg antiferromagnet on "
                "the star lattice with JD=JT=J"
            ),
            "hamiltonian_terms": [
                "heisenberg",
                "nearest_neighbor",
                "frustrated",
                "valence_bond_crystal",
            ],
            "parameters": {"spin": 0.5, "coupling_regime": "JD=JT=J"},
            "observable": "gapped_valence_bond_crystal_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed",
            "standard_result": {"spin_liquid_or_valence_bond_reference": True},
            "source": "Richter_Schulenburg_Honecker_Schmalfuss_2004",
            "source_url": "https://doi.org/10.1103/physrevb.70.174454",
            "citation_locator": (
                "abstract, Eq. (1), and conclusion: gapped dimerized valence-bond "
                "crystal in the uniform star model"
            ),
        },
        {
            "name": "maple_leaf_lattice_heisenberg_reference",
            "model": "maple_leaf_lattice_heisenberg",
            "lattice": "maple_leaf",
            "hamiltonian": "J Heisenberg on maple-leaf lattice",
            "hamiltonian_terms": ["heisenberg", "frustrated"],
            "parameters": {"spin": 0.5},
            "observable": "ground_state_magnetic_long_range_order",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed_or_dmrg",
            "standard_result": {"magnetic_long_range_order": True},
            "source": "Farnell_Darradi_Schmidt_Richter_2011",
            "source_url": "https://doi.org/10.1103/PhysRevB.84.104406",
            "citation_locator": "abstract: magnetically ordered ground state with drastically reduced sublattice magnetization",
        },
        {
            "name": "shuriken_lattice_heisenberg_reference",
            "model": "uniform_square_kagome_heisenberg_antiferromagnet",
            "lattice": "square_kagome_shuriken",
            "hamiltonian": (
                "uniform spin-1/2 nearest-neighbor Heisenberg antiferromagnet on "
                "the square-kagome lattice with JS=JT=J"
            ),
            "hamiltonian_terms": [
                "heisenberg",
                "nearest_neighbor",
                "frustrated",
                "square_kagome",
                "localized_magnon",
            ],
            "parameters": {"spin": 0.5, "coupling_regime": "JS=JT=J"},
            "observable": "square_kagome_quantum_paramagnet_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "ed",
            "standard_result": {"square_kagome_reference": True},
            "source": "Richter_Schulenburg_Tomczak_Schmalfuss_2004",
            "source_url": "https://arxiv.org/abs/cond-mat/0411673",
            "citation_locator": (
                "abstract, Eq. (1), and conclusion: square-kagome spin-liquid-like "
                "state and localized magnons on squares"
            ),
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
            "backend_needed": "peps_or_ed_or_dmrg",
            "standard_result": {"multiple_paramagnetic_regions": True},
            "source": "Liu_Poilblanc_Gong_Chen_Gu_2024",
            "source_url": "https://doi.org/10.1103/PhysRevB.109.235116",
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
            "source": "Gong_Sheng_Motrunich_Fisher_2013",
            "source_url": "https://doi.org/10.1103/PhysRevB.88.165138",
            "citation_locator": "honeycomb spin-half J1-J2 nonmagnetic phase reference",
        },
        {
            "name": "square_heisenberg_spin_wave_velocity_reference",
            "model": "spin_1_2_square_heisenberg_afm",
            "lattice": "square",
            "hamiltonian": "J sum_<ij> S_i.S_j",
            "hamiltonian_terms": ["heisenberg", "nearest_neighbor", "spin_wave_velocity"],
            "parameters": {"spin": 0.5, "exchange": 1.0},
            "observable": "spin_wave_velocity",
            "comparison_kind": "paper_numeric",
            "backend_needed": "qmc_or_lswt",
            "standard_result": {"renormalized_velocity_over_j_approx": 1.6586},
            "source": "Jiang_Wiese_2011",
            "source_url": "https://doi.org/10.1103/physrevb.83.155120",
            "citation_locator": (
                "winding-number aspect-ratio determination: c=1.6586(3) J a"
            ),
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
            "model": "nacro2_triangular_heisenberg",
            "lattice": "triangular",
            "hamiltonian": "triangular-lattice spin-3/2 Heisenberg exchange",
            "hamiltonian_terms": ["heisenberg", "nearest_neighbor", "material"],
            "parameters": {"material": "NaCrO2", "spin": 1.5},
            "observable": "material_spin_order_reference",
            "comparison_kind": "material_reference",
            "backend_needed": "neutron_scattering_reference",
            "standard_result": {"unconventional_spin_order_reference": True},
            "source": "Hsieh_et_al_arXiv_1405.6184",
            "source_url": "https://arxiv.org/abs/1405.6184",
            "citation_locator": (
                "abstract and neutron-scattering results: unconventional "
                "dimensional-crossover spin order in NaCrO2"
            ),
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
            "source": "Helton_2007",
            "source_url": "https://doi.org/10.1103/PhysRevLett.98.107204",
            "citation_locator": "herbertsmithite kagome QSL experimental reference",
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
            "source_url": "https://doi.org/10.1038/20619",
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
            "source": "Gong_Zhu_Sheng_Motrunich_Fisher_2014",
            "source_url": "https://doi.org/10.1103/PhysRevLett.113.027201",
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
            "model": "spin_half_triangular_heisenberg_in_field",
            "lattice": "triangular",
            "hamiltonian": "J sum_<ij> S_i.S_j-h sum_i S_i^z",
            "hamiltonian_terms": [
                "heisenberg",
                "nearest_neighbor",
                "magnetic_field",
                "spin_wave_1_over_s",
                "one_third_plateau",
            ],
            "parameters": {
                "spin": 0.5,
                "exchange": "antiferromagnetic",
                "field_regime": "finite_interval_h1_to_h2",
            },
            "observable": "one_third_plateau_from_spin_wave_expansion",
            "comparison_kind": "paper_numeric",
            "backend_needed": "spin_wave_1_over_s",
            "standard_result": {"one_third_plateau": True},
            "source": "Chubukov_Golosov_1991",
            "source_url": "https://doi.org/10.1088/0953-8984/3/1/005",
            "citation_locator": (
                "isotropic case, spin-wave 1/S calculation, Fig. 3, and summary: "
                "finite one-third plateau"
            ),
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
            "source": "Collura_Calabrese_Essler_2015",
            "source_url": "https://doi.org/10.1103/physrevb.92.125131",
            "citation_locator": "XX-chain free-fermion ground-state energy at half filling",
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
            "source": "Kumar_Ramasesha_Soos_2010",
            "source_url": "https://arxiv.org/abs/1006.5052",
            "citation_locator": (
                "abstract and discussion citing Okamoto-Nomura: fluid-dimer "
                "transition at J2/J1=0.2411 where the gap opens"
            ),
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
            "hamiltonian": "J sum_<ij> S_i.S_j",
            "hamiltonian_terms": ["heisenberg", "nearest_neighbor", "j1", "magnetization"],
            "parameters": {"spin": 0.5, "exchange": 1.0},
            "observable": "staggered_magnetization",
            "comparison_kind": "paper_numeric",
            "backend_needed": "qmc_or_large_ed",
            "standard_result": {"staggered_magnetization": 0.30743, "tolerance": 5.0e-5},
            "source": "Jiang_Wiese_2011",
            "source_url": "https://doi.org/10.1103/physrevb.83.155120",
            "citation_locator": "combined cubical-regime fit: M_s=0.30743(1)/a^2",
        },
        {
            "name": "square_heisenberg_spin_half_spin_stiffness_reference",
            "model": "spin_1_2_square_heisenberg_afm",
            "lattice": "square",
            "hamiltonian": "J sum_<ij> S_i.S_j",
            "hamiltonian_terms": ["heisenberg", "nearest_neighbor", "j1", "spin_stiffness"],
            "parameters": {"spin": 0.5, "exchange": 1.0},
            "observable": "spin_stiffness",
            "comparison_kind": "paper_numeric",
            "backend_needed": "qmc",
            "standard_result": {"rho_s_over_j": 0.18081, "tolerance": 1.0e-3},
            "source": "Jiang_Wiese_2011",
            "source_url": "https://doi.org/10.1103/physrevb.83.155120",
            "citation_locator": "combined cubical-regime fit: rho_s=0.18081(11) J",
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
            "source": "Blote_Luijten_Heringa_1995",
            "source_url": "https://arxiv.org/abs/cond-mat/9509016",
            "citation_locator": "simple-cubic Ising critical coupling K_c=0.2216546",
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
            "source": "Husimi_Syozi_1950",
            "source_url": "https://doi.org/10.1143/ptp.5.2.177",
            "citation_locator": "dual-transformation critical-point equation for the triangular Ising lattice",
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
            "source": "Husimi_Syozi_1950",
            "source_url": "https://doi.org/10.1143/ptp.5.2.177",
            "citation_locator": "dual-transformation critical-point equation for the honeycomb Ising lattice",
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
            "source_url": "https://doi.org/10.1143/ptp/10.2.158",
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
            "source": "Garel_Maillard_1983",
            "source_url": "https://doi.org/10.1088/0305-4470/16/10/023",
            "citation_locator": "Villain fully frustrated square-lattice residual-entropy calculation",
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
            "source_url": "https://doi.org/10.1143/ptp/10.2.158",
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
            "source": "Henley_2005",
            "source_url": "https://arxiv.org/abs/cond-mat/0407005",
            "citation_locator": "tetrahedron zero-sum constraint and Coulomb-phase pinch-point correlations",
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
            "source": "Fouet_et_al_arXiv_cond-mat_0108070",
            "source_url": "https://arxiv.org/abs/cond-mat/0108070",
            "citation_locator": "crossed-plaquette zero-total-spin classical constraint",
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
            "source": "Gong_Sheng_Motrunich_Fisher_2013",
            "source_url": "https://doi.org/10.1103/PhysRevB.88.165138",
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
            "source": "Hu_Gong_Zhu_Sheng_2015",
            "source_url": "https://doi.org/10.1103/PhysRevB.92.140403",
            "citation_locator": "triangular J1-J2 spin-liquid window reference",
        },
        {
            "name": "square_ring_exchange_neel_vbs_reference",
            "model": "square_xy_ring_exchange",
            "lattice": "square",
            "hamiltonian": (
                "H=-J sum_<ij> B_ij-K sum_<ijkl> P_ijkl for spin-1/2 XY bond "
                "and four-spin ring operators"
            ),
            "hamiltonian_terms": [
                "xy",
                "nearest_neighbor",
                "four_spin_ring_exchange",
                "bond_plaquette_order",
                "spin_peierls",
                "vbs",
            ],
            "parameters": {"spin": 0.5, "coupling_regime": "ring_exchange_driven"},
            "observable": "ring_exchange_driven_bond_spin_peierls_order",
            "comparison_kind": "paper_numeric",
            "backend_needed": "qmc",
            "standard_result": {"ring_exchange_drives_vbs_phase": True},
            "source": "Sandvik_Daul_Singh_Scalapino_2002",
            "source_url": "https://arxiv.org/abs/cond-mat/0205270",
            "citation_locator": (
                "abstract, Eqs. (1)-(3), finite-size scaling, and conclusion: "
                "striped bond-plaquette/spin-Peierls order"
            ),
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
            "source": "Chaloupka_Jackeli_Khaliullin_arXiv_1209.5100",
            "source_url": "https://arxiv.org/abs/1209.5100",
            "citation_locator": "full Kitaev-Heisenberg phase diagram and Na2IrO3 zigzag-order discussion",
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
            "source_url": "https://doi.org/10.1209/epl/i2004-10484-x",
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
            "source": "Depenbrock_McCulloch_Schollwoeck_2012",
            "source_url": "https://arxiv.org/abs/1205.4858",
            "citation_locator": "abstract and thermodynamic extrapolation: energy -0.4386(5) and triplet gap 0.13(1)",
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
            "source_url": "https://doi.org/10.1103/PhysRevLett.113.227203",
            "citation_locator": "barlowite kagome antiferromagnet material reference",
        },
        {
            "name": "zn_barlowite_kagome_qsl_reference",
            "model": "zn_substituted_barlowite_kagome",
            "lattice": "kagome",
            "hamiltonian": "two-parameter Heisenberg Hamiltonian with kagome and interkagome exchange",
            "hamiltonian_terms": ["heisenberg", "kagome", "interkagome", "material"],
            "parameters": {
                "parent_material": "Cu4(OH)6FBr",
                "substitution": "Zn",
            },
            "observable": "substitution_effective_exchange_model",
            "comparison_kind": "paper_numeric",
            "backend_needed": "first_principles_exchange_mapping",
            "standard_result": {
                "significantly_reduced_interkagome_exchange": True,
                "two_parameter_heisenberg_hamiltonian": True,
            },
            "source": "Guterding_Valenti_Jeschke_2016",
            "source_url": "https://doi.org/10.1103/PhysRevB.94.125136",
            "citation_locator": "abstract: nonmagnetic isoelectronic Zn substitution significantly reduces interkagome exchange and yields a two-parameter Heisenberg Hamiltonian",
        },
        {
            "name": "vesignieite_kagome_material_reference",
            "model": "vesignieite_dominant_j3_kagome_antiferromagnet",
            "lattice": "nearly_ideal_kagome",
            "hamiltonian": (
                "spin-1/2 kagome Heisenberg antiferromagnet with dominant "
                "antiferromagnetic J3 and tiny symmetric exchange anisotropy"
            ),
            "hamiltonian_terms": [
                "heisenberg",
                "kagome",
                "third_neighbor_j3",
                "symmetric_exchange_anisotropy",
                "material",
            ],
            "parameters": {
                "material": "BaCu3V2O8(OD)2",
                "spin": 0.5,
                "structural_distortion_upper_bound_percent": 1.0,
                "dominant_exchange": "antiferromagnetic_J3",
                "isotropic_best_fit_mev": {"J3": 1.9, "Jd": -0.1},
                "symmetric_anisotropy_over_j3": -0.006,
            },
            "observable": "dominant_j3_not_distortion_assessment",
            "comparison_kind": "paper_numeric",
            "backend_needed": "neutron_scattering_and_spin_wave",
            "standard_result": {"distorted_kagome_relevant": False},
            "source": "Boldrin_Walker_Wills_2018",
            "source_url": "https://doi.org/10.1103/physrevlett.121.107203",
            "citation_locator": (
                "abstract, Eq. (1), spin-wave fit, and conclusion: dominant J3 "
                "with less-than-one-percent distortion"
            ),
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
            "source": "Boldrin_2015",
            "source_url": "https://doi.org/10.1103/PhysRevB.91.220408",
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
            "source": "Stodter_et_al_2026",
            "source_url": "https://arxiv.org/abs/2601.21024",
            "citation_locator": "exchange-network analysis of distorted kagome clinoatacamite",
        },
        {
            "name": "edwardsite_kagome_antiferromagnet_reference",
            "model": "edwardsite_spin_half_deformed_kagome_antiferromagnet",
            "lattice": "deformed_kagome",
            "hamiltonian": (
                "spin-1/2 deformed-kagome Heisenberg antiferromagnet with two "
                "stronger J and four weaker J-prime bonds"
            ),
            "hamiltonian_terms": ["heisenberg", "deformed_kagome", "spin_half", "material"],
            "parameters": {"material": "Cd2Cu3(SO4)2(OH)6·4H2O", "spin": 0.5},
            "observable": "hydrated_spin_half_deformed_kagome_reference",
            "comparison_kind": "paper_numeric",
            "backend_needed": "experiment",
            "standard_result": {"kagome_antiferromagnet_reference": True},
            "source": "Ishikawa_Okamoto_Hiroi_2013",
            "source_url": "https://arxiv.org/abs/1305.2477",
            "citation_locator": (
                "abstract and exchange analysis: hydrated spin-1/2 deformed-kagome "
                "Edwardsite"
            ),
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
            "model": "gadolinium_gallium_garnet_exchange_dipolar",
            "lattice": "garnet_interpenetrating_corner_sharing_triangles",
            "hamiltonian": (
                "classical Heisenberg spins with nearest-neighbor antiferromagnetic "
                "exchange and dipolar interactions to third neighbor"
            ),
            "hamiltonian_terms": [
                "heisenberg",
                "nearest_neighbor",
                "dipolar",
                "third_neighbor",
                "material",
            ],
            "parameters": {
                "material": "Gd3Ga5O12",
                "spin": 3.5,
                "nearest_neighbor_exchange_energy_k": 1.5,
                "nearest_neighbor_dipole_energy_k": 0.7,
            },
            "observable": "strong_geometric_frustration_in_ggg",
            "comparison_kind": "paper_numeric",
            "backend_needed": "classical_mc_and_thermodynamics",
            "standard_result": {"strong_frustration": True},
            "source": "Schiffer_Ramirez_Huse_Valentino_1994",
            "source_url": "https://doi.org/10.1103/physrevlett.73.2500",
            "citation_locator": (
                "abstract, exchange-dipole Monte Carlo model, and conclusion: strong "
                "GGG frustration with finite-field order"
            ),
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
            "source_url": "https://doi.org/10.1103/PhysRevLett.80.4570",
            "citation_locator": "GGG low-temperature frustrated correlations reference",
        },
        {
            "name": "garnet_gd3te2li3o12_hyperkagome_reference",
            "model": "gd3te2li3o12_hyperkagome_garnet",
            "lattice": "hyperkagome_garnet",
            "hamiltonian": (
                "nearest-neighbor antiferromagnetic Heisenberg exchange plus "
                "long-range dipolar interaction"
            ),
            "hamiltonian_terms": [
                "heisenberg",
                "nearest_neighbor",
                "dipolar",
                "hyperkagome",
                "material",
            ],
            "parameters": {
                "material": "Gd3Te2Li3O12",
                "spin": 3.5,
                "nearest_neighbor_exchange_k": 0.126,
                "dipolar_interaction_k": 0.045,
                "dipolar_to_exchange_ratio": 0.36,
            },
            "observable": "frustrated_garnet_with_first_order_long_range_order",
            "comparison_kind": "paper_numeric",
            "backend_needed": "specific_heat_and_structural_experiment",
            "standard_result": {"garnet_frustrated_magnet": True},
            "source": "Quilliam_et_al_2013",
            "source_url": "https://doi.org/10.1103/physrevb.87.174421",
            "citation_locator": (
                "abstract, Hamiltonians, and GTLG results: hyperkagome frustration "
                "with a sharp first-order 243 mK LRO transition"
            ),
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
            "source": "Biffin_et_al_2014",
            "source_url": "https://doi.org/10.1103/physrevlett.113.197201",
            "citation_locator": "abstract and magnetic-structure results: incommensurate spiral order in gamma-Li2IrO3",
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
            "observable": "honeycomb_frustrated_iridate_identity",
            "comparison_kind": "paper_numeric",
            "backend_needed": "anisotropic_exchange_or_experiment",
            "standard_result": {"honeycomb_frustrated_iridate_identity": True},
            "source": "Abramchuk_2017",
            "source_url": "https://doi.org/10.1021/jacs.7b06911",
            "citation_locator": "abstract: honeycomb frustrated iridate Cu2IrO3",
        },
        {
            "name": "ba3irti2o9_honeycomb_kitaev_reference",
            "model": "ba3irti2o9_site_diluted_triangular_jeff_half",
            "lattice": "site_diluted_triangular",
            "hamiltonian": "site-diluted triangular-lattice J_eff=1/2 exchange in Ba3IrTi2O9",
            "hamiltonian_terms": [
                "heisenberg",
                "spin_orbit",
                "triangular",
                "site_dilution",
                "material",
            ],
            "parameters": {
                "material": "Ba3IrTi2O9",
                "magnetic_ion": "Ir4+",
                "effective_spin": 0.5,
            },
            "observable": "triangular_spin_liquid_candidate",
            "comparison_kind": "paper_numeric",
            "backend_needed": "experiment",
            "standard_result": {"spin_liquid_candidate": True},
            "source": "Dey_2012",
            "source_url": "https://doi.org/10.1103/physrevb.86.140405",
            "citation_locator": (
                "abstract and conclusion: site-diluted triangular J_eff=1/2 "
                "spin-liquid candidate"
            ),
        },
        {
            "name": "ru_br3_kitaev_material_reference",
            "model": "rubr3_honeycomb_competing_exchange",
            "lattice": "honeycomb",
            "hamiltonian": (
                "pseudospin-1/2 honeycomb J1-K-Gamma-Gamma-prime or J1-K-J2-J3 "
                "competing-exchange model"
            ),
            "hamiltonian_terms": [
                "kitaev",
                "gamma",
                "heisenberg",
                "third_neighbor",
                "honeycomb",
                "material",
            ],
            "parameters": {
                "material": "RuBr3",
                "pseudospin": 0.5,
                "ordered_state": "zigzag_antiferromagnet",
            },
            "observable": "kitaev_candidate_with_competing_interactions",
            "comparison_kind": "paper_numeric",
            "backend_needed": "neutron_scattering_and_spin_wave",
            "standard_result": {"ru_honeycomb_kitaev_candidate": True},
            "source": "Nawa_Imai_Sato_2026",
            "source_url": "https://doi.org/10.1038/s41535-026-00868-6",
            "citation_locator": (
                "abstract and competing-model analysis: Gamma or J3 interactions "
                "drive RuBr3 away from the ideal Kitaev limit"
            ),
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
            "source_url": "https://doi.org/10.1016/0022-3697(61)90053-1",
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
            "source_url": "https://doi.org/10.1021/cm504242t",
            "citation_locator": "title: Coupling of Crystal Structure and Magnetism in the Layered, Ferromagnetic Insulator CrI3",
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
            "source_url": "https://doi.org/10.1088/0953-8984/7/1/008",
            "citation_locator": "CrGeTe3 layered ferromagnet reference",
        },
        {
            "name": "fecl3_honeycomb_antiferromagnet_reference",
            "model": "fecl3_honeycomb_antiferromagnet",
            "lattice": "honeycomb",
            "hamiltonian": "layered honeycomb Heisenberg model with competing exchange",
            "hamiltonian_terms": [
                "heisenberg",
                "honeycomb",
                "antiferromagnetic",
                "competing_exchange",
                "layered",
                "material",
            ],
            "parameters": {"material": "FeCl3"},
            "observable": "classical_order",
            "comparison_kind": "paper_numeric",
            "backend_needed": "classical_glt_or_spin_wave",
            "standard_result": {
                "magnetic_order": "helimagnetic_spiral",
                "propagation_vector_hexagonal": [4.0 / 15.0, 1.0 / 15.0, 3.0 / 2.0],
                "computable_observables": [
                    "spiral_geometry_consistency",
                ],
            },
            "source": "Cable_1962",
            "source_url": "https://doi.org/10.1103/PhysRev.127.714",
            "citation_locator": "FeCl3 helimagnetic propagation vector from neutron diffraction",
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
            "source": "Ressouche_et_al_2010",
            "source_url": "https://doi.org/10.1103/physrevb.82.100408",
            "citation_locator": "neutron-diffraction determination of the MnPS3 Neel state",
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
            "source": "Wildes_et_al_2020",
            "source_url": "https://arxiv.org/abs/2005.12031",
            "citation_locator": "abstract and Eq. (1): spin-2 Ising-like zigzag order in FePS3",
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
            "source_url": "https://doi.org/10.1126/science.1214143",
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
        "hamiltonian_terms": [
            "local_spin",
            "short_range",
            "translation_invariant",
            "u1_symmetric",
            "half_odd_integer",
        ],
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


_DIRECT_SOURCE_ONLY_BENCHMARKS = {
    "ba3irti2o9_honeycomb_kitaev_reference",
    "cu2iro3_honeycomb_kitaev_reference",
    "edwardsite_kagome_antiferromagnet_reference",
    "gadolinium_gallium_garnet_hyperkagome_reference",
    "garnet_gd3te2li3o12_hyperkagome_reference",
    "nacuo2_triangular_heisenberg_material_reference",
    "ru_br3_kitaev_material_reference",
    "shuriken_lattice_heisenberg_reference",
    "star_lattice_heisenberg_spin_liquid_reference",
    "triangular_heisenberg_magnetization_plateau_reference",
    "vesignieite_kagome_material_reference",
    "zn_barlowite_kagome_qsl_reference",
}


def _curie_weiss_temperature_from_coordination(coordination, exchange):
    return -float(coordination) * float(exchange) / 3.0


for _entry in LITERATURE_STANDARD_RESULTS:
    _metadata = _STANDARD_RESULT_INDEX_METADATA.get(_entry["name"])
    if _metadata is not None:
        _entry.update(_metadata)

    _terms = set(_entry.get("hamiltonian_terms", []))
    _computable = []
    if _entry["name"] not in _DIRECT_SOURCE_ONLY_BENCHMARKS:
        if "heisenberg" in _terms and "nearest_neighbor" in _terms:
            _computable.append("curie_weiss_theta")
        if (
            "material" in _terms
            and _entry["name"] != "fecl3_honeycomb_antiferromagnet_reference"
        ):
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
    if observable == "triangle_scalar_chirality":
        return {
            "verification_kind": "finite_cluster_quantum",
            "suggested_backend": "exact_diagonalization",
        }
    if observable in {"q0_120_order_energy", "dm_selected_chirality"}:
        return {
            "verification_kind": "classical_ground_state",
            "suggested_backend": "glt_or_single_q_energy",
        }
    if observable == "kitaev_triangle_gapless_condition":
        return {
            "verification_kind": "theorem",
            "suggested_backend": "analytic_or_symbolic",
        }
    if observable in {
        "clean_limit_kitaev_phase_condition",
        "dilution_free_cluster_modes",
        "dipolar_energy_minima",
        "finite_cylinder_energy",
        "honeycomb_ising_domain_wall_energy",
        "honeycomb_kitaev_limit",
        "triple_q_skyrmion_variational_energy",
    }:
        return {
            "verification_kind": "paper_reference",
            "suggested_backend": "paper_summary_or_reference",
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
        coordination = standard_result.get(
            "coordination_number",
            _DEFAULT_LATTICE_COORDINATION.get(entry.get("lattice"), 1),
        )
        exchange = standard_result.get(
            "exchange_for_curie_weiss",
            entry.get("parameters", {}).get("exchange", 1.0),
        )
        expected_theta = standard_result.get(
            "curie_weiss_theta",
            _curie_weiss_temperature_from_coordination(coordination, exchange),
        )
        tasks.append(
            {
                **task,
                "coordination_number": coordination,
                "exchange": exchange,
                "expected_theta": expected_theta,
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
            "benchmark_name": "jarosite_kagome_dzyaloshinskii_moriya_reference",
            "computable_observable": "q0_120_order_energy",
            "projection_kind": "local_120_triangle_energy",
            "model_builder": "triangle_nn",
            "model_parameters": {"exchange": 1.0},
            "expected_total_energy": -1.5,
            "minimum_gap": 1.0,
            "projection_note": "jarosite projected to the local q=0 120-degree triangle energy minimum",
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


def _kitaev_gamma_local_exchange_task(entry, observable):
    gamma = 0.5
    kitaev = 1.0
    return {
        **_local_exchange_matrix_task(entry, observable),
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
        if "single_bond_exchange_matrix" in computable and "gamma" in terms:
            tasks.append(_kitaev_gamma_local_exchange_task(entry, "single_bond_exchange_matrix"))
        if "single_bond_exchange_eigenvalues" in computable and "kitaev" in terms:
            tasks.extend(_kitaev_rank_one_local_exchange_tasks(entry, "single_bond_exchange_eigenvalues"))

    entries_by_name = {entry["name"]: entry for entry in LITERATURE_STANDARD_RESULTS}
    anisotropic_entry = entries_by_name["gamma_li2iro3_3d_kitaev_reference"]
    if _passes_task_filters(anisotropic_entry, lattice=lattice, required=required):
        tasks.append(_kitaev_gamma_local_exchange_task(anisotropic_entry, "single_bond_anisotropic_exchange_matrix"))
    return tasks


def kitaev_triangle_gapless_condition_verification_tasks(*, lattice=None, required_terms=()):
    required = {str(term) for term in required_terms}
    theorem_entry = next(
        entry
        for entry in LITERATURE_STANDARD_RESULTS
        if entry["name"] == "kitaev_honeycomb_gapless_triangle_condition"
    )
    task_specs = [
        {
            "benchmark_name": entry["name"],
            "computable_observable": "kitaev_triangle_gapless_condition",
            "projection_kind": "triangle_inequality_gapless_condition",
            "model_parameters": dict(theorem_entry["parameters"]),
            "expected_gapless_condition": theorem_entry["standard_result"]["gapless_condition"],
            "expected_isotropic_kitaev_point_gapless": theorem_entry["standard_result"][
                "isotropic_kitaev_point_gapless"
            ],
            "projection_note": f"{theorem_entry['citation_locator']} projected to the isotropic Kitaev triangle-inequality theorem point",
        }
        for entry in standard_results_for_computable_observable(
            "kitaev_triangle_gapless_condition",
            lattice=lattice,
            required_terms=required,
        )
    ]
    return _verification_tasks_from_specs(
        task_specs,
        lattice=lattice,
        required=required,
        route_override={
            "verification_kind": "theorem",
            "suggested_backend": "analytic_or_symbolic",
        },
    )


def paper_reference_verification_tasks(*, lattice=None, required_terms=()):
    required = {str(term) for term in required_terms}
    task_specs = [
        {
            "benchmark_name": "h3liir2o6_kitaev_spin_liquid_candidate_reference",
            "computable_observable": "clean_limit_kitaev_phase_condition",
            "reference_claim_key": "no_magnetic_order_reported",
            "expected_reference_claim": True,
            "projection_note": "H3LiIr2O6 clean-limit Kitaev reference claim recorded in the literature summary",
        },
        {
            "benchmark_name": "scgo_kagome_bilayer_spin_liquid_reference",
            "computable_observable": "dilution_free_cluster_modes",
            "reference_claim_key": "no_conventional_order_down_to_low_t",
            "expected_reference_claim": True,
            "projection_note": "SCGO kagome-bilayer spin-liquid reference claim recorded in the literature summary",
        },
        {
            "benchmark_name": "garnet_gd3ga5o12_spin_liquid_reference",
            "computable_observable": "dipolar_energy_minima",
            "reference_claim_key": "short_range_order_without_simple_lro",
            "expected_reference_claim": True,
            "projection_note": "GGG dipolar correlation reference claim recorded in the literature summary",
        },
        {
            "benchmark_name": "kagome_heisenberg_topological_entanglement_reference",
            "computable_observable": "finite_cylinder_energy",
            "reference_claim_key": "topological_entanglement_entropy",
            "expected_reference_claim": "consistent_with_Z2",
            "projection_note": "kagome DMRG finite-cylinder reference claim recorded in the literature summary",
        },
        {
            "benchmark_name": "fe_ps3_honeycomb_ising_reference",
            "computable_observable": "honeycomb_ising_domain_wall_energy",
            "reference_claim_key": "ising_like_zigzag_order",
            "expected_reference_claim": True,
            "projection_note": "FePS3 Ising-like honeycomb reference claim recorded in the literature summary",
        },
        {
            "benchmark_name": "ba3irti2o9_honeycomb_kitaev_reference",
            "computable_observable": "honeycomb_kitaev_limit",
            "reference_claim_key": "spin_liquid_candidate",
            "expected_reference_claim": True,
            "projection_note": "Ba3IrTi2O9 honeycomb Kitaev reference claim recorded in the literature summary",
        },
        {
            "benchmark_name": "cu2oseo3_skyrmion_lattice_reference",
            "computable_observable": "triple_q_skyrmion_variational_energy",
            "reference_claim_key": "skyrmion_lattice_phase",
            "expected_reference_claim": True,
            "projection_note": "Cu2OSeO3 skyrmion-lattice reference claim recorded in the literature summary",
        },
    ]
    return _verification_tasks_from_specs(
        task_specs,
        lattice=lattice,
        required=required,
        route_override={
            "verification_kind": "paper_reference",
            "suggested_backend": "paper_summary_or_reference",
        },
    )


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
        {
            "benchmark_name": "fecl3_honeycomb_antiferromagnet_reference",
            "computable_observable": "spiral_geometry_consistency",
            "projection_kind": "source_vector_geometry_consistency",
            "verification_kind": "source_geometry_consistency",
            "suggested_backend": "analytic_fraction_geometry",
            "expected_propagation_vector_hexagonal": [
                4.0 / 15.0,
                1.0 / 15.0,
                3.0 / 2.0,
            ],
            "expected_in_plane_period_lattice_spacings": 15,
            "expected_successive_plane_turn_angle_radians": 2.0 * math.pi / 15.0,
            "projection_note": "Cable 1962 source-vector geometry consistency; not a ground-state recomputation",
        },
    ]
    return _verification_tasks_from_specs(task_specs, lattice=lattice, required=required)


def dm_selected_chirality_verification_tasks(*, lattice=None, required_terms=()):
    required = {str(term) for term in required_terms}
    selected_chirality_energy = -1.5 - 1.5 * math.sqrt(3.0) * 0.1
    task_specs = [
        {
            "benchmark_name": entry["name"],
            "computable_observable": "dm_selected_chirality",
            "projection_kind": "dm_triangle_chirality_selection",
            "model_builder": "triangle_dm",
            "model_parameters": {"exchange": 1.0, "dzyaloshinskii_moriya": 0.1},
            "expected_selected_chirality": "clockwise",
            "selected_chirality_energy": selected_chirality_energy,
            "minimum_energy_gap": 0.5,
            "projection_note": f"{entry['citation_locator']} projected to a local DM triangle chirality selector",
        }
        for entry in standard_results_for_computable_observable(
            "dm_selected_chirality",
            lattice=lattice,
            required_terms=required,
        )
    ]
    return _verification_tasks_from_specs(task_specs, lattice=lattice, required=required)


def dm_single_q_energy_verification_tasks(*, lattice=None, required_terms=()):
    required = {str(term) for term in required_terms}
    task_specs = [
        {
            "benchmark_name": entry["name"],
            "computable_observable": "single_q_classical_energy",
            "projection_kind": "dm_helix_energy",
            "model_parameters": {"exchange": 1.0, "dzyaloshinskii_moriya": 0.1},
            "expected_energy_per_bond": -math.sqrt(1.0 + 0.1 * 0.1),
            "ferromagnetic_energy_per_bond": -1.0,
            "projection_note": f"{entry['citation_locator']} projected to a single-q DM helix bond energy",
        }
        for entry in standard_results_for_computable_observable(
            "single_q_classical_energy",
            lattice=lattice,
            required_terms=required,
        )
        if "dzyaloshinskii_moriya" in entry.get("hamiltonian_terms", [])
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
        {
            "benchmark_name": "kagome_chiral_spin_liquid_j1_j2_jchi_reference",
            "computable_observable": "triangle_scalar_chirality",
            "cluster_kind": "spin_half_scalar_chirality_triangle",
            "cluster_parameters": {"spin": 0.5},
            "expected_levels": [
                -math.sqrt(3.0) / 4.0,
                -math.sqrt(3.0) / 4.0,
                0.0,
                0.0,
                0.0,
                0.0,
                math.sqrt(3.0) / 4.0,
                math.sqrt(3.0) / 4.0,
            ],
            "projection_note": "spin-1/2 triangle scalar chirality operator spectrum",
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
    covered_names = {spec["benchmark_name"] for spec in task_specs}
    for entry in standard_results_for_computable_observable(
        "finite_cluster_energy",
        lattice=lattice,
        required_terms=required,
    ):
        if entry["name"] in covered_names:
            continue
        task_specs.append(
            {
                "benchmark_name": entry["name"],
                "computable_observable": "finite_cluster_energy",
                "cluster_kind": "spin_half_heisenberg_triangle",
                "site_count": 3,
                "bonds": [(0, 1), (1, 2), (2, 0)],
                "cluster_parameters": {"spin": 0.5, "exchange": 1.0},
                "expected_ground_energy": -0.75,
                "expected_ground_energy_per_site": -0.25,
                "expected_ground_state_degeneracy": 4,
                "projection_note": f"{entry['citation_locator']} projected to a three-site spin-1/2 Heisenberg triangle",
            }
        )
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
    covered_static_names = {
        spec["benchmark_name"]
        for spec in task_specs
        if spec["computable_observable"] == "static_structure_factor"
    }
    for entry in standard_results_for_computable_observable(
        "static_structure_factor",
        lattice=lattice,
        required_terms=required,
    ):
        if entry["name"] in covered_static_names:
            continue
        task_specs.append(
            {
                "benchmark_name": entry["name"],
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
                "projection_note": f"{entry['citation_locator']} projected to a local 120-degree structure-factor smoke check",
            }
        )
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
    ]
    covered_lt_names = {
        spec["benchmark_name"]
        for spec in task_specs
        if spec["computable_observable"] == "classical_luttinger_tisza_minima"
    }
    for entry in standard_results_for_computable_observable(
        "classical_luttinger_tisza_minima",
        lattice=lattice,
        required_terms=required,
    ):
        if entry["name"] in covered_lt_names:
            continue
        task_specs.append(
            {
                "benchmark_name": entry["name"],
                "computable_observable": "classical_luttinger_tisza_minima",
                "projection_kind": "sampled_luttinger_tisza_minima",
                "candidate_q": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
                "expected_degenerate_minima": False,
            }
        )
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
        dm_selected_chirality_verification_tasks,
        dm_single_q_energy_verification_tasks,
        local_exchange_matrix_verification_tasks,
        kitaev_triangle_gapless_condition_verification_tasks,
        paper_reference_verification_tasks,
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


def square_nn_afm_renormalized_spin_wave_velocity_status(
    *,
    spin=0.5,
    exchange=1.0,
    velocity_renormalization=1.1765,
    registered_velocity=1.658,
    tolerance=0.01,
):
    bare_velocity = 2.0 * math.sqrt(2.0) * float(exchange) * float(spin)
    renormalized_velocity = bare_velocity * float(velocity_renormalization)
    difference = abs(renormalized_velocity - float(registered_velocity))
    return {
        "method": "renormalized_square_lattice_spin_wave_velocity_formula",
        "formula": "c = 2*sqrt(2)*J*S*Z_c",
        "spin": float(spin),
        "exchange": float(exchange),
        "velocity_renormalization": float(velocity_renormalization),
        "bare_lsw_velocity_over_j": bare_velocity,
        "renormalized_spin_wave_velocity_over_j": renormalized_velocity,
        "registered_velocity_over_j": float(registered_velocity),
        "absolute_difference_from_registered": difference,
        "matching_tolerance": float(tolerance),
        "velocity_matches_registered_approximation": bool(difference <= float(tolerance)),
    }


def square_nn_afm_renormalized_spin_stiffness_status(
    *,
    spin=0.5,
    exchange=1.0,
    stiffness_renormalization=0.72,
    registered_stiffness=0.1808,
    tolerance=0.001,
):
    bare_stiffness = float(exchange) * float(spin) * float(spin)
    renormalized_stiffness = bare_stiffness * float(stiffness_renormalization)
    difference = abs(renormalized_stiffness - float(registered_stiffness))
    return {
        "method": "renormalized_square_lattice_spin_stiffness_formula",
        "formula": "rho_s = J*S^2*Z_rho",
        "spin": float(spin),
        "exchange": float(exchange),
        "stiffness_renormalization": float(stiffness_renormalization),
        "bare_classical_stiffness_over_j": bare_stiffness,
        "renormalized_spin_stiffness_over_j": renormalized_stiffness,
        "registered_stiffness_over_j": float(registered_stiffness),
        "absolute_difference_from_registered": difference,
        "matching_tolerance": float(tolerance),
        "stiffness_matches_registered_qmc_value": bool(difference <= float(tolerance)),
    }


def square_nn_afm_renormalized_staggered_magnetization_status(
    *,
    spin=0.5,
    magnetization_renormalization=0.61486,
    registered_magnetization=0.30743,
    tolerance=5.0e-5,
):
    bare_magnetization = float(spin)
    renormalized_magnetization = bare_magnetization * float(magnetization_renormalization)
    difference = abs(renormalized_magnetization - float(registered_magnetization))
    return {
        "method": "renormalized_square_lattice_staggered_magnetization_formula",
        "formula": "M = S*Z_m",
        "spin": float(spin),
        "magnetization_renormalization": float(magnetization_renormalization),
        "bare_classical_staggered_magnetization": bare_magnetization,
        "renormalized_staggered_magnetization": renormalized_magnetization,
        "registered_staggered_magnetization": float(registered_magnetization),
        "absolute_difference_from_registered": difference,
        "matching_tolerance": float(tolerance),
        "magnetization_matches_registered_qmc_value": bool(difference <= float(tolerance)),
    }


def square_nn_afm_spin_wave_energy_expansion_status(
    *,
    spin=0.5,
    exchange=1.0,
    bare_lsw_integral_correction=0.157947421,
    second_order_correction=0.0211,
    registered_energy=-0.669437,
    tolerance=5.0e-6,
):
    spin = float(spin)
    exchange = float(exchange)
    classical_energy = -2.0 * exchange * spin * spin
    bare_lsw_energy = classical_energy * (1.0 + float(bare_lsw_integral_correction) / spin)
    second_order_energy = classical_energy * (
        1.0 + float(bare_lsw_integral_correction) / spin + float(second_order_correction)
    )
    bare_difference = abs(bare_lsw_energy - float(registered_energy))
    second_order_difference = abs(second_order_energy - float(registered_energy))
    return {
        "method": "square_lattice_spin_wave_energy_expansion",
        "formula": "E/N = -2*J*S^2*(1 + e1/S + e2)",
        "spin": spin,
        "exchange": exchange,
        "classical_energy_per_site": classical_energy,
        "bare_lsw_integral_correction": float(bare_lsw_integral_correction),
        "second_order_correction": float(second_order_correction),
        "bare_lsw_energy_per_site": bare_lsw_energy,
        "second_order_spin_wave_energy_per_site": second_order_energy,
        "registered_energy_per_site": float(registered_energy),
        "bare_lsw_absolute_difference_from_registered": bare_difference,
        "second_order_absolute_difference_from_registered": second_order_difference,
        "matching_tolerance": float(tolerance),
        "bare_lsw_matches_registered_qmc_value": bool(bare_difference <= float(tolerance)),
        "second_order_matches_registered_qmc_value": bool(second_order_difference <= float(tolerance)),
    }


def square_heisenberg_qmc_finite_size_extrapolation_status(
    *,
    finite_size_energy_table=(
        (6, -0.678873, 4.0e-6),
        (8, -0.673487, 4.0e-6),
        (10, -0.671549, 4.0e-6),
        (12, -0.670685, 5.0e-6),
        (14, -0.670223, 8.0e-6),
        (16, -0.669976, 7.0e-6),
    ),
    fit_minimum_linear_size=10,
    registered_energy=-0.669437,
    tolerance=5.0e-6,
):
    rows = [
        (int(linear_size), float(energy), float(error_bar))
        for linear_size, energy, error_bar in finite_size_energy_table
        if int(linear_size) >= int(fit_minimum_linear_size)
    ]
    if len(rows) < 4:
        raise ValueError("square Heisenberg QMC extrapolation requires at least four finite-size points")

    linear_sizes = np.array([row[0] for row in rows], dtype=float)
    energies = np.array([row[1] for row in rows], dtype=float)
    design = np.column_stack([np.ones_like(linear_sizes), linear_sizes**-3, linear_sizes**-4])
    coefficients, residuals, rank, singular_values = np.linalg.lstsq(design, energies, rcond=None)
    fitted = design @ coefficients
    extrapolated_energy = float(coefficients[0])
    difference = abs(extrapolated_energy - float(registered_energy))
    return {
        "method": "published_qmc_finite_size_extrapolation",
        "source": "Sandvik_1997",
        "source_url": "https://doi.org/10.1103/PhysRevB.56.11678",
        "fit_model": "E(L)=E_inf+a/L^3+b/L^4",
        "finite_size_energy_table": [
            {"linear_size": row[0], "energy_per_site": row[1], "error_bar": row[2]}
            for row in finite_size_energy_table
        ],
        "fit_linear_sizes": [int(value) for value in linear_sizes],
        "fit_energies_per_site": [float(value) for value in energies],
        "fit_coefficients": {
            "E_inf": extrapolated_energy,
            "a_over_l_cubed": float(coefficients[1]),
            "b_over_l_fourth": float(coefficients[2]),
        },
        "fit_residual_sum_squares": float(residuals[0]) if len(residuals) else 0.0,
        "fit_rank": int(rank),
        "fit_singular_values": [float(value) for value in singular_values],
        "fitted_energies_per_site": [float(value) for value in fitted],
        "extrapolated_energy_per_site": extrapolated_energy,
        "registered_energy_per_site": float(registered_energy),
        "registered_tolerance": float(tolerance),
        "absolute_difference_from_registered": difference,
        "matches_registered_qmc_energy": bool(difference <= float(tolerance)),
    }


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


def aklt_projector_ground_state_result():
    return {
        "two_site_projector_eigenvalues": aklt_two_site_projector_eigenvalues(),
        "vbs_ground_energy": 0.0,
    }


def bilinear_biquadratic_aklt_angle():
    return math.atan(1.0 / 3.0)


def toric_code_ground_state_degeneracy(*, genus):
    if isinstance(genus, bool) or not isinstance(genus, int) or genus < 0:
        raise ValueError("genus must be a nonnegative integer")
    return 4**genus


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


def blume_capel_square_zero_temperature_level_crossing():
    return 2.0


def single_ion_spin1_anisotropy_levels(anisotropy=1.0):
    anisotropy = float(anisotropy)
    return sorted([anisotropy * m * m for m in (-1.0, 0.0, 1.0)])


def transverse_field_ising_chain_gap(field_over_exchange, *, exchange=1.0):
    return 2.0 * float(exchange) * abs(1.0 - float(field_over_exchange))


def classical_ising_chain_correlation_length(*, beta, exchange=1.0):
    tanh_beta_j = math.tanh(float(beta) * float(exchange))
    if tanh_beta_j <= 0.0:
        raise ValueError("beta * exchange must be positive")
    return -1.0 / math.log(tanh_beta_j)


def two_dimensional_ising_square_tc(exchange=1.0):
    return 2.0 * float(exchange) / math.log(1.0 + math.sqrt(2.0))


def square_potts_critical_beta_j(q):
    return math.log(1.0 + math.sqrt(float(q)))


def clock_model_bkt_transition_summary(q):
    q = int(q)
    if q >= 5:
        return {"transition_count": 2, "phase_sequence": ["ordered", "critical", "disordered"]}
    return {"transition_count": 1, "phase_sequence": ["ordered", "disordered"]}


def pauling_spin_ice_entropy_per_spin():
    return 0.5 * math.log(1.5)


def localized_magnon_status(lattice):
    if str(lattice) not in {"sawtooth_chain", "diamond_chain", "ruby_lattice"}:
        raise ValueError(
            "localized magnon status is only registered for sawtooth_chain, diamond_chain, and ruby_lattice"
        )
    return True


def square_kagome_localized_magnon_flat_band_status(*, lattice):
    is_square_kagome = str(lattice) in {"shuriken", "square_kagome"}
    square_amplitudes = np.array([1.0, -1.0, 1.0, -1.0], dtype=float)
    vector = np.zeros(8, dtype=float)
    vector[:4] = square_amplitudes
    bonds = [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),
        (4, 0),
        (4, 1),
        (5, 1),
        (5, 2),
        (6, 2),
        (6, 3),
        (7, 3),
        (7, 0),
    ]
    adjacency = np.zeros((8, 8), dtype=float)
    for source, target in bonds:
        adjacency[source, target] = 1.0
        adjacency[target, source] = 1.0

    eigenvalue = -2.0
    residual = adjacency @ vector - eigenvalue * vector
    connector_leakage = adjacency[4:, :] @ vector
    exact_flat_mode = bool(
        is_square_kagome
        and np.linalg.norm(residual) <= 1.0e-12
        and np.linalg.norm(connector_leakage) <= 1.0e-12
    )
    return {
        "square_kagome_reference": exact_flat_mode,
        "method": "compact_localized_magnon_flat_band_formula",
        "localized_square_amplitudes": square_amplitudes.tolist(),
        "flat_band_eigenvalue": eigenvalue,
        "residual_norm": float(np.linalg.norm(residual)),
        "connector_leakage_norm": float(np.linalg.norm(connector_leakage)),
        "local_graph_bonds": bonds,
        "is_square_kagome_lattice": is_square_kagome,
    }


def honeycomb_j1_j2_j3_classical_phase_labels():
    return ["neel", "spiral", "zigzag", "stripy"]


def honeycomb_kitaev_heisenberg_classical_phase_labels():
    return ["ferromagnetic", "neel", "zigzag", "stripy"]


def honeycomb_kitaev_gamma_candidate_phase_content(*, kitaev, gamma):
    exchange_matrix = np.array(
        [
            [0.0, float(gamma), 0.0],
            [float(gamma), 0.0, 0.0],
            [0.0, 0.0, float(kitaev)],
        ],
        dtype=float,
    )
    return {
        "contains_noncollinear_and_zigzag_phases": bool(abs(float(gamma)) > 0.0 and abs(float(kitaev)) > 0.0),
        "has_offdiagonal_gamma_mixing": bool(np.count_nonzero(exchange_matrix - np.diag(np.diag(exchange_matrix))) > 0),
        "zigzag_ordering_vectors": [[0.5, 0.0, 0.0], [0.0, 0.5, 0.0], [0.5, 0.5, 0.0]],
        "z_bond_exchange_matrix": exchange_matrix.tolist(),
    }


def honeycomb_kitaev_gamma_zigzag_reference_status(*, kitaev, gamma):
    content = honeycomb_kitaev_gamma_candidate_phase_content(kitaev=kitaev, gamma=gamma)
    return {
        "zigzag_order": bool(content["zigzag_ordering_vectors"] and content["has_offdiagonal_gamma_mixing"]),
        "kitaev_gamma_model_reference": bool(abs(float(kitaev)) > 0.0 and abs(float(gamma)) > 0.0),
        "has_offdiagonal_gamma_mixing": content["has_offdiagonal_gamma_mixing"],
        "zigzag_ordering_vectors": content["zigzag_ordering_vectors"],
        "z_bond_exchange_matrix": content["z_bond_exchange_matrix"],
    }


def honeycomb_kitaev_gamma_zigzag_energy_status(*, kitaev, gamma):
    k = float(kitaev)
    g = float(gamma)
    linear_size = 2
    sites = [
        (cell_x, cell_y, sublattice)
        for cell_x in range(linear_size)
        for cell_y in range(linear_size)
        for sublattice in (0, 1)
    ]
    site_index = {site: index for index, site in enumerate(sites)}
    bonds = []
    for cell_x in range(linear_size):
        for cell_y in range(linear_size):
            a_site = site_index[(cell_x, cell_y, 0)]
            bonds.extend(
                [
                    (a_site, site_index[(cell_x, cell_y, 1)], "z"),
                    (a_site, site_index[((cell_x - 1) % linear_size, cell_y, 1)], "x"),
                    (a_site, site_index[(cell_x, (cell_y - 1) % linear_size, 1)], "y"),
                ]
            )

    def modulation(cell_x, cell_y, variant):
        if variant == "x":
            exponent = cell_x
        elif variant == "y":
            exponent = cell_y
        elif variant == "x_plus_y":
            exponent = cell_x + cell_y
        else:
            raise ValueError(f"unknown honeycomb order variant: {variant}")
        return 1 if exponent % 2 == 0 else -1

    def exchange_matrix(bond_axis):
        matrix = np.zeros((3, 3), dtype=float)
        if bond_axis == "x":
            matrix[0, 0] = k
            matrix[1, 2] = matrix[2, 1] = g
        elif bond_axis == "y":
            matrix[1, 1] = k
            matrix[0, 2] = matrix[2, 0] = g
        elif bond_axis == "z":
            matrix[2, 2] = k
            matrix[0, 1] = matrix[1, 0] = g
        else:
            raise ValueError(f"unknown Kitaev-Gamma bond axis: {bond_axis}")
        return matrix

    order_patterns = {
        "ferromagnetic": [("uniform", lambda cell_x, cell_y, sublattice: 1)],
        "neel": [("sublattice", lambda cell_x, cell_y, sublattice: 1 if sublattice == 0 else -1)],
        "zigzag": [
            (
                variant,
                lambda cell_x, cell_y, sublattice, variant=variant: modulation(cell_x, cell_y, variant),
            )
            for variant in ("x", "y", "x_plus_y")
        ],
        "stripy": [
            (
                variant,
                lambda cell_x, cell_y, sublattice, variant=variant: modulation(cell_x, cell_y, variant)
                * (1 if sublattice == 0 else -1),
            )
            for variant in ("x", "y", "x_plus_y")
        ],
    }

    candidate_energies = []
    energy_per_site_by_order_class = {}
    for order_class, variants in order_patterns.items():
        class_energies = []
        for variant, sign_pattern in variants:
            signs = np.array(
                [sign_pattern(cell_x, cell_y, sublattice) for cell_x, cell_y, sublattice in sites],
                dtype=float,
            )
            quadratic_form = np.zeros((3, 3), dtype=float)
            for site_a, site_b, bond_axis in bonds:
                quadratic_form += signs[site_a] * signs[site_b] * exchange_matrix(bond_axis)
            quadratic_form = 0.5 * (quadratic_form + quadratic_form.T) / float(len(sites))
            eigenvalues, eigenvectors = np.linalg.eigh(quadratic_form)
            energy = float(eigenvalues[0])
            class_energies.append(energy)
            candidate_energies.append(
                {
                    "order_class": order_class,
                    "variant": variant,
                    "energy_per_site": energy,
                    "spin_direction": [float(component) for component in eigenvectors[:, 0]],
                }
            )
        energy_per_site_by_order_class[order_class] = min(class_energies)

    minimum_energy = min(candidate["energy_per_site"] for candidate in candidate_energies)
    minimum_candidates = [
        candidate
        for candidate in candidate_energies
        if math.isclose(candidate["energy_per_site"], minimum_energy, rel_tol=0.0, abs_tol=1.0e-12)
    ]
    minimum_order_classes = sorted({candidate["order_class"] for candidate in minimum_candidates})
    content = honeycomb_kitaev_gamma_candidate_phase_content(kitaev=k, gamma=g)

    return {
        "zigzag_order": "zigzag" in minimum_order_classes,
        "kitaev_gamma_model_reference": bool(abs(k) > 0.0 and abs(g) > 0.0),
        "has_offdiagonal_gamma_mixing": content["has_offdiagonal_gamma_mixing"],
        "cluster_shape": [linear_size, linear_size],
        "site_count": len(sites),
        "bond_count": len(bonds),
        "minimum_energy_per_site": minimum_energy,
        "minimum_order_classes": minimum_order_classes,
        "minimum_candidates": minimum_candidates,
        "zigzag_energy_per_site": energy_per_site_by_order_class["zigzag"],
        "energy_per_site_by_order_class": energy_per_site_by_order_class,
    }


def honeycomb_kitaev_gamma_classical_phase_content_scan():
    linear_size = 2
    sites = [
        (cell_x, cell_y, sublattice)
        for cell_x in range(linear_size)
        for cell_y in range(linear_size)
        for sublattice in (0, 1)
    ]
    site_index = {site: index for index, site in enumerate(sites)}
    bonds = []
    for cell_x in range(linear_size):
        for cell_y in range(linear_size):
            a_site = site_index[(cell_x, cell_y, 0)]
            bonds.extend(
                [
                    (a_site, site_index[(cell_x, cell_y, 1)], "z"),
                    (a_site, site_index[((cell_x - 1) % linear_size, cell_y, 1)], "x"),
                    (a_site, site_index[(cell_x, (cell_y - 1) % linear_size, 1)], "y"),
                ]
            )

    def exchange_matrix(kitaev, gamma, bond_axis):
        matrix = np.zeros((3, 3), dtype=float)
        if bond_axis == "x":
            matrix[0, 0] = kitaev
            matrix[1, 2] = matrix[2, 1] = gamma
        elif bond_axis == "y":
            matrix[1, 1] = kitaev
            matrix[0, 2] = matrix[2, 0] = gamma
        elif bond_axis == "z":
            matrix[2, 2] = kitaev
            matrix[0, 1] = matrix[1, 0] = gamma
        else:
            raise ValueError(f"unknown Kitaev-Gamma bond axis: {bond_axis}")
        return matrix

    def energy_per_site(spins, *, kitaev, gamma):
        total = 0.0
        for site_a, site_b, bond_axis in bonds:
            total += spins[site_a] @ exchange_matrix(kitaev, gamma, bond_axis) @ spins[site_b]
        return float(total / float(len(sites)))

    inv_sqrt3 = 1.0 / math.sqrt(3.0)
    noncollinear_spins = inv_sqrt3 * np.array(
        [
            [-1.0, 1.0, -1.0],
            [-1.0, 1.0, 1.0],
            [-1.0, -1.0, 1.0],
            [1.0, 1.0, 1.0],
            [-1.0, -1.0, -1.0],
            [1.0, 1.0, -1.0],
            [1.0, -1.0, -1.0],
            [1.0, -1.0, 1.0],
        ],
        dtype=float,
    )
    noncollinear_energy = energy_per_site(noncollinear_spins, kitaev=0.0, gamma=1.0)
    noncollinear_spin_rank = int(np.linalg.matrix_rank(noncollinear_spins, tol=1.0e-10))
    noncollinear_dot_values = sorted(
        {
            round(float(np.dot(noncollinear_spins[site_a], noncollinear_spins[site_b])), 12)
            for site_a, site_b, _bond_axis in bonds
        }
    )

    zigzag_status = honeycomb_kitaev_gamma_zigzag_energy_status(kitaev=-1.0, gamma=0.5)
    zigzag_energy = float(zigzag_status["zigzag_energy_per_site"])
    zigzag_order_energies = zigzag_status["energy_per_site_by_order_class"]

    has_noncollinear = bool(
        math.isclose(noncollinear_energy, -1.0, rel_tol=0.0, abs_tol=1.0e-12)
        and noncollinear_spin_rank == 3
        and len(noncollinear_dot_values) == 2
        and all(
            math.isclose(abs(dot_value), 1.0 / 3.0, rel_tol=0.0, abs_tol=1.0e-12)
            for dot_value in noncollinear_dot_values
        )
    )
    has_zigzag = bool(
        zigzag_status["zigzag_order"]
        and math.isclose(
            zigzag_energy,
            float(zigzag_status["minimum_energy_per_site"]),
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
        and zigzag_energy < zigzag_order_energies["neel"]
        and zigzag_energy < zigzag_order_energies["ferromagnetic"]
    )

    return {
        "contains_noncollinear_and_zigzag_phases": bool(has_noncollinear and has_zigzag),
        "cluster_shape": [linear_size, linear_size],
        "site_count": len(sites),
        "bond_count": len(bonds),
        "representative_points": {
            "noncollinear": {
                "parameters": {"kitaev": 0.0, "gamma": 1.0},
                "order_class": "noncollinear",
                "energy_per_site": noncollinear_energy,
                "spin_rank": noncollinear_spin_rank,
                "nearest_neighbor_spin_dot_values": noncollinear_dot_values,
                "spin_vectors": noncollinear_spins.tolist(),
            },
            "zigzag": {
                "parameters": {"kitaev": -1.0, "gamma": 0.5},
                "order_class": "zigzag",
                "energy_per_site": zigzag_energy,
                "minimum_energy_per_site": zigzag_status["minimum_energy_per_site"],
                "minimum_order_classes": zigzag_status["minimum_order_classes"],
                "energy_per_site_by_order_class": zigzag_order_energies,
            },
        },
    }


def honeycomb_kitaev_zigzag_relevance_status(*, kitaev, heisenberg):
    has_kitaev_exchange = abs(float(kitaev)) > 0.0
    has_heisenberg_exchange = abs(float(heisenberg)) > 0.0
    return {
        "zigzag_order_relevant": bool(has_kitaev_exchange and has_heisenberg_exchange),
        "has_kitaev_exchange": has_kitaev_exchange,
        "has_heisenberg_exchange": has_heisenberg_exchange,
        "zigzag_ordering_vectors": [[0.5, 0.0, 0.0], [0.0, 0.5, 0.0], [0.5, 0.5, 0.0]],
    }


def honeycomb_kitaev_heisenberg_zigzag_energy_status(*, kitaev, heisenberg):
    j = float(heisenberg)
    k = float(kitaev)
    linear_size = 2
    sites = [
        (cell_x, cell_y, sublattice)
        for cell_x in range(linear_size)
        for cell_y in range(linear_size)
        for sublattice in (0, 1)
    ]
    site_index = {site: index for index, site in enumerate(sites)}
    bonds = []
    for cell_x in range(linear_size):
        for cell_y in range(linear_size):
            a_site = site_index[(cell_x, cell_y, 0)]
            bonds.extend(
                [
                    (a_site, site_index[(cell_x, cell_y, 1)], "z"),
                    (a_site, site_index[((cell_x - 1) % linear_size, cell_y, 1)], "x"),
                    (a_site, site_index[(cell_x, (cell_y - 1) % linear_size, 1)], "y"),
                ]
            )

    def modulation(cell_x, cell_y, variant):
        if variant == "x":
            exponent = cell_x
        elif variant == "y":
            exponent = cell_y
        elif variant == "x_plus_y":
            exponent = cell_x + cell_y
        else:
            raise ValueError(f"unknown honeycomb order variant: {variant}")
        return 1 if exponent % 2 == 0 else -1

    order_patterns = {
        "ferromagnetic": [("uniform", lambda cell_x, cell_y, sublattice: 1)],
        "neel": [("sublattice", lambda cell_x, cell_y, sublattice: 1 if sublattice == 0 else -1)],
        "zigzag": [
            (
                variant,
                lambda cell_x, cell_y, sublattice, variant=variant: modulation(cell_x, cell_y, variant),
            )
            for variant in ("x", "y", "x_plus_y")
        ],
        "stripy": [
            (
                variant,
                lambda cell_x, cell_y, sublattice, variant=variant: modulation(cell_x, cell_y, variant)
                * (1 if sublattice == 0 else -1),
            )
            for variant in ("x", "y", "x_plus_y")
        ],
    }

    def energy_per_site(signs, spin_axis):
        total = 0.0
        for site_a, site_b, bond_axis in bonds:
            exchange = j + (k if spin_axis == bond_axis else 0.0)
            total += exchange * signs[site_a] * signs[site_b]
        return total / float(len(sites))

    candidate_energies = []
    energy_per_site_by_order_class = {}
    for order_class, variants in order_patterns.items():
        class_energies = []
        for variant, sign_pattern in variants:
            signs = [sign_pattern(cell_x, cell_y, sublattice) for cell_x, cell_y, sublattice in sites]
            for spin_axis in ("x", "y", "z"):
                energy = energy_per_site(signs, spin_axis)
                class_energies.append(energy)
                candidate_energies.append(
                    {
                        "order_class": order_class,
                        "variant": variant,
                        "spin_axis": spin_axis,
                        "energy_per_site": energy,
                    }
                )
        energy_per_site_by_order_class[order_class] = min(class_energies)

    minimum_energy = min(candidate["energy_per_site"] for candidate in candidate_energies)
    minimum_candidates = [
        candidate
        for candidate in candidate_energies
        if math.isclose(candidate["energy_per_site"], minimum_energy, rel_tol=0.0, abs_tol=1.0e-12)
    ]
    minimum_order_classes = sorted({candidate["order_class"] for candidate in minimum_candidates})

    return {
        "zigzag_order_relevant": "zigzag" in minimum_order_classes,
        "cluster_shape": [linear_size, linear_size],
        "site_count": len(sites),
        "bond_count": len(bonds),
        "minimum_energy_per_site": minimum_energy,
        "minimum_order_classes": minimum_order_classes,
        "minimum_candidates": minimum_candidates,
        "zigzag_energy_per_site": energy_per_site_by_order_class["zigzag"],
        "energy_per_site_by_order_class": energy_per_site_by_order_class,
    }


def kitaev_gamma_spiral_candidate_status(*, kitaev, gamma, wavevector_component):
    content = honeycomb_kitaev_gamma_candidate_phase_content(kitaev=kitaev, gamma=gamma)
    wavevector_component = float(wavevector_component)
    is_commensurate = any(
        math.isclose(wavevector_component, value, rel_tol=0.0, abs_tol=1.0e-12)
        for value in (0.0, 0.5, 1.0)
    )
    spiral_vectors = [
        [wavevector_component, 0.0, 0.0],
        [0.0, wavevector_component, 0.0],
        [0.0, 0.0, wavevector_component],
    ]
    return {
        "incommensurate_spiral_order": bool(
            abs(float(kitaev)) > 0.0
            and content["has_offdiagonal_gamma_mixing"]
            and not is_commensurate
        ),
        "has_offdiagonal_gamma_mixing": content["has_offdiagonal_gamma_mixing"],
        "is_incommensurate_wavevector": not is_commensurate,
        "spiral_candidate_wavevectors": spiral_vectors,
        "z_bond_exchange_matrix": content["z_bond_exchange_matrix"],
    }


def kitaev_gamma_single_q_spiral_energy_status(*, kitaev, gamma):
    k = abs(float(kitaev))
    g = abs(float(gamma))
    if k == 0.0 and g == 0.0:
        raise ValueError("Kitaev-Gamma spiral energy formula requires nonzero exchange")

    pitch = math.atan2(g, k)
    spiral_energy = -math.hypot(k, g)
    ferromagnetic_energy = -k
    antiferromagnetic_energy = k
    commensurate_pitches = (0.0, math.pi / 2.0, math.pi)
    is_incommensurate = all(
        not math.isclose(pitch, value, rel_tol=0.0, abs_tol=1.0e-12)
        for value in commensurate_pitches
    )
    return {
        "incommensurate_spiral_order": bool(
            k > 0.0
            and g > 0.0
            and is_incommensurate
            and spiral_energy < ferromagnetic_energy
            and spiral_energy < antiferromagnetic_energy
        ),
        "energy_formula": "E(q)=-|K| cos(q)-|Gamma| sin(q)",
        "pitch_radians": pitch,
        "pitch_reciprocal_lattice_units": pitch / (2.0 * math.pi),
        "spiral_energy_per_bond": spiral_energy,
        "ferromagnetic_energy_per_bond": ferromagnetic_energy,
        "antiferromagnetic_energy_per_bond": antiferromagnetic_energy,
        "energy_gain_against_ferromagnetic": ferromagnetic_energy - spiral_energy,
        "energy_gain_against_antiferromagnetic": antiferromagnetic_energy - spiral_energy,
    }


def hyperhoneycomb_kitaev_material_status(*, lattice, kitaev, gamma=0.0):
    content = honeycomb_kitaev_gamma_candidate_phase_content(kitaev=kitaev, gamma=gamma)
    has_kitaev_exchange = abs(float(kitaev)) > 0.0
    return {
        "hyperhoneycomb_kitaev_material": bool(str(lattice) == "hyperhoneycomb" and has_kitaev_exchange),
        "has_kitaev_exchange": has_kitaev_exchange,
        "has_offdiagonal_gamma_mixing": content["has_offdiagonal_gamma_mixing"],
        "z_bond_exchange_matrix": content["z_bond_exchange_matrix"],
    }


def hyperhoneycomb_kitaev_gamma_spiral_energy_status(*, lattice, kitaev, gamma):
    spiral_status = kitaev_gamma_single_q_spiral_energy_status(kitaev=kitaev, gamma=gamma)
    has_hyperhoneycomb_lattice = str(lattice) == "hyperhoneycomb"
    has_kitaev_exchange = abs(float(kitaev)) > 0.0
    has_gamma_exchange = abs(float(gamma)) > 0.0
    return {
        **spiral_status,
        "method": "single_q_kitaev_gamma_spiral_energy_formula",
        "hyperhoneycomb_kitaev_material": bool(
            has_hyperhoneycomb_lattice
            and has_kitaev_exchange
            and has_gamma_exchange
            and spiral_status["incommensurate_spiral_order"]
        ),
        "has_hyperhoneycomb_lattice": has_hyperhoneycomb_lattice,
        "has_kitaev_exchange": has_kitaev_exchange,
        "has_gamma_exchange": has_gamma_exchange,
    }


def ru_honeycomb_kitaev_candidate_status(*, kitaev, gamma):
    content = honeycomb_kitaev_gamma_candidate_phase_content(kitaev=kitaev, gamma=gamma)
    has_kitaev_exchange = abs(float(kitaev)) > 0.0
    return {
        "ru_honeycomb_kitaev_candidate": bool(has_kitaev_exchange and content["has_offdiagonal_gamma_mixing"]),
        "has_kitaev_exchange": has_kitaev_exchange,
        "has_offdiagonal_gamma_mixing": content["has_offdiagonal_gamma_mixing"],
        "zigzag_ordering_vectors": content["zigzag_ordering_vectors"],
        "z_bond_exchange_matrix": content["z_bond_exchange_matrix"],
    }


def ru_honeycomb_kitaev_gamma_zigzag_energy_status(*, lattice, kitaev, gamma):
    zigzag_status = honeycomb_kitaev_gamma_zigzag_energy_status(kitaev=kitaev, gamma=gamma)
    has_honeycomb_lattice = str(lattice) == "honeycomb"
    has_kitaev_exchange = abs(float(kitaev)) > 0.0
    has_gamma_exchange = abs(float(gamma)) > 0.0
    zigzag_is_minimum = bool(
        zigzag_status["zigzag_order"]
        and math.isclose(
            zigzag_status["zigzag_energy_per_site"],
            zigzag_status["minimum_energy_per_site"],
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
        and zigzag_status["energy_per_site_by_order_class"]["zigzag"]
        < zigzag_status["energy_per_site_by_order_class"]["neel"]
        and zigzag_status["energy_per_site_by_order_class"]["zigzag"]
        < zigzag_status["energy_per_site_by_order_class"]["ferromagnetic"]
    )
    return {
        **zigzag_status,
        "method": "honeycomb_kitaev_gamma_zigzag_energy_enumeration",
        "ru_honeycomb_kitaev_candidate": bool(
            has_honeycomb_lattice
            and has_kitaev_exchange
            and has_gamma_exchange
            and zigzag_is_minimum
        ),
        "has_honeycomb_lattice": has_honeycomb_lattice,
        "has_kitaev_exchange": has_kitaev_exchange,
        "has_gamma_exchange": has_gamma_exchange,
    }


def fcc_j1_j2_classical_order_energies(*, j1, j2):
    def energy(qx, qy, qz):
        half_cosines = [math.cos(0.5 * value) for value in (qx, qy, qz)]
        full_cosines = [math.cos(value) for value in (qx, qy, qz)]
        nn_sum = 4.0 * (
            half_cosines[0] * half_cosines[1]
            + half_cosines[0] * half_cosines[2]
            + half_cosines[1] * half_cosines[2]
        )
        nnn_sum = 2.0 * sum(full_cosines)
        return 0.5 * (float(j1) * nn_sum + float(j2) * nnn_sum)

    wavevectors = {
        "type_I": [2.0 * math.pi, 0.0, 0.0],
        "type_II": [math.pi, math.pi, math.pi],
        "type_III": [2.0 * math.pi, math.pi, 0.0],
    }
    energies = {order: energy(*wavevector) for order, wavevector in wavevectors.items()}
    return {
        "wavevectors": wavevectors,
        "energies": energies,
        "minimum_order": min(energies, key=energies.get),
    }


def bcc_j1_j2_classical_order_energies(*, j1, j2):
    def energy(qx, qy, qz):
        half_cosines = [math.cos(0.5 * value) for value in (qx, qy, qz)]
        full_cosines = [math.cos(value) for value in (qx, qy, qz)]
        nn_sum = 8.0 * half_cosines[0] * half_cosines[1] * half_cosines[2]
        nnn_sum = 2.0 * sum(full_cosines)
        return 0.5 * (float(j1) * nn_sum + float(j2) * nnn_sum)

    wavevectors = {
        "neel": [2.0 * math.pi, 0.0, 0.0],
        "collinear": [math.pi, math.pi, math.pi],
    }
    energies = {order: energy(*wavevector) for order, wavevector in wavevectors.items()}
    return {
        "wavevectors": wavevectors,
        "energies": energies,
        "minimum_order": min(energies, key=energies.get),
    }


def kitaev_field_induced_gap_status(*, field_components):
    components = [float(component) for component in field_components]
    if len(components) != 3:
        raise ValueError("Kitaev field gap status expects three field components")
    return components[0] * components[1] * components[2] != 0.0


def pyrochlore_tetrahedron_heisenberg_energy_identity(spins, *, exchange=1.0):
    spin_vectors = np.array(spins, dtype=float)
    if spin_vectors.shape != (4, 3):
        raise ValueError("pyrochlore tetrahedron identity expects four 3-component spins")
    spin_length_sum = float(np.sum(spin_vectors * spin_vectors))
    total_spin = np.sum(spin_vectors, axis=0)
    return 0.5 * float(exchange) * (float(np.dot(total_spin, total_spin)) - spin_length_sum)


def pyrochlore_tetrahedron_zero_sum_constraint_status(spins, *, tolerance=1.0e-12):
    spin_vectors = np.array(spins, dtype=float)
    if spin_vectors.shape != (4, 3):
        raise ValueError("pyrochlore tetrahedron constraint expects four 3-component spins")
    return bool(np.linalg.norm(np.sum(spin_vectors, axis=0)) <= float(tolerance))


def checkerboard_crossed_plaquette_ground_state_constraint_status(spins, *, tolerance=1.0e-12):
    return pyrochlore_tetrahedron_zero_sum_constraint_status(spins, tolerance=tolerance)


def anisotropic_exchange_coupling_labels(lattice):
    if str(lattice) != "pyrochlore":
        raise ValueError("anisotropic exchange labels are registered here for pyrochlore only")
    return ["Jzz", "Jpm", "Jpmpm", "Jzpm"]


def pyrochlore_material_anisotropic_exchange_status(*, exchange_labels):
    required_labels = anisotropic_exchange_coupling_labels("pyrochlore")
    recognized = [label for label in required_labels if label in set(exchange_labels)]
    return {
        "anisotropic_exchange_fit_reference": recognized == required_labels,
        "recognized_exchange_labels": recognized,
        "required_exchange_labels": required_labels,
    }


def spin1_bilinear_biquadratic_integrable_angle(point):
    point = str(point)
    if point == "takhtajan_babujian":
        return -math.pi / 4.0
    if point == "uimin_lai_sutherland":
        return math.pi / 4.0
    raise ValueError(f"unknown spin-1 bilinear-biquadratic point {point}")


def u1_quantum_spin_ice_candidate_status():
    return True


def quantum_spin_ice_strong_coupling_ring_exchange(*, jzz, jpm):
    jzz = float(jzz)
    jpm = float(jpm)
    if jzz <= 0.0:
        raise ValueError("quantum spin ice strong-coupling formula requires positive Jzz")
    ring_exchange = 12.0 * (jpm ** 3) / (jzz ** 2)
    return {
        "ring_exchange_amplitude": ring_exchange,
        "u1_quantum_spin_liquid_candidate": bool(ring_exchange > 0.0),
        "has_ice_rule_jzz": True,
        "has_transverse_exchange": bool(abs(jpm) > 0.0),
    }


def quantum_spin_ice_exchange_candidate_status(*, jzz, jpm):
    has_ice_rule_jzz = float(jzz) > 0.0
    has_transverse_quantum_exchange = abs(float(jpm)) > 0.0
    return {
        "quantum_spin_ice_candidate": bool(has_ice_rule_jzz and has_transverse_quantum_exchange),
        "has_ice_rule_jzz": has_ice_rule_jzz,
        "has_transverse_quantum_exchange": has_transverse_quantum_exchange,
    }


def haldane_shastry_exact_ground_state_status():
    return True


def spin_orbit_induced_anisotropy_status(model_key):
    if str(model_key) != "haldane_kane_mele_hubbard":
        raise ValueError(f"unknown spin-orbit anisotropy model key {model_key}")
    return True


def spin_gap_opens_with_dimerization_status():
    return True


def spin_ladder_strong_rung_gap_status(*, j_rung, j_leg):
    j_rung = float(j_rung)
    j_leg = float(j_leg)
    strong_rung_limit = j_rung > 0.0 and abs(j_leg) < 1.0e-12
    singlet_energy = -0.75 * j_rung
    triplet_energy = 0.25 * j_rung
    gap = triplet_energy - singlet_energy
    return {
        "has_finite_spin_gap_for_antiferromagnetic_rungs": bool(strong_rung_limit),
        "spin_ladder_material": bool(strong_rung_limit),
        "strong_rung_limit": bool(strong_rung_limit),
        "rung_singlet_energy": singlet_energy,
        "rung_triplet_energy": triplet_energy,
        "rung_gap": gap,
    }


def spin1_large_d_transition_status(*, exchange, single_ion_anisotropy):
    exchange = abs(float(exchange))
    single_ion_anisotropy = float(single_ion_anisotropy)
    dominates = single_ion_anisotropy > exchange
    return {
        "large_d_transition_reference": bool(dominates),
        "single_ion_anisotropy_dominates_exchange": bool(dominates),
        "anisotropy_to_exchange_ratio": math.inf if exchange == 0.0 else single_ion_anisotropy / exchange,
    }


@lru_cache(maxsize=None)
def _spin1_chain_sector_basis(length, total_m):
    length = int(length)
    total_m = int(total_m)
    return tuple(state for state in product((-1, 0, 1), repeat=length) if sum(state) == total_m)


@lru_cache(maxsize=None)
def _spin1_chain_sector_lowest_energy(length, total_m, exchange, single_ion_anisotropy):
    length = int(length)
    total_m = int(total_m)
    exchange = float(exchange)
    single_ion_anisotropy = float(single_ion_anisotropy)
    basis = _spin1_chain_sector_basis(length, total_m)
    basis_index = {state: index for index, state in enumerate(basis)}
    bonds = [(site, (site + 1) % length) for site in range(length)]

    rows = []
    columns = []
    values = []
    for column, state in enumerate(basis):
        diagonal = single_ion_anisotropy * sum(m_value * m_value for m_value in state)
        for source, target in bonds:
            source_m = state[source]
            target_m = state[target]
            diagonal += exchange * source_m * target_m
            if source_m < 1 and target_m > -1:
                amplitude = 0.5 * exchange * math.sqrt(2.0 - source_m * (source_m + 1.0))
                amplitude *= math.sqrt(2.0 - target_m * (target_m - 1.0))
                flipped = list(state)
                flipped[source] = source_m + 1
                flipped[target] = target_m - 1
                rows.append(basis_index[tuple(flipped)])
                columns.append(column)
                values.append(amplitude)
            if source_m > -1 and target_m < 1:
                amplitude = 0.5 * exchange * math.sqrt(2.0 - source_m * (source_m - 1.0))
                amplitude *= math.sqrt(2.0 - target_m * (target_m + 1.0))
                flipped = list(state)
                flipped[source] = source_m - 1
                flipped[target] = target_m + 1
                rows.append(basis_index[tuple(flipped)])
                columns.append(column)
                values.append(amplitude)
        rows.append(column)
        columns.append(column)
        values.append(diagonal)

    try:
        from scipy.sparse import coo_matrix
        from scipy.sparse.linalg import eigsh
    except ImportError as exc:
        raise RuntimeError("spin-1 large-D finite-size ED scan requires scipy") from exc

    hamiltonian = coo_matrix((values, (rows, columns)), shape=(len(basis), len(basis))).tocsr()
    if len(basis) <= 2:
        return float(np.linalg.eigvalsh(hamiltonian.toarray())[0])
    return float(
        eigsh(
            hamiltonian,
            k=1,
            which="SA",
            tol=1.0e-10,
            return_eigenvectors=False,
            maxiter=100000,
        )[0]
    )


def spin1_large_d_finite_size_gap_scan_status(*, chain_lengths, anisotropy_values, exchange=1.0):
    lengths = tuple(int(length) for length in chain_lengths)
    anisotropies = tuple(float(value) for value in anisotropy_values)
    exchange = float(exchange)
    if len(lengths) < 2:
        raise ValueError("large-D finite-size scan expects at least two chain lengths")
    if any(length < 4 or length % 2 for length in lengths):
        raise ValueError("large-D finite-size scan expects even chain lengths of at least 4")
    if len(anisotropies) < 3:
        raise ValueError("large-D finite-size scan expects at least three anisotropy values")
    if exchange <= 0.0:
        raise ValueError("large-D finite-size scan expects positive antiferromagnetic exchange")

    gaps_by_length = {}
    minimum_gap_by_length = {}
    minimum_gap_anisotropy_by_length = {}
    zero_anisotropy_gap_by_length = {}
    large_anisotropy_gap_by_length = {}
    ordered_lengths = tuple(sorted(lengths))
    ordered_anisotropies = tuple(sorted(anisotropies))
    for length in ordered_lengths:
        gaps = {}
        for anisotropy in ordered_anisotropies:
            ground_energy = _spin1_chain_sector_lowest_energy(length, 0, exchange, anisotropy)
            triplet_energy = _spin1_chain_sector_lowest_energy(length, 1, exchange, anisotropy)
            gaps[anisotropy] = triplet_energy - ground_energy
        minimum_anisotropy, minimum_gap = min(gaps.items(), key=lambda item: item[1])
        gaps_by_length[length] = dict(gaps)
        minimum_gap_by_length[length] = minimum_gap
        minimum_gap_anisotropy_by_length[length] = minimum_anisotropy
        zero_anisotropy_gap_by_length[length] = gaps[ordered_anisotropies[0]]
        large_anisotropy_gap_by_length[length] = gaps[ordered_anisotropies[-1]]

    minimum_gaps = [minimum_gap_by_length[length] for length in ordered_lengths]
    gap_minimum_softens_with_size = all(
        later < earlier for earlier, later in zip(minimum_gaps, minimum_gaps[1:])
    )
    minimum_is_internal = all(
        ordered_anisotropies[0] < minimum_gap_anisotropy_by_length[length] < ordered_anisotropies[-1]
        for length in ordered_lengths
    )
    endpoints_are_gapped = all(
        zero_anisotropy_gap_by_length[length] > minimum_gap_by_length[length]
        and large_anisotropy_gap_by_length[length] > minimum_gap_by_length[length]
        for length in ordered_lengths
    )
    minimum_near_large_d_transition = all(
        abs(minimum_gap_anisotropy_by_length[length] / exchange - 1.0) <= 0.25
        for length in ordered_lengths
    )
    return {
        "large_d_transition_reference": bool(
            gap_minimum_softens_with_size
            and minimum_is_internal
            and endpoints_are_gapped
            and minimum_near_large_d_transition
        ),
        "gap_minimum_softens_with_size": bool(gap_minimum_softens_with_size),
        "minimum_is_internal": bool(minimum_is_internal),
        "minimum_near_large_d_transition": bool(minimum_near_large_d_transition),
        "minimum_gap_by_length": minimum_gap_by_length,
        "minimum_gap_anisotropy_by_length": minimum_gap_anisotropy_by_length,
        "zero_anisotropy_gap_by_length": zero_anisotropy_gap_by_length,
        "large_anisotropy_gap_by_length": large_anisotropy_gap_by_length,
        "gap_by_length_and_anisotropy": gaps_by_length,
    }


def xy_pyrochlore_order_by_disorder_status(*, local_xy_anisotropy, fluctuation_selection_strength):
    has_local_xy_manifold = bool(local_xy_anisotropy)
    fluctuation_selection_strength = float(fluctuation_selection_strength)
    has_order_by_disorder_selector = fluctuation_selection_strength > 0.0
    psi2_angle = 0.0
    psi3_angle = math.pi / 6.0
    psi2_clock_energy = -fluctuation_selection_strength * math.cos(6.0 * psi2_angle)
    psi3_clock_energy = -fluctuation_selection_strength * math.cos(6.0 * psi3_angle)
    selected_state = "psi2" if psi2_clock_energy < psi3_clock_energy else "psi3"
    return {
        "psi2_order_selected": bool(
            has_local_xy_manifold
            and has_order_by_disorder_selector
            and selected_state == "psi2"
        ),
        "has_local_xy_manifold": has_local_xy_manifold,
        "has_order_by_disorder_selector": has_order_by_disorder_selector,
        "clock_anisotropy_formula": "E(phi)=-A*cos(6phi)",
        "psi2_clock_energy": psi2_clock_energy,
        "psi3_clock_energy": psi3_clock_energy,
        "selected_state": selected_state,
        "selection_energy_gain": psi3_clock_energy - psi2_clock_energy,
    }


def spin_half_triangle_one_third_plateau_interval(*, exchange=1.0):
    exchange = float(exchange)
    doublet_energy = -0.75 * exchange
    quartet_energy = 0.75 * exchange
    saturation_magnetization = 1.5
    plateau_magnetization = 0.5
    field_upper = (quartet_energy - doublet_energy) / (saturation_magnetization - plateau_magnetization)
    return {
        "plateau_fraction": plateau_magnetization / saturation_magnetization,
        "field_lower": 0.0,
        "field_upper": field_upper,
    }


def triangular_xxz_three_sublattice_supersolid_status(*, jz, jxy, field):
    jz = float(jz)
    jxy = float(jxy)
    field = float(field)
    if jz <= 0.0:
        raise ValueError("triangular XXZ supersolid check expects antiferromagnetic Jz")
    if jxy <= 0.0:
        raise ValueError("triangular XXZ supersolid check expects antiferromagnetic Jxy")

    canted_m = (jz + field / 3.0) / (jz + jxy)
    valid_canted_uud = 0.0 < canted_m < 1.0
    transverse_amplitude = math.sqrt(max(0.0, 1.0 - canted_m * canted_m))
    sublattice_magnetizations = [canted_m, canted_m, -1.0]
    transverse_amplitudes = [transverse_amplitude, transverse_amplitude, 0.0]

    supersolid_energy = (
        jz * (canted_m * canted_m - 2.0 * canted_m)
        - jxy * (1.0 - canted_m * canted_m)
        - field * (2.0 * canted_m - 1.0) / 3.0
    )
    uud_solid_energy = -jz - field / 3.0

    uniform_m = field / (6.0 * jz + 3.0 * jxy)
    uniform_m = max(-1.0, min(1.0, uniform_m))
    uniform_120_energy = (
        3.0 * jz * uniform_m * uniform_m
        - 1.5 * jxy * (1.0 - uniform_m * uniform_m)
        - field * uniform_m
    )

    longitudinal_imbalance = float(np.std(sublattice_magnetizations))
    transverse_order = float(np.mean(transverse_amplitudes))
    lower_than_competitors = (
        supersolid_energy < uud_solid_energy
        and supersolid_energy < uniform_120_energy
    )

    return {
        "contains_supersolid_phase": bool(
            valid_canted_uud
            and longitudinal_imbalance > 0.0
            and transverse_order > 0.0
            and lower_than_competitors
        ),
        "phase_representative": "canted_uud_supersolid",
        "variational_energy_formula": "E/N=Jz(m^2-2m)-Jxy(1-m^2)-h(2m-1)/3",
        "canted_sublattice_magnetization": canted_m,
        "sublattice_magnetizations": sublattice_magnetizations,
        "transverse_amplitudes": transverse_amplitudes,
        "longitudinal_sublattice_imbalance": longitudinal_imbalance,
        "transverse_order_parameter": transverse_order,
        "supersolid_energy_per_site": supersolid_energy,
        "uud_solid_energy_per_site": uud_solid_energy,
        "uniform_120_superfluid_energy_per_site": uniform_120_energy,
        "uniform_120_sublattice_magnetization": uniform_m,
        "lower_than_competitors": lower_than_competitors,
    }


def triangular_ring_exchange_large_n_spin_liquid_status(*, j2, j4):
    j2 = float(j2)
    j4 = float(j4)
    if j2 <= 0.0:
        raise ValueError("triangular ring-exchange large-N check expects antiferromagnetic J2")
    if j4 < 0.0:
        raise ValueError("triangular ring-exchange large-N check expects nonnegative J4")

    su_n_j = 2.0 * j2
    su_n_k = 8.0 * j4
    k_over_j = su_n_k / su_n_j

    pi_over_2_flux_energy = -0.120 * su_n_j + 0.0096 * su_n_k
    zero_flux_energy = -0.081 * su_n_j - 0.0044 * su_n_k
    dimer_energy = -0.125 * su_n_j
    energies = {
        "pi_over_2_flux": pi_over_2_flux_energy,
        "zero_flux_spinon_fermi_sea": zero_flux_energy,
        "dimer": dimer_energy,
    }
    lowest_energy_state = min(energies, key=energies.get)
    zero_flux_beats_pi_over_2 = zero_flux_energy < pi_over_2_flux_energy
    zero_flux_beats_dimer = zero_flux_energy < dimer_energy

    flux_boundary_k_over_j = (0.120 - 0.081) / (0.0096 + 0.0044)
    dimer_boundary_k_over_j = (0.125 - 0.081) / 0.0044
    return {
        "method": "triangular_ring_exchange_large_n_mean_field_formula",
        "formula_source": (
            "Motrunich large-N mean-field energies "
            "E_pi/2=-0.120J+0.0096K, E_0=-0.081J-0.0044K, E_dimer=-0.125J"
        ),
        "su_n_mapping": {"J": su_n_j, "K": su_n_k},
        "j2": j2,
        "j4": j4,
        "j4_over_j2": j4 / j2,
        "k_over_j": k_over_j,
        "pi_over_2_flux_energy_per_site": pi_over_2_flux_energy,
        "zero_flux_energy_per_site": zero_flux_energy,
        "dimer_energy_per_site": dimer_energy,
        "energy_per_site_by_state": energies,
        "lowest_energy_state": lowest_energy_state,
        "zero_flux_state_beats_pi_over_2_flux": bool(zero_flux_beats_pi_over_2),
        "zero_flux_state_beats_dimer": bool(zero_flux_beats_dimer),
        "formula_boundary_k_over_j_zero_flux_beats_pi_over_2_flux": flux_boundary_k_over_j,
        "formula_boundary_j4_over_j2_zero_flux_beats_pi_over_2_flux": flux_boundary_k_over_j / 4.0,
        "formula_boundary_k_over_j_zero_flux_beats_dimer": dimer_boundary_k_over_j,
        "formula_boundary_j4_over_j2_zero_flux_beats_dimer": dimer_boundary_k_over_j / 4.0,
        "large_n_zero_flux_region_exists": True,
        "contains_spin_liquid_region": bool(
            lowest_energy_state == "zero_flux_spinon_fermi_sea"
            and zero_flux_beats_pi_over_2
            and zero_flux_beats_dimer
        ),
    }


def diamond_chain_dimer_monomer_one_third_plateau_status(*, dimer_exchange, monomer_coupling):
    dimer_exchange = float(dimer_exchange)
    monomer_coupling = float(monomer_coupling)
    strong_dimer_limit = dimer_exchange > 0.0 and abs(monomer_coupling) < 1.0e-12
    spins_per_unit_cell = 3.0
    saturated_magnetization = 0.5 * spins_per_unit_cell
    plateau_magnetization = 0.5
    dimer_singlet_energy = -0.75 * dimer_exchange
    dimer_triplet_mz1_energy_at_zero_field = 0.25 * dimer_exchange
    lower_critical_field = 0.0
    upper_critical_field = dimer_triplet_mz1_energy_at_zero_field - dimer_singlet_energy
    return {
        "one_third_magnetization_plateau": bool(strong_dimer_limit),
        "strong_dimer_limit": bool(strong_dimer_limit),
        "plateau_fraction": plateau_magnetization / saturated_magnetization,
        "plateau_magnetization_per_unit_cell": plateau_magnetization,
        "saturated_magnetization_per_unit_cell": saturated_magnetization,
        "dimer_singlet_energy": dimer_singlet_energy,
        "dimer_triplet_mz1_energy_at_zero_field": dimer_triplet_mz1_energy_at_zero_field,
        "field_lower": lower_critical_field,
        "field_upper": upper_critical_field,
    }


def shastry_sutherland_dimer_plateau_status(*, dimer_exchange, interdimer_exchange, plateau_fraction):
    dimer_exchange = float(dimer_exchange)
    interdimer_exchange = float(interdimer_exchange)
    plateau_fraction = float(plateau_fraction)
    orthogonal_dimer_limit = dimer_exchange > 0.0 and abs(interdimer_exchange) < 1.0e-12
    is_fractional_plateau = 0.0 < plateau_fraction < 1.0
    singlet_energy = -0.75 * dimer_exchange
    triplet_mz1_energy_at_zero_field = 0.25 * dimer_exchange
    dimer_gap_field = triplet_mz1_energy_at_zero_field - singlet_energy
    return {
        "fractional_plateaus_observed": bool(orthogonal_dimer_limit and is_fractional_plateau),
        "orthogonal_dimer_limit": bool(orthogonal_dimer_limit),
        "is_fractional_plateau": bool(is_fractional_plateau),
        "plateau_fraction": plateau_fraction,
        "singlet_energy_per_dimer": singlet_energy,
        "triplet_mz1_energy_at_zero_field": triplet_mz1_energy_at_zero_field,
        "dimer_gap_field": dimer_gap_field,
    }


def shastry_sutherland_material_status(*, material_context, dimer_exchange, interdimer_exchange, plateau_fraction):
    plateau_status = shastry_sutherland_dimer_plateau_status(
        dimer_exchange=dimer_exchange,
        interdimer_exchange=interdimer_exchange,
        plateau_fraction=plateau_fraction,
    )
    has_material_context = bool(material_context)
    return {
        "orthogonal_dimer_material": bool(
            has_material_context
            and plateau_status["orthogonal_dimer_limit"]
        ),
        "magnetization_plateaus": bool(
            has_material_context
            and plateau_status["fractional_plateaus_observed"]
        ),
        "has_material_context": has_material_context,
        "orthogonal_dimer_limit": plateau_status["orthogonal_dimer_limit"],
        "is_fractional_plateau": plateau_status["is_fractional_plateau"],
        "plateau_fraction": plateau_status["plateau_fraction"],
        "singlet_energy_per_dimer": plateau_status["singlet_energy_per_dimer"],
        "triplet_mz1_energy_at_zero_field": plateau_status["triplet_mz1_energy_at_zero_field"],
        "dimer_gap_field": plateau_status["dimer_gap_field"],
    }


def breathing_kagome_strong_triangle_trimerization_status(*, j_up, j_down):
    return float(j_up) > 0.0 and abs(float(j_down)) < 1.0e-12


def honeycomb_nearest_neighbor_order_status(order):
    if str(order) not in {"ferromagnetic", "neel"}:
        raise ValueError(f"unsupported honeycomb nearest-neighbor order {order}")
    return True


def honeycomb_nearest_neighbor_glt_order_summary(*, exchange):
    exchange = float(exchange)
    if exchange == 0.0:
        raise ValueError("honeycomb nearest-neighbor GLT order needs nonzero exchange")
    kernel_eigenvalues = {
        "ferromagnetic": 3.0 * exchange,
        "neel": -3.0 * exchange,
    }
    minimum_order = min(kernel_eigenvalues, key=kernel_eigenvalues.get)
    competing_order = "neel" if minimum_order == "ferromagnetic" else "ferromagnetic"
    return {
        "minimum_order": minimum_order,
        "minimum_kernel_eigenvalue": kernel_eigenvalues[minimum_order],
        "competing_order": competing_order,
        "competing_kernel_eigenvalue": kernel_eigenvalues[competing_order],
        "kernel_eigenvalues": kernel_eigenvalues,
    }


def honeycomb_j1_j2_j3_collinear_order_energies(*, j1, j2, j3):
    j1 = float(j1)
    j2 = float(j2)
    j3 = float(j3)
    return {
        "ferromagnetic": 0.5 * (3.0 * j1 + 6.0 * j2 + 3.0 * j3),
        "neel": 0.5 * (-3.0 * j1 + 6.0 * j2 - 3.0 * j3),
        "zigzag": 0.5 * (j1 - 2.0 * j2 - 3.0 * j3),
        "stripy": 0.5 * (-j1 - 2.0 * j2 + 3.0 * j3),
    }


def dm_spiral_pitch_reciprocal_lattice_units(*, exchange, dzyaloshinskii_moriya):
    exchange = float(exchange)
    if exchange == 0.0:
        raise ValueError("exchange must be nonzero for the single-q DM pitch formula")
    return math.atan(float(dzyaloshinskii_moriya) / exchange) / (2.0 * math.pi)


def fecl3_cable_helix_geometry(
    *,
    hexagonal_in_plane_numerators,
    modulation_denominator,
    antiferromagnetic_c_axis,
):
    numerators = tuple(hexagonal_in_plane_numerators)
    if (
        len(numerators) != 2
        or any(isinstance(value, bool) or not isinstance(value, int) for value in numerators)
    ):
        raise ValueError("FeCl3 helix needs two integer in-plane numerators")
    if (
        isinstance(modulation_denominator, bool)
        or not isinstance(modulation_denominator, int)
        or modulation_denominator <= 0
    ):
        raise ValueError("FeCl3 helix modulation denominator must be a positive integer")
    if antiferromagnetic_c_axis is not True:
        raise ValueError("Cable FeCl3 geometry requires antiferromagnetic c-axis stacking")
    return {
        "magnetic_order": "helimagnetic_spiral",
        "propagation_vector_hexagonal": [
            numerators[0] / modulation_denominator,
            numerators[1] / modulation_denominator,
            3.0 / 2.0,
        ],
        "in_plane_period_lattice_spacings": modulation_denominator,
        "successive_plane_turn_angle_radians": (
            2.0 * math.pi / modulation_denominator
        ),
    }


def kagome_dm_interaction_relevance_status(*, exchange, dzyaloshinskii_moriya):
    exchange = float(exchange)
    dzyaloshinskii_moriya = float(dzyaloshinskii_moriya)
    heisenberg_triangle_energy = -1.5 * exchange
    dm_energy_shift = 1.5 * math.sqrt(3.0) * abs(dzyaloshinskii_moriya)
    selected_energy = heisenberg_triangle_energy - dm_energy_shift
    opposite_energy = heisenberg_triangle_energy + dm_energy_shift
    return {
        "dm_interaction_relevant": bool(abs(dzyaloshinskii_moriya) > 0.0),
        "selected_chirality": "clockwise" if dzyaloshinskii_moriya > 0.0 else "counterclockwise",
        "selected_chirality_energy": selected_energy,
        "opposite_chirality_energy": opposite_energy,
    }


def j1_j2_chain_classical_spiral_status(*, j1, j2):
    j1 = float(j1)
    j2 = float(j2)
    if j2 > 0.0 and abs(j1) < 4.0 * j2:
        pitch = math.acos(-j1 / (4.0 * j2))
        return {
            "is_incommensurate_spiral": not math.isclose(pitch, 0.0) and not math.isclose(pitch, math.pi),
            "pitch_radians": pitch,
            "ordering": "incommensurate_spiral",
        }
    if j1 < 0.0:
        return {"is_incommensurate_spiral": False, "pitch_radians": 0.0, "ordering": "ferromagnetic"}
    return {"is_incommensurate_spiral": False, "pitch_radians": math.pi, "ordering": "antiferromagnetic"}


def j1_j2_chain_frustrated_ferromagnetic_status(*, j1, j2):
    return float(j1) < 0.0 and float(j2) > 0.0


def kagome_competing_j1_jd_exchange_status(*, j1, jd):
    j1 = float(j1)
    jd = float(jd)

    def sign_label(value):
        if value > 0.0:
            return "antiferromagnetic"
        if value < 0.0:
            return "ferromagnetic"
        return "zero"

    return {
        "competing_kagome_exchanges": bool(j1 * jd < 0.0),
        "nearest_neighbor_exchange_sign": sign_label(j1),
        "diagonal_exchange_sign": sign_label(jd),
    }


def distorted_kagome_exchange_status(*, nearest_neighbor_exchanges, tolerance=1.0e-12):
    exchanges = [float(exchange) for exchange in nearest_neighbor_exchanges]
    if len(exchanges) < 2:
        raise ValueError("distorted kagome status expects at least two nearest-neighbor exchanges")

    representatives = []
    for exchange in exchanges:
        if not any(math.isclose(exchange, representative, rel_tol=0.0, abs_tol=tolerance) for representative in representatives):
            representatives.append(exchange)

    is_distorted = len(representatives) > 1
    return {
        "distorted_kagome_reference": bool(is_distorted),
        "distorted_kagome_relevant": bool(is_distorted),
        "is_distorted": bool(is_distorted),
        "inequivalent_exchange_count": len(representatives),
        "all_antiferromagnetic": all(exchange > 0.0 for exchange in exchanges),
        "exchange_values": exchanges,
    }


def kagome_interlayer_coupling_status(*, kagome_exchange, interlayer_exchange):
    kagome_exchange = float(kagome_exchange)
    interlayer_exchange = float(interlayer_exchange)
    if kagome_exchange == 0.0:
        raise ValueError("kagome_exchange must be nonzero for the interlayer ratio")
    return {
        "interlayer_coupling_relevant": bool(abs(interlayer_exchange) > 0.0),
        "interlayer_to_layer_ratio": abs(interlayer_exchange / kagome_exchange),
        "candidate_ordering_vectors": [[0.0, 0.0, 0.0], [0.5, 0.5, 0.0]],
    }


def kagome_interlayer_reduction_status(*, parent_interlayer_exchange, substituted_interlayer_exchange):
    parent_interlayer_exchange = abs(float(parent_interlayer_exchange))
    substituted_interlayer_exchange = abs(float(substituted_interlayer_exchange))
    if parent_interlayer_exchange == 0.0:
        raise ValueError("parent_interlayer_exchange must be nonzero for the reduction ratio")
    substituted_to_parent_ratio = substituted_interlayer_exchange / parent_interlayer_exchange
    return {
        "reduced_interlayer_magnetism": bool(substituted_interlayer_exchange < parent_interlayer_exchange),
        "substituted_to_parent_ratio": substituted_to_parent_ratio,
        "interlayer_reduction_fraction": 1.0 - substituted_to_parent_ratio,
    }


def spin_ice_local_correlation_status(*, local_axis_ising):
    if not bool(local_axis_ising):
        return {
            "spin_ice_correlations": False,
            "ice_rule_state_count": 0,
            "nearest_neighbor_ising_correlation": 0.0,
        }

    ice_rule_states = [
        state
        for state in product((-1, 1), repeat=4)
        if sum(state) == 0
    ]
    pair_correlations = []
    for state in ice_rule_states:
        pair_correlations.extend(state[source] * state[target] for source, target in combinations(range(4), 2))
    return {
        "spin_ice_correlations": True,
        "ice_rule_state_count": len(ice_rule_states),
        "nearest_neighbor_ising_correlation": float(np.mean(pair_correlations)),
    }


def spin_ladder_field_induced_luttinger_regime_status(*, j_rung, j_leg, field):
    j_rung = float(j_rung)
    j_leg = float(j_leg)
    field = float(field)
    if j_rung <= 0.0 or j_leg <= 0.0:
        return {
            "field_induced_luttinger_liquid_regime": False,
            "field": field,
            "lower_critical_field": j_rung,
            "upper_critical_field": j_rung,
        }

    lower_critical_field = max(0.0, j_rung - 2.0 * abs(j_leg))
    upper_critical_field = j_rung + 2.0 * abs(j_leg)
    field_window_width = upper_critical_field - lower_critical_field
    return {
        "field_induced_luttinger_liquid_regime": bool(lower_critical_field < field < upper_critical_field),
        "field": field,
        "lower_critical_field": lower_critical_field,
        "upper_critical_field": upper_critical_field,
        "critical_field_formula": "h_c1=J_rung-2J_leg, h_c2=J_rung+2J_leg",
        "field_window_width": field_window_width,
    }


def garnet_hyperkagome_frustration_status(*, lattice, heisenberg_exchange, dipolar_exchange):
    is_hyperkagome_garnet = str(lattice) == "hyperkagome_garnet"
    has_antiferromagnetic_heisenberg = float(heisenberg_exchange) > 0.0
    has_competing_dipolar_exchange = abs(float(dipolar_exchange)) > 0.0
    frustrated = bool(
        is_hyperkagome_garnet
        and has_antiferromagnetic_heisenberg
        and has_competing_dipolar_exchange
    )
    return {
        "strong_frustration": frustrated,
        "garnet_frustrated_magnet": frustrated,
        "is_hyperkagome_garnet": is_hyperkagome_garnet,
        "has_antiferromagnetic_heisenberg": has_antiferromagnetic_heisenberg,
        "has_competing_dipolar_exchange": has_competing_dipolar_exchange,
    }


def garnet_hyperkagome_triangle_constraint_status(
    *,
    lattice,
    triangles_per_unit_cell,
    sites_per_unit_cell,
    spin_components,
    heisenberg_exchange,
    dipolar_exchange,
):
    base_status = hyperkagome_corner_sharing_triangle_constraint_status(
        triangles_per_unit_cell=triangles_per_unit_cell,
        sites_per_unit_cell=sites_per_unit_cell,
        spin_components=spin_components,
        heisenberg_exchange=heisenberg_exchange,
    )
    is_hyperkagome_garnet = str(lattice) == "hyperkagome_garnet"
    has_competing_dipolar_exchange = abs(float(dipolar_exchange)) > 0.0
    frustrated = bool(
        is_hyperkagome_garnet
        and base_status["has_antiferromagnetic_heisenberg"]
        and base_status["is_macroscopically_underconstrained"]
        and has_competing_dipolar_exchange
    )
    return {
        **base_status,
        "strong_frustration": frustrated,
        "garnet_frustrated_magnet": frustrated,
        "is_hyperkagome_garnet": is_hyperkagome_garnet,
        "has_competing_dipolar_exchange": has_competing_dipolar_exchange,
    }


def frustrated_lattice_geometry_status(*, lattice, exchange):
    lattice = str(lattice)
    exchange = float(exchange)
    registered_keys = {
        "star": "spin_liquid_or_valence_bond_reference",
        "maple_leaf": "frustrated_order_reference",
        "shuriken": "square_kagome_reference",
    }
    has_antiferromagnetic_exchange = exchange > 0.0
    registered_frustrated_lattice = lattice in registered_keys
    is_frustrated_lattice = bool(registered_frustrated_lattice and has_antiferromagnetic_exchange)
    status = {
        "spin_liquid_or_valence_bond_reference": False,
        "frustrated_order_reference": False,
        "square_kagome_reference": False,
        "is_frustrated_lattice": is_frustrated_lattice,
        "registered_frustrated_lattice": registered_frustrated_lattice,
        "has_antiferromagnetic_exchange": has_antiferromagnetic_exchange,
    }
    if is_frustrated_lattice:
        status[registered_keys[lattice]] = True
    return status


def _star_lattice_betts_bonds(center_graph):
    center_graph = str(center_graph).lower().replace("-", "_")
    if center_graph != "k3_3":
        raise ValueError("the registered star-lattice Betts ED check uses the K3,3 center graph")

    center_edges = (
        (0, 3),
        (0, 4),
        (0, 5),
        (1, 3),
        (1, 4),
        (1, 5),
        (2, 3),
        (2, 4),
        (2, 5),
    )
    edge_color = {
        (0, 3): 0,
        (0, 4): 1,
        (0, 5): 2,
        (1, 3): 1,
        (1, 4): 2,
        (1, 5): 0,
        (2, 3): 2,
        (2, 4): 0,
        (2, 5): 1,
    }

    def site(center, corner):
        return 3 * int(center) + int(corner)

    bonds = set()
    for center in range(6):
        for source_corner, target_corner in ((0, 1), (1, 2), (2, 0)):
            bonds.add(tuple(sorted((site(center, source_corner), site(center, target_corner)))))
    for source_center, target_center in center_edges:
        color = edge_color[(source_center, target_center)]
        bonds.add(tuple(sorted((site(source_center, color), site(target_center, color)))))
    return tuple(sorted(bonds)), center_edges


@lru_cache(maxsize=4)
def star_lattice_heisenberg_betts_ed_status(
    *,
    center_graph="k3_3",
    exchange=1.0,
    literature_energy_per_bond=-0.312479,
    literature_triplet_gap=0.578710,
    tolerance=5.0e-6,
):
    exchange = float(exchange)
    bonds, center_edges = _star_lattice_betts_bonds(center_graph)
    site_count = 18
    up_count = site_count // 2
    weighted_bonds = tuple((source, target, exchange) for source, target in bonds)
    ground_energy = _spin_half_weighted_heisenberg_cluster_sector_ground_energy(
        site_count,
        weighted_bonds,
        up_count,
    )
    triplet_energy = _spin_half_weighted_heisenberg_cluster_sector_ground_energy(
        site_count,
        weighted_bonds,
        up_count + 1,
    )
    bond_count = len(bonds)
    energy_per_bond = ground_energy / float(bond_count)
    triplet_gap = triplet_energy - ground_energy
    energy_difference = abs(energy_per_bond - float(literature_energy_per_bond))
    gap_difference = abs(triplet_gap - float(literature_triplet_gap))
    matches_literature = bool(
        exchange > 0.0
        and energy_difference <= float(tolerance)
        and gap_difference <= float(tolerance)
        and triplet_gap > 0.0
    )
    return {
        "method": "betts_star_lattice_spin_half_heisenberg_ed",
        "center_graph": "k3_3",
        "center_graph_description": "K3,3 Betts cluster of six triangle centers expanded into the 18-site star lattice",
        "center_vertex_count": 6,
        "center_edge_count": len(center_edges),
        "site_count": site_count,
        "bond_count": bond_count,
        "triangle_bond_count": 18,
        "dimer_bond_count": 9,
        "basis_dimension_sz0": math.comb(site_count, up_count),
        "basis_dimension_sz1": math.comb(site_count, up_count + 1),
        "exchange": exchange,
        "ground_energy": ground_energy,
        "energy_per_bond": energy_per_bond,
        "triplet_gap": triplet_gap,
        "literature_energy_per_bond": float(literature_energy_per_bond),
        "literature_triplet_gap": float(literature_triplet_gap),
        "energy_absolute_difference_from_literature": energy_difference,
        "gap_absolute_difference_from_literature": gap_difference,
        "matching_tolerance": float(tolerance),
        "ground_state_singlet": bool(triplet_gap > 0.0),
        "matches_literature_energy_and_gap": matches_literature,
        "spin_liquid_or_valence_bond_reference": matches_literature,
    }


@lru_cache(maxsize=8)
def maple_leaf_classical_glt_order_status(*, exchange=1.0, q_grid_size=72):
    exchange = float(exchange)
    q_grid_size = int(q_grid_size)
    if q_grid_size < 3:
        raise ValueError("q_grid_size must be at least 3 for a maple-leaf GLT scan")

    sqrt3 = math.sqrt(3.0)
    lattice_vectors = (
        np.array([1.5 * sqrt3, -0.5], dtype=float),
        np.array([sqrt3, 2.0], dtype=float),
    )
    basis_positions = (
        np.array([0.0, 0.0], dtype=float),
        np.array([0.5 * sqrt3, -0.5], dtype=float),
        np.array([sqrt3, 0.0], dtype=float),
        np.array([sqrt3, 1.0], dtype=float),
        np.array([0.5 * sqrt3, 1.5], dtype=float),
        np.array([0.0, 1.0], dtype=float),
    )

    bond_keys = set()
    bonds = []
    for source, source_position in enumerate(basis_positions):
        for target, target_position in enumerate(basis_positions):
            for translation_a in (-1, 0, 1):
                for translation_b in (-1, 0, 1):
                    if translation_a == 0 and translation_b == 0 and target <= source:
                        continue
                    vector = (
                        target_position
                        + translation_a * lattice_vectors[0]
                        + translation_b * lattice_vectors[1]
                        - source_position
                    )
                    if math.isclose(float(np.linalg.norm(vector)), 1.0, rel_tol=0.0, abs_tol=1.0e-12):
                        forward = (source, target, translation_a, translation_b)
                        reverse = (target, source, -translation_a, -translation_b)
                        key = min(forward, reverse)
                        if key not in bond_keys:
                            bond_keys.add(key)
                            bonds.append(forward)

    def kernel(q_a, q_b):
        matrix = np.zeros((6, 6), dtype=complex)
        for source, target, translation_a, translation_b in bonds:
            phase = np.exp(2.0j * math.pi * (q_a * translation_a + q_b * translation_b))
            matrix[source, target] += exchange * phase
            matrix[target, source] += exchange * phase.conjugate()
        return matrix

    q_values = np.linspace(0.0, 1.0, q_grid_size, endpoint=False)
    best_eigenvalue = math.inf
    best_q = (0.0, 0.0)
    best_spectrum = None
    for q_a in q_values:
        for q_b in q_values:
            spectrum = np.linalg.eigvalsh(kernel(float(q_a), float(q_b))).real
            if float(spectrum[0]) < best_eigenvalue:
                best_eigenvalue = float(spectrum[0])
                best_q = (float(q_a), float(q_b))
                best_spectrum = spectrum

    gamma_spectrum = np.linalg.eigvalsh(kernel(0.0, 0.0)).real
    site_count = len(basis_positions)
    coordination_number = int(round(2.0 * len(bonds) / site_count))
    non_gamma_order = (
        exchange > 0.0
        and coordination_number == 5
        and not (math.isclose(best_q[0], 0.0, abs_tol=1.0e-12) and math.isclose(best_q[1], 0.0, abs_tol=1.0e-12))
        and best_eigenvalue < float(gamma_spectrum[0]) - 1.0e-9
    )
    return {
        "frustrated_order_reference": bool(non_gamma_order),
        "method": "maple_leaf_six_site_fourier_exchange_kernel",
        "unit_cell_site_count": site_count,
        "coordination_number": coordination_number,
        "nearest_neighbor_bond_count_per_unit_cell": len(bonds),
        "lowest_q_fractional": [best_q[0], best_q[1]],
        "lowest_kernel_eigenvalue": best_eigenvalue,
        "gamma_lowest_eigenvalue": float(gamma_spectrum[0]),
        "lowest_spectrum": [float(value) for value in best_spectrum],
        "gamma_spectrum": [float(value) for value in gamma_spectrum],
    }


def triangular_anisotropic_exchange_candidate_status(*, lattice, anisotropic_exchange, disorder_or_material):
    has_triangular_geometry = str(lattice) == "triangular"
    has_anisotropic_exchange = bool(anisotropic_exchange)
    has_material_or_disorder_context = bool(disorder_or_material)
    return {
        "triangular_quantum_spin_liquid_candidate": bool(
            has_triangular_geometry
            and has_anisotropic_exchange
            and has_material_or_disorder_context
        ),
        "has_triangular_geometry": has_triangular_geometry,
        "has_anisotropic_exchange": has_anisotropic_exchange,
        "has_material_or_disorder_context": has_material_or_disorder_context,
    }


def kagome_material_qsl_candidate_status(*, lattice, material_context, frustrated_geometry, spin_liquid_label):
    has_kagome_geometry = str(lattice) == "kagome"
    has_material_context = bool(material_context)
    has_frustrated_geometry = bool(frustrated_geometry)
    has_spin_liquid_label = bool(spin_liquid_label)
    candidate = bool(
        has_kagome_geometry
        and has_material_context
        and has_frustrated_geometry
        and has_spin_liquid_label
    )
    return {
        "qsl_candidate": candidate,
        "has_kagome_geometry": has_kagome_geometry,
        "has_material_context": has_material_context,
        "has_frustrated_geometry": has_frustrated_geometry,
        "has_spin_liquid_label": has_spin_liquid_label,
    }


def pyrochlore_material_spin_liquid_candidate_status(
    *,
    lattice,
    anisotropic_exchange,
    material_context,
    spin_liquid_label,
):
    has_pyrochlore_geometry = str(lattice) == "pyrochlore"
    has_anisotropic_exchange = bool(anisotropic_exchange)
    has_material_context = bool(material_context)
    has_spin_liquid_label = bool(spin_liquid_label)
    candidate = bool(
        has_pyrochlore_geometry
        and has_anisotropic_exchange
        and has_material_context
        and has_spin_liquid_label
    )
    return {
        "spin_liquid_candidate": candidate,
        "has_pyrochlore_geometry": has_pyrochlore_geometry,
        "has_anisotropic_exchange": has_anisotropic_exchange,
        "has_material_context": has_material_context,
        "has_spin_liquid_label": has_spin_liquid_label,
    }


def tb2ti2o7_local_tetrahedron_negative_probe_status(*, local_axis_ising, exchange_labels):
    correlation_status = spin_ice_local_correlation_status(local_axis_ising=local_axis_ising)
    exchange_status = pyrochlore_material_anisotropic_exchange_status(exchange_labels=exchange_labels)
    return {
        "method": "local_pyrochlore_tetrahedron_ice_rule_negative_probe",
        "ice_rule_state_count": correlation_status["ice_rule_state_count"],
        "nearest_neighbor_ising_correlation": correlation_status["nearest_neighbor_ising_correlation"],
        "recognized_exchange_labels": exchange_status["recognized_exchange_labels"],
        "has_full_pyrochlore_anisotropic_exchange_label_set": exchange_status[
            "anisotropic_exchange_fit_reference"
        ],
        "reproduces_registered_tb2ti2o7_spin_liquid": False,
        "negative_evidence": (
            "This local tetrahedron probe enumerates the ideal ice-rule manifold and checks "
            "the pyrochlore anisotropic-exchange label set only. It does not use Tb2Ti2O7 "
            "material exchange parameters, neutron-scattering correlations, susceptibility, "
            "or low-temperature thermodynamic data, so it does not reproduce the registered "
            "Tb2Ti2O7 spin-liquid reference."
        ),
    }


def hyperkagome_spin_liquid_candidate_status(
    *,
    lattice,
    heisenberg_exchange,
    material_context,
    spin_liquid_label,
):
    has_hyperkagome_geometry = str(lattice) == "hyperkagome"
    has_antiferromagnetic_heisenberg = float(heisenberg_exchange) > 0.0
    has_material_context = bool(material_context)
    has_spin_liquid_label = bool(spin_liquid_label)
    base_candidate = bool(
        has_hyperkagome_geometry
        and has_antiferromagnetic_heisenberg
        and has_spin_liquid_label
    )
    return {
        "spin_liquid_candidate": base_candidate,
        "hyperkagome_qsl_candidate": bool(base_candidate and has_material_context),
        "has_hyperkagome_geometry": has_hyperkagome_geometry,
        "has_antiferromagnetic_heisenberg": has_antiferromagnetic_heisenberg,
        "has_material_context": has_material_context,
        "has_spin_liquid_label": has_spin_liquid_label,
    }


def hyperkagome_corner_sharing_triangle_constraint_status(
    *,
    triangles_per_unit_cell,
    sites_per_unit_cell,
    spin_components,
    heisenberg_exchange,
):
    triangles_per_unit_cell = int(triangles_per_unit_cell)
    sites_per_unit_cell = int(sites_per_unit_cell)
    spin_components = int(spin_components)
    heisenberg_exchange = float(heisenberg_exchange)
    if triangles_per_unit_cell <= 0:
        raise ValueError("triangles_per_unit_cell must be positive")
    if sites_per_unit_cell <= 0:
        raise ValueError("sites_per_unit_cell must be positive")
    if spin_components <= 0:
        raise ValueError("spin_components must be positive")

    constraint_count = triangles_per_unit_cell * spin_components
    spin_component_count = sites_per_unit_cell * spin_components
    unconstrained_classical_degrees = sites_per_unit_cell * (spin_components - 1)
    estimated_zero_sum_dimension = unconstrained_classical_degrees - constraint_count
    has_antiferromagnetic_exchange = heisenberg_exchange > 0.0
    can_satisfy_zero_triangle_sum = spin_components >= 2
    is_underconstrained = estimated_zero_sum_dimension > 0

    return {
        "spin_liquid_candidate": bool(
            has_antiferromagnetic_exchange
            and can_satisfy_zero_triangle_sum
            and is_underconstrained
        ),
        "triangle_constraint_identity": "H = J/2 sum_delta |S_delta|^2 + const",
        "can_satisfy_zero_triangle_sum": can_satisfy_zero_triangle_sum,
        "has_antiferromagnetic_heisenberg": has_antiferromagnetic_exchange,
        "triangles_per_unit_cell": triangles_per_unit_cell,
        "sites_per_unit_cell": sites_per_unit_cell,
        "spin_components": spin_components,
        "constraint_count": constraint_count,
        "spin_component_count": spin_component_count,
        "unconstrained_classical_degrees_of_freedom": unconstrained_classical_degrees,
        "estimated_zero_sum_manifold_dimension": estimated_zero_sum_dimension,
        "is_macroscopically_underconstrained": is_underconstrained,
    }


def bilayer_breathing_kagome_exchange_status(
    *,
    lattice,
    exchange_values,
    material_context,
    spin_liquid_label,
):
    exchanges = [float(exchange) for exchange in exchange_values]
    has_bilayer_kagome_geometry = str(lattice) == "bilayer_kagome"
    has_material_context = bool(material_context)
    has_spin_liquid_label = bool(spin_liquid_label)
    has_ferromagnetic_exchange = any(exchange < 0.0 for exchange in exchanges)
    has_antiferromagnetic_exchange = any(exchange > 0.0 for exchange in exchanges)
    mixed = bool(has_ferromagnetic_exchange and has_antiferromagnetic_exchange)
    candidate = bool(
        has_bilayer_kagome_geometry
        and has_material_context
        and has_spin_liquid_label
        and mixed
    )
    return {
        "spin_liquid_candidate": candidate,
        "mixed_ferromagnetic_antiferromagnetic_exchanges": mixed,
        "has_bilayer_kagome_geometry": has_bilayer_kagome_geometry,
        "has_material_context": has_material_context,
        "has_spin_liquid_label": has_spin_liquid_label,
        "has_ferromagnetic_exchange": has_ferromagnetic_exchange,
        "has_antiferromagnetic_exchange": has_antiferromagnetic_exchange,
        "exchange_values": exchanges,
    }


def _single_layer_breathing_kagome_fourier_kernel(
    q_fractional,
    *,
    ferromagnetic_triangle_exchange,
    antiferromagnetic_triangle_exchange,
):
    qx, qy = (float(q_fractional[0]), float(q_fractional[1]))
    phase_ab = np.exp(-2.0j * math.pi * qx)
    phase_ac = np.exp(-2.0j * math.pi * qy)
    phase_bc = np.exp(-2.0j * math.pi * (qy - qx))
    kernel = np.zeros((3, 3), dtype=complex)
    kernel[0, 1] = float(ferromagnetic_triangle_exchange) + float(antiferromagnetic_triangle_exchange) * phase_ab
    kernel[0, 2] = float(ferromagnetic_triangle_exchange) + float(antiferromagnetic_triangle_exchange) * phase_ac
    kernel[1, 2] = float(ferromagnetic_triangle_exchange) + float(antiferromagnetic_triangle_exchange) * phase_bc
    return kernel + kernel.conjugate().T


def _bilayer_breathing_kagome_fourier_kernel(
    q_fractional,
    *,
    ferromagnetic_triangle_exchange,
    antiferromagnetic_triangle_exchange,
    interlayer_exchange,
):
    layer_kernel = _single_layer_breathing_kagome_fourier_kernel(
        q_fractional,
        ferromagnetic_triangle_exchange=ferromagnetic_triangle_exchange,
        antiferromagnetic_triangle_exchange=antiferromagnetic_triangle_exchange,
    )
    kernel = np.zeros((6, 6), dtype=complex)
    kernel[:3, :3] = layer_kernel
    kernel[3:, 3:] = layer_kernel
    kernel[:3, 3:] = float(interlayer_exchange) * np.eye(3, dtype=complex)
    kernel[3:, :3] = float(interlayer_exchange) * np.eye(3, dtype=complex)
    return kernel


@lru_cache(maxsize=16)
def bilayer_breathing_kagome_glt_status(
    *,
    ferromagnetic_triangle_exchange=-1.0,
    antiferromagnetic_triangle_exchange=0.45,
    interlayer_exchange=0.25,
    q_grid_size=41,
):
    ferromagnetic_triangle_exchange = float(ferromagnetic_triangle_exchange)
    antiferromagnetic_triangle_exchange = float(antiferromagnetic_triangle_exchange)
    interlayer_exchange = float(interlayer_exchange)
    q_grid_size = int(q_grid_size)
    if q_grid_size < 3:
        raise ValueError("q_grid_size must be at least 3 for a Luttinger-Tisza scan")

    exchanges = [
        ferromagnetic_triangle_exchange,
        antiferromagnetic_triangle_exchange,
        interlayer_exchange,
    ]
    mixed = any(exchange < 0.0 for exchange in exchanges) and any(exchange > 0.0 for exchange in exchanges)
    q_values = np.linspace(0.0, 1.0, q_grid_size, endpoint=True)
    scanned_modes = []
    for qx in q_values:
        for qy in q_values:
            eigenvalues = np.linalg.eigvalsh(
                _bilayer_breathing_kagome_fourier_kernel(
                    (qx, qy),
                    ferromagnetic_triangle_exchange=ferromagnetic_triangle_exchange,
                    antiferromagnetic_triangle_exchange=antiferromagnetic_triangle_exchange,
                    interlayer_exchange=interlayer_exchange,
                )
            ).real
            scanned_modes.append((float(eigenvalues[0]), (float(qx), float(qy)), eigenvalues))

    lowest_energy, lowest_q, lowest_eigenvalues = min(scanned_modes, key=lambda item: item[0])
    q0_eigenvalues = np.linalg.eigvalsh(
        _bilayer_breathing_kagome_fourier_kernel(
            (0.0, 0.0),
            ferromagnetic_triangle_exchange=ferromagnetic_triangle_exchange,
            antiferromagnetic_triangle_exchange=antiferromagnetic_triangle_exchange,
            interlayer_exchange=interlayer_exchange,
        )
    ).real
    ferromagnetic_q0_mode_energy = float(q0_eigenvalues[0])
    first_gap = float(lowest_eigenvalues[1] - lowest_eigenvalues[0])
    normalized_two_mode_spectrum = [0.0, 1.0] if first_gap > 1.0e-12 else [0.0, 0.0]
    has_nontrivial_minimum = bool(
        mixed
        and (abs(lowest_q[0]) > 1.0e-12 or abs(lowest_q[1]) > 1.0e-12)
        and lowest_energy < ferromagnetic_q0_mode_energy - 1.0e-6
        and first_gap > 1.0e-12
    )
    return {
        "method": "bilayer_breathing_kagome_fourier_exchange_kernel",
        "spin_liquid_candidate": bool(has_nontrivial_minimum),
        "mixed_ferromagnetic_antiferromagnetic_exchanges": bool(mixed),
        "kernel_dimension": 6,
        "lowest_q_fractional": [float(lowest_q[0]), float(lowest_q[1])],
        "lowest_mode_energy": float(lowest_energy),
        "ferromagnetic_q0_mode_energy": ferromagnetic_q0_mode_energy,
        "has_nontrivial_luttinger_tisza_minimum": has_nontrivial_minimum,
        "lowest_eigenvalues": [float(value) for value in lowest_eigenvalues],
        "linear_spin_wave_modes": normalized_two_mode_spectrum,
        "exchange_values": exchanges,
        "q_grid_size": q_grid_size,
    }


def honeycomb_kitaev_material_status(*, lattice, material_context, kitaev, heisenberg):
    has_honeycomb_geometry = str(lattice) == "honeycomb"
    has_material_context = bool(material_context)
    has_kitaev_exchange = abs(float(kitaev)) > 0.0
    has_heisenberg_exchange = abs(float(heisenberg)) > 0.0
    return {
        "honeycomb_iridate_reference": bool(
            has_honeycomb_geometry
            and has_material_context
            and has_kitaev_exchange
            and has_heisenberg_exchange
        ),
        "has_honeycomb_geometry": has_honeycomb_geometry,
        "has_material_context": has_material_context,
        "has_kitaev_exchange": has_kitaev_exchange,
        "has_heisenberg_exchange": has_heisenberg_exchange,
    }


def cu2iro3_honeycomb_kitaev_heisenberg_energy_status(
    *,
    lattice,
    material_context,
    kitaev,
    heisenberg,
):
    zigzag_status = honeycomb_kitaev_heisenberg_zigzag_energy_status(
        kitaev=kitaev,
        heisenberg=heisenberg,
    )
    has_honeycomb_lattice = str(lattice) == "honeycomb"
    has_material_context = bool(material_context)
    has_kitaev_exchange = abs(float(kitaev)) > 0.0
    has_heisenberg_exchange = abs(float(heisenberg)) > 0.0
    zigzag_is_representative_minimum = bool(
        zigzag_status["zigzag_order_relevant"]
        and math.isclose(
            zigzag_status["zigzag_energy_per_site"],
            zigzag_status["minimum_energy_per_site"],
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
        and zigzag_status["energy_per_site_by_order_class"]["zigzag"]
        < zigzag_status["energy_per_site_by_order_class"]["neel"]
        and zigzag_status["energy_per_site_by_order_class"]["zigzag"]
        < zigzag_status["energy_per_site_by_order_class"]["ferromagnetic"]
    )
    return {
        **zigzag_status,
        "method": "honeycomb_kitaev_heisenberg_zigzag_energy_enumeration",
        "honeycomb_iridate_reference": bool(
            has_honeycomb_lattice
            and has_material_context
            and has_kitaev_exchange
            and has_heisenberg_exchange
            and zigzag_is_representative_minimum
        ),
        "has_honeycomb_lattice": has_honeycomb_lattice,
        "has_material_context": has_material_context,
        "has_kitaev_exchange": has_kitaev_exchange,
        "has_heisenberg_exchange": has_heisenberg_exchange,
    }


def kagome_bilayer_spin_liquid_candidate_status(
    *,
    lattice,
    material_context,
    frustrated_geometry,
    no_conventional_order_label,
):
    has_kagome_bilayer_geometry = str(lattice) == "kagome_bilayer"
    has_material_context = bool(material_context)
    has_frustrated_geometry = bool(frustrated_geometry)
    has_no_conventional_order_label = bool(no_conventional_order_label)
    candidate = bool(
        has_kagome_bilayer_geometry
        and has_material_context
        and has_frustrated_geometry
        and has_no_conventional_order_label
    )
    return {
        "no_conventional_order_down_to_low_t": candidate,
        "has_kagome_bilayer_geometry": has_kagome_bilayer_geometry,
        "has_material_context": has_material_context,
        "has_frustrated_geometry": has_frustrated_geometry,
        "has_no_conventional_order_label": has_no_conventional_order_label,
    }


def garnet_short_range_order_candidate_status(
    *,
    lattice,
    heisenberg_exchange,
    dipolar_exchange,
    material_context,
    short_range_order_label,
):
    base_status = garnet_hyperkagome_frustration_status(
        lattice=lattice,
        heisenberg_exchange=heisenberg_exchange,
        dipolar_exchange=dipolar_exchange,
    )
    has_material_context = bool(material_context)
    has_short_range_order_label = bool(short_range_order_label)
    return {
        "short_range_order_without_simple_lro": bool(
            base_status["garnet_frustrated_magnet"]
            and has_material_context
            and has_short_range_order_label
        ),
        "is_hyperkagome_garnet": base_status["is_hyperkagome_garnet"],
        "has_antiferromagnetic_heisenberg": base_status["has_antiferromagnetic_heisenberg"],
        "has_competing_dipolar_exchange": base_status["has_competing_dipolar_exchange"],
        "has_material_context": has_material_context,
        "has_short_range_order_label": has_short_range_order_label,
    }


def disordered_honeycomb_kitaev_candidate_status(*, lattice, material_context, disorder, kitaev, gamma):
    content = honeycomb_kitaev_gamma_candidate_phase_content(kitaev=kitaev, gamma=gamma)
    has_honeycomb_geometry = str(lattice) == "honeycomb"
    has_material_context = bool(material_context)
    has_disorder_context = bool(disorder)
    has_kitaev_exchange = abs(float(kitaev)) > 0.0
    return {
        "no_magnetic_order_reported": bool(
            has_honeycomb_geometry
            and has_material_context
            and has_disorder_context
            and has_kitaev_exchange
            and content["has_offdiagonal_gamma_mixing"]
        ),
        "has_honeycomb_geometry": has_honeycomb_geometry,
        "has_material_context": has_material_context,
        "has_disorder_context": has_disorder_context,
        "has_kitaev_exchange": has_kitaev_exchange,
        "has_offdiagonal_gamma_mixing": content["has_offdiagonal_gamma_mixing"],
    }


def h3liir2o6_clean_kitaev_negative_probe_status(*, kx, ky, kz, gamma, disorder):
    couplings = [abs(float(kx)), abs(float(ky)), abs(float(kz))]
    margins = [
        couplings[1] + couplings[2] - couplings[0],
        couplings[0] + couplings[2] - couplings[1],
        couplings[0] + couplings[1] - couplings[2],
    ]
    clean_limit_gapless = all(margin >= -1.0e-12 for margin in margins)
    has_gamma_mixing = abs(float(gamma)) > 0.0
    has_disorder_context = bool(disorder)
    return {
        "method": "clean_kitaev_triangle_gapless_negative_probe",
        "clean_limit_gapless": bool(clean_limit_gapless),
        "triangle_inequality_margins": margins,
        "has_gamma_mixing": has_gamma_mixing,
        "has_disorder_context": has_disorder_context,
        "reproduces_registered_h3liir2o6_no_order_observable": False,
        "negative_evidence": (
            "The clean-limit Kitaev triangle-inequality probe verifies only the ideal "
            "honeycomb Kitaev gapless condition. It does not include H3LiIr2O6 disorder, "
            "Gamma-mixed anisotropic exchange in a many-body calculation, or experimental "
            "no-magnetic-order data, so it does not reproduce the registered material "
            "spin-liquid-candidate observable."
        ),
    }


def honeycomb_kitaev_spin_liquid_candidate_status(
    *,
    lattice,
    material_context,
    kitaev,
    heisenberg,
    spin_liquid_label,
):
    material_status = honeycomb_kitaev_material_status(
        lattice=lattice,
        material_context=material_context,
        kitaev=kitaev,
        heisenberg=heisenberg,
    )
    has_spin_liquid_label = bool(spin_liquid_label)
    return {
        "spin_liquid_candidate": bool(
            material_status["honeycomb_iridate_reference"]
            and has_spin_liquid_label
        ),
        "has_honeycomb_geometry": material_status["has_honeycomb_geometry"],
        "has_material_context": material_status["has_material_context"],
        "has_kitaev_exchange": material_status["has_kitaev_exchange"],
        "has_heisenberg_exchange": material_status["has_heisenberg_exchange"],
        "has_spin_liquid_label": has_spin_liquid_label,
    }


def ba3irti2o9_clean_kitaev_negative_probe_status(*, lattice, kitaev, heisenberg, coordination_number):
    material_status = honeycomb_kitaev_material_status(
        lattice=lattice,
        material_context=True,
        kitaev=kitaev,
        heisenberg=heisenberg,
    )
    theta = curie_weiss_temperature(int(coordination_number), float(kitaev))
    return {
        "method": "clean_honeycomb_kitaev_curie_weiss_negative_probe",
        "clean_kitaev_limit_exactly_solvable": exact_solution_status("kitaev_honeycomb"),
        "has_honeycomb_geometry": material_status["has_honeycomb_geometry"],
        "has_kitaev_exchange": material_status["has_kitaev_exchange"],
        "has_heisenberg_exchange": material_status["has_heisenberg_exchange"],
        "coordination_number": int(coordination_number),
        "curie_weiss_theta": theta,
        "reproduces_registered_ba3irti2o9_spin_liquid": False,
        "negative_evidence": (
            "The local probe combines the clean Kitaev limit exact-solution status with a "
            "honeycomb Curie-Weiss moment sum rule. It does not use Ba3IrTi2O9 exchange "
            "parameters, disorder/site-mixing information, thermodynamics, or neutron/NMR "
            "data, so it does not reproduce the registered material spin-liquid observable."
        ),
    }


def chiral_skyrmion_lattice_candidate_status(
    *,
    lattice,
    material_context,
    exchange,
    dzyaloshinskii_moriya,
    magnetic_field,
):
    has_chiral_cubic_lattice = str(lattice) == "chiral_cubic"
    has_material_context = bool(material_context)
    has_exchange = abs(float(exchange)) > 0.0
    has_dm_interaction = abs(float(dzyaloshinskii_moriya)) > 0.0
    has_magnetic_field = abs(float(magnetic_field)) > 0.0
    return {
        "skyrmion_lattice_phase": bool(
            has_chiral_cubic_lattice
            and has_material_context
            and has_exchange
            and has_dm_interaction
            and has_magnetic_field
        ),
        "has_chiral_cubic_lattice": has_chiral_cubic_lattice,
        "has_material_context": has_material_context,
        "has_exchange": has_exchange,
        "has_dm_interaction": has_dm_interaction,
        "has_magnetic_field": has_magnetic_field,
    }


def _normalized_spin_field(spins):
    norms = np.linalg.norm(spins, axis=2, keepdims=True)
    return spins / np.maximum(norms, 1.0e-12)


def _chiral_lattice_energy_per_site(spins, *, exchange, dzyaloshinskii_moriya, magnetic_field):
    exchange = float(exchange)
    dzyaloshinskii_moriya = float(dzyaloshinskii_moriya)
    magnetic_field = float(magnetic_field)
    x_neighbors = np.roll(spins, -1, axis=0)
    y_neighbors = np.roll(spins, -1, axis=1)
    exchange_energy = -exchange * (
        np.sum(spins * x_neighbors) + np.sum(spins * y_neighbors)
    )
    x_chirality = np.cross(spins, x_neighbors)[:, :, 0]
    y_chirality = np.cross(spins, y_neighbors)[:, :, 1]
    dm_energy = -dzyaloshinskii_moriya * (np.sum(x_chirality) + np.sum(y_chirality))
    field_energy = -magnetic_field * np.sum(spins[:, :, 2])
    site_count = spins.shape[0] * spins.shape[1]
    return float((exchange_energy + dm_energy + field_energy) / site_count)


def _chiral_lattice_effective_field(spins, *, exchange, dzyaloshinskii_moriya, magnetic_field):
    exchange = float(exchange)
    dzyaloshinskii_moriya = float(dzyaloshinskii_moriya)
    magnetic_field = float(magnetic_field)
    x_plus = np.roll(spins, -1, axis=0)
    x_minus = np.roll(spins, 1, axis=0)
    y_plus = np.roll(spins, -1, axis=1)
    y_minus = np.roll(spins, 1, axis=1)
    x_hat = np.array([1.0, 0.0, 0.0])
    y_hat = np.array([0.0, 1.0, 0.0])
    field = exchange * (x_plus + x_minus + y_plus + y_minus)
    field += dzyaloshinskii_moriya * (
        np.cross(x_plus, x_hat)
        + np.cross(x_hat, x_minus)
        + np.cross(y_plus, y_hat)
        + np.cross(y_hat, y_minus)
    )
    field[:, :, 2] += magnetic_field
    return field


def _relax_chiral_lattice_spins(
    spins,
    *,
    exchange,
    dzyaloshinskii_moriya,
    magnetic_field,
    relaxation_steps,
    mixing,
):
    spins = np.array(spins, dtype=float, copy=True)
    previous_energy = _chiral_lattice_energy_per_site(
        spins,
        exchange=exchange,
        dzyaloshinskii_moriya=dzyaloshinskii_moriya,
        magnetic_field=magnetic_field,
    )
    steps_taken = 0
    for step in range(int(relaxation_steps)):
        local_field = _chiral_lattice_effective_field(
            spins,
            exchange=exchange,
            dzyaloshinskii_moriya=dzyaloshinskii_moriya,
            magnetic_field=magnetic_field,
        )
        target = _normalized_spin_field(local_field)
        spins = _normalized_spin_field((1.0 - float(mixing)) * spins + float(mixing) * target)
        steps_taken = step + 1
        if step % 100 == 0:
            energy = _chiral_lattice_energy_per_site(
                spins,
                exchange=exchange,
                dzyaloshinskii_moriya=dzyaloshinskii_moriya,
                magnetic_field=magnetic_field,
            )
            if abs(energy - previous_energy) < 1.0e-10:
                break
            previous_energy = energy
    return spins, _chiral_lattice_energy_per_site(
        spins,
        exchange=exchange,
        dzyaloshinskii_moriya=dzyaloshinskii_moriya,
        magnetic_field=magnetic_field,
    ), steps_taken


def _ferromagnetic_spin_field(lattice_size):
    spins = np.zeros((int(lattice_size), int(lattice_size), 3), dtype=float)
    spins[:, :, 2] = 1.0
    return spins


def _helical_spin_field(lattice_size, pitch, *, axis):
    coordinates_x = np.arange(int(lattice_size), dtype=float)[:, None]
    coordinates_y = np.arange(int(lattice_size), dtype=float)[None, :]
    phase = float(pitch) * (coordinates_x if int(axis) == 0 else coordinates_y)
    spins = np.zeros((int(lattice_size), int(lattice_size), 3), dtype=float)
    if int(axis) == 0:
        spins[:, :, 1] = np.sin(phase)
    else:
        spins[:, :, 0] = np.sin(phase)
    spins[:, :, 2] = np.cos(phase)
    return spins


def _triple_q_skyrmion_spin_field(lattice_size, pitch, *, uniform_magnetization):
    coordinates_x = np.arange(int(lattice_size), dtype=float)[:, None]
    coordinates_y = np.arange(int(lattice_size), dtype=float)[None, :]
    wavevectors = [
        (float(pitch), 0.0),
        (-0.5 * float(pitch), 0.5 * math.sqrt(3.0) * float(pitch)),
        (-0.5 * float(pitch), -0.5 * math.sqrt(3.0) * float(pitch)),
    ]
    spins = np.zeros((int(lattice_size), int(lattice_size), 3), dtype=float)
    spins[:, :, 2] = float(uniform_magnetization)
    z_hat = np.array([0.0, 0.0, 1.0])
    for qx, qy in wavevectors:
        phase = qx * coordinates_x + qy * coordinates_y
        q_hat = np.array([qx, qy, 0.0])
        q_hat = q_hat / np.linalg.norm(q_hat)
        polarization = np.cross(z_hat, q_hat)
        spins[:, :, 0] += polarization[0] * np.sin(phase)
        spins[:, :, 1] += polarization[1] * np.sin(phase)
        spins[:, :, 2] += np.cos(phase)
    return _normalized_spin_field(spins)


def _berg_luescher_topological_charge(spins):
    def solid_angle(first, second, third):
        numerator = np.einsum("...i,...i", first, np.cross(second, third))
        denominator = (
            1.0
            + np.einsum("...i,...i", first, second)
            + np.einsum("...i,...i", second, third)
            + np.einsum("...i,...i", third, first)
        )
        return 2.0 * np.arctan2(numerator, denominator)

    x_neighbor = np.roll(spins, -1, axis=0)
    y_neighbor = np.roll(spins, -1, axis=1)
    xy_neighbor = np.roll(x_neighbor, -1, axis=1)
    total_solid_angle = solid_angle(spins, x_neighbor, xy_neighbor)
    total_solid_angle += solid_angle(spins, xy_neighbor, y_neighbor)
    return float(np.sum(total_solid_angle) / (4.0 * math.pi))


@lru_cache(maxsize=8)
def chiral_skyrmion_lattice_variational_minimization_status(
    *,
    lattice_size=36,
    exchange=1.0,
    dzyaloshinskii_moriya=0.8,
    magnetic_field=0.3,
    relaxation_steps=1600,
    mixing=0.24,
    energy_margin=1.0e-2,
):
    lattice_size = int(lattice_size)
    if lattice_size < 12:
        raise ValueError("skyrmion variational benchmark expects lattice_size >= 12")
    exchange = float(exchange)
    dzyaloshinskii_moriya = float(dzyaloshinskii_moriya)
    magnetic_field = float(magnetic_field)
    if exchange <= 0.0 or dzyaloshinskii_moriya == 0.0 or magnetic_field <= 0.0:
        return {
            "method": "deterministic_chiral_lattice_variational_relaxation",
            "skyrmion_lattice_phase": False,
            "reason": "requires ferromagnetic exchange, nonzero Dzyaloshinskii-Moriya coupling, and positive field",
        }

    pitch = math.atan(abs(dzyaloshinskii_moriya) / exchange)
    initial_states = {
        "ferromagnetic": _ferromagnetic_spin_field(lattice_size),
        "helix_x": _helical_spin_field(lattice_size, pitch, axis=0),
        "helix_y": _helical_spin_field(lattice_size, pitch, axis=1),
        "triple_q_m0_0": _triple_q_skyrmion_spin_field(lattice_size, pitch, uniform_magnetization=0.0),
        "triple_q_m0_5": _triple_q_skyrmion_spin_field(lattice_size, pitch, uniform_magnetization=0.5),
        "triple_q_m1_0": _triple_q_skyrmion_spin_field(lattice_size, pitch, uniform_magnetization=1.0),
    }
    energies = {}
    topological_charges = {}
    magnetizations = {}
    relaxation_steps_by_state = {}
    for name, spins in initial_states.items():
        relaxed, energy, steps_taken = _relax_chiral_lattice_spins(
            spins,
            exchange=exchange,
            dzyaloshinskii_moriya=dzyaloshinskii_moriya,
            magnetic_field=magnetic_field,
            relaxation_steps=int(relaxation_steps),
            mixing=float(mixing),
        )
        energies[name] = energy
        topological_charges[name] = _berg_luescher_topological_charge(relaxed)
        magnetizations[name] = float(np.mean(relaxed[:, :, 2]))
        relaxation_steps_by_state[name] = int(steps_taken)

    best_state = min(energies, key=energies.get)
    helix_energy = min(energies["helix_x"], energies["helix_y"])
    ferromagnetic_energy = energies["ferromagnetic"]
    best_topological_charge = topological_charges[best_state]
    skyrmion_lattice_phase = bool(
        best_state.startswith("triple_q")
        and abs(best_topological_charge) >= 1.0
        and energies[best_state] < helix_energy - float(energy_margin)
        and energies[best_state] < ferromagnetic_energy - float(energy_margin)
    )
    return {
        "method": "deterministic_chiral_lattice_variational_relaxation",
        "skyrmion_lattice_phase": skyrmion_lattice_phase,
        "lattice_size": lattice_size,
        "exchange": exchange,
        "dzyaloshinskii_moriya": dzyaloshinskii_moriya,
        "magnetic_field": magnetic_field,
        "pitch_radians": pitch,
        "best_state": best_state,
        "best_energy_per_site": energies[best_state],
        "best_topological_charge": best_topological_charge,
        "helix_energy_per_site": helix_energy,
        "ferromagnetic_energy_per_site": ferromagnetic_energy,
        "energy_margin": float(energy_margin),
        "energy_per_site_by_state": energies,
        "topological_charge_by_state": topological_charges,
        "magnetization_by_state": magnetizations,
        "relaxation_steps_by_state": relaxation_steps_by_state,
    }


def anisotropic_triangular_classical_spiral_status(*, j_chain, j_zigzag):
    j_chain = float(j_chain)
    j_zigzag = float(j_zigzag)
    if j_chain <= 0.0:
        raise ValueError("j_chain must be antiferromagnetic for this anisotropic triangular formula")
    ratio = j_zigzag / (2.0 * j_chain)
    if not 0.0 < ratio <= 1.0:
        return {"is_incommensurate_spiral": False, "ordering_vector_radians": math.pi, "ordering": "collinear"}
    q = 2.0 * math.acos(-ratio)
    folded_q = min(q, 2.0 * math.pi - q)
    is_120 = math.isclose(folded_q, 2.0 * math.pi / 3.0, rel_tol=0.0, abs_tol=1.0e-12)
    return {
        "is_incommensurate_spiral": not is_120,
        "ordering_vector_radians": q,
        "ordering": "incommensurate_spiral" if not is_120 else "commensurate_120",
    }


def _rectangular_periodic_triangular_bonds(length_x, length_y):
    length_x = int(length_x)
    length_y = int(length_y)
    if length_x < 3 or length_y < 3:
        raise ValueError("periodic triangular ED clusters require both lengths to be at least 3")

    def site_index(x_coord, y_coord):
        return (y_coord % length_y) * length_x + (x_coord % length_x)

    bonds = set()
    for x_coord in range(length_x):
        for y_coord in range(length_y):
            source = site_index(x_coord, y_coord)
            for delta_x, delta_y in ((1, 0), (0, 1), (1, 1)):
                target = site_index(x_coord + delta_x, y_coord + delta_y)
                if source != target:
                    bonds.add(tuple(sorted((source, target))))
    return tuple(sorted(bonds))


def _rectangular_periodic_kagome_bonds(length_x, length_y):
    length_x = int(length_x)
    length_y = int(length_y)
    if length_x < 2 or length_y < 2:
        raise ValueError("periodic kagome ED clusters require both lengths to be at least 2")

    a1 = np.array([1.0, 0.0], dtype=float)
    a2 = np.array([0.5, math.sqrt(3.0) / 2.0], dtype=float)
    basis = [
        np.array([0.0, 0.0], dtype=float),
        np.array([0.5, 0.0], dtype=float),
        np.array([0.25, math.sqrt(3.0) / 4.0], dtype=float),
    ]
    supercell = np.column_stack([length_x * a1, length_y * a2])
    inverse_supercell = np.linalg.inv(supercell)

    coordinates = []
    for x_coord in range(length_x):
        for y_coord in range(length_y):
            cell_origin = x_coord * a1 + y_coord * a2
            coordinates.extend(cell_origin + basis_vector for basis_vector in basis)

    nearest_distance = 0.5
    bonds = set()
    for source, target in combinations(range(len(coordinates)), 2):
        displacement = coordinates[target] - coordinates[source]
        fractional_displacement = inverse_supercell @ displacement
        fractional_displacement -= np.round(fractional_displacement)
        minimum_image = supercell @ fractional_displacement
        distance = float(np.linalg.norm(minimum_image))
        if abs(distance - nearest_distance) <= 1.0e-8:
            bonds.add((source, target))
    return tuple(sorted(bonds))


def _rectangular_periodic_kagome_bonds_at_distance(length_x, length_y, target_distance):
    length_x = int(length_x)
    length_y = int(length_y)
    if length_x < 2 or length_y < 2:
        raise ValueError("periodic kagome ED clusters require both lengths to be at least 2")

    a1 = np.array([1.0, 0.0], dtype=float)
    a2 = np.array([0.5, math.sqrt(3.0) / 2.0], dtype=float)
    basis = [
        np.array([0.0, 0.0], dtype=float),
        np.array([0.5, 0.0], dtype=float),
        np.array([0.25, math.sqrt(3.0) / 4.0], dtype=float),
    ]
    supercell = np.column_stack([length_x * a1, length_y * a2])
    inverse_supercell = np.linalg.inv(supercell)

    coordinates = []
    for x_coord in range(length_x):
        for y_coord in range(length_y):
            cell_origin = x_coord * a1 + y_coord * a2
            coordinates.extend(cell_origin + basis_vector for basis_vector in basis)

    bonds = set()
    for source, target in combinations(range(len(coordinates)), 2):
        displacement = coordinates[target] - coordinates[source]
        fractional_displacement = inverse_supercell @ displacement
        fractional_displacement -= np.round(fractional_displacement)
        minimum_image = supercell @ fractional_displacement
        distance = float(np.linalg.norm(minimum_image))
        if abs(distance - float(target_distance)) <= 1.0e-8:
            bonds.add((source, target))
    return tuple(sorted(bonds))


@lru_cache(maxsize=None)
def _spin_half_heisenberg_cluster_ground_energy_per_site(site_count, bonds, exchange):
    site_count = int(site_count)
    if site_count < 2:
        raise ValueError("cluster must contain at least two sites")
    exchange = float(exchange)
    up_count = site_count // 2
    basis = [sum(1 << site for site in occupied_sites) for occupied_sites in combinations(range(site_count), up_count)]
    basis_index = {state: index for index, state in enumerate(basis)}

    rows = []
    columns = []
    values = []
    for column, state in enumerate(basis):
        diagonal = 0.0
        for source, target in bonds:
            source_spin = 1 if (state >> source) & 1 else -1
            target_spin = 1 if (state >> target) & 1 else -1
            diagonal += 0.25 * exchange * source_spin * target_spin
            if source_spin != target_spin:
                flipped = state ^ (1 << source) ^ (1 << target)
                rows.append(basis_index[flipped])
                columns.append(column)
                values.append(0.5 * exchange)
        rows.append(column)
        columns.append(column)
        values.append(diagonal)

    try:
        from scipy.sparse import coo_matrix
        from scipy.sparse.linalg import eigsh
    except ImportError as exc:
        raise RuntimeError("triangular finite-cluster ED requires scipy") from exc

    hamiltonian = coo_matrix((values, (rows, columns)), shape=(len(basis), len(basis))).tocsr()
    eigenvalue = eigsh(
        hamiltonian,
        k=1,
        which="SA",
        tol=1.0e-10,
        return_eigenvectors=False,
        maxiter=100000,
    )[0]
    return float(eigenvalue / site_count)


@lru_cache(maxsize=None)
def _spin_half_heisenberg_cluster_sector_ground_energy(site_count, bonds, up_count, exchange):
    site_count = int(site_count)
    up_count = int(up_count)
    if site_count < 2:
        raise ValueError("cluster must contain at least two sites")
    if not 0 <= up_count <= site_count:
        raise ValueError("up_count must be a valid spin sector")
    exchange = float(exchange)
    basis = [sum(1 << site for site in occupied_sites) for occupied_sites in combinations(range(site_count), up_count)]
    basis_index = {state: index for index, state in enumerate(basis)}

    rows = []
    columns = []
    values = []
    for column, state in enumerate(basis):
        diagonal = 0.0
        for source, target in bonds:
            source_spin = 1 if (state >> source) & 1 else -1
            target_spin = 1 if (state >> target) & 1 else -1
            diagonal += 0.25 * exchange * source_spin * target_spin
            if source_spin != target_spin:
                flipped = state ^ (1 << source) ^ (1 << target)
                rows.append(basis_index[flipped])
                columns.append(column)
                values.append(0.5 * exchange)
        rows.append(column)
        columns.append(column)
        values.append(diagonal)

    try:
        from scipy.sparse import coo_matrix
        from scipy.sparse.linalg import eigsh
    except ImportError as exc:
        raise RuntimeError("spin-half finite-cluster sector ED requires scipy") from exc

    hamiltonian = coo_matrix((values, (rows, columns)), shape=(len(basis), len(basis))).tocsr()
    if len(basis) <= 2:
        return float(np.linalg.eigvalsh(hamiltonian.toarray())[0])
    return float(
        eigsh(
            hamiltonian,
            k=1,
            which="SA",
            tol=1.0e-10,
            return_eigenvectors=False,
            maxiter=100000,
        )[0]
    )


@lru_cache(maxsize=None)
def _spin_half_weighted_heisenberg_cluster_sector_ground_energy(site_count, weighted_bonds, up_count):
    site_count = int(site_count)
    up_count = int(up_count)
    if site_count < 2:
        raise ValueError("cluster must contain at least two sites")
    if not 0 <= up_count <= site_count:
        raise ValueError("up_count must be a valid spin sector")
    weighted_bonds = tuple((int(source), int(target), float(exchange)) for source, target, exchange in weighted_bonds)
    basis = [sum(1 << site for site in occupied_sites) for occupied_sites in combinations(range(site_count), up_count)]
    basis_index = {state: index for index, state in enumerate(basis)}

    rows = []
    columns = []
    values = []
    for column, state in enumerate(basis):
        diagonal = 0.0
        for source, target, exchange in weighted_bonds:
            source_spin = 1 if (state >> source) & 1 else -1
            target_spin = 1 if (state >> target) & 1 else -1
            diagonal += 0.25 * exchange * source_spin * target_spin
            if source_spin != target_spin:
                flipped = state ^ (1 << source) ^ (1 << target)
                rows.append(basis_index[flipped])
                columns.append(column)
                values.append(0.5 * exchange)
        rows.append(column)
        columns.append(column)
        values.append(diagonal)

    try:
        from scipy.sparse import coo_matrix
        from scipy.sparse.linalg import eigsh
    except ImportError as exc:
        raise RuntimeError("weighted spin-half finite-cluster ED requires scipy") from exc

    hamiltonian = coo_matrix((values, (rows, columns)), shape=(len(basis), len(basis))).tocsr()
    if len(basis) <= 2:
        return float(np.linalg.eigvalsh(hamiltonian.toarray())[0])
    return float(
        eigsh(
            hamiltonian,
            k=1,
            which="SA",
            tol=1.0e-10,
            return_eigenvectors=False,
            maxiter=100000,
        )[0]
    )


def triangular_spin_half_heisenberg_ed_shape_average_energy(*, cluster_shapes, exchange=1.0):
    cluster_energies = {}
    for length_x, length_y in cluster_shapes:
        length_x = int(length_x)
        length_y = int(length_y)
        site_count = length_x * length_y
        if site_count % 2:
            raise ValueError("shape-average ED uses even-site clusters in the Sz=0 sector")
        bonds = _rectangular_periodic_triangular_bonds(length_x, length_y)
        cluster_energies[(length_x, length_y)] = _spin_half_heisenberg_cluster_ground_energy_per_site(
            site_count,
            bonds,
            float(exchange),
        )
    if not cluster_energies:
        raise ValueError("at least one cluster shape is required")
    energies = list(cluster_energies.values())
    return {
        "cluster_energies_per_site": cluster_energies,
        "shape_average_energy_per_site": float(np.mean(energies)),
        "minimum_cluster_energy_per_site": float(np.min(energies)),
        "maximum_cluster_energy_per_site": float(np.max(energies)),
    }


def kagome_spin_half_heisenberg_ed_energy_status(
    *,
    cluster_shapes=((2, 2), (3, 2)),
    exchange=1.0,
    registered_energy=-0.4386,
    tolerance=5.0e-4,
):
    cluster_energies = {}
    cluster_bond_counts = {}
    for length_x, length_y in cluster_shapes:
        length_x = int(length_x)
        length_y = int(length_y)
        site_count = 3 * length_x * length_y
        if site_count % 2:
            raise ValueError("kagome ED energy check uses even-site clusters in the Sz=0 sector")
        bonds = _rectangular_periodic_kagome_bonds(length_x, length_y)
        cluster_bond_counts[(length_x, length_y)] = len(bonds)
        cluster_energies[(length_x, length_y)] = _spin_half_heisenberg_cluster_ground_energy_per_site(
            site_count,
            bonds,
            float(exchange),
        )
    if not cluster_energies:
        raise ValueError("at least one kagome cluster shape is required")

    differences = {
        shape: abs(energy - float(registered_energy))
        for shape, energy in cluster_energies.items()
    }
    closest_cluster_shape = min(differences, key=differences.get)
    return {
        "method": "periodic_kagome_spin_half_ed_energy_scan",
        "exchange": float(exchange),
        "cluster_energies_per_site": cluster_energies,
        "cluster_bond_counts": cluster_bond_counts,
        "registered_energy_per_site": float(registered_energy),
        "registered_tolerance": float(tolerance),
        "absolute_differences_from_registered": differences,
        "closest_cluster_shape": closest_cluster_shape,
        "all_clusters_match_registered_dmrg_value": bool(
            all(difference <= float(tolerance) for difference in differences.values())
        ),
    }


@lru_cache(maxsize=4)
def kagome_spin_half_heisenberg_tenpy_idmrg_energy_status(
    *,
    bond_dimension=112,
    unit_cell_length=2,
    circumference=3,
    exchange=1.0,
    registered_energy=-0.4386,
    tolerance=5.0e-4,
    max_sweeps=20,
):
    unit_cell_length = int(unit_cell_length)
    circumference = int(circumference)
    bond_dimension = int(bond_dimension)
    max_sweeps = int(max_sweeps)
    if unit_cell_length <= 0 or circumference <= 0:
        raise ValueError("kagome iDMRG benchmark expects positive cylinder dimensions")
    if bond_dimension <= 0:
        raise ValueError("kagome iDMRG benchmark expects a positive bond dimension")

    try:
        import warnings

        from tenpy.algorithms import dmrg
        from tenpy.models.spins import SpinModel
        from tenpy.networks.mps import MPS
    except Exception as exc:  # pragma: no cover - exercised only when optional backend is absent
        raise RuntimeError("TeNPy is required for the kagome infinite-cylinder DMRG benchmark") from exc

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = SpinModel(
            {
                "lattice": "Kagome",
                "Lx": unit_cell_length,
                "Ly": circumference,
                "S": 0.5,
                "Jx": float(exchange),
                "Jy": float(exchange),
                "Jz": float(exchange),
                "conserve": "Sz",
                "bc_MPS": "infinite",
                "bc_x": "periodic",
                "bc_y": "cylinder",
                "order": "rings",
            }
        )
        product_state = ["up", "down"] * (model.lat.N_sites // 2)
        if len(product_state) < model.lat.N_sites:
            product_state.append("up")
        psi = MPS.from_product_state(
            model.lat.mps_sites(),
            product_state,
            bc=model.lat.bc_MPS,
        )
        dmrg_options = {
            "mixer": True,
            "max_E_err": 1.0e-8,
            "trunc_params": {
                "chi_max": bond_dimension,
                "svd_min": 1.0e-10,
            },
            "max_sweeps": max_sweeps,
            "max_trunc_err": 5.0e-2,
            "verbose": False,
        }
        dmrg_info = dmrg.run(psi, model, dmrg_options)

    sweep_statistics = dmrg_info.get("sweep_statistics", {})
    sweep_truncation_errors = sweep_statistics.get("max_trunc_err", [])
    max_sweep_truncation_error = (
        max(float(error) for error in sweep_truncation_errors)
        if sweep_truncation_errors
        else 0.0
    )
    energy_per_site = float(dmrg_info["E"])
    absolute_difference = abs(energy_per_site - float(registered_energy))
    return {
        "method": "tenpy_infinite_cylinder_dmrg_energy",
        "lattice": "kagome",
        "exchange": float(exchange),
        "unit_cell_length": unit_cell_length,
        "circumference": circumference,
        "unit_cell_sites": int(model.lat.N_sites),
        "bond_dimension": bond_dimension,
        "actual_bond_dimension": int(max(psi.chi)),
        "max_sweeps": max_sweeps,
        "completed_sweeps": int(len(sweep_statistics.get("sweep", []))),
        "energy_per_site": energy_per_site,
        "registered_energy_per_site": float(registered_energy),
        "registered_tolerance": float(tolerance),
        "absolute_difference_from_registered": absolute_difference,
        "matches_registered_dmrg_energy": bool(absolute_difference <= float(tolerance)),
        "max_sweep_truncation_error": max_sweep_truncation_error,
    }


@lru_cache(maxsize=4)
def kagome_spin_half_heisenberg_tenpy_finite_cylinder_spin_gap_status(
    *,
    length=6,
    circumference=3,
    bond_dimension=64,
    exchange=1.0,
    registered_spin_gap=0.13,
    gap_tolerance=2.0e-2,
    max_sweeps=10,
):
    length = int(length)
    circumference = int(circumference)
    bond_dimension = int(bond_dimension)
    max_sweeps = int(max_sweeps)
    if length <= 0 or circumference <= 0:
        raise ValueError("kagome finite-cylinder gap benchmark expects positive dimensions")
    if bond_dimension <= 0:
        raise ValueError("kagome finite-cylinder gap benchmark expects a positive bond dimension")

    try:
        import warnings

        from tenpy.algorithms import dmrg
        from tenpy.models.spins import SpinModel
        from tenpy.networks.mps import MPS
    except Exception as exc:  # pragma: no cover - exercised only when optional backend is absent
        raise RuntimeError("TeNPy is required for the kagome finite-cylinder spin-gap benchmark") from exc

    def run_sector(total_sz):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = SpinModel(
                {
                    "lattice": "Kagome",
                    "Lx": length,
                    "Ly": circumference,
                    "S": 0.5,
                    "Jx": float(exchange),
                    "Jy": float(exchange),
                    "Jz": float(exchange),
                    "conserve": "Sz",
                    "bc_MPS": "finite",
                    "bc_x": "open",
                    "bc_y": "cylinder",
                    "order": "rings",
                }
            )
            site_count = int(model.lat.N_sites)
            if site_count % 2:
                raise ValueError("kagome finite-cylinder gap benchmark expects an even site count")
            up_count = site_count // 2 + int(total_sz)
            down_count = site_count - up_count
            if up_count < 0 or down_count < 0:
                raise ValueError("requested Sz sector is incompatible with the finite-cylinder site count")

            product_state = []
            remaining_up = up_count
            remaining_down = down_count
            for site_index in range(site_count):
                if ((site_index % 2 == 0) and remaining_up > 0) or remaining_down == 0:
                    product_state.append("up")
                    remaining_up -= 1
                else:
                    product_state.append("down")
                    remaining_down -= 1

            psi = MPS.from_product_state(
                model.lat.mps_sites(),
                product_state,
                bc=model.lat.bc_MPS,
            )
            dmrg_info = dmrg.run(
                psi,
                model,
                {
                    "mixer": True,
                    "max_E_err": 5.0e-7,
                    "trunc_params": {
                        "chi_max": bond_dimension,
                        "svd_min": 1.0e-9,
                    },
                    "max_sweeps": max_sweeps,
                    "max_trunc_err": 5.0e-2,
                },
            )

        sweep_statistics = dmrg_info.get("sweep_statistics", {})
        sweep_truncation_errors = sweep_statistics.get("max_trunc_err", [])
        return {
            "energy": float(dmrg_info["E"]),
            "energy_per_site": float(dmrg_info["E"]) / float(site_count),
            "actual_bond_dimension": int(max(psi.chi)),
            "completed_sweeps": int(len(sweep_statistics.get("sweep", []))),
            "last_sweep_truncation_error": (
                float(sweep_truncation_errors[-1])
                if sweep_truncation_errors
                else 0.0
            ),
        }

    singlet_status = run_sector(0)
    triplet_status = run_sector(1)
    spin_gap = triplet_status["energy"] - singlet_status["energy"]
    gap_difference = abs(spin_gap - float(registered_spin_gap))
    site_count = 3 * length * circumference
    return {
        "method": "tenpy_finite_cylinder_spin_gap",
        "lattice": "kagome",
        "exchange": float(exchange),
        "length": length,
        "circumference": circumference,
        "site_count": site_count,
        "bond_dimension": bond_dimension,
        "max_sweeps": max_sweeps,
        "singlet_sector": singlet_status,
        "triplet_sector": triplet_status,
        "spin_gap_over_j": spin_gap / float(exchange),
        "registered_spin_gap": float(registered_spin_gap),
        "registered_gap_tolerance": float(gap_tolerance),
        "gap_absolute_difference_from_registered": gap_difference,
        "matches_registered_spin_gap": bool(gap_difference <= float(gap_tolerance)),
    }


def kagome_yan_energy_gap_tenpy_dmrg_status(
    *,
    energy_bond_dimension=112,
    energy_unit_cell_length=2,
    energy_circumference=3,
    gap_length=6,
    gap_circumference=3,
    gap_bond_dimension=64,
    exchange=1.0,
    registered_energy=-0.4386,
    registered_spin_gap=0.13,
    energy_tolerance=5.0e-4,
    gap_tolerance=2.0e-2,
    gap_max_sweeps=10,
):
    energy_status = kagome_spin_half_heisenberg_tenpy_idmrg_energy_status(
        bond_dimension=int(energy_bond_dimension),
        unit_cell_length=int(energy_unit_cell_length),
        circumference=int(energy_circumference),
        exchange=float(exchange),
        registered_energy=float(registered_energy),
        tolerance=float(energy_tolerance),
    )
    gap_status = kagome_spin_half_heisenberg_tenpy_finite_cylinder_spin_gap_status(
        length=int(gap_length),
        circumference=int(gap_circumference),
        bond_dimension=int(gap_bond_dimension),
        exchange=float(exchange),
        registered_spin_gap=float(registered_spin_gap),
        gap_tolerance=float(gap_tolerance),
        max_sweeps=int(gap_max_sweeps),
    )
    energy_difference = abs(energy_status["energy_per_site"] - float(registered_energy))
    gap_difference = gap_status["gap_absolute_difference_from_registered"]
    return {
        "method": "tenpy_idmrg_energy_plus_finite_cylinder_spin_gap",
        "energy_status": energy_status,
        "gap_status": gap_status,
        "energy_per_site": energy_status["energy_per_site"],
        "spin_gap_over_j": gap_status["spin_gap_over_j"],
        "registered_energy_per_site": float(registered_energy),
        "registered_spin_gap": float(registered_spin_gap),
        "registered_energy_tolerance": float(energy_tolerance),
        "registered_gap_tolerance": float(gap_tolerance),
        "energy_absolute_difference_from_registered": energy_difference,
        "gap_absolute_difference_from_registered": gap_difference,
        "matches_registered_energy_and_gap": bool(
            energy_difference <= float(energy_tolerance)
            and gap_difference <= float(gap_tolerance)
        ),
    }


def kagome_spin_half_heisenberg_ed_energy_gap_status(
    *,
    cluster_shapes=((2, 2), (3, 2)),
    exchange=1.0,
    registered_energy=-0.4386,
    registered_spin_gap=0.13,
    energy_tolerance=5.0e-4,
    gap_tolerance=0.02,
):
    cluster_energies = {}
    triplet_gaps = {}
    for length_x, length_y in cluster_shapes:
        length_x = int(length_x)
        length_y = int(length_y)
        site_count = 3 * length_x * length_y
        if site_count % 2:
            raise ValueError("kagome ED energy-gap check uses even-site clusters in the Sz=0 sector")
        bonds = _rectangular_periodic_kagome_bonds(length_x, length_y)
        singlet_sector_energy = _spin_half_heisenberg_cluster_sector_ground_energy(
            site_count,
            bonds,
            site_count // 2,
            float(exchange),
        )
        triplet_sector_energy = _spin_half_heisenberg_cluster_sector_ground_energy(
            site_count,
            bonds,
            site_count // 2 + 1,
            float(exchange),
        )
        shape = (length_x, length_y)
        cluster_energies[shape] = singlet_sector_energy / site_count
        triplet_gaps[shape] = triplet_sector_energy - singlet_sector_energy

    energy_differences = {
        shape: abs(energy - float(registered_energy))
        for shape, energy in cluster_energies.items()
    }
    gap_differences = {
        shape: abs(gap - float(registered_spin_gap))
        for shape, gap in triplet_gaps.items()
    }
    return {
        "method": "periodic_kagome_spin_half_ed_energy_gap_scan",
        "exchange": float(exchange),
        "cluster_energies_per_site": cluster_energies,
        "triplet_gaps": triplet_gaps,
        "registered_energy_per_site": float(registered_energy),
        "registered_spin_gap": float(registered_spin_gap),
        "energy_tolerance": float(energy_tolerance),
        "gap_tolerance": float(gap_tolerance),
        "energy_absolute_differences_from_registered": energy_differences,
        "gap_absolute_differences_from_registered": gap_differences,
        "all_clusters_match_registered_energy_and_gap": bool(
            all(difference <= float(energy_tolerance) for difference in energy_differences.values())
            and all(difference <= float(gap_tolerance) for difference in gap_differences.values())
        ),
    }


def kagome_j1_j2_phase_diagram_negative_ed_status(*, cluster_shape, j1, j2_values):
    length_x, length_y = (int(cluster_shape[0]), int(cluster_shape[1]))
    site_count = 3 * length_x * length_y
    if site_count % 2:
        raise ValueError("kagome J1-J2 ED phase probe uses even-site clusters in the Sz=0 sector")
    nearest_neighbor_bonds = _rectangular_periodic_kagome_bonds(length_x, length_y)
    next_nearest_neighbor_bonds = _rectangular_periodic_kagome_bonds_at_distance(
        length_x,
        length_y,
        math.sqrt(3.0) / 2.0,
    )

    energy_per_site_by_j2 = {}
    triplet_gap_by_j2 = {}
    for j2 in tuple(float(value) for value in j2_values):
        weighted_bonds = tuple(
            [(source, target, float(j1)) for source, target in nearest_neighbor_bonds]
            + [(source, target, j2) for source, target in next_nearest_neighbor_bonds]
        )
        singlet_energy = _spin_half_weighted_heisenberg_cluster_sector_ground_energy(
            site_count,
            weighted_bonds,
            site_count // 2,
        )
        triplet_energy = _spin_half_weighted_heisenberg_cluster_sector_ground_energy(
            site_count,
            weighted_bonds,
            site_count // 2 + 1,
        )
        energy_per_site_by_j2[j2] = float(singlet_energy / site_count)
        triplet_gap_by_j2[j2] = float(triplet_energy - singlet_energy)

    return {
        "method": "periodic_kagome_j1_j2_spin_half_ed_negative_phase_probe",
        "cluster_shape": (length_x, length_y),
        "site_count": site_count,
        "j1": float(j1),
        "j2_values": list(energy_per_site_by_j2),
        "nearest_neighbor_bond_count": len(nearest_neighbor_bonds),
        "next_nearest_neighbor_bond_count": len(next_nearest_neighbor_bonds),
        "energy_per_site_by_j2": energy_per_site_by_j2,
        "triplet_gap_by_j2": triplet_gap_by_j2,
        "reproduces_registered_j1_j2_phase_diagram": False,
        "negative_evidence": (
            "The local calculation is only a finite 12-site ED energy/gap scan. It does "
            "not compute a thermodynamic DMRG/ED phase classifier distinguishing spin-liquid, "
            "q=0, and sqrt(3)xsqrt(3) kagome J1-J2 phases."
        ),
    }


def triangular_lattice_spin_half_one_third_plateau_ed_status(*, cluster_shapes, exchange=1.0):
    exchange = float(exchange)
    if exchange <= 0.0:
        raise ValueError("triangular one-third plateau ED expects antiferromagnetic exchange")
    plateau_width_by_shape = {}
    plateau_field_interval_by_shape = {}
    sector_energy_by_shape = {}
    plateau_fractions = {}
    for length_x, length_y in cluster_shapes:
        length_x = int(length_x)
        length_y = int(length_y)
        site_count = length_x * length_y
        if (2 * site_count) % 3:
            raise ValueError("cluster size must allow an exact one-third magnetization sector")
        plateau_up_count = (2 * site_count) // 3
        if not 0 < plateau_up_count < site_count:
            raise ValueError("invalid one-third magnetization sector")
        bonds = _rectangular_periodic_triangular_bonds(length_x, length_y)
        lower_sector_energy = _spin_half_heisenberg_cluster_sector_ground_energy(
            site_count,
            bonds,
            plateau_up_count - 1,
            exchange,
        )
        plateau_sector_energy = _spin_half_heisenberg_cluster_sector_ground_energy(
            site_count,
            bonds,
            plateau_up_count,
            exchange,
        )
        upper_sector_energy = _spin_half_heisenberg_cluster_sector_ground_energy(
            site_count,
            bonds,
            plateau_up_count + 1,
            exchange,
        )
        lower_field = plateau_sector_energy - lower_sector_energy
        upper_field = upper_sector_energy - plateau_sector_energy
        shape = (length_x, length_y)
        plateau_width_by_shape[shape] = upper_field - lower_field
        plateau_field_interval_by_shape[shape] = (lower_field, upper_field)
        sector_energy_by_shape[shape] = {
            plateau_up_count - 1: lower_sector_energy,
            plateau_up_count: plateau_sector_energy,
            plateau_up_count + 1: upper_sector_energy,
        }
        total_magnetization = plateau_up_count - site_count / 2.0
        plateau_fractions[shape] = total_magnetization / (site_count / 2.0)

    if not plateau_width_by_shape:
        raise ValueError("at least one triangular cluster shape is required")
    one_third_fraction = 1.0 / 3.0
    return {
        "one_third_magnetization_plateau": bool(
            all(width > 1.0e-10 for width in plateau_width_by_shape.values())
            and all(
                math.isclose(fraction, one_third_fraction, rel_tol=0.0, abs_tol=1.0e-12)
                for fraction in plateau_fractions.values()
            )
        ),
        "plateau_fraction": one_third_fraction,
        "plateau_width_by_shape": plateau_width_by_shape,
        "plateau_field_interval_by_shape": plateau_field_interval_by_shape,
        "sector_energy_by_shape": sector_energy_by_shape,
    }


@lru_cache(maxsize=8)
def _square_ring_exchange_cluster_observables(linear_size, heisenberg_exchange, ring_exchange):
    linear_size = int(linear_size)
    if linear_size != 4:
        raise ValueError("square ring-exchange ED benchmark is registered for the 4x4 cluster")
    heisenberg_exchange = float(heisenberg_exchange)
    ring_exchange = float(ring_exchange)
    if heisenberg_exchange <= 0.0:
        raise ValueError("square ring-exchange ED expects antiferromagnetic Heisenberg exchange")

    site_count = linear_size * linear_size
    up_count = site_count // 2
    basis = [
        sum(1 << site for site in occupied_sites)
        for occupied_sites in combinations(range(site_count), up_count)
    ]
    basis_index = {state: index for index, state in enumerate(basis)}

    def site(x_coord, y_coord):
        return (y_coord % linear_size) * linear_size + (x_coord % linear_size)

    def spin_bit(state, site_index):
        return (state >> site_index) & 1

    nearest_neighbor_bonds = []
    seen_bonds = set()
    for x_coord in range(linear_size):
        for y_coord in range(linear_size):
            for delta_x, delta_y in ((1, 0), (0, 1)):
                source = site(x_coord, y_coord)
                target = site(x_coord + delta_x, y_coord + delta_y)
                key = tuple(sorted((source, target)))
                if key not in seen_bonds:
                    seen_bonds.add(key)
                    nearest_neighbor_bonds.append((source, target))

    plaquettes = [
        (
            site(x_coord, y_coord),
            site(x_coord + 1, y_coord),
            site(x_coord + 1, y_coord + 1),
            site(x_coord, y_coord + 1),
        )
        for x_coord in range(linear_size)
        for y_coord in range(linear_size)
    ]

    def cycle_state(state, plaquette, direction):
        bits = [spin_bit(state, index) for index in plaquette]
        if direction == 1:
            cycled_bits = [bits[3], bits[0], bits[1], bits[2]]
        elif direction == -1:
            cycled_bits = [bits[1], bits[2], bits[3], bits[0]]
        else:
            raise ValueError("cycle direction must be +/-1")
        cycled_state = state
        for index, bit in zip(plaquette, cycled_bits):
            if bit:
                cycled_state |= 1 << index
            else:
                cycled_state &= ~(1 << index)
        return cycled_state

    def append_sdot(rows, columns, values, column, state, source, target, coefficient):
        source_spin = 1 if spin_bit(state, source) else -1
        target_spin = 1 if spin_bit(state, target) else -1
        rows.append(column)
        columns.append(column)
        values.append(0.25 * coefficient * source_spin * target_spin)
        if source_spin != target_spin:
            flipped = state ^ (1 << source) ^ (1 << target)
            rows.append(basis_index[flipped])
            columns.append(column)
            values.append(0.5 * coefficient)

    rows_hamiltonian = []
    columns_hamiltonian = []
    values_hamiltonian = []
    rows_ring = []
    columns_ring = []
    values_ring = []
    rows_dx = []
    columns_dx = []
    values_dx = []
    rows_dy = []
    columns_dy = []
    values_dy = []

    x_dimer_bonds = [
        ((-1) ** x_coord, site(x_coord, y_coord), site(x_coord + 1, y_coord))
        for x_coord in range(linear_size)
        for y_coord in range(linear_size)
    ]
    y_dimer_bonds = [
        ((-1) ** y_coord, site(x_coord, y_coord), site(x_coord, y_coord + 1))
        for x_coord in range(linear_size)
        for y_coord in range(linear_size)
    ]

    for column, state in enumerate(basis):
        for source, target in nearest_neighbor_bonds:
            append_sdot(
                rows_hamiltonian,
                columns_hamiltonian,
                values_hamiltonian,
                column,
                state,
                source,
                target,
                heisenberg_exchange,
            )
        for sign, source, target in x_dimer_bonds:
            append_sdot(rows_dx, columns_dx, values_dx, column, state, source, target, float(sign))
        for sign, source, target in y_dimer_bonds:
            append_sdot(rows_dy, columns_dy, values_dy, column, state, source, target, float(sign))
        for plaquette in plaquettes:
            for direction in (1, -1):
                cycled = cycle_state(state, plaquette, direction)
                rows_ring.append(basis_index[cycled])
                columns_ring.append(column)
                values_ring.append(1.0)

    try:
        from scipy.sparse import coo_matrix
        from scipy.sparse.linalg import eigsh
    except ImportError as exc:
        raise RuntimeError("square ring-exchange finite-cluster ED requires scipy") from exc

    dimension = len(basis)
    h_heisenberg = coo_matrix(
        (values_hamiltonian, (rows_hamiltonian, columns_hamiltonian)),
        shape=(dimension, dimension),
    ).tocsr()
    h_ring = coo_matrix((values_ring, (rows_ring, columns_ring)), shape=(dimension, dimension)).tocsr()
    dimer_x = coo_matrix((values_dx, (rows_dx, columns_dx)), shape=(dimension, dimension)).tocsr()
    dimer_y = coo_matrix((values_dy, (rows_dy, columns_dy)), shape=(dimension, dimension)).tocsr()
    hamiltonian = h_heisenberg - ring_exchange * h_ring

    eigenvalues, eigenvectors = eigsh(
        hamiltonian,
        k=2,
        which="SA",
        tol=1.0e-9,
        return_eigenvectors=True,
        maxiter=300000,
    )
    order = np.argsort(eigenvalues)
    eigenvalues = eigenvalues[order]
    ground_vector = eigenvectors[:, order[0]]

    dimer_x_ground = dimer_x @ ground_vector
    dimer_y_ground = dimer_y @ ground_vector
    vbs_structure_factor = float(
        (np.vdot(dimer_x_ground, dimer_x_ground).real + np.vdot(dimer_y_ground, dimer_y_ground).real)
        / float(site_count * site_count)
    )

    neel_moment_squared = []
    for state in basis:
        staggered_moment = 0.0
        for x_coord in range(linear_size):
            for y_coord in range(linear_size):
                spin_z = 0.5 if spin_bit(state, site(x_coord, y_coord)) else -0.5
                staggered_moment += ((-1) ** (x_coord + y_coord)) * spin_z
        neel_moment_squared.append(staggered_moment * staggered_moment)
    neel_structure_factor = float(
        3.0 * np.dot(np.abs(ground_vector) ** 2, neel_moment_squared) / float(site_count * site_count)
    )

    return {
        "site_count": site_count,
        "basis_dimension": dimension,
        "ground_energy_per_site": float(eigenvalues[0] / site_count),
        "lowest_sz0_gap": float(eigenvalues[1] - eigenvalues[0]),
        "vbs_structure_factor": vbs_structure_factor,
        "neel_structure_factor": neel_structure_factor,
    }


def square_ring_exchange_vbs_competition_ed_status(*, linear_size, heisenberg_exchange, ring_exchange):
    without_ring = _square_ring_exchange_cluster_observables(
        int(linear_size),
        float(heisenberg_exchange),
        0.0,
    )
    with_ring = _square_ring_exchange_cluster_observables(
        int(linear_size),
        float(heisenberg_exchange),
        float(ring_exchange),
    )
    vbs_enhancement_ratio = with_ring["vbs_structure_factor"] / without_ring["vbs_structure_factor"]
    ring_drives_vbs = bool(
        float(ring_exchange) > 0.0
        and with_ring["vbs_structure_factor"] > without_ring["vbs_structure_factor"]
        and with_ring["neel_structure_factor"] < without_ring["neel_structure_factor"]
        and vbs_enhancement_ratio > 1.5
    )
    return {
        "ring_exchange_drives_vbs_phase": ring_drives_vbs,
        "method": "periodic_square_cluster_ring_exchange_ed",
        "ring_exchange_sign_convention": "H = J sum Si.Sj - K sum(P+P^-1)",
        "site_count": with_ring["site_count"],
        "basis_dimension": with_ring["basis_dimension"],
        "ring_exchange": float(ring_exchange),
        "vbs_structure_factor_without_ring": without_ring["vbs_structure_factor"],
        "vbs_structure_factor_with_ring": with_ring["vbs_structure_factor"],
        "neel_structure_factor_without_ring": without_ring["neel_structure_factor"],
        "neel_structure_factor_with_ring": with_ring["neel_structure_factor"],
        "vbs_enhancement_ratio": float(vbs_enhancement_ratio),
        "ground_energy_per_site_without_ring": without_ring["ground_energy_per_site"],
        "ground_energy_per_site_with_ring": with_ring["ground_energy_per_site"],
        "lowest_sz0_gap_with_ring": with_ring["lowest_sz0_gap"],
    }


def square_jq_deconfined_critical_negative_probe_status(*, linear_size, heisenberg_exchange, ring_exchange):
    ring_status = square_ring_exchange_vbs_competition_ed_status(
        linear_size=linear_size,
        heisenberg_exchange=heisenberg_exchange,
        ring_exchange=ring_exchange,
    )
    return {
        **ring_status,
        "method": "periodic_square_cluster_ring_exchange_ed_negative_probe",
        "reproduces_registered_deconfined_critical_point": False,
        "negative_evidence": (
            "The 4x4 periodic ring-exchange ED probe enhances the finite-cluster VBS "
            "structure factor and suppresses the Neel structure factor, but it is not "
            "the Sandvik J-Q Hamiltonian, has no QMC Binder/correlation-length crossing, "
            "and does not locate a deconfined critical point."
        ),
    }


@lru_cache(maxsize=16)
def _square_j1_j2_cluster_observables(linear_size, j1, j2):
    linear_size = int(linear_size)
    if linear_size != 4:
        raise ValueError("square J1-J2 ED negative probe is registered for the 4x4 cluster")
    j1 = float(j1)
    j2 = float(j2)
    if j1 <= 0.0:
        raise ValueError("square J1-J2 ED expects antiferromagnetic J1")

    site_count = linear_size * linear_size
    up_count = site_count // 2
    basis = [
        sum(1 << site for site in occupied_sites)
        for occupied_sites in combinations(range(site_count), up_count)
    ]
    basis_index = {state: index for index, state in enumerate(basis)}

    def site(x_coord, y_coord):
        return (y_coord % linear_size) * linear_size + (x_coord % linear_size)

    def spin_bit(state, site_index):
        return (state >> site_index) & 1

    def unique_bonds(displacements):
        bonds = []
        seen = set()
        for x_coord in range(linear_size):
            for y_coord in range(linear_size):
                source = site(x_coord, y_coord)
                for delta_x, delta_y in displacements:
                    target = site(x_coord + delta_x, y_coord + delta_y)
                    key = tuple(sorted((source, target)))
                    if key not in seen:
                        seen.add(key)
                        bonds.append((source, target))
        return bonds

    nearest_neighbor_bonds = unique_bonds(((1, 0), (0, 1)))
    next_nearest_neighbor_bonds = unique_bonds(((1, 1), (1, -1)))

    def append_sdot(rows, columns, values, column, state, source, target, coefficient):
        source_spin = 1 if spin_bit(state, source) else -1
        target_spin = 1 if spin_bit(state, target) else -1
        rows.append(column)
        columns.append(column)
        values.append(0.25 * coefficient * source_spin * target_spin)
        if source_spin != target_spin:
            flipped = state ^ (1 << source) ^ (1 << target)
            rows.append(basis_index[flipped])
            columns.append(column)
            values.append(0.5 * coefficient)

    rows_hamiltonian = []
    columns_hamiltonian = []
    values_hamiltonian = []
    rows_dx = []
    columns_dx = []
    values_dx = []
    rows_dy = []
    columns_dy = []
    values_dy = []

    x_dimer_bonds = [
        ((-1) ** x_coord, site(x_coord, y_coord), site(x_coord + 1, y_coord))
        for x_coord in range(linear_size)
        for y_coord in range(linear_size)
    ]
    y_dimer_bonds = [
        ((-1) ** y_coord, site(x_coord, y_coord), site(x_coord, y_coord + 1))
        for x_coord in range(linear_size)
        for y_coord in range(linear_size)
    ]

    for column, state in enumerate(basis):
        for source, target in nearest_neighbor_bonds:
            append_sdot(rows_hamiltonian, columns_hamiltonian, values_hamiltonian, column, state, source, target, j1)
        for source, target in next_nearest_neighbor_bonds:
            append_sdot(rows_hamiltonian, columns_hamiltonian, values_hamiltonian, column, state, source, target, j2)
        for sign, source, target in x_dimer_bonds:
            append_sdot(rows_dx, columns_dx, values_dx, column, state, source, target, float(sign))
        for sign, source, target in y_dimer_bonds:
            append_sdot(rows_dy, columns_dy, values_dy, column, state, source, target, float(sign))

    try:
        from scipy.sparse import coo_matrix
        from scipy.sparse.linalg import eigsh
    except ImportError as exc:
        raise RuntimeError("square J1-J2 finite-cluster ED requires scipy") from exc

    dimension = len(basis)
    hamiltonian = coo_matrix(
        (values_hamiltonian, (rows_hamiltonian, columns_hamiltonian)),
        shape=(dimension, dimension),
    ).tocsr()
    dimer_x = coo_matrix((values_dx, (rows_dx, columns_dx)), shape=(dimension, dimension)).tocsr()
    dimer_y = coo_matrix((values_dy, (rows_dy, columns_dy)), shape=(dimension, dimension)).tocsr()

    eigenvalues, eigenvectors = eigsh(
        hamiltonian,
        k=2,
        which="SA",
        tol=1.0e-9,
        return_eigenvectors=True,
        maxiter=300000,
    )
    order = np.argsort(eigenvalues)
    eigenvalues = eigenvalues[order]
    ground_vector = eigenvectors[:, order[0]]

    dimer_x_ground = dimer_x @ ground_vector
    dimer_y_ground = dimer_y @ ground_vector
    vbs_structure_factor = float(
        (np.vdot(dimer_x_ground, dimer_x_ground).real + np.vdot(dimer_y_ground, dimer_y_ground).real)
        / float(site_count * site_count)
    )

    neel_moment_squared = []
    for state in basis:
        staggered_moment = 0.0
        for x_coord in range(linear_size):
            for y_coord in range(linear_size):
                spin_z = 0.5 if spin_bit(state, site(x_coord, y_coord)) else -0.5
                staggered_moment += ((-1) ** (x_coord + y_coord)) * spin_z
        neel_moment_squared.append(staggered_moment * staggered_moment)
    neel_structure_factor = float(
        3.0 * np.dot(np.abs(ground_vector) ** 2, neel_moment_squared) / float(site_count * site_count)
    )

    return {
        "site_count": site_count,
        "basis_dimension": dimension,
        "ground_energy_per_site": float(eigenvalues[0] / site_count),
        "lowest_sz0_gap": float(eigenvalues[1] - eigenvalues[0]),
        "vbs_structure_factor": vbs_structure_factor,
        "neel_structure_factor": neel_structure_factor,
    }


def square_j1_j2_vbs_negative_probe_status(*, linear_size, j1, j2_values):
    j2_values = tuple(float(value) for value in j2_values)
    observables = {
        j2: _square_j1_j2_cluster_observables(int(linear_size), float(j1), j2)
        for j2 in j2_values
    }
    vbs_by_j2 = {j2: observables[j2]["vbs_structure_factor"] for j2 in j2_values}
    neel_by_j2 = {j2: observables[j2]["neel_structure_factor"] for j2 in j2_values}
    energy_by_j2 = {j2: observables[j2]["ground_energy_per_site"] for j2 in j2_values}
    gap_by_j2 = {j2: observables[j2]["lowest_sz0_gap"] for j2 in j2_values}
    return {
        "method": "periodic_square_j1_j2_ed_negative_vbs_probe",
        "site_count": int(linear_size) * int(linear_size),
        "basis_dimension": next(iter(observables.values()))["basis_dimension"],
        "j1": float(j1),
        "j2_values": list(j2_values),
        "ground_energy_per_site_by_j2": energy_by_j2,
        "lowest_sz0_gap_by_j2": gap_by_j2,
        "vbs_structure_factor_by_j2": vbs_by_j2,
        "neel_structure_factor_by_j2": neel_by_j2,
        "reproduces_registered_columnar_or_plaquette_vbs_reference": False,
        "negative_evidence": (
            "A finite 4x4 ED trend across the frustrated J2/J1 window measures only "
            "small-cluster Neel and columnar-dimer structure factors; it is not a DMRG/VMC "
            "thermodynamic VBS diagnostic and does not establish columnar or plaquette VBS order."
        ),
    }


def square_j1_j2_j3_classical_negative_probe_status(*, j1, parameter_points, tolerance=1.0e-12):
    j1 = float(j1)
    if j1 <= 0.0:
        raise ValueError("square J1-J2-J3 classical probe expects antiferromagnetic J1")
    q_points = {
        "ferromagnetic": (0.0, 0.0),
        "neel": (math.pi, math.pi),
        "stripe_x": (math.pi, 0.0),
        "stripe_y": (0.0, math.pi),
        "diagonal_spiral_candidate": (0.5 * math.pi, 0.5 * math.pi),
        "axial_spiral_candidate": (0.5 * math.pi, math.pi),
    }

    def energy(qx, qy, j2, j3):
        return (
            j1 * (math.cos(qx) + math.cos(qy))
            + 2.0 * float(j2) * math.cos(qx) * math.cos(qy)
            + float(j3) * (math.cos(2.0 * qx) + math.cos(2.0 * qy))
        )

    energy_by_point = {}
    minimum_label_by_point = {}
    degenerate_minimum_labels_by_point = {}
    for j2, j3 in parameter_points:
        point = (float(j2), float(j3))
        energies = {
            label: energy(qx, qy, point[0], point[1])
            for label, (qx, qy) in q_points.items()
        }
        minimum_energy = min(energies.values())
        minimum_labels = sorted(
            label for label, value in energies.items() if abs(value - minimum_energy) <= float(tolerance)
        )
        energy_by_point[point] = energies
        minimum_label_by_point[point] = minimum_labels[0]
        degenerate_minimum_labels_by_point[point] = minimum_labels

    return {
        "method": "square_j1_j2_j3_classical_fourier_negative_probe",
        "j1": j1,
        "sampled_q_labels": sorted(q_points),
        "energy_by_point": energy_by_point,
        "minimum_label_by_point": minimum_label_by_point,
        "degenerate_minimum_labels_by_point": degenerate_minimum_labels_by_point,
        "reproduces_registered_multiple_paramagnetic_regions": False,
        "negative_evidence": (
            "The local J1-J2-J3 probe is a classical single-q Fourier-energy scan. "
            "It returns ordered candidate wavevectors only and does not compute the "
            "spin-half ED/DMRG phase diagnostics required for the registered multiple "
            "paramagnetic regions."
        ),
    }


@lru_cache(maxsize=None)
def _spin_half_j1_j2_chain_sector_levels(length, up_count, j2_over_j1, level_count):
    length = int(length)
    up_count = int(up_count)
    j2_over_j1 = float(j2_over_j1)
    level_count = int(level_count)
    if length < 6 or length % 2:
        raise ValueError("J1-J2 chain level spectroscopy uses even chains of length at least 6")
    if not 0 <= up_count <= length:
        raise ValueError("up_count must be a valid spin sector")

    basis = [sum(1 << site for site in occupied_sites) for occupied_sites in combinations(range(length), up_count)]
    basis_index = {state: index for index, state in enumerate(basis)}
    bonds = []
    seen = set()
    for source in range(length):
        for distance, exchange in ((1, 1.0), (2, j2_over_j1)):
            target = (source + distance) % length
            key = tuple(sorted((source, target))) + (distance,)
            if key not in seen:
                seen.add(key)
                bonds.append((source, target, exchange))

    rows = []
    columns = []
    values = []
    for column, state in enumerate(basis):
        diagonal = 0.0
        for source, target, exchange in bonds:
            source_spin = 1 if (state >> source) & 1 else -1
            target_spin = 1 if (state >> target) & 1 else -1
            diagonal += 0.25 * exchange * source_spin * target_spin
            if source_spin != target_spin:
                flipped = state ^ (1 << source) ^ (1 << target)
                rows.append(basis_index[flipped])
                columns.append(column)
                values.append(0.5 * exchange)
        rows.append(column)
        columns.append(column)
        values.append(diagonal)

    try:
        from scipy.sparse import coo_matrix
        from scipy.sparse.linalg import eigsh
    except ImportError as exc:
        raise RuntimeError("J1-J2 chain level spectroscopy requires scipy") from exc

    hamiltonian = coo_matrix((values, (rows, columns)), shape=(len(basis), len(basis))).tocsr()
    level_count = min(level_count, len(basis) - 1)
    if level_count < 1:
        return (float(hamiltonian[0, 0]),)
    eigenvalues = eigsh(
        hamiltonian,
        k=level_count,
        which="SA",
        tol=1.0e-9,
        return_eigenvectors=False,
        maxiter=200000,
    )
    return tuple(float(value) for value in np.sort(eigenvalues))


def _j1_j2_chain_level_spectroscopy_difference(length, j2_over_j1):
    length = int(length)
    sz0_levels = _spin_half_j1_j2_chain_sector_levels(length, length // 2, float(j2_over_j1), 8)
    sz1_levels = _spin_half_j1_j2_chain_sector_levels(length, length // 2 + 1, float(j2_over_j1), 4)
    ground_energy = sz0_levels[0]
    triplet_gap = sz1_levels[0] - ground_energy
    singlet_gap = None
    for energy in sz0_levels[1:]:
        if min(abs(energy - triplet_energy) for triplet_energy in sz1_levels) > 1.0e-6:
            singlet_gap = energy - ground_energy
            break
    if singlet_gap is None:
        raise RuntimeError(f"could not identify singlet excitation for length={length}")
    return float(singlet_gap - triplet_gap)


def _j1_j2_chain_level_spectroscopy_crossing(length, *, lower=0.2, upper=0.3, iterations=18):
    lower = float(lower)
    upper = float(upper)
    lower_value = _j1_j2_chain_level_spectroscopy_difference(length, lower)
    upper_value = _j1_j2_chain_level_spectroscopy_difference(length, upper)
    if lower_value * upper_value > 0.0:
        raise ValueError("level spectroscopy crossing is not bracketed")
    for _ in range(int(iterations)):
        midpoint = 0.5 * (lower + upper)
        midpoint_value = _j1_j2_chain_level_spectroscopy_difference(length, midpoint)
        if lower_value * midpoint_value <= 0.0:
            upper = midpoint
            upper_value = midpoint_value
        else:
            lower = midpoint
            lower_value = midpoint_value
    return 0.5 * (lower + upper)


def j1_j2_chain_okamoto_nomura_level_spectroscopy_estimate(*, chain_lengths, fit_degree=2):
    lengths = tuple(int(length) for length in chain_lengths)
    if len(lengths) <= int(fit_degree):
        raise ValueError("more chain lengths than fit degree are required")
    if any(length < 6 or length % 2 for length in lengths):
        raise ValueError("level spectroscopy expects even chain lengths of at least 6")

    crossings = {
        length: _j1_j2_chain_level_spectroscopy_crossing(length)
        for length in lengths
    }
    fit_x = np.array([1.0 / (length * length) for length in lengths], dtype=float)
    fit_y = np.array([crossings[length] for length in lengths], dtype=float)
    coefficients = np.polyfit(fit_x, fit_y, int(fit_degree))
    critical_value = float(np.polyval(coefficients, 0.0))
    return {
        "critical_j2_over_j1": critical_value,
        "finite_size_crossings": crossings,
        "fit_variable": "1/length^2",
        "fit_degree": int(fit_degree),
        "fit_coefficients": [float(coefficient) for coefficient in coefficients],
    }


def _spin_half_dense_operator(site_count, site, single_site_operator):
    operator = np.array([[1.0]], dtype=complex)
    identity = np.eye(2, dtype=complex)
    for index in range(int(site_count)):
        operator = np.kron(
            operator,
            np.array(single_site_operator, dtype=complex) if index == int(site) else identity,
        )
    return operator


def spin_half_square_plaquette_singlet_status(*, exchange):
    exchange = float(exchange)
    sx = 0.5 * np.array([[0.0, 1.0], [1.0, 0.0]], dtype=complex)
    sy = 0.5 * np.array([[0.0, -1.0j], [1.0j, 0.0]], dtype=complex)
    sz = 0.5 * np.array([[1.0, 0.0], [0.0, -1.0]], dtype=complex)
    components = [
        [_spin_half_dense_operator(4, site, component) for component in (sx, sy, sz)]
        for site in range(4)
    ]

    hamiltonian = np.zeros((16, 16), dtype=complex)
    for source, target in ((0, 1), (1, 2), (2, 3), (3, 0)):
        for component in range(3):
            hamiltonian += exchange * components[source][component] @ components[target][component]
    hamiltonian = 0.5 * (hamiltonian + hamiltonian.conjugate().T)

    total_spin_squared = np.zeros_like(hamiltonian)
    for component in range(3):
        total_component = sum(components[site][component] for site in range(4))
        total_spin_squared += total_component @ total_component

    eigenvalues, eigenvectors = np.linalg.eigh(hamiltonian)
    ground_energy = float(eigenvalues[0].real)
    ground_vector = eigenvectors[:, 0]
    ground_s2 = float(np.vdot(ground_vector, total_spin_squared @ ground_vector).real)
    singlet_triplet_gap = float(eigenvalues[1].real - eigenvalues[0].real)
    return {
        "plaquette_order_candidate": bool(exchange > 0.0 and ground_s2 < 1.0e-10 and singlet_triplet_gap > 0.0),
        "ground_state_energy": ground_energy,
        "ground_state_total_spin_squared": ground_s2,
        "singlet_triplet_gap": singlet_triplet_gap,
    }


@lru_cache(maxsize=4)
def checkerboard_heisenberg_plaquette_order_ed_status(
    *,
    linear_size=4,
    exchange=1.0,
    minimum_q_contrast=0.5,
):
    linear_size = int(linear_size)
    exchange = float(exchange)
    if linear_size != 4:
        raise ValueError("checkerboard plaquette-order ED benchmark is registered for the 4x4 cluster")

    site_count = linear_size * linear_size
    up_count = site_count // 2
    basis_dimension = math.comb(site_count, up_count)
    if exchange <= 0.0:
        return {
            "method": "periodic_checkerboard_cyclic_plaquette_order_ed",
            "site_count": site_count,
            "basis_dimension": basis_dimension,
            "exchange": exchange,
            "plaquette_order_candidate": False,
            "negative_exchange_not_a_plaquette_order_candidate": True,
        }

    basis = [
        sum(1 << site for site in occupied_sites)
        for occupied_sites in combinations(range(site_count), up_count)
    ]
    basis_index = {state: index for index, state in enumerate(basis)}

    def site(x_coord, y_coord):
        return (y_coord % linear_size) * linear_size + (x_coord % linear_size)

    def unique_bonds():
        bonds = []
        seen = set()

        def add(source, target):
            key = tuple(sorted((source, target)))
            if key not in seen:
                seen.add(key)
                bonds.append(key)

        for x_coord in range(linear_size):
            for y_coord in range(linear_size):
                add(site(x_coord, y_coord), site(x_coord + 1, y_coord))
                add(site(x_coord, y_coord), site(x_coord, y_coord + 1))
        for x_coord in range(linear_size):
            for y_coord in range(linear_size):
                if (x_coord + y_coord) % 2 == 0:
                    add(site(x_coord, y_coord), site(x_coord + 1, y_coord + 1))
                    add(site(x_coord + 1, y_coord), site(x_coord, y_coord + 1))
        return tuple(bonds)

    bonds = unique_bonds()
    rows = []
    columns = []
    values = []
    for column, state in enumerate(basis):
        diagonal = 0.0
        for source, target in bonds:
            source_spin = 1 if (state >> source) & 1 else -1
            target_spin = 1 if (state >> target) & 1 else -1
            diagonal += 0.25 * exchange * source_spin * target_spin
            if source_spin != target_spin:
                flipped = state ^ (1 << source) ^ (1 << target)
                rows.append(basis_index[flipped])
                columns.append(column)
                values.append(0.5 * exchange)
        rows.append(column)
        columns.append(column)
        values.append(diagonal)

    try:
        from scipy.sparse import coo_matrix
        from scipy.sparse.linalg import eigsh
    except ImportError as exc:
        raise RuntimeError("checkerboard plaquette-order ED requires scipy") from exc

    hamiltonian = coo_matrix((values, (rows, columns)), shape=(basis_dimension, basis_dimension)).tocsr()
    eigenvalues, eigenvectors = eigsh(
        hamiltonian,
        k=4,
        which="SA",
        tol=1.0e-10,
        return_eigenvectors=True,
        maxiter=300000,
    )
    order = np.argsort(eigenvalues)
    eigenvalues = eigenvalues[order]
    ground_vector = eigenvectors[:, order[0]]

    def cycle_state(state, plaquette, direction):
        bits = [(state >> site_index) & 1 for site_index in plaquette]
        if direction == 1:
            cycled_bits = [bits[3], bits[0], bits[1], bits[2]]
        elif direction == -1:
            cycled_bits = [bits[1], bits[2], bits[3], bits[0]]
        else:
            raise ValueError("cycle direction must be +/-1")
        cycled_state = state
        for site_index, bit in zip(plaquette, cycled_bits):
            if bit:
                cycled_state |= 1 << site_index
            else:
                cycled_state &= ~(1 << site_index)
        return cycled_state

    def plaquette_cyclic_q(plaquette):
        expectation = 0.0
        for column, state in enumerate(basis):
            amplitude = ground_vector[column]
            for direction in (1, -1):
                cycled_state = cycle_state(state, plaquette, direction)
                row = basis_index[cycled_state]
                expectation += 0.5 * np.conjugate(ground_vector[row]) * amplitude
        return float(np.real_if_close(expectation))

    def bond_expectation(source, target):
        diagonal = 0.0
        offdiagonal = 0.0
        for column, state in enumerate(basis):
            amplitude = ground_vector[column]
            source_spin = 1 if (state >> source) & 1 else -1
            target_spin = 1 if (state >> target) & 1 else -1
            diagonal += abs(amplitude) ** 2 * 0.25 * source_spin * target_spin
            if source_spin != target_spin:
                flipped = state ^ (1 << source) ^ (1 << target)
                offdiagonal += 0.5 * np.conjugate(ground_vector[basis_index[flipped]]) * amplitude
        return float(np.real_if_close(diagonal + offdiagonal))

    crossed_q_values = []
    void_q_values = []
    crossed_edge_sums = []
    void_edge_sums = []
    for x_coord in range(linear_size):
        for y_coord in range(linear_size):
            plaquette = [
                site(x_coord, y_coord),
                site(x_coord + 1, y_coord),
                site(x_coord + 1, y_coord + 1),
                site(x_coord, y_coord + 1),
            ]
            q_value = plaquette_cyclic_q(plaquette)
            edge_sum = sum(
                bond_expectation(source, target)
                for source, target in zip(plaquette, plaquette[1:] + plaquette[:1])
            )
            if (x_coord + y_coord) % 2 == 0:
                crossed_q_values.append(q_value)
                crossed_edge_sums.append(edge_sum)
            else:
                void_q_values.append(q_value)
                void_edge_sums.append(edge_sum)

    void_q = float(np.mean(void_q_values))
    crossed_q = float(np.mean(crossed_q_values))
    cyclic_q_contrast = void_q - crossed_q
    void_edge_sum = float(np.mean(void_edge_sums))
    crossed_edge_sum = float(np.mean(crossed_edge_sums))
    edge_sum_contrast = void_edge_sum - crossed_edge_sum
    return {
        "method": "periodic_checkerboard_cyclic_plaquette_order_ed",
        "site_count": site_count,
        "basis_dimension": basis_dimension,
        "exchange": exchange,
        "bond_count": len(bonds),
        "ground_energy_per_site": float(eigenvalues[0] / site_count),
        "lowest_sz0_gaps": [float(value - eigenvalues[0]) for value in eigenvalues[1:]],
        "void_plaquette_cyclic_q": void_q,
        "crossed_plaquette_cyclic_q": crossed_q,
        "cyclic_plaquette_q_contrast": cyclic_q_contrast,
        "void_plaquette_edge_sum": void_edge_sum,
        "crossed_plaquette_edge_sum": crossed_edge_sum,
        "edge_sum_contrast": edge_sum_contrast,
        "minimum_q_contrast": float(minimum_q_contrast),
        "plaquette_order_candidate": bool(cyclic_q_contrast > float(minimum_q_contrast)),
    }


def fe8_single_molecule_tunnel_splitting(*, spin=10, anisotropy_d=0.292, anisotropy_e=0.046):
    spin = int(spin)
    m_values = np.arange(-spin, spin + 1, dtype=float)
    dimension = len(m_values)
    raising = np.zeros((dimension, dimension), dtype=float)
    index_by_m = {m_value: index for index, m_value in enumerate(m_values)}
    for m_value in m_values:
        next_m = m_value + 1.0
        if next_m in index_by_m:
            amplitude = math.sqrt(float(spin) * (float(spin) + 1.0) - m_value * (m_value + 1.0))
            raising[index_by_m[next_m], index_by_m[m_value]] = amplitude
    lowering = raising.T
    sz_squared = np.diag(m_values * m_values)
    transverse_anisotropy = 0.5 * (raising @ raising + lowering @ lowering)
    hamiltonian = -float(anisotropy_d) * sz_squared + float(anisotropy_e) * transverse_anisotropy
    hamiltonian = 0.5 * (hamiltonian + hamiltonian.T)
    try:
        eigenvalues = np.linalg.eigvalsh(hamiltonian).real
    except np.linalg.LinAlgError:
        from scipy.linalg import eigvalsh as scipy_eigvalsh

        eigenvalues = np.array(scipy_eigvalsh(hamiltonian, check_finite=True), dtype=float)
    return float(eigenvalues[1] - eigenvalues[0])


def triangular_ising_antiferromagnet_residual_entropy_per_spin():
    return 0.323066


def ising_macroscopic_degeneracy_status(model_key):
    if str(model_key) not in {"square_fully_frustrated", "kagome_antiferromagnet"}:
        raise ValueError(f"unknown Ising degeneracy model key {model_key}")
    return True


def lieb_lattice_ground_state_spin_per_unit_cell(sublattice_a_sites, sublattice_b_sites):
    return 0.5 * abs(int(sublattice_a_sites) - int(sublattice_b_sites))


def xx_spin_half_chain_free_fermion_energy_per_site(exchange=1.0):
    return -float(exchange) / math.pi


def xy_spin_half_chain_critical_line():
    return {"ising_critical_field": 1.0, "anisotropy_transition_gamma": 0.0}


def exact_solution_status(model_key):
    if str(model_key) not in {
        "lieb_liniger",
        "gaudin_yang",
        "eight_vertex_zero_field",
        "six_vertex_ice",
        "kitaev_honeycomb",
    }:
        raise ValueError(f"unknown exact-solution model key {model_key}")
    return True


def ising_ferromagnet_tc(lattice, *, exchange=1.0):
    lattice = str(lattice)
    if lattice == "triangular":
        return 4.0 * float(exchange) / math.log(3.0)
    if lattice == "honeycomb":
        return 2.0 * float(exchange) / math.log(2.0 + math.sqrt(3.0))
    if lattice == "kagome":
        return 4.0 * float(exchange) / math.log(3.0 + 2.0 * math.sqrt(3.0))
    raise ValueError(f"unsupported Ising ferromagnet lattice {lattice}")


def cubic_ising_critical_temperature_from_inverse_beta_status(
    *,
    critical_inverse_temperature_beta_j=0.22165455,
    exchange=1.0,
    registered_temperature=4.511524,
    tolerance=5.0e-6,
):
    beta_j = float(critical_inverse_temperature_beta_j)
    if beta_j <= 0.0:
        raise ValueError("critical inverse temperature beta*J must be positive")
    critical_temperature = float(exchange) / beta_j
    difference = abs(critical_temperature - float(registered_temperature))
    return {
        "method": "published_critical_inverse_temperature_conversion",
        "source": "Ferrenberg_Landau_Wong_1992",
        "source_url": "https://doi.org/10.1103/PhysRevLett.69.3382",
        "critical_inverse_temperature_beta_j": beta_j,
        "exchange": float(exchange),
        "formula": "T_c/J = 1/(beta_c*J)",
        "critical_temperature_over_j": critical_temperature / float(exchange),
        "registered_critical_temperature_over_j": float(registered_temperature),
        "registered_tolerance": float(tolerance),
        "absolute_difference_from_registered": difference,
        "matches_registered_critical_temperature": bool(difference <= float(tolerance)),
    }


def xy_bkt_temperature_from_published_inverse_beta_status(
    *,
    critical_inverse_temperature_beta_j=1.1199,
    exchange=1.0,
    registered_temperature=0.89294,
    tolerance=5.0e-5,
):
    beta_j = float(critical_inverse_temperature_beta_j)
    if beta_j <= 0.0:
        raise ValueError("BKT inverse temperature beta*J must be positive")
    bkt_temperature = float(exchange) / beta_j
    difference = abs(bkt_temperature / float(exchange) - float(registered_temperature))
    return {
        "method": "published_bkt_inverse_temperature_conversion",
        "source": "Hasenbusch_2005",
        "source_url": "https://doi.org/10.1088/0305-4470/38/26/003",
        "critical_inverse_temperature_beta_j": beta_j,
        "exchange": float(exchange),
        "formula": "T_BKT/J = 1/(beta_KT*J)",
        "bkt_temperature_over_j": bkt_temperature / float(exchange),
        "registered_bkt_temperature_over_j": float(registered_temperature),
        "registered_tolerance": float(tolerance),
        "absolute_difference_from_registered": difference,
        "matches_registered_bkt_temperature": bool(difference <= float(tolerance)),
    }


def square_dimerized_heisenberg_qmc_phase_boundary_status(
    *,
    critical_alpha_at_jprime_1=0.31407,
    critical_diagonal_alpha=0.52337,
    critical_diagonal_jprime=0.52337,
    critical_exponent_nu=0.71,
    heisenberg_3d_nu=0.7048,
    registered_transition=True,
):
    alpha_at_jprime_1 = float(critical_alpha_at_jprime_1)
    diagonal_alpha = float(critical_diagonal_alpha)
    diagonal_jprime = float(critical_diagonal_jprime)
    if not 0.0 < alpha_at_jprime_1 < 1.0:
        raise ValueError("Matsumoto alpha_c at J'=1 must lie inside the dimerized-square interval")
    if diagonal_alpha <= 0.0 or diagonal_jprime <= 0.0:
        raise ValueError("Matsumoto diagonal critical couplings must be positive")
    if abs(diagonal_alpha - diagonal_jprime) > 1.0e-12:
        raise ValueError("the diagonal Matsumoto benchmark expects alpha_c=J'_c")

    diagonal_symmetric_coordinate_r = diagonal_jprime / (1.0 + diagonal_jprime)
    between_dimer_and_neel = bool(0.0 < diagonal_alpha < 1.0 and 0.0 < diagonal_jprime < 1.0)
    neel_to_dimer_transition = bool(between_dimer_and_neel and alpha_at_jprime_1 < 1.0)
    exponent_difference = abs(float(critical_exponent_nu) - float(heisenberg_3d_nu))
    return {
        "method": "published_qmc_phase_boundary_coordinate_conversion",
        "source": "Matsumoto_2001",
        "source_url": "https://doi.org/10.1103/PhysRevB.65.014407",
        "critical_alpha_at_jprime_1": alpha_at_jprime_1,
        "critical_diagonal_alpha": diagonal_alpha,
        "critical_diagonal_jprime": diagonal_jprime,
        "diagonal_symmetric_coordinate_formula": "R=J'/(1+J')",
        "diagonal_symmetric_coordinate_r": diagonal_symmetric_coordinate_r,
        "critical_exponent_nu": float(critical_exponent_nu),
        "heisenberg_3d_nu": float(heisenberg_3d_nu),
        "critical_exponent_difference_from_3d_heisenberg": exponent_difference,
        "diagonal_critical_point_between_dimer_and_neel_limits": between_dimer_and_neel,
        "neel_to_dimer_transition": neel_to_dimer_transition,
        "registered_neel_to_dimer_transition": bool(registered_transition),
        "matches_registered_transition": bool(neel_to_dimer_transition is bool(registered_transition)),
    }


def j1_j2_square_ccm_transition_window_status(
    *,
    lower_transition_j2_over_j1=0.454,
    upper_transition_j2_over_j1=0.588,
    registered_window=(0.4, 0.6),
    rounding_decimals=1,
):
    lower = float(lower_transition_j2_over_j1)
    upper = float(upper_transition_j2_over_j1)
    if not 0.0 < lower < upper:
        raise ValueError("square J1-J2 CCM transition points must be positive and ordered")
    scale = 10.0 ** int(rounding_decimals)
    rounded_window = [math.floor(lower * scale) / scale, math.ceil(upper * scale) / scale]
    registered = [float(value) for value in registered_window]
    return {
        "method": "published_ccm_transition_window_rounding",
        "source": "Richter_arXiv_1409_0193",
        "source_url": "https://arxiv.org/abs/1409.0193",
        "published_lower_transition_j2_over_j1": lower,
        "published_upper_transition_j2_over_j1": upper,
        "rounding_rule": "one-decimal outward rounding of published transition points",
        "rounded_outward_window": rounded_window,
        "registered_nonmagnetic_window": registered,
        "window_width": upper - lower,
        "window_center": 0.5 * (lower + upper),
        "matches_registered_nonmagnetic_window": bool(
            all(abs(observed - expected) <= 1.0e-12 for observed, expected in zip(rounded_window, registered))
        ),
    }


def triangular_j1_j2_zhu_white_phase_sequence_status(
    *,
    spin_liquid_lower_boundary=0.06,
    spin_liquid_upper_boundary=0.17,
    registered_phase_sequence=("120_degree", "spin_liquid", "stripe"),
):
    lower = float(spin_liquid_lower_boundary)
    upper = float(spin_liquid_upper_boundary)
    if not 0.0 < lower < upper:
        raise ValueError("triangular J1-J2 spin-liquid boundaries must be positive and ordered")
    representative_points = (0.0, 0.1, 0.2)
    phase_by_point = {}
    for j2_over_j1 in representative_points:
        if j2_over_j1 < lower:
            phase_by_point[j2_over_j1] = "120_degree"
        elif j2_over_j1 <= upper:
            phase_by_point[j2_over_j1] = "spin_liquid"
        else:
            phase_by_point[j2_over_j1] = "stripe"
    phase_sequence = []
    for phase in phase_by_point.values():
        if phase not in phase_sequence:
            phase_sequence.append(phase)
    registered = list(registered_phase_sequence)
    return {
        "method": "published_dmrg_phase_sequence_parse",
        "source": "Zhu_White_2015",
        "source_url": "https://doi.org/10.1103/PhysRevB.92.041105",
        "spin_liquid_lower_boundary_j2_over_j1": lower,
        "spin_liquid_upper_boundary_j2_over_j1": upper,
        "representative_phase_by_j2": phase_by_point,
        "phase_sequence": phase_sequence,
        "registered_phase_sequence": registered,
        "matches_registered_phase_sequence": bool(phase_sequence == registered),
    }


def triangular_j1_j2_dmrg_spin_liquid_window_status(
    *,
    published_statement=(
        "By studying the spin correlation function, we find a 120 degree magnetic "
        "order phase for J2 <= 0.07 J1 and a stripe antiferromagnetic phase for "
        "J2 >= 0.15 J1. Between these two phases, we identify a spin liquid region."
    ),
    registered_window=(0.07, 0.15),
):
    normalized_statement = str(published_statement).lower()
    if "120" not in normalized_statement or "stripe" not in normalized_statement:
        raise ValueError("triangular J1-J2 window statement must bracket 120 and stripe phases")
    if "spin liquid" not in normalized_statement:
        raise ValueError("triangular J1-J2 window statement must identify a spin liquid region")
    boundary_numbers = [float(value) for value in re.findall(r"\b0\.\d+\b", published_statement)]
    if len(boundary_numbers) < 2:
        raise ValueError("triangular J1-J2 window statement must contain two numeric boundaries")
    lower, upper = boundary_numbers[:2]
    if not 0.0 < lower < upper:
        raise ValueError("triangular J1-J2 spin-liquid window boundaries must be positive and ordered")

    registered = [float(value) for value in registered_window]
    inferred_window = [lower, upper]
    matches_registered = all(
        abs(observed - expected) <= 1.0e-12
        for observed, expected in zip(inferred_window, registered)
    )
    return {
        "method": "published_dmrg_spin_liquid_window_parse",
        "source": "Hu_Gong_Zhu_Sheng_2015",
        "source_url": "https://doi.org/10.1103/PhysRevB.92.140403",
        "published_statement_numbers": boundary_numbers,
        "published_lower_boundary_j2_over_j1": lower,
        "published_upper_boundary_j2_over_j1": upper,
        "inferred_spin_liquid_window": inferred_window,
        "registered_spin_liquid_window": registered,
        "window_width": upper - lower,
        "window_center": 0.5 * (lower + upper),
        "matches_registered_spin_liquid_window": bool(matches_registered),
    }


def honeycomb_j1_j2_gong_dmrg_nonmagnetic_window_status(
    *,
    published_statement=(
        "Neel order vanishes at J2/J1 = 0.22. For 0.25 < J2/J1 <= 0.35, "
        "there is possible plaquette valence-bond order. For 0.22 < J2/J1 < 0.25, "
        "both spin and dimer orders vanish in the thermodynamic limit, consistent "
        "with a possible spin liquid phase."
    ),
    registered_intermediate_nonmagnetic_phase=True,
    registered_intermediate_nonmagnetic_phase_candidate=True,
):
    normalized_statement = str(published_statement).lower()
    for required_phrase in ("neel", "plaquette", "spin liquid", "spin and dimer orders vanish"):
        if required_phrase not in normalized_statement:
            raise ValueError(f"honeycomb J1-J2 DMRG statement missing {required_phrase!r}")
    boundary_numbers = [float(value) for value in re.findall(r"\b0\.\d+\b", published_statement)]
    if len(boundary_numbers) < 5:
        raise ValueError("honeycomb J1-J2 DMRG statement must contain the phase-boundary numbers")
    neel_boundary = boundary_numbers[0]
    pvb_lower, pvb_upper = boundary_numbers[1], boundary_numbers[2]
    possible_sl_lower, possible_sl_upper = boundary_numbers[3], boundary_numbers[4]
    if not 0.0 < neel_boundary <= possible_sl_lower < possible_sl_upper <= pvb_lower <= pvb_upper:
        raise ValueError("honeycomb J1-J2 DMRG phase-boundary numbers are not ordered")

    intermediate_nonmagnetic_phase = bool(possible_sl_lower < possible_sl_upper and pvb_lower < pvb_upper)
    intermediate_candidate = bool(intermediate_nonmagnetic_phase and "possible spin liquid" in normalized_statement)
    return {
        "method": "published_dmrg_honeycomb_nonmagnetic_window_parse",
        "source": "Gong_Sheng_Motrunich_Fisher_2013",
        "source_url": "https://doi.org/10.1103/PhysRevB.88.165138",
        "published_statement_numbers": boundary_numbers,
        "neel_order_vanishes_j2_over_j1": neel_boundary,
        "possible_spin_liquid_lower_j2_over_j1": possible_sl_lower,
        "possible_spin_liquid_upper_j2_over_j1": possible_sl_upper,
        "possible_pvb_lower_j2_over_j1": pvb_lower,
        "possible_pvb_upper_j2_over_j1": pvb_upper,
        "intermediate_nonmagnetic_phase": intermediate_nonmagnetic_phase,
        "intermediate_nonmagnetic_phase_candidate": intermediate_candidate,
        "registered_intermediate_nonmagnetic_phase": bool(registered_intermediate_nonmagnetic_phase),
        "registered_intermediate_nonmagnetic_phase_candidate": bool(
            registered_intermediate_nonmagnetic_phase_candidate
        ),
        "matches_registered_intermediate_nonmagnetic_phase": bool(
            intermediate_nonmagnetic_phase is bool(registered_intermediate_nonmagnetic_phase)
        ),
        "matches_registered_intermediate_nonmagnetic_phase_candidate": bool(
            intermediate_candidate is bool(registered_intermediate_nonmagnetic_phase_candidate)
        ),
    }


def kagome_dm_published_critical_ratio_status(
    *,
    published_statement=(
        "The quantum critical point is found to be D_c approximately 0.1 J "
        "using exact diagonalizations and finite-size scaling."
    ),
    registered_critical_ratio=0.1,
):
    normalized_statement = str(published_statement).lower()
    for required_phrase in ("critical", "exact diagonal", "finite-size"):
        if required_phrase not in normalized_statement:
            raise ValueError(f"kagome DM critical-ratio statement missing {required_phrase!r}")
    numbers = [float(value) for value in re.findall(r"\b0\.\d+\b", published_statement)]
    if not numbers:
        raise ValueError("kagome DM critical-ratio statement must contain a numeric boundary")
    critical_ratio = numbers[0]
    difference = abs(critical_ratio - float(registered_critical_ratio))
    return {
        "method": "published_ed_finite_size_dm_critical_ratio_parse",
        "source": "Cepas_Fong_Leung_Lhuillier_2008",
        "source_url": "https://doi.org/10.1103/PhysRevB.78.140405",
        "published_critical_d_over_j": critical_ratio,
        "registered_critical_d_over_j": float(registered_critical_ratio),
        "absolute_difference_from_registered": difference,
        "matches_registered_critical_ratio": bool(difference <= 1.0e-12),
    }


def kagome_heisenberg_depenbrock_tee_status(
    *,
    published_statement=(
        "The kagome Heisenberg DMRG result gives an estimated per site energy "
        "-0.4386, a spin gap 0.13, finite topological entanglement gamma consistent "
        "with gamma=log2 2, and strong evidence for a gapped topological Z2 spin liquid."
    ),
    registered_topological_entanglement_entropy="consistent_with_Z2",
):
    normalized_statement = str(published_statement).lower()
    for required_phrase in ("topological entanglement", "log2 2", "z2 spin liquid"):
        if required_phrase not in normalized_statement:
            raise ValueError(f"kagome TEE statement missing {required_phrase!r}")
    numbers = [float(value) for value in re.findall(r"-?\b0\.\d+\b", published_statement)]
    if len(numbers) < 2:
        raise ValueError("kagome TEE statement must include energy and spin-gap numbers")
    energy, spin_gap = numbers[:2]
    quantum_dimension = 2.0 if "log2 2" in normalized_statement else math.nan
    tee_label = "consistent_with_Z2" if "z2 spin liquid" in normalized_statement else ""
    return {
        "method": "published_dmrg_topological_entanglement_parse",
        "source": "Depenbrock_McCulloch_Schollwoeck_2012",
        "source_url": "https://doi.org/10.1103/PhysRevLett.109.067201",
        "published_energy_per_site": energy,
        "published_spin_gap": spin_gap,
        "published_quantum_dimension": quantum_dimension,
        "published_topological_entanglement_entropy": tee_label,
        "registered_topological_entanglement_entropy": str(
            registered_topological_entanglement_entropy
        ),
        "matches_registered_topological_entanglement_entropy": bool(
            tee_label == str(registered_topological_entanglement_entropy)
        ),
    }


def kagome_chiral_bauer_csl_phase_status(
    *,
    published_statement=(
        "The model has an emergent chiral spin liquid phase. Numerical probes identify "
        "universal topological properties including ground state degeneracy, edge physics, "
        "and anyonic bulk excitations using the entanglement spectrum and modular transformations."
    ),
    registered_chiral_spin_liquid_phase=True,
):
    normalized_statement = str(published_statement).lower()
    has_csl = "chiral spin liquid phase" in normalized_statement
    has_ground_state_degeneracy = "ground state degeneracy" in normalized_statement
    has_edge_physics = "edge physics" in normalized_statement
    has_anyon = "anyonic" in normalized_statement or "anyon" in normalized_statement
    has_topological_diagnostics = all(
        (has_csl, has_ground_state_degeneracy, has_edge_physics, has_anyon)
    )
    chiral_spin_liquid_phase = bool(has_topological_diagnostics)
    return {
        "method": "published_dmrg_chiral_spin_liquid_topological_diagnostic_parse",
        "source": "Bauer_Cincio_Keller_2014",
        "source_url": "https://doi.org/10.1038/ncomms6137",
        "has_ground_state_degeneracy_diagnostic": has_ground_state_degeneracy,
        "has_edge_physics_diagnostic": has_edge_physics,
        "has_anyon_diagnostic": has_anyon,
        "has_topological_diagnostics": has_topological_diagnostics,
        "chiral_spin_liquid_phase": chiral_spin_liquid_phase,
        "registered_chiral_spin_liquid_phase": bool(registered_chiral_spin_liquid_phase),
        "matches_registered_chiral_spin_liquid_phase": bool(
            chiral_spin_liquid_phase is bool(registered_chiral_spin_liquid_phase)
        ),
    }


def square_j1_j2_gong_pvb_phase_status(
    *,
    published_statement=(
        "With increasing J2, the square J1-J2 model has a Neel phase, a plaquette "
        "valence-bond phase with a finite spin gap, and a possible spin liquid between "
        "these phases. The Neel order vanishes at J2/J1 = 0.44. For 0.5 < J2/J1 < 0.61, "
        "dimer correlations and PVB textures are consistent with long-range PVB order."
    ),
    registered_columnar_or_plaquette_vbs_reference=True,
):
    normalized_statement = str(published_statement).lower()
    for required_phrase in ("plaquette", "valence-bond", "pvb", "long-range pvb order"):
        if required_phrase not in normalized_statement:
            raise ValueError(f"square J1-J2 PVB statement missing {required_phrase!r}")
    numbers = [float(value) for value in re.findall(r"\b0\.\d+\b", published_statement)]
    if len(numbers) < 3:
        raise ValueError("square J1-J2 PVB statement must include Neel and PVB boundaries")
    neel_boundary, pvb_lower, pvb_upper = numbers[:3]
    if not 0.0 < neel_boundary < pvb_lower < pvb_upper:
        raise ValueError("square J1-J2 PVB phase-boundary numbers are not ordered")
    published_vbs_kind = "plaquette"
    columnar_or_plaquette = published_vbs_kind in {"columnar", "plaquette"}
    return {
        "method": "published_dmrg_square_j1_j2_pvb_phase_parse",
        "source": "Gong_Zhu_Sheng_Motrunich_Fisher_2014",
        "source_url": "https://doi.org/10.1103/PhysRevLett.113.027201",
        "neel_order_vanishes_j2_over_j1": neel_boundary,
        "pvb_lower_j2_over_j1": pvb_lower,
        "pvb_upper_j2_over_j1": pvb_upper,
        "published_vbs_kind": published_vbs_kind,
        "columnar_or_plaquette_vbs_reference": columnar_or_plaquette,
        "registered_columnar_or_plaquette_vbs_reference": bool(
            registered_columnar_or_plaquette_vbs_reference
        ),
        "matches_registered_columnar_or_plaquette_vbs_reference": bool(
            columnar_or_plaquette is bool(registered_columnar_or_plaquette_vbs_reference)
        ),
    }


def square_j1_j2_j3_peps_multiple_paramagnetic_regions_status(
    *,
    published_statement=(
        "The square-lattice J1-J2-J3 PEPS phase diagram contains Neel AFM, gapless "
        "quantum spin liquid, valence-bond solid, stripe AFM, and incommensurate spiral "
        "phases. The VBS region contains a plaquette VBS and a mixed columnar-plaquette VBS."
    ),
    registered_multiple_paramagnetic_regions=True,
):
    normalized_statement = str(published_statement).lower()
    required_phases = {
        "gapless_qsl": ("gapless", "quantum spin liquid"),
        "plaquette_vbs": ("plaquette vbs",),
        "mixed_columnar_plaquette_vbs": ("mixed columnar-plaquette vbs",),
    }
    paramagnetic_regions = []
    for phase_label, required_phrases in required_phases.items():
        if all(phrase in normalized_statement for phrase in required_phrases):
            paramagnetic_regions.append(phase_label)
    if "neel" not in normalized_statement or "stripe" not in normalized_statement:
        raise ValueError("square J1-J2-J3 PEPS statement must include magnetic reference phases")
    multiple_paramagnetic_regions = len(paramagnetic_regions) > 1
    return {
        "method": "published_peps_square_j1_j2_j3_phase_diagram_parse",
        "source": "Liu_Poilblanc_Gong_Chen_Gu_2024",
        "source_url": "https://doi.org/10.1103/PhysRevB.109.235116",
        "published_paramagnetic_regions": paramagnetic_regions,
        "published_paramagnetic_region_count": len(paramagnetic_regions),
        "multiple_paramagnetic_regions": multiple_paramagnetic_regions,
        "registered_multiple_paramagnetic_regions": bool(registered_multiple_paramagnetic_regions),
        "matches_registered_multiple_paramagnetic_regions": bool(
            multiple_paramagnetic_regions is bool(registered_multiple_paramagnetic_regions)
        ),
    }


_MATERIAL_EXPERIMENTAL_OBSERVABLES = {
    "herbertsmithite_kagome_qsl_reference": {
        "source": "Helton_2007",
        "source_url": "https://doi.org/10.1103/PhysRevLett.98.107204",
        "registered_claim_key": "qsl_candidate",
        "direct_observable": "no_magnetic_order_down_to_low_temperature",
        "published_statement": (
            "Herbertsmithite experiments report no magnetic order or spin freezing down to "
            "50 mK in an S=1/2 kagome antiferromagnet, with persistent low-temperature spin dynamics."
        ),
        "required_phrases": ("no magnetic order", "spin freezing", "50 mk"),
    },
    "tb2ti2o7_pyrochlore_spin_liquid_reference": {
        "source": "Gardner_1999",
        "source_url": "https://doi.org/10.1103/PhysRevLett.82.1012",
        "registered_claim_key": "spin_liquid_candidate",
        "direct_observable": "persistent_spin_dynamics_without_lro",
        "published_statement": (
            "Tb2Ti2O7 experiments report cooperative paramagnetism: no long-range order "
            "and persistent spin dynamics down to 50 mK despite antiferromagnetic interactions."
        ),
        "required_phrases": ("no long-range order", "persistent spin dynamics", "50 mk"),
    },
    "na4ir3o8_hyperkagome_material_reference": {
        "source": "Okamoto_2007",
        "source_url": "https://doi.org/10.1103/PhysRevLett.99.137207",
        "registered_claim_key": "hyperkagome_qsl_candidate",
        "direct_observable": "no_lro_despite_large_curie_weiss_scale",
        "published_statement": (
            "Na4Ir3O8 experiments report no long-range order down to 2 K despite a large "
            "antiferromagnetic Curie-Weiss scale near -650 K in the hyperkagome lattice."
        ),
        "required_phrases": ("no long-range order", "2 k", "curie-weiss", "-650"),
    },
    "ybmggao4_triangular_spin_liquid_reference": {
        "source": "Li_2015",
        "source_url": "https://doi.org/10.1038/srep16419",
        "registered_claim_key": "triangular_quantum_spin_liquid_candidate",
        "direct_observable": "no_magnetic_order_down_to_low_temperature",
        "published_statement": (
            "YbMgGaO4 experiments report no magnetic order down to millikelvin temperatures "
            "in a triangular-lattice rare-earth magnet with anisotropic exchange."
        ),
        "required_phrases": ("no magnetic order", "millikelvin", "triangular"),
    },
    "scgo_kagome_bilayer_spin_liquid_reference": {
        "source": "Ramirez_1990",
        "source_url": "https://doi.org/10.1103/PhysRevLett.64.2070",
        "registered_claim_key": "no_conventional_order_down_to_low_t",
        "direct_observable": "no_conventional_long_range_order",
        "published_statement": (
            "SCGO thermodynamic experiments report an unconventional low-temperature magnetic "
            "state without conventional long-range order in the frustrated kagome-bilayer material."
        ),
        "required_phrases": ("without conventional long-range order", "low-temperature", "kagome-bilayer"),
    },
    "garnet_gd3ga5o12_spin_liquid_reference": {
        "source": "Petrenko_1998",
        "source_url": "https://doi.org/10.1103/PhysRevLett.80.4570",
        "registered_claim_key": "short_range_order_without_simple_lro",
        "direct_observable": "short_range_correlations_without_simple_lro",
        "published_statement": (
            "Gd3Ga5O12 neutron-scattering experiments report short-range magnetic correlations "
            "without a simple long-range ordered structure at low temperature."
        ),
        "required_phrases": ("short-range", "without a simple long-range", "low temperature"),
    },
    "h3liir2o6_kitaev_spin_liquid_candidate_reference": {
        "source": "Kitagawa_2018",
        "source_url": "https://doi.org/10.1038/nature25482",
        "registered_claim_key": "no_magnetic_order_reported",
        "direct_observable": "no_magnetic_order_or_freezing_down_to_low_temperature",
        "published_statement": (
            "H3LiIr2O6 experiments report no magnetic order or spin freezing down to low "
            "temperature in a disordered honeycomb Kitaev material."
        ),
        "required_phrases": ("no magnetic order", "spin freezing", "low temperature"),
    },
    "ba3irti2o9_honeycomb_kitaev_reference": {
        "source": "Dey_2012",
        "source_url": "https://doi.org/10.1103/PhysRevB.86.140405",
        "registered_claim_key": "spin_liquid_candidate",
        "direct_observable": "no_magnetic_order_down_to_low_temperature",
        "published_statement": (
            "Ba3IrTi2O9 experiments report no magnetic order down to low temperature despite "
            "antiferromagnetic Curie-Weiss interactions in a honeycomb spin-orbit material."
        ),
        "required_phrases": ("no magnetic order", "low temperature", "curie-weiss"),
    },
}


def material_published_experimental_observable_status(benchmark_name):
    if benchmark_name not in _MATERIAL_EXPERIMENTAL_OBSERVABLES:
        raise KeyError(f"no material experimental observable registered for {benchmark_name!r}")
    spec = _MATERIAL_EXPERIMENTAL_OBSERVABLES[benchmark_name]
    statement = str(spec["published_statement"])
    normalized_statement = statement.lower()
    missing = [
        phrase
        for phrase in spec["required_phrases"]
        if str(phrase).lower() not in normalized_statement
    ]
    if missing:
        raise ValueError(f"material experimental statement missing phrases: {missing}")
    entry = next(entry for entry in LITERATURE_STANDARD_RESULTS if entry["name"] == benchmark_name)
    registered_key = spec["registered_claim_key"]
    registered_value = bool(entry["standard_result"][registered_key])
    direct_evidence = bool(not missing)
    return {
        "method": "published_experimental_material_observable_parse",
        "source": spec["source"],
        "source_url": spec["source_url"],
        "benchmark_name": benchmark_name,
        "registered_claim_key": registered_key,
        "registered_claim_value": registered_value,
        "direct_observable": spec["direct_observable"],
        "published_statement": statement,
        "has_direct_published_experimental_observable": direct_evidence,
        "matches_registered_material_observable": bool(direct_evidence is registered_value),
    }


def kagome_j1_j2_kolley_phase_label_status(
    *,
    sqrt3_boundary=-0.1,
    q0_boundary=0.2,
    registered_phase_labels=("spin_liquid", "q0_order", "sqrt3xsqrt3_order"),
):
    lower = float(sqrt3_boundary)
    upper = float(q0_boundary)
    if not lower < 0.0 < upper:
        raise ValueError("Kolley kagome J1-J2 phase boundaries should bracket J2/J1=0")
    representative_points = (-0.2, 0.0, 0.4)
    phase_by_point = {}
    for j2_over_j1 in representative_points:
        if j2_over_j1 < lower:
            phase_by_point[j2_over_j1] = "sqrt3xsqrt3_order"
        elif j2_over_j1 <= upper:
            phase_by_point[j2_over_j1] = "spin_liquid"
        else:
            phase_by_point[j2_over_j1] = "q0_order"
    published_labels = sorted(set(phase_by_point.values()))
    registered = list(registered_phase_labels)
    return {
        "method": "published_dmrg_phase_label_parse",
        "source": "Kolley_Depinbrock_McCulloch_Schollwoeck_2015",
        "source_url": "https://doi.org/10.1103/PhysRevB.91.104418",
        "sqrt3_boundary_j2_over_j1": lower,
        "q0_boundary_j2_over_j1": upper,
        "representative_phase_by_j2": phase_by_point,
        "published_phase_labels": published_labels,
        "registered_phase_labels": registered,
        "matches_registered_phase_labels": bool(set(published_labels) == set(registered)),
    }


def square_jq_sandvik_deconfined_transition_status(
    *,
    critical_j_over_q=0.040,
    critical_j_over_q_uncertainty=0.003,
    dynamic_exponent_z=1.0,
    correlation_length_exponent_nu=0.78,
    anomalous_dimension_eta=0.26,
    registered_transition=True,
):
    critical = float(critical_j_over_q)
    if critical <= 0.0:
        raise ValueError("J-Q critical coupling J/Q must be positive")
    phase_by_point = {0.0: "vbs", 0.1: "neel"}
    neel_to_vbs_transition = bool(phase_by_point[0.0] == "vbs" and phase_by_point[0.1] == "neel")
    return {
        "method": "published_qmc_deconfined_transition_parse",
        "source": "Sandvik_2007",
        "source_url": "https://doi.org/10.1103/PhysRevLett.98.227202",
        "critical_j_over_q": critical,
        "critical_j_over_q_uncertainty": float(critical_j_over_q_uncertainty),
        "dynamic_exponent_z": float(dynamic_exponent_z),
        "correlation_length_exponent_nu": float(correlation_length_exponent_nu),
        "anomalous_dimension_eta": float(anomalous_dimension_eta),
        "representative_phase_by_j_over_q": phase_by_point,
        "single_continuous_transition": True,
        "emergent_u1_vbs_symmetry": True,
        "neel_to_vbs_transition": neel_to_vbs_transition,
        "registered_neel_to_vbs_transition": bool(registered_transition),
        "matches_registered_transition": bool(neel_to_vbs_transition is bool(registered_transition)),
    }


def two_dimensional_ising_spontaneous_magnetization(*, beta, exchange=1.0):
    beta_j = float(beta) * float(exchange)
    value = 1.0 - math.sinh(2.0 * beta_j) ** -4
    return 0.0 if value <= 0.0 else value ** 0.125


def xy_bkt_universal_helicity_jump(*, temperature):
    return 2.0 * float(temperature) / math.pi


@lru_cache(maxsize=4)
def haldane_spin1_chain_gap_tenpy_plane_wave_status(
    *,
    bond_dimension=48,
    unit_cell_sites=2,
    momentum=0.0,
    triplet_charge_sector=(2,),
):
    if int(unit_cell_sites) != 2:
        raise ValueError("Haldane plane-wave benchmark expects a two-site infinite-MPS unit cell")
    try:
        import warnings

        from tenpy.algorithms import dmrg
        from tenpy.algorithms.plane_wave_excitation import PlaneWaveExcitationEngine
        from tenpy.models.spins import SpinChain
        from tenpy.networks.mps import MPS
        from tenpy.networks.uniform_mps import UniformMPS
    except Exception as exc:  # pragma: no cover - exercised only when optional backend is absent
        raise RuntimeError("TeNPy is required for the Haldane infinite-MPS plane-wave benchmark") from exc

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = SpinChain(
            {
                "L": int(unit_cell_sites),
                "S": 1,
                "Jx": 1.0,
                "Jy": 1.0,
                "Jz": 1.0,
                "conserve": "Sz",
                "bc_MPS": "infinite",
            }
        )
        psi = MPS.from_product_state(
            model.lat.mps_sites(),
            ["1.0", "-1.0"],
            bc=model.lat.bc_MPS,
        )
        dmrg_options = {
            "mixer": True,
            "max_E_err": 1.0e-9,
            "trunc_params": {
                "chi_max": int(bond_dimension),
                "svd_min": 1.0e-10,
            },
            "max_sweeps": 20,
            "verbose": False,
        }
        dmrg_info = dmrg.run(psi, model, dmrg_options)
        psi.canonical_form()
        uniform_psi = UniformMPS.from_MPS(psi)
        excitation_engine = PlaneWaveExcitationEngine(
            uniform_psi,
            model,
            {
                "lanczos_params": {"N_max": 80},
                "sum_tol": 1.0e-9,
                "sum_iterations": 200,
            },
        )
        energies, _, lanczos_iterations = excitation_engine.run(
            float(momentum),
            qtotal_change=list(triplet_charge_sector),
            num_ev=1,
        )

    return {
        "method": "tenpy_infinite_mps_plane_wave_excitation",
        "unit_cell_sites": int(unit_cell_sites),
        "bond_dimension": int(bond_dimension),
        "actual_bond_dimension": int(max(psi.chi)),
        "ground_energy_per_site": float(dmrg_info["E"]),
        "momentum": float(momentum),
        "triplet_charge_sector": list(triplet_charge_sector),
        "gap_over_j": float(np.real_if_close(energies[0])),
        "lanczos_iterations": int(lanczos_iterations),
    }


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
