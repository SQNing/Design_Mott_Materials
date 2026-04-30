import sys
import importlib.util
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_ROOT))

import classical.sun_gswt_classical_solver as classical_solver
from classical.sun_gswt_classical_solver import (
    build_cpn_magnetic_supercell_refinement_candidate,
    choose_refined_classical_branch,
    run_cpn_magnetic_supercell_refinement,
)
from classical.sun_gswt_classical_solver import evaluate_sun_gswt_classical_energy
from common.cpn_magnetic_supercell import (
    lift_cpn_state_between_cells,
    reshape_cpn_model_to_magnetic_supercell,
)
from lswt.build_python_glswt_payload import build_python_glswt_payload
from lswt.build_sun_gswt_payload import build_sun_gswt_payload


def _serialized_real_matrix(rows):
    return [
        [{"real": float(value), "imag": 0.0} for value in row]
        for row in rows
    ]


def _serialized_real_tensor(local_dimension, entries):
    tensor = []
    for left_bra in range(local_dimension):
        left_block = []
        for left_ket in range(local_dimension):
            right_block = []
            for right_bra in range(local_dimension):
                ket_block = []
                for right_ket in range(local_dimension):
                    value = float(entries.get((left_bra, left_ket, right_bra, right_ket), 0.0))
                    ket_block.append({"real": value, "imag": 0.0})
                right_block.append(ket_block)
            left_block.append(right_block)
        tensor.append(left_block)
    return tensor


def _toy_two_site_cpn_model():
    local_dimension = 2
    zz_tensor = _serialized_real_tensor(
        local_dimension,
        {
            (0, 0, 0, 0): -1.0,
            (1, 1, 1, 1): -1.0,
        },
    )
    return {
        "model_version": 2,
        "model_type": "sun_gswt_classical",
        "classical_manifold": "CP^(N-1)",
        "basis_semantics": {"local_space": "pseudospin_orbital"},
        "basis_order": "retained_state_index",
        "pair_basis_order": "site_i_major_site_j_minor",
        "retained_local_space": {
            "dimension": local_dimension,
            "factorization": {"kind": "generic_multiplet", "multiplet_dimension": local_dimension},
        },
        "operator_dictionary": {
            "local_basis_kind": "generic_multiplet",
            "local_operator_basis": {"matrix_construction": "local_generator_basis"},
        },
        "pair_operator_convention": {
            "pair_basis_order": "site_i_major_site_j_minor",
            "tensor_view": {
                "kind": "K_ab_cd",
                "index_order": ["left_bra", "right_bra", "left_ket", "right_ket"],
            },
        },
        "local_dimension": local_dimension,
        "local_basis_labels": ["up", "down"],
        "orbital_count": 0,
        "positions": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
        "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "bond_tensors": [
            {
                "R": [0, 0, 0],
                "source": 0,
                "target": 1,
                "matrix_shape": [4, 4],
                "tensor_shape": [2, 2, 2, 2],
                "tensor": zz_tensor,
                "pair_matrix": _serialized_real_matrix(
                    [
                        [-1.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, -1.0],
                    ]
                ),
            }
        ],
        "onsite_terms": [],
    }


def _toy_classical_result_with_projector_q(q_vector):
    return {
        "energy": -1.0,
        "classical_state": _toy_two_site_periodic_state(),
        "projector_diagnostics": {
            "dominant_ordering_q": [float(value) for value in q_vector],
            "top_components": [
                {"q": [float(value) for value in q_vector], "weight": 0.14},
                {"q": [0.0, 0.0, 0.0], "weight": 0.49},
            ],
        },
    }


def _serialized_vector(values):
    return [{"real": float(value), "imag": 0.0} for value in values]


def _toy_two_site_periodic_state():
    return {
        "schema_version": 1,
        "state_kind": "local_rays",
        "manifold": "CP^(N-1)",
        "basis_order": "retained_state_index",
        "pair_basis_order": "site_i_major_site_j_minor",
        "supercell_shape": [1, 1, 1],
        "local_rays": [
            {"cell": [0, 0, 0], "site": 0, "vector": _serialized_vector([1.0, 0.0])},
            {"cell": [0, 0, 0], "site": 1, "vector": _serialized_vector([0.0, 1.0])},
        ],
    }


def _accepted_refined_branch_fixture():
    model = _toy_two_site_cpn_model()
    classical_state = _toy_two_site_periodic_state()
    reshaped_model = reshape_cpn_model_to_magnetic_supercell(
        model,
        [[2, 0, 0], [0, 1, 0], [0, 0, 1]],
    )
    reshaped_state = lift_cpn_state_between_cells(
        classical_state,
        reshaped_model["magnetic_supercell_mapping"],
        direction="chemical_to_magnetic",
    )
    return reshaped_model, reshaped_state


def _tiled_two_site_periodic_state(shape):
    shape = [int(value) for value in shape]
    local_rays = []
    for ix in range(shape[0]):
        for iy in range(shape[1]):
            for iz in range(shape[2]):
                local_rays.append({"cell": [ix, iy, iz], "site": 0, "vector": _serialized_vector([1.0, 0.0])})
                local_rays.append({"cell": [ix, iy, iz], "site": 1, "vector": _serialized_vector([0.0, 1.0])})
    return {
        "schema_version": 1,
        "state_kind": "local_rays",
        "manifold": "CP^(N-1)",
        "basis_order": "retained_state_index",
        "pair_basis_order": "site_i_major_site_j_minor",
        "supercell_shape": list(shape),
        "local_rays": local_rays,
    }


def _load_fei2_refinement_harness():
    script_path = (
        Path(__file__).resolve().parents[1]
        / "tmp"
        / "fei2-canonical-cpn-validation-2026-04-27"
        / "run_fei2_canonical_cpn_noreshape_compare.py"
    )
    spec = importlib.util.spec_from_file_location("fei2_cpn_refinement_harness", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_refinement_branch_proposes_candidate_from_largest_nonzero_q():
    classical_result = _toy_classical_result_with_projector_q([0.25, 0.0, 0.25])

    branch = build_cpn_magnetic_supercell_refinement_candidate(
        model=_toy_two_site_cpn_model(),
        classical_result=classical_result,
    )

    assert branch["status"] == "candidate"
    assert branch["candidate"]["selected_q"] == [0.25, 0.0, 0.25]


def test_refinement_branch_rejects_when_energy_gain_is_below_tolerance():
    decision = choose_refined_classical_branch(
        original_energy=-1.0000000,
        refined_python_energy=-1.0000000001,
        refined_sunny_energy=None,
        energy_gain_tolerance=1e-6,
    )

    assert decision["accepted"] is False


def test_refinement_branch_accepts_lower_energy_state_and_returns_selected_state():
    decision = choose_refined_classical_branch(
        original_energy=-1.0,
        refined_python_energy=-1.1,
        refined_state={"supercell_shape": [2, 1, 1], "local_rays": []},
        energy_gain_tolerance=1e-6,
    )

    assert decision["accepted"] is True
    assert decision["selected_classical_state"]["supercell_shape"] == [2, 1, 1]


def test_refinement_branch_compares_energy_per_site_not_total_energy():
    decision = choose_refined_classical_branch(
        original_energy=-2.0,
        original_site_count=1,
        refined_python_energy=-8.0,
        refined_site_count=4,
        refined_state={"supercell_shape": [1, 1, 1], "local_rays": []},
        energy_gain_tolerance=1e-6,
    )

    assert decision["accepted"] is False
    assert abs(decision["energy_before_per_site"] - (-2.0)) <= 1e-12
    assert abs(decision["energy_after_python_per_site"] - (-2.0)) <= 1e-12


def test_run_refinement_supports_nondiagonal_candidate_lifting_from_rectangular_source_supercell():
    model = _toy_two_site_cpn_model()
    classical_state = _tiled_two_site_periodic_state([4, 4, 4])
    classical_result = {
        "energy": evaluate_sun_gswt_classical_energy(model, classical_state),
        "classical_state": classical_state,
        "projector_diagnostics": {
            "dominant_ordering_q": [0.25, 0.75, 0.25],
            "top_components": [
                {"q": [0.25, 0.75, 0.25], "weight": 0.14},
                {"q": [0.0, 0.0, 0.0], "weight": 0.49},
            ],
        },
    }

    refinement = run_cpn_magnetic_supercell_refinement(
        model,
        classical_result=classical_result,
        starts=1,
        seed=0,
        max_sweeps=2,
        sweep_tolerance=1e-10,
    )

    assert refinement["status"] == "candidate"
    assert refinement["candidate"]["determinant"] == 4


def test_run_refinement_reports_site_normalized_energies_for_supercell_candidate():
    model = _toy_two_site_cpn_model()
    classical_state = _tiled_two_site_periodic_state([4, 4, 4])
    classical_result = {
        "energy": evaluate_sun_gswt_classical_energy(model, classical_state),
        "classical_state": classical_state,
        "projector_diagnostics": {
            "dominant_ordering_q": [0.25, 0.75, 0.25],
            "top_components": [
                {"q": [0.25, 0.75, 0.25], "weight": 0.14},
                {"q": [0.0, 0.0, 0.0], "weight": 0.49},
            ],
        },
    }

    refinement = run_cpn_magnetic_supercell_refinement(
        model,
        classical_result=classical_result,
        starts=1,
        seed=0,
        max_sweeps=2,
        sweep_tolerance=1e-10,
    )

    diagnostics = refinement["magnetic_supercell_refinement"]
    assert diagnostics["candidate_matrix"]
    assert diagnostics["original_site_count"] == 2
    assert diagnostics["refined_site_count"] == 8
    assert abs(diagnostics["energy_before_per_site"] - (diagnostics["energy_before"] / 2.0)) <= 1e-12
    assert abs(diagnostics["energy_after_python_per_site"] - (diagnostics["energy_after_python"] / 8.0)) <= 1e-12


def test_run_refinement_chooses_best_energy_improving_candidate_among_top_components(monkeypatch):
    model = _toy_two_site_cpn_model()
    classical_state = _tiled_two_site_periodic_state([4, 4, 4])
    classical_result = {
        "energy": evaluate_sun_gswt_classical_energy(model, classical_state),
        "classical_state": classical_state,
        "projector_diagnostics": {
            "dominant_ordering_q": [0.25, 0.75, 0.25],
            "top_components": [
                {"q": [0.25, 0.75, 0.25], "weight": 0.14},
                {"q": [0.25, 0.0, 0.25], "weight": 0.13},
                {"q": [0.0, 0.0, 0.0], "weight": 0.49},
            ],
        },
    }

    energy_by_matrix = {
        ((1, 0, -1), (3, -1, 0), (0, 0, 4)): 0.05,
        ((0, 1, 0), (1, 0, -1), (0, 0, 4)): -0.60,
    }

    def fake_solver(reshaped_model, *, supercell_shape=None, starts=8, seed=0, max_sweeps=200, sweep_tolerance=1e-10):
        del starts, seed, max_sweeps, sweep_tolerance
        matrix = tuple(
            tuple(int(value) for value in row)
            for row in reshaped_model["magnetic_supercell_mapping"]["magnetic_supercell_matrix"]
        )
        per_site_energy = energy_by_matrix[matrix]
        reshaped_site_count = len(reshaped_model["positions"])
        return {
            "energy": float(per_site_energy * reshaped_site_count),
            "supercell_shape": list(supercell_shape),
            "local_rays": [],
            "classical_state": {
                "schema_version": 1,
                "state_kind": "local_rays",
                "manifold": "CP^(N-1)",
                "basis_order": "retained_state_index",
                "pair_basis_order": "site_i_major_site_j_minor",
                "supercell_shape": list(supercell_shape),
                "local_rays": [],
            },
        }

    monkeypatch.setattr(classical_solver, "solve_sun_gswt_classical_ground_state", fake_solver)

    refinement = run_cpn_magnetic_supercell_refinement(
        model,
        classical_result=classical_result,
        starts=1,
        seed=0,
        max_sweeps=2,
        sweep_tolerance=1e-10,
    )

    diagnostics = refinement["magnetic_supercell_refinement"]
    assert diagnostics["accepted"] is True
    assert diagnostics["candidate_matrix"] == [[0, 1, 0], [1, 0, -1], [0, 0, 4]]
    assert abs(diagnostics["energy_after_python_per_site"] - (-0.60)) <= 1e-12
    assert len(diagnostics["candidates"]) == 2
    assert diagnostics["candidates"][0]["accepted"] is False
    assert diagnostics["candidates"][1]["accepted"] is True


def test_run_refinement_records_sunny_verified_acceptance_backend(monkeypatch):
    model = _toy_two_site_cpn_model()
    classical_state = _tiled_two_site_periodic_state([4, 4, 4])
    classical_result = {
        "energy": -1.0,
        "classical_state": classical_state,
        "projector_diagnostics": {
            "dominant_ordering_q": [0.25, 0.75, 0.25],
            "top_components": [
                {"q": [0.25, 0.75, 0.25], "weight": 0.14},
                {"q": [0.0, 0.0, 0.0], "weight": 0.49},
            ],
        },
    }
    seen = {"sunny_calls": 0}

    def fake_solver(reshaped_model, *, supercell_shape=None, starts=8, seed=0, max_sweeps=200, sweep_tolerance=1e-10):
        del starts, seed, max_sweeps, sweep_tolerance
        reshaped_site_count = len(reshaped_model["positions"])
        solver_state = _tiled_two_site_periodic_state(list(supercell_shape))
        return {
            "energy": float(-0.55 * reshaped_site_count),
            "supercell_shape": list(supercell_shape),
            "local_rays": list(solver_state["local_rays"]),
            "classical_state": solver_state,
        }

    def fake_sunny_verification(reshaped_model, *, lifted_state, starts, seed):
        del starts, seed
        seen["sunny_calls"] += 1
        shape = [int(value) for value in lifted_state["supercell_shape"]]
        sunny_state = _tiled_two_site_periodic_state(shape)
        reshaped_site_count = len(reshaped_model["positions"])
        return {
            "energy": float(-0.75 * reshaped_site_count),
            "supercell_shape": shape,
            "local_rays": list(sunny_state["local_rays"]),
            "classical_state": sunny_state,
        }

    monkeypatch.setattr(classical_solver, "solve_sun_gswt_classical_ground_state", fake_solver)
    monkeypatch.setattr(classical_solver, "_run_sunny_cpn_refinement_verification", fake_sunny_verification)

    refinement = run_cpn_magnetic_supercell_refinement(
        model,
        classical_result=classical_result,
        starts=1,
        seed=0,
        max_sweeps=2,
        sweep_tolerance=1e-10,
        verify_with_sunny=True,
    )

    diagnostics = refinement["magnetic_supercell_refinement"]
    assert seen["sunny_calls"] == 1
    assert diagnostics["accepted"] is True
    assert diagnostics["acceptance_backend"] == "sunny"
    assert abs(diagnostics["energy_after_python_per_site"] - (-0.55)) <= 1e-12
    assert abs(diagnostics["energy_after_sunny_per_site"] - (-0.75)) <= 1e-12
    assert refinement["decision"]["selected_backend"] == "sunny"


def test_run_refinement_deduplicates_equivalent_candidate_matrices(monkeypatch):
    model = _toy_two_site_cpn_model()
    classical_state = _tiled_two_site_periodic_state([4, 4, 4])
    classical_result = {
        "energy": evaluate_sun_gswt_classical_energy(model, classical_state),
        "classical_state": classical_state,
        "projector_diagnostics": {
            "dominant_ordering_q": [0.25, 0.0, 0.25],
            "top_components": [
                {"q": [0.25, 0.0, 0.25], "weight": 0.14},
                {"q": [0.75, 0.0, 0.75], "weight": 0.13},
                {"q": [0.0, 0.0, 0.0], "weight": 0.49},
            ],
        },
    }

    call_matrices = []

    def fake_solver(reshaped_model, *, supercell_shape=None, starts=8, seed=0, max_sweeps=200, sweep_tolerance=1e-10):
        del supercell_shape, starts, seed, max_sweeps, sweep_tolerance
        matrix = tuple(
            tuple(int(value) for value in row)
            for row in reshaped_model["magnetic_supercell_mapping"]["magnetic_supercell_matrix"]
        )
        call_matrices.append(matrix)
        reshaped_site_count = len(reshaped_model["positions"])
        return {
            "energy": float(-2.05 * reshaped_site_count),
            "supercell_shape": [1, 1, 1],
            "local_rays": [],
            "classical_state": {
                "schema_version": 1,
                "state_kind": "local_rays",
                "manifold": "CP^(N-1)",
                "basis_order": "retained_state_index",
                "pair_basis_order": "site_i_major_site_j_minor",
                "supercell_shape": [1, 1, 1],
                "local_rays": [],
            },
        }

    monkeypatch.setattr(classical_solver, "solve_sun_gswt_classical_ground_state", fake_solver)

    refinement = run_cpn_magnetic_supercell_refinement(
        model,
        classical_result=classical_result,
        starts=1,
        seed=0,
        max_sweeps=2,
        sweep_tolerance=1e-10,
    )

    diagnostics = refinement["magnetic_supercell_refinement"]
    assert len(call_matrices) == 1
    assert len(diagnostics["candidates"]) == 1
    assert diagnostics["candidates"][0]["candidate_matrix"] == [[0, 1, 0], [1, 0, -1], [0, 0, 4]]


def test_run_refinement_reports_configured_max_denominator_in_diagnostics(monkeypatch):
    model = _toy_two_site_cpn_model()
    classical_state = _tiled_two_site_periodic_state([4, 4, 4])
    classical_result = {
        "energy": evaluate_sun_gswt_classical_energy(model, classical_state),
        "classical_state": classical_state,
        "projector_diagnostics": {
            "dominant_ordering_q": [0.25, 0.0, 0.25],
            "top_components": [
                {"q": [0.25, 0.0, 0.25], "weight": 0.14},
                {"q": [0.0, 0.0, 0.0], "weight": 0.49},
            ],
        },
    }

    def fake_solver(reshaped_model, *, supercell_shape=None, starts=8, seed=0, max_sweeps=200, sweep_tolerance=1e-10):
        del reshaped_model, supercell_shape, starts, seed, max_sweeps, sweep_tolerance
        return {
            "energy": -8.4,
            "supercell_shape": [1, 1, 1],
            "local_rays": [],
            "classical_state": {
                "schema_version": 1,
                "state_kind": "local_rays",
                "manifold": "CP^(N-1)",
                "basis_order": "retained_state_index",
                "pair_basis_order": "site_i_major_site_j_minor",
                "supercell_shape": [1, 1, 1],
                "local_rays": [],
            },
        }

    monkeypatch.setattr(classical_solver, "solve_sun_gswt_classical_ground_state", fake_solver)

    refinement = run_cpn_magnetic_supercell_refinement(
        model,
        classical_result=classical_result,
        starts=1,
        seed=0,
        max_sweeps=2,
        sweep_tolerance=1e-10,
        max_candidate_components=1,
        max_denominator=23,
    )

    diagnostics = refinement["magnetic_supercell_refinement"]
    assert diagnostics["max_denominator"] == 23


def test_refined_reshaped_state_builds_python_glswt_payload():
    model, classical_state = _accepted_refined_branch_fixture()

    payload = build_python_glswt_payload(model, classical_state=classical_state)

    assert payload["initial_local_rays"]
    assert payload["supercell_shape"] == classical_state["supercell_shape"]


def test_refined_reshaped_state_builds_sunny_glswt_payload():
    model, classical_state = _accepted_refined_branch_fixture()

    payload = build_sun_gswt_payload(model, classical_state=classical_state)

    assert payload["initial_local_rays"]
    assert payload["supercell_shape"] == classical_state["supercell_shape"]


def test_fei2_refinement_harness_reports_refinement_diagnostics():
    harness = _load_fei2_refinement_harness()

    report = harness.build_magnetic_supercell_refinement_report(
        model=_toy_two_site_cpn_model(),
        classical_result=_toy_classical_result_with_projector_q([0.25, 0.0, 0.25]),
        starts=1,
        seed=0,
    )

    assert "magnetic_supercell_refinement" in report
    assert report["magnetic_supercell_refinement"]["candidate_matrix"]


def test_fei2_refinement_harness_forwards_configured_candidate_budget(monkeypatch):
    harness = _load_fei2_refinement_harness()
    seen = {}

    def fake_refinement(model, *, classical_result, starts, seed, max_sweeps, sweep_tolerance, max_candidate_components):
        del model, classical_result, starts, seed, max_sweeps, sweep_tolerance
        seen["max_candidate_components"] = int(max_candidate_components)
        return {
            "magnetic_supercell_refinement": {"candidate_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
            "candidate": {"status": "ok"},
            "decision": {"accepted": False},
        }

    monkeypatch.setattr(harness, "run_cpn_magnetic_supercell_refinement", fake_refinement)

    harness.build_magnetic_supercell_refinement_report(
        model=_toy_two_site_cpn_model(),
        classical_result=_toy_classical_result_with_projector_q([0.25, 0.0, 0.25]),
        starts=1,
        seed=0,
        max_candidate_components=7,
    )

    assert seen["max_candidate_components"] == 7


def test_fei2_validation_report_keeps_refinement_diagnostics_when_sunny_times_out():
    harness = _load_fei2_refinement_harness()

    report = harness.build_validation_report(
        model=_toy_two_site_cpn_model(),
        official_reference={"chemical_energy_per_site": -1.0},
        python_result=_toy_classical_result_with_projector_q([0.25, 0.0, 0.25]),
        sunny_result={
            "status": "error",
            "error": {"code": "backend-timeout", "message": "timed out"},
        },
        starts=1,
        seed=0,
        supercell_shape=[4, 4, 4],
        max_candidate_components=5,
        started_at=0.0,
        python_started_at=0.0,
        python_finished_at=1.0,
        sunny_started_at=1.0,
        sunny_finished_at=2.0,
    )

    assert "magnetic_supercell_refinement" in report
    assert report["magnetic_supercell_refinement"]["candidate_matrix"]
    assert report["sunny_solver"]["backend_result"]["error"]["code"] == "backend-timeout"
    assert report["input_summary"]["supercell_shape"] == [4, 4, 4]
    assert report["input_summary"]["magnetic_supercell_max_candidate_components"] == 5
