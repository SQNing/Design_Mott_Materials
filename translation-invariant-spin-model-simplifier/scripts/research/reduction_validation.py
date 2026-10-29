"""Matched full/candidate experiments, with explicit observables and scope."""
from copy import deepcopy
from pathlib import Path
import math
import numpy as np

from research.contracts import restore_complex, task_name, validate_id
from research.state import read_json
from research.experiments import make_job, execute_jobs

CLASSICAL = "classical_ground_state"
SPECTRUM = "spin_wave_spectrum"
QUANTUM = "quantum_low_energy"
MC = "classical_monte_carlo"


def _number(value, label, positive=False):
    if (isinstance(value, bool) or not isinstance(value, (float, int)) or
            not math.isfinite(value) or value < 0 or (positive and value == 0)):
        raise ValueError(label + " must be finite and " + ("positive" if positive else "nonnegative"))
    return float(value)


def prepare_validation(root, state, action, identity):
    settings = action.get("settings", {})
    if not isinstance(settings, dict):
        raise ValueError("comparison settings must be an object")
    allowed_settings = {"candidate_id", "experiments", "energy_window_max", "energy_offset_per_cell",
                        "full_reference_tolerance", "max_memory_mb", "wall_time_seconds"}
    if set(settings) - allowed_settings:
        raise ValueError("unknown comparison settings: " + ", ".join(sorted(set(settings) - allowed_settings)))
    identifier = validate_id(settings.get("candidate_id"))
    entry = state.get("reductions", {}).get(identifier)
    if not entry:
        raise ValueError("unknown candidate_id")
    candidate = read_json(entry["record"])
    if candidate["parent_model_id"] != state["model"]["model_id"]:
        raise ValueError("candidate belongs to a different full model; propose it again")
    if candidate["status"] != "ready":
        raise ValueError("candidate did not pass the complete-model symmetry gate")
    models = {
        "full": {"model_id": state["model"]["model_id"], "model": read_json(
            Path(state["model"]["directory"]) / "solver_model.json")},
        "candidate": {"model_id": candidate["candidate"]["model_id"], "model": read_json(
            Path(candidate["candidate"]["directory"]) / "solver_model.json")}}
    projected = candidate["transformation"]["kind"] == "project_local_space"
    if projected or settings.get("energy_window_max") is not None:
        _number(settings.get("energy_window_max"), "energy_window_max", positive=True)
    offset = settings.get("energy_offset_per_cell", 0.)
    if isinstance(offset, bool) or not isinstance(offset, (int, float)) or not math.isfinite(offset):
        raise ValueError("energy_offset_per_cell must be finite")
    _number(settings.get("full_reference_tolerance", 1e-7), "full_reference_tolerance")
    spaces = models["full"]["model"]["local_hilbert"]["classical_spaces"]
    retained = all(v["kind"] == "complex_projective_space" for v in spaces.values())
    state_metric = "projector_distance" if retained else "spin_correlations"
    allowed = {CLASSICAL: {"energy_per_cell", "full_energy_penalty", state_metric},
               SPECTRUM: {"spectrum"}, QUANTUM: {"quantum_gaps"}, MC: {"mc_energy_per_site"}}
    experiments = deepcopy(settings.get("experiments"))
    if not isinstance(experiments, list) or not experiments:
        raise ValueError("validation requires explicit experiments and tolerances")
    seen, jobs, planned, fingerprints = {}, [], set(), {}
    memory = min(state["request"].get("budget", {}).get("max_memory_mb", 4096),
                 _number(settings.get("max_memory_mb", 4096), "max_memory_mb", positive=True))
    for experiment in experiments:
        if not isinstance(experiment, dict):
            raise ValueError("each experiment must be an object")
        if set(experiment) - {"case_id", "task", "settings", "metrics", "reference_case"}:
            raise ValueError("unknown experiment fields")
        case = validate_id(experiment.get("case_id"))
        if case in seen:
            raise ValueError("duplicate case_id")
        task = task_name(experiment.get("task"))
        experiment["task"] = task
        if task not in allowed:
            raise ValueError("unsupported comparison experiment: " + str(task))
        metrics = experiment.get("metrics", {})
        if not isinstance(metrics, dict):
            raise ValueError("metrics must map each observable to its tolerance")
        if set(metrics) != allowed[task]:
            raise ValueError("experiment metrics must explicitly supply: " + ", ".join(sorted(allowed[task])))
        for name, tolerance in metrics.items():
            _number(tolerance, name + " tolerance")
        physical_settings = experiment.setdefault("settings", {})
        if not isinstance(physical_settings, dict):
            raise ValueError("experiment settings must be an object")
        if set(physical_settings) & {"initial_state", "initial_spins", "reference_spins", "wall_time_seconds"}:
            raise ValueError("comparison starts and references must be matched by the workflow")
        reference_case = experiment.get("reference_case")
        if task == SPECTRUM:
            if reference_case not in seen or seen[reference_case]["task"] != CLASSICAL:
                raise ValueError("spectrum needs a preceding classical reference_case")
        elif reference_case is not None:
            raise ValueError("reference_case is only supported for harmonic spectra")
        for role, model in models.items():
            reference_fingerprint = fingerprints.get((reference_case, role))
            job, missing = make_job(root, case, role, model, task, physical_settings,
                                    identity, memory, reference_fingerprint)
            if missing:
                planned.add(job["fingerprint"])
            jobs.append(job)
            fingerprints[(case, role)] = job["fingerprint"]
        seen[case] = experiment
    tasks = {e["task"] for e in experiments}
    if CLASSICAL not in tasks or not tasks.intersection({SPECTRUM, QUANTUM}):
        raise ValueError("validation needs classical observables and a harmonic or quantum spectrum")
    return {"candidate": candidate, "experiments": experiments, "jobs": jobs,
            "planned_solver_runs": len(planned)}


def _metric(case, name, value, tolerance, reason=None, inconclusive=False):
    finite = value is not None and math.isfinite(float(value))
    return {"case_id": case, "name": name, "value": float(value) if finite else None,
            "tolerance": tolerance, "outcome": "inconclusive" if inconclusive or not finite else
            ("pass" if value <= tolerance else "fail"), **({"reason": reason} if reason else {})}


def _classical_observables(full_model, mapping, full, candidate):
    a, b = full["calculation"], candidate["calculation"]
    if a["supercell_shape"] != b["supercell_shape"]:
        raise ValueError("classical searches selected different supercells; use matched fixed cells")
    if "classical_state" in a:
        from classical.cpn_local_ray_energy import state_array_from_serialized, evaluate_cpn_local_ray_energy
        from research.adapters import retained_payload
        va = state_array_from_serialized({**a["classical_state"], "shape": a["classical_state"]["supercell_shape"]})
        vb = state_array_from_serialized({**b["classical_state"], "shape": b["classical_state"]["supercell_shape"]})
        if mapping["kind"] == "project_local_space":
            embedding = np.asarray(restore_complex(mapping["isometry"]), dtype=complex)
            vb = np.einsum("an,...n->...a", embedding, vb)
        if va.shape != vb.shape:
            raise ValueError("incompatible site/cell ordering or local dimensions")
        da = np.einsum("...i,...j->...ij", va, va.conjugate())
        db = np.einsum("...i,...j->...ij", vb, vb.conjugate())
        distance = float(np.max(np.linalg.norm(da - db, axis=(-2, -1))))
        energy = evaluate_cpn_local_ray_energy(retained_payload(restore_complex(full_model)), vb)
        return float(energy), "projector_distance", distance
    from common.hamiltonian_symmetry_gate import run_hamiltonian_symmetry_gate
    from three_dimensional.spin_payload import global_spin_payload
    from three_dimensional.spin_system import PeriodicSpinSystem
    gate = run_hamiltonian_symmetry_gate(restore_complex(full_model))
    payload = global_spin_payload(gate)
    system = PeriodicSpinSystem(payload, a["supercell_shape"])
    va, vb = np.asarray(a["spins"]), np.asarray(b["spins"])
    if va.shape != vb.shape or a["spin_length"] != b["spin_length"]:
        raise ValueError("incompatible spin lengths or site/cell ordering")
    scale = float(a["spin_length"]) ** 2
    distance = float(np.max(np.abs(va @ va.T - vb @ vb.T)) / scale)
    energy, _ = system.energy_gradient(vb)
    return float(energy / system.cell_count), "spin_correlations", distance


def compare_experiment(experiment, full, candidate, full_model, mapping, settings):
    case, task = experiment["case_id"], experiment["task"]
    tolerances = experiment["metrics"]
    if any(r.get("scientific_status") != "usable_within_scope" for r in (full, candidate)):
        return [_metric(case, name, None, tol, "A control/candidate result is not scientifically usable.",
                        inconclusive=True) for name, tol in tolerances.items()]
    a, b = full["calculation"], candidate["calculation"]
    try:
        if task == CLASSICAL:
            lifted, state_metric, distance = _classical_observables(full_model, mapping, full, candidate)
            penalty = lifted - float(a["energy_per_cell"])
            if penalty < -settings.get("full_reference_tolerance", 1e-7):
                return [_metric(case, name, None, tol,
                    "The lifted candidate has lower full-model energy; refine the full-model reference.",
                    inconclusive=True) for name, tol in tolerances.items()]
            values = {"energy_per_cell": abs(float(b["energy_per_cell"]) +
                      settings.get("energy_offset_per_cell", 0.) - float(a["energy_per_cell"])),
                      "full_energy_penalty": max(0., penalty), state_metric: distance}
            return [_metric(case, name, values[name], tol) for name, tol in tolerances.items()]
        if task == SPECTRUM:
            tolerance = tolerances["spectrum"]
            if a.get("supercell_shape") != b.get("supercell_shape"):
                raise ValueError("spectra use different reference supercells")
            ra, rb = a["dispersion"], b["dispersion"]
            if not ra or len(ra) != len(rb):
                raise ValueError("spectra use different or empty momentum grids")
            maximum, count = 0., 0
            for left, right in zip(ra, rb):
                if not np.allclose(left["q"], right["q"], atol=1e-12, rtol=0):
                    raise ValueError("spectra use different momentum points")
                x, y = np.sort(left["bands"]), np.sort(right["bands"])
                if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
                    raise ValueError("nonfinite spectrum")
                window = settings.get("energy_window_max")
                if window is not None:
                    if np.any(np.abs(x - window) <= tolerance) or np.any(np.abs(y - window) <= tolerance):
                        raise ValueError("a mode is within tolerance of the energy-window boundary")
                    x, y = x[x < window], y[y < window]
                if len(x) != len(y):
                    metric = _metric(case, "spectrum_mode_count", abs(len(x) - len(y)), 0,
                        "Different numbers of modes in the requested energy window at q=" + str(left["q"]))
                    return [metric]
                if len(x):
                    maximum = max(maximum, float(np.max(np.abs(x - y))))
                    count += len(x)
            if count == 0:
                raise ValueError("no modes lie in the requested energy window")
            return [_metric(case, "spectrum", maximum, tolerance)]
        if task == QUANTUM:
            if a["supercell_shape"] != b["supercell_shape"] or a["spin"] != b["spin"]:
                raise ValueError("finite quantum clusters or spins differ")
            x, y = np.asarray(a["eigenvalues"]), np.asarray(b["eigenvalues"])
            if len(x) != len(y) or len(x) < 2:
                raise ValueError("quantum comparison needs the same number of eigenvalues, at least two")
            return [_metric(case, "quantum_gaps", float(np.max(np.abs((x - x[0]) - (y - y[0])))),
                            tolerances["quantum_gaps"])]
        # The existing MC path is explicitly unverified for equilibration and
        # therefore reaches the inconclusive branch above.
        raise ValueError("equilibrated finite-temperature comparison is not implemented")
    except (ValueError, KeyError, TypeError) as exc:
        return [_metric(case, name, None, tol, str(exc), inconclusive=True)
                for name, tol in tolerances.items()]


def run_reduction_validation(inputs):
    comparison = inputs["comparison"]
    results, evidence, runs = execute_jobs(inputs, comparison["jobs"])
    metrics, inadequate_controls = [], set()
    full_model = next(j["inputs"]["model"] for j in comparison["jobs"] if j["role"] == "full")
    for experiment in comparison["experiments"]:
        if experiment.get("reference_case") in inadequate_controls:
            metrics.extend(_metric(experiment["case_id"], name, None, tol,
                "The full/candidate reference comparison is inconclusive; refine it before interpreting this spectrum.",
                inconclusive=True) for name, tol in experiment["metrics"].items())
            continue
        compared = compare_experiment(experiment,
            results[(experiment["case_id"], "full")], results[(experiment["case_id"], "candidate")],
            full_model, comparison["candidate"]["transformation"], inputs["settings"])
        metrics.extend(compared)
        if experiment["task"] == CLASSICAL and any(m["outcome"] == "inconclusive" for m in compared):
            inadequate_controls.add(experiment["case_id"])
    outcomes = {m["outcome"] for m in metrics}
    verdict = ("rejected" if "fail" in outcomes else
               "inconclusive" if "inconclusive" in outcomes or not metrics else "accepted_within_scope")
    scope = {"full_model_id": inputs["model_id"],
             "candidate_model_id": comparison["candidate"]["candidate"]["model_id"],
             "experiments": comparison["experiments"],
             "energy_window_max": inputs["settings"].get("energy_window_max"),
             "energy_offset_per_cell": inputs["settings"].get("energy_offset_per_cell", 0.),
             "full_reference_tolerance": inputs["settings"].get("full_reference_tolerance", 1e-7)}
    scope["realized_cases"] = [
        {"case_id": case, "role": role,
         "supercell_shape": result.get("calculation", {}).get("supercell_shape"),
         "spin_length": result.get("calculation", {}).get("spin_length"),
         "spin": result.get("calculation", {}).get("spin"),
         "local_dimension": result.get("calculation", {}).get("local_dimension")}
        for (case, role), result in results.items()]
    limitations = [
        "Only this parameter point, the recorded finite cells, sampled momenta and selected observables were compared.",
        "Stationary variational states are not proofs of global or infinite-lattice ground states.",
        "State distances can distinguish symmetry-related representatives; rejection concerns the stated metric.",
        "Agreement does not certify phase equivalence, parameter robustness or virtual-excitation corrections."]
    return {"schema_version": "research-result/v1", "result_id": inputs["result_id"],
            "model_id": inputs["model_id"], "task": "reduction_validation",
            "execution_status": "succeeded", "code_identity": inputs["code_identity"],
            "scientific_status": "inconclusive" if verdict == "inconclusive" else "usable_within_scope",
            "validation_status": verdict, "candidate_id": comparison["candidate"]["candidate_id"],
            "reusable": all(r["execution_status"] != "failed" for r in results.values()),
            "candidate_model_id": scope["candidate_model_id"], "solver_runs": runs,
            "metrics": metrics, "validated_scope": scope, "evidence": evidence,
            "calculation": {"validation_status": verdict, "metrics": metrics, "validated_scope": scope},
            "scientific_scope": limitations, "diagnostics": evidence,
            "suggested_actions": [{"type": "calculate", "task": "reduction_validation",
                "reason": "Refine inadequate controls or extend the tested cells, momenta and parameter points.",
                "requires_agent_choice": True}]}

