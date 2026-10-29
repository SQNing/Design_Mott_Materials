"""Independent Hilbert-space checks for matrix-unit symmetry and bond reversal."""
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common.canonical_hamiltonian import swap_pair_matrix, compile_canonical_hamiltonian
from common.operator_family_symmetry import transform_operator_coefficient, canonicalize_family_term
from common.hamiltonian_symmetry_gate import run_hamiltonian_symmetry_gate
from research.examples import retained_three_level


def test_dense_operator_symmetry_matches_hilbert_space_conjugation():
    rng = np.random.default_rng(20261029)
    unitary = np.linalg.qr(rng.normal(size=(3, 3)) + 1j * rng.normal(size=(3, 3)))[0]
    action = np.kron(unitary, unitary.conjugate())
    onsite = rng.normal(size=(3, 3)) + 1j * rng.normal(size=(3, 3))
    onsite += onsite.conjugate().T
    transformed = transform_operator_coefficient(
        {"operator_family": "local_operator_matrix", "arity": 1, "coefficient": onsite.tolist()},
        [action], [0])
    assert np.allclose(transformed, unitary @ onsite @ unitary.conjugate().T)
    pair = rng.normal(size=(9, 9)) + 1j * rng.normal(size=(9, 9))
    pair += pair.conjugate().T
    transformed = transform_operator_coefficient(
        {"operator_family": "pair_matrix", "arity": 2, "coefficient": pair.tolist(),
         "coefficient_representation": "full_pair_operator"},
        [action, action], [0, 1])
    both = np.kron(unitary, unitary)
    assert np.allclose(transformed, both @ pair @ both.conjugate().T)
    left, right = rng.normal(size=3) + 1j * rng.normal(size=3), rng.normal(size=3) + 1j * rng.normal(size=3)
    assert np.allclose(np.vdot(np.kron(left, right), pair @ np.kron(left, right)),
                       np.vdot(np.kron(right, left), np.asarray(swap_pair_matrix(pair)) @ np.kron(right, left)))


def test_onsite_hermiticity_is_checked_before_solver():
    model = retained_three_level()
    model["term_attachments"]["site_terms"][0]["payload"]["matrix"]["data"][0][1] = .2
    gate = run_hamiltonian_symmetry_gate(compile_canonical_hamiltonian(model))
    assert gate["status"] == "error"
    assert gate["completion"]["reason"] == "hamiltonian-not-hermitian"


def test_full_pair_compilation_retains_asymmetric_bond_orientation():
    from research.contracts import restore_complex
    model = retained_three_level()
    pair = model["term_attachments"]["bond_terms"][0]
    raw = np.asarray(restore_complex(pair["payload"]["matrix"]["data"]), dtype=complex)
    # Opposite translation is represented by swapping local Hilbert factors.
    pair["cluster"][1]["translation"] = [-1, 0, 0]
    canonical = compile_canonical_hamiltonian(model)
    term = next(t for t in canonical["terms"] if t["operator_family"] == "pair_matrix")
    assert term["coefficient_representation"] == "full_pair_operator"
    assert np.allclose(term["coefficient"], swap_pair_matrix(raw))
    assert not np.allclose(swap_pair_matrix(raw), raw.conjugate().T)
