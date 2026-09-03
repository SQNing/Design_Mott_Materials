#!/usr/bin/env python3
"""Operator-family rules used by Hamiltonian space-group actions."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass

import numpy as np

from common.canonical_hamiltonian import CanonicalHamiltonianError


@dataclass(frozen=True)
class OperatorFamilyAction:
    name: str
    coefficient_kind: str
    permutation_kind: str


_FAMILIES = {
    "spin_vector": OperatorFamilyAction("spin_vector", "rank_one", "site"),
    "quadratic_spin_tensor": OperatorFamilyAction("quadratic_spin_tensor", "onsite_rank_two", "site"),
    "bilinear_exchange_tensor": OperatorFamilyAction("bilinear_exchange_tensor", "tensor_product", "bond_reverse"),
    "bilinear_exchange_matrix": OperatorFamilyAction("bilinear_exchange_matrix", "tensor_product", "bond_reverse"),
    "pair_matrix": OperatorFamilyAction("pair_matrix", "tensor_product", "bond_reverse"),
    "biquadratic_exchange": OperatorFamilyAction("biquadratic_exchange", "orthogonal_scalar", "bond_reverse"),
    "scalar_chirality": OperatorFamilyAction("scalar_chirality", "oriented_scalar", "cyclic_oriented"),
    "cyclic_ring_exchange": OperatorFamilyAction("cyclic_ring_exchange", "cycle_pair", "dihedral"),
    "generic_local_operator_tensor": OperatorFamilyAction(
        "generic_local_operator_tensor", "tensor_product", "declared"
    ),
}


def registered_operator_families():
    return dict(_FAMILIES)


def _family(term):
    name = str(term.get("operator_family") or "")
    try:
        return _FAMILIES[name]
    except KeyError as exc:
        raise CanonicalHamiltonianError("symmetry-projection-unsupported-term", name) from exc


def _apply_tensor_legs(coefficient, actions):
    result = np.asarray(coefficient, dtype=complex)
    if result.ndim != len(actions):
        raise CanonicalHamiltonianError(
            "operator-tensor-rank-mismatch", f"rank {result.ndim}, actions {len(actions)}"
        )
    for axis, action in enumerate(actions):
        matrix = np.asarray(action, dtype=complex)
        if matrix.ndim != 2 or matrix.shape[1] != result.shape[axis]:
            raise CanonicalHamiltonianError(
                "operator-representation-shape-mismatch",
                f"axis {axis}, action {matrix.shape}, tensor {result.shape}",
            )
        result = np.tensordot(matrix, result, axes=(1, axis))
        result = np.moveaxis(result, 0, axis)
    return result


def _permutation_parity(permutation):
    inversions = 0
    values = [int(index) for index in permutation]
    for left in range(len(values)):
        for right in range(left + 1, len(values)):
            if values[left] > values[right]:
                inversions += 1
    return -1 if inversions % 2 else 1


def _clean_numeric(value, *, tolerance=1.0e-14):
    array = np.asarray(value, dtype=complex)
    if array.ndim == 0:
        scalar = complex(array.item())
        real = 0.0 if abs(scalar.real) <= tolerance else float(scalar.real)
        imag = 0.0 if abs(scalar.imag) <= tolerance else float(scalar.imag)
        return real if imag == 0.0 else complex(real, imag)
    result = array.tolist()

    def clean(child):
        if isinstance(child, list):
            return [clean(entry) for entry in child]
        scalar = complex(child)
        real = 0.0 if abs(scalar.real) <= tolerance else float(scalar.real)
        imag = 0.0 if abs(scalar.imag) <= tolerance else float(scalar.imag)
        return real if imag == 0.0 else complex(real, imag)

    return clean(result)


def _require_common_orthogonal_action(actions, *, tolerance=1.0e-10):
    if not actions:
        raise CanonicalHamiltonianError("symmetry-representation-unavailable")
    reference = np.asarray(actions[0], dtype=float)
    if reference.shape != (3, 3) or not np.allclose(
        reference @ reference.T, np.eye(3), atol=tolerance, rtol=tolerance
    ):
        raise CanonicalHamiltonianError("invalid-operator-representation")
    for action in actions[1:]:
        if not np.allclose(action, reference, atol=tolerance, rtol=tolerance):
            raise CanonicalHamiltonianError(
                "symmetry-projection-unsupported-term",
                "compact invariant requires a common spin frame",
            )
    return reference


def transform_operator_coefficient(term, leg_actions, permutation):
    """Apply local operator representations and reorder mapped tensor legs."""

    family = _family(term)
    permutation = [int(index) for index in permutation]
    if sorted(permutation) != list(range(int(term.get("arity", len(permutation))))):
        raise CanonicalHamiltonianError("invalid-cluster-permutation", permutation)
    coefficient = term.get("coefficient")

    if family.coefficient_kind == "tensor_product":
        transformed = _apply_tensor_legs(coefficient, leg_actions)
        transformed = np.transpose(transformed, axes=permutation)
        return _clean_numeric(transformed)
    if family.coefficient_kind == "rank_one":
        if len(leg_actions) != 1:
            raise CanonicalHamiltonianError("operator-tensor-rank-mismatch")
        return _clean_numeric(np.asarray(leg_actions[0], dtype=complex) @ np.asarray(coefficient, dtype=complex))
    if family.coefficient_kind == "onsite_rank_two":
        if len(leg_actions) != 1:
            raise CanonicalHamiltonianError("operator-tensor-rank-mismatch")
        action = np.asarray(leg_actions[0], dtype=complex)
        tensor = np.asarray(coefficient, dtype=complex)
        return _clean_numeric(action @ tensor @ action.conjugate().T)
    if family.coefficient_kind == "orthogonal_scalar":
        _require_common_orthogonal_action(leg_actions)
        return _clean_numeric(coefficient)
    if family.coefficient_kind == "oriented_scalar":
        action = _require_common_orthogonal_action(leg_actions)
        factor = float(np.linalg.det(action)) * _permutation_parity(permutation)
        return _clean_numeric(complex(coefficient) * factor)
    if family.coefficient_kind == "cycle_pair":
        if not isinstance(coefficient, Mapping):
            raise CanonicalHamiltonianError("invalid-ring-exchange-coefficient")
        result = {"forward": coefficient.get("forward"), "inverse": coefficient.get("inverse")}
        if _permutation_parity(permutation) < 0:
            result = {"forward": result["inverse"], "inverse": result["forward"]}
        return result
    raise CanonicalHamiltonianError("symmetry-projection-unsupported-term", family.name)


def _translate_sequence(sequence):
    if not sequence:
        return [], [0, 0, 0]
    origin = [int(value) for value in sequence[0].get("translation", [0, 0, 0])]
    translated = [
        {
            "site": int(entry["site"]),
            "translation": [
                int(entry.get("translation", [0, 0, 0])[axis]) - origin[axis]
                for axis in range(3)
            ],
        }
        for entry in sequence
    ]
    return translated, [-value for value in origin]


def _sequence_key(sequence):
    return tuple(
        (int(entry["site"]), tuple(int(value) for value in entry["translation"]))
        for entry in sequence
    )


def _cycle_candidates(cluster):
    count = len(cluster)
    for shift in range(count):
        yield [(shift + offset) % count for offset in range(count)], False
    reversed_base = [0] + list(range(count - 1, 0, -1))
    for shift in range(count):
        yield [reversed_base[(shift + offset) % count] for offset in range(count)], True


def canonicalize_family_term(term):
    """Canonicalize family-specific cluster equivalences and coefficients."""

    family = _family(term)
    result = deepcopy(dict(term))
    cluster = list(result.get("cluster") or [])
    if len(cluster) != int(result.get("arity", len(cluster))):
        raise CanonicalHamiltonianError("canonical-term-identity-unresolved", result.get("term_ref"))

    if family.permutation_kind not in {"cyclic_oriented", "dihedral"}:
        translated, shift = _translate_sequence(cluster)
        result["cluster"] = translated
        result["canonicalization"] = {
            "permutation": list(range(len(cluster))),
            "translated_by": shift,
            "orientation_reversed": False,
        }
        return result

    candidates = []
    for permutation, reversed_orientation in _cycle_candidates(cluster):
        sequence = [cluster[index] for index in permutation]
        translated, shift = _translate_sequence(sequence)
        candidates.append(
            (_sequence_key(translated), permutation, reversed_orientation, translated, shift)
        )
    _key, permutation, reversed_orientation, translated, shift = min(
        candidates, key=lambda entry: (entry[0], entry[2], entry[1])
    )
    result["cluster"] = translated
    if family.name == "scalar_chirality" and reversed_orientation:
        result["coefficient"] = _clean_numeric(-complex(result["coefficient"]))
    if family.name == "cyclic_ring_exchange" and reversed_orientation:
        coefficient = result.get("coefficient")
        if not isinstance(coefficient, Mapping):
            raise CanonicalHamiltonianError("invalid-ring-exchange-coefficient")
        result["coefficient"] = {
            "forward": coefficient.get("inverse"),
            "inverse": coefficient.get("forward"),
        }
    result["orientation_sector"] = "positive"
    result["canonicalization"] = {
        "permutation": list(permutation),
        "translated_by": shift,
        "orientation_reversed": bool(reversed_orientation),
    }
    return result
