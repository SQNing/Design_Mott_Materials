from copy import deepcopy
import sys
from pathlib import Path


import numpy as np
import pytest


SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(SKILL_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from common.canonical_hamiltonian import (
    canonical_model_hash,
    canonical_term_key,
    canonicalize_cluster,
    coefficient_map,
    compile_canonical_hamiltonian,
)
from common.lattice_term_contract import ContractValidationError, validate_lattice_term_payload


def _real(value):
    return {"kind": "real", "value": float(value)}


def _parameter(ref):
    return {"kind": "parameter_ref", "parameter_ref": str(ref)}


def _matrix(data):
    return {
        "storage": "dense",
        "shape": [len(data), len(data[0])],
        "scalar_type": "real_parameter_expression",
        "data": data,
    }


def _base_payload(terms):
    return {
        "schema_version": "lattice-term-contract/v1",
        "local_hilbert": {
            "sites": [
                {
                    "site_ref": "site:0",
                    "basis_ref": "basis:spin",
                    "operator_basis_refs": ["operator-basis:spin"],
                },
                {
                    "site_ref": "site:1",
                    "basis_ref": "basis:spin",
                    "operator_basis_refs": ["operator-basis:spin"],
                },
            ],
            "basis_registry": {"basis:spin": {"dimension": 2}},
            "operator_bases": {
                "operator-basis:spin": {
                    "kind": "spin_vector",
                    "labels": ["Sx", "Sy", "Sz"],
                }
            },
            "classical_spaces": {},
        },
        "lattice_structure": {
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "basis_sites": [
                {"site_ref": "site:0", "index": 0, "fractional_position": [0.0, 0.0, 0.0]},
                {"site_ref": "site:1", "index": 1, "fractional_position": [0.5, 0.5, 0.0]},
            ],
            "bond_orbits": [],
            "higher_body_orbits": [],
        },
        "symmetry": {
            "source": "explicit",
            "operations": [
                {
                    "operation_ref": "symop:0",
                    "rotation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                    "translation": [0.0, 0.0, 0.0],
                }
            ],
        },
        "term_attachments": {
            "site_terms": [],
            "bond_terms": list(terms),
            "higher_body_terms": [],
            "candidate_terms": [],
            "term_sets": [],
        },
        "solver_request": {"task": "classical_ground_state"},
        "parameters": {
            "param:J": {"value": 2.5},
            "param:K": {"value": -0.75},
        },
        "provenance": {"source": "unit-test"},
    }


def _bond_term(term_ref, source, target, translation, diagonal):
    return {
        "term_ref": term_ref,
        "support_ref": [f"site:{source}", f"site:{target}"],
        "cluster": [
            {"site": source, "translation": [2, -1, 0]},
            {"site": target, "translation": [2 + translation[0], -1 + translation[1], translation[2]]},
        ],
        "operator_basis_ref": "operator-basis:spin",
        "channel_kind": "two_body",
        "operator_channel": "spin_exchange",
        "payload": {
            "kind": "bilinear_exchange_matrix",
            "matrix": _matrix(
                [
                    [diagonal, _real(0.0), _real(0.0)],
                    [_real(0.0), diagonal, _real(0.0)],
                    [_real(0.0), _real(0.0), diagonal],
                ]
            ),
            "hermiticity": "real_bilinear",
            "orientation_transform": "transpose_on_reverse",
        },
        "provenance": {"input_term_ref": term_ref},
    }


def _payload_with_order(order):
    terms = {
        "x": _bond_term("term:x", 0, 1, [1, 0, 0], _parameter("param:J")),
        "y": _bond_term("term:y", 1, 0, [0, 1, 0], _parameter("param:K")),
    }
    return _base_payload([terms[label] for label in order])


def test_compile_canonical_hamiltonian_is_order_independent_and_non_mutating():
    left_input = _payload_with_order(("x", "y"))
    left_before = deepcopy(left_input)

    left = compile_canonical_hamiltonian(left_input)
    right = compile_canonical_hamiltonian(_payload_with_order(("y", "x")))

    assert left_input == left_before
    assert left["schema_version"] == "canonical-hamiltonian/v1"
    assert coefficient_map(left) == coefficient_map(right)
    assert canonical_model_hash(left) == canonical_model_hash(right)
    assert [term["term_ref"] for term in left["terms"]] == ["term:x", "term:y"]


def test_compile_resolves_parameterized_matrix_and_translates_cluster_origin():
    model = compile_canonical_hamiltonian(_payload_with_order(("x",)))
    term = model["terms"][0]

    assert term["arity"] == 2
    assert term["cluster"] == [
        {"site": 0, "translation": [0, 0, 0]},
        {"site": 1, "translation": [1, 0, 0]},
    ]
    np.testing.assert_allclose(np.asarray(term["coefficient"]), 2.5 * np.eye(3))
    assert term["provenance"]["input_term_ref"] == "term:x"


def test_canonicalize_cluster_reports_applied_permutation_and_translation():
    result = canonicalize_cluster(
        [
            {"site": 1, "translation": [4, 3, -2]},
            {"site": 0, "translation": [3, 3, -2]},
        ],
        family="bilinear_exchange_tensor",
    )

    assert result["cluster"] == [
        {"site": 0, "translation": [0, 0, 0]},
        {"site": 1, "translation": [1, 0, 0]},
    ]
    assert result["permutation"] == [1, 0]
    assert result["translated_by"] == [-3, -3, 2]
    assert result["orientation_reversed"] is True


def test_oriented_three_body_term_keeps_orientation_sector_in_key():
    term = {
        "term_ref": "term:chi",
        "arity": 3,
        "cluster": [
            {"site": 0, "translation": [0, 0, 0]},
            {"site": 1, "translation": [0, 0, 0]},
            {"site": 0, "translation": [1, 0, 0]},
        ],
        "operator_family": "scalar_chirality",
        "coefficient": 1.25,
        "orientation_sector": "positive",
        "permutation_action": {"kind": "alternating"},
        "adjoint_action": {"kind": "self_adjoint"},
        "provenance": {},
    }

    key = canonical_term_key(term)

    assert key[0] == "scalar_chirality"
    assert key[-1] == "positive"


def test_model_hash_changes_when_a_physical_coefficient_changes():
    baseline = compile_canonical_hamiltonian(_payload_with_order(("x",)))
    changed_payload = _payload_with_order(("x",))
    changed_payload["parameters"]["param:J"]["value"] = 2.6
    changed = compile_canonical_hamiltonian(changed_payload)

    assert canonical_model_hash(baseline) != canonical_model_hash(changed)


def _higher_body_term(**overrides):
    term = {
        "term_ref": "term:chi",
        "arity": 3,
        "cluster": [
            {"site": 0, "translation": [0, 0, 0]},
            {"site": 1, "translation": [0, 0, 0]},
            {"site": 0, "translation": [1, 0, 0]},
        ],
        "operator_family": "scalar_chirality",
        "coefficient": _real(1.0),
        "permutation_action": {"kind": "alternating"},
        "adjoint_action": {"kind": "self_adjoint"},
        "payload": {"kind": "scalar_chirality"},
    }
    term.update(overrides)
    return term


def test_contract_rejects_higher_body_term_without_permutation_action():
    payload = _base_payload([])
    term = _higher_body_term()
    term.pop("permutation_action")
    payload["term_attachments"]["higher_body_terms"] = [term]

    with pytest.raises(ContractValidationError, match="higher-body-permutation-action-required"):
        validate_lattice_term_payload(payload)


def test_contract_accepts_complete_higher_body_symmetry_metadata():
    payload = _base_payload([])
    payload["term_attachments"]["higher_body_terms"] = [_higher_body_term()]

    assert validate_lattice_term_payload(payload) is payload
