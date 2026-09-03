from copy import deepcopy
import sys
from pathlib import Path


import numpy as np
import pytest


SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(SKILL_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from common.canonical_hamiltonian import canonical_model_hash
from common.hamiltonian_symmetry_gate import (
    HamiltonianSymmetryError,
    SymmetryGateRequest,
    require_current_symmetry_stamp,
    run_hamiltonian_symmetry_gate,
    validate_hamiltonian_symmetry,
)


def _c4_operations():
    return [
        {
            "operation_ref": f"symop:c4^{power}",
            "rotation": np.linalg.matrix_power(
                np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=int), power
            ).tolist(),
            "translation": [0.0, 0.0, 0.0],
        }
        for power in range(4)
    ]


def _bond(term_ref, translation, matrix):
    return {
        "term_ref": term_ref,
        "arity": 2,
        "cluster": [
            {"site": 0, "translation": [0, 0, 0]},
            {"site": 0, "translation": list(translation)},
        ],
        "operator_family": "bilinear_exchange_tensor",
        "coefficient": np.asarray(matrix, dtype=float).tolist(),
        "coordinate_convention": "global_crystallographic",
        "orientation_sector": "default",
        "permutation_action": {"kind": "swap_tensor_legs"},
        "adjoint_action": {"kind": "conjugate_transpose"},
        "operator_basis_ref": "operator-basis:spin",
        "provenance": {"input_term_ref": term_ref},
    }


def _model(*, include_y=True, y_matrix=None, operations=None):
    x_matrix = np.diag([1.0, 2.0, 3.0])
    if y_matrix is None:
        y_matrix = np.diag([2.0, 1.0, 3.0])
    terms = [_bond("term:x", [1, 0, 0], x_matrix)]
    if include_y:
        terms.append(_bond("term:y", [0, 1, 0], y_matrix))
    return {
        "schema_version": "canonical-hamiltonian/v1",
        "lattice_structure": {
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "basis_sites": [{"site_ref": "site:0", "position": [0.0, 0.0, 0.0]}],
            "local_frames": [],
        },
        "local_hilbert": {
            "operator_bases": {
                "operator-basis:spin": {"kind": "spin_vector", "labels": ["Sx", "Sy", "Sz"]}
            }
        },
        "symmetry": {
            "source": {"international_symbol": "P4", "number": 75},
            "operations": list(_c4_operations() if operations is None else operations),
            "unresolved": [],
        },
        "terms": terms,
        "source_schema_version": "lattice-term-contract/v1",
    }


def _term_for_translation(model, translation):
    target = list(translation)
    for term in model["terms"]:
        if term["cluster"][1]["translation"] == target:
            return term
    raise AssertionError(f"missing term for translation {target}")


def test_validate_symmetric_hamiltonian_passes_every_target_operation():
    report = validate_hamiltonian_symmetry(_model(), SymmetryGateRequest())

    assert report["status"] == "passed"
    assert report["target_group"]["operation_count"] == 4
    assert report["failed_operations"] == []
    assert report["max_absolute_residual"] == pytest.approx(0.0, abs=1.0e-12)


def test_strict_missing_partner_fails_before_solver_and_reports_subgroup():
    input_model = _model(include_y=False)
    before = deepcopy(input_model)

    result = run_hamiltonian_symmetry_gate(input_model, SymmetryGateRequest(repair=False))

    assert input_model == before
    assert result["status"] == "error"
    assert result["completion"] == {
        "status": "failed",
        "reason": "hamiltonian-symmetry-validation-failed",
        "stopping_condition": "pre-solver-symmetry-gate",
    }
    assert result["solver_execution"] == {"started": False, "backends_run": []}
    assert result["symmetry_validation"]["missing_symmetry_partners"]
    subgroup = result["symmetry_validation"]["input_hamiltonian_subgroup"]
    assert subgroup["status"] == "verified-subgroup"
    assert set(subgroup["operation_refs"]) == {"symop:c4^0", "symop:c4^2"}


def test_group_average_adds_missing_partner_and_revalidates():
    input_model = _model(include_y=False)
    result = run_hamiltonian_symmetry_gate(input_model, SymmetryGateRequest(repair=True))

    assert result["status"] == "ok"
    assert result["symmetry_repair_report"]["status"] == "repaired"
    assert result["symmetry_repair_report"]["validation_after"]["status"] == "passed"
    assert result["warnings"][0]["code"] == "hamiltonian-symmetry-repaired"
    repaired = result["solver_model"]
    np.testing.assert_allclose(
        _term_for_translation(repaired, [1, 0, 0])["coefficient"],
        0.5 * np.diag([1.0, 2.0, 3.0]),
        atol=1.0e-12,
    )
    np.testing.assert_allclose(
        _term_for_translation(repaired, [0, 1, 0])["coefficient"],
        0.5 * np.diag([2.0, 1.0, 3.0]),
        atol=1.0e-12,
    )
    assert result["symmetry_repair_report"]["changes"]["added_terms"]


def test_projection_is_idempotent_and_second_pass_is_already_symmetric():
    first = run_hamiltonian_symmetry_gate(
        _model(include_y=False), SymmetryGateRequest(repair=True)
    )
    second = run_hamiltonian_symmetry_gate(
        first["solver_model"], SymmetryGateRequest(repair=True)
    )

    assert canonical_model_hash(first["solver_model"]) == canonical_model_hash(second["solver_model"])
    assert second["symmetry_repair_report"]["status"] == "already-symmetric"
    assert second["warnings"] == []


def test_inconsistent_equivalent_bonds_are_averaged_not_overwritten():
    input_model = _model(y_matrix=np.diag([4.0, 1.0, 3.0]))

    strict = run_hamiltonian_symmetry_gate(input_model, SymmetryGateRequest(repair=False))
    repaired = run_hamiltonian_symmetry_gate(input_model, SymmetryGateRequest(repair=True))

    assert strict["status"] == "error"
    np.testing.assert_allclose(
        _term_for_translation(repaired["solver_model"], [1, 0, 0])["coefficient"],
        np.diag([1.0, 3.0, 3.0]),
        atol=1.0e-12,
    )
    np.testing.assert_allclose(
        _term_for_translation(repaired["solver_model"], [0, 1, 0])["coefficient"],
        np.diag([3.0, 1.0, 3.0]),
        atol=1.0e-12,
    )
    assert repaired["symmetry_repair_report"]["changes"]["modified_terms"]


def test_validation_stamp_detects_any_physical_model_mutation():
    result = run_hamiltonian_symmetry_gate(_model(), SymmetryGateRequest())
    changed = deepcopy(result["solver_model"])
    changed["terms"][0]["coefficient"][0][0] += 0.1

    with pytest.raises(HamiltonianSymmetryError, match="symmetry-validation-stamp-stale"):
        require_current_symmetry_stamp(changed, result["symmetry_validation_stamp"])


def test_unknown_structural_symmetry_fails_in_both_modes():
    model = _model(operations=[])
    model["symmetry"]["unresolved"] = [{"code": "unresolved-lattice-symmetry"}]

    for repair in (False, True):
        result = run_hamiltonian_symmetry_gate(model, SymmetryGateRequest(repair=repair))
        assert result["status"] == "error"
        assert result["completion"]["reason"] == "structural-symmetry-unavailable"


def test_unsupported_term_family_fails_instead_of_being_skipped():
    model = _model()
    model["terms"].append(
        {
            "term_ref": "term:opaque",
            "arity": 3,
            "cluster": [
                {"site": 0, "translation": [0, 0, 0]},
                {"site": 0, "translation": [1, 0, 0]},
                {"site": 0, "translation": [0, 1, 0]},
            ],
            "operator_family": "opaque_unknown_family",
            "coefficient": 1.0,
            "coordinate_convention": "global_crystallographic",
            "orientation_sector": "default",
            "permutation_action": {},
            "adjoint_action": {},
            "operator_basis_ref": "operator-basis:spin",
            "provenance": {},
        }
    )

    result = run_hamiltonian_symmetry_gate(model, SymmetryGateRequest(repair=True))

    assert result["status"] == "error"
    assert result["completion"]["reason"] == "symmetry-projection-unsupported-term"
