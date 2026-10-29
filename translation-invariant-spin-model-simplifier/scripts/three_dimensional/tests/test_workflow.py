"""Physical tests for the additive generic 3D entry point (no paper dispatch)."""

import itertools
import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[2]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def cubic_model(exchange=1.0):
    operations = []
    for permutation in itertools.permutations(range(3)):
        for signs in itertools.product((-1, 1), repeat=3):
            rotation = np.eye(3, dtype=int)[list(permutation)] * np.array(signs)[:, None]
            operations.append({
                "operation_ref": "symop:%d" % len(operations),
                "rotation": rotation.tolist(), "translation": [0, 0, 0],
            })
    return {
        "schema_version": "canonical-hamiltonian/v1",
        "lattice_structure": {
            "lattice_vectors": np.eye(3).tolist(),
            "basis_sites": [{"site_ref": "site:0", "position": [0, 0, 0]}],
        },
        "local_hilbert": {
            "operator_bases": {"operator-basis:spin": {"kind": "spin_vector"}},
            "classical_spaces": {"classical-space:spin": {"kind": "unit_vector_sphere"}},
        },
        "symmetry": {
            "source": {"international_symbol": "Pm-3m", "number": 221},
            "operations": operations, "unresolved": [],
        },
        "terms": [bond(0, 0, delta, exchange * np.eye(3), "term:%d" % axis)
                  for axis, delta in enumerate(np.eye(3, dtype=int))],
    }


def bond(source, target, delta, matrix, ref):
    return {
        "term_ref": ref, "arity": 2,
        "cluster": [{"site": source, "translation": [0, 0, 0]},
                    {"site": target, "translation": list(map(int, delta))}],
        "operator_family": "bilinear_exchange_tensor",
        "coefficient": np.asarray(matrix).tolist(),
        "coordinate_convention": "global_crystallographic",
        "operator_basis_ref": "operator-basis:spin",
        "orientation_sector": "default",
        "adjoint_action": {"kind": "self_adjoint"},
    }


def triclinic_dm_model():
    model = cubic_model()
    model["lattice_structure"] = {
        "lattice_vectors": [[1.0, 0, 0], [0.13, 1.1, 0], [0.21, 0.32, 1.2]],
        "basis_sites": [{"site_ref": "site:%d" % i, "position": position}
                        for i, position in enumerate([[0, 0, 0], [0.21, 0.13, 0.27], [0.37, 0.51, 0.19]])],
    }
    model["symmetry"] = {"source": {"international_symbol": "P1", "number": 1},
                         "operations": [{"operation_ref": "symop:identity",
                                         "rotation": np.eye(3, dtype=int).tolist(), "translation": [0, 0, 0]}],
                         "unresolved": []}
    model["terms"] = [
        bond(0, 1, [1, 0, 0], [[1, .4, .1], [-.2, .7, 0], [.3, 0, 1.2]], "term:a"),
        bond(1, 2, [0, 1, 1], [[-.8, 0, .2], [0, -.5, .3], [-.2, -.3, -.4]], "term:b"),
        bond(2, 0, [0, 0, 1], np.diag([.2, .3, .4]), "term:c"),
    ]
    return model


def test_cubic_tensor_fourier_through_real_symmetry_gate():
    # Catches loss of either the z bonds or the reverse-bond factor of two.
    from three_dimensional.workflow import run_three_dimensional_workflow
    result = run_three_dimensional_workflow(cubic_model(), {
        "task": "fourier_exchange_spectrum",
        "reduced_momenta": [[0, 0, 0], [0.5, 0.5, 0.5], [0.25, 0, 0.5]],
    })
    assert result["status"] == "ok"
    assert result["symmetry_validation"]["target_group"]["operation_count"] == 48
    np.testing.assert_allclose(result["calculation"]["value"],
                               [[6, 6, 6], [-6, -6, -6], [0, 0, 0]], atol=1e-12)


@pytest.mark.parametrize("exchange", [-1.0, 1.0])
def test_cubic_fixed_length_minimum_reaches_finite_cell_bound(exchange):
    # Catches missing periodic bonds, wrong spin normalization or an LT-only state.
    from three_dimensional.workflow import run_three_dimensional_workflow
    result = run_three_dimensional_workflow(cubic_model(exchange), {
        "task": "classical_ground_state", "supercell_shape": [2, 2, 2],
        "spin_length": 0.5, "starts": 3, "seed": 42,
    })
    calculation = result["calculation"]
    assert result["status"] == "ok"
    assert calculation["energy_per_cell"] == pytest.approx(-0.75, abs=1e-8)
    assert calculation["finite_cell_lt_lower_bound_per_cell"] == pytest.approx(-0.75)
    assert calculation["stationarity_max_norm"] < 1e-6
    assert calculation["finite_cell_bound_gap"] < 1e-8
    assert calculation["infinite_lattice_certified"] is False
    spins = np.array(calculation["spins"])
    np.testing.assert_allclose(np.linalg.norm(spins, axis=-1), 0.5, atol=1e-12)


def test_cubic_ferromagnetic_magnons_and_zero_point_energy():
    # Catches missing 3D dispersion, spin factors and an incorrect vacuum offset.
    from three_dimensional.workflow import run_three_dimensional_workflow
    result = run_three_dimensional_workflow(cubic_model(-1.0), {
        "task": "spin_wave_spectrum", "supercell_shape": [1, 1, 1], "spin": 0.5,
        "reference_spins": [[0, 0, 0.5]],
        "reduced_momenta": [[0, 0, 0], [0.5, 0, 0], [0.5, 0.5, 0.5]],
        "zero_point_mesh": [4, 4, 4],
    })
    assert result["status"] == "ok"
    result = result["calculation"]
    np.testing.assert_allclose([point["bands"] for point in result["dispersion"]],
                               [[0], [2], [6]], atol=1e-10)
    assert result["zero_point"]["energy_per_primitive_cell"] == pytest.approx(0.0, abs=1e-12)
    assert result["stability"]["is_stationary"]


def test_spin_one_gswt_retains_the_second_local_excited_mode():
    from three_dimensional.workflow import run_three_dimensional_workflow
    result = run_three_dimensional_workflow(cubic_model(-1), {
        "task": "spin_wave_spectrum", "supercell_shape": [1, 1, 1], "spin": 1.0,
        "reference_spins": [[0, 0, 1]],
        "reduced_momenta": [[0, 0, 0], [0.5, 0, 0], [0.5, 0.5, 0.5]],
    })
    assert result["status"] == "ok"
    actual = [sorted(point["bands"]) for point in result["calculation"]["dispersion"]]
    np.testing.assert_allclose(actual, [[0, 12], [4, 12], [12, 12]], atol=1e-10)


def test_cubic_antiferromagnetic_zero_point_integral():
    # Independent textbook one-magnon integral in the *primitive* cubic BZ.
    # A wrong magnetic-cell normalization changes this correction by eight.
    from three_dimensional.workflow import run_three_dimensional_workflow
    directions = [[0, 0, 0.5 * (-1) ** sum(cell)] for cell in np.ndindex((2, 2, 2))]
    result = run_three_dimensional_workflow(cubic_model(1.0), {
        "task": "spin_wave_spectrum", "supercell_shape": [2, 2, 2], "spin": 0.5,
        "reference_spins": directions, "reduced_momenta": [[0.25, 0, 0]],
        "zero_point_mesh": [4, 4, 4],
    })
    assert result["status"] == "ok"
    primitive_q = (np.array(list(np.ndindex((8, 8, 8)))) + 0.5) / 8
    gamma = np.mean(np.cos(2 * np.pi * primitive_q), axis=1)
    expected = np.mean(1.5 * (np.sqrt(1 - gamma ** 2) - 1))
    assert result["calculation"]["zero_point"]["energy_per_primitive_cell"] == pytest.approx(expected, abs=1e-10)


def test_tensor_dm_fourier_matches_independent_real_space_hessian():
    # Independent real-space Bloch projection detects DM transpose/phase errors
    # that an isotropic one-sublattice benchmark cannot see.
    from three_dimensional.workflow import run_three_dimensional_workflow
    model = triclinic_dm_model()
    shape, basis = (4, 2, 2), 3
    q = np.array([0.25, 0.5, 0.5])
    hessian = np.zeros((144, 144))
    transform = np.zeros((144, 9), dtype=complex)
    for cell in np.ndindex(shape):
        for site in range(basis):
            index = np.ravel_multi_index(cell, shape) * basis + site
            transform[3*index:3*index+3, 3*site:3*site+3] = np.exp(-2j*np.pi*np.dot(q, cell)) * np.eye(3) / 4
        for term in model["terms"]:
            left, right = term["cluster"]
            source = np.ravel_multi_index(cell, shape) * basis + left["site"]
            target_cell = tuple((np.array(cell) + right["translation"]) % shape)
            target = np.ravel_multi_index(target_cell, shape) * basis + right["site"]
            matrix = np.array(term["coefficient"])
            hessian[3*source:3*source+3, 3*target:3*target+3] += matrix
            hessian[3*target:3*target+3, 3*source:3*source+3] += matrix.T
    expected = np.linalg.eigvalsh(transform.conjugate().T @ hessian @ transform)
    result = run_three_dimensional_workflow(model, {"task": "fourier_exchange_spectrum", "reduced_momenta": [q.tolist()]})
    assert result["status"] == "ok"
    np.testing.assert_allclose(result["calculation"]["value"][0], expected, atol=1e-12)


def test_opt_in_repair_reports_changed_hamiltonian_and_warnings():
    from three_dimensional.workflow import run_three_dimensional_workflow
    model = cubic_model()
    model["terms"][0]["coefficient"] = (2 * np.eye(3)).tolist()
    result = run_three_dimensional_workflow(model, {
        "task": "fourier_exchange_spectrum", "reduced_momenta": [[0, 0, 0]],
        "symmetry_repair": True,
    })
    assert result["status"] == "ok"
    assert result["warnings"]
    assert result["symmetry_repair_report"]["status"] == "repaired"


def test_normalized_lattice_term_contract_runs_without_paper_data():
    # Exercise the upstream model contract, not only hand-built canonical terms.
    from three_dimensional.workflow import run_three_dimensional_workflow
    canonical = cubic_model(-1)
    model = {key: value for key, value in canonical.items() if key not in {"terms", "schema_version"}}
    model["schema_version"] = "lattice-term-contract/v1"
    model["term_attachments"] = {
        "site_terms": [], "higher_body_terms": [],
        "bond_terms": [
            {"term_ref": term["term_ref"], "cluster": term["cluster"],
             "operator_basis_ref": "operator-basis:spin",
             "payload": {"kind": "bilinear_exchange_matrix", "matrix": term["coefficient"]}}
            for term in canonical["terms"]],
    }
    result = run_three_dimensional_workflow(model, {
        "task": "fourier_exchange_spectrum", "reduced_momenta": [[0, 0, 0]]})
    assert result["status"] == "ok"
    np.testing.assert_allclose(result["calculation"]["value"], [[-6, -6, -6]])


def test_cli_calculates_an_example_through_classical_reference_to_gswt():
    import json
    import subprocess
    # A runnable user-facing command, including its automatic reference search.
    example = subprocess.run([sys.executable, "-B", str(SCRIPTS / "three_dimensional/examples.py"),
                              "cubic-af", "--task", "spin_wave_spectrum"],
                             capture_output=True, text=True, check=True)
    run = subprocess.run([sys.executable, "-B", str(SCRIPTS / "three_dimensional/workflow.py")],
                         input=example.stdout, capture_output=True, text=True, check=True)
    result = json.loads(run.stdout)
    assert result["status"] == "ok"
    assert result["calculation"]["classical_optimization"]["status"] == "ok"
    assert result["calculation"]["classical_optimization"]["energy_per_cell"] == pytest.approx(-0.75, abs=1e-8)
    assert result["calculation"]["zero_point"]["energy_per_primitive_cell"] < -0.09


def test_local_frame_exchange_is_converted_before_global_reference_spin_waves():
    # Eigenvalues alone cannot catch this: frame rotations leave the Fourier
    # eigenvalues invariant but change which real spin configuration is stationary.
    from copy import deepcopy
    from three_dimensional.workflow import run_three_dimensional_workflow
    global_model = triclinic_dm_model()
    for term in global_model["terms"]:
        term["coefficient"] = (-np.eye(3)).tolist()
    local_model = deepcopy(global_model)
    frames = [np.eye(3), np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]]), np.eye(3)]
    local_model["lattice_structure"]["local_frames"] = [
        {"site_ref": "site:%d" % i, "rotation_matrix": frame.tolist()} for i, frame in enumerate(frames)]
    for term in local_model["terms"]:
        source, target = (site["site"] for site in term["cluster"])
        term["coefficient"] = (frames[source].T @ np.array(term["coefficient"]) @ frames[target]).tolist()
        term["coordinate_convention"] = "local_frames"
    request = {"task": "spin_wave_spectrum", "supercell_shape": [1, 1, 1], "spin": .5,
               "reference_spins": [[0, 0, .5]] * 3, "reduced_momenta": [[.25, .125, .25]]}
    global_result = run_three_dimensional_workflow(global_model, request)
    local_result = run_three_dimensional_workflow(local_model, request)
    assert global_result["status"] == local_result["status"] == "ok"
    np.testing.assert_allclose(local_result["calculation"]["dispersion"][0]["bands"],
                               global_result["calculation"]["dispersion"][0]["bands"], atol=1e-10)


def test_retained_biquadratic_terms_are_reported_without_running_a_truncated_solver():
    # One product-level capability check: all retained terms must be accounted
    # for, even when most of the Hamiltonian matches the spin-bond solver.
    from copy import deepcopy
    from three_dimensional.workflow import run_three_dimensional_workflow
    model = cubic_model()
    additional = deepcopy(model["terms"])
    for term in additional:
        term.update({"term_ref": term["term_ref"] + ":K", "operator_family": "biquadratic_exchange", "coefficient": 0.2})
    model["terms"].extend(additional)
    result = run_three_dimensional_workflow(model, {
        "task": "classical_ground_state", "supercell_shape": [2, 2, 2], "spin_length": .5})
    assert result["status"] == "unsupported"
    assert "biquadratic_exchange" in result["blocker"]
    assert "energy_per_cell" not in result.get("calculation", {})


def test_zero_displacement_self_bond_is_not_misread_as_an_exchange_lt_bound():
    # S^T A S is an onsite quadratic term: the Hessian is A+A^T, not A.
    # This route does not support onsite terms and must not return a false bound.
    from three_dimensional.workflow import run_three_dimensional_workflow
    model = cubic_model()
    model["terms"] = [bond(0, 0, [0, 0, 0], -np.eye(3), "term:onsite")]
    result = run_three_dimensional_workflow(model, {
        "task": "fourier_exchange_spectrum", "reduced_momenta": [[0, 0, 0]]})
    assert result["status"] == "unsupported"
    assert "onsite" in result["blocker"]
