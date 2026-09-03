import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest


SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(SKILL_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from common.hamiltonian_symmetry_action import transform_term
from common.hamiltonian_symmetry_gate import SymmetryGateRequest, run_hamiltonian_symmetry_gate


def _operation(ref, rotation):
    return {
        "operation_ref": ref,
        "rotation": np.asarray(rotation, dtype=int).tolist(),
        "translation": [0.0, 0.0, 0.0],
    }


def _model(terms, operations, *, operator_bases=None):
    return {
        "schema_version": "canonical-hamiltonian/v1",
        "lattice_structure": {
            "lattice_vectors": np.eye(3).tolist(),
            "basis_sites": [{"site_ref": "site:0", "position": [0.0, 0.0, 0.0]}],
            "local_frames": [],
        },
        "local_hilbert": {
            "operator_bases": operator_bases
            or {"operator-basis:spin": {"kind": "spin_vector", "labels": ["Sx", "Sy", "Sz"]}}
        },
        "symmetry": {"source": {"international_symbol": "test"}, "operations": operations, "unresolved": []},
        "terms": terms,
    }


def _bond(family, coefficient, translation=(1, 0, 0), *, basis="operator-basis:spin"):
    return {
        "term_ref": f"term:{family}",
        "arity": 2,
        "cluster": [
            {"site": 0, "translation": [0, 0, 0]},
            {"site": 0, "translation": list(translation)},
        ],
        "operator_family": family,
        "coefficient": deepcopy(coefficient),
        "coordinate_convention": "global_crystallographic",
        "orientation_sector": "default",
        "operator_basis_ref": basis,
        "permutation_action": {},
        "adjoint_action": {"kind": "self_adjoint"},
    }


def test_declared_nonspin_adjoint_representation_is_used_on_every_tensor_leg():
    swap = [[0.0, 1.0], [1.0, 0.0]]
    operation = _operation("symop:swap", np.eye(3))
    context = _model(
        [],
        [operation],
        operator_bases={
            "operator-basis:pseudo": {
                "kind": "dense_local_operator_basis",
                "labels": ["A", "B"],
                "symmetry_actions": {"symop:swap": {"matrix": swap}},
            }
        },
    )
    term = _bond("pair_matrix", [[1.0, 2.0], [3.0, 4.0]], basis="operator-basis:pseudo")

    transformed = transform_term(term, operation, context)[0]

    np.testing.assert_allclose(transformed["coefficient"], [[4.0, 3.0], [2.0, 1.0]])


def test_nonspin_term_without_declared_representation_fails_with_specific_code():
    identity = _operation("symop:identity", np.eye(3))
    model = _model(
        [_bond("pair_matrix", np.eye(2).tolist(), basis="operator-basis:pseudo")],
        [identity],
        operator_bases={
            "operator-basis:pseudo": {"kind": "dense_local_operator_basis", "labels": ["A", "B"]}
        },
    )

    result = run_hamiltonian_symmetry_gate(model, SymmetryGateRequest())

    assert result["status"] == "error"
    assert result["completion"]["reason"] == "symmetry-representation-unavailable"


def test_gate_rejects_nonhermitian_onsite_tensor_before_symmetry_comparison():
    identity = _operation("symop:identity", np.eye(3))
    onsite = {
        "term_ref": "term:onsite",
        "arity": 1,
        "cluster": [{"site": 0, "translation": [0, 0, 0]}],
        "operator_family": "quadratic_spin_tensor",
        "coefficient": [[1.0, 2.0j, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "coordinate_convention": "global_crystallographic",
        "operator_basis_ref": "operator-basis:spin",
        "adjoint_action": {"kind": "self_adjoint"},
    }

    result = run_hamiltonian_symmetry_gate(_model([onsite], [identity]), SymmetryGateRequest(repair=True))

    assert result["status"] == "error"
    assert result["completion"]["reason"] == "hamiltonian-not-hermitian"


def test_ring_forward_and_inverse_coefficients_must_be_adjoint_pairs():
    identity = _operation("symop:identity", np.eye(3))
    ring = {
        "term_ref": "term:ring",
        "arity": 4,
        "cluster": [
            {"site": 0, "translation": translation}
            for translation in ([0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0])
        ],
        "operator_family": "cyclic_ring_exchange",
        "coefficient": {"forward": 1.0 + 2.0j, "inverse": 1.0 + 2.0j},
        "coordinate_convention": "global_crystallographic",
        "operator_basis_ref": "operator-basis:spin",
        "adjoint_action": {"kind": "cycle_inverse"},
    }

    result = run_hamiltonian_symmetry_gate(_model([ring], [identity]), SymmetryGateRequest())

    assert result["completion"]["reason"] == "hamiltonian-not-hermitian"


def test_mirror_forbidden_dm_component_is_zeroed_by_group_average():
    identity = _operation("symop:identity", np.eye(3))
    mirror_y = _operation("symop:mirror-y", np.diag([1, -1, 1]))
    exchange = np.eye(3)
    exchange[0, 1] = 0.6
    exchange[1, 0] = -0.6
    model = _model(
        [_bond("bilinear_exchange_tensor", exchange.tolist())],
        [identity, mirror_y],
    )

    strict = run_hamiltonian_symmetry_gate(model, SymmetryGateRequest())
    repaired = run_hamiltonian_symmetry_gate(model, SymmetryGateRequest(repair=True))

    assert strict["completion"]["reason"] == "hamiltonian-symmetry-validation-failed"
    assert strict["symmetry_validation"]["forbidden_terms"]
    assert strict["hamiltonian_provenance"]["input_model"]["canonical_model_ref"].startswith(
        "canonical-model:"
    )
    repaired_matrix = np.asarray(repaired["solver_model"]["terms"][0]["coefficient"])
    assert repaired_matrix[0, 1] == pytest.approx(0.0, abs=1.0e-12)
    assert repaired_matrix[1, 0] == pytest.approx(0.0, abs=1.0e-12)
    np.testing.assert_allclose(repaired_matrix, repaired_matrix.T.conjugate(), atol=1.0e-12)
    provenance = repaired["hamiltonian_provenance"]
    assert provenance["solver_model"]["canonical_model_ref"].startswith("canonical-model:")
    assert provenance["symmetry_operation"]["target_group"]["operation_count"] == 2
    assert provenance["symmetry_operation"]["tolerance"]["absolute"] == pytest.approx(1.0e-10)
    assert repaired["symmetry_repair_report"]["downstream_model_ref"] == provenance["solver_model"][
        "canonical_model_ref"
    ]


def test_biquadratic_group_average_generates_complete_c4_orbit():
    c4 = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=int)
    operations = [_operation(f"symop:c4^{power}", np.linalg.matrix_power(c4, power)) for power in range(4)]
    model = _model([_bond("biquadratic_exchange", 2.0)], operations)

    repaired = run_hamiltonian_symmetry_gate(model, SymmetryGateRequest(repair=True))

    assert repaired["status"] == "ok"
    assert repaired["symmetry_repair_report"]["validation_after"]["status"] == "passed"
    assert {tuple(term["cluster"][1]["translation"]) for term in repaired["solver_model"]["terms"]} == {
        (1, 0, 0),
        (0, 1, 0),
    }


def test_declared_operator_actions_compose_and_gate_an_invariant_pseudospin_tensor():
    identity = _operation("symop:identity", np.eye(3))
    swap_operation = _operation("symop:swap", np.eye(3))
    swap = [[0.0, 1.0], [1.0, 0.0]]
    bases = {
        "operator-basis:pseudo": {
            "kind": "dense_local_operator_basis",
            "labels": ["A", "B"],
            "symmetry_actions": {
                "symop:identity": {"matrix": np.eye(2).tolist()},
                "symop:swap": {"matrix": swap},
            },
        }
    }
    term = _bond("pair_matrix", np.eye(2).tolist(), basis="operator-basis:pseudo")
    model = _model([term], [identity, swap_operation], operator_bases=bases)

    once = transform_term(term, swap_operation, model)[0]
    twice = transform_term(once, swap_operation, model)[0]
    direct = transform_term(term, identity, model)[0]

    np.testing.assert_allclose(twice["coefficient"], direct["coefficient"], atol=1.0e-12)
    assert twice["cluster"] == direct["cluster"]
    assert run_hamiltonian_symmetry_gate(model, SymmetryGateRequest())["status"] == "ok"
