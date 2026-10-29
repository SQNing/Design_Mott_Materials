import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from test_workflow import cubic_model
from test_workflow import triclinic_dm_model


def test_matrix_free_cubic_spectrum_against_independent_dense_pauli_operators():
    # Independent tensor-product construction catches spin factors, site ordering
    # and double bonds that arise on a length-two periodic direction.
    from three_dimensional.workflow import run_three_dimensional_workflow
    result = run_three_dimensional_workflow(cubic_model(), {
        "task": "quantum_low_energy", "supercell_shape": [2, 2, 2],
        "spin": 0.5, "eigenvalues": 4, "seed": 91,
    })
    assert result["status"] == "ok"
    paulis = [np.array([[0, 1], [1, 0]]) / 2,
              np.array([[0, -1j], [1j, 0]]) / 2,
              np.diag([0.5, -0.5])]
    dense = np.zeros((256, 256), dtype=complex)
    for cell in np.ndindex((2, 2, 2)):
        source = np.ravel_multi_index(cell, (2, 2, 2))
        for direction in np.eye(3, dtype=int):
            target = np.ravel_multi_index(tuple((np.array(cell) + direction) % 2), (2, 2, 2))
            for sigma in paulis:
                product = np.ones((1, 1))
                for site in range(8):
                    product = np.kron(product, sigma if site in (source, target) else np.eye(2))
                dense += product
    expected = np.linalg.eigvalsh(dense)[:4]
    np.testing.assert_allclose(result["calculation"]["eigenvalues"], expected, atol=1e-9)
    assert max(result["calculation"]["residual_norms"]) < 1e-8
    assert result["calculation"]["dense_hamiltonian_allocated"] is False


def test_complex_dm_quantum_spectrum_against_dense_three_site_construction():
    from three_dimensional.workflow import run_three_dimensional_workflow
    model = triclinic_dm_model()
    result = run_three_dimensional_workflow(model, {
        "task": "quantum_low_energy", "supercell_shape": [1, 1, 1],
        "spin": 0.5, "eigenvalues": 3, "seed": 33,
    })
    paulis = [np.array([[0, 1], [1, 0]]) / 2,
              np.array([[0, -1j], [1j, 0]]) / 2, np.diag([0.5, -0.5])]
    dense = np.zeros((8, 8), dtype=complex)
    for term in model["terms"]:
        source, target = (site["site"] for site in term["cluster"])
        for a in range(3):
            for b in range(3):
                factors = [np.eye(2, dtype=complex) for _ in range(3)]
                factors[source], factors[target] = paulis[a], paulis[b]
                dense += term["coefficient"][a][b] * np.kron(np.kron(factors[0], factors[1]), factors[2])
    assert result["status"] == "ok"
    np.testing.assert_allclose(result["calculation"]["eigenvalues"], np.linalg.eigvalsh(dense)[:3], atol=1e-10)


def test_sixteen_site_cubic_quantum_ground_state_without_dense_matrix():
    from three_dimensional.workflow import run_three_dimensional_workflow
    result = run_three_dimensional_workflow(cubic_model(-1), {
        "task": "quantum_low_energy", "supercell_shape": [2, 2, 4],
        "spin": 0.5, "eigenvalues": 2, "seed": 18,
    })["calculation"]
    assert result["status"] == "ok"
    assert result["hilbert_dimension"] == 65536
    np.testing.assert_allclose(result["eigenvalues"], [-12, -12], atol=1e-8)
    assert max(result["residual_norms"]) < 1e-8
    assert result["dense_hamiltonian_allocated"] is False
