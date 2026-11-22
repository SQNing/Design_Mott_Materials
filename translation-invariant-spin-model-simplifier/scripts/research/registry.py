"""Workspace-level append-only registry of research runs.

The registry is a JSONL event log (latest event per run_dir wins) so agents can
list/query/compare runs without opening every state.json. It is also the index
used by the cross-run fingerprint cache: each entry carries the step
fingerprints that may be reused by later runs with the same scoped code
identity.
"""
import fcntl
import json
import time
from pathlib import Path

from research.contracts import json_safe
from research.state import read_json

REGISTRY_VERSION = "research-registry/v1"


def default_registry_path(run_dir=None, workspace=None):
    if workspace is not None:
        return Path(workspace).expanduser().resolve() / "registry.jsonl"
    if run_dir is not None:
        return Path(run_dir).expanduser().resolve().parent / "registry.jsonl"
    return Path("registry.jsonl")


def _append(registry_path, value):
    path = Path(registry_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    with lock_path.open("a") as lock_stream:
        fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX)
        try:
            with path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(json_safe({"time": time.time(), **value}),
                                        sort_keys=True, ensure_ascii=False) + "\n")
        finally:
            fcntl.flock(lock_stream.fileno(), fcntl.LOCK_UN)


def _small_result(result):
    calculation = result.get("calculation") or {}
    static = (calculation.get("observables") or {}).get("static") or {}
    return {
        "result_id": result.get("result_id"),
        "task": result.get("task"),
        "execution_status": result.get("execution_status"),
        "scientific_status": result.get("scientific_status"),
        "claim_level": result.get("claim_level"),
        "energy": calculation.get("energy", static.get("energy")),
        "energy_per_site": calculation.get("energy_per_site"),
        "ordering_q": static.get("ordering_q"),
        "m2_ordering": static.get("m2_ordering"),
        "gaps": static.get("gaps"),
    }


def summarize_run(run_dir):
    """Build the registry entry for one run directory (read-only)."""
    from research.workflow import inspect_research_task  # local import: no cycle

    root = Path(run_dir).expanduser().resolve()
    view = inspect_research_task(root)
    request_path = root / "request.json"
    request = read_json(request_path) if request_path.is_file() else {}
    fingerprints = []
    results = []
    for step in view["steps"]:
        result = step.get("result") or {}
        if result:
            results.append(_small_result(result))
        fingerprint = result.get("calculation_fingerprint")
        if fingerprint:
            fingerprints.append({
                "fingerprint": fingerprint,
                "run_dir": str(root),
                "result_id": result.get("result_id"),
                "task": result.get("task"),
                "execution_status": result.get("execution_status"),
                "scientific_status": result.get("scientific_status"),
                "reusable": result.get("reusable", True),
            })
    claim_level = None
    if view.get("assessments"):
        claim_level = view["assessments"][-1].get("claim_level")
    return {
        "schema_version": REGISTRY_VERSION,
        "run_dir": str(root),
        "recorded_at": time.time(),
        "question": view.get("question", ""),
        "status": view.get("status"),
        "answer_status": view.get("answer_status"),
        "claim_level": claim_level,
        "model_id": (view.get("model") or {}).get("model_id"),
        "requested_tasks": view.get("requested_tasks", []),
        "phase_parameters": request.get("phase_parameters", {}),
        "solver_runs": view.get("solver_runs", 0),
        "compute_seconds": view.get("compute_seconds", 0.0),
        "step_count": len(view.get("steps", [])),
        "fingerprints": fingerprints,
        "results": results,
    }


def record_run(run_dir, registry_path=None):
    registry_path = registry_path or default_registry_path(run_dir=run_dir)
    entry = summarize_run(run_dir)
    _append(registry_path, {"type": "run_update", "entry": entry})
    return entry


def load_registry(registry_path):
    path = Path(registry_path).expanduser().resolve()
    if not path.is_file():
        return []
    latest = {}
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            value = json.loads(line)
            entry = value.get("entry")
            if entry and entry.get("run_dir"):
                latest[entry["run_dir"]] = entry
    return [latest[key] for key in sorted(latest)]


def query_runs(registry_path, *, status=None, claim_level=None, model_id=None,
               task=None, text=None):
    entries = load_registry(registry_path)
    def keep(entry):
        if status and entry.get("status") != status:
            return False
        if claim_level and entry.get("claim_level") != claim_level:
            return False
        if model_id and entry.get("model_id") != model_id:
            return False
        if task and task not in entry.get("requested_tasks", []) and not any(
                r.get("task") == task for r in entry.get("results", [])):
            return False
        if text and text not in json.dumps(entry, ensure_ascii=False, sort_keys=True):
            return False
        return True
    return [entry for entry in entries if keep(entry)]


def find_fingerprint(registry_path, fingerprint):
    """Latest registry candidate for a calculation fingerprint."""
    candidates = []
    for entry in load_registry(registry_path):
        for item in entry.get("fingerprints", []):
            if item.get("fingerprint") == fingerprint:
                candidates.append((entry.get("recorded_at", 0.0), item))
    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0])
    return candidates[-1][1]


def sync_runs(run_dirs, registry_path):
    synced, errors = [], []
    for run_dir in run_dirs:
        try:
            synced.append(record_run(run_dir, registry_path))
        except (ValueError, OSError, KeyError) as exc:
            errors.append({"run_dir": str(run_dir), "blocker": str(exc)})
    return {"schema_version": REGISTRY_VERSION, "registry": str(registry_path),
            "synced": len(synced), "errors": errors}
