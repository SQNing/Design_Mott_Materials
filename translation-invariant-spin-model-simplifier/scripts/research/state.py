"""Append-only model/step records with a small atomically updated index."""
import contextlib
import fcntl
import json
import math
import os
import socket
import subprocess
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


_PROC_AVAILABLE = Path("/proc").is_dir()


def _proc_identity(pid):
    try:
        stat = Path("/proc/%s/stat" % pid).read_text()
        tail = stat[stat.rfind(")") + 2:].split()
        if tail[0] == "Z":
            return None
        return {"host": socket.gethostname(), "pid": int(pid), "start_ticks": tail[19]}
    except (OSError, IndexError):
        return None


def _psutil_identity(pid):
    """ps(1) can be sandbox-blocked; psutil's create_time is equally stable."""
    try:
        import psutil
    except ImportError:
        return "unavailable"
    try:
        process = psutil.Process(int(pid))
    except (psutil.NoSuchProcess, ValueError):
        return None
    try:
        if process.status() == psutil.STATUS_ZOMBIE:
            return None
        start = process.create_time()
    except psutil.Error:
        return None
    return {"host": socket.gethostname(), "pid": int(pid),
            "start": "%.6f" % float(start)}


def _ps_identity(pid):
    """ps(1) fallback: its start time is fixed for a process's lifetime."""
    try:
        completed = subprocess.run(
            ["ps", "-o", "pid=,stat=,lstart=", "-p", str(int(pid))],
            check=False, capture_output=True, text=True, timeout=10)
    except Exception:
        # ps unavailable (sandbox, missing binary, or monkeypatched subprocess):
        # identity unknown is safer than crashing supervision.
        return None
    if completed.returncode != 0:
        return None
    lines = [line.split(None, 2) for line in completed.stdout.splitlines() if line.strip()]
    if len(lines) != 1 or len(lines[0]) != 3:
        return None
    field_pid, field_stat, field_start = lines[0]
    try:
        if int(field_pid) != int(pid):
            return None
    except ValueError:
        return None
    if field_stat.startswith("Z"):
        return None
    return {"host": socket.gethostname(), "pid": int(pid), "start": field_start.strip()}


def process_identity(pid):
    if _PROC_AVAILABLE:
        return _proc_identity(pid)
    identity = _psutil_identity(pid)
    if identity != "unavailable":
        return identity
    return _ps_identity(pid)


def process_state(identity):
    if not identity or identity.get("host") != socket.gethostname():
        return "unknown"
    current = process_identity(identity["pid"])
    if current is None:
        return "missing"
    return "running" if current == identity else "missing"


def _seconds(value):
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError("recorded compute duration must be finite and nonnegative")
    return value


def _execution_seconds(execution):
    if not execution.get("counted"):
        return 0.
    if "charged_seconds" in execution:
        return _seconds(execution["charged_seconds"])
    if execution.get("finished_at") is not None:
        return max(0., execution["finished_at"] - execution.get("started_at", execution["finished_at"]))
    if execution.get("status") == "interrupted":
        # Legacy steps lack checkpoints. Reserve their originally allocated
        # duration rather than inventing a termination time from today's clock.
        if "timeout_seconds" not in execution:
            raise ValueError("interrupted step has no recorded duration or allocated timeout")
        return _seconds(execution["timeout_seconds"])
    return max(0., time.time() - execution.get("started_at", time.time()))


def _time_accounting(directory, execution, result):
    """Read elapsed-time evidence; never rewrite archived execution records."""
    if not execution.get("counted"):
        return {"seconds": 0., "kind": "not_charged", "uncertain": False}
    if result is not None and result.get("compute_seconds") is not None:
        return {"seconds": _seconds(result["compute_seconds"]), "kind": "measured", "uncertain": False}
    if execution.get("finished_at") is not None:
        return {"seconds": _execution_seconds(execution), "kind": "recorded_finish", "uncertain": False}
    child_path = directory / "computation-result.json"
    if child_path.is_file():
        child = read_json(child_path)
        if child.get("compute_seconds") is not None:
            return {"seconds": _seconds(child["compute_seconds"]), "kind": "completed_child", "uncertain": False}
        if child.get("finished_at") is not None:
            elapsed = max(0., child["finished_at"] - execution["started_at"])
            return {"seconds": elapsed, "kind": "completed_child", "uncertain": False}
    timing_path = directory / "timing.json"
    if timing_path.is_file():
        timing = read_json(timing_path)
        if timing.get("result_id", directory.name) != directory.name:
            raise ValueError("timing checkpoint belongs to another action")
        terminal = bool(timing.get("terminal"))
        return {"seconds": _seconds(timing["elapsed_seconds"]),
                "kind": "measured" if terminal else "last_checkpoint",
                "uncertain": not terminal,
                "updated_at": timing.get("updated_at"),
                "note": ("Recorded through completion." if terminal else
                         "Recorded through the last checkpoint; an interruption tail is unmeasured.")}
    interrupted = execution.get("status") == "interrupted"
    return {"seconds": _execution_seconds(execution),
            "kind": "legacy_timeout_reservation" if interrupted else "live_wall_clock",
            "uncertain": interrupted,
            **({"note": "No legacy timing checkpoint: charge the fixed original timeout reservation, not idle time."}
               if interrupted else {})}


def collect_steps(root, state):
    """Observe existing handles only. Observation never launches a replacement."""
    steps = []
    for action_id in state.get("steps", []):
        directory = Path(root) / "steps" / action_id
        execution = read_json(directory / "execution.json")
        result_path = directory / "result.json"
        result = None
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
        accounting = _time_accounting(directory, execution, result)
        execution["charged_seconds"] = accounting["seconds"]
        execution["time_accounting"] = accounting
        steps.append({"action_id": action_id, "execution": execution,
                      "result": result,
                      "action": read_json(directory / "action.json")})
    return steps


def compute_seconds(steps):
    return sum(_execution_seconds(step["execution"]) for step in steps)


def new_state(request):
    return {"schema_version": "research-state/v1", "request": request, "version": 0,
            "steps": [], "input_actions": {}, "assessments": [],
            "created_at": time.time(), "answer_status": "pending"}

