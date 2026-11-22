"""A host agent chooses actions; this module validates and records them."""
from copy import deepcopy
import os
from pathlib import Path
import subprocess
import sys
import time

from research.contracts import (SCRIPTS, budget_for, code_identity, digest,
                                same_code_identity, task_code_groups, task_name,
                                validate_id)
from research.models import load_source, merge_patch, prepare_model
from research.state import (collect_steps, compute_seconds, event, locked,
                            new_state, process_identity, read_json, write_json)


def _view(root, state):
    model = state["model"]
    steps = collect_steps(root, state)
    active = [s["action_id"] for s in steps
              if s["execution"]["status"] in {"running", "pending", "unknown"}]
    solver_runs = sum(s["execution"].get("solver_runs", int(bool(s["execution"].get("counted"))))
                      for s in steps)
    reductions = []
    for entry in state.get("reductions", {}).values():
        candidate = read_json(entry["record"])
        candidate["current_parent"] = candidate["parent_model_id"] == model["model_id"]
        candidate["validations"] = [
            {"result_id": s["action_id"], "validation_status": s["result"]["validation_status"]}
            for s in steps if s["result"] and s["result"].get("candidate_id") == candidate["candidate_id"]
            and "validation_status" in s["result"]]
        reductions.append(candidate)
    mechanisms = []
    for entry in state.get("mechanisms", {}).values():
        plan = read_json(entry["record"])
        plan["current_parent"] = plan["parent_model_id"] == model["model_id"]
        plan["tests"] = [
            {"result_id": s["action_id"], "scientific_status": s["result"]["scientific_status"],
             "hypotheses": [{"hypothesis_id": h["hypothesis_id"], "status": h["status"]}
                            for h in s["result"].get("hypotheses", [])]}
            for s in steps if s["result"] and s["result"].get("mechanism_id") == plan["mechanism_id"]]
        mechanisms.append(plan)
    status = model["status"]
    if active:
        status = "running"
    elif state["answer_status"] == "answered_within_scope":
        status = "completed"
    elif steps and steps[-1]["result"] and steps[-1]["result"]["scientific_status"] != "usable_within_scope":
        status = "inconclusive" if status == "ready" else status
    return {"schema_version": "research-inspection/v1", "run_dir": str(root),
            "status": status, "question": state["request"].get("question", ""),
            "requested_tasks": state["request"].get("requested_tasks", []),
            "answer_status": state["answer_status"], "model": model,
            "questions": model.get("questions", []), "steps": steps,
            "active_actions": active, "solver_runs": solver_runs,
            "compute_seconds": compute_seconds(steps),
            "time_accounting": [{"action_id": s["action_id"], **s["execution"]["time_accounting"]}
                                for s in steps],
            "budget": budget_for(state["request"]),
            "assessments": state["assessments"],
            "reductions": reductions,
            "mechanisms": mechanisms,
            "next_actions": _next_actions(model, steps)}


def _next_actions(model, steps):
    if model["status"] == "needs_input":
        return [{"type": "provide_input", "reason": "Resolve the recorded physical questions."}]
    if model["status"] != "ready":
        return []
    if steps:
        result = steps[-1].get("result") or {}
        return result.get("suggested_actions", [])
    return [{"type": "calculate", "task": "classical_ground_state",
             "reason": "Choose explicit finite-cell settings for the full model."}]


def prepare_research_task(request, run_dir):
    request = deepcopy(request)
    budget_for(request)
    if not request.get("question"):
        raise ValueError("request.question is required")
    root = Path(run_dir).expanduser().resolve()
    with locked(root):
        index = root / "state.json"
        if index.exists():
            state = read_json(index)
            if state["initial_request_hash"] != digest(request):
                raise ValueError("run already exists with another request; use provide_input or a new run_dir")
            return _view(root, state)
        source, provenance = load_source(request)
        state = new_state(request)
        state["initial_request_hash"] = digest(request)
        state["version"] = 1
        state["model"] = prepare_model(source, request, root, 1)
        write_json(root / "request.json", request, exclusive=True)
        write_json(root / "source-provenance.json", provenance, exclusive=True)
        write_json(root / "state.json", state)
        event(root, {"type": "prepare", "model_id": state["model"]["model_id"]})
        return _view(root, state)


def inspect_research_task(run_dir):
    root = Path(run_dir).expanduser().resolve()
    if not (root / "state.json").is_file():
        raise ValueError("research task does not exist: " + str(root))
    with locked(root):
        return _view(root, read_json(root / "state.json"))


def _provide_input(root, state, action):
    old = state["input_actions"].get(action["action_id"])
    if old:
        if old["action_hash"] != digest(action):
            raise ValueError("action_id already used with different content")
        return _view(root, state)
    if _view(root, state)["active_actions"]:
        raise ValueError("cannot revise the model while its calculation is active")
    source = read_json(Path(state["model"]["directory"]) / "source.json")
    if "model" in action:
        source = deepcopy(action["model"])
    if "model_patch" in action:
        source = merge_patch(source, action["model_patch"])
    updates = action.get("request_updates", {})
    allowed = {"normalization", "agent_normalized_document", "physics_policy",
               "budget", "requested_tasks", "question"}
    if set(updates) - allowed:
        raise ValueError("unsupported request update: " + str(sorted(set(updates) - allowed)))
    state["request"] = merge_patch(state["request"], updates)
    budget_for(state["request"])
    state["version"] += 1
    state["model"] = prepare_model(source, state["request"], root, state["version"])
    state["answer_status"] = "pending"
    state["input_actions"][action["action_id"]] = {"action_hash": digest(action),
                                                 "version": state["version"]}
    write_json(root / "inputs" / (action["action_id"] + ".json"), action, exclusive=True)
    write_json(root / "state.json", state)
    event(root, {"type": "provide_input", "action": action, "model_id": state["model"]["model_id"]})
    return _view(root, state)


def _assess(root, state, action):
    for existing in state["assessments"]:
        if existing["action_id"] == action["action_id"]:
            if digest(existing) != digest(action):
                raise ValueError("action_id already used with different content")
            return _view(root, state)
    status = action.get("answer_status")
    if status not in {"answered_within_scope", "partial", "inconclusive"}:
        raise ValueError("assessment needs a valid answer_status")
    if not action.get("conclusion") or not action.get("limitations"):
        raise ValueError("assessment needs conclusion and explicit limitations")
    claim = action.get("claim_level", "within_recorded_scope")
    if claim not in {"within_recorded_scope", "stationary_reference",
                     "finite_cell_ground_state", "thermodynamic_ground_state"}:
        raise ValueError("unknown assessment claim_level")
    results = {s["action_id"]: s["result"] for s in collect_steps(root, state)}
    evidence = action.get("evidence", [])
    tasks = set()
    classical = []
    for citation in evidence:
        result = results.get(citation.get("result_id"))
        if not result or result["model_id"] != state["model"]["model_id"]:
            raise ValueError("assessment evidence must refer to a result of the current model")
        value = result
        for part in citation.get("path", "calculation").split("."):
            try:
                value = value[int(part)] if isinstance(value, list) else value[part]
            except (KeyError, IndexError, ValueError, TypeError):
                raise ValueError("assessment evidence path does not exist")
        if status == "answered_within_scope" and result["scientific_status"] != "usable_within_scope":
            raise ValueError("inconclusive or diagnostic-only evidence cannot complete the task")
        tasks.add(result["task"])
        if result["task"] == "classical_ground_state":
            classical.append(result)
    required = {task_name(t) for t in state["request"].get("requested_tasks", [])}
    if status == "answered_within_scope":
        if not evidence or not required or not required.issubset(tasks):
            raise ValueError("answered assessment requires evidence covering explicit requested_tasks")
        if _view(root, state)["active_actions"] or state["model"]["status"] != "ready":
            raise ValueError("task still has active calculations or unresolved physical inputs")
        if not action.get("scope"):
            raise ValueError("answered assessment requires the finite/approximate scope of the claim")
        if claim == "thermodynamic_ground_state":
            raise ValueError("thermodynamic ground-state claims need evidence beyond the connected finite-cell calculations")
        if claim in {"stationary_reference", "finite_cell_ground_state"}:
            if not classical:
                raise ValueError("the declared claim_level needs explicit classical reference evidence")
            for result in classical:
                recorded = result["calculation"].get("ground_state_evidence", {})
                if claim == "finite_cell_ground_state" and recorded.get("finite_cell_status") != "bound_saturated":
                    raise ValueError("finite-cell ground-state claims require recorded finite-cell bound saturation")
                if claim == "stationary_reference" and recorded.get("stationary") is not True:
                    raise ValueError("stationary_reference claims require recorded stationarity evidence")
    state["assessments"].append(deepcopy(action))
    state["answer_status"] = status
    write_json(root / "assessments" / (action["action_id"] + ".json"), action, exclusive=True)
    write_json(root / "state.json", state)
    event(root, {"type": "assess", "action": action})
    return _view(root, state)


def _blocked(root, state, action, blocker, *, scientific_status="inconclusive"):
    directory = root / "steps" / action["action_id"]
    directory.mkdir(parents=True, exist_ok=False)
    result = {"schema_version": "research-result/v1", "result_id": action["action_id"],
              "model_id": state["model"]["model_id"], "task": task_name(action["task"]),
              "execution_status": "not_started", "scientific_status": scientific_status,
              "blocker": blocker, "finished_at": time.time(), "diagnostics": [],
              "scientific_scope": [], "suggested_actions": []}
    write_json(directory / "action.json", action, exclusive=True)
    write_json(directory / "execution.json", {"status": "not_started", "counted": False}, exclusive=True)
    write_json(directory / "result.json", result, exclusive=True)
    state["steps"].append(action["action_id"])
    state["answer_status"] = "pending"
    write_json(root / "state.json", state)
    event(root, {"type": "blocked", "action": action, "blocker": blocker})
    return result


def _registry_path(root):
    override = os.environ.get("SPINFORGE_RESEARCH_REGISTRY")
    if override:
        return Path(override).expanduser().resolve()
    return Path(root).expanduser().resolve().parent / "registry.jsonl"


def _record_registry_best_effort(root):
    try:
        from research.registry import record_run
        record_run(root, _registry_path(root))
    except Exception:
        # Registry sync must never change the scientific outcome of a run.
        pass


def _reuse_result(root, state, action, result, *, source):
    directory = root / "steps" / action["action_id"]
    directory.mkdir(parents=True, exist_ok=False)
    reused = {**result, "result_id": action["action_id"],
              "reused_from": result["result_id"], "execution_status": "reused",
              "finished_at": time.time()}
    if source != "local":
        reused["reused_from_run_dir"] = str(source)
    if "solver_runs" in reused:
        reused["solver_runs"] = 0
    write_json(directory / "action.json", action, exclusive=True)
    write_json(directory / "execution.json", {"status": "reused", "counted": False}, exclusive=True)
    write_json(directory / "result.json", reused, exclusive=True)
    state["steps"].append(action["action_id"])
    state["answer_status"] = "pending"
    write_json(root / "state.json", state)
    event(root, {"type": "reuse", "action": action,
                 "reused_from": result["result_id"], "source": str(source)})
    return reused


def _registry_fingerprint_candidate(root, fingerprint):
    try:
        from research.registry import find_fingerprint
        candidate = find_fingerprint(_registry_path(root), fingerprint)
    except Exception:
        return None
    if not candidate:
        return None
    candidate_run = Path(candidate["run_dir"]).expanduser().resolve()
    if candidate_run == Path(root).expanduser().resolve():
        return None
    path = candidate_run / "steps" / candidate["result_id"] / "result.json"
    if not path.is_file():
        return None
    result = read_json(path)
    if (result.get("calculation_fingerprint") == fingerprint and
            result.get("execution_status") in {"succeeded", "reused"} and
            result.get("reusable", True) and
            same_code_identity(result.get("code_identity"))):
        return result, candidate_run
    return None


def _launch(root, state, action):
    from research.adapters import capability_for
    view = _view(root, state)
    if view["active_actions"]:
        raise ValueError("calculation already active: " + ",".join(view["active_actions"]))
    if state["model"]["status"] != "ready":
        return _blocked(root, state, action, "model-needs-input-or-unsupported",
                        scientific_status=state["model"]["status"])
    model = read_json(Path(state["model"]["directory"]) / "solver_model.json")
    task = task_name(action.get("task"))
    # Scope the identity to the code groups this task actually executes so
    # caches and references survive edits to unrelated solver backends.
    identity = code_identity(groups=task_code_groups(task))
    comparison = None
    if task == "reduction_validation":
        from research.reduction_validation import prepare_validation
        comparison = prepare_validation(root, state, action, identity)
        capability = {"status": "supported", "solver_id": "reduction-comparison"}
    elif task == "mechanism_test":
        from research.mechanism_analysis import prepare_mechanism_test
        comparison = prepare_mechanism_test(root, state, action, identity)
        capability = {"status": "supported", "solver_id": "mechanism-response"}
    else:
        capability = capability_for(model, task, action.get("settings", {}))
    if capability["status"] != "supported":
        return _blocked(root, state, action, capability["blocker"], scientific_status="unsupported")
    reference = None
    reference_id = action.get("reference_result")
    if reference_id:
        validate_id(reference_id)
        path = root / "steps" / reference_id / "result.json"
        if not path.is_file():
            raise ValueError("reference result is absent or still running")
        reference = read_json(path)
        if reference["model_id"] != state["model"]["model_id"]:
            raise ValueError("reference belongs to a different model")
        if not same_code_identity(reference.get("code_identity")):
            raise ValueError("reference code/runtime differs; recompute or explicitly import with provenance")
        if reference.get("task") != "classical_ground_state":
            raise ValueError("reference must be a classical ground-state result")
        if task == "spin_wave_spectrum" and reference.get("scientific_status") != "usable_within_scope":
            raise ValueError("reference is not scientifically usable; refine it first")
        if not reference.get("calculation"):
            raise ValueError("reference contains no state to refine")
    if task == "spin_wave_spectrum" and reference is None:
        raise ValueError("harmonic spectrum requires an explicit saved reference_result")
    fingerprint = digest({"model_id": state["model"]["model_id"], "task": task,
                          "settings": action.get("settings", {}),
                          "reference": reference_id, "code_identity": identity})
    for step in view["steps"]:
        result = step["result"]
        if (result and result.get("calculation_fingerprint") == fingerprint and
                result.get("execution_status") in {"succeeded", "reused"} and
                result.get("reusable", True)):
            return _reuse_result(root, state, action, result, source="local")
    registry_candidate = _registry_fingerprint_candidate(root, fingerprint)
    if registry_candidate:
        result, source_run = registry_candidate
        return _reuse_result(root, state, action, result, source=source_run)
    budget = view["budget"]
    planned_runs = comparison["planned_solver_runs"] if comparison else 1
    if view["solver_runs"] + planned_runs > budget["max_solver_runs"]:
        return _blocked(root, state, action, "solver-run-budget-exhausted")
    remaining = budget["max_wall_time_seconds"] - view["compute_seconds"]
    if remaining <= 0:
        return _blocked(root, state, action, "wall-time-budget-exhausted")
    settings = deepcopy(action.get("settings", {}))
    if not isinstance(settings, dict):
        raise ValueError("settings must be an object")
    settings["max_memory_mb"] = min(float(settings.get("max_memory_mb", budget["max_memory_mb"])),
                                    budget["max_memory_mb"])
    timeout = min(float(settings.pop("wall_time_seconds", remaining)), remaining)
    if timeout <= 0:
        raise ValueError("wall_time_seconds must be positive")
    directory = root / "steps" / action["action_id"]
    directory.mkdir(parents=True, exist_ok=False)
    write_json(directory / "action.json", action, exclusive=True)
    write_json(directory / "input.json", {
        "model": model, "model_id": state["model"]["model_id"], "task": task,
        "settings": settings, "reference": reference, "result_id": action["action_id"],
        "capability": capability, "code_identity": identity, "timeout": timeout,
        "max_memory_mb": settings["max_memory_mb"], "calculation_fingerprint": fingerprint,
        **({"comparison": comparison, "work_directory": str(directory)} if comparison else {}),
    }, exclusive=True)
    execution = {"status": "pending", "counted": True, "started_at": time.time(),
                 "timeout_seconds": timeout, "max_memory_mb": settings["max_memory_mb"],
                 "solver_runs": planned_runs}
    write_json(directory / "execution.json", execution, exclusive=True)
    state["steps"].append(action["action_id"])
    state["answer_status"] = "pending"
    write_json(root / "state.json", state)
    env = dict(os.environ, PYTHONPATH=str(SCRIPTS), PYTHONDONTWRITEBYTECODE="1",
               OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    try:
        with (directory / "worker.log").open("ab") as stream:
            process = subprocess.Popen(
                [sys.executable, "-B", "-m", "research.worker", str(directory)],
                stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                start_new_session=True, env=env)
        execution.update(status="running", worker=process_identity(process.pid))
        write_json(directory / "execution.json", execution)
    except OSError as exc:
        write_json(directory / "result.json", {
            "result_id": action["action_id"], "model_id": state["model"]["model_id"],
            "task": task, "execution_status": "failed", "scientific_status": "inconclusive",
            "solver_runs": 0,
            "blocker": "worker-launch-failed: " + str(exc), "finished_at": time.time(),
        }, exclusive=True)
    event(root, {"type": "calculate", "action": action, "execution": execution})
    return {"result_id": action["action_id"], "execution_status": execution["status"],
            "scientific_status": "pending", "worker": execution.get("worker")}


def execute_research_action(run_dir, action, *, wait=False):
    action = deepcopy(action)
    validate_id(action.get("action_id"))
    if not isinstance(action.get("reason"), str) or not action["reason"].strip():
        raise ValueError("each action needs a nonempty reason")
    root = Path(run_dir).expanduser().resolve()
    with locked(root):
        state = read_json(root / "state.json")
        identifier = action["action_id"]
        if identifier in state["steps"]:
            step = next(s for s in collect_steps(root, state) if s["action_id"] == identifier)
            if digest(step["action"]) != digest(action):
                raise ValueError("action_id already used with different content")
            outcome = step["result"] or {
                "result_id": identifier, "execution_status": step["execution"]["status"],
                "scientific_status": "pending", "worker": step["execution"].get("worker")}
        else:
            known = (set(state["input_actions"]) | {a["action_id"] for a in state["assessments"]} |
                     set(state.get("reductions", {})) | set(state.get("mechanisms", {})))
            if identifier in known and not (
                action.get("type") == "provide_input" and identifier in state["input_actions"] or
                action.get("type") == "assess" and any(a["action_id"] == identifier for a in state["assessments"]) or
                action.get("type") == "propose_reduction" and identifier in state.get("reductions", {}) or
                action.get("type") == "propose_mechanism" and identifier in state.get("mechanisms", {})):
                raise ValueError("action_id already used")
            if action.get("type") == "provide_input":
                return _provide_input(root, state, action)
            if action.get("type") == "assess":
                return _assess(root, state, action)
            if action.get("type") == "propose_reduction":
                from research.reductions import propose_reduction
                return propose_reduction(root, state, action)
            if action.get("type") == "propose_mechanism":
                from research.mechanisms import propose_mechanism
                return propose_mechanism(root, state, action)
            if action.get("type") != "calculate" or not action.get("task"):
                raise ValueError("action must be provide_input, propose_reduction, propose_mechanism, calculate with task, or assess")
            outcome = _launch(root, state, action)
    if outcome.get("execution_status") in {"succeeded", "reused"}:
        _record_registry_best_effort(root)
    if wait and outcome["execution_status"] in {"running", "pending"}:
        while True:
            view = inspect_research_task(root)
            step = next(s for s in view["steps"] if s["action_id"] == action["action_id"])
            if step["result"]:
                _record_registry_best_effort(root)
                return step["result"]
            if step["execution"]["status"] not in {"running", "pending"}:
                _record_registry_best_effort(root)
                return {"result_id": action["action_id"], "execution_status": step["execution"]["status"],
                        "scientific_status": "inconclusive", "blocker": "worker-state-needs-inspection"}
            time.sleep(.1)
    return outcome
