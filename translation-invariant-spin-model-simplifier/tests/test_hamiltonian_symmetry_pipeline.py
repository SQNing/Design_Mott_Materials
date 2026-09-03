import sys
from copy import deepcopy
from pathlib import Path


import numpy as np
import pytest


SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(SKILL_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical.build_spin_only_solver_payload import build_spin_only_solver_payload
from classical.lt_fourier_exchange import fourier_exchange_matrix
from common.canonical_hamiltonian import (
    CanonicalHamiltonianError,
    coefficient_map,
    compile_canonical_hamiltonian,
)
from common.hamiltonian_symmetry_gate import SymmetryGateRequest, run_hamiltonian_symmetry_gate
from common.lattice_structure_builder import build_lattice_structure
from input.normalize_input import normalize_input


def _c4_operations():
    generator = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=int)
    return [
        {
            "operation_ref": f"symop:c4^{power}",
            "kind": "space_group_operation",
            "rotation": np.linalg.matrix_power(generator, power).tolist(),
            "translation": [0.0, 0.0, 0.0],
        }
        for power in range(4)
    ]


def _structured_matrix(matrix):
    matrix = np.asarray(matrix, dtype=float)
    return {
        "storage": "dense",
        "shape": list(matrix.shape),
        "scalar_type": "real_parameter_expression",
        "data": matrix.tolist(),
    }


def _representative_payload():
    orbit = {
        "orbit_ref": "bond-orbit:J",
        "kind": "pair",
        "directed": False,
        "orientation_convention": "undirected",
        "representative": {"source": 0, "target": 0, "translation": [1, 0, 0]},
        "members": [
            {
                "source": 0,
                "target": 0,
                "translation": [1, 0, 0],
                "generated_by_operation_ref": "symop:c4^0",
            },
            {
                "source": 0,
                "target": 0,
                "translation": [0, 1, 0],
                "generated_by_operation_ref": "symop:c4^1",
            },
        ],
        "reverse_orientation": {"kind": "transpose_and_swap", "transpose": True},
    }
    term = {
        "term_ref": "term:J",
        "support_ref": ["site:0", "site:0"],
        "attach_to": {
            "kind": "bond_orbit",
            "orbit_ref": "bond-orbit:J",
            "orientation": "representative",
        },
        "operator_basis_ref": "operator-basis:spin",
        "channel_kind": "two_body",
        "operator_channel": "spin_exchange",
        "payload": {
            "kind": "bilinear_exchange_matrix",
            "matrix": _structured_matrix(np.diag([1.0, 2.0, 3.0])),
            "hermiticity": "real_bilinear",
            "orientation_transform": "transpose_on_reverse",
        },
        "provenance": {"source": "representative-test"},
    }
    return {
        "schema_version": "lattice-term-contract/v1",
        "local_hilbert": {
            "sites": [
                {
                    "site_ref": "site:0",
                    "basis_ref": "basis:spin",
                    "classical_space_ref": "classical-space:spin",
                    "operator_basis_refs": ["operator-basis:spin"],
                }
            ],
            "basis_registry": {"basis:spin": {"dimension": 2}},
            "operator_bases": {
                "operator-basis:spin": {
                    "kind": "spin_vector",
                    "labels": ["Sx", "Sy", "Sz"],
                }
            },
            "classical_spaces": {
                "classical-space:spin": {"kind": "unit_vector_sphere", "dimension": 3}
            },
        },
        "lattice_structure": {
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "basis_sites": [{"site_ref": "site:0", "position": [0.0, 0.0, 0.0]}],
            "local_frames": [],
            "bond_orbits": [orbit],
            "higher_body_orbits": [],
        },
        "symmetry": {
            "source": {"international_symbol": "P4", "number": 75},
            "operations": _c4_operations(),
            "unresolved": [],
        },
        "term_attachments": {
            "site_terms": [],
            "bond_terms": [term],
            "higher_body_terms": [],
            "candidate_terms": [term],
            "term_sets": [],
        },
        "solver_request": {
            "task": "classical_ground_state",
            "symmetry_repair": False,
            "selected_term_refs": [],
            "selected_bond_orbit_refs": [],
        },
        "parameters": {},
        "provenance": {"source": "unit-test"},
    }


def _matrix_by_translation(records, translation, *, vector_key):
    for record in records:
        vector = (
            record["cluster"][1]["translation"]
            if vector_key == "cluster"
            else record["vector"]
        )
        if list(vector) == list(translation):
            return np.asarray(record["matrix" if vector_key == "vector" else "coefficient"], dtype=float)
    raise AssertionError(f"missing translation {translation}")


def test_normalization_defaults_symmetry_repair_to_false_and_preserves_true():
    source = {
        "representation": "operator",
        "support": [0, 1],
        "expression": "J1*Sz@0 Sz@1",
    }

    strict = normalize_input(source)
    repaired = normalize_input({**source, "symmetry_repair": True})

    assert strict["solver_request"]["symmetry_repair"] is False
    assert repaired["solver_request"]["symmetry_repair"] is True


def test_normalization_rejects_non_boolean_symmetry_repair_flag():
    with pytest.raises(ValueError, match="invalid-symmetry-repair-flag"):
        normalize_input(
            {
                "representation": "operator",
                "support": [0, 1],
                "expression": "J1*Sz@0 Sz@1",
                "symmetry_repair": "yes",
            }
        )


def test_lattice_structure_keeps_geometry_needed_by_shared_symmetry_action():
    lattice_vectors = [[1.0, 0.0, 0.0], [0.5, 0.8660254037844386, 0.0], [0.0, 0.0, 2.0]]
    structure = build_lattice_structure(
        {
            "lattice_model": {
                "lattice_vectors": lattice_vectors,
                "positions": [[0.0, 0.0, 0.0]],
                "types": ["A"],
            }
        }
    )

    np.testing.assert_allclose(structure["lattice_vectors"], lattice_vectors, atol=1.0e-12)
    assert structure["basis_sites"][0]["position"] == [0.0, 0.0, 0.0]


def test_representative_term_expands_with_rotated_matrices_before_gate():
    canonical = compile_canonical_hamiltonian(_representative_payload())

    assert len(canonical["terms"]) == 2
    np.testing.assert_allclose(
        _matrix_by_translation(canonical["terms"], [1, 0, 0], vector_key="cluster"),
        np.diag([1.0, 2.0, 3.0]),
        atol=1.0e-12,
    )
    np.testing.assert_allclose(
        _matrix_by_translation(canonical["terms"], [0, 1, 0], vector_key="cluster"),
        np.diag([2.0, 1.0, 3.0]),
        atol=1.0e-12,
    )
    assert run_hamiltonian_symmetry_gate(canonical, SymmetryGateRequest())["status"] == "ok"


def test_canonical_spin_only_bridge_uses_same_rotated_representative_orbit():
    bridge = build_spin_only_solver_payload(_representative_payload())
    bonds = bridge["payload"]["bonds"]

    assert len(bonds) == 2
    np.testing.assert_allclose(
        _matrix_by_translation(bonds, [1, 0, 0], vector_key="vector"),
        np.diag([1.0, 2.0, 3.0]),
        atol=1.0e-12,
    )
    np.testing.assert_allclose(
        _matrix_by_translation(bonds, [0, 1, 0], vector_key="vector"),
        np.diag([2.0, 1.0, 3.0]),
        atol=1.0e-12,
    )


def test_representative_pair_matrix_without_local_symmetry_representation_fails():
    payload = _representative_payload()
    payload["local_hilbert"]["operator_bases"]["operator-basis:spin"] = {
        "kind": "dense_local_matrix_units",
        "dimension": 2,
    }
    term = payload["term_attachments"]["bond_terms"][0]
    term["operator_channel"] = "pair_matrix"
    term["payload"] = {
        "kind": "pair_matrix",
        "matrix": _structured_matrix(np.eye(4)),
        "orientation_transform": "swap_tensor_factors_then_adjoint",
    }

    with pytest.raises(CanonicalHamiltonianError, match="symmetry-representation-unavailable"):
        compile_canonical_hamiltonian(payload)


def test_representative_pair_matrix_uses_declared_local_symmetry_representation():
    payload = _representative_payload()
    payload["local_hilbert"]["operator_bases"]["operator-basis:spin"] = {
        "kind": "dense_local_matrix_units",
        "dimension": 2,
        "symmetry_actions": {
            operation["operation_ref"]: {"matrix": np.eye(2).tolist()}
            for operation in payload["symmetry"]["operations"]
        },
    }
    term = payload["term_attachments"]["bond_terms"][0]
    term["operator_channel"] = "pair_matrix"
    term["payload"] = {
        "kind": "pair_matrix",
        "matrix": _structured_matrix([[1.0, 0.25], [0.25, 2.0]]),
        "orientation_transform": "swap_tensor_factors_then_adjoint",
    }

    canonical = compile_canonical_hamiltonian(payload)

    assert len(canonical["terms"]) == 2
    assert {tuple(item["cluster"][1]["translation"]) for item in canonical["terms"]} == {
        (1, 0, 0),
        (0, 1, 0),
    }
    for item in canonical["terms"]:
        np.testing.assert_allclose(item["coefficient"], [[1.0, 0.25], [0.25, 2.0]])


def test_representative_explicit_and_validated_adapter_paths_are_fourier_equivalent():
    representative_payload = _representative_payload()
    representative_model = compile_canonical_hamiltonian(representative_payload)

    explicit_payload = _representative_payload()
    source = explicit_payload["term_attachments"]["bond_terms"][0]
    source["attach_to"] = {"kind": "explicit_cluster", "orientation": "explicit"}
    source["cluster"] = [
        {"site": 0, "translation": [0, 0, 0]},
        {"site": 0, "translation": [1, 0, 0]},
    ]
    y_term = deepcopy(source)
    y_term["term_ref"] = "term:Jy"
    y_term["cluster"][1]["translation"] = [0, 1, 0]
    y_term["payload"]["matrix"] = _structured_matrix(np.diag([2.0, 1.0, 3.0]))
    explicit_payload["term_attachments"]["bond_terms"] = [source, y_term]
    explicit_model = compile_canonical_hamiltonian(explicit_payload)

    assert coefficient_map(representative_model) == coefficient_map(explicit_model)
    gate = run_hamiltonian_symmetry_gate(representative_model, SymmetryGateRequest())
    representative_bridge = build_spin_only_solver_payload(representative_payload)["payload"]
    validated_bridge = build_spin_only_solver_payload(gate)["payload"]
    for q in ([0.0, 0.0, 0.0], [0.137, 0.291, 0.0], [0.5, 0.25, 0.0]):
        np.testing.assert_allclose(
            fourier_exchange_matrix(representative_bridge, q),
            fourier_exchange_matrix(validated_bridge, q),
            atol=1.0e-12,
        )
