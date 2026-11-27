import sys
from pathlib import Path

import numpy as np
import pytest

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from common.many_body_hr_orbital_to_atom_mapping import (
    validate_many_body_hr_orbital_to_atom_mapping,
)
from common.orbital_representation import (
    OrbitalRepresentation,
    close_generator_group,
    orbital_rotation_matrix,
)

D5 = ["d_z2", "d_xz", "d_yz", "d_xy", "d_x2-y2"]
C4Z = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
C3 = np.array([[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
INVERSION = -np.eye(3)
MIRROR_X = np.diag([-1.0, 1.0, 1.0])


def test_c4z_acts_on_the_real_d_orbitals_as_the_standard_table():
    action = orbital_rotation_matrix(D5, C4Z).real

    assert np.allclose(
        action,
        np.array(
            [
                [1.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, -1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, -1.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, -1.0],
            ]
        ),
    )


def test_inversion_is_even_on_d_orbitals_and_odd_on_p_orbitals():
    assert np.allclose(orbital_rotation_matrix(D5, INVERSION).real, np.eye(5))
    assert np.allclose(
        orbital_rotation_matrix(["p_x", "p_y", "p_z"], INVERSION).real, -np.eye(3)
    )


def test_every_cubic_operation_acts_orthogonally_on_the_d_orbitals():
    group = close_generator_group(
        [
            {"rotation": C4Z, "matrix": np.eye(5)},
            {"rotation": C3, "matrix": np.eye(5)},
            {"rotation": INVERSION, "matrix": np.eye(5)},
        ]
    )

    assert len(group) == 48
    for rotation, _matrix in group:
        action = orbital_rotation_matrix(D5, rotation)
        assert np.allclose(action @ action.conj().T, np.eye(5), atol=1.0e-10)


def test_mixed_degrees_act_block_diagonally():
    characters = ["s", "d_z2", "d_xy"]

    action = orbital_rotation_matrix(characters, C4Z).real

    assert action[0, 0] == pytest.approx(1.0)
    assert np.allclose(action[0, 1:], 0.0)
    assert np.allclose(action[1:, 0], 0.0)
    assert np.allclose(action[1:, 1:], orbital_rotation_matrix(["d_z2", "d_xy"], C4Z).real)


def test_generators_close_into_the_cubic_group_and_match_the_characters():
    group = close_generator_group(
        [
            {"rotation": C4Z, "matrix": orbital_rotation_matrix(D5, C4Z)},
            {"rotation": C3, "matrix": orbital_rotation_matrix(D5, C3)},
            {"rotation": INVERSION, "matrix": orbital_rotation_matrix(D5, INVERSION)},
        ]
    )

    assert len(group) == 48
    for rotation, matrix in group:
        assert np.allclose(matrix, orbital_rotation_matrix(D5, rotation), atol=1.0e-10)


def test_a_mirror_and_a_four_fold_axis_close_into_c4v():
    group = close_generator_group(
        [
            {"rotation": C4Z, "matrix": orbital_rotation_matrix(D5, C4Z)},
            {"rotation": MIRROR_X, "matrix": orbital_rotation_matrix(D5, MIRROR_X)},
        ]
    )

    assert len(group) == 8


def test_quantization_axis_rotates_the_frame_the_characters_live_in():
    action = orbital_rotation_matrix(["p_x", "p_y", "p_z"], C4Z, [0.0, 0.0, 1.0])

    assert np.allclose(action.real, C4Z)


def test_representation_rejects_an_unknown_character():
    with pytest.raises(ValueError, match="character-unknown"):
        OrbitalRepresentation(
            {"convention": "real_spherical_harmonics", "characters": ["f_xyz"]},
            orbital_count=1,
        )


def test_representation_rejects_a_character_count_mismatch():
    with pytest.raises(ValueError, match="character-count-mismatch"):
        OrbitalRepresentation(
            {"convention": "real_spherical_harmonics", "characters": D5},
            orbital_count=3,
        )


def test_representation_rejects_a_non_unitary_generator_matrix():
    with pytest.raises(ValueError, match="must-be-unitary"):
        OrbitalRepresentation(
            {
                "convention": "generator_matrices",
                "generators": [{"rotation": C4Z, "matrix": 2.0 * np.eye(5)}],
            },
            orbital_count=5,
        )


def test_representation_rejects_a_generator_of_the_wrong_size():
    with pytest.raises(ValueError, match="generator-size-mismatch"):
        OrbitalRepresentation(
            {
                "convention": "generator_matrices",
                "generators": [{"rotation": C4Z, "matrix": np.eye(3)}],
            },
            orbital_count=5,
        )


def test_generator_lookup_returns_none_outside_the_declared_group():
    representation = OrbitalRepresentation(
        {
            "convention": "generator_matrices",
            "generators": [
                {"rotation": C4Z, "matrix": orbital_rotation_matrix(D5, C4Z)}
            ],
        },
        orbital_count=5,
    )

    assert representation.action(C4Z, C4Z) is not None
    assert representation.action(C3, C3) is None


def _mapping(representation):
    return {
        "schema_version": 1,
        "site_level_mapping": [{"site": 0, "level_indexes": list(range(10))}],
        "orbital_representation": representation,
    }


def _local_space_spec():
    return {
        "kind": "orbital_times_spin",
        "orbital_count": 5,
        "spin_dimension": 2,
        "local_dimension": 10,
    }


def test_mapping_carries_a_validated_orbital_representation():
    normalized = validate_many_body_hr_orbital_to_atom_mapping(
        _mapping({"convention": "real_spherical_harmonics", "characters": D5}),
        {"positions": [[0.0, 0.0, 0.0]]},
        _local_space_spec(),
    )

    assert normalized["orbital_representation"]["characters"] == D5


def test_mapping_without_a_representation_stays_unchanged():
    normalized = validate_many_body_hr_orbital_to_atom_mapping(
        {"schema_version": 1, "site_level_mapping": [{"site": 0, "level_indexes": list(range(10))}]},
        {"positions": [[0.0, 0.0, 0.0]]},
        _local_space_spec(),
    )

    assert "orbital_representation" not in normalized


def test_mapping_rejects_a_representation_without_an_orbital_factor():
    with pytest.raises(ValueError, match="orbital_times_spin"):
        validate_many_body_hr_orbital_to_atom_mapping(
            _mapping({"convention": "real_spherical_harmonics", "characters": D5}),
            {"positions": [[0.0, 0.0, 0.0]]},
            {"kind": "generic_multiplet", "local_dimension": 10},
        )
