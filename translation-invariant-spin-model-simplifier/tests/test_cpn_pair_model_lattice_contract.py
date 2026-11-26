import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from common.canonical_hamiltonian import compile_canonical_hamiltonian
from common.cpn_pair_model import normalize_cpn_pair_model


def _pair_matrix(dimension):
    size = dimension * dimension
    matrix = [[0.0 for _ in range(size)] for _ in range(size)]
    matrix[0][0] = 1.0
    return matrix


def _payload(site_count, dimension, source, target, translation):
    size = dimension * dimension
    return {
        "schema_version": 1,
        "model_bond_label": "cpn_pair_model",
        "classical_bond_label": "cpn",
        "local_dimension": dimension,
        "structure": {
            "lattice_vectors": [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
            ],
            "positions": [
                [float(index) / float(site_count), 0.0, 0.0]
                for index in range(site_count)
            ],
        },
        "onsite_terms": [],
        "bond_terms": [
            {
                "source": source,
                "target": target,
                "translation": list(translation),
                "matrix_shape": [size, size],
                "pair_matrix": _pair_matrix(dimension),
            }
        ],
    }


def test_single_sublattice_pair_model_declares_one_positioned_basis_site():
    normalized = normalize_cpn_pair_model(
        _payload(1, 4, source=0, target=0, translation=[1, 0, 0])
    )

    assert [site["site_ref"] for site in normalized["local_hilbert"]["sites"]] == [
        "site:0"
    ]
    assert normalized["lattice_structure"]["basis_sites"] == [
        {"site_ref": "site:0", "position": [0.0, 0.0, 0.0]}
    ]
    assert normalized["lattice_structure"]["lattice_vectors"] == [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]


def test_two_sublattice_pair_model_keeps_every_declared_position():
    normalized = normalize_cpn_pair_model(
        _payload(2, 2, source=0, target=1, translation=[1, 0, 0])
    )

    assert [site["site_ref"] for site in normalized["local_hilbert"]["sites"]] == [
        "site:0",
        "site:1",
    ]
    assert normalized["lattice_structure"]["basis_sites"] == [
        {"site_ref": "site:0", "position": [0.0, 0.0, 0.0]},
        {"site_ref": "site:1", "position": [0.5, 0.0, 0.0]},
    ]


def test_pair_model_declares_identity_symmetry_with_matrix_unit_action():
    dimension = 3
    normalized = normalize_cpn_pair_model(
        _payload(1, dimension, source=0, target=0, translation=[1, 0, 0])
    )

    assert [
        operation["operation_ref"]
        for operation in normalized["symmetry"]["operations"]
    ] == ["symmetry-operation:identity"]
    actions = normalized["local_hilbert"]["operator_bases"][
        "op_basis:retained_local_matrix"
    ]["symmetry_actions"]
    matrix = actions["symmetry-operation:identity"]["matrix"]
    assert len(matrix) == dimension * dimension
    assert all(
        row[index] == (1.0 if index == position else 0.0)
        for position, row in enumerate(matrix)
        for index in range(len(row))
    )


def test_normalized_pair_model_compiles_through_the_canonical_gate():
    normalized = normalize_cpn_pair_model(
        _payload(1, 2, source=0, target=0, translation=[1, 0, 0])
    )

    canonical = compile_canonical_hamiltonian(normalized)

    assert len(canonical["terms"]) == 1
    term = canonical["terms"][0]
    assert term["operator_family"] == "pair_matrix"
    assert [
        (entry["site"], tuple(entry["translation"])) for entry in term["cluster"]
    ] == [(0, (0, 0, 0)), (0, (1, 0, 0))]
