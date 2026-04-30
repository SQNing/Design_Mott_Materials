import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_ROOT))

from common.cpn_magnetic_supercell import (
    enumerate_magnetic_cell_cosets,
    lift_cpn_state_between_cells,
    magnetic_supercell_candidate_from_projector,
    reshape_cpn_model_to_magnetic_supercell,
)
from classical.sun_gswt_classical_solver import evaluate_sun_gswt_classical_energy


def _serialized_real_matrix(rows):
    return [
        [{"real": float(value), "imag": 0.0} for value in row]
        for row in rows
    ]


def _serialized_real_tensor(local_dimension, entries):
    tensor = []
    for left_bra in range(local_dimension):
        left_block = []
        for left_ket in range(local_dimension):
            right_block = []
            for right_bra in range(local_dimension):
                ket_block = []
                for right_ket in range(local_dimension):
                    value = float(entries.get((left_bra, left_ket, right_bra, right_ket), 0.0))
                    ket_block.append({"real": value, "imag": 0.0})
                right_block.append(ket_block)
            left_block.append(right_block)
        tensor.append(left_block)
    return tensor


def _toy_two_site_cpn_model():
    local_dimension = 2
    zz_tensor = _serialized_real_tensor(
        local_dimension,
        {
            (0, 0, 0, 0): -1.0,
            (1, 1, 1, 1): -1.0,
        },
    )
    return {
        "model_version": 2,
        "model_type": "sun_gswt_classical",
        "classical_manifold": "CP^(N-1)",
        "basis_semantics": {"local_space": "pseudospin_orbital"},
        "basis_order": "retained_state_index",
        "pair_basis_order": "site_i_major_site_j_minor",
        "retained_local_space": {
            "dimension": local_dimension,
            "factorization": {"kind": "generic_multiplet", "multiplet_dimension": local_dimension},
        },
        "operator_dictionary": {
            "local_basis_kind": "generic_multiplet",
            "local_operator_basis": {"matrix_construction": "local_generator_basis"},
        },
        "pair_operator_convention": {
            "pair_basis_order": "site_i_major_site_j_minor",
            "tensor_view": {
                "kind": "K_ab_cd",
                "index_order": ["left_bra", "right_bra", "left_ket", "right_ket"],
            },
        },
        "local_dimension": local_dimension,
        "local_basis_labels": ["up", "down"],
        "orbital_count": 0,
        "positions": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
        "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "bond_tensors": [
            {
                "R": [0, 0, 0],
                "source": 0,
                "target": 1,
                "matrix_shape": [4, 4],
                "tensor_shape": [2, 2, 2, 2],
                "tensor": zz_tensor,
                "pair_matrix": _serialized_real_matrix(
                    [
                        [-1.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, -1.0],
                    ]
                ),
            }
        ],
        "onsite_terms": [],
    }


def _toy_single_site_intercell_cpn_model():
    local_dimension = 2
    zz_tensor = _serialized_real_tensor(
        local_dimension,
        {
            (0, 0, 0, 0): -1.0,
            (1, 1, 1, 1): -1.0,
        },
    )
    return {
        "model_version": 2,
        "model_type": "sun_gswt_classical",
        "classical_manifold": "CP^(N-1)",
        "basis_semantics": {"local_space": "pseudospin_orbital"},
        "basis_order": "retained_state_index",
        "pair_basis_order": "site_i_major_site_j_minor",
        "retained_local_space": {
            "dimension": local_dimension,
            "factorization": {"kind": "generic_multiplet", "multiplet_dimension": local_dimension},
        },
        "operator_dictionary": {
            "local_basis_kind": "generic_multiplet",
            "local_operator_basis": {"matrix_construction": "local_generator_basis"},
        },
        "pair_operator_convention": {
            "pair_basis_order": "site_i_major_site_j_minor",
            "tensor_view": {
                "kind": "K_ab_cd",
                "index_order": ["left_bra", "right_bra", "left_ket", "right_ket"],
            },
        },
        "local_dimension": local_dimension,
        "local_basis_labels": ["up", "down"],
        "orbital_count": 0,
        "positions": [[0.0, 0.0, 0.0]],
        "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "bond_tensors": [
            {
                "R": [1, 0, 0],
                "source": 0,
                "target": 0,
                "matrix_shape": [4, 4],
                "tensor_shape": [2, 2, 2, 2],
                "tensor": zz_tensor,
                "pair_matrix": _serialized_real_matrix(
                    [
                        [-1.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, -1.0],
                    ]
                ),
            }
        ],
        "onsite_terms": [],
    }


def _serialized_vector(values):
    return [{"real": float(value), "imag": 0.0} for value in values]


def _toy_two_site_periodic_state():
    return {
        "schema_version": 1,
        "state_kind": "local_rays",
        "manifold": "CP^(N-1)",
        "basis_order": "retained_state_index",
        "pair_basis_order": "site_i_major_site_j_minor",
        "supercell_shape": [1, 1, 1],
        "local_rays": [
            {"cell": [0, 0, 0], "site": 0, "vector": _serialized_vector([1.0, 0.0])},
            {"cell": [0, 0, 0], "site": 1, "vector": _serialized_vector([0.0, 1.0])},
        ],
    }


def _cell_parity_modulated_single_site_state(shape):
    shape = [int(value) for value in shape]
    local_rays = []
    for ix in range(shape[0]):
        for iy in range(shape[1]):
            for iz in range(shape[2]):
                vector = [1.0, 0.0] if (ix + iy) % 2 == 0 else [0.0, 1.0]
                local_rays.append(
                    {"cell": [ix, iy, iz], "site": 0, "vector": _serialized_vector(vector)}
                )
    return {
        "schema_version": 1,
        "state_kind": "local_rays",
        "manifold": "CP^(N-1)",
        "basis_order": "retained_state_index",
        "pair_basis_order": "site_i_major_site_j_minor",
        "supercell_shape": list(shape),
        "local_rays": local_rays,
    }


def test_candidate_from_projector_returns_integer_matrix_for_commensurate_q():
    projector = {
        "top_components": [
            {"q": [0.25, 0.0, 0.25], "weight": 0.14},
            {"q": [0.0, 0.0, 0.0], "weight": 0.49},
        ]
    }

    candidate = magnetic_supercell_candidate_from_projector(projector)

    assert candidate["status"] == "ok"
    assert candidate["selected_q"] == [0.25, 0.0, 0.25]
    assert candidate["matrix"]
    assert candidate["determinant"] >= 1


def test_candidate_from_coupled_q_finds_smaller_than_axiswise_diagonal_volume():
    projector = {
        "top_components": [
            {"q": [0.25, 0.75, 0.25], "weight": 0.14},
            {"q": [0.0, 0.0, 0.0], "weight": 0.49},
        ]
    }

    candidate = magnetic_supercell_candidate_from_projector(projector)

    assert candidate["status"] == "ok"
    assert candidate["selected_q"] == [0.25, 0.75, 0.25]
    assert candidate["determinant"] == 4
    for row in candidate["matrix"]:
        phase_winding = sum(
            candidate["selected_q"][axis] * row[axis]
            for axis in range(3)
        )
        assert abs(phase_winding - round(phase_winding)) <= 1e-10


def test_enumerate_coset_representatives_matches_absolute_determinant():
    matrix = [[1, 0, 0], [0, 1, -2], [0, 1, 2]]

    reps = enumerate_magnetic_cell_cosets(matrix)

    assert len(reps) == 4


def test_reshape_model_multiplies_site_count_by_cell_volume():
    model = _toy_two_site_cpn_model()
    matrix = [[2, 0, 0], [0, 1, 0], [0, 0, 1]]

    reshaped = reshape_cpn_model_to_magnetic_supercell(model, matrix)

    assert len(reshaped["positions"]) == 4


def test_reshaped_model_preserves_classical_energy_for_equivalent_state():
    model = _toy_two_site_cpn_model()
    state = _toy_two_site_periodic_state()
    matrix = [[2, 0, 0], [0, 1, 0], [0, 0, 1]]

    reshaped_model = reshape_cpn_model_to_magnetic_supercell(model, matrix)
    reshaped_state = lift_cpn_state_between_cells(
        state,
        reshaped_model["magnetic_supercell_mapping"],
        direction="chemical_to_magnetic",
    )

    e0 = evaluate_sun_gswt_classical_energy(model, state)
    e1 = evaluate_sun_gswt_classical_energy(reshaped_model, reshaped_state)

    assert abs(e0 - e1) <= 1e-10


def test_reshape_model_reports_mapping_diagnostics():
    reshaped = reshape_cpn_model_to_magnetic_supercell(
        _toy_two_site_cpn_model(),
        [[2, 0, 0], [0, 1, 0], [0, 0, 1]],
    )

    assert reshaped["magnetic_supercell_mapping"]["representative_count"] == 2
    assert reshaped["magnetic_supercell_mapping"]["reshaped_site_count"] == 4


def test_lift_cpn_state_round_trips_for_nondiagonal_magnetic_supercell():
    model = _toy_single_site_intercell_cpn_model()
    matrix = [[1, 0, -1], [0, 1, 1], [0, 0, 4]]
    reshaped_model = reshape_cpn_model_to_magnetic_supercell(model, matrix)
    mapping = dict(reshaped_model["magnetic_supercell_mapping"])
    mapping["chemical_supercell_shape"] = [4, 4, 4]

    chemical_state = _cell_parity_modulated_single_site_state([4, 4, 4])
    magnetic_state = lift_cpn_state_between_cells(
        chemical_state,
        mapping,
        direction="chemical_to_magnetic",
    )
    lifted_back = lift_cpn_state_between_cells(
        magnetic_state,
        mapping,
        direction="magnetic_to_chemical",
    )

    assert magnetic_state["supercell_shape"] == [4, 4, 1]
    assert lifted_back["supercell_shape"] == [4, 4, 4]
    assert lifted_back["local_rays"] == chemical_state["local_rays"]


def test_nondiagonal_reshape_preserves_classical_energy_density_for_nonuniform_finite_state():
    model = _toy_single_site_intercell_cpn_model()
    chemical_state = _cell_parity_modulated_single_site_state([4, 4, 4])
    matrix = [[1, 0, -1], [3, -1, 0], [0, 0, 4]]

    reshaped_model = reshape_cpn_model_to_magnetic_supercell(model, matrix)
    mapping = dict(reshaped_model["magnetic_supercell_mapping"])
    mapping["chemical_supercell_shape"] = [4, 4, 4]
    magnetic_state = lift_cpn_state_between_cells(
        chemical_state,
        mapping,
        direction="chemical_to_magnetic",
    )

    original_energy_density = evaluate_sun_gswt_classical_energy(model, chemical_state) / len(model["positions"])
    reshaped_energy_density = evaluate_sun_gswt_classical_energy(reshaped_model, magnetic_state) / len(reshaped_model["positions"])

    assert abs(original_energy_density - reshaped_energy_density) <= 1e-10
