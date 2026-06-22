import math
import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from classical import cpn_generalized_lt_solver as glt


def _serialize_complex(value):
    return {"real": float(np.real(value)), "imag": float(np.imag(value))}


def _serialized_tensor_from_coupling(coupling):
    basis = glt._orthonormal_hermitian_basis(2)
    tensor = np.einsum("mn,mab,ncd->abcd", np.asarray(coupling, dtype=float), basis, basis, optimize=True)
    return [
        [
            [
                [_serialize_complex(tensor[a, b, c, d]) for d in range(2)]
                for c in range(2)
            ]
            for b in range(2)
        ]
        for a in range(2)
    ]


def _cp1_harmonic_model(harmonics):
    bonds = []
    for period, coefficient in harmonics:
        if isinstance(period, int):
            vector = [int(period), 0, 0]
        else:
            vector = [int(value) for value in period]
        coupling = np.zeros((4, 4), dtype=float)
        coupling[1, 1] = float(coefficient)
        bonds.append(
            {
                "source": 0,
                "target": 0,
                "R": vector,
                "tensor": _serialized_tensor_from_coupling(coupling),
            }
        )
    return {
        "classical_manifold": "CP^(N-1)",
        "local_dimension": 2,
        "magnetic_site_count": 1,
        "bond_tensors": bonds,
    }


def _cp1_isotropic_heisenberg_chain_model(j1, j2):
    return _cp1_isotropic_heisenberg_model_from_bonds([((1, 0, 0), j1), ((2, 0, 0), j2)])


def _cp1_isotropic_heisenberg_model_from_bonds(bondspec):
    bonds = []
    for vector, coefficient in bondspec:
        coupling = np.zeros((4, 4), dtype=float)
        coupling[1, 1] = float(coefficient)
        coupling[2, 2] = float(coefficient)
        coupling[3, 3] = float(coefficient)
        bonds.append(
            {
                "source": 0,
                "target": 0,
                "R": [int(value) for value in vector],
                "tensor": _serialized_tensor_from_coupling(coupling),
            }
        )
    return {
        "classical_manifold": "CP^(N-1)",
        "local_dimension": 2,
        "magnetic_site_count": 1,
        "bond_tensors": bonds,
    }


def _cp1_isotropic_heisenberg_multisite_model(magnetic_site_count, bondspec):
    bonds = []
    for source, target, vector, coefficient in bondspec:
        coupling = np.zeros((4, 4), dtype=float)
        coupling[1, 1] = float(coefficient)
        coupling[2, 2] = float(coefficient)
        coupling[3, 3] = float(coefficient)
        bonds.append(
            {
                "source": int(source),
                "target": int(target),
                "R": [int(value) for value in vector],
                "tensor": _serialized_tensor_from_coupling(coupling),
            }
        )
    return {
        "classical_manifold": "CP^(N-1)",
        "local_dimension": 2,
        "magnetic_site_count": int(magnetic_site_count),
        "magnetic_sites": [{"label": f"site-{index}"} for index in range(int(magnetic_site_count))],
        "bond_tensors": bonds,
    }


def _literature_j1_j2_spiral_q(j1, j2):
    # Sirker et al., PRB 84, 144403: classical FM-AFM J1-J2 chain pitch.
    ratio = -float(j1) / (4.0 * float(j2))
    if ratio >= 1.0:
        return 0.0
    if ratio <= -1.0:
        return 0.5
    return math.acos(ratio) / (2.0 * math.pi)


def _square_lattice_j1_j2_model(j1, j2):
    return _cp1_isotropic_heisenberg_model_from_bonds(
        [
            ((1, 0, 0), j1),
            ((0, 1, 0), j1),
            ((1, 1, 0), j2),
            ((1, -1, 0), j2),
        ]
    )


def _square_lattice_j1_j3_model(j1, j3):
    return _cp1_isotropic_heisenberg_model_from_bonds(
        [
            ((1, 0, 0), j1),
            ((0, 1, 0), j1),
            ((2, 0, 0), j3),
            ((0, 2, 0), j3),
        ]
    )


def _literature_square_j1_j3_spiral_component(j1, j3):
    ratio = float(j1) / (4.0 * float(j3))
    if ratio >= 1.0:
        return 0.5
    q_shift = math.acos(ratio) / (2.0 * math.pi)
    return 0.5 - q_shift


def _triangular_lattice_nearest_neighbor_model(j1):
    return _cp1_isotropic_heisenberg_model_from_bonds(
        [
            ((1, 0, 0), j1),
            ((0, 1, 0), j1),
            ((1, -1, 0), j1),
        ]
    )


def _triangular_lattice_j1_j2_model(j1, j2):
    return _cp1_isotropic_heisenberg_model_from_bonds(
        [
            ((1, 0, 0), j1),
            ((0, 1, 0), j1),
            ((1, -1, 0), j1),
            ((1, 1, 0), j2),
            ((2, -1, 0), j2),
            ((1, -2, 0), j2),
        ]
    )


def _simple_cubic_j1_j2_model(j1, j2):
    return _cp1_isotropic_heisenberg_model_from_bonds(
        [
            ((1, 0, 0), j1),
            ((0, 1, 0), j1),
            ((0, 0, 1), j1),
            ((1, 1, 0), j2),
            ((1, -1, 0), j2),
            ((1, 0, 1), j2),
            ((1, 0, -1), j2),
            ((0, 1, 1), j2),
            ((0, 1, -1), j2),
        ]
    )


def _honeycomb_j1_j2_model(j1, j2):
    bonds = [
        (0, 1, (0, 0, 0), j1),
        (0, 1, (-1, 0, 0), j1),
        (0, 1, (0, -1, 0), j1),
    ]
    for site in (0, 1):
        bonds.extend(
            [
                (site, site, (1, 0, 0), j2),
                (site, site, (0, 1, 0), j2),
                (site, site, (1, -1, 0), j2),
            ]
        )
    return _cp1_isotropic_heisenberg_multisite_model(2, bonds)


def _honeycomb_spiral_ring_component_along_10(j1, j2):
    target_abs_f = abs(float(j1)) / (2.0 * abs(float(j2)))
    cos_argument = (target_abs_f * target_abs_f - 5.0) / 4.0
    return math.acos(cos_argument) / (2.0 * math.pi)


def _honeycomb_spiral_ring_x_value(j1, j2):
    target_abs_f = abs(float(j1)) / (2.0 * abs(float(j2)))
    return 0.5 * (target_abs_f * target_abs_f - 3.0)


def _kagome_nearest_neighbor_model(j1):
    return _cp1_isotropic_heisenberg_multisite_model(
        3,
        [
            (0, 1, (0, 0, 0), j1),
            (0, 1, (-1, 0, 0), j1),
            (0, 2, (0, 0, 0), j1),
            (0, 2, (0, -1, 0), j1),
            (1, 2, (0, 0, 0), j1),
            (1, 2, (1, -1, 0), j1),
        ],
    )


def _pyrochlore_nearest_neighbor_model(j1):
    return _cp1_isotropic_heisenberg_multisite_model(
        4,
        [
            (0, 1, (0, 0, 0), j1),
            (0, 1, (-1, 0, 0), j1),
            (0, 2, (0, 0, 0), j1),
            (0, 2, (0, -1, 0), j1),
            (0, 3, (0, 0, 0), j1),
            (0, 3, (0, 0, -1), j1),
            (1, 2, (0, 0, 0), j1),
            (1, 2, (1, -1, 0), j1),
            (1, 3, (0, 0, 0), j1),
            (1, 3, (1, 0, -1), j1),
            (2, 3, (0, 0, 0), j1),
            (2, 3, (0, 1, -1), j1),
        ],
    )


def _diamond_j1_j2_model(j1, j2):
    bonds = [
        (0, 1, (0, 0, 0), j1),
        (0, 1, (-1, 0, 0), j1),
        (0, 1, (0, -1, 0), j1),
        (0, 1, (0, 0, -1), j1),
    ]
    for site in (0, 1):
        bonds.extend(
            [
                (site, site, (1, 0, 0), j2),
                (site, site, (0, 1, 0), j2),
                (site, site, (0, 0, 1), j2),
                (site, site, (1, -1, 0), j2),
                (site, site, (1, 0, -1), j2),
                (site, site, (0, 1, -1), j2),
            ]
        )
    return _cp1_isotropic_heisenberg_multisite_model(2, bonds)


def _diamond_spiral_surface_q_110(j1, j2):
    target_abs_f = abs(float(j1)) / (2.0 * abs(float(j2)))
    return math.acos(target_abs_f / 4.0) / math.pi


def _diamond_spiral_surface_q_1_minus_10(j1, j2):
    target_abs_f = abs(float(j1)) / (2.0 * abs(float(j2)))
    return math.acos(math.sqrt(target_abs_f / 4.0)) / math.pi


def _diamond_spiral_surface_x_value(j1, j2):
    target_abs_f = abs(float(j1)) / (2.0 * abs(float(j2)))
    return 0.5 * (target_abs_f * target_abs_f - 4.0)


def _single_q_glt_energy(model, q_vector):
    blocks_payload = glt._lt_blocks(model)
    candidate = glt._evaluate_weighted_candidate(
        blocks_payload,
        q_mesh=[q_vector],
        local_dimension=int(model["local_dimension"]),
        p_weights=[1.0] * int(model.get("magnetic_site_count", 1)),
    )
    return float(candidate["energy"])


def _kernel_eigensystem(model, q_vector):
    blocks_payload = glt._lt_blocks(model)
    kernel = glt._kernel_at_q(
        blocks_payload["blocks"],
        q_vector,
        magnetic_site_count=int(blocks_payload["magnetic_site_count"]),
    )
    return glt._stable_hermitian_eigh(kernel)


def _lowest_kernel_eigenvalue(model, q_vector):
    eigenvalues, _ = _kernel_eigensystem(model, q_vector)
    return float(eigenvalues[0])


def _near_degenerate_two_minima_model(q_left, q_right, *, split=1.0e-4):
    left = math.cos(2.0 * math.pi * q_left)
    right = math.cos(2.0 * math.pi * q_right)
    polynomial = np.poly1d(
        [
            1.0,
            -2.0 * (left + right),
            left * left + 4.0 * left * right + right * right,
            -2.0 * left * right * (left + right),
            left * left * right * right,
        ]
    )
    sample_x = np.linspace(0.0, 2.0 * math.pi, 64, endpoint=False)
    design = np.column_stack([np.ones(sample_x.size)] + [np.cos(period * sample_x) for period in range(1, 5)])
    base_coefficients = np.linalg.lstsq(design, np.polyval(polynomial.coefficients, np.cos(sample_x)), rcond=None)[0]

    def value_row(q_value):
        x_value = 2.0 * math.pi * q_value
        return [1.0] + [math.cos(period * x_value) for period in range(1, 5)]

    def derivative_row(q_value):
        x_value = 2.0 * math.pi * q_value
        return [0.0] + [-2.0 * math.pi * period * math.sin(period * x_value) for period in range(1, 5)]

    perturbation_matrix = np.array(
        [value_row(q_left), value_row(q_right), derivative_row(q_left), derivative_row(q_right)],
        dtype=float,
    )
    perturbation = np.linalg.lstsq(
        perturbation_matrix,
        np.array([0.0, 1.0, 0.0, 0.0], dtype=float),
        rcond=None,
    )[0]
    coefficients = base_coefficients + float(split) * perturbation
    return _cp1_harmonic_model(
        [(0, -0.2 + coefficients[0])] + [(period, coefficients[period]) for period in range(1, 5)]
    )


def _flat_valley_model():
    target = 0.5
    constant = 1.0 + target * target - 0.2
    return _cp1_harmonic_model(
        [
            ((0, 0, 0), constant),
            ((2, 0, 0), 0.5),
            ((0, 2, 0), 0.5),
            ((1, 1, 0), 1.0),
            ((1, -1, 0), 1.0),
            ((1, 0, 0), -2.0 * target),
            ((0, 1, 0), -2.0 * target),
        ]
    )


def _two_sublattice_weight_competition_model():
    bonds = []
    for site, coefficient in ((0, -1.0), (1, -0.1)):
        coupling = np.zeros((4, 4), dtype=float)
        coupling[1, 1] = float(coefficient)
        bonds.append(
            {
                "source": site,
                "target": site,
                "R": [0, 0, 0],
                "tensor": _serialized_tensor_from_coupling(coupling),
            }
        )
    return {
        "classical_manifold": "CP^(N-1)",
        "local_dimension": 2,
        "magnetic_site_count": 2,
        "magnetic_sites": [{"label": "strong"}, {"label": "weak"}],
        "bond_tensors": bonds,
    }


def _identity_finalize(_model, result, **_kwargs):
    return result


def _nearest_mesh_distance(q_value, mesh_count):
    if int(mesh_count) <= 1:
        mesh_points = [0.0]
    else:
        mesh_points = [index / float(int(mesh_count) - 1) for index in range(int(mesh_count))]
    return min(abs(float(q_value) - point) for point in mesh_points)


def _nearest_low_denominator_distance(q_value, *, max_denominator):
    q_value = float(q_value) % 1.0
    best_distance = 1.0
    for denominator in range(1, int(max_denominator) + 1):
        for numerator in range(denominator + 1):
            delta = abs(q_value - numerator / float(denominator)) % 1.0
            best_distance = min(best_distance, delta, 1.0 - delta)
    return best_distance


STRONGLY_INCOMMENSURATE_Q_TARGETS = [
    (math.sqrt(5.0) - 1.0) / 4.0,
    1.0 / math.sqrt(19.0),
    0.225 + math.sqrt(2.0) * 1.0e-6,
]


LITERATURE_BENCHMARK_MODELS = [
    {
        "name": "1d_j1_j2_chain_spiral_fm_afm",
        "source": "Sirker_PRB_2011",
        "source_url": "https://arxiv.org/abs/1106.1008",
        "expected": "q=acos(-J1/4J2)",
        "checked_by": "test_literature_j1_j2_heisenberg_chain_pitch_matches_continuous_glt",
    },
    {
        "name": "1d_j1_j2_chain_spiral_irrational",
        "source": "Sirker_PRB_2011",
        "source_url": "https://arxiv.org/abs/1106.1008",
        "expected": "off-mesh incommensurate q",
        "checked_by": "test_literature_j1_j2_heisenberg_chain_pitch_matches_continuous_glt",
    },
    {
        "name": "1d_j1_j2_chain_spiral_afm_afm",
        "source": "Sirker_PRB_2011",
        "source_url": "https://arxiv.org/abs/1106.1008",
        "expected": "q=acos(-J1/4J2)",
        "checked_by": "test_literature_j1_j2_heisenberg_chain_pitch_matches_continuous_glt",
    },
    {
        "name": "1d_j1_j2_chain_ferromagnetic_side",
        "source": "Sirker_PRB_2011",
        "source_url": "https://arxiv.org/abs/1106.1008",
        "expected": "q=Gamma for J1/J2<-4",
        "checked_by": "test_literature_j1_j2_heisenberg_chain_ferromagnetic_side_stays_at_gamma",
    },
    {
        "name": "square_j1_j2_neel",
        "source": "Richter_arXiv_1409_0193",
        "source_url": "https://arxiv.org/abs/1409.0193",
        "expected": "Neel for small J2/J1",
        "checked_by": "test_literature_square_lattice_j1_j2_limits_select_neel_or_stripe_wavevectors",
    },
    {
        "name": "square_j1_j2_stripe_x",
        "source": "Richter_arXiv_1409_0193",
        "source_url": "https://arxiv.org/abs/1409.0193",
        "expected": "stripe for large J2/J1",
        "checked_by": "test_literature_square_lattice_j1_j2_limits_select_neel_or_stripe_wavevectors",
    },
    {
        "name": "square_j1_j2_stripe_y",
        "source": "Richter_arXiv_1409_0193",
        "source_url": "https://arxiv.org/abs/1409.0193",
        "expected": "symmetry-related stripe",
        "checked_by": "test_literature_square_lattice_j1_j2_limits_select_neel_or_stripe_wavevectors",
    },
    {
        "name": "square_j1_j3_spiral",
        "source": "square_J1J3_classical_Lifshitz",
        "source_url": "https://arxiv.org/abs/1804.04308",
        "expected": "cos(Q)=J1/(4J3)",
        "checked_by": "test_literature_square_lattice_j1_j3_lifshitz_spiral_matches_formula",
    },
    {
        "name": "square_j1_j3_neel_side",
        "source": "square_J1J3_classical_Lifshitz",
        "source_url": "https://arxiv.org/abs/1804.04308",
        "expected": "Neel for J3<J1/4",
        "checked_by": "test_literature_square_lattice_j1_j3_neel_side_of_lifshitz_point",
    },
    {
        "name": "triangular_nn_120_degree",
        "source": "triangular_classical_Heisenberg",
        "source_url": "https://przyrbwn.icm.edu.pl/APP/PDF/127/a127z2p051.pdf",
        "expected": "K-point 120-degree order",
        "checked_by": "test_literature_triangular_lattice_nearest_neighbor_afm_selects_k_point_120_degree_order",
    },
    {
        "name": "triangular_j1_j2_120_side",
        "source": "triangular_J1J2_classical",
        "source_url": "https://przyrbwn.icm.edu.pl/APP/PDF/127/a127z2p051.pdf",
        "expected": "120-degree for J2/J1<1/8",
        "checked_by": "test_literature_triangular_lattice_j1_j2_crosses_from_120_degree_to_stripe_order",
    },
    {
        "name": "triangular_j1_j2_stripe_1",
        "source": "triangular_J1J2_classical",
        "source_url": "https://przyrbwn.icm.edu.pl/APP/PDF/127/a127z2p051.pdf",
        "expected": "stripe for J2/J1>1/8",
        "checked_by": "test_literature_triangular_lattice_j1_j2_crosses_from_120_degree_to_stripe_order",
    },
    {
        "name": "triangular_j1_j2_stripe_2",
        "source": "triangular_J1J2_classical",
        "source_url": "https://przyrbwn.icm.edu.pl/APP/PDF/127/a127z2p051.pdf",
        "expected": "symmetry-related stripe",
        "checked_by": "test_literature_triangular_lattice_j1_j2_crosses_from_120_degree_to_stripe_order",
    },
    {
        "name": "triangular_j1_j2_stripe_3",
        "source": "triangular_J1J2_classical",
        "source_url": "https://przyrbwn.icm.edu.pl/APP/PDF/127/a127z2p051.pdf",
        "expected": "symmetry-related stripe",
        "checked_by": "test_literature_triangular_lattice_j1_j2_crosses_from_120_degree_to_stripe_order",
    },
    {
        "name": "simple_cubic_j1_j2_neel",
        "source": "Pinettes_Diep_JAP_1998",
        "source_url": "https://pubs.aip.org/aip/jap/article/83/11/6317/492023/Phase-transition-and-phase-diagram-of-the-J1-J2",
        "expected": "(pi,pi,pi) for J2/J1<1/4",
        "checked_by": "test_literature_simple_cubic_j1_j2_selects_neel_or_collinear_wavevectors",
    },
    {
        "name": "simple_cubic_j1_j2_collinear_x",
        "source": "Pinettes_Diep_JAP_1998",
        "source_url": "https://pubs.aip.org/aip/jap/article/83/11/6317/492023/Phase-transition-and-phase-diagram-of-the-J1-J2",
        "expected": "(0,pi,pi)-type for J2/J1>1/4",
        "checked_by": "test_literature_simple_cubic_j1_j2_selects_neel_or_collinear_wavevectors",
    },
    {
        "name": "simple_cubic_j1_j2_collinear_y",
        "source": "Pinettes_Diep_JAP_1998",
        "source_url": "https://pubs.aip.org/aip/jap/article/83/11/6317/492023/Phase-transition-and-phase-diagram-of-the-J1-J2",
        "expected": "symmetry-related collinear",
        "checked_by": "test_literature_simple_cubic_j1_j2_selects_neel_or_collinear_wavevectors",
    },
    {
        "name": "simple_cubic_j1_j2_collinear_z",
        "source": "Pinettes_Diep_JAP_1998",
        "source_url": "https://pubs.aip.org/aip/jap/article/83/11/6317/492023/Phase-transition-and-phase-diagram-of-the-J1-J2",
        "expected": "symmetry-related collinear",
        "checked_by": "test_literature_simple_cubic_j1_j2_selects_neel_or_collinear_wavevectors",
    },
    {
        "name": "honeycomb_nn_bipartite_afm",
        "source": "Bergman_NatPhys_2007_and_honeycomb_SSL",
        "source_url": "https://www.osti.gov/pages/servlets/purl/1874654",
        "expected": "Gamma staggered sublattice mode",
        "checked_by": "test_literature_honeycomb_nearest_neighbor_afm_selects_gamma_staggered_sublattice_mode",
    },
    {
        "name": "honeycomb_j1_j2_spiral_ring",
        "source": "Bergman_NatPhys_2007_and_honeycomb_SSL",
        "source_url": "https://www.osti.gov/pages/servlets/purl/1874654",
        "expected": "|f(q)|=|J1|/(2J2)",
        "checked_by": "test_literature_honeycomb_j1_j2_spiral_ring_matches_bergman_condition",
    },
    {
        "name": "kagome_nn_flat_band",
        "source": "kagome_classical_Heisenberg",
        "source_url": "https://link.aps.org/doi/10.1103/PhysRevB.91.184407",
        "expected": "lowest LT flat band",
        "checked_by": "test_literature_kagome_nearest_neighbor_afm_has_luttinger_tisza_flat_band",
    },
    {
        "name": "kagome_nn_flat_valley_report",
        "source": "kagome_classical_Heisenberg",
        "source_url": "https://link.aps.org/doi/10.1103/PhysRevB.91.184407",
        "expected": "flat_valley unresolved sectors",
        "checked_by": "test_literature_kagome_flat_band_is_reported_as_unresolved_flat_valley",
    },
    {
        "name": "pyrochlore_nn_flat_band",
        "source": "Moessner_Chalker_PRL_1998",
        "source_url": "https://link.aps.org/doi/10.1103/PhysRevLett.80.2929",
        "expected": "lowest LT flat band",
        "checked_by": "test_literature_pyrochlore_nearest_neighbor_afm_has_luttinger_tisza_flat_band",
    },
    {
        "name": "diamond_j1_j2_neel_low_j2",
        "source": "Bergman_NatPhys_2007",
        "source_url": "https://arxiv.org/abs/cond-mat/0612001",
        "expected": "Neel for J2/J1<1/8",
        "checked_by": "test_literature_diamond_j1_j2_below_one_eighth_stays_neel",
    },
    {
        "name": "diamond_j1_j2_neel_near_lifshitz",
        "source": "Bergman_NatPhys_2007",
        "source_url": "https://arxiv.org/abs/cond-mat/0612001",
        "expected": "Neel side below 1/8",
        "checked_by": "test_literature_diamond_j1_j2_below_one_eighth_stays_neel",
    },
    {
        "name": "diamond_j1_j2_spiral_surface",
        "source": "Bergman_NatPhys_2007",
        "source_url": "https://arxiv.org/abs/cond-mat/0612001",
        "expected": "|f(q)|=|J1|/(2J2)",
        "checked_by": "test_literature_diamond_j1_j2_spiral_surface_matches_bergman_condition",
    },
]


def test_literature_benchmark_registry_tracks_at_least_twenty_models():
    names = [entry["name"] for entry in LITERATURE_BENCHMARK_MODELS]

    assert len(LITERATURE_BENCHMARK_MODELS) >= 20
    assert len(names) == len(set(names))
    for entry in LITERATURE_BENCHMARK_MODELS:
        assert entry["source"]
        assert entry["source_url"].startswith("http")
        assert entry["expected"]
        assert entry["checked_by"].startswith("test_literature_")


@pytest.mark.parametrize("q_star", STRONGLY_INCOMMENSURATE_Q_TARGETS)
@pytest.mark.parametrize("mesh_count", [4, 5, 6, 7])
def test_real_tensor_strongly_incommensurate_minimum_refines_off_multiple_coarse_meshes(
    monkeypatch, mesh_count, q_star
):
    coefficient_r2 = 1.0
    coefficient_r1 = -4.0 * math.cos(2.0 * math.pi * q_star)
    model = _cp1_harmonic_model([(1, coefficient_r1), (2, coefficient_r2)])

    monkeypatch.setattr(glt, "finalize_cpn_glt_result", _identity_finalize)

    result = glt.solve_cpn_generalized_lt_ground_state(model, mesh_shape=(mesh_count, 1, 1))

    refined_q = result["q_vector"][0]
    mesh_probe_q = result["mesh_probe"]["best_q_vector"][0]

    assert _nearest_low_denominator_distance(q_star, max_denominator=8) > 2.0e-2
    assert _nearest_mesh_distance(q_star, mesh_count) > 2.0e-2
    assert refined_q == pytest.approx(q_star, abs=1.5e-3)
    assert abs(refined_q - mesh_probe_q) > 2.0e-2


def test_frustrated_exchange_continuous_q_is_not_the_coarse_mesh_probe(monkeypatch):
    q_star = 0.225 + math.sqrt(2.0) * 1.0e-6
    model = _cp1_harmonic_model([(1, -4.0 * math.cos(2.0 * math.pi * q_star)), (2, 1.0)])

    monkeypatch.setattr(glt, "finalize_cpn_glt_result", _identity_finalize)

    result = glt.solve_cpn_generalized_lt_ground_state(model, mesh_shape=(6, 1, 1))
    mesh_probe = result["mesh_probe"]

    assert _nearest_low_denominator_distance(q_star, max_denominator=8) > 2.0e-2
    assert _nearest_mesh_distance(q_star, 6) > 2.0e-2
    assert result["q_vector"][0] == pytest.approx(q_star, abs=1.5e-3)
    assert abs(result["q_vector"][0] - mesh_probe["best_q_vector"][0]) > 2.0e-2
    assert result["energy"] < mesh_probe["best_lower_bound"] - 1.0e-2
    assert result["continuous_search_classification"] == "isolated_minimum"
    assert result["continuous_search_status"] == "resolved"
    raw_sources = {
        source
        for sector in result["continuous_low_energy_sectors"]
        for source in sector.get("raw_sources", [])
    }
    assert "mesh-seed" not in raw_sources


@pytest.mark.parametrize(
    "j1,j2,mesh_count",
    [
        (-1.0, 1.0, 5),
        (-math.sqrt(2.0), 1.0, 7),
        (-4.0 * math.cos(2.0 * math.pi * (0.225 + math.sqrt(2.0) * 1.0e-6)), 1.0, 6),
        (1.0, 1.0, 5),
    ],
)
def test_literature_j1_j2_heisenberg_chain_pitch_matches_continuous_glt(monkeypatch, j1, j2, mesh_count):
    q_literature = _literature_j1_j2_spiral_q(j1, j2)
    model = _cp1_isotropic_heisenberg_chain_model(j1, j2)

    monkeypatch.setattr(glt, "finalize_cpn_glt_result", _identity_finalize)

    result = glt.solve_cpn_generalized_lt_ground_state(model, mesh_shape=(mesh_count, 1, 1))
    mesh_probe_q = result["mesh_probe"]["best_q_vector"][0]

    assert 0.0 < q_literature < 0.5
    assert _nearest_mesh_distance(q_literature, mesh_count) > 2.0e-2
    assert result["q_vector"][0] == pytest.approx(q_literature, abs=1.5e-3)
    assert abs(result["q_vector"][0] - mesh_probe_q) > 2.0e-2
    assert result["energy"] < result["mesh_probe"]["best_lower_bound"] - 1.0e-2
    assert result["continuous_search_classification"] == "isolated_minimum"
    assert result["continuous_search_status"] == "resolved"


def test_literature_j1_j2_heisenberg_chain_ferromagnetic_side_stays_at_gamma(monkeypatch):
    model = _cp1_isotropic_heisenberg_chain_model(j1=-4.5, j2=1.0)

    monkeypatch.setattr(glt, "finalize_cpn_glt_result", _identity_finalize)

    result = glt.solve_cpn_generalized_lt_ground_state(model, mesh_shape=(5, 1, 1))

    assert _literature_j1_j2_spiral_q(-4.5, 1.0) == pytest.approx(0.0)
    assert result["q_vector"] == pytest.approx([0.0, 0.0, 0.0])
    assert result["continuous_low_energy_sectors"][0]["q_vector"] == pytest.approx([0.0, 0.0, 0.0])
    assert len(result["continuous_low_energy_sectors"]) == 1
    assert result["continuous_search_classification"] != "quasi_degenerate"
    assert result["continuous_search_status"] != "unresolved"


@pytest.mark.parametrize(
    "j2,expected_q,competing_q",
    [
        (0.2, [0.5, 0.5, 0.0], [[0.5, 0.0, 0.0], [0.0, 0.5, 0.0]]),
        (0.8, [0.5, 0.0, 0.0], [[0.5, 0.5, 0.0], [0.0, 0.0, 0.0]]),
        (0.8, [0.0, 0.5, 0.0], [[0.5, 0.5, 0.0], [0.0, 0.0, 0.0]]),
    ],
)
def test_literature_square_lattice_j1_j2_limits_select_neel_or_stripe_wavevectors(
    j2, expected_q, competing_q
):
    # Richter et al., arXiv:1409.0193: square J1-J2 has Neel order at small J2/J1
    # and collinear striped order at large J2/J1.
    model = _square_lattice_j1_j2_model(j1=1.0, j2=j2)

    expected_energy = _single_q_glt_energy(model, expected_q)

    for q_vector in competing_q:
        assert expected_energy < _single_q_glt_energy(model, q_vector) - 1.0e-6


def test_literature_square_lattice_j1_j3_lifshitz_spiral_matches_formula():
    # Recent J1-J3 square-lattice analyses quote the classical Lifshitz point J3=J1/4
    # and spiral condition cos(Q)=J1/(4J3).
    model = _square_lattice_j1_j3_model(j1=1.0, j3=1.0)
    q_component = _literature_square_j1_j3_spiral_component(j1=1.0, j3=1.0)
    expected_q = [q_component, q_component, 0.0]
    symmetry_related_q = [1.0 - q_component, q_component, 0.0]
    expected_energy = _single_q_glt_energy(model, expected_q)

    assert q_component == pytest.approx(0.2902153116, abs=1.0e-9)
    assert expected_energy == pytest.approx(_single_q_glt_energy(model, symmetry_related_q), abs=1.0e-12)
    assert expected_energy < _single_q_glt_energy(model, [0.5, 0.5, 0.0]) - 1.0e-1
    assert expected_energy < _single_q_glt_energy(model, [0.5, 0.0, 0.0]) - 1.0e-1


def test_literature_square_lattice_j1_j3_neel_side_of_lifshitz_point():
    model = _square_lattice_j1_j3_model(j1=1.0, j3=0.2)
    neel_energy = _single_q_glt_energy(model, [0.5, 0.5, 0.0])

    assert _literature_square_j1_j3_spiral_component(j1=1.0, j3=0.2) == pytest.approx(0.5)
    assert neel_energy < _single_q_glt_energy(model, [0.25, 0.25, 0.0]) - 1.0e-1
    assert neel_energy < _single_q_glt_energy(model, [0.5, 0.0, 0.0]) - 1.0e-1


def test_literature_triangular_lattice_nearest_neighbor_afm_selects_k_point_120_degree_order():
    # The triangular-lattice Heisenberg antiferromagnet has 120-degree order at K.
    model = _triangular_lattice_nearest_neighbor_model(j1=1.0)
    k_energy = _single_q_glt_energy(model, [1.0 / 3.0, 2.0 / 3.0, 0.0])

    assert k_energy == pytest.approx(_single_q_glt_energy(model, [2.0 / 3.0, 1.0 / 3.0, 0.0]), abs=1.0e-12)
    assert k_energy < _single_q_glt_energy(model, [0.5, 0.5, 0.0]) - 1.0e-1
    assert k_energy < _single_q_glt_energy(model, [0.0, 0.0, 0.0]) - 1.0


@pytest.mark.parametrize(
    "j2,expected_q,competing_q",
    [
        (0.05, [1.0 / 3.0, 2.0 / 3.0, 0.0], [[0.5, 0.0, 0.0], [0.0, 0.5, 0.0]]),
        (0.20, [0.5, 0.0, 0.0], [[1.0 / 3.0, 2.0 / 3.0, 0.0], [0.0, 0.0, 0.0]]),
        (0.20, [0.0, 0.5, 0.0], [[1.0 / 3.0, 2.0 / 3.0, 0.0], [0.0, 0.0, 0.0]]),
        (0.20, [0.5, 0.5, 0.0], [[1.0 / 3.0, 2.0 / 3.0, 0.0], [0.0, 0.0, 0.0]]),
    ],
)
def test_literature_triangular_lattice_j1_j2_crosses_from_120_degree_to_stripe_order(
    j2, expected_q, competing_q
):
    # Classical triangular J1-J2 studies place the 120-degree/stripe crossing at J2/J1=1/8.
    model = _triangular_lattice_j1_j2_model(j1=1.0, j2=j2)
    expected_energy = _single_q_glt_energy(model, expected_q)

    crossing_model = _triangular_lattice_j1_j2_model(j1=1.0, j2=0.125)
    assert _single_q_glt_energy(crossing_model, [1.0 / 3.0, 2.0 / 3.0, 0.0]) == pytest.approx(
        _single_q_glt_energy(crossing_model, [0.5, 0.0, 0.0]),
        abs=1.0e-12,
    )
    for q_vector in competing_q:
        assert expected_energy < _single_q_glt_energy(model, q_vector) - 1.0e-3


@pytest.mark.parametrize(
    "j2,expected_q,competing_q",
    [
        (0.1, [0.5, 0.5, 0.5], [[0.0, 0.5, 0.5], [0.5, 0.0, 0.5], [0.5, 0.5, 0.0]]),
        (0.4, [0.0, 0.5, 0.5], [[0.5, 0.5, 0.5], [0.0, 0.0, 0.0]]),
        (0.4, [0.5, 0.0, 0.5], [[0.5, 0.5, 0.5], [0.0, 0.0, 0.0]]),
        (0.4, [0.5, 0.5, 0.0], [[0.5, 0.5, 0.5], [0.0, 0.0, 0.0]]),
    ],
)
def test_literature_simple_cubic_j1_j2_selects_neel_or_collinear_wavevectors(
    j2, expected_q, competing_q
):
    # Simple-cubic J1-J2 studies describe competition between (pi,pi,pi)
    # and collinear (0,pi,pi)-type orders; the classical crossing is J2/J1=1/4.
    model = _simple_cubic_j1_j2_model(j1=1.0, j2=j2)
    expected_energy = _single_q_glt_energy(model, expected_q)

    for q_vector in competing_q:
        assert expected_energy < _single_q_glt_energy(model, q_vector) - 1.0e-6


def test_literature_honeycomb_nearest_neighbor_afm_selects_gamma_staggered_sublattice_mode():
    # The honeycomb NN antiferromagnet is bipartite: the LT minimum is the
    # Gamma-point staggered sublattice mode.
    model = _honeycomb_j1_j2_model(j1=1.0, j2=0.0)
    gamma_energy = _single_q_glt_energy(model, [0.0, 0.0, 0.0])
    eigenvalues, eigenvectors = _kernel_eigensystem(model, [0.0, 0.0, 0.0])
    mode = eigenvectors[:, 0]

    assert gamma_energy == pytest.approx(-1.5, abs=1.0e-12)
    assert _lowest_kernel_eigenvalue(model, [0.0, 0.0, 0.0]) < _lowest_kernel_eigenvalue(
        model,
        [1.0 / 3.0, 2.0 / 3.0, 0.0],
    ) - 1.0
    assert _lowest_kernel_eigenvalue(model, [0.0, 0.0, 0.0]) < _lowest_kernel_eigenvalue(
        model,
        [0.5, 0.0, 0.0],
    ) - 0.5
    assert eigenvalues[0] == pytest.approx(-1.5, abs=1.0e-12)
    assert mode[0] * mode[3] < 0.0


def test_literature_honeycomb_j1_j2_spiral_ring_matches_bergman_condition():
    # Bergman et al. report a classical honeycomb spiral ring for J2/J1 > 1/6
    # satisfying |1 + exp(i q1) + exp(i q2)| = |J1| / (2 J2).
    model = _honeycomb_j1_j2_model(j1=1.0, j2=0.25)
    q_axis = _honeycomb_spiral_ring_component_along_10(j1=1.0, j2=0.25)
    spiral_energy = _single_q_glt_energy(model, [q_axis, 0.0, 0.0])
    gamma_energy = _single_q_glt_energy(model, [0.0, 0.0, 0.0])
    k_energy = _single_q_glt_energy(model, [1.0 / 3.0, 2.0 / 3.0, 0.0])

    assert q_axis == pytest.approx(0.2902153116, abs=1.0e-10)
    assert _honeycomb_spiral_ring_x_value(j1=1.0, j2=0.25) == pytest.approx(0.5)
    assert spiral_energy < k_energy - 0.1
    assert spiral_energy < gamma_energy - 1.0e-1


@pytest.mark.parametrize(
    "q_vector",
    [
        [0.0, 0.5, 0.0],
        [0.5, 0.0, 0.0],
        [0.5, 0.5, 0.0],
        [0.125, 0.375, 0.0],
    ],
)
def test_literature_kagome_nearest_neighbor_afm_has_luttinger_tisza_flat_band(q_vector):
    # The kagome nearest-neighbor antiferromagnet has a flat lowest LT band.
    model = _kagome_nearest_neighbor_model(j1=1.0)

    assert _lowest_kernel_eigenvalue(model, q_vector) == pytest.approx(-1.0, abs=1.0e-12)


def test_literature_kagome_flat_band_is_reported_as_unresolved_flat_valley(monkeypatch):
    model = _kagome_nearest_neighbor_model(j1=1.0)

    monkeypatch.setattr(glt, "finalize_cpn_glt_result", _identity_finalize)

    result = glt.solve_cpn_generalized_lt_ground_state(model, mesh_shape=(4, 4, 1))

    assert result["continuous_search_classification"] == "flat_valley"
    assert result["continuous_search_status"] == "unresolved"
    assert len(result["continuous_low_energy_sectors"]) >= 3
    assert all(sector["delta_energy"] <= 1.0e-4 for sector in result["continuous_low_energy_sectors"])


@pytest.mark.parametrize(
    "q_vector",
    [
        [0.0, 0.0, 0.0],
        [0.5, 0.0, 0.0],
        [0.0, 0.5, 0.0],
        [0.5, 0.5, 0.0],
        [0.25, 0.25, 0.25],
        [1.0 / 3.0, 0.2, 0.1],
    ],
)
def test_literature_pyrochlore_nearest_neighbor_afm_has_luttinger_tisza_flat_band(q_vector):
    # The pyrochlore nearest-neighbor antiferromagnet has a flat lowest LT band.
    model = _pyrochlore_nearest_neighbor_model(j1=1.0)

    assert _lowest_kernel_eigenvalue(model, q_vector) == pytest.approx(-1.0, abs=1.0e-12)


@pytest.mark.parametrize("j2", [0.05, 0.10])
def test_literature_diamond_j1_j2_below_one_eighth_stays_neel(j2):
    # Bergman et al. give a diamond-lattice Lifshitz point at J2/J1 = 1/8.
    model = _diamond_j1_j2_model(j1=1.0, j2=j2)
    gamma_energy = _single_q_glt_energy(model, [0.0, 0.0, 0.0])

    assert gamma_energy == pytest.approx(_lowest_kernel_eigenvalue(model, [0.0, 0.0, 0.0]))
    assert _lowest_kernel_eigenvalue(model, [0.0, 0.0, 0.0]) < _lowest_kernel_eigenvalue(
        model,
        [0.25, 0.25, 0.0],
    ) - 1.0e-2
    assert _lowest_kernel_eigenvalue(model, [0.0, 0.0, 0.0]) < _lowest_kernel_eigenvalue(
        model,
        [0.5, 0.0, 0.0],
    ) - 1.0e-2


def test_literature_diamond_j1_j2_spiral_surface_matches_bergman_condition():
    # On the diamond lattice, the spiral surface obeys
    # |1 + exp(iq1) + exp(iq2) + exp(iq3)| = |J1| / (2 J2).
    model = _diamond_j1_j2_model(j1=1.0, j2=0.25)
    q_110 = _diamond_spiral_surface_q_110(j1=1.0, j2=0.25)
    q_1_minus_10 = _diamond_spiral_surface_q_1_minus_10(j1=1.0, j2=0.25)
    spiral_energy = _lowest_kernel_eigenvalue(model, [q_110, q_110, 0.0])
    alternate_spiral_energy = _lowest_kernel_eigenvalue(model, [q_1_minus_10, 1.0 - q_1_minus_10, 0.0])

    assert _diamond_spiral_surface_x_value(j1=1.0, j2=0.25) == pytest.approx(0.0)
    assert q_110 == pytest.approx(1.0 / 3.0, abs=1.0e-12)
    assert q_1_minus_10 == pytest.approx(0.25, abs=1.0e-12)
    assert spiral_energy == pytest.approx(alternate_spiral_energy, abs=1.0e-12)
    assert spiral_energy < _lowest_kernel_eigenvalue(model, [0.0, 0.0, 0.0]) - 1.0e-1
    assert spiral_energy == pytest.approx(_lowest_kernel_eigenvalue(model, [0.5, 0.0, 0.0]), abs=1.0e-12)


def test_near_degenerate_continuous_sectors_are_reported_as_quasi_degenerate_or_unresolved(monkeypatch):
    q_left = (math.sqrt(5.0) - 1.0) / 4.0
    q_right = 1.0 / math.sqrt(19.0)
    model = _near_degenerate_two_minima_model(q_left, q_right, split=1.0e-4)

    monkeypatch.setattr(glt, "finalize_cpn_glt_result", _identity_finalize)

    result = glt.solve_cpn_generalized_lt_ground_state(model, mesh_shape=(6, 1, 1))
    reported = result["continuous_low_energy_sectors"]
    reported_q = sorted(sector.get("canonical_q_vector", sector["q_vector"])[0] for sector in reported)
    positive_deltas = sorted(sector["delta_energy"] for sector in reported if sector["delta_energy"] > 1.0e-8)

    assert _nearest_low_denominator_distance(q_left, max_denominator=8) > 2.0e-2
    assert _nearest_low_denominator_distance(q_right, max_denominator=8) > 2.0e-2
    assert _nearest_mesh_distance(q_left, 6) > 2.0e-2
    assert _nearest_mesh_distance(q_right, 6) > 2.0e-2
    assert len(reported) == 2
    assert reported_q == pytest.approx(sorted([q_left, q_right]), abs=2.0e-3)
    assert all(sector["raw_q_vectors"] for sector in reported)
    assert positive_deltas[0] == pytest.approx(5.0e-5, abs=1.5e-5)
    assert result["continuous_search_classification"] == "quasi_degenerate"
    assert result["continuous_search_status"] == "unresolved"


def test_ring_or_flat_valley_is_not_reported_as_single_unqualified_q(monkeypatch):
    model = _flat_valley_model()

    monkeypatch.setattr(glt, "finalize_cpn_glt_result", _identity_finalize)

    result = glt.solve_cpn_generalized_lt_ground_state(model, mesh_shape=(5, 5, 1))
    reported = result["continuous_low_energy_sectors"]
    q_array = np.array([sector["q_vector"] for sector in reported], dtype=float)

    assert result["continuous_search_classification"] == "flat_valley"
    assert result["continuous_search_status"] == "unresolved"
    assert len(reported) >= 3
    assert all(sector["classification"] == "flat_valley" for sector in reported)
    assert all(sector["delta_energy"] <= 1.0e-4 for sector in reported)
    assert np.count_nonzero(np.ptp(q_array[:, :2], axis=0) > 1.0e-2) >= 2


def test_inversion_related_equal_energy_q_keeps_raw_representatives_without_false_quasi_degeneracy():
    sectors = glt._cluster_continuous_low_energy_sectors(
        [
            {"q_vector": [0.137, 0.0, 0.0], "energy": -1.0, "source": "left"},
            {"q_vector": [0.863, 0.0, 0.0], "energy": -1.0, "source": "right"},
        ]
    )

    assert len(sectors) == 1
    assert sectors[0]["classification"] == "isolated_minimum"
    assert sectors[0]["status"] == "resolved"
    assert sectors[0]["inversion_merged"] is True
    assert sorted(q_vector[0] for q_vector in sectors[0]["raw_q_vectors"]) == pytest.approx([0.137, 0.863])


def test_inversion_related_split_energy_q_is_not_silently_merged():
    sectors = glt._cluster_continuous_low_energy_sectors(
        [
            {"q_vector": [0.137, 0.0, 0.0], "energy": -1.0, "source": "left"},
            {"q_vector": [0.863, 0.0, 0.0], "energy": -0.99995, "source": "right"},
        ]
    )

    assert len(sectors) == 2
    assert {sector["classification"] for sector in sectors} == {"quasi_degenerate"}
    assert {sector["status"] for sector in sectors} == {"unresolved"}


@pytest.mark.parametrize(
    "left_q,right_q",
    [
        (0.0009, 0.9991),
        (0.4991, 0.5009),
    ],
)
def test_near_boundary_inversion_split_is_not_hidden_by_basin_tolerance(left_q, right_q):
    sectors = glt._cluster_continuous_low_energy_sectors(
        [
            {"q_vector": [left_q, 0.0, 0.0], "energy": -1.0, "source": "left"},
            {"q_vector": [right_q, 0.0, 0.0], "energy": -0.99995, "source": "right"},
        ]
    )

    assert len(sectors) == 2
    assert {sector["classification"] for sector in sectors} == {"quasi_degenerate"}
    assert {sector["status"] for sector in sectors} == {"unresolved"}


def test_close_optimizer_endpoints_from_same_basin_are_clustered():
    sectors = glt._cluster_continuous_low_energy_sectors(
        [
            {"q_vector": [0.1370, 0.0, 0.0], "energy": -1.0, "source": "left"},
            {"q_vector": [0.1380, 0.0, 0.0], "energy": -0.999999, "source": "nearby"},
        ]
    )

    assert len(sectors) == 1
    assert sectors[0]["classification"] == "isolated_minimum"
    assert len(sectors[0]["raw_q_vectors"]) == 2


def test_anisotropy_perturbation_refines_tiny_shift_from_symmetric_q(monkeypatch):
    q_star = 0.25 + math.sqrt(2.0) * 1.0e-3
    coefficient_r2 = 1.0
    coefficient_r1 = -4.0 * math.cos(2.0 * math.pi * q_star)
    assert abs(coefficient_r1) < 4.0e-2
    model = _cp1_harmonic_model([(1, coefficient_r1), (2, coefficient_r2)])

    monkeypatch.setattr(glt, "finalize_cpn_glt_result", _identity_finalize)

    result = glt.solve_cpn_generalized_lt_ground_state(model, mesh_shape=(4, 1, 1))

    assert result["q_vector"][0] == pytest.approx(q_star, abs=3.0e-4)
    assert abs(result["q_vector"][0] - 0.25) > 1.0e-3


def test_search_weights_selects_lower_energy_weight_candidate_from_real_two_sublattice_tensor():
    model = _two_sublattice_weight_competition_model()
    blocks_payload = glt._lt_blocks(model)

    result = glt._search_weights(
        blocks_payload,
        q_mesh=[[0.0, 0.0, 0.0]],
        local_dimension=2,
        magnetic_site_count=2,
        weight_bound=1.0,
        weight_points=3,
    )
    uniform = glt._evaluate_weighted_candidate(
        blocks_payload,
        q_mesh=[[0.0, 0.0, 0.0]],
        local_dimension=2,
        p_weights=[1.0, 1.0],
    )
    axis_energies = []
    for log_weight in (-1.0, 0.0, 1.0):
        p_weights, _, _ = glt._weights_from_log_coordinates(np.array([log_weight], dtype=float))
        candidate = glt._evaluate_weighted_candidate(
            blocks_payload,
            q_mesh=[[0.0, 0.0, 0.0]],
            local_dimension=2,
            p_weights=p_weights,
        )
        axis_energies.append(float(candidate["energy"]))

    assert result["energy"] < uniform["energy"] - 1.0
    assert result["energy"] == pytest.approx(min(axis_energies))
    assert result["p_weights"][0] > result["p_weights"][1]


def test_q_independent_two_sublattice_model_does_not_emit_fake_q_sectors(monkeypatch):
    model = _two_sublattice_weight_competition_model()

    monkeypatch.setattr(glt, "finalize_cpn_glt_result", _identity_finalize)

    result = glt.solve_cpn_generalized_lt_ground_state(model, mesh_shape=(5, 1, 1))
    sectors = result["continuous_low_energy_sectors"]

    assert result["q_vector"] == pytest.approx([0.0, 0.0, 0.0])
    assert result["continuous_search_classification"] != "quasi_degenerate"
    assert result["continuous_search_status"] != "unresolved"
    assert len(sectors) <= 1
