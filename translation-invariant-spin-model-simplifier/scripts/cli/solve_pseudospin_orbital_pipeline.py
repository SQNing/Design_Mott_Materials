#!/usr/bin/env python3
import argparse
from copy import deepcopy
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from classical.build_pseudospin_orbital_classical_model import build_pseudospin_orbital_classical_model
from classical.build_sun_gswt_classical_payload import build_sun_gswt_classical_payload
from classical.cpn_generalized_lt_solver import solve_cpn_generalized_lt_ground_state
from classical.cpn_local_ray_solver import solve_cpn_local_ray_ground_state
from classical.pseudospin_orbital_solver import solve_pseudospin_orbital_variational
from classical.sun_gswt_classical_solver import (
    diagnose_sun_gswt_classical_state,
    solve_sun_gswt_classical_ground_state,
    solve_sun_gswt_single_q_ground_state,
)
from classical.sunny_sun_classical_driver import run_sunny_sun_classical
from classical.sunny_sun_thermodynamics_driver import run_sunny_sun_thermodynamics
from cli.build_pseudospin_orbital_payload import build_pseudospin_orbital_payload
from cli.write_results_bundle import write_results_bundle
from common.classical_state_result import (
    build_diagnostic_classical_result,
    build_final_classical_state_result,
)
from common.cpn_classical_state import resolve_cpn_classical_state_payload, resolve_cpn_local_state
from common.lattice_geometry import lattice_vector_rank, vector_rank
from lswt.build_python_glswt_payload import build_python_glswt_payload
from lswt.build_sun_gswt_payload import build_sun_gswt_payload
from lswt.single_q_z_harmonic_convergence_driver import run_single_q_z_harmonic_convergence_driver
from lswt.python_glswt_driver import run_python_glswt_driver
from lswt.sun_gswt_driver import run_sun_gswt
from output.render_pseudospin_orbital_report import write_pseudospin_orbital_reports
from simplify.group_pseudospin_orbital_terms import group_pseudospin_orbital_terms
from simplify.score_fidelity import score_fidelity
from simplify.simplify_pseudospin_orbital_payload import simplify_pseudospin_orbital_payload

THERMODYNAMICS_PROFILES = {
    "smoke": {
        "backend_method": "sunny-local-sampler",
        "sweeps": 10,
        "burn_in": 5,
        "measurement_interval": 1,
        "proposal": "delta",
        "proposal_scale": 0.1,
        "pt_exchange_interval": 1,
        "wl_windows": 1,
        "wl_overlap": 0.25,
        "wl_ln_f": 1.0,
        "wl_sweeps": 20,
    },
    "balanced": {
        "backend_method": "sunny-local-sampler",
        "sweeps": 100,
        "burn_in": 50,
        "measurement_interval": 1,
        "proposal": "delta",
        "proposal_scale": 0.2,
        "pt_exchange_interval": 1,
        "wl_windows": 1,
        "wl_overlap": 0.25,
        "wl_ln_f": 1.0,
        "wl_sweeps": 100,
    },
}


def _progress(message):
    print(f"[pseudospin-cli] {message}", file=sys.stderr, flush=True)


def _write_json_atomically(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".tmp",
        encoding="utf-8",
        dir=str(path.parent),
        delete=False,
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _build_cpn_local_ray_progress_callback(checkpoint_path):
    checkpoint_path = Path(checkpoint_path)

    def _callback(event):
        _write_json_atomically(checkpoint_path, event)
        result = event.get("result", {}) if isinstance(event, dict) else {}
        convergence = result.get("convergence", {}) if isinstance(result, dict) else {}
        history = convergence.get("history", []) if isinstance(convergence, dict) else []
        latest = history[-1] if history else {}
        shape = result.get("supercell_shape")
        energy = result.get("energy")
        stable_count = event.get("stable_count")
        repeats_required = event.get("repeats_required")
        _progress(
            "CPN local-ray progress: "
            f"status={event.get('status')} "
            f"supercell={shape} "
            f"energy={float(energy):.12g} "
            f"stable_count={stable_count}/{repeats_required} "
            f"best_start_source={latest.get('best_start_source')}"
        )

    return _callback


def _run_sunny_classical_backend(payload, *, stream_progress):
    try:
        return run_sunny_sun_classical(payload, stream_progress=stream_progress)
    except TypeError as exc:
        if "unexpected keyword argument 'stream_progress'" not in str(exc):
            raise
        return run_sunny_sun_classical(payload)


def _run_sunny_thermodynamics_backend(payload, *, stream_progress):
    try:
        return run_sunny_sun_thermodynamics(payload, stream_progress=stream_progress)
    except TypeError as exc:
        if "unexpected keyword argument 'stream_progress'" not in str(exc):
            raise
        return run_sunny_sun_thermodynamics(payload)


def _structural_dimension_from_sunny_model(model):
    explicit_dimension = model.get("dimension", model.get("spatial_dimension"))
    if isinstance(explicit_dimension, int) and explicit_dimension > 0:
        return max(1, min(3, int(explicit_dimension)))
    rank = lattice_vector_rank(
        {
            "lattice_vectors": list(model.get("lattice_vectors", [])),
            "positions": list(model.get("positions", [])),
        }
    )
    return max(1, min(3, int(rank or 1)))


def _structural_supercell_shape(structural_dimension, linear_size):
    linear_size = max(1, int(linear_size))
    if int(structural_dimension) <= 1:
        return (linear_size, 1, 1)
    if int(structural_dimension) == 2:
        return (linear_size, linear_size, 1)
    return (linear_size, linear_size, linear_size)


def _structural_supercell_schedule(structural_dimension, max_linear_size, *, start_linear_size=1):
    start_linear_size = max(1, int(start_linear_size))
    if max_linear_size is None or int(max_linear_size) <= 0:
        linear_size = start_linear_size
        while True:
            yield _structural_supercell_shape(structural_dimension, linear_size)
            linear_size += 1
        return

    max_linear_size = max(start_linear_size, int(max_linear_size))
    for linear_size in range(start_linear_size, max_linear_size + 1):
        yield _structural_supercell_shape(structural_dimension, linear_size)


def _starting_linear_size(supercell_shape, structural_dimension):
    shape = [max(1, int(value)) for value in (supercell_shape or (1, 1, 1))]
    active_axes = 1 if int(structural_dimension) <= 1 else 2 if int(structural_dimension) == 2 else 3
    return max(shape[:active_axes])


def _resolve_cpn_seed_state(seed_payload, *, default_supercell_shape):
    resolved = resolve_cpn_local_state(seed_payload, default_supercell_shape=default_supercell_shape)
    if resolved is None:
        return None
    return {
        "shape": [int(value) for value in resolved["shape"]],
        "local_rays": list(resolved["local_rays"]),
    }


def _extract_cpn_glt_preconditioner(glt_result, *, default_supercell_shape):
    if not isinstance(glt_result, dict):
        return None, {
            "method": None,
            "used": False,
            "source": None,
            "q_vector": None,
            "projector_exact_solution": None,
        }

    projector_exactness = glt_result.get("projector_exactness", {})
    seed_candidate = glt_result.get("seed_candidate", {})
    reconstruction = glt_result.get("reconstruction", {})
    candidates = [
        ("seed_candidate", seed_candidate.get("classical_state") if isinstance(seed_candidate, dict) else None),
        ("reconstruction", reconstruction.get("classical_state") if isinstance(reconstruction, dict) else None),
    ]

    for source, candidate_state in candidates:
        state = _resolve_cpn_seed_state(candidate_state, default_supercell_shape=default_supercell_shape)
        if state is None:
            continue
        return state, {
            "method": glt_result.get("method"),
            "solver_role": glt_result.get("solver_role"),
            "diagnostic_scope": glt_result.get("diagnostic_scope"),
            "used": True,
            "source": str(source),
            "seed_kind": seed_candidate.get("kind") if isinstance(seed_candidate, dict) else None,
            "q_vector": list(glt_result.get("q_vector", [])) if isinstance(glt_result.get("q_vector"), list) else None,
            "projector_exact_solution": projector_exactness.get("is_exact_projector_solution"),
            "supercell_shape": [int(value) for value in state["shape"]],
        }

    return None, {
        "method": glt_result.get("method"),
        "solver_role": glt_result.get("solver_role"),
        "diagnostic_scope": glt_result.get("diagnostic_scope"),
        "used": False,
        "source": None,
        "seed_kind": seed_candidate.get("kind") if isinstance(seed_candidate, dict) else None,
        "q_vector": list(glt_result.get("q_vector", [])) if isinstance(glt_result.get("q_vector"), list) else None,
        "projector_exact_solution": projector_exactness.get("is_exact_projector_solution"),
        "supercell_shape": None,
    }


def _tile_cpn_local_rays(previous_state, new_shape):
    previous_shape = tuple(int(value) for value in previous_state["shape"])
    new_shape = tuple(int(value) for value in new_shape)
    ray_by_cell = {
        tuple(int(value) for value in item["cell"]): item["vector"]
        for item in previous_state.get("local_rays", [])
    }
    tiled = []
    for ix in range(new_shape[0]):
        for iy in range(new_shape[1]):
            for iz in range(new_shape[2]):
                source = (
                    ix % previous_shape[0],
                    iy % previous_shape[1],
                    iz % previous_shape[2],
                )
                tiled.append(
                    {
                        "cell": [ix, iy, iz],
                        "vector": deepcopy(ray_by_cell[source]),
                    }
                )
    return tiled


def _projector_ordering_matches(previous_diagnostics, current_diagnostics, tolerance=1e-6):
    previous_projector = (
        previous_diagnostics.get("projector_diagnostics", {})
        if isinstance(previous_diagnostics, dict)
        else {}
    )
    current_projector = (
        current_diagnostics.get("projector_diagnostics", {})
        if isinstance(current_diagnostics, dict)
        else {}
    )
    previous_kind = previous_projector.get("ordering_kind")
    current_kind = current_projector.get("ordering_kind")
    if previous_kind != current_kind:
        return False
    if previous_kind == "uniform":
        return True
    previous_q = previous_projector.get("dominant_ordering_q")
    current_q = current_projector.get("dominant_ordering_q")
    if previous_q is None or current_q is None:
        return previous_q == current_q
    if len(previous_q) != len(current_q):
        return False
    return all(abs(float(left) - float(right)) <= float(tolerance) for left, right in zip(previous_q, current_q))


def _stationarity_for_convergence(backend_result, diagnostics, tolerance):
    backend_stationarity = (
        backend_result.get("backend_stationarity", {})
        if isinstance(backend_result, dict) and isinstance(backend_result.get("backend_stationarity"), dict)
        else {}
    )
    python_stationarity = (
        diagnostics.get("stationarity", {})
        if isinstance(diagnostics, dict) and isinstance(diagnostics.get("stationarity"), dict)
        else {}
    )

    source = "python-diagnostics"
    selected = python_stationarity
    if backend_stationarity.get("max_residual_norm") is not None:
        source = "backend"
        selected = backend_stationarity

    selected_max = float(selected.get("max_residual_norm", float("inf")))
    backend_max = (
        float(backend_stationarity.get("max_residual_norm"))
        if backend_stationarity.get("max_residual_norm") is not None
        else None
    )
    python_max = (
        float(python_stationarity.get("max_residual_norm"))
        if python_stationarity.get("max_residual_norm") is not None
        else None
    )
    return {
        "source": source,
        "max_residual_norm": selected_max,
        "converged": bool(selected_max <= float(tolerance)),
        "backend_max_residual_norm": backend_max,
        "python_max_residual_norm": python_max,
    }


def _run_sunny_cpn_minimize_until_converged(
    classical_model,
    *,
    supercell_shape,
    initial_state=None,
    preconditioner=None,
    starts,
    seed,
    max_linear_size,
    convergence_repeats,
    energy_tolerance=1.0e-6,
    stationarity_tolerance=1.0e-6,
):
    structural_dimension = _structural_dimension_from_sunny_model(classical_model)
    start_linear_size = _starting_linear_size(supercell_shape, structural_dimension)
    if isinstance(initial_state, dict) and initial_state.get("shape"):
        start_linear_size = max(
            int(start_linear_size),
            int(_starting_linear_size(initial_state.get("shape"), structural_dimension)),
        )
    bounded_search = max_linear_size is not None and int(max_linear_size) > 0
    schedule = _structural_supercell_schedule(
        structural_dimension,
        max_linear_size=max_linear_size,
        start_linear_size=start_linear_size,
    )

    final_result = None
    previous_energy = None
    previous_state = (
        {
            "shape": [int(value) for value in initial_state.get("shape", [])],
            "local_rays": list(initial_state.get("local_rays", [])),
        }
        if isinstance(initial_state, dict) and initial_state.get("shape") and initial_state.get("local_rays")
        else None
    )
    previous_diagnostics = None
    stable_size_count = 0
    history = []
    repeats_required = max(1, int(convergence_repeats))

    for shape in schedule:
        _progress(
            f"Sunny pseudospin-orbital SUN classical convergence: evaluating supercell={list(shape)} starts={int(starts)} seed={int(seed)}"
        )
        backend_payload = {
            "backend": "Sunny.jl",
            "payload_kind": "sunny_sun_classical",
            "model": classical_model,
            "supercell_shape": [int(value) for value in shape],
            "starts": int(starts),
            "seed": int(seed),
        }
        if previous_state is not None:
            backend_payload["initial_local_rays"] = _tile_cpn_local_rays(previous_state, shape)

        backend_result = _run_sunny_classical_backend(backend_payload, stream_progress=True)
        if backend_result.get("status") != "ok":
            return backend_result

        current_energy = float(backend_result["energy"])
        current_state = resolve_cpn_local_state(backend_result, default_supercell_shape=shape)
        current_diagnostics = (
            diagnose_sun_gswt_classical_state(classical_model, current_state)
            if current_state is not None
            else {}
        )
        current_projector = current_diagnostics.get("projector_diagnostics", {}) if isinstance(current_diagnostics, dict) else {}
        current_stationarity = _stationarity_for_convergence(
            backend_result,
            current_diagnostics,
            stationarity_tolerance,
        )
        stationarity_max = float(current_stationarity["max_residual_norm"])
        stationarity_converged = bool(current_stationarity["converged"])
        energy_delta = None
        energy_matches_previous = False
        ordering_matches_previous = False
        if previous_energy is None:
            stable_size_count = 1
        else:
            energy_delta = current_energy - previous_energy
            energy_matches_previous = abs(float(energy_delta)) <= float(energy_tolerance)
            ordering_matches_previous = _projector_ordering_matches(previous_diagnostics, current_diagnostics)
            stable_size_count = (
                stable_size_count + 1
                if energy_matches_previous and ordering_matches_previous and stationarity_converged
                else 1
            )

        history.append(
            {
                "shape": [int(value) for value in shape],
                "energy": current_energy,
                "energy_delta_vs_previous": None if energy_delta is None else float(energy_delta),
                "energy_matches_previous": bool(energy_matches_previous),
                "ordering_kind": current_projector.get("ordering_kind"),
                "dominant_ordering_q": current_projector.get("dominant_ordering_q"),
                "ordering_matches_previous": bool(ordering_matches_previous),
                "stationarity_source": current_stationarity["source"],
                "stationarity_max_residual_norm": stationarity_max,
                "stationarity_converged": bool(stationarity_converged),
                "backend_stationarity_max_residual_norm": current_stationarity["backend_max_residual_norm"],
                "python_stationarity_max_residual_norm": current_stationarity["python_max_residual_norm"],
                "starts": int(starts),
                "seed": int(seed),
                "used_tiled_initial_guess": previous_state is not None,
                "preconditioner_source": preconditioner.get("source") if isinstance(preconditioner, dict) else None,
            }
        )
        _progress(
            "Sunny pseudospin-orbital SUN classical convergence result: "
            f"supercell={list(shape)} energy={current_energy:.12g} "
            f"stationarity={stationarity_max:.6g} stable_count={stable_size_count}/{repeats_required}"
        )

        previous_energy = current_energy
        previous_state = current_state
        previous_diagnostics = current_diagnostics
        final_result = {
            **backend_result,
            "supercell_shape": [int(value) for value in shape],
        }
        if stable_size_count >= repeats_required:
            break

    if final_result is None:
        return {
            "status": "error",
            "backend": {"name": "Sunny.jl", "mode": "SUN"},
            "payload_kind": "sunny_sun_classical",
            "error": {
                "code": "empty-supercell-schedule",
                "message": "Sunny pseudospin-orbital CP^(N-1) minimization produced no schedule entries",
            },
        }

    converged = bool(stable_size_count >= repeats_required)
    return {
        **final_result,
        "preconditioner": dict(preconditioner or {}),
        "convergence": {
            "energy_converged": converged,
            "history": history,
            "energy_tolerance": float(energy_tolerance),
            "stationarity_converged": bool(history[-1]["stationarity_converged"]) if history else False,
            "stationarity_source": history[-1]["stationarity_source"] if history else None,
            "stationarity_tolerance": float(stationarity_tolerance),
            "repeats_required": int(repeats_required),
            "structural_dimension": int(structural_dimension),
            "search_mode": "bounded" if bounded_search else "until-converged",
            "max_linear_size": int(max_linear_size) if bounded_search else None,
            "stopped_reason": "converged" if converged else "max_linear_size_reached",
        },
    }


def _solver_phase_summary(
    parsed_payload,
    simplified_payload,
    grouped_payload,
    classical_model,
    solver_result,
    report_manifest,
    classical_method,
    *,
    thermodynamics_backend=None,
    thermodynamics_result=None,
    dos_result=None,
):
    convergence = solver_result.get("convergence", {})
    relaxed_lt = solver_result.get("relaxed_lt", {})
    projector = solver_result.get("projector_diagnostics", {})
    stationarity = solver_result.get("stationarity", {})
    backend_stationarity = solver_result.get("backend_stationarity", {})
    ansatz_stationarity = solver_result.get("ansatz_stationarity", {})
    backend = solver_result.get("backend", {}) if isinstance(solver_result.get("backend"), dict) else {}
    gswt = solver_result.get("gswt", {})
    gswt_ordering = gswt.get("ordering", {}) if isinstance(gswt, dict) else {}
    gswt_compatibility = gswt_ordering.get("compatibility_with_supercell", {}) if isinstance(gswt_ordering, dict) else {}
    preconditioner = solver_result.get("preconditioner", {}) if isinstance(solver_result.get("preconditioner"), dict) else {}
    grid_shape = projector.get("grid_shape")
    thermodynamics_result = thermodynamics_result or {}
    thermodynamics_grid = thermodynamics_result.get("grid", []) if isinstance(thermodynamics_result, dict) else []
    thermodynamics_backend_info = (
        thermodynamics_result.get("backend", {})
        if isinstance(thermodynamics_result.get("backend"), dict)
        else {}
    )
    thermodynamics_configuration = (
        thermodynamics_result.get("configuration", {})
        if isinstance(thermodynamics_result.get("configuration"), dict)
        else {}
    )
    inferred = parsed_payload.get("inferred", {})
    lines = [
        "# Pseudospin-Orbital Solver Phase",
        "",
        "## Conventions",
        "",
        "- local space: pseudospin_orbital",
        f"- basis order: {parsed_payload.get('basis_order')}",
        f"- local_dimension: {inferred['local_dimension']}",
        f"- classical_method: {classical_method}",
        "- coefficient convention in classical solver: require projected coefficients to be real within tolerance",
        "",
        "## Process",
        "",
        "- parsed POSCAR into lattice metadata",
        "- parsed wannier-style VR_hr.dat into R-resolved bond blocks",
        "- projected bond matrices into pseudospin-orbital operator basis",
        "- generated both human-friendly and full-coefficient reports",
        "- built a classical solver payload",
        "- executed the requested classical-ground-state solver branch",
        "",
        "## Current counts",
        "",
        f"- bond blocks: {len(parsed_payload['bond_blocks'])}",
        f"- grouped bonds: {len(grouped_payload['bonds'])}",
        f"- simplification candidates: {len(simplified_payload['simplification']['candidates'])}",
        f"- classical payload bond count: {classical_model.get('bond_count', classical_model.get('bond_count', len(classical_model.get('bond_tensors', []))))}",
        "",
        "## Solver result",
        "",
        f"- method: {solver_result['method']}",
        f"- solver_role: {solver_result.get('solver_role')}",
        f"- diagnostic_scope: {solver_result.get('diagnostic_scope')}",
        f"- recommended_followup: {solver_result.get('recommended_followup')}",
        f"- energy: {solver_result['energy']}",
        f"- starts: {solver_result['starts']}",
        f"- seed: {solver_result['seed']}",
        f"- classical_backend: {backend.get('name')}",
        f"- classical_backend_mode: {backend.get('mode')}",
        f"- classical_backend_solver: {backend.get('solver')}",
        f"- preconditioner_method: {preconditioner.get('method')}",
        f"- preconditioner_source: {preconditioner.get('source')}",
        f"- preconditioner_used: {preconditioner.get('used')}",
        f"- preconditioner_q_vector: {preconditioner.get('q_vector')}",
        f"- preconditioner_projector_exact_solution: {preconditioner.get('projector_exact_solution')}",
        f"- preconditioner_supercell_shape: {preconditioner.get('supercell_shape')}",
        f"- preconditioner_error: {preconditioner.get('error')}",
        f"- ansatz: {solver_result.get('ansatz')}",
        f"- q_vector: {solver_result.get('q_vector')}",
        f"- supercell_shape: {solver_result.get('supercell_shape')}",
        f"- gswt_payload_written: {bool(gswt)}",
        f"- gswt_status: {gswt.get('status')}",
        f"- gswt_backend: {gswt.get('backend', {}).get('name')}",
        f"- gswt_payload_kind: {gswt.get('payload_kind')}",
        f"- gswt_ordering_ansatz: {gswt_ordering.get('ansatz')}",
        f"- gswt_ordering_compatibility_kind: {gswt_compatibility.get('kind')}",
        f"- ansatz_optimizer_method: {ansatz_stationarity.get('optimizer_method')}",
        f"- ansatz_optimization_mode: {ansatz_stationarity.get('optimization_mode')}",
        f"- ansatz_optimizer_success: {ansatz_stationarity.get('optimizer_success')}",
        f"- ansatz_optimizer_optimality: {ansatz_stationarity.get('optimizer_optimality')}",
        f"- ansatz_optimizer_constraint_violation: {ansatz_stationarity.get('optimizer_constraint_violation')}",
        f"- ansatz_active_q_axes: {ansatz_stationarity.get('active_q_axes')}",
        f"- ansatz_q_parameterization: {ansatz_stationarity.get('q_parameterization')}",
        f"- ansatz_generator_normalization: {ansatz_stationarity.get('generator_normalization')}",
        f"- energy_converged: {convergence.get('energy_converged')}",
        f"- convergence_search_mode: {convergence.get('search_mode')}",
        f"- convergence_stopped_reason: {convergence.get('stopped_reason')}",
        f"- convergence_max_linear_size: {convergence.get('max_linear_size')}",
        f"- convergence_stationarity_source: {convergence.get('stationarity_source')}",
        f"- structure_factor_converged: {convergence.get('structure_factor_converged')}",
        f"- structure_factor_peak_q: {convergence.get('structure_factor', {}).get('peak_q')}",
        f"- relaxed_lt_q_seed: {relaxed_lt.get('q_seed')}",
        f"- relaxed_lt_lower_bound: {relaxed_lt.get('lower_bound')}",
        f"- projector_exact_solution: {solver_result.get('projector_exactness', {}).get('is_exact_projector_solution')}",
        f"- projector_trace_residual: {solver_result.get('projector_exactness', {}).get('trace_residual')}",
        f"- projector_hermiticity_residual: {solver_result.get('projector_exactness', {}).get('hermiticity_residual')}",
        f"- projector_negativity_residual: {solver_result.get('projector_exactness', {}).get('negativity_residual')}",
        f"- projector_purity_residual: {solver_result.get('projector_exactness', {}).get('purity_residual')}",
        f"- projector_rank_one_residual: {solver_result.get('projector_exactness', {}).get('rank_one_residual')}",
        f"- projector_ordering_kind: {projector.get('ordering_kind')}",
        f"- projector_uniform_q_weight: {projector.get('uniform_q_weight')}",
        f"- projector_dominant_ordering_q: {projector.get('dominant_ordering_q')}",
        f"- projector_dominant_ordering_weight: {projector.get('dominant_ordering_weight')}",
        f"- stationarity_max_residual_norm: {stationarity.get('max_residual_norm')}",
        f"- stationarity_mean_residual_norm: {stationarity.get('mean_residual_norm')}",
        f"- backend_stationarity_max_residual_norm: {backend_stationarity.get('max_residual_norm')}",
        f"- backend_stationarity_mean_residual_norm: {backend_stationarity.get('mean_residual_norm')}",
        "",
        "## Report artifacts",
        "",
        f"- human-friendly pdf status: {report_manifest['reports']['human_friendly']['pdf_status']}",
        f"- full-coefficients pdf status: {report_manifest['reports']['full_coefficients']['pdf_status']}",
        "",
        "## Pseudospin-Orbital Thermodynamics",
        "",
        f"- thermodynamics_backend: {thermodynamics_backend}",
        f"- thermodynamics_present: {bool(thermodynamics_grid)}",
        f"- thermodynamics_method: {thermodynamics_result.get('method')}",
        f"- thermodynamics_backend_name: {thermodynamics_backend_info.get('name')}",
        f"- thermodynamics_backend_sampler: {thermodynamics_backend_info.get('sampler')}",
        f"- thermodynamics_profile: {thermodynamics_configuration.get('profile')}",
        f"- thermodynamics_sweeps: {thermodynamics_configuration.get('sweeps')}",
        f"- thermodynamics_burn_in: {thermodynamics_configuration.get('burn_in')}",
        f"- thermodynamics_measurement_interval: {thermodynamics_configuration.get('measurement_interval')}",
        f"- thermodynamics_temperature_count: {len(thermodynamics_grid)}",
        f"- dos_present: {dos_result is not None}",
        "",
        "## GSWT Diagnostics",
        "",
        "- for `sun-gswt-cpn`, the physically relevant ordering wavevector is read from the Fourier components of the projector field `Q_R = |z_R><z_R|`, not from a gauge phase of `z_R` itself",
        "- for `sun-gswt-single-q`, the current implementation performs single-q direct joint optimization over the ordering vector and internal ansatz variables; it does not do a preliminary q-mesh sweep",
        "- for `cpn-generalized-lt`, the current branch is diagnostic-only: it now performs generalized relaxed `CP^(N-1)` GLT with weighted multisublattice kernels plus commensurate lowest-shell lifting when available, but it is still not the final constrained classical ground-state solver",
        "- exact or approximate commensurate GLT local-ray textures can be used as preconditioners for `sunny-cpn-minimize`, but choosing `cpn-generalized-lt` directly still does not auto-run GSWT or thermodynamics",
        f"- stored projector diagnostic grid: {grid_shape}",
        f"- stationarity residual definition: {stationarity.get('residual_definition')}",
        f"- backend stationarity residual definition: {backend_stationarity.get('residual_definition')}",
        "",
        "## Residual limitations",
        "",
        "- the parser remains general in orbital count, but downstream solver coverage is still method-dependent",
        "- the present solver does not yet map this pseudospin-orbital model into the existing spin-only Sunny thermodynamics or LSWT chain",
        "- the LT-style relaxed diagnostic is intentionally retained as an alternative classical route and has not been removed",
    ]
    if "orbital_count" in inferred:
        lines.insert(8, f"- orbital_count: {inferred['orbital_count']}")
    if "multiplet_dimension" in inferred:
        lines.insert(8, f"- multiplet_dimension: {inferred['multiplet_dimension']}")
    if grid_shape == [1, 1, 1]:
        insertion_index = lines.index("## Residual limitations")
        lines[insertion_index:insertion_index] = [
            "- because the stored projector grid is `[1, 1, 1]`, this run probes only the uniform magnetic-cell ansatz; the absence of nonzero `q` components here is therefore not a model-level conclusion about the true ordering vector",
            "",
        ]
    return "\n".join(lines)


def _write_solver_stage_markdown(summary, docs_dir):
    docs_dir = Path(docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)
    path = docs_dir / f"{date.today().isoformat()}-pseudospin-orbital-solver-phase.md"
    path.write_text(summary, encoding="utf-8")
    return path


def _single_q_convergence_scan_values(gswt_payload):
    phase_grid_size = int(gswt_payload.get("phase_grid_size", 32))
    z_harmonic_cutoff = int(gswt_payload.get("z_harmonic_cutoff", 1))
    sideband_cutoff = int(gswt_payload.get("sideband_cutoff", 0))
    return {
        "phase_grid_sizes": sorted({phase_grid_size, max(8, phase_grid_size // 2)}),
        "z_harmonic_cutoffs": sorted({z_harmonic_cutoff, max(0, z_harmonic_cutoff - 1)}),
        "sideband_cutoffs": sorted({sideband_cutoff, max(0, sideband_cutoff - 1)}),
    }


def _run_single_q_convergence_analysis(classical_model, solver_result, gswt_payload):
    scan_values = _single_q_convergence_scan_values(gswt_payload)
    payload = {
        **classical_model,
        "classical_state": solver_result,
        "phase_grid_sizes": scan_values["phase_grid_sizes"],
        "z_harmonic_cutoffs": scan_values["z_harmonic_cutoffs"],
        "sideband_cutoffs": scan_values["sideband_cutoffs"],
        "z_harmonic_reference_mode": str(gswt_payload.get("z_harmonic_reference_mode", "input")),
    }
    return run_single_q_z_harmonic_convergence_driver(payload)


def _format_convergence_value(value):
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return format(value, ".8g")
    return str(value)


def _single_q_convergence_summary(convergence_result):
    reference = (
        convergence_result.get("reference_parameters", {})
        if isinstance(convergence_result.get("reference_parameters"), dict)
        else {}
    )
    metrics = (
        convergence_result.get("reference_metrics", {})
        if isinstance(convergence_result.get("reference_metrics"), dict)
        else {}
    )

    def _scan_lines(entries, primary_key):
        lines = []
        for entry in entries:
            lines.append(
                "- "
                f"{primary_key}={entry.get(primary_key)} "
                f"omega_min={_format_convergence_value(entry.get('omega_min'))} "
                f"omega_min_delta_vs_reference={_format_convergence_value(entry.get('omega_min_delta_vs_reference'))} "
                f"max_band_delta_vs_reference={_format_convergence_value(entry.get('max_band_delta_vs_reference'))} "
                f"retained_linear_term_max_norm={_format_convergence_value(entry.get('retained_linear_term_max_norm'))} "
                f"full_tangent_linear_term_max_norm={_format_convergence_value(entry.get('full_tangent_linear_term_max_norm'))}"
            )
        return lines or ["- n/a"]

    lines = [
        "# Single-Q Z-Harmonic Convergence Summary",
        "",
        "## Reference",
        "",
        f"- reference phase_grid_size: {reference.get('phase_grid_size')}",
        f"- reference z_harmonic_cutoff: {reference.get('z_harmonic_cutoff')}",
        f"- reference sideband_cutoff: {reference.get('sideband_cutoff')}",
        f"- reference z_harmonic_reference_mode: {reference.get('z_harmonic_reference_mode')}",
        f"- reference omega_min: {_format_convergence_value(metrics.get('omega_min'))}",
        f"- reference omega_min_q_vector: {metrics.get('omega_min_q_vector')}",
        "",
        "## Phase Grid Scan",
        "",
        *_scan_lines(convergence_result.get("phase_grid_scan", []), "phase_grid_size"),
        "",
        "## Z Harmonic Cutoff Scan",
        "",
        *_scan_lines(convergence_result.get("z_harmonic_cutoff_scan", []), "z_harmonic_cutoff"),
        "",
        "## Sideband Cutoff Scan",
        "",
        *_scan_lines(convergence_result.get("sideband_cutoff_scan", []), "sideband_cutoff"),
    ]
    return "\n".join(lines)


def _resolve_thermodynamics_profile(profile_name):
    if profile_name is None:
        return None
    profile = THERMODYNAMICS_PROFILES.get(str(profile_name))
    if profile is None:
        supported = ", ".join(sorted(THERMODYNAMICS_PROFILES))
        raise ValueError(f"unsupported thermodynamics profile: {profile_name!r}; supported profiles: {supported}")
    return {"name": str(profile_name), **profile}


def _profile_override(current_value, default_value, profile_value):
    if profile_value is None:
        return current_value
    if current_value == default_value:
        return profile_value
    return current_value


def _normalized_thermodynamics_backend_result(backend_output, thermodynamics_settings):
    if not isinstance(backend_output, dict):
        return None

    thermodynamics_result = backend_output.get("thermodynamics_result")
    if not isinstance(thermodynamics_result, dict):
        candidate_keys = {
            "backend",
            "configuration",
            "grid",
            "method",
            "observables",
            "reference",
            "sampling",
            "uncertainties",
        }
        if any(key in backend_output for key in ("grid", "observables", "sampling", "reference", "method")):
            thermodynamics_result = {
                key: value
                for key, value in backend_output.items()
                if key in candidate_keys
            }

    if isinstance(thermodynamics_result, dict):
        return {
            **thermodynamics_result,
            "configuration": thermodynamics_settings,
        }
    return None


def _standardized_pseudospin_method(classical_method):
    mapping = {
        "cpn-local-ray-minimize": "pseudospin-cpn-local-ray-minimize",
        "sunny-cpn-minimize": "pseudospin-sunny-cpn-minimize",
        "cpn-generalized-lt": "pseudospin-cpn-generalized-lt",
        "cpn-luttinger-tisza": "pseudospin-cpn-luttinger-tisza",
    }
    return mapping.get(str(classical_method))


def _pseudospin_result_diagnostics(solver_result):
    diagnostics = {}
    for key in (
        "projector_diagnostics",
        "stationarity",
        "convergence",
        "backend_stationarity",
        "ansatz_stationarity",
        "preconditioner",
        "glt_preconditioner",
        "glt_preconditioner_diagnostic",
        "relaxed_lt",
        "projector_exactness",
    ):
        value = solver_result.get(key)
        if isinstance(value, dict) and value:
            diagnostics[key] = value
    return diagnostics or None


def _pseudospin_result_energy(solver_result):
    for key in ("energy", "lower_bound"):
        value = solver_result.get(key)
        if value is not None:
            return float(value)
    return None


def _build_pseudospin_classical_state_result(solver_result, *, classical_method, default_supercell_shape):
    standardized_method = _standardized_pseudospin_method(classical_method)
    if standardized_method is None or not isinstance(solver_result, dict):
        return None

    diagnostics = _pseudospin_result_diagnostics(solver_result)

    if classical_method in {"cpn-local-ray-minimize", "sunny-cpn-minimize"}:
        classical_state = resolve_cpn_classical_state_payload(
            solver_result,
            default_supercell_shape=default_supercell_shape,
        )
        if not classical_state.get("local_rays"):
            return None

        result = build_final_classical_state_result(
            classical_state,
            thermodynamics_supported=True,
            diagnostics=diagnostics,
        )
        result["solver_family"] = "retained_local_multiplet"
        result["method"] = standardized_method
        result["ordering"] = classical_state.get("ordering")
        result["supercell_shape"] = [
            int(value) for value in classical_state.get("supercell_shape", default_supercell_shape)
        ]
        energy = _pseudospin_result_energy(solver_result)
        if energy is not None:
            result["energy"] = energy
        return result

    if classical_method in {"cpn-generalized-lt", "cpn-luttinger-tisza"}:
        result = build_diagnostic_classical_result(
            reason="diagnostic-seed-method",
            diagnostics=diagnostics,
        )
        result["solver_family"] = "diagnostic_seed_only"
        result["method"] = standardized_method
        for key in ("lower_bound", "seed_candidate", "recommended_followup", "ordering_hint"):
            if solver_result.get(key) is not None:
                result[key] = solver_result.get(key)
        return result

    return None


def _resolved_bundle_classical_state(solver_result, *, default_supercell_shape):
    resolved_state = resolve_cpn_classical_state_payload(
        solver_result,
        default_supercell_shape=default_supercell_shape,
    )
    if resolved_state.get("local_rays"):
        return resolved_state

    classical_state = solver_result.get("classical_state")
    if isinstance(classical_state, dict):
        return dict(classical_state)
    return None


def _bundle_lattice_payload(parsed_payload):
    structure = parsed_payload.get("structure", {})
    bond_blocks = parsed_payload.get("bond_blocks", [])
    translation_vectors = [
        block.get("R")
        for block in bond_blocks
        if isinstance(block, dict) and isinstance(block.get("R"), (list, tuple))
    ]
    structural_dimension = lattice_vector_rank(structure)
    interaction_dimension = vector_rank(translation_vectors) if translation_vectors else None
    return {
        "lattice_vectors": list(structure.get("lattice_vectors", [])),
        "positions": list(structure.get("positions", [])),
        "coordinate_mode": structure.get("coordinate_mode"),
        "species": list(structure.get("species", [])),
        "counts": list(structure.get("counts", [])),
        "dimension": int(structural_dimension) if structural_dimension > 0 else None,
        "interaction_dimension": int(interaction_dimension) if interaction_dimension and interaction_dimension > 0 else None,
    }


def _build_result_payload(
    parsed_payload,
    simplified_payload,
    solver_result,
    *,
    classical_method,
    default_supercell_shape,
    gswt_payload=None,
    single_q_convergence=None,
    thermodynamics_settings=None,
    thermodynamics_result=None,
    dos_result=None,
):
    inferred = parsed_payload.get("inferred", {})
    hamiltonian = parsed_payload.get("hamiltonian", {})
    effective_model = simplified_payload.get("effective_model", {})
    classical_state = _resolved_bundle_classical_state(
        solver_result,
        default_supercell_shape=default_supercell_shape,
    )

    payload = {
        "model_name": str(hamiltonian.get("comment") or "pseudospin-orbital-model"),
        "normalized_model": {
            "local_hilbert": {
                "dimension": int(inferred.get("local_dimension", 0)),
            }
        },
        "simplification": simplified_payload.get("simplification", {}),
        "canonical_model": simplified_payload.get("canonical_model", {}),
        "effective_model": effective_model,
        "fidelity": score_fidelity(effective_model),
        "projection": {
            "status": "many_body_hr-pseudospin_orbital",
        },
        "lattice": _bundle_lattice_payload(parsed_payload),
        "bonds": [],
        "basis_order": parsed_payload.get("basis_order"),
        "pair_basis_order": parsed_payload.get("pair_basis_order"),
        "local_basis_labels": parsed_payload.get("local_basis_labels", []),
        "retained_local_space": parsed_payload.get("retained_local_space", {}),
        "classical": {
            "requested_method": str(classical_method),
            "chosen_method": str(classical_method),
            "solver_method": solver_result.get("method"),
        },
    }
    if classical_state is not None:
        payload["classical"]["classical_state"] = classical_state
        payload["classical_state"] = classical_state
    classical_state_result = solver_result.get("classical_state_result")
    if isinstance(classical_state_result, dict):
        payload["classical"]["classical_state_result"] = classical_state_result
        payload["classical_state_result"] = classical_state_result
    if gswt_payload is not None:
        payload["gswt_payload"] = gswt_payload
    if isinstance(solver_result.get("gswt"), dict):
        payload["gswt"] = solver_result["gswt"]
    if single_q_convergence is not None:
        payload["single_q_convergence"] = single_q_convergence
    if thermodynamics_settings is not None:
        payload["thermodynamics"] = thermodynamics_settings
    if thermodynamics_result is not None:
        payload["thermodynamics_result"] = thermodynamics_result
    if dos_result is not None:
        payload["dos_result"] = dos_result
    return payload


def _build_selected_gswt_payload(
    classical_model,
    solver_result,
    *,
    gswt_backend,
    z_harmonic_reference_mode="input",
):
    if gswt_backend == "sunny":
        return build_sun_gswt_payload(classical_model, classical_state=solver_result)
    if gswt_backend == "python":
        python_model = dict(classical_model)
        python_model["z_harmonic_reference_mode"] = str(z_harmonic_reference_mode)
        return build_python_glswt_payload(python_model, classical_state=solver_result)
    raise ValueError(f"unsupported gswt_backend: {gswt_backend!r}")


def _run_selected_gswt(gswt_payload, *, gswt_backend):
    if gswt_backend == "sunny":
        return run_sun_gswt(gswt_payload)
    if gswt_backend == "python":
        return run_python_glswt_driver(gswt_payload)
    raise ValueError(f"unsupported gswt_backend: {gswt_backend!r}")


def solve_from_files(
    poscar_path,
    hr_path,
    output_dir,
    docs_dir,
    *,
    compile_pdf=True,
    coefficient_tolerance=1e-10,
    local_space_mode="auto",
    classical_method="restricted-product-state",
    supercell_shape=(1, 1, 1),
    starts=16,
    seed=0,
    max_linear_size=5,
    convergence_repeats=2,
    max_sweeps=200,
    run_gswt=True,
    gswt_backend="sunny",
    z_harmonic_reference_mode="input",
    run_thermodynamics=False,
    thermodynamics_backend=None,
    temperatures=None,
    thermo_seed=0,
    thermo_profile=None,
    thermo_sweeps=100,
    thermo_burn_in=50,
    thermo_measurement_interval=1,
    thermo_proposal="delta",
    thermo_proposal_scale=0.2,
    thermo_pt_temperatures=None,
    thermo_pt_exchange_interval=1,
    thermo_wl_bounds=None,
    thermo_wl_bin_size=None,
    thermo_wl_windows=1,
    thermo_wl_overlap=0.25,
    thermo_wl_ln_f=1.0,
    thermo_wl_sweeps=100,
):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    classical_checkpoint_path = output_dir / "classical_checkpoint.json"

    parsed_payload = build_pseudospin_orbital_payload(
        poscar_path=poscar_path,
        hr_path=hr_path,
        coefficient_tolerance=coefficient_tolerance,
        local_space_mode=local_space_mode,
    )
    _progress("Parsed POSCAR + hr.dat payload")
    simplified_payload = simplify_pseudospin_orbital_payload(parsed_payload)
    grouped_payload = group_pseudospin_orbital_terms(parsed_payload)
    shell_count = len(grouped_payload.get("distance_shells", [])) if isinstance(grouped_payload, dict) else 0
    _progress(f"Grouped bond terms into {shell_count} distance shells")
    report_manifest = write_pseudospin_orbital_reports(
        parsed_payload,
        grouped_payload,
        output_dir=output_dir,
        compile_pdf=compile_pdf,
    )
    _progress("Wrote initial human-readable reports")

    if run_thermodynamics and classical_method == "restricted-product-state":
        raise ValueError("Sunny pseudospin-orbital thermodynamics requires a CP^(N-1) classical state")
    if run_thermodynamics and classical_method in {"cpn-generalized-lt", "cpn-luttinger-tisza"}:
        raise ValueError(
            "cpn-generalized-lt is a diagnostic-only lower-bound / seed method and cannot be used directly for thermodynamics"
        )

    if classical_method == "restricted-product-state":
        variational_max_linear_size = int(max_linear_size) if int(max_linear_size) > 0 else 5
        classical_model = build_pseudospin_orbital_classical_model(parsed_payload)
        solver_result = solve_pseudospin_orbital_variational(
            classical_model,
            starts=starts,
            seed=seed,
            max_linear_size=variational_max_linear_size,
            convergence_repeats=convergence_repeats,
            max_sweeps=max_sweeps,
        )
        gswt_payload = None
    elif classical_method == "sun-gswt-cpn":
        classical_model = build_sun_gswt_classical_payload(parsed_payload)
        solver_result = solve_sun_gswt_classical_ground_state(
            classical_model,
            starts=starts,
            seed=seed,
        )
        gswt_payload = (
            _build_selected_gswt_payload(
                classical_model,
                solver_result,
                gswt_backend=gswt_backend,
                z_harmonic_reference_mode=z_harmonic_reference_mode,
            )
            if run_gswt
            else None
        )
    elif classical_method == "sun-gswt-single-q":
        classical_model = build_sun_gswt_classical_payload(parsed_payload)
        solver_result = solve_sun_gswt_single_q_ground_state(
            classical_model,
            starts=starts,
            seed=seed,
        )
        gswt_payload = (
            _build_selected_gswt_payload(
                classical_model,
                solver_result,
                gswt_backend=gswt_backend,
                z_harmonic_reference_mode=z_harmonic_reference_mode,
            )
            if run_gswt
            else None
        )
    elif classical_method == "cpn-local-ray-minimize":
        _progress("Starting CP^(N-1) local-ray constrained minimization")
        classical_model = build_sun_gswt_classical_payload(parsed_payload)
        progress_callback = _build_cpn_local_ray_progress_callback(classical_checkpoint_path)
        _progress("Running strict GLT diagnostic preconditioner for local-ray minimization")
        glt_initial_state = None
        glt_preconditioner_result = None
        glt_preconditioner = {
            "method": "cpn-generalized-lt",
            "used": False,
            "source": None,
            "q_vector": None,
            "projector_exact_solution": None,
        }
        try:
            glt_preconditioner_result = solve_cpn_generalized_lt_ground_state(
                classical_model,
                requested_method="cpn-generalized-lt",
                starts=1,
                seed=seed,
            )
            glt_initial_state, glt_preconditioner = _extract_cpn_glt_preconditioner(
                glt_preconditioner_result,
                default_supercell_shape=supercell_shape,
            )
        except Exception as exc:
            _progress(f"GLT preconditioner unavailable: {exc}")
            glt_preconditioner["error"] = {
                "code": "glt-preconditioner-failed",
                "message": str(exc),
            }
        solver_result = solve_cpn_local_ray_ground_state(
            classical_model,
            starts=starts,
            seed=seed,
            initial_state=glt_initial_state,
            max_linear_size=max_linear_size,
            convergence_repeats=convergence_repeats,
            max_sweeps=max_sweeps,
            progress_callback=progress_callback,
        )
        solver_result["glt_preconditioner"] = glt_preconditioner
        solver_result["glt_preconditioner_diagnostic"] = glt_preconditioner_result
        gswt_payload = (
            _build_selected_gswt_payload(
                classical_model,
                solver_result,
                gswt_backend=gswt_backend,
                z_harmonic_reference_mode=z_harmonic_reference_mode,
            )
            if run_gswt
            else None
        )
        _progress("Finished CP^(N-1) local-ray constrained minimization")
    elif classical_method == "sunny-cpn-minimize":
        _progress("Starting Sunny pseudospin-orbital CP^(N-1) classical minimization")
        classical_model = build_sun_gswt_classical_payload(parsed_payload)
        _progress("Running strict GLT diagnostic preconditioner for Sunny pseudospin-orbital minimization")
        glt_initial_state = None
        glt_preconditioner_result = None
        glt_preconditioner = {
            "method": "cpn-generalized-lt",
            "used": False,
            "source": None,
            "q_vector": None,
            "projector_exact_solution": None,
        }
        try:
            glt_preconditioner_result = solve_cpn_generalized_lt_ground_state(
                classical_model,
                requested_method="cpn-generalized-lt",
                starts=1,
                seed=seed,
            )
            glt_initial_state, glt_preconditioner = _extract_cpn_glt_preconditioner(
                glt_preconditioner_result,
                default_supercell_shape=supercell_shape,
            )
        except Exception as exc:
            _progress(f"GLT preconditioner unavailable: {exc}")
            glt_preconditioner["error"] = {
                "code": "glt-preconditioner-failed",
                "message": str(exc),
            }
        backend_result = _run_sunny_cpn_minimize_until_converged(
            classical_model,
            supercell_shape=supercell_shape,
            initial_state=glt_initial_state,
            preconditioner=glt_preconditioner,
            starts=starts,
            seed=seed,
            max_linear_size=max_linear_size,
            convergence_repeats=convergence_repeats,
        )
        if backend_result.get("status") != "ok":
            error = backend_result.get("error", {})
            code = error.get("code", "sunny-classical-backend-error")
            message = error.get("message", "Sunny pseudospin-orbital classical backend failed")
            raise RuntimeError(f"{code}: {message}")
        solver_result = {key: value for key, value in backend_result.items() if key != "status"}
        solver_result["glt_preconditioner_diagnostic"] = glt_preconditioner_result
        state = resolve_cpn_local_state(solver_result, default_supercell_shape=supercell_shape)
        if state is not None:
            diagnostics = diagnose_sun_gswt_classical_state(classical_model, state)
            solver_result = {
                **solver_result,
                "supercell_shape": list(solver_result.get("supercell_shape", state["shape"])),
                "local_rays": list(solver_result.get("local_rays", state["local_rays"])),
                "classical_state": resolve_cpn_classical_state_payload(
                    solver_result,
                    default_supercell_shape=supercell_shape,
                ),
                "projector_diagnostics": diagnostics["projector_diagnostics"],
                "stationarity": diagnostics["stationarity"],
            }
        gswt_payload = (
            _build_selected_gswt_payload(
                classical_model,
                solver_result,
                gswt_backend=gswt_backend,
                z_harmonic_reference_mode=z_harmonic_reference_mode,
            )
            if run_gswt and state is not None
            else None
        )
        _progress("Finished Sunny pseudospin-orbital classical minimization")
    elif classical_method in {"cpn-generalized-lt", "cpn-luttinger-tisza"}:
        classical_model = build_sun_gswt_classical_payload(parsed_payload)
        solver_result = solve_cpn_generalized_lt_ground_state(
            classical_model,
            requested_method=str(classical_method),
            starts=1,
            seed=seed,
        )
        gswt_payload = None
    else:
        raise ValueError(f"unsupported classical_method: {classical_method}")

    thermodynamics_result = None
    dos_result = None
    thermodynamics_settings = None
    standardized_classical_result = _build_pseudospin_classical_state_result(
        solver_result,
        classical_method=classical_method,
        default_supercell_shape=supercell_shape,
    )
    if standardized_classical_result is not None:
        solver_result["classical_state_result"] = standardized_classical_result
    if run_thermodynamics:
        thermodynamics_profile = _resolve_thermodynamics_profile(thermo_profile)
        resolved_backend = str(thermodynamics_backend or "sunny-local-sampler")
        if thermodynamics_backend is None and thermodynamics_profile is not None:
            resolved_backend = str(thermodynamics_profile.get("backend_method", resolved_backend))
        resolved_temperatures = [float(value) for value in (temperatures or [])]
        resolved_pt_temperatures = [float(value) for value in (thermo_pt_temperatures or [])]
        resolved_thermo_sweeps = int(
            _profile_override(int(thermo_sweeps), 100, thermodynamics_profile.get("sweeps") if thermodynamics_profile else None)
        )
        resolved_thermo_burn_in = int(
            _profile_override(int(thermo_burn_in), 50, thermodynamics_profile.get("burn_in") if thermodynamics_profile else None)
        )
        resolved_measurement_interval = int(
            _profile_override(
                int(thermo_measurement_interval),
                1,
                thermodynamics_profile.get("measurement_interval") if thermodynamics_profile else None,
            )
        )
        resolved_proposal = str(
            _profile_override(str(thermo_proposal), "delta", thermodynamics_profile.get("proposal") if thermodynamics_profile else None)
        )
        resolved_proposal_scale = float(
            _profile_override(
                float(thermo_proposal_scale),
                0.2,
                thermodynamics_profile.get("proposal_scale") if thermodynamics_profile else None,
            )
        )
        resolved_pt_exchange_interval = int(
            _profile_override(
                int(thermo_pt_exchange_interval),
                1,
                thermodynamics_profile.get("pt_exchange_interval") if thermodynamics_profile else None,
            )
        )
        resolved_wl_windows = int(
            _profile_override(
                int(thermo_wl_windows),
                1,
                thermodynamics_profile.get("wl_windows") if thermodynamics_profile else None,
            )
        )
        resolved_wl_overlap = float(
            _profile_override(
                float(thermo_wl_overlap),
                0.25,
                thermodynamics_profile.get("wl_overlap") if thermodynamics_profile else None,
            )
        )
        resolved_wl_ln_f = float(
            _profile_override(
                float(thermo_wl_ln_f),
                1.0,
                thermodynamics_profile.get("wl_ln_f") if thermodynamics_profile else None,
            )
        )
        resolved_wl_sweeps = int(
            _profile_override(
                int(thermo_wl_sweeps),
                100,
                thermodynamics_profile.get("wl_sweeps") if thermodynamics_profile else None,
            )
        )

        if resolved_backend == "sunny-parallel-tempering":
            if not resolved_pt_temperatures:
                raise ValueError("sunny-parallel-tempering requires --thermo-pt-temperatures")
            if resolved_temperatures and resolved_temperatures != resolved_pt_temperatures:
                raise ValueError("for sunny-parallel-tempering, --temperatures must match --thermo-pt-temperatures")
            resolved_temperatures = list(resolved_pt_temperatures)
        elif resolved_backend == "sunny-wang-landau":
            if thermo_wl_bounds is None or thermo_wl_bin_size is None:
                raise ValueError("sunny-wang-landau requires --thermo-wl-bounds and --thermo-wl-bin-size")
            if not resolved_temperatures:
                raise ValueError("sunny-wang-landau requires --temperatures")
        else:
            if not resolved_temperatures:
                raise ValueError(f"{resolved_backend} requires --temperatures")

        initial_state = resolve_cpn_local_state(solver_result, default_supercell_shape=supercell_shape)
        if initial_state is None:
            raise ValueError("Sunny pseudospin-orbital thermodynamics requires a CP^(N-1) classical state")

        thermodynamics_payload = {
            "backend": "Sunny.jl",
            "payload_kind": "sunny_sun_thermodynamics",
            "backend_method": resolved_backend,
            "profile": thermodynamics_profile.get("name") if thermodynamics_profile is not None else None,
            "model": classical_model,
            "initial_state": initial_state,
            "supercell_shape": list(initial_state["shape"]),
            "temperatures": resolved_temperatures,
            "seed": int(thermo_seed),
            "sweeps": resolved_thermo_sweeps,
            "burn_in": resolved_thermo_burn_in,
            "measurement_interval": resolved_measurement_interval,
            "proposal": resolved_proposal,
            "proposal_scale": resolved_proposal_scale,
            "pt_temperatures": resolved_pt_temperatures,
            "pt_exchange_interval": resolved_pt_exchange_interval,
            "wl_bounds": list(thermo_wl_bounds) if thermo_wl_bounds is not None else None,
            "wl_bin_size": float(thermo_wl_bin_size) if thermo_wl_bin_size is not None else None,
            "wl_windows": resolved_wl_windows,
            "wl_overlap": resolved_wl_overlap,
            "wl_ln_f": resolved_wl_ln_f,
            "wl_sweeps": resolved_wl_sweeps,
        }
        thermodynamics_settings = {
            "profile": thermodynamics_payload["profile"],
            "backend_method": thermodynamics_payload["backend_method"],
            "temperatures": list(thermodynamics_payload["temperatures"]),
            "seed": int(thermodynamics_payload["seed"]),
            "sweeps": int(thermodynamics_payload["sweeps"]),
            "burn_in": int(thermodynamics_payload["burn_in"]),
            "measurement_interval": int(thermodynamics_payload["measurement_interval"]),
            "proposal": str(thermodynamics_payload["proposal"]),
            "proposal_scale": float(thermodynamics_payload["proposal_scale"]),
            "pt_temperatures": list(thermodynamics_payload["pt_temperatures"]),
            "pt_exchange_interval": int(thermodynamics_payload["pt_exchange_interval"]),
            "wl_bounds": (
                list(thermodynamics_payload["wl_bounds"])
                if thermodynamics_payload["wl_bounds"] is not None
                else None
            ),
            "wl_bin_size": thermodynamics_payload["wl_bin_size"],
            "wl_windows": int(thermodynamics_payload["wl_windows"]),
            "wl_overlap": float(thermodynamics_payload["wl_overlap"]),
            "wl_ln_f": float(thermodynamics_payload["wl_ln_f"]),
            "wl_sweeps": int(thermodynamics_payload["wl_sweeps"]),
        }
        _progress(
            "Starting Sunny pseudospin-orbital thermodynamics: "
            f"backend={resolved_backend} temperatures={resolved_temperatures} sweeps={resolved_thermo_sweeps}"
        )
        backend_output = _run_sunny_thermodynamics_backend(thermodynamics_payload, stream_progress=True)
        if backend_output.get("status") != "ok":
            error = backend_output.get("error", {})
            code = error.get("code", "thermodynamics-backend-error")
            message = error.get("message", "Sunny pseudospin-orbital thermodynamics backend failed")
            raise RuntimeError(f"{code}: {message}")

        thermodynamics_result = _normalized_thermodynamics_backend_result(
            backend_output,
            thermodynamics_settings,
        )
        dos_result = backend_output.get("dos_result")
        thermodynamics_backend = resolved_backend
        _progress("Finished Sunny pseudospin-orbital thermodynamics")

    classical_solver_result = dict(solver_result)
    parsed_path = output_dir / "parsed_payload.json"
    simplified_path = output_dir / "simplified_payload.json"
    grouped_path = output_dir / "grouped_terms.json"
    classical_model_path = output_dir / "classical_model.json"
    solver_result_path = output_dir / "solver_result.json"
    gswt_payload_path = output_dir / "gswt_payload.json"
    gswt_result_path = output_dir / "gswt_result.json"
    thermodynamics_result_path = output_dir / "thermodynamics_result.json"
    dos_result_path = output_dir / "dos_result.json"
    result_payload_path = output_dir / "result_payload.json"
    single_q_convergence_path = output_dir / "single_q_convergence.json"
    single_q_convergence_summary_path = output_dir / "single_q_convergence_summary.md"

    single_q_convergence_result = None

    parsed_path.write_text(json.dumps(parsed_payload, indent=2, sort_keys=True), encoding="utf-8")
    simplified_path.write_text(json.dumps(simplified_payload, indent=2, sort_keys=True), encoding="utf-8")
    grouped_path.write_text(json.dumps(grouped_payload, indent=2, sort_keys=True), encoding="utf-8")
    classical_model_path.write_text(json.dumps(classical_model, indent=2, sort_keys=True), encoding="utf-8")
    if gswt_payload is not None:
        gswt_result = _run_selected_gswt(gswt_payload, gswt_backend=gswt_backend)
        solver_result = {**solver_result, "gswt": gswt_result}
        gswt_payload_path.write_text(json.dumps(gswt_payload, indent=2, sort_keys=True), encoding="utf-8")
        gswt_result_path.write_text(json.dumps(gswt_result, indent=2, sort_keys=True), encoding="utf-8")
    solver_result_path.write_text(json.dumps(solver_result, indent=2, sort_keys=True), encoding="utf-8")
    if thermodynamics_result is not None:
        thermodynamics_result_path.write_text(
            json.dumps(thermodynamics_result, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    if dos_result is not None:
        dos_result_path.write_text(json.dumps(dos_result, indent=2, sort_keys=True), encoding="utf-8")
    if (
        isinstance(gswt_payload, dict)
        and str(gswt_payload.get("payload_kind")) == "python_glswt_single_q_z_harmonic"
    ):
        single_q_convergence_result = _run_single_q_convergence_analysis(
            classical_model,
            classical_solver_result,
            gswt_payload,
        )
        single_q_convergence_path.write_text(
            json.dumps(single_q_convergence_result, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        single_q_convergence_summary_path.write_text(
            _single_q_convergence_summary(single_q_convergence_result),
            encoding="utf-8",
        )

    result_payload = _build_result_payload(
        parsed_payload,
        simplified_payload,
        solver_result,
        classical_method=classical_method,
        default_supercell_shape=supercell_shape,
        gswt_payload=gswt_payload,
        single_q_convergence=single_q_convergence_result,
        thermodynamics_settings=thermodynamics_settings,
        thermodynamics_result=thermodynamics_result,
        dos_result=dos_result,
    )
    result_payload_path.write_text(json.dumps(result_payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_manifest = write_results_bundle(
        result_payload,
        output_dir=output_dir,
        run_missing_classical=False,
        run_missing_thermodynamics=False,
        run_missing_gswt=False,
        run_missing_lswt=False,
    )

    phase_note = _write_solver_stage_markdown(
        _solver_phase_summary(
            parsed_payload,
            simplified_payload,
            grouped_payload,
            classical_model,
            solver_result,
            report_manifest,
            classical_method,
            thermodynamics_backend=thermodynamics_backend,
            thermodynamics_result=thermodynamics_result,
            dos_result=dos_result,
        ),
        docs_dir=docs_dir,
    )
    _progress("Wrote final artifacts and phase note")

    return {
        "status": "ok",
        "reports": report_manifest["reports"],
        "solver": solver_result,
        "bundle": bundle_manifest,
        "artifacts": {
            "parsed_payload": str(parsed_path),
            "simplified_payload": str(simplified_path),
            "grouped_terms": str(grouped_path),
            "classical_model": str(classical_model_path),
            "solver_result": str(solver_result_path),
            "classical_checkpoint": (
                str(classical_checkpoint_path)
                if classical_method == "cpn-local-ray-minimize" and classical_checkpoint_path.exists()
                else None
            ),
            "gswt_payload": str(gswt_payload_path) if gswt_payload is not None else None,
            "gswt_result": str(gswt_result_path) if gswt_payload is not None else None,
            "thermodynamics_result": str(thermodynamics_result_path) if thermodynamics_result is not None else None,
            "dos_result": str(dos_result_path) if dos_result is not None else None,
            "single_q_convergence": (
                str(single_q_convergence_path) if single_q_convergence_result is not None else None
            ),
            "single_q_convergence_summary": (
                str(single_q_convergence_summary_path) if single_q_convergence_result is not None else None
            ),
            "result_payload": str(result_payload_path),
            "bundle_manifest": str(output_dir / "bundle_manifest.json"),
            "bundle_report": str(output_dir / "report.txt"),
            "plot_payload": str(output_dir / "plot_payload.json"),
            "phase_note": str(phase_note),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--poscar", required=True)
    parser.add_argument("--hr", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--docs-dir", required=True)
    parser.add_argument("--no-pdf", action="store_true")
    parser.add_argument("--coefficient-tolerance", type=float, default=1e-10)
    parser.add_argument(
        "--local-space-mode",
        choices=["auto", "orbital-times-spin", "generic-multiplet"],
        default="auto",
    )
    parser.add_argument(
        "--classical-method",
        default="restricted-product-state",
        choices=[
            "restricted-product-state",
            "sun-gswt-cpn",
            "sun-gswt-single-q",
            "cpn-local-ray-minimize",
            "sunny-cpn-minimize",
            "cpn-generalized-lt",
            "cpn-luttinger-tisza",
        ],
    )
    parser.add_argument("--supercell-shape", type=int, nargs=3, metavar=("NX", "NY", "NZ"), default=(1, 1, 1))
    parser.add_argument("--starts", type=int, default=16)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--max-linear-size",
        type=int,
        default=0,
        help="Positive values impose a hard supercell linear-size cap; 0 means no cap for sunny-cpn-minimize and cpn-local-ray-minimize.",
    )
    parser.add_argument("--convergence-repeats", type=int, default=2)
    parser.add_argument("--max-sweeps", type=int, default=200)
    parser.add_argument("--no-gswt", action="store_true")
    parser.add_argument("--gswt-backend", choices=["sunny", "python"], default="sunny")
    parser.add_argument(
        "--z-harmonic-reference-mode",
        choices=["input", "refined-retained-local"],
        default="input",
    )
    parser.add_argument("--run-thermodynamics", action="store_true")
    parser.add_argument(
        "--thermodynamics-backend",
        choices=["sunny-local-sampler", "sunny-parallel-tempering", "sunny-wang-landau"],
    )
    parser.add_argument("--temperatures", type=float, nargs="+")
    parser.add_argument("--thermo-seed", type=int, default=0)
    parser.add_argument("--thermo-profile", choices=sorted(THERMODYNAMICS_PROFILES))
    parser.add_argument("--thermo-sweeps", type=int, default=100)
    parser.add_argument("--thermo-burn-in", type=int, default=50)
    parser.add_argument("--thermo-measurement-interval", type=int, default=1)
    parser.add_argument("--thermo-proposal", choices=["delta", "uniform", "flip"], default="delta")
    parser.add_argument("--thermo-proposal-scale", type=float, default=0.2)
    parser.add_argument("--thermo-pt-temperatures", type=float, nargs="+")
    parser.add_argument("--thermo-pt-exchange-interval", type=int, default=1)
    parser.add_argument("--thermo-wl-bounds", type=float, nargs=2)
    parser.add_argument("--thermo-wl-bin-size", type=float)
    parser.add_argument("--thermo-wl-windows", type=int, default=1)
    parser.add_argument("--thermo-wl-overlap", type=float, default=0.25)
    parser.add_argument("--thermo-wl-ln-f", type=float, default=1.0)
    parser.add_argument("--thermo-wl-sweeps", type=int, default=100)
    args = parser.parse_args()

    manifest = solve_from_files(
        poscar_path=Path(args.poscar),
        hr_path=Path(args.hr),
        output_dir=Path(args.output_dir),
        docs_dir=Path(args.docs_dir),
        compile_pdf=not args.no_pdf,
        coefficient_tolerance=float(args.coefficient_tolerance),
        local_space_mode=str(args.local_space_mode),
        classical_method=str(args.classical_method),
        supercell_shape=tuple(int(value) for value in args.supercell_shape),
        starts=int(args.starts),
        seed=int(args.seed),
        max_linear_size=int(args.max_linear_size),
        convergence_repeats=int(args.convergence_repeats),
        max_sweeps=int(args.max_sweeps),
        run_gswt=not args.no_gswt,
        gswt_backend=str(args.gswt_backend),
        z_harmonic_reference_mode=str(args.z_harmonic_reference_mode),
        run_thermodynamics=bool(args.run_thermodynamics),
        thermodynamics_backend=str(args.thermodynamics_backend) if args.thermodynamics_backend is not None else None,
        temperatures=list(args.temperatures) if args.temperatures is not None else None,
        thermo_seed=int(args.thermo_seed),
        thermo_profile=str(args.thermo_profile) if args.thermo_profile is not None else None,
        thermo_sweeps=int(args.thermo_sweeps),
        thermo_burn_in=int(args.thermo_burn_in),
        thermo_measurement_interval=int(args.thermo_measurement_interval),
        thermo_proposal=str(args.thermo_proposal),
        thermo_proposal_scale=float(args.thermo_proposal_scale),
        thermo_pt_temperatures=list(args.thermo_pt_temperatures) if args.thermo_pt_temperatures is not None else None,
        thermo_pt_exchange_interval=int(args.thermo_pt_exchange_interval),
        thermo_wl_bounds=list(args.thermo_wl_bounds) if args.thermo_wl_bounds is not None else None,
        thermo_wl_bin_size=float(args.thermo_wl_bin_size) if args.thermo_wl_bin_size is not None else None,
        thermo_wl_windows=int(args.thermo_wl_windows),
        thermo_wl_overlap=float(args.thermo_wl_overlap),
        thermo_wl_ln_f=float(args.thermo_wl_ln_f),
        thermo_wl_sweeps=int(args.thermo_wl_sweeps),
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
