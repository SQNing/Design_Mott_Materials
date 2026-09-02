import math
import sys
from pathlib import Path

import numpy as np
import pytest


SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(SKILL_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT / "scripts"))


def test_local_spectrum_analyzes_any_hermitian_local_matrix():
    from cli.simplify_text_input import run_simplification_from_normalized_model
    from common.model_analysis import run_model_analysis
    from input.normalize_input import normalize_input

    normalized = normalize_input(
        {
            "representation": "matrix",
            "support": [0],
            "matrix": [[1, 0, 0], [0, 0, 0], [0, 0, 1]],
            "local_dim": 3,
            "classical_bond_label": "spin-only",
        }
    )
    product_result = run_simplification_from_normalized_model(normalized)

    analysis = run_model_analysis(
        product_result,
        {"task": "local_spectrum"},
    )

    assert analysis["status"] == "ok"
    assert analysis["task"] == "local_spectrum"
    assert analysis["matrix_dimension"] == 3
    assert analysis["eigenvalues"] == pytest.approx([0.0, 1.0, 1.0])


def test_local_spectrum_can_derive_a_gap_without_model_specific_logic():
    from common.model_analysis import run_model_analysis

    analysis = run_model_analysis(
        {
            "status": "ok",
            "local_term_record": {
                "representation": {
                    "kind": "matrix",
                    "value": [
                        [-0.75, 0.0, 0.0, 0.0],
                        [0.0, 0.25, 0.0, 0.0],
                        [0.0, 0.0, 0.25, 0.0],
                        [0.0, 0.0, 0.0, 0.25],
                    ],
                }
            },
        },
        {
            "task": "local_spectrum",
            "observable": "spectral_gap",
            "units": "energy",
        },
    )

    assert analysis["status"] == "ok"
    assert analysis["value"] == pytest.approx(1.0)
    assert analysis["ground_state_energy"] == pytest.approx(-0.75)
    assert analysis["ground_state_degeneracy"] == 1
    assert analysis["spectral_gap"] == pytest.approx(1.0)


def test_unknown_model_analysis_is_reported_as_unsupported():
    from common.model_analysis import run_model_analysis

    analysis = run_model_analysis(
        {"status": "ok"},
        {"task": "paper_specific_answer"},
    )

    assert analysis == {
        "status": "unsupported",
        "task": "paper_specific_answer",
        "blocker": "unsupported model analysis task: paper_specific_answer",
    }


def test_scalar_root_solves_an_answer_free_equation_with_a_bracket():
    from common.model_analysis import run_model_analysis

    analysis = run_model_analysis(
        {"status": "ok"},
        {
            "task": "scalar_root",
            "variable": "x",
            "equation": "x**2 - scale",
            "parameters": {"scale": 2.0},
            "bracket": [1.0, 2.0],
            "absolute_tolerance": 1.0e-12,
            "observable": "positive_root",
            "units": "dimensionless",
        },
    )

    assert analysis["status"] == "ok"
    assert analysis["task"] == "scalar_root"
    assert analysis["observable"] == "positive_root"
    assert analysis["units"] == "dimensionless"
    assert analysis["value"] == pytest.approx(2.0**0.5, abs=1.0e-12)
    assert analysis["residual"] <= 1.0e-12
    assert analysis["bracket_width"] <= 2.0e-12


def test_one_dimensional_transfer_matrix_handles_a_generic_finite_state_chain():
    from common.model_analysis import run_model_analysis

    pair_energies = [
        [0.0, 0.4, 0.9],
        [0.4, -0.2, 0.3],
        [0.9, 0.3, 0.1],
    ]
    local_matrix = [[0.0 for _ in range(9)] for _ in range(9)]
    for left in range(3):
        for right in range(3):
            index = 3 * left + right
            local_matrix[index][index] = pair_energies[left][right]
    product_result = {
        "status": "ok",
        "lattice": {"kind": "chain", "dimension": 1},
        "normalized_model": {
            "lattice_structure": {
                "basis_sites": [{"site_ref": "site:0"}],
            }
        },
        "local_term_record": {
            "support": [0, 1],
            "local_basis_order": ["a", "b", "c"],
            "representation": {"kind": "matrix", "value": local_matrix},
        },
    }

    analysis = run_model_analysis(
        product_result,
        {
            "task": "one_dimensional_transfer_matrix",
            "diagnostic_temperatures": [0.5, 1.0, 2.0],
            "observable": "critical_temperature",
            "units": "energy/k_B",
        },
    )

    assert analysis["status"] == "ok"
    assert analysis["value"] == 0.0
    assert analysis["finite_temperature_transition"] is False
    assert analysis["proof_kind"] == "positive_finite_transfer_matrix"
    assert len(analysis["diagnostics"]) == 3
    assert all(row["spectral_gap"] > 0.0 for row in analysis["diagnostics"])


def test_classical_sz_enumeration_derives_energy_levels_from_canonical_terms():
    from common.model_analysis import run_model_analysis

    product_result = {
        "status": "ok",
        "canonical_model": {
            "one_body": [],
            "two_body": [
                {
                    "canonical_label": label,
                    "coefficient": 4.0,
                }
                for label in (
                    "Sz@0 Sz@1",
                    "Sz@0 Sz@2",
                    "Sz@1 Sz@2",
                )
            ],
            "three_body": [],
            "four_body": [],
            "higher_body": [],
        },
    }

    analysis = run_model_analysis(
        product_result,
        {
            "task": "classical_sz_enumeration",
            "observable": "energy_levels",
            "units": "J",
        },
    )

    assert analysis["status"] == "ok"
    assert analysis["configuration_count"] == 8
    assert analysis["ground_state_degeneracy"] == 6
    assert analysis["value"] == [
        {"energy": -1.0, "degeneracy": 6},
        {"energy": 3.0, "degeneracy": 2},
    ]


def test_periodic_classical_sz_enumeration_uses_lattice_bond_translations():
    from common.model_analysis import run_model_analysis

    product_result = {
        "status": "ok",
        "canonical_model": {
            "one_body": [],
            "two_body": [
                {
                    "canonical_label": "Sz@0 Sz@1",
                    "coefficient": -4.0,
                }
            ],
            "three_body": [],
            "four_body": [],
            "higher_body": [],
        },
        "normalized_model": {
            "lattice_structure": {
                "dimension": 1,
                "basis_sites": [{"site_ref": "site:0"}],
                "bond_orbits": [
                    {
                        "orbit_ref": "bond-orbit:nearest",
                        "members": [
                            {
                                "source": 0,
                                "target": 0,
                                "translation": [1, 0, 0],
                            }
                        ],
                    }
                ],
            }
        },
    }

    analysis = run_model_analysis(
        product_result,
        {
            "task": "periodic_classical_sz_enumeration",
            "bond_orbit_ref": "bond-orbit:nearest",
            "supercells": [[4]],
            "observable": "finite_size_residual_entropy",
            "units": "k_B/spin",
        },
    )

    assert analysis["status"] == "ok"
    assert analysis["ground_state_degeneracy"] == 2
    assert analysis["ground_state_energy"] == pytest.approx(-4.0)
    assert analysis["value"] == pytest.approx(math.log(2.0) / 4.0)
    assert analysis["finite_size_estimates"] == [
        {
            "supercell": [4],
            "site_count": 4,
            "bond_count": 4,
            "ground_state_energy": -4.0,
            "ground_state_degeneracy": 2,
            "entropy_per_site": pytest.approx(math.log(2.0) / 4.0),
        }
    ]


def test_finite_cluster_ed_assembles_spin_terms_over_explicit_bonds():
    from common.model_analysis import run_model_analysis

    product_result = {
        "status": "ok",
        "canonical_model": {
            "one_body": [],
            "two_body": [
                {"canonical_label": f"{axis}@0 {axis}@1", "coefficient": 1.0}
                for axis in ("Sx", "Sy", "Sz")
            ],
            "three_body": [],
            "four_body": [],
            "higher_body": [],
        },
        "normalized_model": {
            "lattice": {"dimension": 0},
            "lattice_structure": {
                "basis_sites": [
                    {"site_ref": f"site:{site}"} for site in range(3)
                ],
                "bond_orbits": [
                    {
                        "orbit_ref": "bond-orbit:triangle",
                        "members": [
                            {"source": 0, "target": 1, "translation": [0, 0, 0]},
                            {"source": 1, "target": 2, "translation": [0, 0, 0]},
                            {"source": 2, "target": 0, "translation": [0, 0, 0]},
                        ],
                    }
                ],
            },
            "local_hilbert": {
                "sites": [
                    {"site_ref": f"site:{site}", "basis_ref": "basis:spin_half"}
                    for site in range(3)
                ],
                "basis_registry": {
                    "basis:spin_half": {"dimension": 2},
                },
            },
        },
    }

    analysis = run_model_analysis(
        product_result,
        {
            "task": "finite_cluster_ed",
            "bond_orbit_ref": "bond-orbit:triangle",
            "supercell": [],
            "observable": "spectrum",
            "units": "J",
        },
    )

    assert analysis["status"] == "ok"
    assert analysis["site_count"] == 3
    assert analysis["matrix_dimension"] == 8
    assert analysis["ground_state_energy"] == pytest.approx(-0.75)
    assert analysis["ground_state_degeneracy"] == 4
    assert analysis["spectral_gap"] == pytest.approx(1.5)
    assert analysis["eigenvalues"] == pytest.approx(
        [-0.75] * 4 + [0.75] * 4
    )


def test_ising_chain_free_fermion_analysis_extracts_couplings_from_model():
    from common.model_analysis import run_model_analysis

    analysis = run_model_analysis(
        {
            "status": "ok",
            "canonical_model": {
                "two_body": [
                    {
                        "canonical_label": "Sz@0 Sz@1",
                        "coefficient": -6.8,
                    }
                ],
                "onsite_terms": [
                    {
                        "kind": "linear_spin_cartesian",
                        "payload": {"vector": [-0.8, 0.0, 0.0]},
                    }
                ],
            },
            "normalized_model": {
                "lattice": {"kind": "chain", "dimension": 1},
                "lattice_structure": {
                    "basis_sites": [{"site_ref": "site:0"}],
                },
            },
        },
        {
            "task": "ising_chain_free_fermion",
            "observable": "critical_field",
            "momenta": [0.0, 1.0, 2.0, 3.141592653589793],
            "units": "energy",
        },
    )

    assert analysis["status"] == "ok"
    assert analysis["exchange"] == pytest.approx(1.7)
    assert analysis["field"] == pytest.approx(0.4)
    assert analysis["value"] == pytest.approx(1.7)
    assert analysis["current_gap"] == pytest.approx(2.6)
    assert analysis["critical_gap_residual"] == pytest.approx(0.0)
    assert len(analysis["dispersion_samples"]) == 4


def test_xx_chain_free_fermion_energy_comes_from_refined_momentum_integral():
    from common.model_analysis import run_model_analysis

    analysis = run_model_analysis(
        {
            "status": "ok",
            "canonical_model": {
                "two_body": [
                    {"canonical_label": "Sx@0 Sx@1", "coefficient": 2.3},
                    {"canonical_label": "Sy@0 Sy@1", "coefficient": 2.3},
                ],
                "onsite_terms": [],
            },
            "normalized_model": {
                "lattice": {"kind": "chain", "dimension": 1},
                "lattice_structure": {
                    "basis_sites": [{"site_ref": "site:0"}],
                },
            },
        },
        {
            "task": "xx_chain_free_fermion",
            "observable": "ground_state_energy_per_site",
            "grid_sizes": [2048, 4096],
            "units": "J",
        },
    )

    assert analysis["status"] == "ok"
    assert analysis["exchange"] == pytest.approx(2.3)
    assert analysis["value"] == pytest.approx(-2.3 / math.pi, abs=1.0e-6)
    assert len(analysis["grid_estimates"]) == 2
    assert analysis["refinement_difference"] < 1.0e-6


def test_spin_one_bilinear_biquadratic_coefficients_are_fit_from_matrix():
    from common.model_analysis import run_model_analysis

    root_two = math.sqrt(2.0)
    sx = np.asarray(
        [[0.0, 1.0 / root_two, 0.0],
         [1.0 / root_two, 0.0, 1.0 / root_two],
         [0.0, 1.0 / root_two, 0.0]],
        dtype=complex,
    )
    sy = np.asarray(
        [[0.0, -1.0j / root_two, 0.0],
         [1.0j / root_two, 0.0, -1.0j / root_two],
         [0.0, 1.0j / root_two, 0.0]],
        dtype=complex,
    )
    sz = np.diag([1.0, 0.0, -1.0]).astype(complex)
    dot = sum(np.kron(component, component) for component in (sx, sy, sz))
    matrix = 0.7 * np.eye(9) + 1.8 * dot + 0.6 * (dot @ dot)

    analysis = run_model_analysis(
        {
            "status": "ok",
            "local_term_record": {
                "support": [0, 1],
                "representation": {
                    "kind": "matrix",
                    "value": matrix.tolist(),
                },
            },
        },
        {
            "task": "spin_one_bilinear_biquadratic_decomposition",
            "observable": "coefficient_summary",
            "units": "model_energy_units",
        },
    )

    assert analysis["status"] == "ok"
    assert analysis["constant_shift"] == pytest.approx(0.7)
    assert analysis["bilinear_coefficient"] == pytest.approx(1.8)
    assert analysis["biquadratic_coefficient"] == pytest.approx(0.6)
    assert analysis["value"] == pytest.approx(
        {
            "bilinear_biquadratic_ratio": 1.0 / 3.0,
            "theta_radians": math.atan(1.0 / 3.0),
            "su3_symmetric": False,
        }
    )
    assert analysis["reconstruction_residual"] < 1.0e-12


def test_local_constraint_entropy_is_derived_from_enumerated_ground_states():
    from common.model_analysis import run_model_analysis

    analysis = run_model_analysis(
        {
            "status": "ok",
            "canonical_model": {
                "one_body": [],
                "two_body": [
                    {
                        "canonical_label": "Sz@0 Sz@1",
                        "coefficient": 4.0,
                    }
                ],
                "three_body": [],
                "four_body": [],
                "higher_body": [],
            },
            "normalized_model": {
                "lattice_structure": {
                    "basis_sites": [
                        {"site_ref": f"site:{site}"} for site in range(4)
                    ],
                    "bond_orbits": [
                        {
                            "orbit_ref": "bond-orbit:tetrahedron",
                            "members": [
                                {
                                    "source": left,
                                    "target": right,
                                    "translation": [0, 0, 0],
                                }
                                for left, right in (
                                    (0, 1), (0, 2), (0, 3),
                                    (1, 2), (1, 3), (2, 3),
                                )
                            ],
                        }
                    ],
                }
            },
        },
        {
            "task": "local_constraint_entropy_estimate",
            "bond_orbit_ref": "bond-orbit:tetrahedron",
            "constraints_per_site": 0.5,
            "observable": "pauling_entropy_per_spin",
            "units": "k_B/spin",
        },
    )

    assert analysis["status"] == "ok"
    assert analysis["configuration_count"] == 16
    assert analysis["allowed_configuration_count"] == 6
    assert analysis["value"] == pytest.approx(0.5 * math.log(1.5))


def test_xy_chain_boundaries_are_derived_from_canonical_exchange_couplings():
    from common.model_analysis import run_model_analysis

    analysis = run_model_analysis(
        {
            "status": "ok",
            "canonical_model": {
                "two_body": [
                    {"canonical_label": "Sx@0 Sx@1", "coefficient": -3.0},
                    {"canonical_label": "Sy@0 Sy@1", "coefficient": -1.0},
                ],
                "onsite_terms": [
                    {"kind": "linear_spin_cartesian", "payload": {"vector": [0, 0, -0.4]}}
                ],
            },
            "normalized_model": {"lattice": {"kind": "chain", "dimension": 1}},
        },
        {
            "task": "xy_chain_free_fermion_boundaries",
            "observable": "critical_boundaries",
            "units": "dimensionless",
        },
    )

    assert analysis["status"] == "ok"
    assert analysis["exchange"] == pytest.approx(2.0)
    assert analysis["input_anisotropy"] == pytest.approx(0.5)
    assert analysis["value"] == pytest.approx(
        {
            "ising_critical_field": 2.0,
            "anisotropy_transition_gamma": 0.0,
        }
    )


def test_xxx_chain_bethe_energy_comes_from_refined_integral():
    from common.model_analysis import run_model_analysis

    analysis = run_model_analysis(
        {
            "status": "ok",
            "canonical_model": {
                "two_body": [
                    {"canonical_label": f"S{axis}@0 S{axis}@1", "coefficient": 1.7}
                    for axis in ("x", "y", "z")
                ],
                "onsite_terms": [],
            },
            "normalized_model": {"lattice": {"kind": "chain", "dimension": 1}},
        },
        {
            "task": "xxx_chain_bethe_integral",
            "quadrature_orders": [64, 128],
            "integration_cutoff": 40.0,
            "observable": "ground_state_energy_per_site",
            "units": "J",
        },
    )

    assert analysis["status"] == "ok"
    assert analysis["exchange"] == pytest.approx(1.7)
    assert analysis["value"] == pytest.approx(
        1.7 * (0.25 - math.log(2.0)), abs=1.0e-10
    )
    assert len(analysis["quadrature_estimates"]) == 2
    assert analysis["refinement_difference"] < 1.0e-9


def test_fourier_exchange_spectrum_is_built_from_bond_orbits():
    from common.model_analysis import run_model_analysis

    analysis = run_model_analysis(
        {
            "status": "ok",
            "canonical_model": {
                "two_body": [
                    {
                        "canonical_label": f"S{axis}@0 S{axis}@1",
                        "coefficient": 1.0,
                        "block_kind": "J1",
                    }
                    for axis in ("x", "y", "z")
                ],
                "onsite_terms": [],
            },
            "normalized_model": {
                "lattice": {
                    "kind": "dimer_chain",
                    "dimension": 1,
                    "positions": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
                    "lattice_vectors": [
                        [1.0, 0.0, 0.0],
                        [0.0, 8.0, 0.0],
                        [0.0, 0.0, 8.0],
                    ],
                },
                "lattice_structure": {
                    "basis_sites": [
                        {"site_ref": "site:0", "position": [0.0, 0.0, 0.0]},
                        {"site_ref": "site:1", "position": [0.5, 0.0, 0.0]},
                    ],
                    "bond_orbits": [
                        {
                            "orbit_ref": "bond-orbit:J1",
                            "members": [
                                {"source": 0, "target": 1, "translation": [0, 0, 0]},
                                {"source": 0, "target": 1, "translation": [-1, 0, 0]},
                            ],
                        }
                    ],
                },
            },
        },
        {
            "task": "fourier_exchange_spectrum",
            "term_orbit_map": {"J1": "bond-orbit:J1"},
            "reduced_momenta": [[0.0], [0.5]],
            "observable": "exchange_eigenvalues",
            "units": "J",
        },
    )

    assert analysis["status"] == "ok"
    assert analysis["spectra"][0]["eigenvalues"] == pytest.approx([-2.0, 2.0])
    assert analysis["spectra"][1]["eigenvalues"] == pytest.approx([0.0, 0.0], abs=1.0e-12)


def test_fourier_flat_band_projectors_diagnose_pyrochlore_constraint():
    from common.model_analysis import run_model_analysis

    edges = (
        (0, 1, (-1, 0, 0)), (0, 1, (0, 0, 0)),
        (0, 2, (0, -1, 0)), (0, 2, (0, 0, 0)),
        (0, 3, (0, 0, -1)), (0, 3, (0, 0, 0)),
        (1, 2, (0, 0, 0)), (1, 2, (1, -1, 0)),
        (1, 3, (0, 0, 0)), (1, 3, (1, 0, -1)),
        (2, 3, (0, 0, 0)), (2, 3, (0, 1, -1)),
    )
    analysis = run_model_analysis(
        {
            "status": "ok",
            "canonical_model": {
                "two_body": [
                    {
                        "canonical_label": f"S{axis}@0 S{axis}@1",
                        "coefficient": 1.0,
                        "block_kind": "J1",
                    }
                    for axis in ("x", "y", "z")
                ],
                "onsite_terms": [],
            },
            "normalized_model": {
                "lattice": {"kind": "pyrochlore", "dimension": 3},
                "lattice_structure": {
                    "basis_sites": [{"site_ref": f"site:{site}"} for site in range(4)],
                    "bond_orbits": [
                        {
                            "orbit_ref": "bond-orbit:J1",
                            "members": [
                                {"source": source, "target": target, "translation": list(translation)}
                                for source, target, translation in edges
                            ],
                        }
                    ],
                },
            },
        },
        {
            "task": "fourier_exchange_spectrum",
            "term_orbit_map": {"J1": "bond-orbit:J1"},
            "reduced_momenta": [
                [0.001, 0.0, 0.0],
                [0.0, 0.001, 0.0],
                [0.0, 0.0, 0.001],
                [0.13, 0.27, 0.31],
            ],
            "flat_band_count": 2,
            "observable": "flat_band_constraint_summary",
            "units": "dimensionless",
        },
    )

    assert analysis["status"] == "ok"
    assert analysis["value"] == {
        "zero_total_spin_per_tetrahedron": True,
        "pinch_points": True,
    }
    assert analysis["flat_band_width"] < 1.0e-10
    assert analysis["directional_projector_difference"] > 1.0e-3


def test_bravais_fourier_competing_order_boundary_is_solved_from_orbits():
    from common.model_analysis import run_model_analysis

    orbit_members = {
        "J1": [(1, 0, 0), (0, 1, 0), (0, 0, 1)],
        "J2": [
            (1, 1, 0), (1, -1, 0),
            (1, 0, 1), (1, 0, -1),
            (0, 1, 1), (0, 1, -1),
        ],
    }
    analysis = run_model_analysis(
        {
            "status": "ok",
            "canonical_model": {
                "two_body": [
                    {
                        "canonical_label": f"S{axis}@0 S{axis}@1",
                        "coefficient": coefficient,
                        "block_kind": block,
                    }
                    for block, coefficient in (("J1", 1.0), ("J2", 0.3))
                    for axis in ("x", "y", "z")
                ],
                "onsite_terms": [],
            },
            "normalized_model": {
                "lattice": {"kind": "simple_cubic", "dimension": 3},
                "lattice_structure": {
                    "basis_sites": [{"site_ref": "site:0"}],
                    "bond_orbits": [
                        {
                            "orbit_ref": f"bond-orbit:{block}",
                            "members": [
                                {"source": 0, "target": 0, "translation": list(vector)}
                                for vector in vectors
                            ],
                        }
                        for block, vectors in orbit_members.items()
                    ],
                },
            },
        },
        {
            "task": "bravais_fourier_competing_order_boundary",
            "term_orbit_map": {
                "J1": "bond-orbit:J1",
                "J2": "bond-orbit:J2",
            },
            "reference_block": "J1",
            "varied_block": "J2",
            "competing_momenta": [[0.5, 0.5, 0.5], [0.5, 0.5, 0.0]],
            "observable": "critical_ratio",
            "units": "J2/J1",
        },
    )

    assert analysis["status"] == "ok"
    assert analysis["value"] == pytest.approx(0.25)
    assert analysis["energy_crossing_residual"] < 1.0e-12


def test_multisublattice_fourier_curvature_finds_diamond_spiral_onset():
    from common.model_analysis import run_model_analysis

    nearest = (
        (0, 1, (-1, 0, 0)), (0, 1, (0, -1, 0)),
        (0, 1, (0, 0, -1)), (0, 1, (0, 0, 0)),
    )
    next_vectors = (
        (-1, 0, 0), (-1, 0, 1), (-1, 1, 0),
        (0, -1, 0), (0, -1, 1), (0, 0, -1),
    )
    next_nearest = tuple(
        (site, site, vector) for site in (0, 1) for vector in next_vectors
    )
    analysis = run_model_analysis(
        {
            "status": "ok",
            "canonical_model": {
                "two_body": [
                    {
                        "canonical_label": f"S{axis}@0 S{axis}@1",
                        "coefficient": coefficient,
                        "block_kind": block,
                    }
                    for block, coefficient in (("J1", 1.0), ("J2", 0.15))
                    for axis in ("x", "y", "z")
                ],
                "onsite_terms": [],
            },
            "normalized_model": {
                "lattice": {"kind": "diamond", "dimension": 3},
                "lattice_structure": {
                    "basis_sites": [{"site_ref": "site:0"}, {"site_ref": "site:1"}],
                    "bond_orbits": [
                        {
                            "orbit_ref": "bond-orbit:J1",
                            "members": [
                                {"source": a, "target": b, "translation": list(t)}
                                for a, b, t in nearest
                            ],
                        },
                        {
                            "orbit_ref": "bond-orbit:J2",
                            "members": [
                                {"source": a, "target": b, "translation": list(t)}
                                for a, b, t in next_nearest
                            ],
                        },
                    ],
                },
            },
        },
        {
            "task": "fourier_curvature_instability_boundary",
            "term_orbit_map": {"J1": "bond-orbit:J1", "J2": "bond-orbit:J2"},
            "reference_block": "J1",
            "varied_block": "J2",
            "central_momentum": [0.0, 0.0, 0.0],
            "momentum_displacement": [0.001, 0.0, 0.0],
            "ratio_bracket": [0.05, 0.2],
            "absolute_tolerance": 1.0e-10,
            "observable": "spiral_onset_j2_over_j1",
            "units": "J2/J1",
        },
    )

    assert analysis["status"] == "ok"
    assert analysis["value"] == pytest.approx(0.125, abs=1.0e-6)
    assert analysis["curvature_residual"] < 1.0e-8


def test_kitaev_majorana_gap_is_derived_from_exchange_and_field():
    from common.model_analysis import run_model_analysis

    analysis = run_model_analysis(
        {
            "status": "ok",
            "canonical_model": {
                "two_body": [
                    {
                        "canonical_label": f"S{axis}@0 S{axis}@1",
                        "coefficient": 1.0,
                        "block_kind": f"{axis}_bond",
                    }
                    for axis in ("x", "y", "z")
                ],
                "onsite_terms": [
                    {
                        "kind": "linear_spin_cartesian",
                        "payload": {"vector": [-0.1, -0.08, -0.06]},
                    }
                ],
            },
            "normalized_model": {
                "lattice": {"kind": "honeycomb", "dimension": 2}
            },
        },
        {
            "task": "kitaev_majorana_field_gap",
            "observable": "field_opens_non_abelian_gap",
            "units": "dimensionless",
        },
    )

    assert analysis["status"] == "ok"
    assert analysis["value"] is True
    assert analysis["majorana_gap"] > 0.0
    assert analysis["mass_sign"] == 1
    assert analysis["dirac_residual"] < 1.0e-12


def test_pauli_stabilizer_rank_derives_toric_ground_space():
    from common.model_analysis import run_model_analysis

    size = 2
    horizontal = lambda x, y: y * size + x
    vertical = lambda x, y: size * size + y * size + x
    terms = []
    for y in range(size):
        for x in range(size):
            star = (
                horizontal(x, y), horizontal((x - 1) % size, y),
                vertical(x, y), vertical(x, (y - 1) % size),
            )
            plaquette = (
                horizontal(x, y), vertical((x + 1) % size, y),
                horizontal(x, (y + 1) % size), vertical(x, y),
            )
            terms.append({
                "canonical_label": " ".join(f"Sx@{site}" for site in star),
                "coefficient": 16.0,
                "block_kind": f"star_{x}_{y}",
            })
            terms.append({
                "canonical_label": " ".join(f"Sz@{site}" for site in plaquette),
                "coefficient": 16.0,
                "block_kind": f"plaquette_{x}_{y}",
            })

    analysis = run_model_analysis(
        {
            "status": "ok",
            "canonical_model": {
                "four_body": terms,
                "one_body": [], "two_body": [], "three_body": [],
                "higher_body": [], "onsite_terms": [],
            },
        },
        {
            "task": "pauli_stabilizer_rank",
            "qubit_count": 8,
            "observable": "torus_ground_state_degeneracy",
            "units": "states",
        },
    )

    assert analysis["status"] == "ok"
    assert analysis["stabilizer_rank"] == 6
    assert analysis["logical_qubit_count"] == 2
    assert analysis["value"] == 4
    assert analysis["maximum_symplectic_commutator"] == 0


def test_ising_strip_transfer_extrapolates_fully_frustrated_entropy():
    from common.model_analysis import run_model_analysis

    analysis = run_model_analysis(
        {
            "status": "ok",
            "canonical_model": {
                "two_body": [
                    {"canonical_label": "Sz@0 Sz@1", "coefficient": -4.0, "block_kind": "horizontal"},
                    {"canonical_label": "Sz@0 Sz@1", "coefficient": -4.0, "block_kind": "vertical_even"},
                    {"canonical_label": "Sz@0 Sz@1", "coefficient": 4.0, "block_kind": "vertical_odd"},
                ],
                "onsite_terms": [],
            },
            "normalized_model": {
                "lattice": {"kind": "square_fully_frustrated", "dimension": 2},
                "lattice_structure": {
                    "basis_sites": [{"site_ref": "site:0"}, {"site_ref": "site:1"}],
                    "bond_orbits": [
                        {"orbit_ref": "bond-orbit:horizontal", "members": [
                            {"source": 0, "target": 1, "translation": [0, 0, 0]},
                            {"source": 1, "target": 0, "translation": [1, 0, 0]},
                        ]},
                        {"orbit_ref": "bond-orbit:vertical_even", "members": [
                            {"source": 0, "target": 0, "translation": [0, 1, 0]},
                        ]},
                        {"orbit_ref": "bond-orbit:vertical_odd", "members": [
                            {"source": 1, "target": 1, "translation": [0, 1, 0]},
                        ]},
                    ],
                },
            },
        },
        {
            "task": "ising_strip_transfer_entropy",
            "term_orbit_map": {
                "horizontal": "bond-orbit:horizontal",
                "vertical_even": "bond-orbit:vertical_even",
                "vertical_odd": "bond-orbit:vertical_odd",
            },
            "strip_cell_widths": [3, 4, 5, 6],
            "inverse_temperatures": [15.0, 16.0],
            "observable": "residual_entropy_per_spin",
            "units": "k_B/spin",
        },
    )

    assert analysis["status"] == "ok"
    assert [row["site_width"] for row in analysis["width_estimates"]] == [6, 8, 10, 12]
    assert analysis["value"] == pytest.approx(0.2915609, abs=2.0e-5)
    assert analysis["fit_stability_difference"] < 2.0e-5
