#!/usr/bin/env python3
"""Run a batch of independent research tasks and sync them to the registry."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.registry import default_registry_path, record_run
from research.workflow import (execute_research_action, inspect_research_task,
                               prepare_research_task)


def _load_batch(path):
    text = Path(path).read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("empty batch file")
    if text[0] in "[{":
        value = json.loads(text)
        if isinstance(value, list):
            return value
        if isinstance(value, dict) and "jobs" in value:
            return value["jobs"]
        return [value]
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _run_job(job):
    run_dir = Path(job["run_dir"]).expanduser().resolve()
    request = job["request"]
    actions = job.get("actions") or ([job["action"]] if job.get("action") else [])
    prepare_research_task(request, run_dir)
    action_results = []
    for action in actions:
        result = execute_research_action(run_dir, action, wait=True)
        action_results.append({
            "action_id": action.get("action_id"),
            "execution_status": result.get("execution_status"),
            "scientific_status": result.get("scientific_status"),
            "blocker": result.get("blocker"),
        })
    view = inspect_research_task(run_dir)
    registry_path = job.get("registry") or default_registry_path(run_dir=run_dir)
    entry = record_run(run_dir, registry_path)
    return {"run_dir": str(run_dir), "status": view["status"],
            "answer_status": view["answer_status"], "claim_level": entry.get("claim_level"),
            "solver_runs": view["solver_runs"], "compute_seconds": view["compute_seconds"],
            "actions": action_results, "registry": str(registry_path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True,
                        help="JSON/JSONL batch: jobs with run_dir, request and optional action/actions")
    parser.add_argument("--registry", help="override registry.jsonl for all jobs")
    parser.add_argument("--concurrency", type=int, default=1,
                        help="maximum concurrent run directories (default: 1)")
    args = parser.parse_args(argv)
    if args.concurrency < 1:
        print(json.dumps({"status": "invalid_request", "blocker": "concurrency must be >= 1"}))
        return 2
    try:
        jobs = _load_batch(args.batch)
        if args.registry:
            for job in jobs:
                job["registry"] = args.registry
        results, errors = [], []
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = {pool.submit(_run_job, job): job for job in jobs}
            for future in as_completed(futures):
                job = futures[future]
                try:
                    results.append(future.result())
                except (ValueError, OSError, KeyError) as exc:
                    errors.append({"run_dir": job.get("run_dir"), "blocker": str(exc)})
        results.sort(key=lambda item: item["run_dir"])
        print(json.dumps({"status": "ok" if not errors else "incomplete",
                          "schema_version": "research-batch/v1", "runs": results,
                          "errors": errors}, indent=2, ensure_ascii=False, allow_nan=False))
        return 0 if not errors else 2
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({"status": "invalid_request", "blocker": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
