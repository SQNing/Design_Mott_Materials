"""Test stated mechanisms against controlled numerical responses."""
from copy import deepcopy
from pathlib import Path
import math

from research.contracts import task_name, validate_id
from research.state import read_json
from research.experiments import make_job, execute_jobs
from research.mechanism_observables import (validate_observables, classical_energy_responses,
                                           read_observable)


def _number(value, name, positive=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float)) or
            not math.isfinite(value) or value < 0 or (positive and value == 0)):
        raise ValueError(name + " must be finite and " + ("positive" if positive else "nonnegative"))
    return float(value)


def _validate_hypotheses(hypotheses, observables, groups):
    if not isinstance(hypotheses, list) or not hypotheses:
        raise ValueError("provide explicit testable mechanism hypotheses")
    seen, used = set(), set()
    for hypothesis in hypotheses:
        if not isinstance(hypothesis, dict):
            raise ValueError("hypothesis must be an object")
        identifier = validate_id(hypothesis.get("hypothesis_id"))
        if identifier in seen:
            raise ValueError("duplicate hypothesis_id")
        seen.add(identifier)
        if not isinstance(hypothesis.get("statement"), str) or not hypothesis["statement"].strip():
            raise ValueError("hypothesis needs a physical statement")
        if hypothesis.get("observable_id") not in observables or hypothesis.get("group_id") not in groups:
            raise ValueError("hypothesis refers to an unknown observable or group")
        used.add(hypothesis["observable_id"])
        _number(hypothesis.get("numerical_tolerance"), "numerical_tolerance")
        allowed = {"hypothesis_id", "statement", "kind", "observable_id", "group_id", "numerical_tolerance"}
        kind = hypothesis.get("kind")
        if kind == "monotonic_response":
            allowed |= {"direction", "min_effect"}
            if hypothesis.get("direction") not in {"increasing", "decreasing"}:
                raise ValueError("response direction must be increasing or decreasing")
            _number(hypothesis.get("min_effect"), "min_effect", positive=True)
        elif kind == "insensitive_response":
            allowed.add("max_change")
            _number(hypothesis.get("max_change"), "max_change")
        elif kind == "necessary_in_context":
            allowed |= {"present_above", "absent_below"}
            a = _number(hypothesis.get("present_above"), "present_above", positive=True)
            b = _number(hypothesis.get("absent_below"), "absent_below")
            if a <= b:
                raise ValueError("present_above must exceed absent_below")
        else:
            raise ValueError("unsupported mechanism hypothesis kind")
        if set(hypothesis) - allowed:
            raise ValueError("unknown hypothesis fields")
    if used != set(observables):
        raise ValueError("every requested observable must be used in a hypothesis")


def prepare_mechanism_test(root, state, action, identity):
    settings = action.get("settings", {})
    if not isinstance(settings, dict) or set(settings) - {
            "mechanism_id", "experiments", "observables", "hypotheses",
            "reference_tolerance", "max_memory_mb", "wall_time_seconds"}:
        raise ValueError("invalid mechanism settings")
    identifier = validate_id(settings.get("mechanism_id"))
    entry = state.get("mechanisms", {}).get(identifier)
    if not entry:
        raise ValueError("unknown mechanism_id")
    plan = read_json(entry["record"])
    if plan["parent_model_id"] != state["model"]["model_id"]:
        raise ValueError("mechanism plan belongs to a different full model")
    if plan["status"] != "ready":
        raise ValueError("mechanism points did not pass the original structural symmetry gate")
    _number(settings.get("reference_tolerance", 1e-7), "reference_tolerance")
    models = {p["point_id"]: {"model_id": p["model"]["model_id"],
                "model": read_json(Path(p["model"]["directory"]) / "solver_model.json")}
              for p in plan["points"]}
    experiments = deepcopy(settings.get("experiments"))
    if not isinstance(experiments, list) or not experiments:
        raise ValueError("mechanism test needs numerical experiments")
    seen, jobs, missing, fingerprints = {}, [], set(), {}
    memory = min(state["request"].get("budget", {}).get("max_memory_mb", 4096),
                 _number(settings.get("max_memory_mb", 4096), "max_memory_mb", positive=True))
    for experiment in experiments:
        if not isinstance(experiment, dict) or set(experiment) - {"case_id", "task", "settings", "reference_case"}:
            raise ValueError("invalid mechanism experiment")
        case = validate_id(experiment.get("case_id"))
        if case in seen:
            raise ValueError("duplicate case_id")
        task = task_name(experiment.get("task"))
        experiment["task"] = task
        if task not in {"classical_ground_state", "spin_wave_spectrum", "quantum_low_energy", "classical_monte_carlo"}:
            raise ValueError("unsupported mechanism experiment")
        physical = experiment.setdefault("settings", {})
        if not isinstance(physical, dict) or set(physical) & {
                "initial_state", "initial_spins", "reference_spins", "wall_time_seconds"}:
            raise ValueError("intervention starts and references must be matched by the workflow")
        reference = experiment.get("reference_case")
        if task == "spin_wave_spectrum":
            if reference not in seen or seen[reference]["task"] != "classical_ground_state":
                raise ValueError("spectrum needs a preceding classical reference_case")
        elif reference is not None:
            raise ValueError("reference_case is only supported for harmonic spectra")
        for role, model in models.items():
            job, needed = make_job(root, case, role, model, task, physical, identity, memory,
                                   fingerprints.get((reference, role)))
            if task == "classical_ground_state" and job["inputs"]["capability"]["solver_id"] == "retained-local-python":
                _number(physical.get("max_linear_size"), "retained max_linear_size", positive=True)
            jobs.append(job)
            if needed:
                missing.add(job["fingerprint"])
            fingerprints[(case, role)] = job["fingerprint"]
        seen[case] = experiment
    observables, hypotheses = deepcopy(settings.get("observables")), deepcopy(settings.get("hypotheses"))
    validate_observables(observables, seen, models[plan["baseline_point_id"]]["model"])
    _validate_hypotheses(hypotheses, {x["observable_id"] for x in observables}, {g["group_id"] for g in plan["groups"]})
    return {"plan": plan, "models": models, "experiments": experiments,
            "observables": observables, "hypotheses": hypotheses,
            "jobs": jobs, "planned_solver_runs": len(missing)}


def evaluate_hypothesis(hypothesis, points, values, baseline_point_id):
    baseline = next(p for p in points if p["point_id"] == baseline_point_id)
    group = hypothesis["group_id"]
    isolated = sorted((p for p in points if all(
        p["factors"][g] == factor for g, factor in baseline["factors"].items() if g != group)),
        key=lambda p: p["factors"][group])
    eligible = ([p for p in isolated if p["point_id"] == baseline_point_id or p["factors"][group] == 0]
                if hypothesis["kind"] == "necessary_in_context" else isolated)
    record = {**hypothesis, "status": "inconclusive",
              "used_points": [p["point_id"] for p in eligible],
              "excluded_confounded_points": [p["point_id"] for p in points if p not in isolated],
              "unused_isolated_points": [p["point_id"] for p in isolated if p not in eligible],
              "evidence": [{"point_id": p["point_id"], "factor": p["factors"][group],
                            **values.get(p["point_id"], {})} for p in eligible]}
    minimum_points = 3 if hypothesis["kind"] == "monotonic_response" else 2
    if len(eligible) < minimum_points:
        record["reason"] = ("Necessity requires an isolated zero-factor intervention."
            if hypothesis["kind"] == "necessary_in_context" else
            "Insufficient isolated coupling points with all other groups fixed to the full-model control.")
        return record
    if any(values.get(p["point_id"], {}).get("scientific_status") != "usable_within_scope" or
           values[p["point_id"]].get("value") is None or not math.isfinite(values[p["point_id"]]["value"])
           for p in eligible):
        record["reason"] = "A required control or response is scientifically inconclusive."
        return record
    x = [p["factors"][group] for p in eligible]
    y = [values[p["point_id"]]["value"] for p in eligible]
    baseline_value = values[baseline_point_id]["value"]
    tolerance = hypothesis["numerical_tolerance"]
    kind = hypothesis["kind"]
    record["response"] = {"factors": x, "values": y, "baseline_value": baseline_value}
    if kind == "monotonic_response":
        sign = 1 if hypothesis["direction"] == "increasing" else -1
        differences = [sign * (b - a) for a, b in zip(y[:-1], y[1:])]
        effect = sign * (y[-1] - y[0])
        record["response"].update(directed_span=effect, minimum_directed_increment=min(differences))
        if min(differences) < -tolerance:
            record.update(status="refuted_within_scope", reason="A sampled isolated response reverses the proposed direction.")
        elif effect < hypothesis["min_effect"] - tolerance:
            record.update(status="refuted_within_scope", reason="The measured span is smaller than the stated minimum effect.")
        elif effect > hypothesis["min_effect"] + tolerance:
            record.update(status="supported_within_scope", reason="All sampled isolated increments follow the proposed direction and the span exceeds the threshold.")
        else:
            record["reason"] = "The response is within the comparison tolerance of the effect threshold."
    elif kind == "insensitive_response":
        change = max(abs(v - baseline_value) for v in y)
        record["response"]["maximum_change_from_control"] = change
        limit = hypothesis["max_change"]
        if change < limit - tolerance:
            record.update(status="supported_within_scope", reason="All sampled isolated responses stay within the stated change bound.")
        elif change > limit + tolerance:
            record.update(status="refuted_within_scope", reason="An isolated intervention exceeds the stated change bound.")
        else:
            record["reason"] = "The observed change is within the comparison tolerance of the bound."
    else:
        off = [p for p in eligible if p["factors"][group] == 0]
        if not off:
            record["reason"] = "Necessity requires an isolated zero-factor intervention."
        elif baseline_value <= hypothesis["present_above"] + tolerance:
            record["reason"] = "The full-model control does not clearly establish the specified phenomenon."
        else:
            off_value = values[off[0]["point_id"]]["value"]
            record["response"]["zero_factor_value"] = off_value
            if off_value < hypothesis["absent_below"] - tolerance:
                record.update(status="supported_within_scope", reason="The phenomenon is present in the full-model control and disappears under the isolated removal.")
            elif off_value > hypothesis["absent_below"] + tolerance:
                record.update(status="refuted_within_scope", reason="The phenomenon remains above the absence threshold after the isolated removal.")
            else:
                record["reason"] = "The removal response is within the comparison tolerance of the absence threshold."
    record["explanation"] = (
        "Within the recorded finite model, varying group '%s' over %s gives observable '%s' values %s. %s" %
        (group, x, hypothesis["observable_id"], [float("%.10g" % v) for v in y], record["reason"]))
    return record


def run_mechanism_test(inputs):
    comparison = inputs["comparison"]
    plan = comparison["plan"]
    results, evidence, runs = execute_jobs(inputs, comparison["jobs"])
    experiments = {e["case_id"]: e for e in comparison["experiments"]}
    energies, invalid_controls = classical_energy_responses(
        plan, experiments, results, comparison["models"], inputs["settings"].get("reference_tolerance", 1e-7))
    evidence_by_case = {(e["case_id"], e["role"]): e for e in evidence}
    observations, values = [], {}
    for spec in comparison["observables"]:
        case = spec["case_id"]
        reference = experiments[case].get("reference_case", case)
        for point in plan["points"]:
            point_id = point["point_id"]
            observation = read_observable(spec, results[(case, point_id)],
                evidence_by_case[(case, point_id)], invalid_controls.get((reference, point_id)))
            observation["point_id"] = point_id
            observations.append(observation)
            values.setdefault(spec["observable_id"], {})[point_id] = observation
    hypotheses = [evaluate_hypothesis(h, plan["points"], values[h["observable_id"]], plan["baseline_point_id"])
                  for h in comparison["hypotheses"]]
    scientific = "inconclusive" if any(h["status"] == "inconclusive" for h in hypotheses) else "usable_within_scope"
    scope = {"mechanism_id": plan["mechanism_id"], "full_model_id": inputs["model_id"],
             "units": comparison["models"][plan["baseline_point_id"]]["model"].get("units", {}),
             "local_basis_labels": comparison["models"][plan["baseline_point_id"]]["model"].get("local_basis_labels", []),
             "baseline_point_id": plan["baseline_point_id"], "groups": plan["groups"],
             "points": [{"point_id": p["point_id"], "factors": p["factors"],
                         "model_id": p["model"]["model_id"]} for p in plan["points"]],
             "experiments": comparison["experiments"], "observables": comparison["observables"],
             "reference_tolerance": inputs["settings"].get("reference_tolerance", 1e-7),
             "realized_cases": [{"case_id": case, "point_id": point,
                 "supercell_shape": r.get("calculation", {}).get("supercell_shape"),
                 "local_dimension": r.get("calculation", {}).get("local_dimension"),
                 "spin_length": r.get("calculation", {}).get("spin_length"),
                 "spin": r.get("calculation", {}).get("spin")} for (case, point), r in results.items()]}
    limitations = [
        "Mechanism tests concern only the explicit Hamiltonian interventions, sampled coupling points and observables.",
        "Other groups stay at their full-model values for each one-group hypothesis; confounded points are excluded explicitly.",
        "Stationary finite classical states are not proofs of unique global or infinite-system ground states.",
        "Harmonic observables use sorted frequencies at specified q in the saved magnetic cell, without unfolding or eigenvector branch tracking.",
        "Numerical tolerances are declared comparison resolutions, not certified error bars or phase-equivalence bounds.",
        "Necessity in this context does not establish sufficiency, exclusivity or a universal mechanism.",
        "No virtual-excitation corrections or automatic extension of a simplified model's validated scope."]
    return {"schema_version": "research-result/v1", "result_id": inputs["result_id"],
            "model_id": inputs["model_id"], "task": "mechanism_test",
            "execution_status": "succeeded", "scientific_status": scientific,
            "code_identity": inputs["code_identity"], "mechanism_id": plan["mechanism_id"],
            "solver_runs": runs, "reusable": all(r["execution_status"] != "failed" for r in results.values()),
            "hypotheses": hypotheses, "observations": observations, "energy_responses": energies,
            "evidence": evidence, "validated_scope": scope,
            "calculation": {"hypotheses": hypotheses, "observations": observations,
                            "energy_responses": energies, "validated_scope": scope},
            "diagnostics": evidence, "scientific_scope": limitations,
            "suggested_actions": [{"type": "calculate", "task": "mechanism_test",
                "reason": "Resolve inadequate controls or test additional finite sizes, momenta and isolated coupling points.",
                "requires_agent_choice": True}]}

