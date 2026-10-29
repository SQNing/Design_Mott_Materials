"""Durable supervisor and resource-bounded computation process (Linux)."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback

from research.state import process_identity, read_json, write_json


def failure(inputs, blocker, status="failed"):
    progress = Path(inputs.get("work_directory", "")) / "comparison-progress.json"
    counts = ({"solver_runs": read_json(progress)["solver_runs"] if progress.exists() else 0}
              if inputs["task"] in {"reduction_validation", "mechanism_test"} else {})
    return {"schema_version": "research-result/v1", "result_id": inputs["result_id"],
            "model_id": inputs["model_id"], "task": inputs["task"],
            "execution_status": status, "scientific_status": "inconclusive",
            "code_identity": inputs["code_identity"], "blocker": blocker,
            "finished_at": time.time(), "diagnostics": [], "scientific_scope": [],
            "suggested_actions": [], **counts}


def compute(directory, inputs):
    # Set limits before importing NumPy/SciPy. The stdlib-only supervisor remains
    # alive to record failure even if the numerical process runs out of memory.
    import resource
    memory = int(inputs["max_memory_mb"] * 1024 ** 2)
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    try:
        from research.contracts import code_identity
        if code_identity() != inputs["code_identity"]:
            raise RuntimeError("implementation/environment changed before calculation")
        from research.adapters import run_calculation
        result = run_calculation(inputs)
        if code_identity() != inputs["code_identity"]:
            raise RuntimeError("implementation/environment changed during calculation")
        result["calculation_fingerprint"] = inputs["calculation_fingerprint"]
        result["finished_at"] = time.time()
    except Exception as exc:
        traceback.print_exc()
        result = failure(inputs, type(exc).__name__ + ": " + str(exc))
    write_json(directory / "computation-result.json", result)


def supervise(directory, inputs):
    with (directory / "calculation.log").open("ab") as stream:
        child = subprocess.Popen([sys.executable, "-B", "-m", "research.worker",
                                  str(directory), "--compute"],
                                 stdin=subprocess.DEVNULL, stdout=stream,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        write_json(directory / "computation.json", {"worker": process_identity(child.pid),
                                                   "started_at": time.time()})
        try:
            child.wait(timeout=inputs["timeout"])
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
            write_json(directory / "result.json", failure(inputs, "wall-time-limit", "timed_out"))
            return
    output = directory / "computation-result.json"
    if output.exists():
        result = read_json(output)
    else:
        result = failure(inputs, "computation-exited-without-result (exit %s); inspect calculation.log" % child.returncode)
    write_json(directory / "result.json", result)


def main():
    directory = Path(sys.argv[1])
    inputs = read_json(directory / "input.json")
    if "--compute" in sys.argv[2:]:
        compute(directory, inputs)
    else:
        try:
            supervise(directory, inputs)
        except Exception as exc:
            traceback.print_exc()
            write_json(directory / "result.json", failure(inputs, "supervisor: " + str(exc)))


if __name__ == "__main__":
    main()
