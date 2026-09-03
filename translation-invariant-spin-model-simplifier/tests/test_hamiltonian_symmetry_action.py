import sys
from pathlib import Path


import numpy as np


SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(SKILL_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical.build_spin_only_solver_payload import _cartesian_spin_rotation_from_fractional
from common.hamiltonian_symmetry_action import (
    axial_spin_rotation,
    cartesian_rotation,
    map_cluster,
    transform_term,
)
from common.lattice_structure_builder import build_symmetry_record


def _operation(rotation, translation=(0.0, 0.0, 0.0), ref="symop:test"):
    return {
        "operation_ref": ref,
        "rotation": [list(row) for row in rotation],
        "translation": list(translation),
    }


def _single_site_context():
    return {
        "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "basis_sites": [{"site_ref": "site:0", "position": [0.0, 0.0, 0.0]}],
        "local_frames": [],
    }


def _two_site_context(local_frames=None):
    return {
        "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "basis_sites": [
            {"site_ref": "site:0", "position": [0.0, 0.0, 0.0]},
            {"site_ref": "site:1", "position": [0.5, 0.0, 0.0]},
        ],
        "local_frames": list(local_frames or []),
    }


def _bond_term(matrix, *, source=0, target=0, translation=(1, 0, 0), convention="global_crystallographic"):
    return {
        "term_ref": "term:J",
        "arity": 2,
        "cluster": [
            {"site": source, "translation": [0, 0, 0]},
            {"site": target, "translation": list(translation)},
        ],
        "operator_family": "bilinear_exchange_tensor",
        "coefficient": np.asarray(matrix, dtype=float).tolist(),
        "coordinate_convention": convention,
        "orientation_sector": "default",
        "permutation_action": {"kind": "swap_tensor_legs"},
        "adjoint_action": {"kind": "conjugate_transpose"},
        "operator_basis_ref": "operator-basis:spin",
        "provenance": {},
    }


def test_cartesian_rotation_is_metric_correct_for_nonorthogonal_lattice():
    lattice = [[1.0, 0.0, 0.0], [0.5, np.sqrt(3.0) / 2.0, 0.0], [0.0, 0.0, 2.0]]
    fractional_c6 = [[0, -1, 0], [1, 1, 0], [0, 0, 1]]

    result = cartesian_rotation(lattice, fractional_c6)

    np.testing.assert_allclose(result @ result.T, np.eye(3), atol=1.0e-12)
    np.testing.assert_allclose(np.linalg.det(result), 1.0, atol=1.0e-12)


def test_axial_spin_rotation_makes_inversion_act_trivially_on_spin():
    inversion = -np.eye(3, dtype=int)

    result = axial_spin_rotation(np.eye(3), inversion)

    np.testing.assert_allclose(result, np.eye(3), atol=1.0e-12)


def test_map_cluster_tracks_nonsymmorphic_like_cell_offsets():
    half_translation = _operation(np.eye(3, dtype=int), translation=(0.5, 0.0, 0.0))

    mapped = map_cluster(
        half_translation,
        [
            {"site": 0, "translation": [0, 0, 0]},
            {"site": 1, "translation": [0, 0, 0]},
        ],
        _two_site_context(),
    )

    assert mapped == [
        {"site": 1, "translation": [0, 0, 0]},
        {"site": 0, "translation": [1, 0, 0]},
    ]


def test_global_anisotropic_tensor_rotates_instead_of_being_copied():
    c4 = _operation([[0, -1, 0], [1, 0, 0], [0, 0, 1]])
    matrix = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]])
    spin_rotation = axial_spin_rotation(np.eye(3), c4["rotation"])

    transformed = transform_term(_bond_term(matrix), c4, _single_site_context())

    assert len(transformed) == 1
    assert transformed[0]["cluster"] == [
        {"site": 0, "translation": [0, 0, 0]},
        {"site": 0, "translation": [0, 1, 0]},
    ]
    np.testing.assert_allclose(
        transformed[0]["coefficient"],
        spin_rotation @ matrix @ spin_rotation.T,
        atol=1.0e-12,
    )


def test_local_frame_action_uses_original_and_mapped_site_frames():
    identity = np.eye(3)
    quarter_turn = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    context = _two_site_context(
        local_frames=[
            {"site_ref": "site:0", "rotation_matrix": identity.tolist()},
            {"site_ref": "site:1", "rotation_matrix": quarter_turn.tolist()},
        ]
    )
    half_translation = _operation(np.eye(3, dtype=int), translation=(0.5, 0.0, 0.0))
    matrix = np.diag([1.0, 2.0, 3.0])

    transformed = transform_term(
        _bond_term(matrix, source=0, target=1, translation=(0, 0, 0), convention="local_frames"),
        half_translation,
        context,
    )[0]

    expected_left = np.linalg.inv(quarter_turn) @ identity @ identity
    expected_right = np.linalg.inv(identity) @ identity @ quarter_turn
    np.testing.assert_allclose(
        transformed["symmetry_action"]["leg_actions"][0], expected_left, atol=1.0e-12
    )
    np.testing.assert_allclose(
        transformed["symmetry_action"]["leg_actions"][1], expected_right, atol=1.0e-12
    )
    np.testing.assert_allclose(
        transformed["coefficient"], expected_left @ matrix @ expected_right.T, atol=1.0e-12
    )


def test_legacy_rotation_wrapper_uses_shared_axial_rotation():
    lattice = [[1.0, 0.0, 0.0], [0.5, np.sqrt(3.0) / 2.0, 0.0], [0.0, 0.0, 2.0]]
    fractional_c6 = [[0, -1, 0], [1, 1, 0], [0, 0, 1]]

    np.testing.assert_allclose(
        _cartesian_spin_rotation_from_fractional(lattice, fractional_c6),
        axial_spin_rotation(lattice, fractional_c6),
        atol=1.0e-12,
    )


def test_symmetry_record_stores_cartesian_axial_rotations():
    lattice = [[1.0, 0.0, 0.0], [0.5, np.sqrt(3.0) / 2.0, 0.0], [0.0, 0.0, 2.0]]
    symmetry = build_symmetry_record(
        {
            "lattice_model": {
                "lattice_vectors": lattice,
                "positions": [[0.0, 0.0, 0.0]],
                "types": ["A"],
            },
            "hamiltonian_model": {
                "bond_terms": [{"bond_ref": "bond:J", "payload": {"kind": "bilinear_exchange_matrix"}}]
            },
        }
    )
    operations = {entry["operation_ref"]: entry for entry in symmetry["operations"]}

    assert len(symmetry["spin_space_rotations"]) > 1
    for record in symmetry["spin_space_rotations"]:
        operation = operations[record["operation_ref"]]
        expected = axial_spin_rotation(lattice, operation["rotation"])
        np.testing.assert_allclose(record["matrix"], expected, atol=1.0e-12)
