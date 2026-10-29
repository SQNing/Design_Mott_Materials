"""Regress the real-coefficient bridge failure found by the pyrochlore example."""

import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[2]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from classical.build_spin_only_solver_payload import _canonical_scalar_to_float
from test_workflow import triclinic_dm_model


@pytest.mark.parametrize("value", [1.25 + 0j, {"kind": "complex", "re": 1.25, "im": 0.0}])
def test_real_complex_scalar_representations_reach_the_real_spin_bridge(value):
    # Native complex numbers arise from canonical reversal of real directed bonds.
    assert _canonical_scalar_to_float(value, {}) == 1.25


@pytest.mark.parametrize("value", [1.25 + .01j, {"kind": "complex", "re": 1.25, "im": .01}])
def test_nonreal_exchange_is_not_silently_projected_to_a_real_hamiltonian(value):
    # A blanket .real cast would change a genuinely complex Hamiltonian.
    with pytest.raises(ValueError, match="spin-only exchange matrices must be real"):
        _canonical_scalar_to_float(value, {})


def test_normalized_multisublattice_dm_model_runs_through_public_quantum_cli():
    # Catches the compiler -> symmetry gate -> real spin bridge regression,
    # including the transpose/sign of a reversed DM bond, without a paper oracle.
    original = triclinic_dm_model()
    model = {key: value for key, value in original.items() if key not in {"schema_version", "terms"}}
    model["schema_version"] = "lattice-term-contract/v1"
    bonds = []
    for index, term in enumerate(original["terms"]):
        cluster, matrix = term["cluster"], np.asarray(term["coefficient"])
        if index == 0:
            # Reversing a real directed interaction does not change its physics.
            cluster = [{"site": cluster[1]["site"], "translation": [0, 0, 0]},
                       {"site": cluster[0]["site"],
                        "translation": [-value for value in cluster[1]["translation"]]}]
            matrix = matrix.T
        bonds.append({"term_ref": term["term_ref"], "cluster": cluster,
                      "operator_basis_ref": "operator-basis:spin",
                      "payload": {"kind": "bilinear_exchange_matrix", "matrix": matrix.tolist()}})
    model["term_attachments"] = {"site_terms": [], "higher_body_terms": [], "bond_terms": bonds}
    request = {"task": "quantum_low_energy", "supercell_shape": [1, 1, 1],
               "spin": .5, "eigenvalues": 3, "seed": 33}
    process = subprocess.run([sys.executable, "-B", str(SCRIPTS / "three_dimensional/workflow.py")],
                             input=json.dumps({"model": model, "request": request}),
                             capture_output=True, text=True, check=False)
    assert process.returncode == 0, process.stderr
    result = json.loads(process.stdout)
    assert result["status"] == "ok"
    assert result["symmetry_validation"]["status"] == "passed"
    assert result["symmetry_validation"]["target_group"]["operation_count"] == 1

    # Direct tensor products of spin-1/2 matrices in a separate 8-dimensional
    # construction. No production spin, pair-operator or matvec helper is used.
    paulis = [np.array([[0, 1], [1, 0]]) / 2,
              np.array([[0, -1j], [1j, 0]]) / 2, np.diag([.5, -.5])]
    dense = np.zeros((8, 8), dtype=complex)
    for term in original["terms"]:
        source, target = (site["site"] for site in term["cluster"])
        for alpha in range(3):
            for beta in range(3):
                factors = [np.eye(2, dtype=complex) for _ in range(3)]
                factors[source], factors[target] = paulis[alpha], paulis[beta]
                dense += term["coefficient"][alpha][beta] * np.kron(np.kron(factors[0], factors[1]), factors[2])
    np.testing.assert_allclose(result["calculation"]["eigenvalues"],
                               np.linalg.eigvalsh(dense)[:3], atol=1e-10, rtol=0)
    assert max(result["calculation"]["residual_norms"]) < 1e-8
