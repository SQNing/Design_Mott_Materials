import sys
from pathlib import Path


import numpy as np
import pytest


SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(SKILL_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from common.canonical_hamiltonian import CanonicalHamiltonianError
from common.operator_family_symmetry import (
    canonicalize_family_term,
    registered_operator_families,
    transform_operator_coefficient,
)


def _cluster(sites):
    return [
        {"site": int(site), "translation": [0, 0, 0]}
        for site in sites
    ]


def _term(family, coefficient, sites):
    return {
        "term_ref": f"term:{family}",
        "arity": len(sites),
        "cluster": _cluster(sites),
        "operator_family": family,
        "coefficient": coefficient,
        "coordinate_convention": "global_crystallographic",
        "orientation_sector": "positive",
        "permutation_action": {},
        "adjoint_action": {"kind": "self_adjoint"},
        "provenance": {},
    }


def test_registry_contains_required_initial_operator_families():
    assert set(registered_operator_families()) >= {
        "spin_vector",
        "quadratic_spin_tensor",
        "bilinear_exchange_tensor",
        "biquadratic_exchange",
        "scalar_chirality",
        "cyclic_ring_exchange",
        "generic_local_operator_tensor",
    }


def test_generic_rank_three_tensor_applies_one_action_per_leg_then_permutation():
    coefficient = np.arange(8, dtype=float).reshape(2, 2, 2)
    actions = [
        np.array([[0.0, 1.0], [1.0, 0.0]]),
        np.diag([2.0, 3.0]),
        np.array([[1.0, 1.0], [0.0, 1.0]]),
    ]
    term = _term("generic_local_operator_tensor", coefficient.tolist(), (0, 1, 2))

    result = transform_operator_coefficient(term, actions, permutation=[2, 0, 1])

    expected = np.einsum("ia,jb,kc,abc->ijk", *actions, coefficient)
    expected = np.transpose(expected, axes=[2, 0, 1])
    np.testing.assert_allclose(result, expected, atol=1.0e-12)


def test_biquadratic_scalar_is_invariant_under_orthogonal_spin_actions():
    c4 = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    term = _term("biquadratic_exchange", 2.75, (0, 1))

    result = transform_operator_coefficient(term, [c4, c4], permutation=[0, 1])

    assert result == pytest.approx(2.75)


def test_scalar_chirality_changes_sign_under_odd_cluster_permutation():
    positive = canonicalize_family_term(_term("scalar_chirality", 1.25, (0, 1, 2)))
    odd = canonicalize_family_term(_term("scalar_chirality", 1.25, (0, 2, 1)))

    assert positive["cluster"] == odd["cluster"]
    assert positive["coefficient"] == pytest.approx(-odd["coefficient"])


def test_scalar_chirality_is_invariant_under_cyclic_permutation():
    reference = canonicalize_family_term(_term("scalar_chirality", 1.25, (0, 1, 2)))
    cyclic = canonicalize_family_term(_term("scalar_chirality", 1.25, (1, 2, 0)))

    assert reference["cluster"] == cyclic["cluster"]
    assert reference["coefficient"] == pytest.approx(cyclic["coefficient"])


def test_cyclic_ring_reversal_swaps_forward_and_inverse_coefficients():
    forward = canonicalize_family_term(
        _term("cyclic_ring_exchange", {"forward": 2.0, "inverse": 3.0}, (0, 1, 2, 3))
    )
    reversed_term = canonicalize_family_term(
        _term("cyclic_ring_exchange", {"forward": 2.0, "inverse": 3.0}, (0, 3, 2, 1))
    )

    assert forward["cluster"] == reversed_term["cluster"]
    assert forward["coefficient"] == {"forward": 2.0, "inverse": 3.0}
    assert reversed_term["coefficient"] == {"forward": 3.0, "inverse": 2.0}


def test_unknown_operator_family_fails_instead_of_being_ignored():
    term = _term("opaque_unknown_family", 1.0, (0, 1, 2))

    with pytest.raises(CanonicalHamiltonianError, match="symmetry-projection-unsupported-term"):
        transform_operator_coefficient(term, [np.eye(1)] * 3, permutation=[0, 1, 2])
