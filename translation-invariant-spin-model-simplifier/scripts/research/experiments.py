"""Reusable numerical jobs with immutable, content-checked evidence."""
from copy import deepcopy
from pathlib import Path
import time

from research.contracts import digest
from research.state import read_json, write_json


def cached_result(path, fingerprint, identity):
    from research.contracts import same_code_identity
    if not Path(path).exists():
        return None
    record = read_json(path)
    if record.get("code_identity") != identity and not same_code_identity(record.get("code_identity")):
        raise ValueError("invalid or incompatible comparison cache: " + str(path))
    if (record.get("job_fingerprint") != fingerprint or
            record.get("execution_status") != "succeeded" or
            record.get("evidence_digest") != digest({k: v for k, v in record.items() if k != "evidence_digest"})):
        raise ValueError("invalid or incompatible comparison cache: " + str(path))
    return record


def make_job(root, case, role, model, task, settings, identity, memory, reference_fingerprint=None):
    from research.adapters import capability_for
    import math
    cap = capability_for(model["model"], task, settings)
    if cap["status"] != "supported":
        raise ValueError(role + " experiment unsupported: " + cap["blocker"])
    solver_settings = deepcopy(settings)
    requested = solver_settings.get("max_memory_mb", memory)
    if (isinstance(requested, bool) or not isinstance(requested, (int, float)) or
            not math.isfinite(requested) or requested <= 0):
        raise ValueError("max_memory_mb must be positive and finite")
    solver_settings["max_memory_mb"] = min(float(requested), memory)
    fingerprint = digest({"model_id": model["model_id"], "task": task, "settings": solver_settings,
                          "reference": reference_fingerprint, "code_identity": identity})
    cache = str(Path(root) / "validation-cache" / (fingerprint + ".json"))
    missing = cached_result(cache, fingerprint, identity) is None
    return {"case_id": case, "role": role, "fingerprint": fingerprint,
            "cache": cache, "reference_fingerprint": reference_fingerprint,
            "inputs": {**model, "task": task, "settings": solver_settings, "capability": cap,
                       "code_identity": identity, "result_id": "job-" + fingerprint[:24]}}, missing


def execute_jobs(inputs, jobs):
    from research.adapters import run_calculation
    from research.contracts import same_code_identity
    directory = Path(inputs["work_directory"])
    completed, results, evidence, runs = {}, {}, [], 0
    for job in jobs:
        fingerprint = job["fingerprint"]
        result = completed.get(fingerprint) or cached_result(job["cache"], fingerprint, inputs["code_identity"])
        reused = result is not None
        if result is None:
            child = deepcopy(job["inputs"])
            reference = completed.get(job["reference_fingerprint"])
            if child["task"] == "spin_wave_spectrum" and (
                    reference is None or reference.get("scientific_status") != "usable_within_scope"):
                result = {"result_id": child["result_id"], "model_id": child["model_id"],
                          "task": child["task"], "execution_status": "not_started",
                          "scientific_status": "inconclusive", "calculation": {},
                          "blocker": "reference is not scientifically usable"}
            else:
                if not same_code_identity(inputs["code_identity"]):
                    raise RuntimeError("implementation changed during comparison")
                runs += 1
                write_json(directory / "comparison-progress.json", {"solver_runs": runs})
                child["reference"] = reference
                try:
                    result = run_calculation(child)
                except Exception as exc:
                    result = {"result_id": child["result_id"], "model_id": child["model_id"],
                              "task": child["task"], "execution_status": "failed",
                              "scientific_status": "inconclusive", "calculation": {},
                              "blocker": type(exc).__name__ + ": " + str(exc)}
                if not same_code_identity(inputs["code_identity"]):
                    raise RuntimeError("implementation changed during comparison")
                if result["execution_status"] == "succeeded":
                    result = {**result, "job_fingerprint": fingerprint, "finished_at": time.time()}
                    result["evidence_digest"] = digest(result)
                    write_json(job["cache"], result, exclusive=True)
        completed[fingerprint] = result
        results[(job["case_id"], job["role"])] = result
        path = directory / "evidence" / job["case_id"] / (job["role"] + ".json")
        write_json(path, result, exclusive=True)
        evidence.append({"case_id": job["case_id"], "role": job["role"], "path": str(path),
                         "reused": reused, "job_fingerprint": fingerprint,
                         "scientific_status": result["scientific_status"], "blocker": result.get("blocker")})
    return results, evidence, runs

