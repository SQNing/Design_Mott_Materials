import sys
from pathlib import Path

import numpy as np
import pytest

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from common.canonical_hamiltonian import compile_canonical_hamiltonian
from common.cpn_pair_model import normalize_cpn_pair_model
from common.hamiltonian_symmetry_gate import run_hamiltonian_symmetry_gate
from common.orbital_representation import orbital_rotation_matrix

PAULI = [
    np.array(matrix, dtype=complex)
    for matrix in ([[0, 1], [1, 0]], [[0, -1j], [1j, 0]], [[1, 0], [0, -1]])
]
SPIN = [0.5 * matrix for matrix in PAULI]
CHARACTERS = ["d_z2", "d_xz", "d_yz", "d_xy", "d_x2-y2"]
C4Z = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
C3 = np.array([[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
INVERSION = -np.eye(3)
C4X = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]])


def _pair_matrix(weights):
    """Orbital-selective Heisenberg exchange, sum_A w_A S_A . S_A.

    Each orbital channel couples only to itself, which is the model an orbital
    representation is needed for: the exchange is invariant under operations
    that permute the retained orbitals, and under nothing that mixes them.
    """
    total = np.zeros((100, 100), dtype=complex)
    for orbital, weight in enumerate(weights):
        projector = np.zeros((5, 5))
        projector[orbital, orbital] = 1.0
        local = [np.kron(projector, spin) for spin in SPIN]
        total += weight * sum(np.kron(operator, operator) for operator in local)
    return total


def _payload(weights, representation):
    matrix = _pair_matrix(weights)
    bond_terms = []
    for axis in range(3):
        for sign in (1, -1):
            translation = [0, 0, 0]
            translation[axis] = sign
            bond_terms.append(
                {
                    "source": 0,
                    "target": 0,
                    "translation": translation,
                    "matrix_shape": [100, 100],
                    "pair_matrix": matrix.tolist(),
                }
            )
    return {
        "schema_version": 1,
        "model_bond_label": "cpn_pair_model",
        "classical_bond_label": "cpn",
        "local_dimension": 10,
        "retained_local_space": {
            "dimension": 10,
            "factorization": {
                "kind": "orbital_times_spin",
                "orbital_count": 5,
                "spin_dimension": 2,
            },
            "tensor_factor_order": "orbital_major_spin_minor",
            "basis_labels": [
                f"{spin}_orb{index + 1}" for index in range(5) for spin in ("up", "down")
            ],
            **(
                {"orbital_representation": representation}
                if representation is not None
                else {}
            ),
        },
        "structure": {
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "positions": [[0.0, 0.0, 0.0]],
        },
        "onsite_terms": [],
        "bond_terms": bond_terms,
    }


def _character_record():
    return {"convention": "real_spherical_harmonics", "characters": CHARACTERS}


def _generator_record():
    return {
        "convention": "generator_matrices",
        "generators": [
            {
                "rotation": C4Z.tolist(),
                "matrix": orbital_rotation_matrix(CHARACTERS, C4Z).tolist(),
            },
            {
                "rotation": C3.tolist(),
                "matrix": orbital_rotation_matrix(CHARACTERS, C3).tolist(),
            },
            {
                "rotation": INVERSION.tolist(),
                "matrix": orbital_rotation_matrix(CHARACTERS, INVERSION).tolist(),
            },
        ],
    }


def _certified(payload):
    normalized = normalize_cpn_pair_model(payload)
    canonical = compile_canonical_hamiltonian(normalized)
    gate = run_hamiltonian_symmetry_gate(canonical)
    return normalized, gate


def test_t2g_exchange_certifies_the_full_cubic_group():
    normalized, gate = _certified(
        _payload([0.0, 1.0, 1.0, 1.0, 0.0], _character_record())
    )

    assert normalized["symmetry_synthesis"]["operation_count"] == 48
    assert gate["status"] == "ok"
    assert gate["symmetry_validation"]["max_absolute_residual"] < 1.0e-12


def test_single_orbital_exchange_certifies_only_its_stabiliser():
    normalized, gate = _certified(
        _payload([0.0, 0.0, 0.0, 1.0, 0.0], _character_record())
    )

    # The three t2g orbitals form one orbit under the cubic group, so the
    # stabiliser of a single one has 48 / 3 operations. A four-fold rotation
    # about z only flips the sign of d_xy and therefore survives, while one
    # about x turns d_xy into d_xz and does not.
    assert normalized["symmetry_synthesis"]["operation_count"] == 16
    assert gate["status"] == "ok"
    rotations = [
        np.asarray(operation["rotation"], dtype=float)
        for operation in normalized["symmetry"]["operations"]
    ]
    assert any(np.allclose(rotation, C4Z) for rotation in rotations)
    assert not any(np.allclose(rotation, C4X) for rotation in rotations)


def test_the_same_model_without_a_representation_stays_identity_only():
    normalized, gate = _certified(_payload([0.0, 1.0, 1.0, 1.0, 0.0], None))

    assert normalized["symmetry_synthesis"] == {
        "mode": "identity-only",
        "operation_count": 1,
    }
    assert gate["status"] == "ok"


def test_generator_matrices_certify_the_same_group_as_the_characters():
    weights = [0.0, 0.0, 0.0, 1.0, 0.0]

    from_characters, _gate = _certified(_payload(weights, _character_record()))
    from_generators, _gate = _certified(_payload(weights, _generator_record()))

    assert (
        from_characters["symmetry_synthesis"]
        == from_generators["symmetry_synthesis"]
    )
    assert {
        operation["operation_ref"] for operation in from_characters["symmetry"]["operations"]
    } == {
        operation["operation_ref"] for operation in from_generators["symmetry"]["operations"]
    }


def test_a_malformed_representation_raises_instead_of_degrading():
    payload = _payload(
        [0.0, 0.0, 0.0, 1.0, 0.0],
        {"convention": "real_spherical_harmonics", "characters": ["d_xy"]},
    )

    with pytest.raises(ValueError, match="character-count-mismatch"):
        normalize_cpn_pair_model(payload)
