"""Model builders for quantum ED tests (identity-symmetry term contracts)."""

import numpy as np


def spin_bond_model(lattice_vectors, basis_positions, bonds):
    """lattice-term-contract/v1 model with explicit bilinear bonds.

    ``bonds``: list of (source_site, target_site, translation, 3x3 matrix).
    Symmetry is declared as P1 identity only; do not reuse these models for
    symmetry-gate physics tests.
    """
    return {
        "schema_version": "lattice-term-contract/v1",
        "lattice_structure": {
            "lattice_vectors": [list(map(float, v)) for v in lattice_vectors],
            "basis_sites": [{"site_ref": "site:%d" % i, "position": list(map(float, p))}
                            for i, p in enumerate(basis_positions)]},
        "local_hilbert": {
            "operator_bases": {"operator-basis:spin": {"kind": "spin_vector",
                                                       "labels": ["Sx", "Sy", "Sz"]}},
            "classical_spaces": {"classical-space:spin": {"kind": "unit_vector_sphere",
                                                          "dimension": 3}}},
        "symmetry": {"source": {"international_symbol": "P1", "number": 1},
                     "operations": [{"operation_ref": "symop:0",
                                     "rotation": np.eye(3, dtype=int).tolist(),
                                     "translation": [0, 0, 0]}],
                     "unresolved": []},
        "parameters": {},
        "term_attachments": {"site_terms": [], "higher_body_terms": [],
                             "bond_terms": [
                                 {"term_ref": "term:b%d" % index,
                                  "cluster": [{"site": int(source), "translation": [0, 0, 0]},
                                              {"site": int(target),
                                               "translation": [int(v) for v in translation]}],
                                  "operator_basis_ref": "operator-basis:spin",
                                  "coordinate_convention": "global_crystallographic",
                                  "payload": {"kind": "bilinear_exchange_matrix",
                                              "matrix": np.asarray(matrix, dtype=float).tolist()}}
                                 for index, (source, target, translation, matrix)
                                 in enumerate(bonds)]}}


def chain_model(exchange=1.0, second_neighbor=0.0):
    """1D Heisenberg chain along x (J2 optional), P1 symmetry."""
    bonds = [(0, 0, (1, 0, 0), exchange * np.eye(3))]
    if second_exchange := float(second_neighbor):
        bonds.append((0, 0, (2, 0, 0), second_exchange * np.eye(3)))
    return spin_bond_model(np.eye(3), [[0, 0, 0]], bonds)


def kitaev_chain_model(exchange=1.0):
    """Bond-directional xx coupling: breaks total-Sz conservation."""
    matrix = np.zeros((3, 3))
    matrix[0, 0] = exchange
    return spin_bond_model(np.eye(3), [[0, 0, 0]], [(0, 0, (1, 0, 0), matrix)])


def honeycomb_model(exchange=1.0):
    """Nearest-neighbor honeycomb; A at origin, B at (a1+a2)/3."""
    sqrt3_2 = float(np.sqrt(3) / 2)
    vectors = [[1, 0, 0], [0.5, sqrt3_2, 0], [0, 0, 1]]
    positions = [[0, 0, 0], [1 / 3, 1 / 3, 0]]
    bonds = [(0, 1, (0, 0, 0), exchange * np.eye(3)),
             (0, 1, (-1, 0, 0), exchange * np.eye(3)),
             (0, 1, (0, -1, 0), exchange * np.eye(3))]
    return spin_bond_model(vectors, positions, bonds)


def heisenberg_dense_reference(model, shape, spin):
    """Independent dense full-basis Hamiltonian for cross-checks."""
    from common.canonical_hamiltonian import compile_canonical_hamiltonian
    from common.hamiltonian_symmetry_gate import SymmetryGateRequest, run_hamiltonian_symmetry_gate
    from three_dimensional.spin_payload import global_spin_payload
    from three_dimensional.spin_system import PeriodicSpinSystem
    from three_dimensional.quantum_operators import spin_operators
    if model.get("schema_version") == "lattice-term-contract/v1":
        model = compile_canonical_hamiltonian(model)
    gate = run_hamiltonian_symmetry_gate(model, SymmetryGateRequest(repair=False))
    system = PeriodicSpinSystem(global_spin_payload(gate), shape)
    operators = spin_operators(spin)
    d = operators.shape[1]
    dimension = d ** system.site_count
    dense = np.zeros((dimension, dimension), dtype=complex)
    grouped = {}
    for source, target, matrix in zip(system.source, system.target, system.matrices):
        key = (min(int(source), int(target)), max(int(source), int(target)))
        mat = matrix if source <= target else matrix.T
        grouped[key] = grouped.get(key, np.zeros((3, 3))) + mat
    for (i, j), matrix in grouped.items():
        for a in range(3):
            for b in range(3):
                if abs(matrix[a, b]) < 1e-15:
                    continue
                ops_ab = [np.eye(d)] * system.site_count
                ops_ab[i] = operators[a]
                ops_ab[j] = operators[b]
                term = ops_ab[0]
                for factor in ops_ab[1:]:
                    term = np.kron(term, factor)
                dense += matrix[a, b] * term
    return dense
