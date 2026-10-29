"""Append-only model/step records with a small atomically updated index."""
import contextlib
import fcntl
import json
import os
import socket
import time
import uuid
from pathlib import Path

from research.contracts import json_safe


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value, *, exclusive=False):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(json_safe(value), indent=2, sort_keys=True, allow_nan=False) + "\n"
    if exclusive:
        with p.open("x", encoding="utf-8") as stream:
            stream.write(text)
        return
    temporary = p.with_name(p.name + ".tmp-" + uuid.uuid4().hex)
    with temporary.open("x", encoding="utf-8") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(str(temporary), str(p))


@contextlib.contextmanager
def locked(run_dir):
    root = Path(run_dir)
    root.mkdir(parents=True, exist_ok=True)
    with (root / "workflow.lock").open("a") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield root
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def event(root, value):
    with (Path(root) / "decisions.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(json_safe({"time": time.time(), **value}), sort_keys=True) + "\n")


def process_identity(pid):
    try:
        stat = Path("/proc/%s/stat" % pid).read_text()
        tail = stat[stat.rfind(")") + 2:].split()
        if tail[0] == "Z":
            return None
        return {"host": socket.gethostname(), "pid": int(pid), "start_ticks": tail[19]}
    except (OSError, IndexError):
        return None


def process_state(identity):
    if not identity or identity.get("host") != socket.gethostname():
        return "unknown"
    current = process_identity(identity["pid"])
    if current is None:
        return "missing"
    return "running" if current == identity else "missing"


def collect_steps(root, state):
    """Observe existing handles only. Observation never launches a replacement."""
    steps = []
    for action_id in state.get("steps", []):
        directory = Path(root) / "steps" / action_id
        execution = read_json(directory / "execution.json")
        result_path = directory / "result.json"
        if result_path.exists():
            result = read_json(result_path)
            execution["status"] = result["execution_status"]
            execution["finished_at"] = result.get("finished_at", execution.get("finished_at"))
            if "solver_runs" in result:
                execution["solver_runs"] = result["solver_runs"]
        elif execution.get("status") in {"pending", "running"}:
            live = process_state(execution.get("worker"))
            computation = directory / "computation.json"
            if live == "missing" and computation.exists():
                child = process_state(read_json(computation).get("worker"))
                if child in {"running", "unknown"}:
                    live = "unknown"
            execution["status"] = "running" if live == "running" else (
                "interrupted" if live == "missing" else "unknown")
            progress = directory / "comparison-progress.json"
            if execution["status"] == "interrupted" and progress.exists():
                execution["solver_runs"] = read_json(progress)["solver_runs"]
        steps.append({"action_id": action_id, "execution": execution,
                      "result": read_json(result_path) if result_path.exists() else None,
                      "action": read_json(directory / "action.json")})
    return steps


def compute_seconds(steps):
    now = time.time()
    return sum(max(0., (s["execution"].get("finished_at") or now) -
                      s["execution"].get("started_at", now))
               for s in steps if s["execution"].get("counted"))


def new_state(request):
    return {"schema_version": "research-state/v1", "request": request, "version": 0,
            "steps": [], "input_actions": {}, "assessments": [],
            "created_at": time.time(), "answer_status": "pending"}

